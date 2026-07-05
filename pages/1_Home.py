"""Home — small companies that just won big government money."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.ui.theme import inject_css, disclaimer
from src.ui.components import info_popover, glossary_popover
from src.data.gov_contracts import fetch_recent_awards, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index, ticker_to_cik
from src.data.stock_detail import get_market_stats, get_price_changes_since
from src.data.insider_trades import insider_buys_for_cik
from src.analysis.asymmetry import build_contract_signals

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
        if delta < 7: return f"{delta} days ago"
        if delta < 30: return f"{delta//7} weeks ago"
        return f"{delta//30} months ago"
    except Exception:
        return ""


def fmt_cap(cap: float) -> str:
    if cap >= 1e9:
        return f"worth ${cap/1e9:.1f} billion"
    return f"worth ${cap/1e6:.0f} million"


def fmt_money(v: float) -> str:
    if v >= 1e9:
        return f"${v/1e9:.1f} billion"
    if v >= 1e6:
        return f"${v/1e6:.0f} million"
    return f"${v/1e3:.0f}K"


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-bottom:6px;">
    <div class="app-brand">Flow<span class="app-brand-accent">Signal</span></div>
    <div class="app-tagline">{datetime.now().strftime('%A, %B %-d').lower()}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="feed-section">💰 Small Companies That Just Won Big</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="feed-section-sub">The U.S. government just gave these small companies '
    'a LOT of money. That\'s real income — and the stock price may not have caught up yet.</div>',
    unsafe_allow_html=True,
)

hcol1, hcol2 = st.columns([1, 1])
with hcol1:
    info_popover("How does this work?", """
**In 3 steps:**

1. Every time the U.S. government pays a company to do work, it's posted publicly online. We read all of it, every day.
2. We skip the giant companies — a big deal means nothing to them.
3. We show you **small companies** where the deal is **huge compared to the company's size**.

