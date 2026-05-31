"""
DashboardGenerator — 圖表與視覺化生成器

使用 Plotly 產生 Dashboard 所需的所有圖表。
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {
    "bg": "#0B1120",
    "sidebar": "#111827",
    "card": "#1F2937",
    "card_2": "#162033",
    "border": "#374151",
    "grid": "#334155",
    "text": "#F9FAFB",
    "muted": "#CBD5E1",
    "muted_2": "#94A3B8",
    "primary": "#3B82F6",
    "primary_2": "#2563EB",
    "teal": "#14B8A6",
    "positive": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "purple": "#8B5CF6",
    "blue_soft": "rgba(59, 130, 246, 0.18)",
    "green_soft": "rgba(34, 197, 94, 0.18)",
    "warning_soft": "rgba(245, 158, 11, 0.20)",
    "danger_soft": "rgba(239, 68, 68, 0.18)",
    "accent1": "#3B82F6",
    "accent2": "#14B8A6",
    "accent3": "#8B5CF6",
    "accent4": "#F59E0B",
}

CHART_FONT = 'Arial, "Microsoft JhengHei", sans-serif'


class DashboardGenerator:
    """產生 Dashboard 所需的所有 Plotly 圖表"""

    def __init__(self, ratios: dict, health: dict, narratives: dict):
        self.ratios = ratios
        self.health = health
        self.narratives = narratives

    @staticmethod
    def _format_percent(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value * 100:.1f}%"

    @staticmethod
    def _format_times(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:.2f}x"

    @staticmethod
    def _format_amount(value: float | None) -> str:
        if value is None:
            return "—"
        if abs(value) >= 1e8:
            return f"{value / 1e8:,.1f} 億"
        if abs(value) >= 1e4:
            return f"{value / 1e4:,.0f} 萬"
        return f"{value:,.0f}"

    @staticmethod
    def _bar_axis_range(values: list[float]) -> list[float] | None:
        if not values:
            return None
        max_v = max(values)
        min_v = min(values)
        top = max(max_v * 1.22, max_v + 1, 1)
        bottom = min(min_v * 1.18, min_v - 1, 0) if min_v < 0 else 0
        return [bottom, top]

    @staticmethod
    def _apply_layout(fig: go.Figure, title: str, height: int = 380) -> go.Figure:
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=17, color=COLORS["text"])),
            height=height,
            margin=dict(t=72, b=76, l=64, r=42),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor=COLORS["card"],
            font=dict(color=COLORS["text"], family=CHART_FONT, size=12),
            hoverlabel=dict(
                bgcolor=COLORS["card_2"],
                bordercolor=COLORS["border"],
                font=dict(color=COLORS["text"], family=CHART_FONT),
            ),
        )
        fig.update_xaxes(
            tickfont=dict(color=COLORS["muted"], size=12),
            linecolor=COLORS["border"],
            automargin=True,
        )
        fig.update_yaxes(
            tickfont=dict(color=COLORS["muted"], size=12),
            linecolor=COLORS["border"],
            gridcolor=COLORS["grid"],
            zerolinecolor=COLORS["border"],
            automargin=True,
        )
        fig.update_traces(textfont=dict(color=COLORS["text"], size=12), cliponaxis=False)
        return fig

    def health_gauge(self) -> go.Figure:
        total = self.health.get('total', 0)
        grade = self.health.get('grade', '—')

        color = COLORS['positive'] if total >= 70 else (
            COLORS['warning'] if total >= 50 else COLORS['danger']
        )

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total,
            title={
                'text': f"財務健康總分（{grade} 級）",
                'font': {'size': 20, 'color': COLORS['text'], 'family': CHART_FONT},
            },
            number={
                'suffix': ' 分',
                'font': {'size': 36, 'color': COLORS['text'], 'family': CHART_FONT},
            },
            gauge={
                'axis': {
                    'range': [0, 100],
                    'tickwidth': 1,
                    'tickcolor': COLORS['muted_2'],
                    'tickfont': {'color': COLORS['muted'], 'size': 11},
                },
                'bar': {'color': color, 'thickness': 0.68},
                'bgcolor': COLORS['card_2'],
                'borderwidth': 1,
                'bordercolor': COLORS['border'],
                'steps': [
                    {'range': [0, 40], 'color': COLORS['danger_soft']},
                    {'range': [40, 55], 'color': COLORS['warning_soft']},
                    {'range': [55, 70], 'color': 'rgba(245, 158, 11, 0.13)'},
                    {'range': [70, 85], 'color': COLORS['green_soft']},
                    {'range': [85, 100], 'color': 'rgba(34, 197, 94, 0.28)'},
                ],
                'threshold': {
                    'line': {'color': COLORS['text'], 'width': 2},
                    'thickness': 0.8,
                    'value': total,
                },
            },
        ))
        fig.update_layout(
            height=300,
            margin=dict(t=68, b=18, l=30, r=30),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS['text'], family=CHART_FONT),
        )
        return fig

    def dimension_radar(self) -> go.Figure:
        dims = self.health.get('dimensions', {})
        labels = [d.get('name', '') for d in dims.values()]
        scores = [d.get('score', 0) for d in dims.values()]

        if not labels:
            return self._empty_chart('四大面向評分')

        labels.append(labels[0])
        scores.append(scores[0])

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=scores,
            theta=labels,
            fill='toself',
            fillcolor='rgba(59, 130, 246, 0.22)',
            line=dict(color=COLORS['primary'], width=2.6),
            marker=dict(size=8, color=COLORS['teal']),
            name='分數（滿分 100）',
        ))
        fig.update_layout(
            polar=dict(
                bgcolor=COLORS['card'],
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    tickfont=dict(size=10, color=COLORS['muted_2']),
                    gridcolor=COLORS['grid'],
                    linecolor=COLORS['border'],
                ),
                angularaxis=dict(
                    tickfont=dict(size=13, color=COLORS['text']),
                    gridcolor=COLORS['grid'],
                    linecolor=COLORS['border'],
                ),
            ),
            showlegend=False,
            height=360,
            margin=dict(t=58, b=36, l=58, r=58),
            title=dict(text='四大面向評分', x=0.5, font=dict(size=17, color=COLORS['text'])),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS['text'], family=CHART_FONT),
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
            x=metrics,
            y=values,
            marker_color=colors[:len(metrics)],
            text=[f"{v:.1f}%" for v in values],
            textposition='outside',
            hovertemplate='%{x}<br>%{y:.1f}%<extra></extra>',
        ))
        self._apply_layout(fig, '獲利能力指標', height=390)
        fig.update_layout(yaxis_title='百分比（%）')
        fig.update_yaxes(range=self._bar_axis_range(values))
        fig.update_xaxes(tickangle=-18)
        return fig

    def efficiency_bars(self) -> go.Figure:
        e = self.ratios.get('efficiency', {})
        metrics = []
        values = []
        labels = []

        for key in ['asset_turnover', 'inventory_turnover', 'receivable_turnover']:
            data = e.get(key, {})
            if data.get('value') is not None:
                metrics.append(data['name'])
                values.append(data['value'])
                labels.append(f"{data['value']:.2f}x")

        cash_cycle = e.get('cash_cycle', {}).get('value')
        if cash_cycle is not None:
            metrics.append('現金循環天數')
            values.append(cash_cycle)
            labels.append(f"{cash_cycle:.1f} 天")

        if not metrics:
            return self._empty_chart('營運效率指標')

        colors = [COLORS['primary'], COLORS['teal'], COLORS['purple'], COLORS['warning']]
        fig = go.Figure(go.Bar(
            x=metrics,
            y=values,
            marker_color=colors[:len(metrics)],
            text=labels,
            textposition='outside',
            hovertemplate='%{x}<br>%{text}<extra></extra>',
        ))
        self._apply_layout(fig, '營運效率指標', height=390)
        fig.update_layout(yaxis_title='倍數 / 天數')
        fig.update_yaxes(range=self._bar_axis_range(values))
        fig.update_xaxes(tickangle=-18)
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
        boxes = [
            ('淨利率', self._format_percent(nm), COLORS['primary']),
            ('總資產週轉率', self._format_times(at), COLORS['teal']),
            ('權益乘數', self._format_times(em), COLORS['purple']),
            ('ROE', self._format_percent(roe), COLORS['positive']),
        ]
        x_positions = [0.13, 0.38, 0.63, 0.88]
        signs = ['×', '×', '=']

        for idx, ((label, value, color), x) in enumerate(zip(boxes, x_positions)):
            fig.add_shape(
                type='rect', xref='paper', yref='paper',
                x0=x - 0.105, x1=x + 0.105, y0=0.38, y1=0.68,
                line=dict(color=color, width=2),
                fillcolor='rgba(31, 41, 55, 0.96)',
                layer='below',
            )
            fig.add_annotation(
                x=x, y=0.59, xref='paper', yref='paper', showarrow=False,
                text=f"<b>{value}</b>",
                font=dict(size=19, color=color, family=CHART_FONT),
            )
            fig.add_annotation(
                x=x, y=0.46, xref='paper', yref='paper', showarrow=False,
                text=label,
                font=dict(size=12, color=COLORS['muted'], family=CHART_FONT),
            )
            if idx < len(signs):
                fig.add_annotation(
                    x=(x + x_positions[idx + 1]) / 2, y=0.53,
                    xref='paper', yref='paper', showarrow=False,
                    text=f"<b>{signs[idx]}</b>",
                    font=dict(size=24, color=COLORS['text'], family=CHART_FONT),
                )

        fig.add_annotation(
            text='ROE = 淨利率 × 總資產週轉率 × 權益乘數',
            xref='paper', yref='paper', x=0.5, y=0.21,
            showarrow=False,
            font=dict(size=14, color=COLORS['muted'], family=CHART_FONT),
        )
        fig.update_layout(
            title=dict(text='杜邦分析：ROE 拆解', x=0.5, font=dict(size=17, color=COLORS['text'])),
            height=340,
            margin=dict(t=72, b=40, l=30, r=30),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor=COLORS['card'],
            font=dict(color=COLORS['text'], family=CHART_FONT),
            xaxis=dict(visible=False, range=[0, 1]),
            yaxis=dict(visible=False, range=[0, 1]),
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
            x=labels,
            y=values,
            marker_color=colors,
            text=[self._format_amount(v) for v in values],
            textposition='outside',
            hovertemplate='%{x}<br>%{text}<extra></extra>',
        ))
        self._apply_layout(fig, '現金流量比較', height=380)
        fig.update_layout(yaxis_title='金額（千元）')
        fig.update_yaxes(range=self._bar_axis_range(values))
        return fig

    def solvency_bars(self) -> go.Figure:
        s = self.ratios.get('solvency', {})
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=['流動比率', '負債比率'],
            horizontal_spacing=0.22,
        )

        cr = s.get('current_ratio', {}).get('value')
        dr = s.get('debt_ratio', {}).get('value')

        if cr is not None:
            cr_color = COLORS['positive'] if cr >= 1.5 else (
                COLORS['warning'] if cr >= 1.0 else COLORS['danger'])
            fig.add_trace(go.Bar(
                x=['流動比率'],
                y=[cr],
                marker_color=cr_color,
                text=[f"{cr:.2f}"],
                textposition='outside',
                showlegend=False,
                hovertemplate='流動比率<br>%{y:.2f}<extra></extra>',
            ), row=1, col=1)
            fig.add_hline(
                y=1.5,
                line_dash='dash',
                line_color=COLORS['muted_2'],
                annotation_text='健康線 1.5',
                annotation_font_color=COLORS['muted'],
                row=1,
                col=1,
            )

        if dr is not None:
            dr_value = dr * 100
            dr_color = COLORS['positive'] if dr <= 0.5 else (
                COLORS['warning'] if dr <= 0.7 else COLORS['danger'])
            fig.add_trace(go.Bar(
                x=['負債比率'],
                y=[dr_value],
                marker_color=dr_color,
                text=[f"{dr_value:.1f}%"],
                textposition='outside',
                showlegend=False,
                hovertemplate='負債比率<br>%{y:.1f}%<extra></extra>',
            ), row=1, col=2)
            fig.add_hline(
                y=70,
                line_dash='dash',
                line_color=COLORS['muted_2'],
                annotation_text='警戒線 70%',
                annotation_font_color=COLORS['muted'],
                row=1,
                col=2,
            )

        self._apply_layout(fig, '償債能力指標', height=380)
        fig.update_annotations(font=dict(color=COLORS['text'], size=14, family=CHART_FONT))
        fig.update_yaxes(gridcolor=COLORS['grid'])
        return fig

    @staticmethod
    def _empty_chart(title: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text='資料不足，無法繪製圖表',
            xref='paper', yref='paper', x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color=COLORS['muted'], family=CHART_FONT),
        )
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(color=COLORS['text'], size=17)),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor=COLORS['card'],
            font=dict(color=COLORS['text'], family=CHART_FONT),
            margin=dict(t=70, b=40, l=40, r=40),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig
