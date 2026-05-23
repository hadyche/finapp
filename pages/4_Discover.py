"""Discover — browse and filter all scored stocks."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header, disclaimer
from src.ui.components import render_compact_row
from src.data.sec_holdings import get_all_institution_changes
from src.data.market_data import fetch_sector_performance
from src.data.gov_contracts import top_recipients
from src.analysis.watchlist import build_watchlist

inject_css()
page_header("🔍 Discover", "Filter and explore all stocks with FlowSignal data")

# Filter panel
with st.expander("🎛️ Filters", expanded=True):
    f1, f2 = st.columns(2)
    with f1:
        lookback = st.selectbox(
            "Time window",
            [7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"Last {x} days",
        )
        actions = st.multiselect(
            "Institutional action",
            ["NEW", "INCREASED", "HELD", "DECREASED"],
            default=["NEW", "INCREASED"],
        )
    with f2:
        sizes = st.multiselect(
            "Company size",
            ["Small Cap", "Mid Cap", "Large Cap"],
            default=["Small Cap", "Mid Cap"],
        )
        min_score = st.slider("Minimum score", 0, 100, 20, step=5)

    sectors_filter = st.multiselect(
        "Sector",
        ["Defense", "Technology", "Healthcare", "Financials", "Industrials",
         "Consumer Disc.", "Consumer Staples", "Energy", "Communication"],
        default=[],
    )

@st.cache_data(ttl=3600)
def _data(days):
    return (
        get_all_institution_changes(),
        fetch_sector_performance(days_back=days),
        top_recipients(days_back=days, top_n=20),
    )

holdings, perf, recipients = _data(lookback)
if actions and not holdings.empty:
    holdings = holdings[holdings["action"].isin(actions)]

watchlist = build_watchlist(holdings, perf, recipients, hidden_gems_only=False)

# Filter by size and sector and score
size_map = {"Small Cap": "small", "Mid Cap": "mid", "Large Cap": "large"}
allowed_sizes = {size_map[s] for s in sizes} if sizes else {"small", "mid", "large"}

results = [
    w for w in watchlist
    if w.size in allowed_sizes
    and w.score >= min_score
    and (not sectors_filter or w.sector in sectors_filter)
]

st.caption(f"Showing **{len(results)}** stocks matching your filters")

if not results:
    st.info("No stocks match these filters. Try relaxing them.")
else:
    sort_col1, sort_col2 = st.columns([1, 4])
    with sort_col1:
        sort_by = st.selectbox("Sort by", ["Score", "Sector", "Ticker"], label_visibility="collapsed")
    if sort_by == "Sector":
        results = sorted(results, key=lambda x: (x.sector, -x.score))
    elif sort_by == "Ticker":
        results = sorted(results, key=lambda x: x.ticker)

    for i, entry in enumerate(results):
        render_compact_row(entry, key_prefix=f"disc_{i}")

disclaimer()
