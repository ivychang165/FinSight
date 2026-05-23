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

    def fetch_report_page(self, company_id: str, year: int, season: int,
                          report_type: str = 'consolidated') -> BeautifulSoup:
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
        except requests.RequestException as e:
            raise ConnectionError(f"無法連線至 MOPS XBRL 平台：{e}")

        # XBRL page declares charset=big5; try big5 first, fall back to utf-8
        try:
            content = resp.content.decode('big5', errors='replace')
        except (UnicodeDecodeError, LookupError):
            content = resp.content.decode('utf-8', errors='replace')

        if '查無資料' in content or len(content) < 500:
            raise ValueError(
                f"查無 {company_id} 於 {year} 年第 {season} 季的財務報表。"
                "請確認公司代號、年度及季度是否正確。"
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

        results['_meta'] = {
            'company_id': company_id,
            'year': year,
            'season': season,
            'source': 'MOPS XBRL',
        }

        return results

    def search_company(self, keyword: str) -> list:
        common_companies = {
            '2330': '台積電', '2317': '鴻海', '2454': '聯發科',
            '2303': '聯電', '2882': '國泰金', '2881': '富邦金',
            '1301': '台塑', '1303': '南亞', '2002': '中鋼',
            '2886': '兆豐金', '2891': '中信金', '3711': '日月光投控',
            '2308': '台達電', '2412': '中華電', '1216': '統一',
            '2603': '長榮', '2609': '陽明', '5880': '合庫金',
            '2892': '第一金', '2884': '玉山金', '2357': '華碩',
            '3008': '大立光', '2301': '光寶科', '6505': '台塑化',
            '2207': '和泰車', '5871': '中租-KY', '2345': '智邦',
            '3037': '欣興', '2379': '瑞昱', '4904': '遠傳',
        }
        results = []
        for code, name in common_companies.items():
            if keyword in code or keyword in name:
                results.append({'code': code, 'name': name})
        return results
