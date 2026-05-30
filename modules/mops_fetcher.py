"""
MOPSFetcher — 從公開資訊觀測站新版 JSON API 擷取財務報表

新版 MOPS（2025 年改版）使用 REST API 回傳 JSON，
取代舊版 XBRL HTML 頁面。

若 MOPS API 無法存取（如海外 IP 被阻擋），自動切換至
FinMind 開放資料 API 作為備用來源。
"""

import re
import logging
import requests
import urllib3
import pandas as pd

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 新版 MOPS API 基底 URL
API_BASE_URL = "https://mops.twse.com.tw/mops/api/"

# FinMind API
FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"

# 三大報表對應的 MOPS API endpoint
STATEMENT_ENDPOINTS = {
    'balance_sheet': 't164sb03',
    'income_statement': 't164sb04',
    'cash_flow': 't164sb05',
}

# FinMind 資料集對應
FINMIND_DATASETS = {
    'balance_sheet': 'TaiwanStockBalanceSheet',
    'income_statement': 'TaiwanStockFinancialStatements',
    'cash_flow': 'TaiwanStockCashFlowsStatement',
}

# 季末日期
SEASON_END_DATES = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}


def _roc_to_western(text: str) -> str:
    """將文字中的民國年轉為西元年（例如 '113年12月31日' → '2024年12月31日'）"""
    def replace_year(m):
        roc_year = int(m.group(1))
        return str(roc_year + 1911)
    return re.sub(r'(\d{2,3})(?=年)', replace_year, text)


