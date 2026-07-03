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

home         = st.Page("pages/1_Home.py",         title="Signals",      icon="⚡", default=True)
stock_detail = st.Page("pages/3_Stock_Detail.py", title="Stock Detail", icon="📊")
settings_pg  = st.Page("pages/8_Settings.py",     title="Settings",     icon="⚙️")

nav = st.navigation([home, stock_detail, settings_pg])
nav.run()
