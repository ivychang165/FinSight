"""
MOPSFetcher — 從公開資訊觀測站 XBRL 資訊平台擷取財務報表
"""

import requests
import warnings
import re
import pandas as pd
from bs4 import BeautifulSoup

warnings.filterwarnings('ignore')

XBRL_BASE_URL = "https://mopsov.twse.com.tw/server-java/t164sb01"

REPORT_IDS = {
    'individual': 'A',
    'consolidated': 'C',
}

TABLE_ANCHORS = {
    'balance_sheet': 'BalanceSheet',
    'income_statement': 'StatementOfComprehensiveIncome',
    'cash_flow': 'StatementsOfCashFlows',
}


class MOPSFetcher:
    """從 MOPS XBRL 資訊平台擷取合併財務報表"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        self._soup = None
        self._company_id = None
        self._year = None
        self._season = None
        self._report_type_used = None  # 記錄實際使用的報表類型

    @property
    def report_type_used(self):
        """回傳實際成功擷取的報表類型 ('consolidated' 或 'individual')"""
        return self._report_type_used

    def _try_fetch_page(self, company_id: str, year: int, season: int,
                        report_type: str) -> str | None:
        """嘗試擷取指定類型的報表頁面，回傳 HTML 內容或 None"""
        params = {
            'step': '1',
            'CO_ID': str(company_id),
            'SYEAR': str(year),
            'SSEASON': str(season),
            'REPORT_ID': REPORT_IDS.get(report_type, 'C'),
        }
        try:
            resp = self.session.get(XBRL_BASE_URL, params=params, verify=False, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return None

        try:
            content = resp.content.decode('big5', errors='replace')
        except (UnicodeDecodeError, LookupError):
            content = resp.content.decode('utf-8', errors='replace')

        # 檢查是否有實際資料
        if '查無資料' in content or len(content) < 500:
            return None

        # 進一步檢查：確認頁面包含至少一個報表錨點
        has_table = any(
            anchor_id in content
            for anchor_id in TABLE_ANCHORS.values()
        )
        if not has_table:
            return None

        return content

    def fetch_report_page(self, company_id: str, year: int, season: int,
                          report_type: str = 'consolidated') -> BeautifulSoup:
        # 先嘗試使用者指定的報表類型
        content = self._try_fetch_page(company_id, year, season, report_type)

        if content is not None:
            self._report_type_used = report_type
        else:
            # 自動嘗試另一種報表類型作為 fallback
            fallback_type = 'individual' if report_type == 'consolidated' else 'consolidated'
            content = self._try_fetch_page(company_id, year, season, fallback_type)

            if content is not None:
                self._report_type_used = fallback_type
            else:
                # 兩種都沒資料
                raise ValueError(
                    f"查無 {company_id} 於 {year} 年第 {season} 季的財務報表（合併報表與個別報表皆無資料）。\n\n"
                    f"可能原因：\n"
                    f"① 該公司未在 XBRL 平台申報此期報表\n"
                    f"② 公司代號輸入錯誤\n"
                    f"③ 該年度/季度尚未公告\n\n"
                    f"建議：請至公開資訊觀測站(mops.twse.com.tw)確認該公司是否有公告此期報表。"
                )

        self._soup = BeautifulSoup(content, 'html.parser')
        self._company_id = company_id
        self._year = year
        self._season = season
        return self._soup

    def _parse_table_near_anchor(self, anchor_id: str) -> pd.DataFrame:
        if self._soup is None:
            raise RuntimeError("請先呼叫 fetch_report_page() 取得報表頁面")

        anchor = self._soup.find('div', id=anchor_id)
        if anchor is None:
            anchor = self._soup.find('a', attrs={'name': anchor_id})
        if anchor is None:
            raise ValueError(f"找不到報表區段：{anchor_id}")

        table = anchor.find_next('table')
        if table is None:
            raise ValueError(f"找不到 {anchor_id} 對應的表格")

        rows = table.find_all('tr')
        if len(rows) < 3:
            raise ValueError(f"{anchor_id} 表格資料不足")

        header_row = rows[1]
        headers = [cell.get_text(strip=True) for cell in header_row.find_all(['td', 'th'])]

        data_rows = []
        for row in rows[2:]:
            cells = row.find_all(['td', 'th'])
            cell_texts = [c.get_text(strip=True) for c in cells]
            if len(cell_texts) >= 2:
                data_rows.append(cell_texts)

        if not data_rows:
            raise ValueError(f"{anchor_id} 沒有可解析的資料列")

        max_cols = max(len(r) for r in data_rows)
        if len(headers) < max_cols:
            headers = headers + [f'col_{i}' for i in range(len(headers), max_cols)]

        normalized_rows = []
        for r in data_rows:
            while len(r) < max_cols:
                r.append('')
            normalized_rows.append(r[:max_cols])

        df = pd.DataFrame(normalized_rows, columns=headers[:max_cols])
        df = self._clean_dataframe(df)
        return df

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        col_map = {}
        for col in df.columns:
            lower = col.lower()
            if 'code' in lower or '代號' in col or '代碼' in col:
                col_map[col] = 'code'
            elif 'accounting' in lower or '會計' in col or '項目' in col:
                col_map[col] = 'account'
            else:
                col_map[col] = col

        df = df.rename(columns=col_map)

        if 'account' in df.columns:
            df['account_zh'] = df['account'].apply(self._extract_chinese)
            df['account_en'] = df['account'].apply(self._extract_english)

        value_cols = [c for c in df.columns if c not in ('code', 'account', 'account_zh', 'account_en')]
        for col in value_cols:
            df[col] = df[col].apply(self._parse_number)

        if 'code' in df.columns:
            df['code'] = df['code'].astype(str).str.strip()

        return df

    @staticmethod
    def _extract_chinese(text: str) -> str:
        chinese = re.findall(r'[一-鿿　-〿＀-￯（）]+', str(text))
        result = ''.join(chinese).strip()
        result = re.sub(r'^[\s　]+', '', result)
        return result

    @staticmethod
    def _extract_english(text: str) -> str:
        cleaned = re.sub(r'[一-鿿　-〿＀-￯（）]+', '', str(text))
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @staticmethod
    def _parse_number(value) -> object:
        if pd.isna(value):
            return None
        s = str(value).strip()
        if s == '' or s == '-':
            return None

        is_negative = s.startswith('(') and s.endswith(')')
        if is_negative:
            s = s[1:-1]

        s = s.replace(',', '').replace('，', '').replace(' ', '')

        try:
            num = float(s)
            return -num if is_negative else num
        except ValueError:
            return None

    def fetch_balance_sheet(self) -> pd.DataFrame:
        return self._parse_table_near_anchor(TABLE_ANCHORS['balance_sheet'])

    def fetch_income_statement(self) -> pd.DataFrame:
        return self._parse_table_near_anchor(TABLE_ANCHORS['income_statement'])

    def fetch_cash_flow(self) -> pd.DataFrame:
        return self._parse_table_near_anchor(TABLE_ANCHORS['cash_flow'])

    def fetch_all_statements(self, company_id: str, year: int, season: int) -> dict:
        self.fetch_report_page(company_id, year, season)

        results = {}
        errors = []

        for name, anchor in TABLE_ANCHORS.items():
            try:
                results[name] = self._parse_table_near_anchor(anchor)
            except (ValueError, RuntimeError) as e:
                errors.append(f"{name}: {e}")
                results[name] = pd.DataFrame()

        if errors:
            results['_warnings'] = errors

        report_label = '合併報表' if self._report_type_used == 'consolidated' else '個別報表'
        results['_meta'] = {
            'company_id': company_id,
            'year': year,
            'season': season,
            'source': 'MOPS XBRL',
            'report_type': self._report_type_used,
            'report_label': report_label,
        }

        return results

    def search_company(self, keyword: str) -> list:
        """搜尋公司（支援代號或名稱），委派給 company_data 模組"""
        from modules.company_data import search_companies
        return search_companies(keyword)

    @staticmethod
    def get_company_name(company_id: str) -> str:
        """根據代號取得公司名稱"""
        from modules.company_data import get_company_name
        return get_company_name(company_id)
