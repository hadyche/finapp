"""Settings — user preferences."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header
from src.data.favorites import get_favorites

inject_css()
page_header("⚙️ Settings", "Tune what counts as an asymmetric signal")

settings = st.session_state.settings

st.markdown('<div class="feed-section">Signal Thresholds</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">Defaults for the Signals feed</div>', unsafe_allow_html=True)

settings["min_ratio_pct"] = st.select_slider(
    "Minimum impact — award value as % of company market cap",
    options=[1, 2, 5, 10, 25],
    value=int(settings.get("min_ratio_pct", 1)),
    format_func=lambda x: f"{x}%",
    help="Higher = only the most dramatic mismatches. A 25% event means the contract is worth a quarter of the whole company.",
)
settings["max_cap_b"] = st.select_slider(
    "Maximum company size (market cap)",
    options=[0.5, 1.0, 2.0, 5.0],
    value=float(settings.get("max_cap_b", 5.0)),
    format_func=lambda x: f"${x:g}B",
    help="$5B is already below the smallest S&P 500 company. Go lower for true micro-caps (higher risk, thinner liquidity).",
)

st.divider()

st.markdown('<div class="feed-section">Your Data</div>', unsafe_allow_html=True)
favs = get_favorites()
fav_col1, fav_col2 = st.columns([1, 3])
with fav_col1:
    st.metric("Saved stocks", len(favs))
with fav_col2:
    if favs:
        st.caption("**Saved tickers:** " + ", ".join(sorted(favs)))
    else:
        st.caption("No saved stocks yet — tap ☆ Save on any stock's detail page.")

if favs and st.button("🗑️ Clear all saved stocks"):
    st.session_state.favorites = set()
    st.success("Cleared.")
    st.rerun()

st.divider()

st.markdown('<div class="feed-section">Data Sources</div>', unsafe_allow_html=True)
st.markdown("""
FlowSignal pulls only free, public, primary-source data — and never shows fake fallbacks:
- 🏛️ **USAspending.gov** — every federal contract award, updated daily
- 🗂️ **SEC** — the registry of all ~10,000 U.S. public companies + Form 4 insider filings
- 🎩 **STOCK Act disclosures** — Congress members' trades (via CapitolTrades)
- 👤 **OpenInsider** — market-wide Form 4 purchase screener
- 📈 **Yahoo Finance** — live prices, market caps, trading volume, news

No personal data is collected. Saved stocks live in your browser session only —
they reset when you refresh the page.
""")

st.divider()

st.markdown('<div class="feed-section">About</div>', unsafe_allow_html=True)
st.markdown("""
**FlowSignal BETA**
v0.2 · Built with Streamlit · Open source on [GitHub](https://github.com/hadyche/finapp)

Found a bug or have a feature request? Reach out on GitHub.
""")

st.markdown("""
<div style="background: rgba(255,82,82,0.06); border: 1px solid rgba(255,82,82,0.2);
border-radius: 10px; padding: 14px 18px; margin-top: 24px; color: #FCA5A5; font-size: 0.82rem;">
<strong>⚠️ Legal Disclaimer:</strong> FlowSignal is for informational and educational purposes only.
It is NOT investment advice and we are NOT licensed financial advisors. Small and micro-cap
stocks are volatile and often thinly traded. Past signals do not guarantee future returns.
You assume all risk for any investment decisions. Always consult a licensed financial
advisor before investing.
</div>
""", unsafe_allow_html=True)
