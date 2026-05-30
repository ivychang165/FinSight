"""
RiskDetector — 財務風險偵測與健康評分系統
"""


RISK_RULES = {
    'profitability': {
        'gross_margin': [
            {'condition': lambda v: v is not None and v < 0, 'level': 'danger',
             'message': '毛利率為負值，公司每賣出一件商品都在虧錢，營運模式可能有根本性問題。'},
            {'condition': lambda v: v is not None and 0 <= v < 0.10, 'level': 'warning',
             'message': '毛利率偏低（< 10%），代表成本控制或定價能力有待加強。'},
            {'condition': lambda v: v is not None and 0.10 <= v < 0.40, 'level': 'stable',
             'message': '毛利率中等（10% ~ 40%），代表公司具備基本獲利能力。'},
            {'condition': lambda v: v is not None and v >= 0.40, 'level': 'positive',
             'message': '毛利率表現優異（≥ 40%），公司具有良好的定價能力或成本優勢。'},
        ],
        'net_margin': [
            {'condition': lambda v: v is not None and v < 0, 'level': 'danger',
             'message': '淨利率為負值，公司本期處於虧損狀態。'},
            {'condition': lambda v: v is not None and 0 <= v < 0.03, 'level': 'warning',
             'message': '淨利率偏低（< 3%），獲利空間薄弱。'},
            {'condition': lambda v: v is not None and 0.03 <= v < 0.15, 'level': 'stable',
             'message': '淨利率中等（3% ~ 15%），公司具備基本獲利能力，但仍有提升空間。'},
            {'condition': lambda v: v is not None and v >= 0.15, 'level': 'positive',
             'message': '淨利率表現優異（≥ 15%），公司具有良好的獲利能力。'},
        ],
        'roe': [
            {'condition': lambda v: v is not None and v < 0, 'level': 'danger',
             'message': 'ROE 為負值，股東投入的資金目前無法創造報酬。'},
            {'condition': lambda v: v is not None and 0 <= v < 0.15, 'level': 'stable',
             'message': 'ROE 中等（0% ~ 15%），公司能為股東創造報酬，但資本運用效率仍有提升空間。'},
            {'condition': lambda v: v is not None and v >= 0.15, 'level': 'positive',
             'message': 'ROE 表現優異（≥ 15%），股東資金運用效率優異。'},
        ],
        'roa': [
            {'condition': lambda v: v is not None and v < 0.02, 'level': 'warning',
             'message': 'ROA 偏低（< 2%），代表公司運用資產創造獲利的效率不足。'},
            {'condition': lambda v: v is not None and 0.02 <= v < 0.08, 'level': 'stable',
             'message': 'ROA 中等（2% ~ 8%），公司具備基本的資產獲利能力。'},
            {'condition': lambda v: v is not None and v >= 0.08, 'level': 'positive',
             'message': 'ROA 表現優異（≥ 8%），代表公司能有效運用資產創造獲利。'},
]
    },
    'solvency': {
        'current_ratio': [
        {'condition': lambda v: v is not None and v < 1.0, 'level': 'danger',
         'message': '流動比率低下（< 1），說明流動負債高於流動資產，短期償債能力可能不足。'},
         {'condition': lambda v: v is not None and 1.0 <= v < 1.5, 'level': 'warning',
         'message': '流動比率偏低（1.0 ~ 1.5），短期資金調度需特別留意。'},
        {'condition': lambda v: v is not None and 1.5 <= v < 2.0, 'level': 'stable',
         'message': '流動比率適中（1.5 ~ 2.0），公司具備穩定的短期償債能力。'},
        {'condition': lambda v: v is not None and v >= 2.0, 'level': 'positive',
         'message': '流動比率良好（≥ 2.0），公司短期償債能力充裕。'},
        ],

        'debt_ratio': [
        {'condition': lambda v: v is not None and v > 0.70, 'level': 'warning',
         'message': '負債比率偏高（> 70%），公司較依賴借款支撐營運，需注意財務槓桿風險。'},
        {'condition': lambda v: v is not None and 0.40 < v <= 0.70, 'level': 'stable',
         'message': '負債比率中等（40% ~ 70%），公司具備適度的財務槓桿。'},
        {'condition': lambda v: v is not None and v <= 0.40, 'level': 'positive',
         'message': '負債比率偏低（≤ 40%），財務結構相對穩健，負債壓力較小。'},
        ],

        'interest_coverage': [
        {'condition': lambda v: v is not None and v < 2, 'level': 'danger',
         'message': '利息保障倍數偏低（< 2），公司獲利不足以支付利息，償債壓力較高。'},
        {'condition': lambda v: v is not None and 2 <= v < 5, 'level': 'stable',
         'message': '利息保障倍數普通（2 ~ 5），公司具備基本利息支付能力，但安全緩衝有限。'},
        {'condition': lambda v: v is not None and 5 <= v < 10, 'level': 'positive',
         'message': '利息保障倍數良好（5 ~ 10），公司利息支付能力充足，財務結構穩健。'},
        {'condition': lambda v: v is not None and v >= 10, 'level': 'positive',
         'message': '利息保障倍數充裕（≥ 10），公司利息支付能力非常充足，財務風險低。'},
        ]
},
    'efficiency': {
        'asset_turnover': [
        {'condition': lambda v: v is not None and v < 0.3, 'level': 'warning',
         'message': '總資產週轉率偏低（< 0.3），資產運用效率有待提升。'},
        {'condition': lambda v: v is not None and 0.3 <= v < 0.6, 'level': 'stable',
         'message': '總資產週轉率普通（0.3 ~ 0.6），資產運用效率屬於基本水準。'},
        {'condition': lambda v: v is not None and 0.6 <= v < 1.0, 'level': 'positive',
         'message': '總資產週轉率良好（0.6 ~ 1.0），資產運用效率表現不錯。'},
        {'condition': lambda v: v is not None and v >= 1.0, 'level': 'positive',
         'message': '總資產週轉率優異（≥ 1.0），資產運用效率高，營運資源使用效率佳。'},
        ],

        'cash_cycle': [
        {'condition': lambda v: v is not None and v > 120, 'level': 'warning',
         'message': '現金循環天數偏高（> 120 天），資金回收速度較慢，短期資金壓力較大。'},
        {'condition': lambda v: v is not None and 60 < v <= 120, 'level': 'stable',
         'message': '現金循環天數普通（60 ~ 120 天），資金週轉效率一般。'},
        {'condition': lambda v: v is not None and 0 <= v <= 60, 'level': 'positive',
         'message': '現金循環天數良好（0 ~ 60 天），資金週轉效率佳。'},
        {'condition': lambda v: v is not None and v < 0, 'level': 'positive',
         'message': '現金循環為負（< 0 天），公司營運資金效率極佳，通常代表先收款後付款的優勢。'},
        ],
},
    'cashflow': {
        'operating_cashflow': [
        {'condition': lambda v: v is not None and v < 0, 'level': 'danger',
         'message': '營業活動現金流量為負，本業未能產生正現金流，須高度警戒。'},
        {'condition': lambda v: v is not None and 0 <= v < 1e6, 'level': 'stable',
         'message': '營業活動現金流量偏低（< 100萬），本業現金創造能力可能較弱。'},
        {'condition': lambda v: v is not None and v >= 1e6, 'level': 'positive',
         'message': '營業活動現金流量較高（> 100萬），本業具備良好的現金創造能力。'},
        ],

        'fcf': [
        {'condition': lambda v: v is not None and v < 0, 'level': 'warning',
         'message': '自由現金流為負，資本支出超過營業現金流入，公司可能處於擴張或現金壓力狀態。'},
        {'condition': lambda v: v is not None and 0 <= v < 1e6, 'level': 'stable',
         'message': '自由現金流偏低（< 100萬），企業可用於再投資或分配的現金可能有限。'},
        {'condition': lambda v: v is not None and v >= 1e6, 'level': 'positive',
         'message': '自由現金流較高（> 100萬），公司具備良好的現金創造與分配能力。'},
        ],

        'earnings_quality': [
        {'condition': lambda v: v is not None and v < 0.8, 'level': 'warning',
         'message': '盈餘品質比偏低（< 0.8），帳面獲利但現金回收能力偏弱，獲利品質較低。'},
        {'condition': lambda v: v is not None and 0.8 <= v < 1.0, 'level': 'stable',
         'message': '盈餘品質比適中且接近 1（0.8 ~ 1.0），獲利與現金流大致匹配，但仍略有落差。'},
        {'condition': lambda v: v is not None and v >= 1.0, 'level': 'positive',
         'message': '盈餘品質比良好（≥ 1），獲利有充足現金流支撐，盈餘品質良好。'},
        ],
    },
}


