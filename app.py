"""
FlowSignal — main entry point with multi-page navigation.
"""
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="FlowSignal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state defaults
if "settings" not in st.session_state:
    st.session_state.settings = {
        "lookback_days": 30,
        "min_ratio_pct": 1,
        "max_cap_b": 5.0,
    }
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None

home         = st.Page("pages/1_Home.py",         title="Today's Picks",  icon="💰", default=True)
smart_money  = st.Page("pages/5_Smart_Money.py",  title="Smart Money",    icon="🎩")
stock_detail = st.Page("pages/3_Stock_Detail.py", title="Stock Details",  icon="📊")
track_record = st.Page("pages/4_Track_Record.py", title="Report Card",    icon="📜")
settings_pg  = st.Page("pages/8_Settings.py",     title="Settings",       icon="⚙️")

nav = st.navigation([home, smart_money, stock_detail, track_record, settings_pg])
nav.run()
