"""
DashboardGenerator — 圖表與視覺化生成器

使用 Plotly 產生 Dashboard 所需的所有圖表。
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {
    'primary': '#1a73e8',
    'secondary': '#5f6368',
    'positive': '#0d904f',
    'warning': '#f9a825',
    'danger': '#d93025',
    'info': '#4285f4',
    'light_bg': '#f8f9fa',
    'accent1': '#4285f4',
    'accent2': '#34a853',
    'accent3': '#fbbc04',
    'accent4': '#ea4335',
}


class DashboardGenerator:
    """產生 Dashboard 所需的所有 Plotly 圖表"""

    def __init__(self, ratios: dict, health: dict, narratives: dict):
        self.ratios = ratios
        self.health = health
        self.narratives = narratives

    def health_gauge(self) -> go.Figure:
        total = self.health.get('total', 0)
        grade = self.health.get('grade', '—')

        color = COLORS['positive'] if total >= 70 else (
            COLORS['warning'] if total >= 50 else COLORS['danger']
        )

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total,
            title={'text': f"財務健康總分（{grade} 級）", 'font': {'size': 20}},
            number={'suffix': ' 分', 'font': {'size': 36}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': color, 'thickness': 0.7},
                'steps': [
                    {'range': [0, 40], 'color': '#fce4ec'},
                    {'range': [40, 55], 'color': '#fff3e0'},
                    {'range': [55, 70], 'color': '#fff9c4'},
                    {'range': [70, 85], 'color': '#e8f5e9'},
                    {'range': [85, 100], 'color': '#c8e6c9'},
                ],
                'threshold': {
                    'line': {'color': 'black', 'width': 2},
                    'thickness': 0.8,
                    'value': total,
                },
            },
        ))
        fig.update_layout(height=280, margin=dict(t=60, b=20, l=30, r=30))
        return fig

    def dimension_radar(self) -> go.Figure:
        dims = self.health.get('dimensions', {})
        labels = [d['name'] for d in dims.values()]
        scores = [d['score'] for d in dims.values()]

        labels.append(labels[0])
        scores.append(scores[0])

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=scores,
            theta=labels,
            fill='toself',
            fillcolor='rgba(26, 115, 232, 0.15)',
            line=dict(color=COLORS['primary'], width=2),
            marker=dict(size=8, color=COLORS['primary']),
            name='評分',
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
                angularaxis=dict(tickfont=dict(size=13)),
            ),
            showlegend=False,
            height=350,
            margin=dict(t=30, b=30, l=60, r=60),
            title=dict(text='四大面向評分', x=0.5, font=dict(size=16)),
        )
        return fig

    def profitability_bars(self) -> go.Figure:
        p = self.ratios.get('profitability', {})
        metrics = []
        values = []
        for key in ['gross_margin', 'net_margin', 'roe', 'roa']:
            data = p.get(key, {})
            if data.get('value') is not None:
                metrics.append(data['name'])
                values.append(data['value'] * 100)

        if not metrics:
            return self._empty_chart('獲利能力指標')

        colors = [COLORS['accent1'], COLORS['accent2'], COLORS['accent3'], COLORS['accent4']]

        fig = go.Figure(go.Bar(
            x=metrics, y=values,
            marker_color=colors[:len(metrics)],
            text=[f"{v:.1f}%" for v in values],
            textposition='outside',
        ))
        fig.update_layout(
            title=dict(text='獲利能力指標', x=0.5, font=dict(size=16)),
            yaxis_title='百分比（%）',
            height=350,
            margin=dict(t=60, b=40, l=50, r=30),
            yaxis=dict(gridcolor='#eee'),
            plot_bgcolor='white',
        )
        return fig

    def dupont_waterfall(self) -> go.Figure:
        d = self.ratios.get('dupont', {})
        nm = d.get('net_margin', {}).get('value')
        at = d.get('asset_turnover', {}).get('value')
        em = d.get('equity_multiplier', {}).get('value')
        roe = d.get('roe_dupont', {}).get('value')

        if roe is None:
            return self._empty_chart('杜邦分析')

        fig = go.Figure()
        categories = ['淨利率', '週轉率', '權益乘數', 'ROE']
        display_values = [
            nm * 100 if nm else 0,
            at * 100 if at else 0,
            em * 100 if em else 0,
            roe * 100 if roe else 0,
        ]
        labels = [
            f"{nm*100:.1f}%" if nm else '—',
            f"{at:.2f}x" if at else '—',
            f"{em:.2f}x" if em else '—',
            f"{roe*100:.1f}%" if roe else '—',
        ]

        fig.add_trace(go.Bar(
            x=categories, y=display_values,
            marker_color=[COLORS['accent1'], COLORS['accent2'], COLORS['accent3'], COLORS['primary']],
            text=labels,
            textposition='outside',
            width=0.5,
        ))
        fig.update_layout(
            title=dict(text='杜邦分析：ROE 拆解', x=0.5, font=dict(size=16)),
            height=380,
            margin=dict(t=60, b=60, l=50, r=30),
            yaxis=dict(gridcolor='#eee', title=''),
            xaxis=dict(tickfont=dict(size=13)),
            plot_bgcolor='white',
            annotations=[dict(
                text='ROE = 淨利率 × 總資產週轉率 × 權益乘數',
                xref='paper', yref='paper', x=0.5, y=-0.15,
                showarrow=False, font=dict(size=12, color=COLORS['secondary']),
            )],
        )
        return fig

    def cashflow_comparison(self) -> go.Figure:
        c = self.ratios.get('cashflow', {})
        labels = []
        values = []

        for key, display in [('operating_cashflow', '營業活動'), ('fcf', '自由現金流')]:
            data = c.get(key, {})
            if data.get('value') is not None:
                labels.append(display)
                values.append(data['value'])

        if not labels:
            return self._empty_chart('現金流量比較')

        colors = [COLORS['positive'] if v >= 0 else COLORS['danger'] for v in values]

        fig = go.Figure(go.Bar(
            x=labels, y=values,
            marker_color=colors,
            text=[f"{v/1e8:,.1f} 億" if abs(v) >= 1e8 else f"{v/1e4:,.0f} 萬" for v in values],
            textposition='outside',
        ))
        fig.update_layout(
            title=dict(text='現金流量比較', x=0.5, font=dict(size=16)),
            yaxis_title='金額（千元）',
            height=350,
            margin=dict(t=60, b=40, l=60, r=30),
            yaxis=dict(gridcolor='#eee'),
            plot_bgcolor='white',
        )
        return fig

    def solvency_bars(self) -> go.Figure:
        s = self.ratios.get('solvency', {})
        fig = make_subplots(rows=1, cols=2, subplot_titles=['流動比率', '負債比率'])

        cr = s.get('current_ratio', {}).get('value')
        dr = s.get('debt_ratio', {}).get('value')

        if cr is not None:
            cr_color = COLORS['positive'] if cr >= 1.5 else (
                COLORS['warning'] if cr >= 1.0 else COLORS['danger'])
            fig.add_trace(go.Bar(
                x=['流動比率'], y=[cr],
                marker_color=cr_color,
                text=[f"{cr:.2f}"], textposition='outside',
                showlegend=False,
            ), row=1, col=1)
            fig.add_hline(y=1.5, line_dash='dash', line_color='gray',
                          annotation_text='健康線 1.5', row=1, col=1)

        if dr is not None:
            dr_color = COLORS['positive'] if dr <= 0.5 else (
                COLORS['warning'] if dr <= 0.7 else COLORS['danger'])
            fig.add_trace(go.Bar(
                x=['負債比率'], y=[dr * 100],
                marker_color=dr_color,
                text=[f"{dr*100:.1f}%"], textposition='outside',
                showlegend=False,
            ), row=1, col=2)
            fig.add_hline(y=70, line_dash='dash', line_color='gray',
                          annotation_text='警戒線 70%', row=1, col=2)

        fig.update_layout(
            height=350,
            margin=dict(t=60, b=40, l=50, r=30),
            plot_bgcolor='white',
        )
        return fig

    @staticmethod
    def _empty_chart(title: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text='資料不足，無法繪製圖表',
            xref='paper', yref='paper', x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color='#999'),
        )
        fig.update_layout(
            title=dict(text=title, x=0.5),
            height=300,
            plot_bgcolor='white',
        )
        return fig
