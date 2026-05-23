"""
Market Flow Intelligence Dashboard
====================================
Aggregates public data to surface where money is flowing:
  - USAspending.gov — federal contract awards by sector
  - SEC EDGAR 13F   — actual institutional holdings (BlackRock, Vanguard, State Street)
  - FRED            — macroeconomic indicators
  - yfinance        — sector ETF momentum

Produces a ranked stock watchlist of tickers where government money
AND institutional smart money are flowing in the same direction.

DISCLAIMER: For informational and educational purposes only.
This is NOT financial advice. Past signals do not guarantee future returns.
Always consult a licensed financial advisor before making investment decisions.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.data.gov_contracts import sector_spending_summary, top_recipients, fetch_recent_awards
from src.data.sec_holdings import get_all_institution_changes, get_position_changes, INSTITUTIONS
from src.data.sec_filings import get_institution_filing_summary
from src.data.economic_indicators import fetch_all_indicators_latest, yield_curve_signal
from src.data.market_data import fetch_sector_performance, fetch_broad_market, fetch_sector_history
from src.analysis.scoring import build_sector_scores, signals_to_dataframe
from src.analysis.watchlist import build_watchlist, watchlist_to_dataframe
from src.analysis.cache import cache_get, cache_set
from src.ui.charts import (
    sector_bar_chart,
    score_heatmap,
    sector_momentum_chart,
    price_history_chart,
    contract_treemap,
    indicators_gauge_row,
)

st.set_page_config(
    page_title="Market Flow Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0E1117; }
    .disclaimer {
        background: #1A1208;
        border-left: 3px solid #FFD600;
        padding: 10px 16px;
        border-radius: 4px;
        font-size: 0.8em;
        color: #FFD600;
    }
    .signal-strong { color: #00C853; font-weight: bold; }
    .signal-positive { color: #64DD17; }
    .signal-neutral { color: #FFD600; }
    .signal-weak { color: #FF6D00; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Cached data loaders ────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_sector_performance(days: int):
    return fetch_sector_performance(days_back=days)


@st.cache_data(ttl=21600, show_spinner=False)
def load_contracts(days: int):
    return sector_spending_summary(days_back=days)


@st.cache_data(ttl=21600, show_spinner=False)
def load_contract_recipients(days: int):
    return top_recipients(days_back=days, top_n=20)


@st.cache_data(ttl=43200, show_spinner=False)
def load_indicators():
    return fetch_all_indicators_latest()


@st.cache_data(ttl=86400, show_spinner=False)
def load_all_holdings_changes():
    return get_all_institution_changes()


@st.cache_data(ttl=86400, show_spinner=False)
def load_institution_changes(name: str):
    return get_position_changes(name)


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📈 Market Flow Intelligence")
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.divider()

    lookback = st.selectbox(
        "Contract lookback window",
        [7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"{x} days",
    )

    st.divider()
    st.markdown("**Data Sources**")
    st.markdown("- [USAspending.gov](https://www.usaspending.gov)")
    st.markdown("- [SEC EDGAR 13F](https://www.sec.gov/cgi-bin/browse-edgar)")
    st.markdown("- [FRED](https://fred.stlouisfed.org)")
    st.markdown("- [Yahoo Finance](https://finance.yahoo.com)")
    st.divider()

    if st.button("🔄 Refresh All Data"):
        from src.analysis.cache import cache_bust
        for key in ["gov_contracts", "sector_perf", "economic_indicators", "sec_filings"]:
            cache_bust(key)
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown(
        '<div class="disclaimer">⚠️ NOT financial advice. '
        "Informational only. Past signals ≠ future returns. "
        "Consult a licensed advisor before investing.</div>",
        unsafe_allow_html=True,
    )

# ── Main ───────────────────────────────────────────────────────────────────────

st.title("Where Is Smart Money Flowing?")
st.caption(
    "Cross-references federal contract awards + BlackRock/Vanguard/State Street 13F holdings "
    "to surface stocks with converging institutional and government money flows."
)

tab_watch, tab_inst, tab_contracts, tab_market, tab_macro = st.tabs([
    "🎯 Stock Watchlist",
    "🏦 Institutional Holdings",
    "🏛️ Gov Contracts",
    "📉 Market Data",
    "📊 Macro Indicators",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — STOCK WATCHLIST (the main output)
# ══════════════════════════════════════════════════════════════════════════════

with tab_watch:
    title_col, info_col = st.columns([6, 1])
    with title_col:
        st.subheader("Ranked Stock Watchlist")
    with info_col:
        with st.popover("ℹ️ How scores work", use_container_width=True):
            st.markdown("""
