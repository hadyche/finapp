"""Settings — user preferences."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header
from src.data.favorites import get_favorites

inject_css()
page_header("⚙️ Settings", "Customize FlowSignal to your preferences")

settings = st.session_state.settings

st.markdown('<div class="section-h">Default Filters</div>', unsafe_allow_html=True)
st.markdown('<div class="section-s">Applied across the Home and Discover pages</div>', unsafe_allow_html=True)

settings["lookback_days"] = st.selectbox(
    "Default time window for contract data",
    [7, 14, 30, 60, 90, 180],
    index=[7, 14, 30, 60, 90, 180].index(settings.get("lookback_days", 30)),
    format_func=lambda x: f"Last {x} days",
)
settings["min_score"] = st.slider(
    "Minimum score for picks to appear on Home",
    0, 100,
    value=settings.get("min_score", 25),
    step=5,
    help="Lower = more picks (some lower quality). Higher = only strong signals."
)
settings["hidden_gems_only"] = st.toggle(
    "🔹 Show Hidden Gems by default (small & mid cap only)",
    value=settings.get("hidden_gems_only", True),
    help="Filter out large-cap stocks most people already know about."
)

st.divider()

st.markdown('<div class="section-h">Your Data</div>', unsafe_allow_html=True)
favs = get_favorites()
fav_col1, fav_col2 = st.columns([1, 3])
with fav_col1:
    st.metric("Favorites", len(favs))
with fav_col2:
    if favs:
        st.caption("**Saved tickers:** " + ", ".join(sorted(favs)))
    else:
        st.caption("No favorites saved yet.")

if favs and st.button("🗑️ Clear all favorites"):
    st.session_state.favorites = set()
    st.success("Favorites cleared.")
    st.rerun()

st.divider()

st.markdown('<div class="section-h">Data Sources</div>', unsafe_allow_html=True)
st.markdown("""
FlowSignal pulls from these free, public data sources:
- 🏛️ **USAspending.gov** — Federal contract awards
- 🏦 **SEC EDGAR** — Institutional 13F filings (BlackRock, Vanguard, State Street)
- 📊 **FRED** (Federal Reserve) — Macroeconomic indicators
- 📈 **Yahoo Finance** — Live stock prices and fundamentals

No personal data is collected. Favorites are stored in your browser session.
""")

st.divider()

st.markdown('<div class="section-h">About</div>', unsafe_allow_html=True)
st.markdown("""
**FlowSignal BETA**
v0.1 · Built with Streamlit · Open source on [GitHub](https://github.com/hadyche/finapp)

Found a bug or have a feature request? Reach out on GitHub.
""")

st.markdown("""
<div style="background: rgba(255,82,82,0.06); border: 1px solid rgba(255,82,82,0.2);
border-radius: 10px; padding: 14px 18px; margin-top: 24px; color: #FCA5A5; font-size: 0.82rem;">
<strong>⚠️ Legal Disclaimer:</strong> FlowSignal is for informational and educational purposes only.
It is NOT investment advice and we are NOT licensed financial advisors. Past signals do not
guarantee future returns. You assume all risk for any investment decisions. Always consult
a licensed financial advisor before investing.
</div>
""", unsafe_allow_html=True)
