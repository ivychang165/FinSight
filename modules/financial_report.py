"""
FinancialReport — 統整所有財務報表資料的核心資料結構
"""

import pandas as pd


class FinancialReport:
    """封裝一間公司某期財務報表的所有結構化資料"""

    def __init__(self, company_id: str, year: int, season: int):
        self.company_id = company_id
        self.year = year
        self.season = season
        self.raw_statements = {}
        self.mapped_data = {}
        self.warnings = []
        self._flat_cache = None

    def set_raw_statements(self, statements: dict):
        self.raw_statements = statements
        if '_warnings' in statements:
            self.warnings.extend(statements['_warnings'])

    def set_mapped_data(self, mapped: dict):
        self.mapped_data.update(mapped)
        self._flat_cache = None

    def get_value(self, key: str, period: str = 'current') -> float | None:
        flat = self._get_flat_values()
        if key not in flat:
            return None
        values = flat[key]['values']

        sorted_periods = sorted(values.keys(), reverse=True)
        if period == 'current' and sorted_periods:
            return values[sorted_periods[0]]
        elif period == 'previous' and len(sorted_periods) > 1:
            return values[sorted_periods[1]]
        elif period in values:
            return values[period]
        return None

    def get_current_and_previous(self, key: str) -> tuple:
        return self.get_value(key, 'current'), self.get_value(key, 'previous')

    def get_average(self, key: str) -> float | None:
        current, previous = self.get_current_and_previous(key)
        if current is not None and previous is not None:
            return (current + previous) / 2
        return current

    def _get_flat_values(self) -> dict:
        if self._flat_cache is not None:
            return self._flat_cache
        self._flat_cache = {}
        for source_data in self.mapped_data.values():
            if isinstance(source_data, dict):
                for key, item in source_data.items():
                    if isinstance(item, dict) and 'values' in item:
                        self._flat_cache[key] = item
        return self._flat_cache

    def get_label(self, key: str) -> str:
        flat = self._get_flat_values()
        if key in flat:
            return flat[key].get('label', key)
        return key

    def available_keys(self) -> list:
        return list(self._get_flat_values().keys())

    def validate_balance_sheet(self, tolerance_rate: float = 0.01) -> dict:
        total_assets = self.get_value('total_assets')
        total_liabilities = self.get_value('total_liabilities')
        total_equity = self.get_value('total_equity')

        result = {'valid': True, 'message': '', 'details': {}}

        if total_assets is None:
            result['valid'] = False
            result['message'] = '缺少「資產總計」欄位'
            return result

        if total_liabilities is not None and total_equity is not None:
            expected = total_liabilities + total_equity
            diff = abs(total_assets - expected)
            tolerance = abs(total_assets) * tolerance_rate

            result['details'] = {
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'total_equity': total_equity,
                'liabilities_plus_equity': expected,
                'difference': diff,
            }

            if diff > tolerance:
                result['valid'] = False
                result['message'] = (
                    f'資產負債不平衡：資產 {total_assets:,.0f} ≠ '
                    f'負債 {total_liabilities:,.0f} + 權益 {total_equity:,.0f}'
                )
            else:
                result['message'] = '資產負債表平衡檢查通過'

        return result

    def completeness_check(self) -> dict:
        critical_keys = ['revenue', 'net_income', 'total_assets', 'total_equity', 'total_liabilities', 'operating_cashflow']
        important_keys = ['gross_profit', 'operating_income', 'current_assets', 'current_liabilities', 'inventory', 'accounts_receivable', 'capex']

        flat = self._get_flat_values()
        missing_critical, missing_important, found = [], [], []

        for key in critical_keys:
            label = self.get_label(key) # 動態獲取中文標籤
            if key in flat:
                found.append(label)
            else:
                missing_critical.append(label)
        for key in important_keys:
            label = self.get_label(key) # 動態獲取中文標籤
            if key in flat:
                found.append(label)
            else:
                missing_important.append(label)

        total = len(critical_keys) + len(important_keys)
        score = len(found) / total if total > 0 else 0

        return {
            'score': score,
            'found': found,
            'missing_critical': missing_critical,
            'missing_important': missing_important,
        }

    def summary_dict(self) -> dict:
        flat = self._get_flat_values()
        summary = {}
        for key, item in flat.items():
            vals = item.get('values', {})
            sorted_periods = sorted(vals.keys(), reverse=True)
            if sorted_periods:
                summary[key] = {
                    'label': item.get('label', key),
                    'current': vals[sorted_periods[0]],
                    'previous': vals[sorted_periods[1]] if len(sorted_periods) > 1 else None,
                }
        return summary
