"""Home — clean Robinhood-style feed of federal awards and big money moves."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.ui.theme import inject_css, disclaimer
from src.data.gov_contracts import recent_award_feed
from src.data.sec_holdings import recent_moves_feed

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


# ── Feed toggle ───────────────────────────────────────────────────────────────
feed_choice = st.radio(
    "Feed",
    ["🏛️ Federal Awards", "🏦 BlackRock & Big Money"],
    horizontal=True,
    label_visibility="collapsed",
)


@st.cache_data(ttl=21600)
def _awards(days, min_amt):
    return recent_award_feed(days_back=days, min_amount=min_amt, top_n=25)

@st.cache_data(ttl=86400)
def _moves():
    return recent_moves_feed(top_n=25)


def go_to_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    st.switch_page("pages/3_Stock_Detail.py")


def fmt_amount(amount: float) -> str:
    if amount >= 1e9:
        return f"${amount/1e9:.1f}B"
    if amount >= 1e6:
        return f"${amount/1e6:.0f}M"
    return f"${amount/1e3:.0f}K"


def fmt_date(date_str: str) -> str:
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        delta = (datetime.now() - d).days
        if delta == 0: return "today"
        if delta == 1: return "yesterday"
        if delta < 7: return f"{delta}d ago"
        if delta < 30: return f"{delta//7}w ago"
        if delta < 365: return f"{delta//30}mo ago"
        return f"{delta//365}y ago"
    except Exception:
        return ""


def render_feed_row(ticker, name, primary, secondary, key, amount_color="green"):
    """Robinhood-style row with click-through."""
    icon = ticker[:3] if ticker else "?"
    color_cls = "feed-amount-green" if amount_color == "green" else ""

    col1, col2 = st.columns([10, 1])
    with col1:
        st.markdown(f"""
        <div class="feed-row">
            <div class="feed-left">
                <div class="feed-icon">{icon}</div>
                <div class="feed-text">
                    <div class="feed-ticker">{ticker or "—"}</div>
                    <div class="feed-company">{name}</div>
                </div>
            </div>
            <div class="feed-right">
                <div class="feed-amount {color_cls}">{primary}</div>
                <div class="feed-meta">{secondary}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if ticker:
            st.button("→", key=key, on_click=go_to_detail, args=(ticker,))


# ══════════════════════════════════════════════════════════════════════════════
# FEED 1 — FEDERAL AWARDS
# ══════════════════════════════════════════════════════════════════════════════

if "Federal" in feed_choice:
    st.markdown('<div class="feed-section">Recent Federal Contract Awards</div>', unsafe_allow_html=True)
    st.markdown('<div class="feed-section-sub">Biggest awards scanned from USAspending.gov</div>', unsafe_allow_html=True)

    # Filter for amount threshold
    f1, f2 = st.columns(2)
    with f1:
        days = st.selectbox(
            "Period", [7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"Last {x} days",
            label_visibility="collapsed",
        )
    with f2:
        min_m = st.selectbox(
            "Min amount", [1, 5, 10, 50, 100, 500],
            index=1,
            format_func=lambda x: f"≥ ${x}M",
            label_visibility="collapsed",
        )

    with st.spinner(""):
        awards = _awards(days, min_m * 1_000_000)

    if awards.empty:
        st.markdown('<div class="empty-state">No awards found above ${0}M in the last {1} days.<br>Try lowering the threshold.</div>'.format(min_m, days), unsafe_allow_html=True)
    else:
        for i, row in awards.iterrows():
            ticker = row.get("ticker") or ""
            recipient = str(row.get("recipient", "Unknown"))[:45]
            agency = str(row.get("agency", ""))[:35]
            amount = float(row.get("amount", 0) or 0)
            date_str = str(row.get("date", ""))[:10] if row.get("date") else ""

            secondary = f"{agency}" + (f" · {fmt_date(date_str)}" if date_str else "")
            render_feed_row(
                ticker=ticker,
                name=recipient,
                primary=fmt_amount(amount),
                secondary=secondary,
                key=f"fed_{i}",
                amount_color="green",
            )


# ══════════════════════════════════════════════════════════════════════════════
# FEED 2 — BLACKROCK / BIG MONEY
# ══════════════════════════════════════════════════════════════════════════════

else:
    st.markdown('<div class="feed-section">Big Money is Buying</div>', unsafe_allow_html=True)
    st.markdown('<div class="feed-section-sub">Latest 13F position changes from BlackRock, Vanguard, State Street</div>', unsafe_allow_html=True)

    inst_filter = st.selectbox(
        "Institution",
        ["All institutions", "BlackRock only", "Vanguard only", "State Street only"],
        label_visibility="collapsed",
    )

    with st.spinner(""):
        moves = _moves()

    if inst_filter != "All institutions" and not moves.empty:
        target = inst_filter.replace(" only", "")
        moves = moves[moves["institution"] == target]

    if moves.empty:
        st.markdown('<div class="empty-state">No big money moves to show.</div>', unsafe_allow_html=True)
    else:
        for i, row in moves.iterrows():
            ticker = str(row.get("ticker") or "")
            company = str(row.get("company", ticker))[:40]
            institution = str(row.get("institution", ""))
            action = str(row.get("action", ""))
            value = float(row.get("value_current", 0) or 0)
            change_pct = float(row.get("value_change_pct", 0) or 0)

            action_word = "Just opened" if action == "NEW" else "Added to"
            secondary = f"{action_word} · {institution}"
            if action == "INCREASED" and change_pct > 0:
                secondary += f" · +{change_pct:.0f}%"

            render_feed_row(
                ticker=ticker,
                name=company,
                primary=fmt_amount(value),
                secondary=secondary,
                key=f"big_{i}",
                amount_color="green",
            )


# ── Footer ────────────────────────────────────────────────────────────────────

with st.expander("💡 How does FlowSignal work?"):
    st.markdown("""
**Two simple feeds, both updated daily:**

🏛️ **Federal Awards** — Every contract the U.S. government awards is public on USAspending.gov. We surface the biggest ones in the time window you choose.

🏦 **Big Money** — Every quarter, BlackRock, Vanguard, and State Street must publicly disclose every stock they hold. We track new positions and big additions.

**Why this matters:** When the U.S. government commits hundreds of millions to a company, that's guaranteed revenue. When the world's biggest investors open a brand-new position in a small company, that's a high-conviction bet.

Tap any row to see live price chart, federal $ breakdown, and full institutional activity.
    """)

disclaimer()
