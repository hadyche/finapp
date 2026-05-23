"""
Market Flow Intelligence Dashboard
====================================
Aggregates public data to surface where money is flowing:
  - USAspending.gov — federal contract awards by sector
  - SEC EDGAR       — institutional 13F filing activity
  - FRED            — macroeconomic indicators
  - yfinance        — sector ETF momentum

DISCLAIMER: For informational and educational purposes only.
This is NOT financial advice. Past signals do not guarantee future returns.
Always consult a licensed financial advisor before making investment decisions.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.data.gov_contracts import sector_spending_summary, top_recipients
from src.data.sec_filings import get_institution_filing_summary
from src.data.economic_indicators import fetch_all_indicators_latest, yield_curve_signal
from src.data.market_data import fetch_sector_performance, fetch_broad_market, fetch_sector_history
from src.analysis.scoring import build_sector_scores, signals_to_dataframe
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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0E1117; }
    .metric-card {
        background: #1E2130;
        border-radius: 8px;
        padding: 16px;
        margin: 4px;
    }
    .disclaimer {
        background: #1A1208;
        border-left: 3px solid #FFD600;
        padding: 10px 16px;
        border-radius: 4px;
        font-size: 0.8em;
        color: #FFD600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_sector_performance(days: int):
    cached = cache_get("sector_perf")
    if cached is not None:
        return cached
    df = fetch_sector_performance(days_back=days)
    cache_set("sector_perf", df)
    return df


@st.cache_data(ttl=21600, show_spinner=False)
def load_contracts(days: int):
    cached = cache_get("gov_contracts")
    if cached is not None:
        return cached
    df = sector_spending_summary(days_back=days)
    cache_set("gov_contracts", df)
    return df


@st.cache_data(ttl=43200, show_spinner=False)
def load_indicators():
    cached = cache_get("economic_indicators")
    if cached is not None:
        return cached
    df = fetch_all_indicators_latest()
    cache_set("economic_indicators", df)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def load_sec_filings():
    cached = cache_get("sec_filings")
    if cached is not None:
        return cached
    df = get_institution_filing_summary()
    cache_set("sec_filings", df)
    return df


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📊 Market Flow Intelligence")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
    st.markdown("- [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar)")
    st.markdown("- [FRED (St. Louis Fed)](https://fred.stlouisfed.org)")
    st.markdown("- [yfinance](https://finance.yahoo.com)")
    st.divider()

    if st.button("Refresh All Data"):
        from src.analysis.cache import cache_bust
        for key in ["gov_contracts", "sector_perf", "economic_indicators", "sec_filings"]:
            cache_bust(key)
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown(
        '<div class="disclaimer">⚠️ NOT financial advice. '
        "For informational purposes only. "
        "Consult a licensed advisor before investing.</div>",
        unsafe_allow_html=True,
    )

# ── Main content ───────────────────────────────────────────────────────────────

st.title("Where Is Money Flowing?")
st.caption("Aggregating government contracts, institutional filings, and market data into daily sector signals.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📈 Sector Scores", "🏛️ Gov Contracts", "📉 Market Data", "🏦 Economic Indicators", "🔎 Institutions"]
)

# ── Tab 1: Sector Scores ───────────────────────────────────────────────────────

with tab1:
    st.subheader("Sector Signal Scorecard")
    st.caption(
        "Combines government contract flow (0-40), market ETF momentum (0-40), "
        "and institutional filing activity (0-20) into a 0-100 score."
    )

    with st.spinner("Building scores..."):
        contracts_df = load_contracts(lookback)
        perf_df = load_sector_performance(lookback)

    if contracts_df.empty and perf_df.empty:
        st.warning("Could not load data. Check your internet connection.")
    else:
        signals = build_sector_scores(contracts_df, perf_df)
        scores_df = signals_to_dataframe(signals)

        col1, col2, col3 = st.columns(3)
        if len(signals) >= 1:
            top = signals[0]
            col1.metric("Top Sector", top.sector, f"Score: {top.total_score}/100")
        if len(signals) >= 2:
            second = signals[1]
            col2.metric("2nd Sector", second.sector, f"Score: {second.total_score}/100")
        if len(signals) >= 3:
            third = signals[2]
            col3.metric("3rd Sector", third.sector, f"Score: {third.total_score}/100")

        st.plotly_chart(score_heatmap(scores_df), use_container_width=True)

        st.dataframe(
            scores_df.style.background_gradient(
                subset=["Total Score (0-100)"], cmap="RdYlGn", vmin=0, vmax=100
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.caption(
            "Scoring methodology: Gov Contracts score = normalized $ flow (max 40). "
            "Market score = normalized ETF return (max 40). "
            "Institutional = baseline 10/20 (full 13F XML analysis requires premium data). "
            "Higher = more converging signals."
        )

# ── Tab 2: Government Contracts ─────────────────────────────────────────────────

with tab2:
    st.subheader("Federal Contract Awards")
    st.caption(f"Data from USAspending.gov — past {lookback} days")

    with st.spinner("Fetching contract data..."):
        contracts_df = load_contracts(lookback)
        recipients_df = top_recipients(days_back=lookback)

    if contracts_df.empty:
        st.warning(
            "No contract data returned. USAspending.gov may be slow or rate-limiting. "
            "Try refreshing in a few minutes."
        )
    else:
        st.plotly_chart(contract_treemap(contracts_df), use_container_width=True)
        st.plotly_chart(
            sector_bar_chart(
                contracts_df,
                x="sector",
                y="total_amount",
                title=f"Total Contract $ by Sector (last {lookback} days)",
            ),
            use_container_width=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Sector Summary**")
            if not contracts_df.empty:
                display = contracts_df.copy()
                display["total_amount"] = display["total_amount"].apply(
                    lambda x: f"${x:,.0f}"
                )
                st.dataframe(display, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("**Top Contract Recipients**")
            if not recipients_df.empty:
                display_r = recipients_df.copy()
                display_r["total_amount"] = display_r["total_amount"].apply(
                    lambda x: f"${x:,.0f}"
                )
                st.dataframe(display_r, hide_index=True, use_container_width=True)

# ── Tab 3: Market Data ─────────────────────────────────────────────────────────

with tab3:
    st.subheader("Sector ETF Performance")
    st.caption(f"SPDR sector ETFs — past {lookback} days via Yahoo Finance")

    with st.spinner("Fetching market data..."):
        perf_df = load_sector_performance(lookback)
        broad_df = fetch_broad_market(lookback)

    col1, col2, col3, col4 = st.columns(4)
    if not broad_df.empty:
        for i, (_, row) in enumerate(broad_df.iterrows()):
            [col1, col2, col3, col4][i % 4].metric(
                row["index"],
                f"${row['latest_price']:.2f}",
                f"{row['return_pct']:+.2f}%",
            )

    if not perf_df.empty:
        st.plotly_chart(sector_momentum_chart(perf_df), use_container_width=True)

        selected_sector = st.selectbox("View sector price history", perf_df["sector"].tolist())
        if selected_sector:
            with st.spinner(f"Loading {selected_sector} history..."):
                history = fetch_sector_history(selected_sector, days_back=90)
            if not history.empty:
                st.plotly_chart(price_history_chart(history, selected_sector), use_container_width=True)
    else:
        st.warning("Market data unavailable. Try refreshing.")

# ── Tab 4: Economic Indicators ─────────────────────────────────────────────────

with tab4:
    st.subheader("Macroeconomic Indicators")
    st.caption("From FRED (St. Louis Fed). Add FRED_API_KEY to .env for live data.")

    with st.spinner("Fetching indicators..."):
        indicators_df = load_indicators()
        yc_signal = yield_curve_signal()

    col1, col2 = st.columns([2, 1])
    with col1:
        if not indicators_df.empty:
            st.plotly_chart(indicators_gauge_row(indicators_df), use_container_width=True)
            st.dataframe(indicators_df, hide_index=True, use_container_width=True)
    with col2:
        st.markdown("**Yield Curve**")
        color = "red" if "INVERTED" in yc_signal else ("orange" if "FLAT" in yc_signal else "green")
        st.markdown(f":{color}[{yc_signal}]")
        st.divider()
        st.markdown(
            """
            **How to read:**
            - **GDP Growth** > 2% = healthy expansion
            - **CPI** rising fast = Fed likely to raise rates
            - **Unemployment** < 4% = tight labor market
            - **Inverted yield curve** = recession historically likely in 12-18mo
            - **Consumer Sentiment** dropping = spending slowdown ahead
            """
        )

# ── Tab 5: Institutional Filings ──────────────────────────────────────────────

with tab5:
    st.subheader("Institutional 13F Filing Tracker")
    st.caption(
        "SEC EDGAR — tracks when major institutions last filed 13F reports. "
        "13Fs are filed 45 days after each quarter-end."
    )

    with st.spinner("Fetching SEC filings..."):
        filings_df = load_sec_filings()

    if not filings_df.empty:
        st.dataframe(filings_df, hide_index=True, use_container_width=True)

    st.divider()
    st.markdown(
        """
        **How to use 13F data for market insights:**
        1. **BlackRock** manages ~$10T — its sector allocations set the benchmark
        2. **Look for increases** in a sector quarter-over-quarter as "smart money" signals
        3. **Combine with contracts**: if both gov spending AND BlackRock are buying defense, strong signal
        4. **Lag**: 13Fs are 45 days old by the time they're public — use as medium-term signals

        **Free tools to analyze actual holdings:**
        - [WhaleWisdom.com](https://whalewisdom.com) — tracks 13F changes
        - [13F.info](https://13f.info) — simple 13F viewer
        - [Fintel.io](https://fintel.io) — institutional flows & fund sentiment
        """
    )