#### Score Breakdown (0–100)

Each stock is scored across 4 signals that are added together:

---

**🟢 Institutional Score (up to 60 pts)**
Tracks what BlackRock, Vanguard & State Street are doing with their 13F filings each quarter.

| Action | Points |
|--------|--------|
| NEW position opened | 15 pts × size multiplier |
| Position INCREASED | 12 pts × size multiplier |
| Position HELD | 3 pts |

**Size multipliers** (why small caps score higher):
- 🔹 Small cap (< $3B): **2×** — a new position means real conviction
- 🔸 Mid cap ($3–15B): **1.4×** — still meaningful
- ⬜ Large cap (> $15B): **1×** — routine index buying

---

**🔵 Government Contract Score (up to 30 pts)**
Scaled from USAspending.gov contract award data.
The top contract recipient gets 30 pts; others are scaled relative to them.

---

**🟠 Sector Momentum Score (up to 15 pts)**
Based on the sector ETF (e.g. XLK for tech, ITA for defense) return over your selected time window.
Rising sector = rising tide for stocks in it.

---

**🟣 Conviction Score (up to 10 pts)**
Total dollar value held across all 3 institutions.
Larger combined position = higher institutional conviction.

---

**Signal thresholds:**
- **60+** → STRONG SIGNAL
- **40–59** → POSITIVE SIGNAL
- **25–39** → WATCH
- **< 25** → WEAK

