"""Home — Today's Picks (the main landing page)."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.ui.theme import inject_css, page_header, disclaimer
from src.ui.components import render_pick_card
from src.data.sec_holdings import get_all_institution_changes
from src.data.market_data import fetch_sector_performance
from src.data.gov_contracts import top_recipients
from src.analysis.watchlist import build_watchlist

inject_css()

settings = st.session_state.settings

# Brand header
st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
    <div>
        <div style="font-size:1.7rem; font-weight:800; color:#FAFAFA; letter-spacing:-0.02em;">
            Flow<span style="color:#00E676;">Signal</span>
            <span style="background:#1F2937; color:#9CA3AF; padding:2px 8px; border-radius:999px; font-size:0.65rem; margin-left:6px; vertical-align:middle;">BETA</span>
        </div>
        <div style="color:#9CA3AF; font-size:0.95rem;">Where smart money is flowing today.</div>
    </div>
    <div style="color:#6B7280; font-size:0.85rem; text-align:right;">
        {datetime.now().strftime('%A, %b %d')}<br>
        <span style="color:#00E676;">●</span> Live
    </div>
</div>
""", unsafe_allow_html=True)
st.divider()

# Quick controls
ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
with ctrl1:
    mode = st.selectbox(
        "Mode",
        ["🔹 Hidden Gems (small/mid cap)", "📊 All stocks"],
        index=0 if settings["hidden_gems_only"] else 1,
        label_visibility="collapsed",
    )
    settings["hidden_gems_only"] = "Hidden Gems" in mode
with ctrl2:
    lookback = st.selectbox(
        "Time window",
        [7, 14, 30, 60, 90],
        index=[7, 14, 30, 60, 90].index(settings.get("lookback_days", 30)),
        format_func=lambda x: f"📅 Last {x} days",
        label_visibility="collapsed",
    )
    settings["lookback_days"] = lookback
with ctrl3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=3600, show_spinner=False)
def _perf(days): return fetch_sector_performance(days_back=days)
@st.cache_data(ttl=21600, show_spinner=False)
def _recipients(days): return top_recipients(days_back=days, top_n=20)
@st.cache_data(ttl=86400, show_spinner=False)
def _holdings(): return get_all_institution_changes()


with st.spinner(""):
    holdings = _holdings()
    perf = _perf(lookback)
    recipients = _recipients(lookback)

home_changes = holdings[holdings["action"].isin(["NEW", "INCREASED"])] if not holdings.empty else holdings
watchlist = build_watchlist(home_changes, perf, recipients, hidden_gems_only=settings["hidden_gems_only"])
top_picks = [w for w in watchlist if w.buying_institutions and w.score >= settings["min_score"]][:5]

if not top_picks:
    st.warning("No picks meet your filters right now. Try widening the time window or lowering the minimum score in Settings.")
else:
    st.markdown('<div class="section-h">🔥 Today\'s Top Pick</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-s">Highest confluence of institutional buying + government contracts</div>', unsafe_allow_html=True)
    render_pick_card(top_picks[0], rank=1, is_hero=True, key_prefix="home")

    if len(top_picks) > 1:
        st.markdown('<div class="section-h">Also Worth Watching</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-s">Other strong converging signals today</div>', unsafe_allow_html=True)
        for i, entry in enumerate(top_picks[1:], start=2):
            render_pick_card(entry, rank=i, key_prefix=f"home_{i}")

with st.expander("💡 How does FlowSignal work?"):
    st.markdown("""
    **We watch 3 things every day:**

    🏛️ **Government Contracts** — Every federal contract is public data. We track who wins big ones in defense, tech, healthcare.

    🏦 **Institutional Holdings** — BlackRock, Vanguard, State Street manage ~$25 trillion combined. When all three buy the same small company, that's a signal.

    📈 **Sector Momentum** — Which industries are heating up.

    **When all three line up on the same stock**, we surface it. Small-cap signals weigh more because a new institutional position in a $500M company means far more than buying a tiny slice of Apple.
    """)

disclaimer()
