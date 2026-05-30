"""
MOPSFetcher — 從公開資訊觀測站新版 JSON API 擷取財務報表

新版 MOPS（2025 年改版）使用 REST API 回傳 JSON，
取代舊版 XBRL HTML 頁面。
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

# 三大報表對應的 API endpoint
STATEMENT_ENDPOINTS = {
    'balance_sheet': 't164sb03',
    'income_statement': 't164sb04',
    'cash_flow': 't164sb05',
}


def _roc_to_western(text: str) -> str:
    """將文字中的民國年轉為西元年（例如 '113年12月31日' → '2024年12月31日'）"""
    def replace_year(m):
        roc_year = int(m.group(1))
        return str(roc_year + 1911)
    return re.sub(r'(\d{2,3})(?=年)', replace_year, text)


class MOPSFetcher:
    """從 MOPS 新版 JSON API 擷取合併/個別財務報表"""

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

    @property
    def report_type_used(self):
        """回傳實際成功擷取的報表類型 ('consolidated' 或 'individual')"""
        return self._report_type_used

    # ── API 呼叫 ──────────────────────────────────────────────────

    def _call_api(self, endpoint: str, company_id: str,
                  year: int, season: int) -> dict | None:
        """
        呼叫 MOPS JSON API，回傳 result dict 或 None。
        year 為西元年，會自動轉換為民國年。
        """
        roc_year = str(year - 1911)

        payload = {
            'companyId': str(company_id),
            'dataType': '2',       # 自訂年季
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

    # ── JSON → DataFrame 轉換 ────────────────────────────────────

    def _extract_period_names(self, titles: list) -> list[str]:
        """從 titles 結構中提取期間名稱（轉為西元年）"""
        periods = []
        for title_obj in titles[1:]:  # 跳過第一個（會計項目）
            name = title_obj.get('main', '')
            periods.append(_roc_to_western(name))
        return periods

    def _result_to_dataframe(self, result: dict,
                             statement_type: str) -> pd.DataFrame:
        """將 API result 轉換為 FinancialMapper 相容的 DataFrame"""
        titles = result.get('titles', [])
        report_list = result.get('reportList', [])

        if not report_list:
            return pd.DataFrame()

        periods = self._extract_period_names(titles)
        is_cashflow = (statement_type == 'cash_flow')

        rows = []
        for row_data in report_list:
            if not row_data or len(row_data) < 2:
                continue

            account_name = row_data[0].strip()
            # 移除全形空格前綴（用於層級縮排）
            account_clean = account_name.replace('　', '').strip()

            if not account_clean:
                continue

            values = {}
            if is_cashflow:
                # 現金流量表：[名稱, 值1, 值2]
                for idx, period in enumerate(periods):
                    col_idx = 1 + idx
                    if col_idx < len(row_data):
                        values[period] = self._parse_number(row_data[col_idx])
            else:
                # 資產負債表/損益表：[名稱, 值1, %1, 值2, %2]
                for idx, period in enumerate(periods):
                    col_idx = 1 + idx * 2  # 跳過百分比欄
                    if col_idx < len(row_data):
                        values[period] = self._parse_number(row_data[col_idx])

            # 至少要有一個非 None 的值，或者是父層科目（全是 None 也保留）
            rows.append({
                'code': '',
                'account_zh': account_clean,
                'account_en': '',
                **values,
            })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        return df

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

    # ── 主要擷取方法 ─────────────────────────────────────────────

    def fetch_all_statements(self, company_id: str, year: int,
                             season: int) -> dict:
        """
        擷取三大財務報表，回傳 dict 包含 DataFrame。

        回傳格式與舊版相同：
        {
            'balance_sheet': DataFrame,
            'income_statement': DataFrame,
            'cash_flow': DataFrame,
            '_meta': { ... },
            '_warnings': [ ... ],  # 若有部分失敗
        }
        """
        results = {}
        errors = []
        api_result_meta = None  # 取任一成功的 result 來讀 meta

        for st_key, endpoint in STATEMENT_ENDPOINTS.items():
            result = self._call_api(endpoint, company_id, year, season)
            if result is not None:
                df = self._result_to_dataframe(result, st_key)
                results[st_key] = df
                if api_result_meta is None:
                    api_result_meta = result
            else:
                errors.append(f"{st_key}: {self._last_debug}")
                results[st_key] = pd.DataFrame()

        # 全部都失敗
        if api_result_meta is None:
            debug_msg = f"\n\n🔍 診斷：{self._last_debug}" if self._last_debug else ""
            raise ValueError(
                f"查無 {company_id} 於 {year} 年第 {season} 季的財務報表。\n\n"
                f"可能原因：\n"
                f"① 該公司未在 MOPS 平台申報此期報表\n"
                f"② 公司代號輸入錯誤\n"
                f"③ 該年度/季度尚未公告\n\n"
                f"建議：請至公開資訊觀測站(mops.twse.com.tw)確認該公司是否有公告此期報表。"
                f"{debug_msg}"
            )

        if errors:
            results['_warnings'] = errors

        # 組裝 meta
        report_type_raw = api_result_meta.get('reportType', '合併')
        if '個別' in report_type_raw:
            self._report_type_used = 'individual'
        else:
            self._report_type_used = 'consolidated'

        report_label = '合併報表' if self._report_type_used == 'consolidated' else '個別報表'
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
        """
        根據代號取得公司名稱。
        先查本地 DB，若找不到則查 TWSE API。
        """
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
