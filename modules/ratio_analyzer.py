"""
RatioAnalyzer — 財務比率分析引擎

四大面向：獲利能力、償債能力、營運效率、現金流
加上杜邦分析。

注意：本系統以年度（Q4）資料為最佳分析基準。
若使用季度資料，部分週轉率與報酬率為累計數，可能需年化後解讀。
"""

from modules.financial_report import FinancialReport


def safe_divide(numerator, denominator) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


class RatioAnalyzer:
    """根據 FinancialReport 計算所有財務比率"""

    def __init__(self, report: FinancialReport):
        self.report = report
        self._ratios = {}
        self._confidence_notes = []

    def analyze_all(self) -> dict:
        self._ratios = {}
        self._confidence_notes = []       # 每次重算時清空，避免累積
        self._ratios['profitability'] = self._profitability()
        self._ratios['solvency'] = self._solvency()
        self._ratios['efficiency'] = self._efficiency()
        self._ratios['cashflow'] = self._cashflow()
        self._ratios['dupont'] = self._dupont()
        return self._ratios

    def get_ratios(self) -> dict:
        if not self._ratios:
            self.analyze_all()
        return self._ratios

    # ── 輔助：None-safe 檢查 ──

    @staticmethod
    def _has_values(*values) -> bool:
        """檢查所有值皆非 None（0 和負數視為有效值）"""
        return all(v is not None for v in values)

    @staticmethod
    def _sum_optional(*values) -> float | None:
        """加總非 None 的值；全部為 None 時回傳 None"""
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        return sum(valid)

    # ── 獲利能力 ──

    def _profitability(self) -> dict:
        r = self.report
        revenue = r.get_value('revenue')
        gross_profit = r.get_value('gross_profit')
        operating_cost = r.get_value('operating_cost')
        net_income = r.get_value('net_income')
        net_income_parent = r.get_value('net_income_parent')
        avg_equity = r.get_average('total_equity')
        avg_assets = r.get_average('total_assets')

        if gross_profit is None and revenue is not None and operating_cost is not None:
            gross_profit = revenue - operating_cost

        profit_for_ratios = net_income_parent if net_income_parent is not None else net_income

        gross_margin = safe_divide(gross_profit, revenue)
        net_margin = safe_divide(profit_for_ratios, revenue)
        roe = safe_divide(profit_for_ratios, avg_equity)
        roa = safe_divide(profit_for_ratios, avg_assets)

        _, prev_equity = r.get_current_and_previous('total_equity')
        _, prev_assets = r.get_current_and_previous('total_assets')

        confidence = 'high'
        if prev_equity is None or prev_assets is None:
            confidence = 'medium'
            self._confidence_notes.append('缺少前期資料，ROE/ROA 使用期末值計算')

        return {
            'gross_margin': self._build_ratio(
                '毛利率', gross_margin,
                f'{gross_profit:,.0f} ÷ {revenue:,.0f}'
                if self._has_values(gross_profit, revenue) else None,
                'percent'
            ),
            'net_margin': self._build_ratio(
                '淨利率', net_margin,
                f'{profit_for_ratios:,.0f} ÷ {revenue:,.0f}'
                if self._has_values(profit_for_ratios, revenue) else None,
                'percent'
            ),
            'roe': self._build_ratio(
                'ROE 股東權益報酬率', roe,
                f'{profit_for_ratios:,.0f} ÷ {avg_equity:,.0f}'
                if self._has_values(profit_for_ratios, avg_equity) else None,
                'percent', confidence=confidence
            ),
            'roa': self._build_ratio(
                'ROA 資產報酬率', roa,
                f'{profit_for_ratios:,.0f} ÷ {avg_assets:,.0f}'
                if self._has_values(profit_for_ratios, avg_assets) else None,
                'percent', confidence=confidence
            ),
        }

    # ── 償債能力 ──

    def _solvency(self) -> dict:
        r = self.report
        current_assets = r.get_value('current_assets')
        current_liabilities = r.get_value('current_liabilities')
        total_liabilities = r.get_value('total_liabilities')
        total_assets = r.get_value('total_assets')
        operating_income = r.get_value('operating_income')
        interest_expense = r.get_value('interest_expense')

        current_ratio = safe_divide(current_assets, current_liabilities)
        debt_ratio = safe_divide(total_liabilities, total_assets)

        interest_coverage = None
        interest_note = None
        if interest_expense is not None and interest_expense != 0:
            interest_coverage = safe_divide(operating_income, abs(interest_expense))

        return {
            'current_ratio': self._build_ratio(
                '流動比率', current_ratio,
                f'{current_assets:,.0f} ÷ {current_liabilities:,.0f}'
                if self._has_values(current_assets, current_liabilities) else None,
                'times'
            ),
            'debt_ratio': self._build_ratio(
                '負債比率', debt_ratio,
                f'{total_liabilities:,.0f} ÷ {total_assets:,.0f}'
                if self._has_values(total_liabilities, total_assets) else None,
                'percent'
            ),
            'interest_coverage': self._build_ratio(
                '利息保障倍數', interest_coverage,
                f'{operating_income:,.0f} ÷ {abs(interest_expense):,.0f}'
                if self._has_values(operating_income, interest_expense) and interest_expense != 0
                else None,
                'times', note=interest_note
            ),
        }

    # ── 營運效率 ──

    def _efficiency(self) -> dict:
        r = self.report
        revenue = r.get_value('revenue')
        operating_cost = r.get_value('operating_cost')
        avg_assets = r.get_average('total_assets')
        avg_inventory = r.get_average('inventory')
        avg_receivable = self._get_avg_receivable()
        avg_payable = self._get_avg_payable()

        asset_turnover = safe_divide(revenue, avg_assets)
        inventory_turnover = safe_divide(operating_cost, avg_inventory)
        receivable_turnover = safe_divide(revenue, avg_receivable)

        inv_note = None
        if avg_inventory is not None and avg_inventory < 1000:
            inv_note = '此公司可能屬服務業，存貨指標參考性較低'

        inventory_days = safe_divide(365, inventory_turnover)
        receivable_days = safe_divide(365, receivable_turnover)

        payable_turnover = safe_divide(operating_cost, avg_payable)
        payable_days = safe_divide(365, payable_turnover)

        cash_cycle = None
        if self._has_values(inventory_days, receivable_days, payable_days):
            cash_cycle = inventory_days + receivable_days - payable_days

        return {
            'asset_turnover': self._build_ratio(
                '總資產週轉率', asset_turnover, None, 'times'
            ),
            'inventory_turnover': self._build_ratio(
                '存貨週轉率', inventory_turnover, None, 'times', note=inv_note
            ),
            'receivable_turnover': self._build_ratio(
                '應收帳款週轉率', receivable_turnover, None, 'times'
            ),
            'cash_cycle': self._build_ratio(
                '現金循環天數', cash_cycle, None, 'days'
            ),
        }

    def _get_avg_receivable(self) -> float | None:
        r = self.report
        curr_total = self._sum_optional(
            r.get_value('accounts_receivable', 'current'),
            r.get_value('notes_receivable', 'current'),
        )
        prev_total = self._sum_optional(
            r.get_value('accounts_receivable', 'previous'),
            r.get_value('notes_receivable', 'previous'),
        )
        if curr_total is None:
            return None
        if prev_total is None:
            return curr_total
        return (curr_total + prev_total) / 2

    def _get_avg_payable(self) -> float | None:
        r = self.report
        curr_total = self._sum_optional(
            r.get_value('accounts_payable', 'current'),
            r.get_value('notes_payable', 'current'),
        )
        prev_total = self._sum_optional(
            r.get_value('accounts_payable', 'previous'),
            r.get_value('notes_payable', 'previous'),
        )
        if curr_total is None:
            return None
        if prev_total is None:
            return curr_total
        return (curr_total + prev_total) / 2

    # ── 現金流 ──

    def _cashflow(self) -> dict:
        r = self.report
        op_cf = r.get_value('operating_cashflow')
        capex = r.get_value('capex')
        net_income = r.get_value('net_income')

        fcf = None
        if self._has_values(op_cf, capex):
            fcf = op_cf - abs(capex)

        earnings_quality = None
        eq_note = None
        if net_income is not None and net_income != 0 and op_cf is not None:
            if net_income < 0:
                eq_note = '本期虧損，此指標不具參考意義'
            else:
                earnings_quality = op_cf / net_income

        return {
            'operating_cashflow': self._build_ratio(
                '營業活動現金流量', op_cf, None, 'amount'
            ),
            'fcf': self._build_ratio(
                '自由現金流 FCF', fcf,
                f'{op_cf:,.0f} - {abs(capex):,.0f}'
                if self._has_values(op_cf, capex) else None,
                'amount'
            ),
            'earnings_quality': self._build_ratio(
                '盈餘品質比', earnings_quality,
                f'{op_cf:,.0f} ÷ {net_income:,.0f}'
                if self._has_values(op_cf, net_income) and net_income > 0 else None,
                'times', note=eq_note
            ),
        }

    # ── 杜邦分析 ──

    def _dupont(self) -> dict:
        r = self.report
        # 嚴謹的 None 判斷：0 也是有效值，不能被 or 跳過
        net_income_parent = r.get_value('net_income_parent')
        net_income = net_income_parent if net_income_parent is not None else r.get_value('net_income')
        revenue = r.get_value('revenue')
        avg_assets = r.get_average('total_assets')
        avg_equity = r.get_average('total_equity')

        net_margin = safe_divide(net_income, revenue)
        asset_turnover = safe_divide(revenue, avg_assets)
        equity_multiplier = safe_divide(avg_assets, avg_equity)

        roe_dupont = None
        if self._has_values(net_margin, asset_turnover, equity_multiplier):
            roe_dupont = net_margin * asset_turnover * equity_multiplier

        return {
            'net_margin': self._build_ratio('淨利率', net_margin, None, 'percent'),
            'asset_turnover': self._build_ratio('總資產週轉率', asset_turnover, None, 'times'),
            'equity_multiplier': self._build_ratio('權益乘數', equity_multiplier, None, 'times'),
            'roe_dupont': self._build_ratio('ROE（杜邦）', roe_dupont, None, 'percent'),
        }

    # ── 輔助：建立標準比率 dict ──

    @staticmethod
    def _build_ratio(name: str, value, formula: str | None,
                     unit: str, confidence: str = 'high',
                     note: str | None = None) -> dict:
        return {
            'name': name,
            'value': value,
            'formula': formula,
            'unit': unit,
            'confidence': confidence,
            'note': note,
        }

    def confidence_notes(self) -> list:
        return self._confidence_notes
