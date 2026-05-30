"""
MOPSFetcher — 從公開資訊觀測站 XBRL 資訊平台擷取財務報表
"""

import time
import requests
import urllib3
import re
import logging
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://mopsov.twse.com.tw/server-java/t164sb01',
            'Connection': 'keep-alive',
        })
        self._soup = None
        self._company_id = None
        self._year = None
        self._season = None
        self._report_type_used = None  # 記錄實際使用的報表類型
        self._session_warmed = False   # 是否已預熱 session

    def _warm_session(self):
        """先訪問 MOPS 首頁以建立合法 session cookie，
        避免海外 IP 直接請求報表被擋。"""
        if self._session_warmed:
            return
        try:
            self.session.get(
                XBRL_BASE_URL,
                params={'step': '0'},
                verify=False, timeout=15,
            )
            logger.info("MOPS session warm-up done, cookies: %s",
                        list(self.session.cookies.keys()))
        except requests.RequestException as e:
            logger.warning("MOPS session warm-up failed: %s", e)
        self._session_warmed = True

    @property
    def report_type_used(self):
        """回傳實際成功擷取的報表類型 ('consolidated' 或 'individual')"""
        return self._report_type_used

    def _try_fetch_page(self, company_id: str, year: int, season: int,
                        report_type: str,
                        max_retries: int = 3) -> str | None:
        """嘗試擷取指定類型的報表頁面，回傳 HTML 內容或 None

        內建重試機制：當 MOPS 回傳不完整內容時（常見於海外 IP），
        會自動重試最多 max_retries 次，每次間隔遞增。
        """
        self._warm_session()

        params = {
            'step': '1',
            'CO_ID': str(company_id),
            'SYEAR': str(year),
            'SSEASON': str(season),
            'REPORT_ID': REPORT_IDS.get(report_type, 'C'),
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(
                    XBRL_BASE_URL, params=params,
                    verify=False, timeout=45,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.warning("MOPS request failed [%s] attempt %d/%d: %s",
                               report_type, attempt, max_retries, e)
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                    continue
                return None

            logger.info("MOPS response [%s] attempt %d: status=%s, bytes=%d",
                         report_type, attempt, resp.status_code, len(resp.content))

            try:
                content = resp.content.decode('big5', errors='replace')
            except (UnicodeDecodeError, LookupError):
                content = resp.content.decode('utf-8', errors='replace')

            # 檢查是否有實際資料
            if '查無資料' in content:
                logger.info("MOPS no data [%s]: len=%d", report_type, len(content))
                return None  # 明確查無資料，不需重試

            if len(content) < 500:
                # 回傳過短 → 可能是 MOPS 暫時性問題，值得重試
                logger.warning("MOPS incomplete response [%s] attempt %d/%d: len=%d",
                               report_type, attempt, max_retries, len(content))
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                    continue
                return None

            # 進一步檢查：新格式有錨點 ID，舊格式（2013-2018）有「會計項目」表格
            has_new_format = any(anchor_id in content for anchor_id in TABLE_ANCHORS.values())
            has_old_format = '會計項目' in content
            if not has_new_format and not has_old_format:
                logger.warning("MOPS format not recognized [%s]: len=%d", report_type, len(content))
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                    continue
                return None

            return content

        return None

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

    # ── 新格式解析（2019+，有錨點 ID）──────────────────────────────

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
        # recursive=False：只取直接子節點，避免抓到下層 row 的 cell
        headers = [cell.get_text(strip=True) for cell in header_row.find_all(['td', 'th'], recursive=False)]

        data_rows = []
        for row in rows[2:]:
            cells = row.find_all(['td', 'th'], recursive=False)
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

    # ── 舊格式解析（2013–2018，無錨點，<tr> 未關閉）──────────────

    def _is_old_format(self) -> bool:
        """2013–2018 的舊版 XBRL 頁面沒有錨點 ID"""
        if self._soup is None:
            return False
        return (
            self._soup.find('div', id='BalanceSheet') is None and
            self._soup.find('a', attrs={'name': 'BalanceSheet'}) is None
        )

    def _find_old_format_table(self, statement_type: str):
        """
        舊格式：從所有 table 中找出對應報表的 table element。
        判斷邏輯：
          - 資產負債表：第一欄為「會計項目」，其他欄為日期點（年月日）
          - 損益表  ：第一欄為「會計項目」，其他欄為日期段（含「年度」或「至」）
                     且第一筆資料列包含「收入」或「銷貨」
          - 現金流量表：同上，但第一筆資料列包含「現金」或「活動」
        """
        tables = self._soup.find_all('table')
        candidates = {'balance_sheet': [], 'income_statement': [], 'cash_flow': []}

        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue
            header_cells = rows[0].find_all(['td', 'th'], recursive=False)
            headers = [c.get_text(strip=True) for c in header_cells]
            if not headers or '會計項目' not in headers[0]:
                continue

            # 判斷欄位是日期點（YYYY年MM月DD日）還是日期段（年度 / 至）
            is_date_range = any(
                '年度' in h or '至' in h
                for h in headers[1:]
            )

            if not is_date_range:
                candidates['balance_sheet'].append(table)
            else:
                # 看前幾列資料判斷是損益還是現金流
                data_texts = ''
                for row in rows[2:8]:
                    cells = row.find_all(['td', 'th'], recursive=False)
                    data_texts += ' '.join(c.get_text(strip=True) for c in cells)

                if '現金' in data_texts or '活動' in data_texts:
                    candidates['cash_flow'].append(table)
                else:
                    candidates['income_statement'].append(table)

        # 若同類型有多個 table，取第一個（最完整的）
        found = candidates.get(statement_type, [])
        if not found:
            raise ValueError(f"舊格式頁面找不到「{statement_type}」報表")
        return found[0]

    def _parse_old_format_table(self, statement_type: str) -> pd.DataFrame:
        """
        解析舊格式（2013–2018）財務報表 table。
        使用 recursive=False 避免 <tr> 未關閉造成的巢狀問題。
        資產負債表若有 3 個日期欄（IFRS 首次採用），只取前兩欄。
        """
        table = self._find_old_format_table(statement_type)
        rows = table.find_all('tr')
        if not rows:
            raise ValueError(f"舊格式 {statement_type} 表格為空")

        # 取標題行（row 0）
        header_cells = rows[0].find_all(['td', 'th'], recursive=False)
        headers = [c.get_text(strip=True) for c in header_cells]

        # 如果有 3 個日期欄（2013 年 IFRS 過渡期），只保留前 2 個日期
        if len(headers) == 4:   # ['會計項目', date1, date2, transition_date]
            headers = headers[:3]
            trim_cols = 3
        else:
            trim_cols = len(headers)

        data_rows = []
        for row in rows[1:]:    # 從 row 1 開始（跳過標題）
            cells = row.find_all(['td', 'th'], recursive=False)
            if not cells:
                continue
            texts = [c.get_text(strip=True) for c in cells[:trim_cols]]
            # 補足欄位
            while len(texts) < trim_cols:
                texts.append('')
            # 跳過只有標題文字的分段列（如「資產負債表」、「損益表」）
            if len(texts) == 1:
                continue
            if texts[0] and any(texts[1:]):    # 至少要有名稱和一個值
                data_rows.append(texts)
            elif texts[0] and all(t == '' for t in texts[1:]):
                # 父層科目（無數值），也保留（mapper 可能用到名稱）
                data_rows.append(texts)

        if not data_rows:
            raise ValueError(f"舊格式 {statement_type} 沒有可解析的資料")

        # 舊格式沒有獨立的 code 欄，加一個空的
        col_names = ['code'] + headers
        rows_with_code = [[''] + r for r in data_rows]

        df = pd.DataFrame(rows_with_code, columns=col_names)
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
        old_format = self._is_old_format()

        for name in TABLE_ANCHORS:
            try:
                if old_format:
                    results[name] = self._parse_old_format_table(name)
                else:
                    results[name] = self._parse_table_near_anchor(TABLE_ANCHORS[name])
            except (ValueError, RuntimeError) as e:
                errors.append(f"{name}: {e}")
                results[name] = pd.DataFrame()

        if errors:
            results['_warnings'] = errors

        # 標示舊格式（供前端顯示提示）
        if old_format:
            results['_old_format'] = True

        report_label = '合併報表' if self._report_type_used == 'consolidated' else '個別報表'

        # 自動取得公司名稱（不阻斷流程）
        company_name = self.get_company_name(company_id)

        results['_meta'] = {
            'company_id': company_id,
            'company_name': company_name,
            'year': year,
            'season': season,
            'source': 'MOPS XBRL',
            'report_type': self._report_type_used,
            'report_label': report_label,
        }

        return results

    # ── TWSE 即時搜尋 API ──────────────────────────────────────────

    @staticmethod
    def _query_twse_api(keyword: str) -> list:
        """
        查詢 TWSE 即時代碼搜尋 API。
        僅保留 4 位數字的正股代碼（過濾掉權證、ETF 等）。
        """
        try:
            url = "https://www.twse.com.tw/rwd/zh/api/codeQuery"
            resp = requests.get(url, params={"query": keyword}, timeout=5)
            data = resp.json()
            suggestions = data.get("suggestions", [])
            results = []
            for s in suggestions:
                if s == "(無符合之代碼或名稱)":
                    continue
                parts = s.split("\t")
                if len(parts) < 2:
                    continue
                code = parts[0].strip()
                name = parts[1].strip()
                # 只保留 4 位數字的正股代碼（權證為 6 位數，ETF代碼另計）
                # 4 位純數字 = 一般上市櫃公司正股
                if re.fullmatch(r'\d{4}', code):
                    results.append({'code': code, 'name': name})
            return results
        except Exception:
            return []

    def search_company(self, keyword: str) -> list:
        """
        搜尋公司（支援代號或名稱）。
        策略：本地資料庫（即時）＋ TWSE 官方 API（完整）合併去重。
        """
        from modules.company_data import search_companies
        keyword = keyword.strip()
        if not keyword:
            return []

        # 先查本地資料庫（快速）
        local = search_companies(keyword)
        local_codes = {m['code'] for m in local}

        # 再查 TWSE API（完整，但需網路）
        api_results = self._query_twse_api(keyword)

        # 合併：本地優先，API 補充
        combined = list(local)
        for item in api_results:
            if item['code'] not in local_codes:
                combined.append(item)
                local_codes.add(item['code'])

        return combined[:20]

    @staticmethod
    def get_company_name(company_id: str) -> str:
        """
        根據代號取得公司名稱。
        先查本地 DB，若找不到則查 TWSE API。
        """
        from modules.company_data import get_company_name
        local_name = get_company_name(company_id)
        if local_name:
            return local_name

        # 查 TWSE API
        try:
            url = "https://www.twse.com.tw/rwd/zh/api/codeQuery"
            resp = requests.get(url, params={"query": company_id}, timeout=5)
            data = resp.json()
            for s in data.get("suggestions", []):
                parts = s.split("\t")
                if len(parts) >= 2 and parts[0].strip() == company_id:
                    return parts[1].strip()
        except Exception:
            pass
        return ''