**Example:** imagine a lemonade stand worth $100 suddenly gets a $25 order.
That one order = 25% of what the whole stand is worth. That's the kind of
mismatch we look for — just with real companies and millions of dollars.
""")
with hcol2:
    glossary_popover()

# ── Filters (plain-language labels) ───────────────────────────────────────────
settings = st.session_state.get("settings", {})
f1, f2, f3 = st.columns(3)
with f1:
    days = st.selectbox(
        "How far back to look",
        [7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"Last {x} days",
        help="We only show deals signed in this time window.",
    )
with f2:
    min_ratio_pct = st.selectbox(
        "How big the deal must be",
        [1, 2, 5, 10, 25],
        index=[1, 2, 5, 10, 25].index(int(settings.get("min_ratio_pct", 1))),
        format_func=lambda x: f"At least {x}% of company's value",
        help="A deal worth 25% of the whole company is a much bigger event than one worth 1%.",
    )
with f3:
    max_cap_b = st.selectbox(
        "Biggest company to show",
        [0.5, 1.0, 2.0, 5.0],
        index=[0.5, 1.0, 2.0, 5.0].index(float(settings.get("max_cap_b", 5.0))),
        format_func=lambda x: f"Under ${x:g} billion",
        help="Smaller companies move more on big news. Even the $5B setting is below every famous stock you've heard of.",
    )

registry_ok = bool(_name_index().get("exact"))
if not registry_ok:
    # Clear so the next rerun retries the download instead of caching failure
    _sec_map.clear()
    _name_index.clear()
    st.warning("We can't reach the company name list right now. Refresh in a minute.", icon="🗂️")

with st.spinner("Reading government deals…"):
    matched, scanned_at = _matched_awards(days, registry_ok)

if matched is None or matched.empty:
    st.error(
        "The government website isn't answering right now. We never show fake "
        "numbers — please try again in a minute.",
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
        st.caption(f"checked {len(matched)} deals · {fmt_ago(scanned_at)}")
        st.markdown(
            '<div class="empty-state">Nothing big enough in the last '
            f'{days} days with these filters.<br>Try looking further back or '
            'lowering "how big the deal must be" — truly huge wins are rare, '
            'and that\'s what makes them special.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Checking prices and what the bosses are doing…"):
            pairs = tuple((r["ticker"], str(r["date"])[:10]) for _, r in signals.iterrows() if r["date"])
            changes = _price_changes(pairs)
            insider_map = {t: _insiders(t) for t in signals["ticker"].head(12)}

        st.caption(
            f"{len(signals)} stocks found · checked {len(matched)} government deals · updated {fmt_ago(scanned_at)}"
        )

        for i, row in signals.iterrows():
            ticker = row["ticker"]
            ratio_pct = row["impact_ratio"] * 100
            n = int(row.get("n_awards", 1))
            deal_word = "deals worth" if n > 1 else "a deal worth"
            line = (f"Won {deal_word} {fmt_money(row['total_awarded'])} — "
                    f"that's {ratio_pct:.0f}% of what the whole company is worth")
            meta = f"{fmt_cap(row['market_cap'])} · {str(row['agency'])[:32]}"
            if row["date"]:
                meta += f" · signed {fmt_date(row['date'])}"

            # Simple answers to: am I late? can I trade it? are bosses buying?
            tags = []
            chg = changes.get(ticker)
            if chg is not None:
                if chg >= 25:
                    tags.append(f'<span class="pill pill-red">already jumped +{chg:.0f}% — you may be late</span>')
                elif chg >= 0:
                    tags.append(f'<span class="pill pill-green">up {chg:.1f}% since the deal</span>')
                else:
                    tags.append(f'<span class="pill pill-gray">down {abs(chg):.1f}% since the deal</span>')
            adv = stats.get(ticker, {}).get("adv_usd")
            if adv is not None and adv < THIN_VOLUME_USD:
                tags.append('<span class="pill pill-red">⚠ hard to trade</span>')
            ins = insider_map.get(ticker)
            if ins and ins["n_insiders"] >= 1:
                who = f"{ins['n_insiders']} boss{'es' if ins['n_insiders'] > 1 else ''}"
                tags.append(f'<span class="pill pill-green">🔥 {who} bought their own stock</span>')
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
                        <div class="feed-meta">of company value</div>
                    </div>
                </div>
                <div style="color:#D1D5DB; font-size:0.85rem; margin:-6px 0 6px 56px;">{line}</div>
                {tags_html}
                """, unsafe_allow_html=True)
            with col2:
                # st.switch_page is a silent no-op inside on_click callbacks,
                # so the click must be handled in the main script flow
                if st.button("→", key=f"sig_{i}_{ticker}", help="See everything about this stock"):
                    go_to_detail(ticker)

        # Transparency: what got scanned but not matched to a public company
        unmatched = matched[matched["ticker"].isna()]["recipient"].dropna().unique()
        if len(unmatched):
            with st.expander(f"🔍 {len(unmatched)} winners we couldn't show (they're private companies or universities — you can't buy their stock)"):
                st.caption(" · ".join(sorted(set(str(u)[:40] for u in unmatched))[:60]))


with st.expander("💡 Why small companies? (30-second read)"):
    st.markdown("""
A $100 million government deal means **nothing** to a giant like Apple —
it's pocket change to them.

But give that same deal to a company worth $400 million, and it equals
**a quarter of everything the company is worth**. That's the kind of news
that can move a stock.

**What the little tags mean:**
- 🟢 **up X% since the deal** — the stock rose a little. The news may not be fully "priced in" yet.
- 🔴 **already jumped X%** — the stock shot up already. Buying now means you're late to the party.
- ⚠ **hard to trade** — very few people trade this stock daily, so it's tricky to buy and sell.
- 🔥 **bosses bought their own stock** — the company's own executives spent personal money on it. They know the company best.

**One honest warning:** none of this is a guarantee. Small stocks can drop fast.
Check the 📜 Report Card page to see how past picks actually did.
""")

disclaimer()
