"""
FinancialMapper — 財務科目標準化對照模組

將不同公司財報中的科目名稱對應到統一的標準欄位，
支援完全匹配、部分匹配、代碼匹配。
"""

import re
import pandas as pd


ACCOUNT_MAP = {
    # ===== 損益表 =====
    'revenue': {
        'label': '營業收入', 'source': 'income_statement',
        'keywords': ['營業收入合計', '營業收入淨額', '收入合計', '營業收入'],
        'codes': ['4000'],
        'partial': [],
    },
    'operating_cost': {
        'label': '營業成本', 'source': 'income_statement',
        'keywords': ['營業成本合計', '營業成本'],
        'codes': ['5000'],
        'partial': [],
    },
    'gross_profit': {
        'label': '營業毛利', 'source': 'income_statement',
        'keywords': ['營業毛利（毛損）', '營業毛利（毛損）淨額', '營業毛利'],
        'codes': ['5900', '5950'],
        'partial': [],
    },
    'operating_expense': {
        'label': '營業費用', 'source': 'income_statement',
        'keywords': ['營業費用合計', '營業費用'],
        'codes': ['6000'],
        'partial': [],
    },
    'operating_income': {
        'label': '營業利益', 'source': 'income_statement',
        'keywords': ['營業利益（損失）', '營業利益', '營業淨利'],
        'codes': ['6900'],
        'partial': [],
    },
    'interest_expense': {
        'label': '利息費用', 'source': 'income_statement',
        'keywords': ['利息費用', '財務成本'],
        'codes': ['7050'],
        'partial': [],
    },
    'pretax_income': {
        'label': '稅前淨利', 'source': 'income_statement',
        'keywords': ['繼續營業單位稅前淨利（淨損）', '稅前淨利（淨損）',
                     '稅前淨利', '繼續營業單位稅前損益'],
        'codes': ['7900'],
        'partial': [],
    },
    'net_income': {
        'label': '本期淨利', 'source': 'income_statement',
        'keywords': ['本期淨利（淨損）', '本期淨利', '本期稅後淨利'],
        'codes': ['8200'],
        'partial': [],
    },
    'net_income_parent': {
        'label': '淨利歸屬母公司', 'source': 'income_statement',
        'keywords': ['淨利（損）歸屬於母公司業主', '歸屬於母公司業主之淨利',
                     '淨利歸屬於母公司業主'],
        'codes': ['8610'],
        'partial': ['歸屬於母公司業主'],
    },
    'eps': {
        'label': '每股盈餘', 'source': 'income_statement',
        'keywords': ['基本每股盈餘'],
        'codes': ['9750'],
        'partial': [],
    },

    # ===== 資產負債表 =====
    'cash': {
        'label': '現金及約當現金', 'source': 'balance_sheet',
        'keywords': ['現金及約當現金'],
        'codes': ['1100'],
        'partial': [],
    },
    'accounts_receivable': {
        'label': '應收帳款', 'source': 'balance_sheet',
        'keywords': ['應收帳款淨額', '應收帳款'],
        'codes': ['1150', '1170'],
        'partial': [],
    },
    'notes_receivable': {
        'label': '應收票據', 'source': 'balance_sheet',
        'keywords': ['應收票據淨額', '應收票據'],
        'codes': ['1110'],
        'partial': [],
    },
    'inventory': {
        'label': '存貨', 'source': 'balance_sheet',
        'keywords': ['存貨', '存貨淨額'],
        'codes': ['1300', '130X'],
        'partial': [],
    },
    'current_assets': {
        'label': '流動資產合計', 'source': 'balance_sheet',
        'keywords': ['流動資產合計', '流動資產總計', '流動資產總額'],
        'codes': ['1X00', '11XX'],
        'partial': [],
    },
    'total_assets': {
        'label': '資產總計', 'source': 'balance_sheet',
        'keywords': ['資產總計', '資產總額'],
        'codes': ['1XXX'],
        'partial': [],
    },
    'accounts_payable': {
        'label': '應付帳款', 'source': 'balance_sheet',
        'keywords': ['應付帳款'],
        'codes': ['2100', '2170'],
        'partial': [],
    },
    'notes_payable': {
        'label': '應付票據', 'source': 'balance_sheet',
        'keywords': ['應付票據'],
        'codes': ['2110'],
        'partial': [],
    },
    'current_liabilities': {
        'label': '流動負債合計', 'source': 'balance_sheet',
        'keywords': ['流動負債合計', '流動負債總計', '流動負債總額'],
        'codes': ['2X00', '21XX'],
        'partial': [],
    },
    'total_liabilities': {
        'label': '負債總計', 'source': 'balance_sheet',
        'keywords': ['負債總計', '負債總額', '負債合計'],
        'codes': ['2XXX'],
        'partial': [],
    },
    'equity_parent': {
        'label': '歸屬母公司權益', 'source': 'balance_sheet',
        'keywords': ['歸屬於母公司業主之權益合計', '歸屬於母公司業主之權益'],
        'codes': ['3X00'],
        'partial': ['歸屬於母公司業主之權益'],
    },
    'total_equity': {
        'label': '權益總計', 'source': 'balance_sheet',
        'keywords': ['權益總計', '權益總額', '股東權益合計', '權益合計'],
        'codes': ['3XXX'],
        'partial': [],
    },

    # ===== 現金流量表 =====
    'operating_cashflow': {
        'label': '營業活動現金流量', 'source': 'cash_flow',
        'keywords': ['營業活動之淨現金流入（流出）', '營業活動之淨現金流入',
                     '營業活動之淨現金流出'],
        'codes': ['AAAA'],
        'partial': [],
    },
    'capex': {
        'label': '資本支出', 'source': 'cash_flow',
        'keywords': ['取得不動產、廠房及設備', '購置不動產廠房及設備',
                     '取得不動產廠房及設備'],
        'codes': ['B02700'],
        'partial': ['取得不動產'],
    },
    'investing_cashflow': {
        'label': '投資活動現金流量', 'source': 'cash_flow',
        'keywords': ['投資活動之淨現金流入（流出）', '投資活動之淨現金流入',
                     '投資活動之淨現金流出'],
        'codes': ['BBBB'],
        'partial': [],
    },
    'financing_cashflow': {
        'label': '籌資活動現金流量', 'source': 'cash_flow',
        'keywords': ['籌資活動之淨現金流入（流出）', '籌資活動之淨現金流入',
                     '籌資活動之淨現金流出'],
        'codes': ['CCCC'],
        'partial': [],
    },
    'depreciation': {
        'label': '折舊費用', 'source': 'cash_flow',
        'keywords': ['折舊費用'],
        'codes': ['A20100'],
        'partial': [],
    },
}