class RiskDetector:
    """偵測財務風險並計算健康評分"""

    def __init__(self, ratios: dict):
        self.ratios = ratios
        self.alerts = []
        self.dimension_scores = {}

    def detect_all(self) -> list:
        self.alerts = []
        for dimension, rules in RISK_RULES.items():
            dim_ratios = self.ratios.get(dimension, {})
            for ratio_key, checks in rules.items():
                ratio_data = dim_ratios.get(ratio_key, {})
                value = ratio_data.get('value')
                for check in checks:
                    try:
                        if check['condition'](value):
                            self.alerts.append({
                                'dimension': dimension,
                                'ratio': ratio_key,
                                'ratio_name': ratio_data.get('name', ratio_key),
                                'level': check['level'],
                                'message': check['message'],
                                'value': value,
                            })
                    except (TypeError, ValueError):
                        pass

                if ratio_data.get('note'):
                    self.alerts.append({
                        'dimension': dimension,
                        'ratio': ratio_key,
                        'ratio_name': ratio_data.get('name', ratio_key),
                        'level': 'info',
                        'message': ratio_data['note'],
                        'value': None,
                    })

        return self.alerts

    def health_score(self) -> dict:
        if not self.alerts:
            self.detect_all()

        dimensions = {
            'profitability': {'name': '獲利能力', 'weight': 0.30, 'score': 70},
            'solvency': {'name': '償債能力', 'weight': 0.25, 'score': 70},
            'efficiency': {'name': '營運效率', 'weight': 0.20, 'score': 70},
            'cashflow': {'name': '現金流', 'weight': 0.25, 'score': 70},
        }

        for alert in self.alerts:
            dim = alert['dimension']
            if dim not in dimensions:
                continue

            if alert['level'] == 'danger':
                dimensions[dim]['score'] -= 25
            elif alert['level'] == 'warning':
                dimensions[dim]['score'] -= 10
            elif alert['level'] == 'stable':
                dimensions[dim]['score'] += 2
            elif alert['level'] == 'positive':
                dimensions[dim]['score'] += 10

        for dim_data in dimensions.values():
            dim_data['score'] = max(0, min(100, dim_data['score']))

        total = sum(d['weight'] * d['score'] for d in dimensions.values())

        self.dimension_scores = dimensions
        return {
            'total': round(total, 1),
            'dimensions': dimensions,
            'grade': self._grade(total),
            'method_note': (
                '本分數為 rule-based financial health scorecard，'
                '依據獲利能力、償債能力、營運效率與現金流四大構面計算。'
                '此分數用於初步財務風險提示，不等同於投資建議或信用評等。'
            ),
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 85:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 55:
            return 'C'
        elif score >= 40:
            return 'D'
        return 'F'

    def personality_tag(self) -> dict:
        if not self.dimension_scores:
            self.health_score()

        dims = self.dimension_scores
        prof_score = dims.get('profitability', {}).get('score', 50)
        solv_score = dims.get('solvency', {}).get('score', 50)
        eff_score = dims.get('efficiency', {}).get('score', 50)
        cf_score = dims.get('cashflow', {}).get('score', 50)

        debt_ratio = self.ratios.get('solvency', {}).get('debt_ratio', {}).get('value')
        roe = self.ratios.get('profitability', {}).get('roe', {}).get('value')

        if prof_score >= 80 and eff_score >= 70 and cf_score >= 70:
            if debt_ratio is not None and debt_ratio > 0.6:
                return {'tag': '高槓桿型', 'emoji': '⚡',
                'desc': '公司整體獲利能力與營運效率表現強勁，但成長動能高度依賴財務槓桿支撐，需留意債務結構與利息負擔對未來穩定性的影響。'}

            if roe is not None and roe > 0.20:
                return {'tag': '成長型', 'emoji': '🚀',
                'desc': '公司具備優異的獲利能力與營運效率，股東報酬率表現突出，顯示企業具有持續成長與擴張的潛力。'}
            return {'tag': '穩健型', 'emoji': '🛡️',
                'desc': '公司在獲利能力、營運效率與現金流表現上均衡穩定，整體財務結構健全，具備良好的長期經營基礎。'}

        if solv_score >= 80 and cf_score >= 70:
                return {'tag': '成熟型', 'emoji': '🏦',
                'desc': '公司財務結構穩健，現金流充裕且償債能力良好，營運模式成熟穩定，適合長期持有或保守型投資配置。'}

        if debt_ratio is not None and debt_ratio > 0.65:
                return {'tag': '高槓桿型', 'emoji': '⚡',
                'desc': '公司負債比率偏高，營運資金與成長動能在一定程度上依賴外部融資，需持續關注槓桿風險與景氣波動影響。'}

        if prof_score < 50 or cf_score < 50:
                return {'tag': '體質待改善', 'emoji': '🔧',
                'desc': '公司在獲利能力或現金流表現上相對偏弱，財務體質仍有改善空間，需持續觀察營運改善情況。'}

        return {'tag': '一般型', 'emoji': '📊',
            'desc': '公司整體財務表現處於市場平均水準，各項指標無明顯優勢或風險，屬於穩定但成長性有限的類型。'}
