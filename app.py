"""
FlowSignal
==========
Where smart money is flowing today.

Cross-references federal contract awards + institutional 13F holdings
+ sector momentum to surface stocks with converging money flows.

DISCLAIMER: For informational and educational purposes only.
NOT financial advice. Past signals do not guarantee future returns.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.data.gov_contracts import sector_spending_summary, top_recipients
from src.data.sec_holdings import get_all_institution_changes, get_position_changes, INSTITUTIONS
from src.data.economic_indicators import fetch_all_indicators_latest, yield_curve_signal
from src.data.market_data import fetch_sector_performance, fetch_broad_market, fetch_sector_history
from src.analysis.scoring import build_sector_scores
from src.analysis.watchlist import (
    build_watchlist, watchlist_to_dataframe, SIZE_LABELS
)
from src.ui.charts import (
    sector_momentum_chart, price_history_chart, contract_treemap, indicators_gauge_row,
)

st.set_page_config(
    page_title="FlowSignal — Where smart money flows",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# Premium CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

.stApp { background: #0A0E16; }

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.stDeployButton { display: none; }

/* Hero */
.hero {
    padding: 24px 0 8px 0;
    border-bottom: 1px solid #1F2937;
    margin-bottom: 28px;
}
.brand {
    font-size: 1.6rem;
    font-weight: 800;
    color: #FAFAFA;
    letter-spacing: -0.02em;
    margin: 0;
}
.brand-accent { color: #00E676; }
.brand-beta {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 600;
    background: #1F2937;
    color: #9CA3AF;
    padding: 2px 8px;
    border-radius: 999px;
    margin-left: 8px;
    vertical-align: middle;
    letter-spacing: 0.05em;
}
.tagline {
    color: #9CA3AF;
    font-size: 1rem;
    margin-top: 4px;
    font-weight: 400;
}
.date-row {
    color: #6B7280;
    font-size: 0.85rem;
    margin-top: 12px;
}

/* Stock cards */
.pick-card {
    background: linear-gradient(135deg, #131A26 0%, #0F1520 100%);
    border: 1px solid #1F2937;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    transition: all 0.2s ease;
}
.pick-card:hover {
    border-color: #00E676;
    box-shadow: 0 8px 32px rgba(0, 230, 118, 0.08);
}
.pick-hero {
    background: linear-gradient(135deg, #0F1F19 0%, #0A1610 100%);
    border: 1px solid #00E676;
    box-shadow: 0 8px 40px rgba(0, 230, 118, 0.12);
}
.pick-rank {
    color: #6B7280;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    margin-bottom: 4px;
}
.pick-ticker {
    font-size: 2.4rem;
    font-weight: 800;
    color: #FAFAFA;
    letter-spacing: -0.04em;
    line-height: 1;
}
.pick-hero .pick-ticker {
    font-size: 3.2rem;
    background: linear-gradient(135deg, #00E676 0%, #4FC3F7 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.pick-name {
    font-size: 1.05rem;
    color: #E5E7EB;
    font-weight: 500;
    margin-top: 4px;
}
.pick-meta {
    color: #6B7280;
    font-size: 0.82rem;
    margin-top: 6px;
}
.pick-score-pill {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 0.02em;
    margin-top: 16px;
}
.score-strong { background: rgba(0, 230, 118, 0.15); color: #00E676; }
.score-positive { background: rgba(100, 221, 23, 0.12); color: #64DD17; }
.score-watch { background: rgba(255, 214, 0, 0.12); color: #FFD600; }

.signal-row {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #1F2937;
}
.signal-item {
    color: #D1D5DB;
    font-size: 0.9rem;
    margin: 6px 0;
    display: flex;
    align-items: center;
}
.signal-check { color: #00E676; margin-right: 8px; font-weight: 700; }

/* Size badges */
.size-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge-small { background: rgba(0, 230, 118, 0.15); color: #00E676; }
.badge-mid { background: rgba(79, 195, 247, 0.15); color: #4FC3F7; }
.badge-large { background: rgba(156, 163, 175, 0.15); color: #9CA3AF; }

/* Section headers */
.section-header {
    font-size: 1.3rem;
    font-weight: 700;
    color: #FAFAFA;
    margin: 32px 0 4px 0;
    letter-spacing: -0.02em;
}
.section-sub {
    color: #6B7280;
    font-size: 0.9rem;
    margin-bottom: 20px;
}

/* Source badges */
.source-pill {
    display: inline-block;
    background: #1F2937;
    color: #9CA3AF;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 0.78rem;
    margin: 4px 8px 4px 0;
    font-weight: 500;
}
.source-pill .check { color: #00E676; margin-right: 4px; }

/* Disclaimer */
.disclaimer {
    background: rgba(255, 152, 0, 0.06);
    border: 1px solid rgba(255, 152, 0, 0.2);
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 32px;
    color: #FCD34D;
    font-size: 0.82rem;
    line-height: 1.5;
}

/* Streamlit overrides */
.stButton > button {
    background: #00E676;
    color: #0A0E16;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 10px 20px;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: #00C853;
    transform: translateY(-1px);
}
div[data-testid="stExpander"] {
    background: #131A26;
    border: 1px solid #1F2937;
    border-radius: 12px;
}

/* Hide the default streamlit metric styling we don't want */
[data-testid="stMetricDelta"] svg { display: none; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Data loaders (cached)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_sector_performance(days: int):
    return fetch_sector_performance(days_back=days)

@st.cache_data(ttl=21600, show_spinner=False)
def load_contract_recipients(days: int):
    return top_recipients(days_back=days, top_n=20)

@st.cache_data(ttl=21600, show_spinner=False)
def load_contracts(days: int):
    return sector_spending_summary(days_back=days)

@st.cache_data(ttl=86400, show_spinner=False)
def load_holdings():
    return get_all_institution_changes()

@st.cache_data(ttl=86400, show_spinner=False)
def load_institution(name):
    return get_position_changes(name)

@st.cache_data(ttl=43200, show_spinner=False)
def load_indicators():
    return fetch_all_indicators_latest()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def size_badge_html(size: str) -> str:
    labels = {"small": "Small Cap", "mid": "Mid Cap", "large": "Large Cap"}
    classes = {"small": "badge-small", "mid": "badge-mid", "large": "badge-large"}
    return f'<span class="size-badge {classes.get(size, "badge-large")}">{labels.get(size, "Stock")}</span>'

def score_class(score: float) -> tuple[str, str]:
    if score >= 60: return "score-strong", "STRONG SIGNAL"
    if score >= 40: return "score-positive", "POSITIVE SIGNAL"
    return "score-watch", "EARLY WATCH"

def render_pick_card(entry, rank: int, is_hero: bool = False):
    score_cls, score_label = score_class(entry.score)
    hero_cls = "pick-hero" if is_hero else ""

    signals_html = ""
    for sig in entry.signals[:4]:
        signals_html += f'<div class="signal-item"><span class="signal-check">✓</span>{sig}</div>'

    sources_html = ""
    if entry.buying_institutions:
        for inst in entry.buying_institutions:
            sources_html += f'<span class="source-pill"><span class="check">✓</span>{inst}</span>'

    rank_label = "TOP PICK" if rank == 1 else f"#{rank}"

    st.markdown(f"""
    <div class="pick-card {hero_cls}">
        <div class="pick-rank">{rank_label}  ·  {entry.sector.upper()}</div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div class="pick-ticker">{entry.ticker}</div>
                <div class="pick-name">{entry.company}</div>
                <div class="pick-meta">{size_badge_html(entry.size)}</div>
            </div>
            <div style="text-align: right;">
                <div class="pick-score-pill {score_cls}">{score_label}</div>
                <div class="pick-meta" style="margin-top: 8px;">Score {entry.score}/100</div>
            </div>
        </div>
        <div class="signal-row">{signals_html}</div>
        <div style="margin-top: 14px;">{sources_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="hero">
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
            <div class="brand">Flow<span class="brand-accent">Signal</span><span class="brand-beta">BETA</span></div>
            <div class="tagline">Where smart money is flowing today.</div>
        </div>
    </div>
    <div class="date-row">📅 {datetime.now().strftime('%A, %B %d, %Y')} · Auto-refreshes every 6 hours</div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Settings (in a clean toolbar)
# ══════════════════════════════════════════════════════════════════════════════

settings_col1, settings_col2, settings_col3 = st.columns([2, 2, 3])
with settings_col1:
    mode = st.selectbox(
        "Show me",
        ["🔹 Hidden Gems (small/mid cap)", "📊 All stocks"],
        index=0,
        label_visibility="collapsed",
    )
with settings_col2:
    lookback = st.selectbox(
        "Time window",
        [7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"Last {x} days",
        label_visibility="collapsed",
    )
with settings_col3:
    advanced_mode = st.toggle("⚙️ Advanced (show dashboard)", value=False)

hidden_gems = "Hidden Gems" in mode

# ══════════════════════════════════════════════════════════════════════════════
# Load data once
# ══════════════════════════════════════════════════════════════════════════════

with st.spinner(""):
    holdings = load_holdings()
    perf = load_sector_performance(lookback)
    recipients = load_contract_recipients(lookback)

# Build watchlist (filtered to NEW + INCREASED for the home view)
home_changes = holdings[holdings["action"].isin(["NEW", "INCREASED"])] if not holdings.empty else holdings
watchlist = build_watchlist(home_changes, perf, recipients, hidden_gems_only=hidden_gems)
top_picks = [w for w in watchlist if w.buying_institutions and w.score >= 25][:5]


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLE HOME VIEW (default)
# ══════════════════════════════════════════════════════════════════════════════

if not advanced_mode:
    if not top_picks:
        st.warning("No picks meet the criteria right now. Try widening the time window.")
    else:
        # Hero pick (#1)
        st.markdown('<div class="section-header">Today\'s Top Pick</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Highest confluence of institutional buying + government contracts</div>', unsafe_allow_html=True)
        render_pick_card(top_picks[0], rank=1, is_hero=True)

        # Other picks
        if len(top_picks) > 1:
            st.markdown('<div class="section-header">Also Worth Watching</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-sub">Other stocks with strong converging signals</div>', unsafe_allow_html=True)

            for i, entry in enumerate(top_picks[1:], start=2):
                render_pick_card(entry, rank=i, is_hero=False)

        # How it works
        with st.expander("💡 How does FlowSignal work?", expanded=False):
            st.markdown("""
            **We watch 3 things every day:**

            🏛️ **Government Contracts** — Every federal contract awarded is public data. We track who's winning the big ones in defense, tech, healthcare, and infrastructure.

            🏦 **Institutional Holdings** — BlackRock, Vanguard, and State Street manage ~$25 trillion combined. When all three start buying the same small company, that's a powerful signal.

            📈 **Sector Momentum** — We track sector ETFs to see which industries are heating up.

            **When all three line up on the same stock**, we surface it. Small-cap signals are weighted more heavily because a new institutional position in a $500M company means far more than adding 0.01% to an Apple holding.

            **Sources:** USAspending.gov · SEC EDGAR · FRED · Yahoo Finance
            """)

        # Disclaimer
        st.markdown("""
        <div class="disclaimer">
        <strong>⚠️ Important:</strong> FlowSignal is for informational and educational purposes only.
        This is NOT financial advice. Past signals do not guarantee future returns. Markets are
        unpredictable. Always do your own research and consult a licensed financial advisor before
        making any investment decisions. You assume all risk.
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ADVANCED DASHBOARD (power users)
# ══════════════════════════════════════════════════════════════════════════════

else:
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Full Watchlist",
        "🏦 Institutions",
        "🏛️ Gov Contracts",
        "📊 Macro",
    ])

    with tab1:
        st.markdown('<div class="section-header">Full Scored Watchlist</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            min_score = st.slider("Minimum score", 0, 100, 20, step=5)
        with col2:
            actions = st.multiselect(
                "Institutional action",
                ["NEW", "INCREASED", "HELD", "DECREASED"],
                default=["NEW", "INCREASED"],
            )
        filt_changes = holdings[holdings["action"].isin(actions)] if actions else holdings
        full_wl = build_watchlist(filt_changes, perf, recipients, hidden_gems_only=hidden_gems)
        full_wl = [w for w in full_wl if w.score >= min_score]
        df = watchlist_to_dataframe(full_wl)

        if df.empty:
            st.info("No matches. Lower the score threshold or change filters.")
        else:
            chart_df = df.head(20)
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Institutional", x=chart_df["Ticker"],
                                 y=chart_df["Inst. Score"], marker_color="#00E676"))
            fig.add_trace(go.Bar(name="Gov Contracts", x=chart_df["Ticker"],
                                 y=chart_df["Contract"], marker_color="#4FC3F7"))
            fig.add_trace(go.Bar(name="Momentum", x=chart_df["Ticker"],
                                 y=chart_df["Momentum"], marker_color="#FFB74D"))
            fig.add_trace(go.Bar(name="Conviction", x=chart_df["Ticker"],
                                 y=chart_df["Conviction"], marker_color="#BA68C8"))
            fig.update_layout(
                barmode="stack", template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=400, xaxis_tickangle=-45,
                margin=dict(t=20, b=80, l=20, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        st.markdown('<div class="section-header">Institutional 13F Holdings</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Quarter-over-quarter position changes from SEC EDGAR</div>', unsafe_allow_html=True)
        inst_tabs = st.tabs(list(INSTITUTIONS.keys()))
        for tab_obj, inst_name in zip(inst_tabs, INSTITUTIONS.keys()):
            with tab_obj:
                ch = load_institution(inst_name)
                if ch.empty:
                    st.warning(f"No data for {inst_name}")
                    continue
                c1, c2, c3 = st.columns(3)
                c1.metric("New positions", len(ch[ch["action"] == "NEW"]))
                c2.metric("Increased", len(ch[ch["action"] == "INCREASED"]))
                c3.metric("Sold/Decreased", len(ch[ch["action"].isin(["DECREASED", "SOLD"])]))

                movers = ch[ch["action"].isin(["NEW", "INCREASED"])].head(15)
                if not movers.empty:
                    fig = px.bar(movers, x="ticker", y="value_current", color="action",
                                title=f"{inst_name} — top buys",
                                color_discrete_map={"NEW": "#00E676", "INCREASED": "#64DD17"},
                                template="plotly_dark")
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                     height=350, margin=dict(t=40, b=40, l=20, r=20))
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(ch, hide_index=True, use_container_width=True)

    with tab3:
        st.markdown('<div class="section-header">Federal Contract Awards</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-sub">From USAspending.gov · last {lookback} days</div>', unsafe_allow_html=True)
        contracts_df = load_contracts(lookback)
        if not contracts_df.empty:
            st.plotly_chart(contract_treemap(contracts_df), use_container_width=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**By sector**")
                d = contracts_df.copy()
                d["total_amount"] = d["total_amount"].apply(lambda x: f"${x:,.0f}")
                st.dataframe(d, hide_index=True, use_container_width=True)
            with c2:
                st.markdown("**Top recipients**")
                if not recipients.empty:
                    r = recipients.copy()
                    r["total_amount"] = r["total_amount"].apply(lambda x: f"${x:,.0f}")
                    st.dataframe(r, hide_index=True, use_container_width=True)

    with tab4:
        st.markdown('<div class="section-header">Macroeconomic Indicators</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">From FRED (St. Louis Fed) — economic context for the picks</div>', unsafe_allow_html=True)
        ind = load_indicators()
        yc = yield_curve_signal()
        c1, c2 = st.columns([3, 1])
        with c1:
            if not ind.empty:
                st.plotly_chart(indicators_gauge_row(ind), use_container_width=True)
                st.dataframe(ind, hide_index=True, use_container_width=True)
        with c2:
            st.markdown("**Yield Curve**")
            st.info(yc)

    st.markdown("""
    <div class="disclaimer" style="margin-top: 24px;">
    <strong>⚠️ Important:</strong> FlowSignal is for informational and educational purposes only.
    This is NOT financial advice. Past signals do not guarantee future returns.
    Always consult a licensed financial advisor before making investment decisions.
    </div>
    """, unsafe_allow_html=True)
