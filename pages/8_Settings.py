"""Settings — user preferences."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header
from src.data.favorites import get_favorites

inject_css()
page_header("⚙️ Settings", "Choose what counts as a big win")

settings = st.session_state.settings

st.markdown('<div class="feed-section">Your filters</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">These become the starting filters on the Picks page</div>', unsafe_allow_html=True)

settings["min_ratio_pct"] = st.select_slider(
    "How big must a deal be, compared to the company's value?",
    options=[1, 2, 5, 10, 25],
    value=int(settings.get("min_ratio_pct", 1)),
    format_func=lambda x: f"At least {x}%",
    help="Slide right to only see the most dramatic wins. At 25%, the deal is worth a quarter of the entire company.",
)
settings["max_cap_b"] = st.select_slider(
    "Biggest company you want to see",
    options=[0.5, 1.0, 2.0, 5.0],
    value=float(settings.get("max_cap_b", 5.0)),
    format_func=lambda x: f"Under ${x:g} billion",
    help="Even $5 billion is smaller than every famous stock. Slide left for truly tiny companies — bigger potential, bigger risk, harder to trade.",
)

st.divider()

st.markdown('<div class="feed-section">Your saved stocks</div>', unsafe_allow_html=True)
favs = get_favorites()
fav_col1, fav_col2 = st.columns([1, 3])
with fav_col1:
    st.metric("Saved", len(favs))
with fav_col2:
    if favs:
        st.caption("**Your stocks:** " + ", ".join(sorted(favs)))
    else:
        st.caption("Nothing saved yet — tap ☆ Save on any stock's page.")

if favs and st.button("🗑️ Clear all saved stocks"):
    st.session_state.favorites = set()
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
- 📈 **Yahoo Finance** — stock prices and company sizes

We don't collect anything about you. Saved stocks only last until you refresh the page.
""")

st.divider()

st.markdown('<div class="feed-section">About</div>', unsafe_allow_html=True)
st.markdown("""
**FlowSignal BETA**
v0.2 · Built with Streamlit · Open source on [GitHub](https://github.com/hadyche/finapp)

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
