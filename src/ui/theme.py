"""Clean light theme — white, layered light greys, money-green accent."""
import streamlit as st

# Chart colors for plotly (CSS variables can't reach plotly figures)
ACCENT = "#00B25D"
ACCENT_FILL = "rgba(0, 178, 93, 0.08)"
DOWN = "#E5484D"
CHART_GRID = "#E9ECEF"


def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --bg: #FFFFFF;             /* page background */
    --surface: #F6F7F9;        /* sidebar, inputs, expanders, popovers */
    --surface-2: #ECEEF2;      /* hovers, feed icons, chips */
    --border: #E1E4E8;         /* visible borders */
    --hairline: #EEF0F3;       /* row dividers */
    --text: #17191C;           /* primary text */
    --text-2: #52585F;         /* secondary text */
    --muted: #878E96;          /* captions, labels */
    --accent: #00B25D;         /* money green — fills, buttons, brand */
    --accent-strong: #067647;  /* green as small TEXT (bright green fails contrast on white) */
    --accent-dim: #009C51;
    --down: #E5484D;           /* losses — fills */
    --down-strong: #B42318;    /* red as small text */
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

.stApp { background: var(--bg); }
#MainMenu, footer { visibility: hidden; }
header { background: transparent !important; box-shadow: none !important; }
.stDeployButton { display: none; }

/* Hide Streamlit Cloud's toolbar cluster (Share / star / edit / GitHub / Fork).
   The sidebar expand chevron lives outside this container, so it survives. */
[data-testid="stToolbar"] { display: none !important; }

/* Tighten default Streamlit padding */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 880px !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] > div { padding-top: 1.5rem; }

/* Sidebar collapse/expand toggle — always visible */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {
    visibility: visible !important;
    background: var(--surface-2) !important;
    border-radius: 0 8px 8px 0 !important;
    border: 1px solid var(--border) !important;
    border-left: none !important;
}
[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg { fill: var(--text-2) !important; }
[data-testid="collapsedControl"]:hover,
[data-testid="stSidebarCollapseButton"]:hover { background: var(--border) !important; }
[data-testid="collapsedControl"]:hover svg,
[data-testid="stSidebarCollapseButton"]:hover svg { fill: var(--text) !important; }

/* Top navigation section headers */
[data-testid="stNavSectionHeader"] {
    color: var(--muted) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}

/* Page brand */
.app-brand {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.02em;
    margin-bottom: 2px;
}
.app-brand-accent { color: var(--accent); }
.app-tagline {
    color: var(--text-2);
    font-size: 0.85rem;
    margin-bottom: 22px;
}

/* Section headers */
.feed-section {
    color: var(--text);
    font-size: 1.05rem;
    font-weight: 700;
    margin: 28px 0 4px 0;
    letter-spacing: -0.01em;
}
.feed-section-sub {
    color: var(--muted);
    font-size: 0.78rem;
    margin-bottom: 12px;
    font-weight: 500;
}

/* Feed rows */
.feed-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 4px;
    border-bottom: 1px solid var(--hairline);
    transition: background 0.15s;
}
.feed-row:hover { background: var(--surface); }
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
    background: linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%);
    display: flex; align-items: center; justify-content: center;
    color: var(--text); font-weight: 700; font-size: 0.75rem;
    flex-shrink: 0;
    border: 1px solid var(--border);
}
.feed-text { min-width: 0; flex: 1; }
.feed-ticker {
    color: var(--text);
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
}
.feed-company {
    color: var(--text-2);
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
    color: var(--text);
    font-size: 1rem;
    font-weight: 700;
}
.feed-amount-green { color: var(--accent-strong); }
.feed-meta {
    color: var(--muted);
    font-size: 0.75rem;
    margin-top: 2px;
}

/* Buttons */
.stButton > button {
    background: transparent;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 999px;
    font-weight: 600;
    padding: 7px 16px;
    font-size: 0.82rem;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: var(--surface);
    border-color: var(--accent);
    color: var(--accent-strong);
}
.stButton > button[kind="primary"] {
    background: var(--accent);
    color: #FFFFFF;
    border: none;
    font-weight: 700;
}
.stButton > button[kind="primary"]:hover {
    background: var(--accent-dim);
}

/* Inputs */
.stSelectbox > div > div, .stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}

/* Stat boxes */
.stat-box {
    background: transparent;
    padding: 12px 0;
    border-bottom: 1px solid var(--hairline);
}
.stat-label {
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.stat-value {
    color: var(--text);
    font-size: 1.4rem;
    font-weight: 700;
    margin-top: 2px;
    letter-spacing: -0.02em;
}
.stat-delta-up { color: var(--accent-strong); font-size: 0.85rem; font-weight: 600; }
.stat-delta-down { color: var(--down-strong); font-size: 0.85rem; font-weight: 600; }

/* Stock detail header */
.detail-ticker {
    font-size: 2.6rem;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.04em;
    line-height: 1;
}
.detail-name {
    color: var(--text-2);
    font-size: 1rem;
    margin-top: 4px;
}
.detail-price {
    font-size: 2.4rem;
    font-weight: 700;
    color: var(--text);
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
.pill-green { background: rgba(0, 178, 93, 0.12); color: var(--accent-strong); }
.pill-red { background: rgba(229, 72, 77, 0.10); color: var(--down-strong); }
.pill-gray { background: var(--surface-2); color: var(--text-2); }

/* Source chips */
.source-chip {
    display: inline-block;
    background: var(--surface-2);
    color: var(--text-2);
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
    color: var(--muted);
    font-size: 0.9rem;
}

/* Disclaimer */
.disclaimer-bottom {
    color: var(--muted);
    font-size: 0.7rem;
    text-align: center;
    margin-top: 32px;
    line-height: 1.5;
}

[data-testid="stMarkdownContainer"] hr { border-color: var(--hairline); margin: 12px 0; }

/* Expander & popover surfaces */
[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
}
[data-testid="stExpander"] summary { color: var(--text); font-weight: 500; }
[data-testid="stPopover"] > div {
    background: var(--surface);
    border: 1px solid var(--border);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--hairline); }
.stTabs [data-baseweb="tab"] { color: var(--text-2); }
.stTabs [aria-selected="true"] { color: var(--text) !important; }
</style>
""", unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    st.markdown(f'<div style="font-size:1.5rem; font-weight:800; color:var(--text); letter-spacing:-0.02em;">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div style="color:var(--text-2); font-size:0.85rem; margin-bottom:22px;">{subtitle}</div>', unsafe_allow_html=True)


def disclaimer():
    st.markdown("""
    <div class="disclaimer-bottom">
    Informational purposes only. Not financial advice.<br>
    Past signals do not guarantee future returns.
    </div>
    """, unsafe_allow_html=True)