> ⚠️ This is not financial advice. Past signals do not guarantee future returns.
            """)

    with st.spinner("Analyzing institutional holdings & contracts..."):
        holdings_changes = load_all_holdings_changes()
        perf_df = load_sector_performance(lookback)
        recipients_df = load_contract_recipients(lookback)

    if holdings_changes.empty:
        st.warning("Could not load holdings data.")
    else:
        # ── Mode toggle ────────────────────────────────────────────────────────
        col_mode1, col_mode2 = st.columns([1, 2])
        with col_mode1:
            hidden_gems = st.toggle(
                "🔹 Hidden Gems mode",
                value=True,
                help="ON = small & mid-cap only (under-the-radar picks). OFF = all sizes including large cap.",
            )
        with col_mode2:
            show_actions = st.multiselect(
                "Institution action filter",
                ["NEW", "INCREASED", "HELD", "DECREASED"],
                default=["NEW", "INCREASED"],
            )

        min_score = st.slider("Minimum score to show", 0, 100, 20, step=5)

        if show_actions:
            filtered_changes = holdings_changes[holdings_changes["action"].isin(show_actions)]
        else:
            filtered_changes = holdings_changes

        watchlist = build_watchlist(
            filtered_changes, perf_df, recipients_df, hidden_gems_only=hidden_gems
        )
        scored = [w for w in watchlist if w.score >= min_score]
        wl_df = watchlist_to_dataframe(scored)

        if hidden_gems:
            st.caption(
                "🔹 Hidden Gems mode ON — showing small & mid-cap stocks only. "
                "Small cap NEW positions score 2x, mid cap 1.4x. "
                "These are the lesser-known names most people haven't heard of."
            )
        else:
            st.caption("Showing all market caps. Toggle Hidden Gems to focus on under-the-radar picks.")

        st.divider()

        # ── Top 3 highlight cards ──────────────────────────────────────────────
        top3 = [w for w in scored if w.buying_institutions][:3]
        if top3:
            cols = st.columns(3)
            for i, entry in enumerate(top3):
                with cols[i]:
                    from src.analysis.watchlist import SIZE_LABELS
                    size_label = SIZE_LABELS.get(entry.size, "")
                    st.metric(
                        label=f"#{i+1} {entry.ticker}  {size_label}",
                        value=entry.company[:24],
                        delta=f"Score {entry.score}/100 — {entry.recommendation}",
                    )
                    st.caption(f"{entry.sector} | " + " + ".join(entry.buying_institutions))

        st.divider()

        if wl_df.empty:
            st.info("No stocks match these filters. Try lowering the score threshold or adjusting the action filter.")
        else:
            # Stacked score chart
            chart_df = wl_df.head(20).copy()
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Institutional",  x=chart_df["Ticker"],
                                  y=chart_df["Inst. Score"],    marker_color="#00C853"))
            fig.add_trace(go.Bar(name="Gov Contracts",  x=chart_df["Ticker"],
                                  y=chart_df["Contract"],       marker_color="#2196F3"))
            fig.add_trace(go.Bar(name="Momentum",       x=chart_df["Ticker"],
                                  y=chart_df["Momentum"],       marker_color="#FF9800"))
            fig.add_trace(go.Bar(name="Conviction",     x=chart_df["Ticker"],
                                  y=chart_df["Conviction"],     marker_color="#9C27B0"))
            fig.update_layout(
                barmode="stack",
                title="Top Stocks — Score Breakdown (small caps boosted)",
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=430,
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Size distribution pie
            if "Size" in wl_df.columns:
                size_counts = wl_df["Size"].value_counts().reset_index()
                size_counts.columns = ["Size", "count"]
                fig2 = px.pie(
                    size_counts, names="Size", values="count",
                    title="Watchlist Breakdown by Market Cap",
                    template="plotly_dark",
                    color_discrete_sequence=["#00C853", "#FF9800", "#9E9E9E"],
                )
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", height=280
                )
                st.plotly_chart(fig2, use_container_width=True)

            # Full table
            st.dataframe(
                wl_df.style.background_gradient(
                    subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.markdown(
            """
            **Scoring guide:**
            | Score | Signal | Meaning |
            |-------|--------|---------|
            | 60+ | STRONG | Multiple institutions buying + gov contracts flowing in |
            | 40–59 | POSITIVE | At least 1 institution actively buying |
            | 25–39 | WATCH | Early signal, one factor present |
            | < 25 | WEAK | Not enough confluence yet |

            **Why small caps score higher:** A NEW position in a $500M company means far more than
            adding 0.01% to an Apple position. The size multiplier reflects that.
            """
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INSTITUTIONAL HOLDINGS (BlackRock / Vanguard / State Street)
# ══════════════════════════════════════════════════════════════════════════════

with tab_inst:
    inst_title_col, inst_info_col = st.columns([6, 1])
    with inst_title_col:
        st.subheader("Institutional 13F Holdings — Quarter-over-Quarter Changes")
    with inst_info_col:
        with st.popover("ℹ️ What is a 13F?", use_container_width=True):
            st.markdown("""
#### What is a 13F Filing?

Any investment manager with **$100M+ in assets** must file a **Form 13F** with the SEC every quarter, listing every stock they hold.

**Why it matters:**
- BlackRock manages ~$10 **trillion**
- Vanguard + State Street together own ~15% of every S&P 500 stock
- When they open a NEW position in a small company, it's a powerful signal

**Actions explained:**
| Action | Meaning |
|--------|---------|
| 🟢 NEW | Opened a brand new position this quarter |
| 🟩 INCREASED | Added more shares vs. last quarter |
| ⬜ HELD | Same position, no change |
| 🟥 DECREASED | Trimmed the position |
| ❌ SOLD | Exited entirely |

