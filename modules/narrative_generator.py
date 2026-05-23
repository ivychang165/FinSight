"""
NarrativeGenerator — 白話分析與財務總結生成器

將冰冷的財務數字轉譯為一般人能理解的語言。
"""


def fmt_pct(value, decimal: int = 1) -> str:
    if value is None:
        return '—'
    return f"{value * 100:.{decimal}f}%"


def fmt_num(value) -> str:
    if value is None:
        return '—'
    if abs(value) >= 1e8:
        return f"{value / 1e8:,.1f} 億"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:,.1f} 萬"
    return f"{value:,.0f}"


def fmt_times(value) -> str:
    if value is None:
        return '—'
    return f"{value:.2f} 倍"


def fmt_days(value) -> str:
    if value is None:
        return '—'
    return f"{value:.0f} 天"


class NarrativeGenerator:
    """產生白話風格的財務分析文字"""

    def __init__(self, ratios: dict, health: dict, personality: dict):
        self.ratios = ratios
        self.health = health
        self.personality = personality

    def generate_all(self) -> dict:
        return {
            'profitability': self._narrate_profitability(),
            'solvency': self._narrate_solvency(),
            'efficiency': self._narrate_efficiency(),
            'cashflow': self._narrate_cashflow(),
            'dupont': self._narrate_dupont(),
            'summary': self._generate_summary(),
        }

    # ── 獲利能力 ──

    def _narrate_profitability(self) -> list:
        p = self.ratios.get('profitability', {})
        texts = []

        gm = p.get('gross_margin', {}).get('value')
        if gm is not None:
            texts.append({
                'title': f"毛利率 {fmt_pct(gm)}",
                'body': (
                    f"公司每賣出 100 元商品，扣除直接成本後能留下 {gm*100:.1f} 元毛利。"
                    + ('' if gm >= 0.20 else ' 毛利率偏低，代表成本壓力較大或市場競爭激烈。')
                ),
            })

        nm = p.get('net_margin', {}).get('value')
        if nm is not None:
            texts.append({
                'title': f"淨利率 {fmt_pct(nm)}",
                'body': (
                    f"扣除所有費用與稅負後，公司每 100 元營收最終留下 {nm*100:.1f} 元淨利。"
                    + (' 整體獲利表現穩健。' if nm >= 0.10 else '')
                ),
            })

        roe = p.get('roe', {}).get('value')
        if roe is not None:
            texts.append({
                'title': f"ROE {fmt_pct(roe)}",
                'body': (
                    f"股東每投入 100 元資金，公司一年能幫股東賺 {roe*100:.1f} 元。"
                    + (' 資金運用效率相當優異。' if roe >= 0.15 else '')
                    + (' ROE 偏低，需留意公司是否有效利用股東資金。' if roe is not None and 0 < roe < 0.08 else '')
                ),
            })

        roa = p.get('roa', {}).get('value')
        if roa is not None:
            body = f"公司運用所有資產每年能創造 {roa*100:.1f}% 的報酬。"
            if roe is not None and roa is not None and roe > 0 and roa > 0:
                leverage_gap = roe / roa
                if leverage_gap > 3:
                    body += ' ROE 遠高於 ROA，暗示公司高度依賴財務槓桿。'
            texts.append({'title': f"ROA {fmt_pct(roa)}", 'body': body})

        return texts

    # ── 償債能力 ──

    def _narrate_solvency(self) -> list:
        s = self.ratios.get('solvency', {})
        texts = []

        cr = s.get('current_ratio', {}).get('value')
        if cr is not None:
            status = '充裕' if cr >= 2 else ('尚可' if cr >= 1.5 else '偏緊')
            texts.append({
                'title': f"流動比率 {fmt_times(cr)}",
                'body': f"公司短期資金調度能力{status}，每 1 元的短期負債有 {cr:.2f} 元的流動資產可償還。",
            })

        dr = s.get('debt_ratio', {}).get('value')
        if dr is not None:
            texts.append({
                'title': f"負債比率 {fmt_pct(dr)}",
                'body': (
                    f"公司每 100 元的資產中，有 {dr*100:.1f} 元來自借款。"
                    + (' 負債偏高，需注意財務槓桿風險。' if dr > 0.60 else ' 財務結構尚屬穩健。')
                ),
            })

        ic = s.get('interest_coverage', {})
        if ic.get('note'):
            texts.append({
                'title': '利息保障倍數',
                'body': ic['note'],
            })
        elif ic.get('value') is not None:
            texts.append({
                'title': f"利息保障倍數 {fmt_times(ic['value'])}",
                'body': (
                    f"公司營業利益是利息費用的 {ic['value']:.1f} 倍。"
                    + (' 利息支付無虞。' if ic['value'] >= 5 else '')
                    + (' 利息負擔偏重。' if ic['value'] < 2 else '')
                ),
            })

        return texts

    # ── 營運效率 ──

    def _narrate_efficiency(self) -> list:
        e = self.ratios.get('efficiency', {})
        texts = []

        at = e.get('asset_turnover', {}).get('value')
        if at is not None:
            texts.append({
                'title': f"總資產週轉率 {fmt_times(at)}",
                'body': f"公司每 1 元的資產一年可以創造 {at:.2f} 元的營收，反映資產運用效率。",
            })

        it_data = e.get('inventory_turnover', {})
        it = it_data.get('value')
        if it_data.get('note'):
            texts.append({'title': '存貨週轉率', 'body': it_data['note']})
        elif it is not None:
            days = 365 / it if it > 0 else None
            texts.append({
                'title': f"存貨週轉率 {fmt_times(it)}",
                'body': (
                    f"存貨平均 {days:.0f} 天可以銷售完畢。"
                    + (' 存貨去化速度良好。' if days and days < 60 else '')
                ) if days else f"存貨週轉率為 {it:.2f} 倍。",
            })

        rt = e.get('receivable_turnover', {}).get('value')
        if rt is not None:
            days = 365 / rt if rt > 0 else None
            texts.append({
                'title': f"應收帳款週轉率 {fmt_times(rt)}",
                'body': (
                    f"公司平均 {days:.0f} 天可以收回貨款。"
                    + (' 收款速度良好。' if days and days < 60 else '')
                ) if days else f"應收帳款週轉率為 {rt:.2f} 倍。",
            })

        cc = e.get('cash_cycle', {}).get('value')
        if cc is not None:
            texts.append({
                'title': f"現金循環 {fmt_days(cc)}",
                'body': (
                    f"公司完成一次營運循環需要約 {cc:.0f} 天的資金周轉。"
                    + (' 現金循環天數長，短期資金壓力較高。' if cc > 120 else '')
                    + (' 資金周轉效率優異。' if cc < 30 else '')
                ),
            })

        return texts

    # ── 現金流 ──

    def _narrate_cashflow(self) -> list:
        c = self.ratios.get('cashflow', {})
        texts = []

        ocf = c.get('operating_cashflow', {}).get('value')
        if ocf is not None:
            status = '正向' if ocf > 0 else '負向'
            texts.append({
                'title': f"營業活動現金流量 {fmt_num(ocf)}",
                'body': (
                    f"本業現金流量為{status}（{fmt_num(ocf)}），"
                    + ('代表公司本業確實能產生現金，不只是帳面獲利。' if ocf > 0
                       else '代表公司本業目前未能產生正現金流，需高度警戒。')
                ),
            })

        fcf = c.get('fcf', {}).get('value')
        if fcf is not None:
            texts.append({
                'title': f"自由現金流 {fmt_num(fcf)}",
                'body': (
                    f"扣除維持營運所需的資本支出後，公司真正剩下 {fmt_num(fcf)} 的自由現金。"
                    + (' 有餘裕進行配息或投資。' if fcf > 0 else ' 資金需依賴外部融資。')
                ),
            })

        eq_data = c.get('earnings_quality', {})
        eq = eq_data.get('value')
        if eq_data.get('note'):
            texts.append({'title': '盈餘品質比', 'body': eq_data['note']})
        elif eq is not None:
            texts.append({
                'title': f"盈餘品質比 {fmt_times(eq)}",
                'body': (
                    f"每 1 元帳面淨利有 {eq:.2f} 元的現金流支撐。"
                    + (' 盈餘品質良好，獲利有真實現金收入。' if eq >= 1.0 else '')
                    + (' 帳面有獲利但現金回收能力較弱。' if eq < 0.8 else '')
                ),
            })

        return texts

    # ── 杜邦分析 ──

    def _narrate_dupont(self) -> list:
        d = self.ratios.get('dupont', {})
        nm = d.get('net_margin', {}).get('value')
        at = d.get('asset_turnover', {}).get('value')
        em = d.get('equity_multiplier', {}).get('value')
        roe = d.get('roe_dupont', {}).get('value')

        if roe is None:
            return [{'title': '杜邦分析', 'body': '資料不足，無法進行杜邦分析。'}]

        driver = '綜合型'
        if nm is not None and at is not None and em is not None:
            scores = {'淨利率（獲利能力）': nm, '週轉率（資產效率）': at, '槓桿（財務槓桿）': em - 1}
            max_driver = max(scores, key=lambda k: scores[k] if scores[k] is not None else 0)
            driver = max_driver

        return [{
            'title': f"杜邦分析 ROE = {fmt_pct(roe)}",
            'body': (
                f"ROE 拆解：淨利率 {fmt_pct(nm)} × 總資產週轉率 {fmt_times(at)} × 權益乘數 {fmt_times(em)}。"
                f" 公司 ROE 的主要驅動力來自{driver}。"
            ),
        }]

    # ── 總結 ──

    def _generate_summary(self) -> str:
        dims = self.health.get('dimensions', {})
        total = self.health.get('total', 0)
        grade = self.health.get('grade', '—')
        tag = self.personality.get('tag', '—')

        strengths = []
        weaknesses = []
        for dim_key, dim_data in dims.items():
            name = dim_data['name']
            score = dim_data['score']
            if score >= 80:
                strengths.append(name)
            elif score < 60:
                weaknesses.append(name)

        parts = []
        if strengths:
            parts.append(f"公司在{'、'.join(strengths)}方面表現良好")
        if weaknesses:
            parts.append(f"但{'、'.join(weaknesses)}需要留意")

        if not parts:
            parts.append('公司各項財務指標表現中規中矩')

        summary = '，'.join(parts) + '。'
        summary += f" 整體財務健康評分為 {total:.0f} 分（{grade} 級），屬於「{tag}」公司。"

        return summary
