"""Big Money — institutional 13F holdings deep dive."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.express as px
from src.ui.theme import inject_css, page_header, disclaimer
from src.data.sec_holdings import get_position_changes, INSTITUTIONS

inject_css()
page_header("🏦 Big Money", "What BlackRock, Vanguard & State Street are doing this quarter")

@st.cache_data(ttl=86400)
def _inst(name): return get_position_changes(name)

tabs = st.tabs([f"💼 {n}" for n in INSTITUTIONS.keys()])

for tab, name in zip(tabs, INSTITUTIONS.keys()):
    with tab:
        ch = _inst(name)
        if ch.empty:
            st.warning(f"No data for {name}")
            continue

        new_count = len(ch[ch["action"] == "NEW"])
        inc_count = len(ch[ch["action"] == "INCREASED"])
        held_count = len(ch[ch["action"] == "HELD"])
        sold_count = len(ch[ch["action"].isin(["DECREASED", "SOLD"])])
        total_val = ch["value_current"].sum() / 1e9

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f"""<div class="stat-box"><div class="stat-label">Total Held</div><div class="stat-value">${total_val:.1f}B</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="stat-box"><div class="stat-label">New</div><div class="stat-value">{new_count}</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="stat-box"><div class="stat-label">Increased</div><div class="stat-value">{inc_count}</div></div>""", unsafe_allow_html=True)
        c4.markdown(f"""<div class="stat-box"><div class="stat-label">Held</div><div class="stat-value">{held_count}</div></div>""", unsafe_allow_html=True)
        c5.markdown(f"""<div class="stat-box"><div class="stat-label">Sold/Trimmed</div><div class="stat-value">{sold_count}</div></div>""", unsafe_allow_html=True)

        st.divider()

        movers = ch[ch["action"].isin(["NEW", "INCREASED"])].head(15)
        if not movers.empty:
            fig = px.bar(
                movers, x="ticker", y="value_current", color="action",
                title=f"Top new & increased positions",
                color_discrete_map={"NEW": "#00E676", "INCREASED": "#64DD17"},
                template="plotly_dark",
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=380, margin=dict(t=40, b=40, l=20, r=20),
                yaxis_title="Value held ($)", xaxis_title=None,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-h">All positions</div>', unsafe_allow_html=True)
        action_filter = st.multiselect(
            "Filter",
            ["NEW", "INCREASED", "HELD", "DECREASED", "SOLD"],
            default=["NEW", "INCREASED"],
            key=f"filter_{name}",
        )
        display = ch[ch["action"].isin(action_filter)] if action_filter else ch
        st.dataframe(display, hide_index=True, use_container_width=True)

disclaimer()
