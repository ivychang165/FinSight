"""
FinSight — 智慧化財務報表翻譯與分析平台

新手友善的財報翻譯器 + 財務健康 Dashboard
"""

import re
import logging
import streamlit as st
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from modules.mops_fetcher import MOPSFetcher
from modules.financial_mapper import FinancialMapper
from modules.financial_report import FinancialReport
from modules.ratio_analyzer import RatioAnalyzer
from modules.risk_detector import RiskDetector
from modules.narrative_generator import NarrativeGenerator
from modules.dashboard_generator import DashboardGenerator
from modules.report_generator import ReportGenerator
from modules.glossary import GLOSSARY
from modules.company_data import search_companies, get_company_name

# ─── Page Config ───

st.set_page_config(
    page_title="FinSight 財務分析平台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───

st.markdown("""
<style>
    /* ─── Desktop Styles ─── */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem;
        border-left: 4px solid #1a73e8;
        margin-bottom: 0.8rem;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #5f6368;
        margin-bottom: 0.3rem;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a2e;
    }
    .risk-danger {
        background: #fce4ec;
        border-left: 4px solid #d93025;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .risk-warning {
        background: #fff3e0;
        border-left: 4px solid #f9a825;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .risk-positive {
        background: #e8f5e9;
        border-left: 4px solid #0d904f;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .risk-info {
        background: #e3f2fd;
        border-left: 4px solid #4285f4;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .narrative-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .personality-badge {
        font-size: 1.8rem;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
    }
    .company-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .company-subtitle {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 1rem;
    }

    /* ─── Mobile Responsive ─── */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.5rem;
        }
        .sub-header {
            font-size: 0.8rem;
            margin-bottom: 1rem;
        }
        .metric-value {
            font-size: 1.2rem;
        }
        .personality-badge {
            font-size: 1.3rem;
            padding: 0.8rem;
        }
        .personality-badge span {
            font-size: 0.7rem !important;
        }
        .narrative-card {
            padding: 0.7rem 0.9rem;
            font-size: 0.9rem;
        }
        .risk-danger, .risk-warning, .risk-positive, .risk-info {
            padding: 0.6rem 0.8rem;
            font-size: 0.85rem;
        }
        .company-title {
            font-size: 1.2rem;
        }
        .company-subtitle {
            font-size: 0.8rem;
        }

        /* 讓欄位在手機上堆疊成單欄 */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width: 100% !important;
            flex: 0 0 100% !important;
            min-width: 100% !important;
        }

        /* Tab 標籤可水平捲動 */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            flex-wrap: nowrap !important;
            gap: 4px;
            scrollbar-width: none;
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.75rem;
            padding: 6px 12px;
            white-space: nowrap;
        }

        /* 縮小 Plotly 圖表高度 */
        [data-testid="stPlotlyChart"] > div {
            max-height: 320px;
        }
    }

    /* ─── Tablet ─── */
    @media (min-width: 769px) and (max-width: 1024px) {
        .main-header {
            font-size: 1.8rem;
        }
        .personality-badge {
            font-size: 1.4rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ─── 快取搜尋（避免每次打字都呼叫 TWSE API）───

@st.cache_data(ttl=300, show_spinner=False)
def cached_search(keyword: str) -> list:
    """搜尋公司：本地資料庫 + TWSE 官方 API，結果快取 5 分鐘"""
    _fetcher = MOPSFetcher()
    return _fetcher.search_company(keyword)


# ─── Header ───

st.markdown('<div class="main-header">📊 FinSight</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">智慧化財務報表翻譯與分析平台 — 讓財報不再是天書</div>',
    unsafe_allow_html=True,
)

# ─── Sidebar ───

with st.sidebar:
    st.markdown("### 📋 查詢設定")

    search_query = st.text_input(
        "搜尋公司（代號或名稱）",
        value="2330",
        placeholder="例如：2330 或 台積電",
        help="輸入股票代號或公司名稱的部分文字即可搜尋，例如「台積」、「鴻海」、「2330」",
    )

    # 搜尋與選擇公司
    company_id = search_query.strip()
    company_name = ""

    if search_query.strip():
        matches = cached_search(search_query.strip())

        if len(matches) == 1:
            company_id = matches[0]['code']
            company_name = matches[0]['name']
            st.caption(f"✅ {company_id} {company_name}")
        elif len(matches) > 1:
            # 用 dict 避免字串分割的脆弱性
            option_map = {f"{m['code']}　{m['name']}": m for m in matches}
            selected = st.selectbox(
                "搜尋結果（點選切換）",
                list(option_map.keys()),
            )
            company_id = option_map[selected]['code']
            company_name = option_map[selected]['name']
        else:
            # TWSE API 也找不到 → 直接當作代號輸入
            if re.fullmatch(r'\d{4,6}', search_query.strip()):
                company_id = search_query.strip()
                company_name = ""
                st.caption(f"🔍 將直接搜尋代號 {company_id}")
            else:
                st.warning("找不到符合的公司，請嘗試輸入 4 位數股票代號")

    col_y, col_s = st.columns(2)
    with col_y:
        year = st.number_input("年度", min_value=2013, max_value=2026, value=2024)
    with col_s:
        season = st.selectbox("季度", [1, 2, 3, 4], index=3,
                              format_func=lambda x: f"Q{x}" + (" (年報)" if x == 4 else ""))

    st.markdown("---")
    analyze_btn = st.button("🚀 開始分析", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### 📖 財報小百科")
    glossary_term = st.selectbox(
        "選擇指標",
        list(GLOSSARY.keys()),
        index=0,
    )
    if glossary_term:
        entry = GLOSSARY[glossary_term]
        st.markdown(f"**{glossary_term}**")
        st.info(entry['professional_definition'])
        st.caption(f"📐 公式：{entry['formula']}")
        with st.expander("💡 白話比喻"):
            st.write(entry['analogy'])
        with st.expander("📏 健康區間"):
            st.write(entry['healthy_range'])

    st.markdown("---")
    st.caption("資料來源：公開資訊觀測站 XBRL")
    st.caption("FinSight v1.0 Prototype")

# ─── Main Analysis Flow ───

if analyze_btn:
    with st.spinner("正在從公開資訊觀測站擷取資料..."):
        try:
            fetcher = MOPSFetcher()
            statements = fetcher.fetch_all_statements(company_id, year, season)
        except ConnectionError as e:
            st.error(f"🌐 網路連線失敗：{e}")
            st.info("請檢查網路連線後重試，或稍後再試。")
            st.stop()
        except ValueError as e:
            st.error(f"📭 查無資料")
            st.markdown(str(e))
            if hasattr(fetcher, '_last_debug') and fetcher._last_debug:
                st.code(fetcher._last_debug, language="text")
            st.info(
                "💡 **小提示**：部分公司（如金控子公司、興櫃公司、KY 公司等）"
                "可能未在 XBRL 平台提供報表。\n\n"
                "您可以嘗試搜尋其他公司代號，例如：2330（台積電）、2317（鴻海）、2454（聯發科）。"
            )
            st.stop()
        except Exception as e:
            st.error(f"❌ 發生未預期的錯誤：{e}")
            st.stop()

    # 如果使用了個別報表（fallback），顯示提醒
    meta = statements.get('_meta', {})
    if meta.get('report_type') == 'individual':
        st.warning(
            "⚠️ 此公司無合併報表資料，已自動改用**個別報表**進行分析。"
            "個別報表僅涵蓋母公司，不含子公司資料，分析結果可能與合併報表有差異。"
        )

    progress = st.progress(0, text="解析財務科目...")

    # Step 1: Map financial accounts
    mapper = FinancialMapper()
    report = FinancialReport(company_id, year, season)
    report.set_raw_statements(statements)

    statement_types = {
        'balance_sheet': '資產負債表',
        'income_statement': '綜合損益表',
        'cash_flow': '現金流量表',
    }

    for st_key, st_label in statement_types.items():
        df = statements.get(st_key, pd.DataFrame())
        if not df.empty:
            mapped = mapper.extract_financials(df, st_key)
            report.set_mapped_data({st_key: mapped})

    progress.progress(30, text="計算財務比率...")

    # Step 2: Calculate ratios
    analyzer = RatioAnalyzer(report)
    ratios = analyzer.analyze_all()

    progress.progress(50, text="偵測財務風險...")

    # Step 3: Risk detection
    detector = RiskDetector(ratios)
    alerts = detector.detect_all()
    health = detector.health_score()
    personality = detector.personality_tag()

    progress.progress(70, text="生成分析報告...")

    # Step 4: Generate narratives
    narrator = NarrativeGenerator(ratios, health, personality)
    narratives = narrator.generate_all()

    # Step 5: Generate dashboard
    dashboard = DashboardGenerator(ratios, health, narratives)

    progress.progress(90, text="繪製圖表...")

    # Step 6: Validation
    balance_check = report.validate_balance_sheet()
    completeness = report.completeness_check()

    progress.progress(100, text="分析完成！")
    progress.empty()

    # 公司名稱：優先用 API 取得的（已存在 meta），再用側邊欄搜尋結果
    meta_name = statements.get('_meta', {}).get('company_name', '')
    if meta_name:
        company_name = meta_name
    elif not company_name:
        company_name = get_company_name(company_id)

    # Store in session state
    st.session_state['analysis_done'] = True
    st.session_state['report'] = report
    st.session_state['ratios'] = ratios
    st.session_state['alerts'] = alerts
    st.session_state['health'] = health
    st.session_state['personality'] = personality
    st.session_state['narratives'] = narratives
    st.session_state['dashboard'] = dashboard
    st.session_state['balance_check'] = balance_check
    st.session_state['completeness'] = completeness
    st.session_state['company_id'] = company_id
    st.session_state['company_name'] = company_name
    st.session_state['year'] = year
    st.session_state['season'] = season
    st.session_state['statements'] = statements

# ─── Display Results ───

if st.session_state.get('analysis_done'):
    report = st.session_state['report']
    ratios = st.session_state['ratios']
    alerts = st.session_state['alerts']
    health = st.session_state['health']
    personality = st.session_state['personality']
    narratives = st.session_state['narratives']
    dashboard = st.session_state['dashboard']
    balance_check = st.session_state['balance_check']
    completeness = st.session_state['completeness']
    cid = st.session_state['company_id']
    cname = st.session_state.get('company_name', '')
    yr = st.session_state['year']
    ssn = st.session_state['season']

    # ── Warnings ──
    if report.warnings:
        for w in report.warnings:
            st.warning(f"⚠️ {w}")

    if not balance_check['valid']:
        st.warning(f"⚠️ {balance_check['message']}")

    if completeness['missing_critical']:
        st.warning(f"⚠️ 缺少關鍵欄位：{', '.join(completeness['missing_critical'])}")

    # ── Top Summary Row ──
    statements_meta = st.session_state.get('statements', {}).get('_meta', {})
    report_label = statements_meta.get('report_label', '合併報表')
    display_name = f"{cid} {cname}" if cname else cid
    st.markdown(
        f'<div class="company-title">{display_name}</div>'
        f'<div class="company-subtitle">{yr} 年 Q{ssn} 財務分析 ｜ {report_label}</div>',
        unsafe_allow_html=True,
    )

    top_col1, top_col2, top_col3 = st.columns([1, 1, 1])

    with top_col1:
        st.plotly_chart(dashboard.health_gauge(), use_container_width=True)

    with top_col2:
        st.markdown(
            f'<div class="personality-badge">'
            f'{personality["emoji"]} {personality["tag"]}<br>'
            f'<span style="font-size:0.8rem">{personality["desc"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="narrative-card">'
            f'<strong>💬 一句話總結</strong><br>{narratives["summary"]}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with top_col3:
        st.plotly_chart(dashboard.dimension_radar(), use_container_width=True)

    # ── Tabbed Detail Sections ──
    tabs = st.tabs([
        "📈 獲利能力",
        "🛡️ 償債能力",
        "⚡ 營運效率",
        "💰 現金流",
        "🔬 杜邦分析",
        "⚠️ 風險提醒",
        "📋 原始資料",
    ])

    # Tab: 獲利能力
    with tabs[0]:
        col_chart, col_text = st.columns([1, 1])
        with col_chart:
            st.plotly_chart(dashboard.profitability_bars(), use_container_width=True)
        with col_text:
            for item in narratives.get('profitability', []):
                st.markdown(
                    f'<div class="narrative-card">'
                    f'<strong>{item["title"]}</strong><br>{item["body"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Tab: 償債能力
    with tabs[1]:
        col_chart, col_text = st.columns([1, 1])
        with col_chart:
            st.plotly_chart(dashboard.solvency_bars(), use_container_width=True)
        with col_text:
            for item in narratives.get('solvency', []):
                st.markdown(
                    f'<div class="narrative-card">'
                    f'<strong>{item["title"]}</strong><br>{item["body"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Tab: 營運效率
    with tabs[2]:
        for item in narratives.get('efficiency', []):
            st.markdown(
                f'<div class="narrative-card">'
                f'<strong>{item["title"]}</strong><br>{item["body"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Tab: 現金流
    with tabs[3]:
        col_chart, col_text = st.columns([1, 1])
        with col_chart:
            st.plotly_chart(dashboard.cashflow_comparison(), use_container_width=True)
        with col_text:
            for item in narratives.get('cashflow', []):
                st.markdown(
                    f'<div class="narrative-card">'
                    f'<strong>{item["title"]}</strong><br>{item["body"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Tab: 杜邦分析
    with tabs[4]:
        col_chart, col_text = st.columns([1, 1])
        with col_chart:
            st.plotly_chart(dashboard.dupont_waterfall(), use_container_width=True)
        with col_text:
            for item in narratives.get('dupont', []):
                st.markdown(
                    f'<div class="narrative-card">'
                    f'<strong>{item["title"]}</strong><br>{item["body"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Tab: 風險提醒
    with tabs[5]:
        if not alerts:
            st.success("✅ 未偵測到重大風險")
        else:
            danger_alerts = [a for a in alerts if a['level'] == 'danger']
            warning_alerts = [a for a in alerts if a['level'] == 'warning']
            positive_alerts = [a for a in alerts if a['level'] == 'positive']
            info_alerts = [a for a in alerts if a['level'] == 'info']

            if danger_alerts:
                st.subheader("🔴 高風險", anchor=False)
                for a in danger_alerts:
                    st.error(f"🔴 **{a['ratio_name']}**：{a['message']}")

            if warning_alerts:
                st.subheader("🟡 注意事項", anchor=False)
                for a in warning_alerts:
                    st.warning(f"🟡 **{a['ratio_name']}**：{a['message']}")

            if positive_alerts:
                st.subheader("🟢 正面訊號", anchor=False)
                for a in positive_alerts:
                    st.success(f"🟢 **{a['ratio_name']}**：{a['message']}")

            if info_alerts:
                st.subheader("ℹ️ 備註資訊", anchor=False)
                for a in info_alerts:
                    st.info(f"ℹ️ **{a['ratio_name']}**：{a['message']}")

            if not danger_alerts and not warning_alerts:
                st.warning(
                    "⚠️ 本次分析未偵測到明顯風險訊號，但這**不代表完全沒有風險**。"
                    "財務數據僅反映過去表現，無法預測未來變化。"
                    "建議搭配產業趨勢、公司治理等非財務資訊綜合判斷，不應僅憑此結果做出投資決策。"
                )

    # Tab: 原始資料
    with tabs[6]:
        statements = st.session_state.get('statements', {})
        for key, label in [('balance_sheet', '合併資產負債表'),
                           ('income_statement', '合併綜合損益表'),
                           ('cash_flow', '合併現金流量表')]:
            df = statements.get(key, pd.DataFrame())
            if not df.empty:
                with st.expander(f"📄 {label}（{len(df)} 列）"):
                    display_cols = [c for c in df.columns if c != 'account']
                    st.dataframe(df[display_cols], use_container_width=True, height=400)

        st.markdown("#### 🔍 科目對照結果")
        summary = report.summary_dict()
        if summary:
            rows = []
            for key, item in summary.items():
                rows.append({
                    '標準欄位': key,
                    '科目名稱': item['label'],
                    '本期數值': f"{item['current']:,.0f}" if item['current'] else '—',
                    '前期數值': f"{item['previous']:,.0f}" if item.get('previous') else '—',
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # ── Report Download ──
    st.markdown("---")
    st.subheader("📥 下載分析報告", anchor=False)

    try:
        gen = ReportGenerator(
            cid, yr, ssn, ratios, health, personality, narratives, alerts
        )
        excel_bytes = gen.generate_excel()
        file_label = f"{cid}_{cname}" if cname else cid
        st.download_button(
            label="📥 下載 Excel 報告",
            data=excel_bytes,
            file_name=f"FinSight_{file_label}_{yr}Q{ssn}_報告.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    except Exception as e:
        st.error(f"報告產生失敗：{e}")

else:
    # ── Landing Page ──
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        #### 🔍 自動擷取
        從公開資訊觀測站 XBRL 平台自動擷取財務報表，不需手動上傳 PDF。
        """)
    with col2:
        st.markdown("""
        #### 🧠 智慧翻譯
        將複雜的財務數字翻譯成白話文，讓一般人也能看懂財報。
        """)
    with col3:
        st.markdown("""
        #### 📊 視覺化 Dashboard
        四大面向分析、健康評分、財務人格標籤，一眼掌握公司財務體質。
        """)

    st.markdown("---")
    st.markdown("#### 🚀 快速開始")
    st.markdown("""
    1. 在左側輸入**公司代號**（例如 2330 台積電）
    2. 選擇**年度**和**季度**
    3. 點擊 **「開始分析」**
    """)

    st.markdown("---")
    st.info("💡 **提示**：第四季（Q4）視為年度財報，資料最完整。建議優先選擇 Q4 進行分析。")
