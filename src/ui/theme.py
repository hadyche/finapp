"""Shared theme CSS and helpers for all pages."""
import streamlit as st


def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif !important; }
.stApp { background: #0A0E16; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0F1520;
    border-right: 1px solid #1F2937;
}
[data-testid="stSidebar"] .stMarkdown { color: #E5E7EB; }

/* Page header */
.page-title {
    font-size: 1.8rem;
    font-weight: 800;
    color: #FAFAFA;
    letter-spacing: -0.02em;
    margin: 0 0 4px 0;
}
.page-subtitle {
    color: #9CA3AF;
    font-size: 0.95rem;
    margin-bottom: 24px;
}

/* Cards */
.card {
    background: linear-gradient(135deg, #131A26 0%, #0F1520 100%);
    border: 1px solid #1F2937;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 14px;
    transition: all 0.2s;
}
.card:hover { border-color: #00E676; box-shadow: 0 4px 24px rgba(0,230,118,0.08); }

.card-hero {
    background: linear-gradient(135deg, #0F1F19 0%, #0A1610 100%);
    border: 1px solid #00E676;
    box-shadow: 0 8px 32px rgba(0,230,118,0.1);
}

.ticker-big { font-size: 2.4rem; font-weight: 800; color: #FAFAFA; letter-spacing: -0.04em; line-height: 1; }
.ticker-hero {
    font-size: 3rem; font-weight: 900;
    background: linear-gradient(135deg, #00E676 0%, #4FC3F7 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.company-name { font-size: 1rem; color: #E5E7EB; margin-top: 4px; font-weight: 500; }
.meta-text { color: #6B7280; font-size: 0.82rem; margin-top: 4px; }

/* Pills & badges */
.pill {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.02em;
}
.pill-strong { background: rgba(0,230,118,0.15); color: #00E676; }
.pill-positive { background: rgba(100,221,23,0.12); color: #64DD17; }
.pill-watch { background: rgba(255,214,0,0.12); color: #FFD600; }

.badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    margin-right: 4px;
}
.badge-small { background: rgba(0,230,118,0.15); color: #00E676; }
.badge-mid { background: rgba(79,195,247,0.15); color: #4FC3F7; }
.badge-large { background: rgba(156,163,175,0.15); color: #9CA3AF; }

.source-chip {
    display: inline-block;
    background: #1F2937;
    color: #9CA3AF;
    padding: 5px 11px;
    border-radius: 8px;
    font-size: 0.76rem;
    margin: 3px 6px 3px 0;
    font-weight: 500;
}
.source-chip .check { color: #00E676; margin-right: 4px; }

/* Section dividers */
.section-h {
    font-size: 1.2rem;
    font-weight: 700;
    color: #FAFAFA;
    margin: 24px 0 4px 0;
    letter-spacing: -0.02em;
}
.section-s { color: #6B7280; font-size: 0.85rem; margin-bottom: 14px; }

/* Stat boxes */
.stat-box {
    background: #131A26;
    border: 1px solid #1F2937;
    border-radius: 12px;
    padding: 16px 20px;
}
.stat-label { color: #6B7280; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }
.stat-value { color: #FAFAFA; font-size: 1.6rem; font-weight: 700; margin-top: 4px; }
.stat-delta-up { color: #00E676; font-size: 0.85rem; font-weight: 600; }
.stat-delta-down { color: #FF5252; font-size: 0.85rem; font-weight: 600; }

/* Buttons */
.stButton > button {
    background: #00E676; color: #0A0E16; border: none;
    border-radius: 10px; font-weight: 600; padding: 9px 18px;
    transition: all 0.2s;
}
.stButton > button:hover { background: #00C853; transform: translateY(-1px); }
.stButton > button[kind="secondary"] {
    background: #1F2937; color: #E5E7EB;
}

/* Disclaimer */
.disclaimer-bottom {
    background: rgba(255,152,0,0.05);
    border: 1px solid rgba(255,152,0,0.18);
    border-radius: 10px;
    padding: 12px 16px;
    margin-top: 28px;
    color: #FCD34D;
    font-size: 0.78rem;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def disclaimer():
    st.markdown("""
    <div class="disclaimer-bottom">
    <strong>⚠️ Informational only — NOT financial advice.</strong>
    Past signals do not guarantee future returns. Always do your own research
    and consult a licensed financial advisor before investing.
    </div>
    """, unsafe_allow_html=True)
