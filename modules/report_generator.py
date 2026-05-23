"""
ReportGenerator — 分析報告輸出模組

匯出 Excel 格式的財務分析報告。
"""

import io
import pandas as pd
from modules.narrative_generator import fmt_pct, fmt_num, fmt_times, fmt_days


class ReportGenerator:
    """將分析結果匯出為可下載的 Excel 報告"""

    def __init__(self, company_id: str, year: int, season: int,
                 ratios: dict, health: dict, personality: dict,
                 narratives: dict, alerts: list):
        self.company_id = company_id
        self.year = year
        self.season = season
        self.ratios = ratios
        self.health = health
        self.personality = personality
        self.narratives = narratives
        self.alerts = alerts

    def generate_excel(self) -> bytes:
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            self._write_summary_sheet(writer)
            self._write_ratios_sheet(writer)
            self._write_risks_sheet(writer)
            self._write_narrative_sheet(writer)

        return output.getvalue()

    def _write_summary_sheet(self, writer):
        total = self.health.get('total', 0)
        grade = self.health.get('grade', '—')
        tag = self.personality.get('tag', '—')
        emoji = self.personality.get('emoji', '')
        summary_text = self.narratives.get('summary', '')

        rows = [
            ['FinSight 財務分析報告', ''],
            ['', ''],
            ['公司代號', self.company_id],
            ['分析期間', f'{self.year} 年第 {self.season} 季'],
            ['', ''],
            ['財務健康總分', f'{total:.0f} 分（{grade} 級）'],
            ['公司人格標籤', f'{emoji} {tag}'],
            ['', ''],
            ['一句話總結', summary_text],
        ]

        dims = self.health.get('dimensions', {})
        rows.append(['', ''])
        rows.append(['面向', '分數'])
        for dim_data in dims.values():
            rows.append([dim_data['name'], f"{dim_data['score']:.0f}"])

        df = pd.DataFrame(rows, columns=['項目', '內容'])
        df.to_excel(writer, sheet_name='總覽', index=False)

    def _write_ratios_sheet(self, writer):
        rows = []
        dimension_labels = {
            'profitability': '獲利能力',
            'solvency': '償債能力',
            'efficiency': '營運效率',
            'cashflow': '現金流',
            'dupont': '杜邦分析',
        }

        for dim_key, dim_label in dimension_labels.items():
            dim_ratios = self.ratios.get(dim_key, {})
            for ratio_key, ratio_data in dim_ratios.items():
                value = ratio_data.get('value')
                unit = ratio_data.get('unit', '')

                if value is None:
                    formatted = '—'
                elif unit == 'percent':
                    formatted = fmt_pct(value)
                elif unit == 'times':
                    formatted = fmt_times(value)
                elif unit == 'days':
                    formatted = fmt_days(value)
                elif unit == 'amount':
                    formatted = fmt_num(value)
                else:
                    formatted = str(value)

                rows.append({
                    '面向': dim_label,
                    '指標': ratio_data.get('name', ratio_key),
                    '數值': formatted,
                    '公式': ratio_data.get('formula', ''),
                    '可信度': ratio_data.get('confidence', ''),
                    '備註': ratio_data.get('note', '') or '',
                })

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name='財務比率', index=False)

    def _write_risks_sheet(self, writer):
        if not self.alerts:
            df = pd.DataFrame([{'訊息': '未偵測到重大風險'}])
        else:
            level_map = {
                'danger': '🔴 高風險',
                'warning': '🟡 注意',
                'positive': '🟢 正面',
                'info': 'ℹ️ 資訊',
            }
            rows = []
            for alert in self.alerts:
                rows.append({
                    '等級': level_map.get(alert['level'], alert['level']),
                    '指標': alert.get('ratio_name', ''),
                    '訊息': alert['message'],
                })
            df = pd.DataFrame(rows)

        df.to_excel(writer, sheet_name='風險提醒', index=False)

    def _write_narrative_sheet(self, writer):
        rows = []
        dimension_labels = {
            'profitability': '獲利能力',
            'solvency': '償債能力',
            'efficiency': '營運效率',
            'cashflow': '現金流',
            'dupont': '杜邦分析',
        }

        for dim_key, dim_label in dimension_labels.items():
            items = self.narratives.get(dim_key, [])
            for item in items:
                rows.append({
                    '面向': dim_label,
                    '標題': item.get('title', ''),
                    '分析': item.get('body', ''),
                })

        rows.append({
            '面向': '總結',
            '標題': '一句話總結',
            '分析': self.narratives.get('summary', ''),
        })

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name='白話分析', index=False)
