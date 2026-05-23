"""Favorites — saved stocks."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header, disclaimer
from src.ui.components import render_pick_card
from src.data.favorites import get_favorites, remove_favorite
from src.data.sec_holdings import get_all_institution_changes
from src.data.market_data import fetch_sector_performance
from src.data.gov_contracts import top_recipients
from src.analysis.watchlist import build_watchlist

inject_css()
page_header("⭐ Favorites", "Stocks you've saved to track")

favs = get_favorites()

if not favs:
    st.info("No favorites yet. Tap **☆ Save** on any stock from the Home or Discover page to add it here.")
    disclaimer()
    st.stop()

st.caption(f"You have **{len(favs)}** saved stocks.")

@st.cache_data(ttl=3600)
def _all_data(days):
    return (
        get_all_institution_changes(),
        fetch_sector_performance(days_back=days),
        top_recipients(days_back=days, top_n=20),
    )

lookback = st.session_state.settings.get("lookback_days", 30)
holdings, perf, recipients = _all_data(lookback)

watchlist = build_watchlist(holdings, perf, recipients, hidden_gems_only=False)
favs_entries = [w for w in watchlist if w.ticker.upper() in favs]

# Show favorites that have signal data
found = {e.ticker for e in favs_entries}
missing = favs - found

if favs_entries:
    st.markdown('<div class="section-h">Your Tracked Stocks</div>', unsafe_allow_html=True)
    for i, entry in enumerate(favs_entries):
        render_pick_card(entry, key_prefix=f"fav_{i}")

if missing:
    st.markdown('<div class="section-h">Other Saved Tickers</div>', unsafe_allow_html=True)
    st.caption("These don't currently have institutional/contract signal data, but you can still view their details.")
    for ticker in sorted(missing):
        cols = st.columns([1, 3, 1, 1])
        cols[0].markdown(f"### {ticker}")
        cols[2].button("Details", key=f"miss_view_{ticker}",
                       on_click=lambda t=ticker: (
                           st.session_state.update(selected_ticker=t),
                           st.switch_page("pages/3_Stock_Detail.py")
                       ))
        if cols[3].button("Remove", key=f"miss_rm_{ticker}"):
            remove_favorite(ticker)
            st.rerun()

disclaimer()
