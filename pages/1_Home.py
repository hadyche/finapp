"""Home — the Signals feed: asymmetric events on small companies."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.ui.theme import inject_css, disclaimer
from src.data.gov_contracts import fetch_recent_awards, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index
from src.data.stock_detail import get_market_caps
from src.analysis.asymmetry import build_contract_signals, format_asymmetry_line

inject_css()

# ── Brand header ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
    <div>
        <div class="app-brand">Flow<span class="app-brand-accent">Signal</span></div>
        <div class="app-tagline">{datetime.now().strftime('%A, %B %-d').lower()}</div>
    </div>
    <div>
        <span style="color:#00C805; font-size:0.7rem;">●</span>
        <span style="color:#8A8A8A; font-size:0.75rem; margin-left:4px;">LIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="feed-section">Asymmetric Signals</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="feed-section-sub">Small companies that just landed federal money '
    'that is HUGE relative to their size. No S&amp;P 500 names — ever.</div>',
    unsafe_allow_html=True,
)

# ── Filters ───────────────────────────────────────────────────────────────────
settings = st.session_state.get("settings", {})
f1, f2, f3 = st.columns(3)
with f1:
    days = st.selectbox(
        "Period", [7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"Last {x} days",
        label_visibility="collapsed",
    )
with f2:
    min_ratio_pct = st.selectbox(
        "Min impact", [1, 2, 5, 10, 25],
        index=[1, 2, 5, 10, 25].index(int(settings.get("min_ratio_pct", 1))),
        format_func=lambda x: f"≥ {x}% of mkt cap",
        label_visibility="collapsed",
    )
with f3:
    max_cap_b = st.selectbox(
        "Max size", [0.5, 1.0, 2.0, 5.0],
        index=[0.5, 1.0, 2.0, 5.0].index(float(settings.get("max_cap_b", 5.0))),
        format_func=lambda x: f"Cap < ${x:g}B",
        label_visibility="collapsed",
    )


# ── Data pipeline (each stage cached separately) ──────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    sec_map = load_sec_company_map()
    return build_name_index(sec_map), len(sec_map)

@st.cache_data(ttl=21600, show_spinner=False)
def _matched_awards(days_back: int):
    awards = fetch_recent_awards(days_back=days_back, limit=500, min_amount=5_000_000)
    if awards.empty:
        return awards
    index, _ = _name_index()
    return match_awards_to_tickers(awards, index)

@st.cache_data(ttl=21600, show_spinner=False)
def _caps(tickers: tuple):
    return get_market_caps(list(tickers))


def go_to_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    st.switch_page("pages/3_Stock_Detail.py")


def fmt_date(date_str: str) -> str:
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        delta = (datetime.now() - d).days
        if delta <= 0: return "today"
        if delta == 1: return "yesterday"
        if delta < 7: return f"{delta}d ago"
        if delta < 30: return f"{delta//7}w ago"
        return f"{delta//30}mo ago"
    except Exception:
        return ""


def fmt_cap(cap: float) -> str:
    if cap >= 1e9:
        return f"${cap/1e9:.1f}B company"
    return f"${cap/1e6:.0f}M company"


with st.spinner("Scanning federal awards…"):
    matched = _matched_awards(days)

if matched.empty:
    st.error(
        "USAspending.gov didn't return data. This is a live-data app with no fake "
        "fallbacks — try refreshing in a minute.",
        icon="🏛️",
    )
else:
    candidates = tuple(sorted(matched["ticker"].dropna().unique()))
    with st.spinner("Checking company sizes…"):
        caps = _caps(candidates)

    signals = build_contract_signals(
        matched, caps,
        max_cap=max_cap_b * 1e9,
        min_ratio=min_ratio_pct / 100,
    )

    if signals.empty:
        st.markdown(
            '<div class="empty-state">No asymmetric events found in the last '
            f'{days} days at these thresholds.<br>Try a longer period or lower '
            'the impact filter — big mismatches are rare by design.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{len(signals)} signals · scanned {len(matched)} awards · updated {datetime.now().strftime('%H:%M')}")
        for i, row in signals.iterrows():
            ticker = row["ticker"]
            ratio_pct = row["impact_ratio"] * 100
            line = format_asymmetry_line(row)
            meta = f"{fmt_cap(row['market_cap'])} · {str(row['agency'])[:32]}"
            if row["date"]:
                meta += f" · {fmt_date(row['date'])}"

            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f"""
                <div class="feed-row">
                    <div class="feed-left">
                        <div class="feed-icon">{ticker[:4]}</div>
                        <div class="feed-text">
                            <div class="feed-ticker">{ticker}</div>
                            <div class="feed-company">{str(row['matched_name'])[:48]}</div>
                            <div class="feed-meta" style="margin-top:3px;">{meta}</div>
                        </div>
                    </div>
                    <div class="feed-right">
                        <div class="feed-amount feed-amount-green">+{ratio_pct:.0f}%</div>
                        <div class="feed-meta">of mkt cap</div>
                    </div>
                </div>
                <div style="color:#D1D5DB; font-size:0.85rem; margin:-6px 0 10px 56px;">{line}</div>
                """, unsafe_allow_html=True)
            with col2:
                st.button("→", key=f"sig_{i}_{ticker}", on_click=go_to_detail, args=(ticker,))

        # Transparency: what got scanned but not matched to a public company
        unmatched = matched[matched["ticker"].isna()]["recipient"].dropna().unique()
        if len(unmatched):
            with st.expander(f"🔍 {len(unmatched)} recipients had no public-company match (private companies, subsidiaries, universities)"):
                st.caption(" · ".join(sorted(set(str(u)[:40] for u in unmatched))[:60]))


with st.expander("💡 How FlowSignal finds hidden gems"):
    st.markdown("""
**The idea: size mismatch = opportunity.**

An $84M contract means nothing to Lockheed Martin. But to a $380M company,
it's 22% of everything the company is worth — real revenue that can move the stock.

**How the feed works:**
1. We scan every federal contract award on USAspending.gov (updated daily)
2. Each recipient is matched against the SEC registry of all ~10,000 public companies
3. We look up the company's market cap and compute **award ÷ company size**
4. Only companies under your size ceiling with a material award make the feed

**Why you won't see famous stocks:** the size ceiling ($5B max) is below the
smallest company in the S&P 500. Everything here is under the radar by construction.
    """)

disclaimer()
