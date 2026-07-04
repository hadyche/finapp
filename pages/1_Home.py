"""Home — the Signals feed: asymmetric events on small companies."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.ui.theme import inject_css, disclaimer
from src.data.gov_contracts import fetch_recent_awards, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index, ticker_to_cik
from src.data.stock_detail import get_market_stats, get_price_changes_since
from src.data.insider_trades import insider_buys_for_cik
from src.analysis.asymmetry import build_contract_signals, format_asymmetry_line

inject_css()

THIN_VOLUME_USD = 1_000_000  # avg daily $ volume below this = hard to trade


# ── Data pipeline (each stage cached separately) ──────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def _sec_map():
    return load_sec_company_map()

@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    return build_name_index(_sec_map())

@st.cache_data(ttl=21600, show_spinner=False)
def _matched_awards(days_back: int, registry_ok: bool):
    # registry_ok is part of the cache key: a failed registry fetch must
    # not poison the awards cache with all-unmatched rows for 6 hours.
    awards = fetch_recent_awards(days_back=days_back, limit=500, min_amount=5_000_000)
    scanned_at = datetime.now().isoformat()
    if awards.empty:
        return awards, scanned_at
    return match_awards_to_tickers(awards, _name_index()), scanned_at

@st.cache_data(ttl=21600, show_spinner=False)
def _stats(tickers: tuple):
    return get_market_stats(list(tickers))

@st.cache_data(ttl=21600, show_spinner=False)
def _price_changes(pairs: tuple):
    return get_price_changes_since(list(pairs))

@st.cache_data(ttl=86400, show_spinner=False)
def _insiders(ticker: str):
    cik = ticker_to_cik(ticker, _sec_map())
    if cik is None:
        return None
    return insider_buys_for_cik(cik, days_back=90)


def go_to_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    st.switch_page("pages/3_Stock_Detail.py")


def fmt_ago(iso: str) -> str:
    try:
        mins = int((datetime.now() - datetime.fromisoformat(iso)).total_seconds() // 60)
        if mins < 2: return "just now"
        if mins < 60: return f"{mins}m ago"
        return f"{mins//60}h ago"
    except Exception:
        return ""


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


# ── Header (freshness shown in the feed caption — no fake LIVE dot) ──────────
st.markdown(f"""
<div style="margin-bottom:6px;">
    <div class="app-brand">Flow<span class="app-brand-accent">Signal</span></div>
    <div class="app-tagline">{datetime.now().strftime('%A, %B %-d').lower()}</div>
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

registry_ok = bool(_name_index().get("exact"))
if not registry_ok:
    # Clear so the next rerun retries the download instead of caching failure
    _sec_map.clear()
    _name_index.clear()
    st.warning("SEC company registry is unreachable — company matching is paused. Refresh in a minute.", icon="🗂️")

with st.spinner("Scanning federal awards…"):
    matched, scanned_at = _matched_awards(days, registry_ok)

if matched is None or matched.empty:
    st.error(
        "USAspending.gov didn't return data. This is a live-data app with no fake "
        "fallbacks — try refreshing in a minute.",
        icon="🏛️",
    )
else:
    candidates = tuple(sorted(matched["ticker"].dropna().unique()))
    with st.spinner("Checking company sizes…"):
        stats = _stats(candidates)
    caps = {t: s.get("cap") for t, s in stats.items()}

    signals = build_contract_signals(
        matched, caps,
        max_cap=max_cap_b * 1e9,
        min_ratio=min_ratio_pct / 100,
    )

    if signals.empty:
        st.caption(f"scanned {len(matched)} awards · {fmt_ago(scanned_at)}")
        st.markdown(
            '<div class="empty-state">No asymmetric events found in the last '
            f'{days} days at these thresholds.<br>Try a longer period or lower '
            'the impact filter — big mismatches are rare by design.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Checking price reaction & insider buying…"):
            pairs = tuple((r["ticker"], str(r["date"])[:10]) for _, r in signals.iterrows() if r["date"])
            changes = _price_changes(pairs)
            insider_map = {t: _insiders(t) for t in signals["ticker"].head(12)}

        st.caption(
            f"{len(signals)} signals · scanned {len(matched)} awards · {fmt_ago(scanned_at)} · "
            f"prices refresh every 6h, insider data every 24h"
        )

        for i, row in signals.iterrows():
            ticker = row["ticker"]
            ratio_pct = row["impact_ratio"] * 100
            line = format_asymmetry_line(row)
            meta = f"{fmt_cap(row['market_cap'])} · {str(row['agency'])[:32]}"
            if row["date"]:
                meta += f" · signed {fmt_date(row['date'])}"

            # Context tags: are you late? can you trade it? are insiders in?
            tags = []
            chg = changes.get(ticker)
            if chg is not None:
                if chg >= 25:
                    tags.append(f'<span class="pill pill-red">already moved +{chg:.0f}% since award</span>')
                elif chg >= 0:
                    tags.append(f'<span class="pill pill-green">+{chg:.1f}% since award</span>')
                else:
                    tags.append(f'<span class="pill pill-gray">{chg:.1f}% since award</span>')
            adv = stats.get(ticker, {}).get("adv_usd")
            if adv is not None and adv < THIN_VOLUME_USD:
                tags.append('<span class="pill pill-red">⚠ thin volume</span>')
            ins = insider_map.get(ticker)
            if ins and ins["n_insiders"] >= 1:
                who = f"{ins['n_insiders']} insider{'s' if ins['n_insiders'] > 1 else ''}"
                tags.append(f'<span class="pill pill-green">🔥 {who} bought ${ins["total_usd"]/1e3:,.0f}K</span>')
            tags_html = f'<div style="margin:2px 0 12px 56px;">{" ".join(tags)}</div>' if tags else ""

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
                <div style="color:#D1D5DB; font-size:0.85rem; margin:-6px 0 6px 56px;">{line}</div>
                {tags_html}
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
1. We scan federal contracts **newly signed** in your time window on USAspending.gov — modifications to old contracts don't count
2. Each recipient is matched against the SEC registry of all ~10,000 public companies
3. We look up the company's market cap and compute **award ÷ company size**
4. Only companies under your size ceiling with a material award make the feed

**Reading the tags:**
- **+x% since award** — how much the stock already moved after the contract was signed. Small = the market may not have noticed yet. Big red = you're probably late.
- **⚠ thin volume** — trades under $1M/day on average; hard to buy or sell without moving the price.
- **🔥 insiders bought** — company officers/directors purchased shares on the open market in the last 90 days (SEC Form 4). Insiders buying after a big award is the strongest combination this app can show you.

**Why you won't see famous stocks:** the size ceiling ($5B max) is below the
smallest company in the S&P 500. Everything here is under the radar by construction.
    """)

disclaimer()
