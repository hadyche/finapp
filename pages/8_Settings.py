"""About — saved stocks, data sources, and the honest fine print."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header
from src.data.favorites import get_favorites

inject_css()
page_header("ℹ️ About FlowSignal", "What this app is, where its information comes from, and your saved stocks")

st.markdown('<div class="feed-section">Your saved stocks</div>', unsafe_allow_html=True)
favs = get_favorites()
fav_col1, fav_col2 = st.columns([1, 3])
with fav_col1:
    st.metric("Saved", len(favs))
with fav_col2:
    if favs:
        chips = "".join(
            f'<a class="feed-link" style="display:inline-block;" href="stock?t={t}" target="_self">'
            f'<span class="source-chip">⭐ {t}</span></a>'
            for t in sorted(favs)
        )
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.caption("Nothing saved yet — tap ☆ Save on any stock's page.")

if favs:
    st.caption(
        "💡 **Your saved stocks travel in the web address.** Bookmark this page "
        "(or any page) after saving, and your list comes back with the bookmark — "
        "no account needed."
    )
    if st.button("🗑️ Clear all saved stocks"):
        st.session_state.favorites = set()
        try:
            if "w" in st.query_params:
                del st.query_params["w"]
        except Exception:
            pass
        st.success("Cleared.")
        st.rerun()

st.divider()

st.markdown('<div class="feed-section">Where the information comes from</div>', unsafe_allow_html=True)
st.markdown("""
Everything in FlowSignal comes from free, public, official sources — and we never
show made-up numbers. If a source is down, we tell you.

- 🏛️ **USAspending.gov** — the government's own list of every deal it makes
- 🗂️ **SEC.gov** — the official registry of all U.S. public companies, plus the forms bosses file when they buy stock
- 🎩 **Senate.gov** — senators' trade reports, from the official disclosure site
- 👤 **OpenInsider** — a free view of the SEC's insider-buying filings
- 📈 **Yahoo Finance** — stock prices, company sizes, and trading volume

We don't collect anything about you.
""")

st.divider()

st.markdown('<div class="feed-section">About</div>', unsafe_allow_html=True)
st.markdown("""
**FlowSignal BETA**
v0.3 · Built with Streamlit · Open source on [GitHub](https://github.com/hadyche/finapp)

Found a bug or have a feature request? Reach out on GitHub.
""")

st.markdown("""
<div style="background: rgba(220,38,38,0.06); border: 1px solid rgba(220,38,38,0.3);
border-radius: 10px; padding: 14px 18px; margin-top: 24px; color: #991B1B; font-size: 0.82rem;">
<strong>⚠️ The important warning (please actually read this):</strong> FlowSignal shows you
interesting public information — it does NOT tell you what to buy. We are not financial
advisors. Small companies' stocks can drop fast and hard, and past results don't promise
future ones. Never invest money you can't afford to lose, and talk to a licensed
financial advisor before making real decisions. In legal terms: this is for informational
and educational purposes only and is not investment advice; you assume all risk for
your investment decisions.
</div>
""", unsafe_allow_html=True)
