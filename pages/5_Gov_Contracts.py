"""Government Contracts page."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ui.theme import inject_css, page_header, disclaimer
from src.data.gov_contracts import sector_spending_summary, top_recipients
from src.ui.charts import contract_treemap

inject_css()
page_header("🏛️ Government Contracts", "Where federal money is flowing — sectors and top recipients")

lookback = st.selectbox(
    "Time window",
    [7, 14, 30, 60, 90, 180, 365],
    index=2,
    format_func=lambda x: f"Last {x} days",
)

@st.cache_data(ttl=21600)
def _data(days):
    return sector_spending_summary(days_back=days), top_recipients(days_back=days, top_n=20)

contracts, recipients = _data(lookback)

if contracts.empty:
    st.warning("Contract data unavailable.")
    st.stop()

# Top stats
total = contracts["total_amount"].sum()
count = int(contracts["contract_count"].sum()) if "contract_count" in contracts.columns else 0

m1, m2, m3 = st.columns(3)
m1.markdown(f"""<div class="stat-box">
    <div class="stat-label">Total awarded</div>
    <div class="stat-value">${total/1e9:.1f}B</div>
</div>""", unsafe_allow_html=True)
m2.markdown(f"""<div class="stat-box">
    <div class="stat-label">Contracts</div>
    <div class="stat-value">{count:,}</div>
</div>""", unsafe_allow_html=True)
m3.markdown(f"""<div class="stat-box">
    <div class="stat-label">Sectors</div>
    <div class="stat-value">{len(contracts)}</div>
</div>""", unsafe_allow_html=True)

st.divider()
st.markdown('<div class="section-h">By sector</div>', unsafe_allow_html=True)
st.plotly_chart(contract_treemap(contracts), use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown('<div class="section-h">Sector breakdown</div>', unsafe_allow_html=True)
    d = contracts.copy()
    d["total_amount"] = d["total_amount"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(d, hide_index=True, use_container_width=True)
with c2:
    st.markdown('<div class="section-h">Top recipients</div>', unsafe_allow_html=True)
    if not recipients.empty:
        r = recipients.copy()
        r["total_amount"] = r["total_amount"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(r, hide_index=True, use_container_width=True)

disclaimer()
