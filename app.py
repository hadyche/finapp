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
        "min_score": 25,
        "hidden_gems_only": True,
        "sectors_filter": [],
    }
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None

# Navigation
home          = st.Page("pages/1_Home.py",          title="Today's Picks",   icon="🎯", default=True)
favorites     = st.Page("pages/2_Favorites.py",     title="Favorites",       icon="⭐")
stock_detail  = st.Page("pages/3_Stock_Detail.py",  title="Stock Detail",    icon="📊")
discover      = st.Page("pages/4_Discover.py",      title="Discover",        icon="🔍")
gov           = st.Page("pages/5_Gov_Contracts.py", title="Gov Contracts",   icon="🏛️")
big_money     = st.Page("pages/6_Big_Money.py",     title="Big Money",       icon="🏦")
macro         = st.Page("pages/7_Macro.py",         title="Macro",           icon="📉")
settings_page = st.Page("pages/8_Settings.py",      title="Settings",        icon="⚙️")

nav = st.navigation({
    "Picks":     [home, favorites, stock_detail, discover],
    "Insights":  [gov, big_money, macro],
    "Account":   [settings_page],
})
nav.run()
