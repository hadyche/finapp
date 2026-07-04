"""Smart Money — Congress trades and the biggest insider buys, daily."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.ui.theme import inject_css, page_header, disclaimer
from src.data.congress_trades import fetch_congress_trades, top_purchased_tickers
from src.data.insider_leaderboard import fetch_top_insider_buys
from src.data.stock_detail import get_market_stats

inject_css()
page_header("🎩 Smart Money", "What people with information advantages are buying — updated daily")


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
        return str(date_str)[:10]


@st.cache_data(ttl=86400, show_spinner=False)
def _congress(days: int):
    return fetch_congress_trades(days_back=days), datetime.now().isoformat()

@st.cache_data(ttl=86400, show_spinner=False)
def _insider_buys(days: int):
    return fetch_top_insider_buys(days=days, min_value_k=100, limit=100), datetime.now().isoformat()

@st.cache_data(ttl=21600, show_spinner=False)
def _caps(tickers: tuple):
    return get_market_stats(list(tickers))


tab_congress, tab_insiders = st.tabs(["🏛️ Congress Trades", "👤 Biggest Insider Buys"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CONGRESS
# ══════════════════════════════════════════════════════════════════════════════
with tab_congress:
    c1, c2 = st.columns(2)
    with c1:
        cg_days = st.selectbox(
            "Window", [30, 60, 90, 180], index=2,
            format_func=lambda x: f"Disclosed in last {x} days",
            label_visibility="collapsed", key="cg_days",
        )
    with c2:
        chamber = st.selectbox(
            "Chamber", ["Both chambers", "House", "Senate"],
            label_visibility="collapsed", key="cg_chamber",
        )

    with st.spinner("Loading STOCK Act disclosures…"):
        trades, fetched_at = _congress(cg_days)

    if trades.empty:
        st.error(
            "Congress disclosure data is unavailable right now. No fake fallbacks — "
            "try again in a few minutes.",
            icon="🏛️",
        )
    else:
        if chamber != "Both chambers":
            trades = trades[trades["chamber"] == chamber]

        top = top_purchased_tickers(trades, top_n=8)
        if not top.empty:
            chips = "".join(
                f'<span class="source-chip">{r.ticker} · {r.politicians} member{"s" if r.politicians > 1 else ""}</span>'
                for r in top.itertuples()
            )
            st.markdown('<div class="feed-section-sub" style="margin-top:8px;">Most bought across Congress</div>', unsafe_allow_html=True)
            st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)

        st.caption(
            f"{len(trades)} trades · newest disclosures first · politicians may report up to 45 days late · "
            f"data: official STOCK Act filings via Stock Watcher"
        )

        for i, row in trades.head(60).iterrows():
            action = row["action"]
            pill = {"BUY": "pill-green", "SELL": "pill-red"}.get(action, "pill-gray")
            traded = fmt_date(row["transaction_date"]) if row["transaction_date"] else "—"
            disclosed = fmt_date(row["disclosure_date"]) if row["disclosure_date"] else "—"

            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f"""
                <div class="feed-row">
                    <div class="feed-left">
                        <div class="feed-icon">{str(row['ticker'])[:4]}</div>
                        <div class="feed-text">
                            <div class="feed-ticker">{row['ticker']}
                                <span class="pill {pill}" style="margin-left:8px;">{action}</span>
                            </div>
                            <div class="feed-company">{row['politician']} · {row['chamber']}</div>
                            <div class="feed-meta" style="margin-top:3px;">traded {traded} · disclosed {disclosed}</div>
                        </div>
                    </div>
                    <div class="feed-right">
                        <div class="feed-amount">{row['amount'] or '—'}</div>
                        <div class="feed-meta">reported range</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.button("→", key=f"cg_{i}", on_click=go_to_detail, args=(row["ticker"],))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INSIDER BUY LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_insiders:
    in_days = st.selectbox(
        "Window", [3, 7, 14, 30], index=1,
        format_func=lambda x: f"Filed in last {x} days",
        label_visibility="collapsed", key="in_days",
    )

    with st.spinner("Ranking the biggest insider buys…"):
        buys, fetched_at = _insider_buys(in_days)

    if buys.empty:
        st.error(
            "Insider filing data is unavailable right now. No fake fallbacks — "
            "try again in a few minutes.",
            icon="👤",
        )
    else:
        shown = buys.head(30)
        stats = _caps(tuple(sorted(shown["ticker"].unique())))

        st.caption(
            f"Top {len(shown)} open-market purchases (SEC Form 4, code P) · "
            f"executives buying with their own money · data via OpenInsider"
        )

        for i, row in shown.iterrows():
            cap = (stats.get(row["ticker"]) or {}).get("cap")
            gem = cap is not None and cap < 5e9
            cap_txt = f"${cap/1e9:.1f}B cap" if cap and cap >= 1e9 else (f"${cap/1e6:.0f}M cap" if cap else "cap unknown")
            gem_tag = ' <span class="pill pill-green">hidden-gem size</span>' if gem else ""
            title = str(row["title"] or "").strip()

            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f"""
                <div class="feed-row">
                    <div class="feed-left">
                        <div class="feed-icon">{str(row['ticker'])[:4]}</div>
                        <div class="feed-text">
                            <div class="feed-ticker">{row['ticker']}{gem_tag}</div>
                            <div class="feed-company">{str(row['insider'])[:30]}{f" · {title[:22]}" if title else ""} · {str(row['company'])[:26]}</div>
                            <div class="feed-meta" style="margin-top:3px;">{cap_txt} · filed {fmt_date(row['filing_date'])}</div>
                        </div>
                    </div>
                    <div class="feed-right">
                        <div class="feed-amount feed-amount-green">${row['value']/1e6:.2f}M</div>
                        <div class="feed-meta">{f"{row['qty']:,.0f} sh @ ${row['price']:.2f}" if row['qty'] and row['price'] else "purchase"}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.button("→", key=f"in_{i}", on_click=go_to_detail, args=(row["ticker"],))


with st.expander("💡 Why follow this money?"):
    st.markdown("""
**🏛️ Congress** — Members of Congress must disclose their stock trades under the
STOCK Act. Studies have repeatedly found their portfolios outperform the market.
They can disclose up to 45 days after trading, so you're seeing what they *did*,
not what they're doing today — the "disclosed" date shows exactly how stale each trade is.

**👤 Insiders** — Officers and directors buying their own company's stock on the
open market (SEC Form 4, code P) are betting their personal money on the business
they know best. Sales are routine (taxes, diversification) and carry no signal —
that's why this board only shows **buys**. The green **hidden-gem size** tag marks
companies under $5B, where insider conviction moves the needle most.

Both boards refresh daily. This is public information published with a delay —
never inside information.
    """)

disclaimer()
