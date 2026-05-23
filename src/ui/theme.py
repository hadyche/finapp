"""Robinhood-inspired premium theme — true black, minimal, mobile-app feel."""
import streamlit as st


def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

.stApp { background: #000000; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Tighten default Streamlit padding */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 880px !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0A0A0A;
    border-right: 1px solid #1A1A1A;
}
[data-testid="stSidebar"] > div { padding-top: 1.5rem; }

/* Top navigation bar styling */
[data-testid="stNavSectionHeader"] {
    color: #6B6B6B !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}

/* Page brand */
.app-brand {
    font-size: 1.5rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.02em;
    margin-bottom: 2px;
}
.app-brand-accent { color: #00C805; }
.app-tagline {
    color: #8A8A8A;
    font-size: 0.85rem;
    margin-bottom: 22px;
}

/* Section headers — minimal */
.feed-section {
    color: #FFFFFF;
    font-size: 1.05rem;
    font-weight: 700;
    margin: 28px 0 4px 0;
    letter-spacing: -0.01em;
}
.feed-section-sub {
    color: #6B6B6B;
    font-size: 0.78rem;
    margin-bottom: 12px;
    font-weight: 500;
}

/* Feed rows — Robinhood-style list */
.feed-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 4px;
    border-bottom: 1px solid #141414;
    transition: background 0.15s;
}
.feed-row:hover { background: #0D0D0D; }
.feed-row:last-child { border-bottom: none; }

.feed-left {
    display: flex;
    align-items: center;
    gap: 14px;
    flex: 1;
    min-width: 0;
}
.feed-icon {
    width: 42px; height: 42px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1A1A1A 0%, #0A0A0A 100%);
    display: flex; align-items: center; justify-content: center;
    color: #FFF; font-weight: 700; font-size: 0.75rem;
    flex-shrink: 0;
    border: 1px solid #1F1F1F;
}
.feed-text { min-width: 0; flex: 1; }
.feed-ticker {
    color: #FFFFFF;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
}
.feed-company {
    color: #8A8A8A;
    font-size: 0.82rem;
    margin-top: 1px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.feed-right {
    text-align: right;
    margin-left: 12px;
}
.feed-amount {
    color: #FFFFFF;
    font-size: 1rem;
    font-weight: 700;
}
.feed-amount-green { color: #00C805; }
.feed-meta {
    color: #6B6B6B;
    font-size: 0.75rem;
    margin-top: 2px;
}

/* Tabs / toggle pills (top of feed) */
div[role="radiogroup"] > label {
    background: transparent !important;
    border: none !important;
    color: #6B6B6B !important;
    font-weight: 600 !important;
    padding: 8px 0 !important;
    margin-right: 24px !important;
    font-size: 1rem !important;
    transition: color 0.2s;
}
div[role="radiogroup"] > label:hover { color: #FFF !important; }
div[role="radiogroup"] > label > div:first-child { display: none !important; }
div[role="radiogroup"] > label[data-baseweb="radio"] > div:nth-child(2) {
    border-bottom: 2px solid transparent;
    padding-bottom: 6px;
}
/* Active radio - Streamlit applies a different attribute */
div[role="radiogroup"] > label:has(input:checked) {
    color: #FFFFFF !important;
}
div[role="radiogroup"] > label:has(input:checked) > div:nth-child(2) {
    border-bottom: 2px solid #00C805 !important;
}

/* Buttons */
.stButton > button {
    background: transparent;
    color: #FFFFFF;
    border: 1px solid #2A2A2A;
    border-radius: 999px;
    font-weight: 600;
    padding: 7px 16px;
    font-size: 0.82rem;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #1A1A1A;
    border-color: #00C805;
    color: #00C805;
}
.stButton > button[kind="primary"] {
    background: #00C805;
    color: #000000;
    border: none;
    font-weight: 700;
}
.stButton > button[kind="primary"]:hover {
    background: #00B005;
}

/* Inputs */
.stSelectbox > div > div, .stTextInput > div > div > input {
    background: #0A0A0A !important;
    border: 1px solid #1F1F1F !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
}

/* Stat boxes — for stock detail */
.stat-box {
    background: transparent;
    padding: 12px 0;
    border-bottom: 1px solid #141414;
}
.stat-label {
    color: #6B6B6B;
    font-size: 0.72rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.stat-value {
    color: #FFFFFF;
    font-size: 1.4rem;
    font-weight: 700;
    margin-top: 2px;
    letter-spacing: -0.02em;
}
.stat-delta-up { color: #00C805; font-size: 0.85rem; font-weight: 600; }
.stat-delta-down { color: #FF5000; font-size: 0.85rem; font-weight: 600; }

/* Stock detail header */
.detail-ticker {
    font-size: 2.6rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.04em;
    line-height: 1;
}
.detail-name {
    color: #8A8A8A;
    font-size: 1rem;
    margin-top: 4px;
}
.detail-price {
    font-size: 2.4rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.03em;
}

/* Pills */
.pill {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.72rem;
}
.pill-green { background: rgba(0,200,5,0.15); color: #00C805; }
.pill-red { background: rgba(255,80,0,0.15); color: #FF5000; }
.pill-gray { background: #1A1A1A; color: #8A8A8A; }

/* Source chips */
.source-chip {
    display: inline-block;
    background: #1A1A1A;
    color: #8A8A8A;
    padding: 5px 11px;
    border-radius: 8px;
    font-size: 0.74rem;
    margin: 3px 6px 3px 0;
    font-weight: 500;
}

/* Empty states */
.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: #6B6B6B;
    font-size: 0.9rem;
}

/* Disclaimer — small, unobtrusive */
.disclaimer-bottom {
    color: #4A4A4A;
    font-size: 0.7rem;
    text-align: center;
    margin-top: 32px;
    line-height: 1.5;
}

/* Hide some streamlit extras */
[data-testid="stMarkdownContainer"] hr { border-color: #141414; margin: 12px 0; }

/* Expander */
[data-testid="stExpander"] {
    background: transparent;
    border: 1px solid #1A1A1A;
    border-radius: 10px;
}
[data-testid="stExpander"] summary { color: #FFFFFF; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    st.markdown(f'<div style="font-size:1.5rem; font-weight:800; color:#FFF; letter-spacing:-0.02em;">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div style="color:#8A8A8A; font-size:0.85rem; margin-bottom:22px;">{subtitle}</div>', unsafe_allow_html=True)


def disclaimer():
    st.markdown("""
    <div class="disclaimer-bottom">
    Informational purposes only. Not financial advice.<br>
    Past signals do not guarantee future returns.
    </div>
    """, unsafe_allow_html=True)