class FinancialMapper:
    """將原始財報科目名稱對應到標準化欄位"""

    def __init__(self):
        self.account_map = ACCOUNT_MAP

    def map_single_account(self, account_name: str, code: str = '',
                           statement_type: str = '') -> str | None:
        account_clean = self._clean_account_name(account_name)
        code_clean = str(code).strip()

        candidates = {
            k: v for k, v in self.account_map.items()
            if not statement_type or v.get('source', '') == statement_type
        }

        for std_key, mapping in candidates.items():
            for kw in mapping['keywords']:
                if kw == account_clean:
                    return std_key

        for std_key, mapping in candidates.items():
            if code_clean and code_clean in mapping.get('codes', []):
                return std_key

        for std_key, mapping in candidates.items():
            for partial in mapping.get('partial', []):
                if partial and partial in account_clean:
                    return std_key

        return None

    def extract_financials(self, df: pd.DataFrame, statement_type: str) -> dict:
        results = {}
        account_col = self._find_account_column(df)
        code_col = 'code' if 'code' in df.columns else None
        value_cols = self._find_value_columns(df)

        if account_col is None or not value_cols:
            return results

        for _, row in df.iterrows():
            account_name = str(row.get(account_col, ''))
            code = str(row.get(code_col, '')) if code_col else ''
            std_key = self.map_single_account(account_name, code, statement_type)

            if std_key is None:
                continue

            if std_key in results:
                continue

            values = {}
            for vc in value_cols:
                val = row.get(vc)
                if val is not None and not pd.isna(val):
                    period_label = self._parse_period_label(vc)
                    values[period_label] = float(val)

            if values:
                results[std_key] = {
                    'label': self.account_map[std_key]['label'],
                    'values': values,
                    'raw_account': account_name,
                    'code': code,
                }

        return results

    def _clean_account_name(self, name: str) -> str:
        name = re.sub(r'[A-Za-z0-9\s\(\)\/\-\.,]+', '', str(name))
        name = re.sub(r'[\s　]+', '', name)
        name = name.strip()
        return name

    def _find_account_column(self, df: pd.DataFrame) -> str | None:
        for col in df.columns:
            if col in ('account', 'account_zh'):
                return col
            if '會計' in str(col) or 'Accounting' in str(col):
                return col
        return None

    def _find_value_columns(self, df: pd.DataFrame) -> list:
        skip = {'code', 'account', 'account_zh', 'account_en'}
        result = []
        for col in df.columns:
            if col in skip:
                continue
            if df[col].dtype in ('float64', 'int64', 'float32'):
                result.append(col)
                continue
            try:
                numeric_count = pd.to_numeric(df[col], errors='coerce').notna().sum()
                if numeric_count > len(df) * 0.3:
                    result.append(col)
            except Exception:
                pass
        return result

    def _parse_period_label(self, col_name: str) -> str:
        year_match = re.search(r'(\d{4})', str(col_name))
        if year_match:
            return f"Y{year_match.group(1)}"
        return str(col_name)
