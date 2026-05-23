"""Macro indicators."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header, disclaimer
from src.data.economic_indicators import fetch_all_indicators_latest, yield_curve_signal
from src.ui.charts import indicators_gauge_row

inject_css()
page_header("📉 Macro", "Big-picture economic indicators that drive markets")

@st.cache_data(ttl=43200)
def _ind(): return fetch_all_indicators_latest()

ind = _ind()
yc = yield_curve_signal()

c1, c2 = st.columns([3, 1])
with c1:
    if not ind.empty:
        st.plotly_chart(indicators_gauge_row(ind), use_container_width=True)
        st.dataframe(ind, hide_index=True, use_container_width=True)
with c2:
    st.markdown('<div class="section-h">Yield Curve</div>', unsafe_allow_html=True)
    if "INVERTED" in yc:
        st.error(yc)
    elif "FLAT" in yc:
        st.warning(yc)
    else:
        st.success(yc)
    st.divider()
    st.markdown("""
    **How to read:**
    - **GDP > 2%** = healthy
    - **CPI rising fast** = rate hike risk
    - **Unemployment < 4%** = tight labor
    - **Inverted yield curve** = recession risk in 12-18mo
    """)

disclaimer()