class MOPSFetcher:
    """從 MOPS 新版 JSON API 擷取合併/個別財務報表，支援 FinMind 備援"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Content-Type': 'application/json',
            'Origin': 'https://mops.twse.com.tw',
            'Referer': 'https://mops.twse.com.tw/mops/',
            'Accept': 'application/json',
        })
        self._report_type_used = None
        self._last_debug = ''
        self._data_source = 'MOPS API'

    @property
    def report_type_used(self):
        """回傳實際成功擷取的報表類型 ('consolidated' 或 'individual')"""
        return self._report_type_used

    # ══════════════════════════════════════════════════════════════
    #  MOPS API（主要來源）
    # ══════════════════════════════════════════════════════════════

    def _call_mops_api(self, endpoint: str, company_id: str,
                       year: int, season: int) -> dict | None:
        """呼叫 MOPS JSON API，回傳 result dict 或 None。"""
        roc_year = str(year - 1911)

        payload = {
            'companyId': str(company_id),
            'dataType': '2',
            'year': roc_year,
            'season': str(season),
            'subsidiaryCompanyId': '',
        }

        url = f"{API_BASE_URL}{endpoint}"
        try:
            resp = self.session.post(url, json=payload, verify=False, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("MOPS API request failed [%s]: %s", endpoint, e)
            self._last_debug = f"MOPS API 連線失敗 ({endpoint}): {e}"
            return None

        try:
            data = resp.json()
        except ValueError:
            logger.warning("MOPS API invalid JSON [%s]", endpoint)
            self._last_debug = f"MOPS API 回傳非 JSON 格式 ({endpoint})"
            return None

        if data.get('code') != 200:
            msg = data.get('message', '未知錯誤')
            logger.info("MOPS API error [%s]: %s", endpoint, msg)
            self._last_debug = f"MOPS API 回傳錯誤 ({endpoint}): {msg}"
            return None

        result = data.get('result')
        if not result or not result.get('reportList'):
            self._last_debug = f"MOPS API 查無資料 ({endpoint})"
            return None

        return result

    def _mops_result_to_dataframe(self, result: dict,
                                  statement_type: str) -> pd.DataFrame:
        """將 MOPS API result 轉換為 FinancialMapper 相容的 DataFrame"""
        titles = result.get('titles', [])
        report_list = result.get('reportList', [])

        if not report_list:
            return pd.DataFrame()

        periods = []
        for title_obj in titles[1:]:
            name = title_obj.get('main', '')
            periods.append(_roc_to_western(name))

        is_cashflow = (statement_type == 'cash_flow')

        rows = []
        for row_data in report_list:
            if not row_data or len(row_data) < 2:
                continue

            account_name = row_data[0].strip()
            account_clean = account_name.replace('　', '').strip()
            if not account_clean:
                continue

            values = {}
            if is_cashflow:
                for idx, period in enumerate(periods):
                    col_idx = 1 + idx
                    if col_idx < len(row_data):
                        values[period] = self._parse_number(row_data[col_idx])
            else:
                for idx, period in enumerate(periods):
                    col_idx = 1 + idx * 2
                    if col_idx < len(row_data):
                        values[period] = self._parse_number(row_data[col_idx])

            rows.append({
                'code': '',
                'account_zh': account_clean,
                'account_en': '',
                **values,
            })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def _try_fetch_mops(self, company_id: str, year: int,
                        season: int) -> dict | None:
        """嘗試用 MOPS API 擷取全部報表，成功回傳 results dict，失敗回傳 None"""
        results = {}
        api_result_meta = None

        for st_key, endpoint in STATEMENT_ENDPOINTS.items():
            result = self._call_mops_api(endpoint, company_id, year, season)
            if result is not None:
                df = self._mops_result_to_dataframe(result, st_key)
                results[st_key] = df
                if api_result_meta is None:
                    api_result_meta = result
            else:
                results[st_key] = pd.DataFrame()

        if api_result_meta is None:
            return None

        report_type_raw = api_result_meta.get('reportType', '合併')
        self._report_type_used = 'individual' if '個別' in report_type_raw else 'consolidated'
        self._data_source = 'MOPS API'

        company_name = api_result_meta.get('companyAbbreviation', '')
        if not company_name:
            company_name = self.get_company_name(company_id)

        results['_meta'] = {
            'company_id': company_id,
            'company_name': company_name,
            'year': year,
            'season': season,
            'source': 'MOPS API',
            'report_type': self._report_type_used,
            'report_label': '合併報表' if self._report_type_used == 'consolidated' else '個別報表',
        }

        return results

    # ══════════════════════════════════════════════════════════════
    #  FinMind API（備用來源）
    # ══════════════════════════════════════════════════════════════

    def _call_finmind_api(self, dataset: str, company_id: str,
                          start_date: str, end_date: str) -> list | None:
        """呼叫 FinMind API，回傳 data list 或 None"""
        try:
            resp = requests.get(FINMIND_API_URL, params={
                'dataset': dataset,
                'data_id': str(company_id),
                'start_date': start_date,
                'end_date': end_date,
            }, timeout=20)

            data = resp.json()
            if data.get('status') != 200:
                logger.warning("FinMind API error [%s]: %s",
                               dataset, data.get('msg'))
                return None

            records = data.get('data', [])
            if not records:
                return None

            return records
        except Exception as e:
            logger.warning("FinMind API failed [%s]: %s", dataset, e)
            return None

    def _finmind_to_dataframe(self, records: list, statement_type: str,
                              target_date: str, prev_date: str,
                              year: int, season: int) -> pd.DataFrame:
        """
        將 FinMind API 回傳的記錄轉為 FinancialMapper 相容的 DataFrame。

        資產負債表：快照 → 直接取 target_date 的值。
        現金流量表：FinMind 已是累積值 → 直接取 target_date 的值。
        損益表：FinMind 是季度值 → 加總從 Q1 到目標季度。
        FinMind 值以「元」為單位，轉為「千元」以符合 MOPS 格式。
        """
        is_income_statement = (statement_type == 'income_statement')

        # 過濾掉百分比欄位
        records = [r for r in records if not r['type'].endswith('_per')]

        if is_income_statement:
            # 損益表：FinMind 是季度資料，需要加總
            current_dates = [
                f"{year}-{SEASON_END_DATES[s]}"
                for s in range(1, season + 1)
            ]
            prev_dates = [
                f"{year - 1}-{SEASON_END_DATES[s]}"
                for s in range(1, season + 1)
            ]

            current_records = {}
            for r in records:
                if r['date'] in current_dates:
                    name = r['origin_name']
                    current_records[name] = current_records.get(name, 0) + r['value'] / 1000

            prev_records = {}
            for r in records:
                if r['date'] in prev_dates:
                    name = r['origin_name']
                    prev_records[name] = prev_records.get(name, 0) + r['value'] / 1000
        else:
            # 資產負債表（快照）& 現金流量表（已是累積值）：
            # 直接取 target_date 和 prev_date
            current_records = {r['origin_name']: r['value'] / 1000
                               for r in records if r['date'] == target_date}
            prev_records = {r['origin_name']: r['value'] / 1000
                            for r in records if r['date'] == prev_date}

        # 合併所有科目名稱
        all_accounts = list(dict.fromkeys(
            list(current_records.keys()) + list(prev_records.keys())
        ))

        if not all_accounts:
            return pd.DataFrame()

        # 欄位名稱（西元年格式，讓 _parse_period_label 能提取年份）
        if statement_type == 'balance_sheet':
            curr_col = f"{year}年{SEASON_END_DATES[season].replace('-', '月')}日"
            prev_col = f"{year - 1}年{SEASON_END_DATES[season].replace('-', '月')}日"
        else:
            curr_col = f"{year}年度" if season == 4 else f"{year}年Q{season}"
            prev_col = f"{year - 1}年度" if season == 4 else f"{year - 1}年Q{season}"

        rows = []
        for acct in all_accounts:
            rows.append({
                'code': '',
                'account_zh': acct,
                'account_en': '',
                curr_col: current_records.get(acct),
                prev_col: prev_records.get(acct),
            })

        return pd.DataFrame(rows)

    def _try_fetch_finmind(self, company_id: str, year: int,
                           season: int) -> dict | None:
        """嘗試用 FinMind API 擷取全部報表"""
        logger.info("Falling back to FinMind API for %s/%d/Q%d",
                     company_id, year, season)

        target_date = f"{year}-{SEASON_END_DATES[season]}"
        prev_date = f"{year - 1}-{SEASON_END_DATES[season]}"

        # 查詢範圍：前一年 Q1 到今年目標季度
        start_date = f"{year - 1}-01-01"
        end_date = f"{year}-12-31"

        results = {}
        any_success = False

        for st_key, dataset in FINMIND_DATASETS.items():
            records = self._call_finmind_api(
                dataset, company_id, start_date, end_date
            )
            if records:
                df = self._finmind_to_dataframe(
                    records, st_key, target_date, prev_date, year, season
                )
                results[st_key] = df
                if not df.empty:
                    any_success = True
            else:
                results[st_key] = pd.DataFrame()

        if not any_success:
            return None

        self._report_type_used = 'consolidated'
        self._data_source = 'FinMind'

        company_name = self.get_company_name(company_id)

        results['_meta'] = {
            'company_id': company_id,
            'company_name': company_name,
            'year': year,
            'season': season,
            'source': 'FinMind 開放資料',
            'report_type': 'consolidated',
            'report_label': '合併報表',
        }

        return results

    # ══════════════════════════════════════════════════════════════
    #  主要擷取方法（MOPS → FinMind 備援）
    # ══════════════════════════════════════════════════════════════

    def fetch_all_statements(self, company_id: str, year: int,
                             season: int) -> dict:
        """
        擷取三大財務報表，回傳 dict 包含 DataFrame。
        優先使用 MOPS API，若失敗自動切換 FinMind API。
        """
        # 嘗試 MOPS API
        results = self._try_fetch_mops(company_id, year, season)
        if results is not None:
            logger.info("MOPS API success for %s/%d/Q%d",
                         company_id, year, season)
            return results

        # MOPS 失敗，嘗試 FinMind
        logger.info("MOPS API failed, trying FinMind for %s/%d/Q%d",
                     company_id, year, season)
        results = self._try_fetch_finmind(company_id, year, season)
        if results is not None:
            logger.info("FinMind API success for %s/%d/Q%d",
                         company_id, year, season)
            return results

        # 全部失敗
        raise ValueError(
            f"查無 {company_id} 於 {year} 年第 {season} 季的財務報表。\n\n"
            f"可能原因：\n"
            f"① 該公司未在 MOPS 平台申報此期報表\n"
            f"② 公司代號輸入錯誤\n"
            f"③ 該年度/季度尚未公告\n\n"
            f"建議：請至公開資訊觀測站(mops.twse.com.tw)確認該公司是否有公告此期報表。"
        )

    # ══════════════════════════════════════════════════════════════
    #  共用工具
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _parse_number(value) -> object:
        """解析數值字串（支援千分位逗號、括號表示負數）"""
        if pd.isna(value):
            return None
        s = str(value).strip()
        if s == '' or s == '-' or s == '0':
            if s == '0':
                return 0.0
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

    # ── TWSE 即時搜尋 API ──────────────────────────────────────────

    @staticmethod
    def _query_twse_api(keyword: str) -> list:
        """查詢 TWSE 即時代碼搜尋 API"""
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
                if re.fullmatch(r'\d{4}', code):
                    results.append({'code': code, 'name': name})
            return results
        except Exception:
            return []

    def search_company(self, keyword: str) -> list:
        """搜尋公司（支援代號或名稱）"""
        from modules.company_data import search_companies
        keyword = keyword.strip()
        if not keyword:
            return []

        local = search_companies(keyword)
        local_codes = {m['code'] for m in local}

        api_results = self._query_twse_api(keyword)

        combined = list(local)
        for item in api_results:
            if item['code'] not in local_codes:
                combined.append(item)
                local_codes.add(item['code'])

        return combined[:20]

    @staticmethod
    def get_company_name(company_id: str) -> str:
        """根據代號取得公司名稱"""
        from modules.company_data import get_company_name
        local_name = get_company_name(company_id)
        if local_name:
            return local_name

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
