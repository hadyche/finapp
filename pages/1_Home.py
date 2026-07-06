"""Home — small companies that just won big government money."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta
from src.ui.theme import inject_css, disclaimer
from src.ui.components import info_popover, glossary_popover
from src.data.gov_contracts import fetch_awards_wide, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index, ticker_to_cik
from src.data.stock_detail import get_market_stats, get_price_changes_since
from src.data.insider_trades import insider_buys_for_cik
from src.data.congress_trades import fetch_congress_trades
from src.analysis.asymmetry import build_contract_signals, score_signal_row
from src.analysis.convergence import smart_money_tags, congress_buy_set

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
    awards = fetch_awards_wide(days_back=days_back)
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

@st.cache_data(ttl=86400, show_spinner=False)
def _congress_buys() -> set:
    try:
        trades, _latest, _err = fetch_congress_trades(days_back=90, max_reports=20)
        return congress_buy_set(trades)
    except Exception:
        return set()


def fmt_ago(iso: str) -> str:
    try:
        mins = int((datetime.now() - datetime.fromisoformat(iso)).total_seconds() // 60)
        if mins < 2: return "just now"
        if mins < 60: return f"{mins}m ago"
        return f"{mins//60}h ago"
    except Exception:
        return ""


def fmt_next_scan(iso: str) -> str:
    try:
        nxt = datetime.fromisoformat(iso) + timedelta(hours=6)
        return nxt.strftime("%H:%M")
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


def days_since(date_str: str) -> float | None:
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        return max((datetime.now() - d).days, 0)
    except Exception:
        return None


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


def change_pill(chg) -> str:
    """The since-deal price reaction, colored by direction."""
    if chg is None:
        return '<span class="feed-meta">no price data</span>'
    if chg >= 25:
        return f'<span class="pill pill-red">already jumped +{chg:.0f}%</span>'
    if chg >= 0:
        return f'<div class="feed-amount" style="color:var(--accent-strong);">+{chg:.1f}%</div><div class="feed-meta">since the deal</div>'
    return f'<div class="feed-amount" style="color:var(--down-strong);">−{abs(chg):.1f}%</div><div class="feed-meta">since the deal</div>'


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
3. We show you **small companies** where the deal is **huge compared to the company's size**, and we check whether **insiders and senators are buying too**.

**Example:** imagine a lemonade stand worth $100 suddenly gets a $25 order.
That one order = 25% of what the whole stand is worth. That's the kind of
mismatch we look for — just with real companies and millions of dollars.

**The Strength score (0–100)** adds it all up: how big the deal is, how fresh,
whether the price already moved, how easy the stock is to trade, and whether
smart money agrees.
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
        st.caption(f"checked {len(matched)} deals · {fmt_ago(scanned_at)} · next scan ~{fmt_next_scan(scanned_at)}")
        st.markdown(
            '<div class="empty-state">Nothing big enough in the last '
            f'{days} days with these filters — and we won\'t pretend otherwise.<br>'
            'Deals this lopsided only show up a few times a week; that rarity is '
            'exactly why they matter. Try a longer window, or come back tomorrow.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Scoring each pick — price reaction, insiders, senators…"):
            pairs = tuple((r["ticker"], str(r["date"])[:10]) for _, r in signals.iterrows() if r["date"])
            changes = _price_changes(pairs)
            insider_map = {t: _insiders(t) for t in signals["ticker"].head(8)}
            senate_buys = _congress_buys()

        # ── Signal Strength: one score that combines everything ──────────────
        scored = []
        for _, row in signals.iterrows():
            t = row["ticker"]
            conv = smart_money_tags(t, senate_buys, insider_map.get(t))
            score, reasons = score_signal_row(
                impact_ratio=row["impact_ratio"],
                days_since_award=days_since(row["date"]),
                pct_change_since=changes.get(t),
                adv_usd=stats.get(t, {}).get("adv_usd"),
                confidence=row["confidence"],
                n_smart_signals=conv["n_signals"],
            )
            scored.append({"row": row, "score": score, "reasons": reasons, "conv": conv})
        scored.sort(key=lambda x: x["score"], reverse=True)

        st.caption(
            f"{len(scored)} picks · checked {len(matched)} government deals · updated {fmt_ago(scanned_at)} · "
            f"next scan ~{fmt_next_scan(scanned_at)}"
        )

        # ── Hero: the strongest pick today ────────────────────────────────────
        top = scored[0]
        trow, tconv = top["row"], top["conv"]
        t = trow["ticker"]
        chg = changes.get(t)
        reasons_html = "".join(
            f'<div class="hero-reason"><span class="check">✓</span>{r}</div>'
            for r in (top["reasons"] + tconv["labels"])[:5]
        )
        chg_html = ""
        if chg is not None:
            sign = "+" if chg >= 0 else "−"
            color = "var(--accent-strong)" if chg >= 0 else "var(--down-strong)"
            chg_html = f'<span style="color:{color}; font-weight:700;">{sign}{abs(chg):.1f}% since the deal</span>'
        st.markdown(f"""
        <a class="feed-link" href="stock?t={t}" target="_self">
        <div class="hero-card">
            <div class="hero-label">⭐ Today's strongest pick · Strength {top['score']:.0f}/100</div>
            <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:4px;">
                <div class="hero-ticker">{t} <span style="font-size:0.95rem; font-weight:500; color:var(--text-2);">{str(trow['matched_name'])[:40]}</span></div>
                <div>{chg_html}</div>
            </div>
            <div class="feed-meta" style="margin:2px 0 10px 0;">{fmt_cap(trow['market_cap'])} · {str(trow['agency'])[:36]} · signed {fmt_date(trow['date'])}</div>
            {reasons_html}
            <div class="feed-meta" style="margin-top:10px;">Tap for the full picture →</div>
        </div>
        </a>
        """, unsafe_allow_html=True)

        # ── The rest of the feed ──────────────────────────────────────────────
        for item in scored[1:]:
            row, conv = item["row"], item["conv"]
            t = row["ticker"]
            ratio_pct = row["impact_ratio"] * 100
            chg = changes.get(t)
            meta = f"{fmt_cap(row['market_cap'])} · {str(row['agency'])[:30]}"
            if row["date"]:
                meta += f" · signed {fmt_date(row['date'])}"

            tags = [f'<span class="pill pill-gray">deal = {ratio_pct:.0f}% of the company</span>',
                    f'<span class="pill pill-gray">Strength {item["score"]:.0f}</span>']
            adv = stats.get(t, {}).get("adv_usd")
            if adv is not None and adv < THIN_VOLUME_USD:
                tags.append('<span class="pill pill-red">⚠ hard to trade</span>')
            for lbl in conv["labels"]:
                tags.append(f'<span class="pill pill-green">{lbl}</span>')

            st.markdown(f"""
            <a class="feed-link" href="stock?t={t}" target="_self">
            <div class="feed-row">
                <div class="feed-left">
                    <div class="feed-icon">{t[:4]}</div>
                    <div class="feed-text">
                        <div class="feed-ticker">{t}</div>
                        <div class="feed-company">{str(row['matched_name'])[:48]}</div>
                        <div class="feed-meta" style="margin-top:3px;">{meta}</div>
                    </div>
                </div>
                <div class="feed-right">{change_pill(chg)}</div>
            </div>
            </a>
            <div style="margin:-6px 0 12px 56px;">{' '.join(tags)}</div>
            """, unsafe_allow_html=True)

        st.markdown(
            '<div class="feed-meta" style="margin-top:14px;">Small stocks can drop fast. '
            'This is public information, not advice — check the 📜 Report Card to see how past picks did.</div>',
            unsafe_allow_html=True,
        )

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

**What the Strength score means:** we add up how big the deal is compared to
the company, how recently it was signed, whether the price already reacted,
how easy the stock is to trade, and whether **insiders or senators are buying
the same stock**. 100 = everything lines up. Most picks score 40–70.

**One honest warning:** none of this is a guarantee. Small stocks can drop fast.
Check the 📜 Report Card page to see how past picks actually did.
""")

disclaimer()