**Important lag:** 13Fs are filed **45 days after** each quarter ends.
So Q4 (Oct–Dec) data becomes public in mid-February.
Use for medium-term signals, not short-term trading.
            """)
    st.caption("NEW = opened this quarter | INCREASED = added shares | DECREASED = trimmed | SOLD = exited.")

    inst_tab1, inst_tab2, inst_tab3 = st.tabs(list(INSTITUTIONS.keys()))

    for tab_obj, inst_name in zip([inst_tab1, inst_tab2, inst_tab3], INSTITUTIONS.keys()):
        with tab_obj:
            with st.spinner(f"Loading {inst_name} holdings..."):
                changes_df = load_institution_changes(inst_name)

            if changes_df.empty:
                st.warning(f"No data for {inst_name}")
                continue

            # Summary metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("New Positions",      len(changes_df[changes_df["action"] == "NEW"]))
            c2.metric("Increased",          len(changes_df[changes_df["action"] == "INCREASED"]))
            c3.metric("Decreased/Sold",     len(changes_df[changes_df["action"].isin(["DECREASED","SOLD"])]))
            c4.metric("Total Holdings",     len(changes_df))

            # Action filter
            action_filter = st.multiselect(
                "Filter by action",
                ["NEW", "INCREASED", "HELD", "DECREASED", "SOLD"],
                default=["NEW", "INCREASED"],
                key=f"filter_{inst_name}",
            )
            display = changes_df[changes_df["action"].isin(action_filter)] if action_filter else changes_df

            # Top movers chart
            movers = display[display["action"].isin(["NEW","INCREASED"])].head(15)
            if not movers.empty:
                fig = px.bar(
                    movers,
                    x="ticker",
                    y="value_current",
                    color="action",
                    title=f"{inst_name} — New & Increased Positions",
                    color_discrete_map={"NEW": "#00C853", "INCREASED": "#64DD17"},
                    template="plotly_dark",
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    height=380,
                    yaxis_title="Current Value ($)",
                    xaxis_title="Ticker",
                )
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                display.style.background_gradient(
                    subset=["value_change_pct"], cmap="RdYlGn", vmin=-50, vmax=50
                ),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    st.markdown(
        """
        **Why 13F filings matter:**
        - BlackRock manages ~$10 trillion — its buys/sells move markets
        - Vanguard + State Street together hold ~15% of every S&P 500 company
        - When all three increase the same position → very strong institutional conviction
        - **Lag:** 13Fs are filed 45 days after quarter-end — use for medium-term signals, not trading

        **Free tools to dig deeper:**
        - [WhaleWisdom.com](https://whalewisdom.com) | [13F.info](https://13f.info) | [Fintel.io](https://fintel.io)
        """
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — GOVERNMENT CONTRACTS
# ══════════════════════════════════════════════════════════════════════════════

with tab_contracts:
    ct_title, ct_info = st.columns([6, 1])
    with ct_title:
        st.subheader("Federal Contract Awards")
    with ct_info:
        with st.popover("ℹ️ About this data", use_container_width=True):
            st.markdown("""
#### Federal Contract Data

Source: **USAspending.gov** — the official U.S. government open data portal for all federal spending.

**What it shows:**
- Every contract awarded by federal agencies (DoD, DHS, HHS, DOE, etc.)
- Grouped by NAICS industry sector
- Filtered to the lookback window you selected in the sidebar

**Why contracts matter:**
A company winning a large federal contract gets **guaranteed revenue** — often multi-year.
This is one of the strongest leading indicators for small/mid-cap growth, especially in:
- Defense & aerospace
- Cybersecurity & IT services
- Healthcare services (Medicare/Medicaid)
- Infrastructure & construction
- Nuclear & clean energy

**How to use it:**
Cross-reference the top recipients with the Watchlist tab.
If a company is getting contracts AND institutions are buying → strong signal.
            """)
    st.caption(f"Data from USAspending.gov — past {lookback} days")

    with st.spinner("Fetching contract data..."):
        contracts_df = load_contracts(lookback)
        recipients_df = load_contract_recipients(lookback)

    if not contracts_df.empty:
        st.plotly_chart(contract_treemap(contracts_df), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Sector Summary**")
            display = contracts_df.copy()
            display["total_amount"] = display["total_amount"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(display, hide_index=True, use_container_width=True)
        with col2:
            st.markdown("**Top Contract Recipients**")
            if not recipients_df.empty:
                disp_r = recipients_df.copy()
                disp_r["total_amount"] = disp_r["total_amount"].apply(lambda x: f"${x:,.0f}")
                st.dataframe(disp_r, hide_index=True, use_container_width=True)
    else:
        st.warning("Contract data unavailable. Try refreshing.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — MARKET DATA
# ══════════════════════════════════════════════════════════════════════════════

with tab_market:
    st.subheader("Sector ETF Performance")
    st.caption(f"SPDR sector ETFs — past {lookback} days")

    with st.spinner("Fetching market data..."):
        perf_df2 = load_sector_performance(lookback)
        broad_df = fetch_broad_market(lookback)

    col1, col2, col3, col4 = st.columns(4)
    if not broad_df.empty:
        for i, (_, row) in enumerate(broad_df.iterrows()):
            [col1, col2, col3, col4][i % 4].metric(
                row["index"], f"${row['latest_price']:.2f}", f"{row['return_pct']:+.2f}%"
            )

    if not perf_df2.empty:
        st.plotly_chart(sector_momentum_chart(perf_df2), use_container_width=True)

        selected = st.selectbox("View 90-day price history", perf_df2["sector"].tolist())
        if selected:
            with st.spinner(f"Loading {selected}..."):
                hist = fetch_sector_history(selected, days_back=90)
            if not hist.empty:
                st.plotly_chart(price_history_chart(hist, selected), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — MACRO INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

with tab_macro:
    macro_title, macro_info = st.columns([6, 1])
    with macro_title:
        st.subheader("Macroeconomic Indicators")
    with macro_info:
        with st.popover("ℹ️ Reading the indicators", use_container_width=True):
            st.markdown("""
#### How to Read Macro Indicators

Source: **FRED** (Federal Reserve Bank of St. Louis) — the gold standard for free economic data.

| Indicator | Bullish | Bearish |
|-----------|---------|---------|
| GDP Growth | > 2% | < 0% (recession) |
| CPI Inflation | 2–3% | > 5% (Fed hikes rates) |
| Unemployment | < 4% | Rising fast |
| Fed Funds Rate | Falling | Rising (hurts growth) |
| 10Y Treasury | Stable / falling | Spiking up |
| Consumer Sentiment | > 80 | Dropping fast |

**Yield Curve (10Y minus 2Y):**
- **Normal** (10Y > 2Y): healthy economy
- **Flat** (spread < 0.5%): slowdown risk
- **Inverted** (2Y > 10Y): historically precedes recession by 12–18 months

**How to combine with the Watchlist:**
- Rising rates → favor defense, energy, financials
- Rate cuts expected → tech and growth stocks benefit
- Recession signal → stay defensive (healthcare, staples)
            """)
    st.caption("From FRED (St. Louis Fed). Add FRED_API_KEY to secrets for live data.")

    with st.spinner("Fetching indicators..."):
        indicators_df = load_indicators()
        yc_signal = yield_curve_signal()

    col1, col2 = st.columns([2, 1])
    with col1:
        if not indicators_df.empty:
            st.plotly_chart(indicators_gauge_row(indicators_df), use_container_width=True)
            st.dataframe(indicators_df, hide_index=True, use_container_width=True)
    with col2:
        st.markdown("**Yield Curve Signal**")
        color = "red" if "INVERTED" in yc_signal else ("orange" if "FLAT" in yc_signal else "green")
        st.markdown(f":{color}[{yc_signal}]")
        st.divider()
        st.markdown("""
        **How to read:**
        - **GDP > 2%** = healthy expansion
        - **CPI rising fast** = rate hike risk
        - **Unemployment < 4%** = tight labor
        - **Inverted yield curve** = recession risk in 12-18mo
        - **Sentiment dropping** = slowdown ahead
        """)
