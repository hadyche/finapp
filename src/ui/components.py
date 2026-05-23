"""Reusable UI components."""
import streamlit as st
from src.data.favorites import is_favorite, toggle_favorite


SIZE_LABELS = {"small": "Small Cap", "mid": "Mid Cap", "large": "Large Cap"}
SIZE_CLASS = {"small": "badge-small", "mid": "badge-mid", "large": "badge-large"}


def size_badge_html(size: str) -> str:
    return f'<span class="badge {SIZE_CLASS.get(size, "badge-large")}">{SIZE_LABELS.get(size, "Stock")}</span>'


def score_pill_html(score: float) -> str:
    if score >= 60:
        return '<span class="pill pill-strong">🔥 STRONG SIGNAL</span>'
    if score >= 40:
        return '<span class="pill pill-positive">✓ POSITIVE</span>'
    return '<span class="pill pill-watch">👀 WATCH</span>'


def open_stock_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    st.switch_page("pages/3_Stock_Detail.py")


def render_pick_card(entry, rank: int = None, is_hero: bool = False, key_prefix: str = ""):
    """Render a stock pick card with click-through, favorite button, and signals."""
    hero_cls = "card-hero" if is_hero else ""
    ticker_cls = "ticker-hero" if is_hero else "ticker-big"

    rank_text = ""
    if rank == 1:
        rank_text = '<span style="color:#00E676; font-weight:700; font-size:0.75rem; letter-spacing:0.1em;">🔥 TOP PICK</span> · '
    elif rank:
        rank_text = f'<span style="color:#6B7280; font-weight:600; font-size:0.75rem; letter-spacing:0.1em;">#{rank}</span> · '

    signals_html = ""
    for sig in entry.signals[:4]:
        signals_html += f'<div style="color:#D1D5DB; font-size:0.88rem; margin:5px 0;"><span style="color:#00E676; margin-right:8px; font-weight:700;">✓</span>{sig}</div>'

    sources_html = ""
    for inst in entry.buying_institutions:
        sources_html += f'<span class="source-chip"><span class="check">✓</span>{inst}</span>'

    st.markdown(f"""
    <div class="card {hero_cls}">
        <div style="font-size:0.78rem; color:#6B7280; letter-spacing:0.06em; margin-bottom:6px;">
            {rank_text}<span style="text-transform:uppercase; font-weight:600;">{entry.sector}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
                <div class="{ticker_cls}">{entry.ticker}</div>
                <div class="company-name">{entry.company}</div>
                <div style="margin-top:6px;">{size_badge_html(entry.size)}</div>
            </div>
            <div style="text-align:right;">
                {score_pill_html(entry.score)}
                <div class="meta-text" style="margin-top:8px;">Confidence {int(entry.score)}/100</div>
            </div>
        </div>
        <div style="margin-top:14px; padding-top:14px; border-top:1px solid #1F2937;">
            {signals_html}
        </div>
        <div style="margin-top:12px;">{sources_html}</div>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons under the card
    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button("📊 View details", key=f"{key_prefix}_view_{entry.ticker}", use_container_width=True):
            open_stock_detail(entry.ticker)
    with c2:
        fav = is_favorite(entry.ticker)
        label = "⭐ Saved" if fav else "☆ Save"
        if st.button(label, key=f"{key_prefix}_fav_{entry.ticker}", use_container_width=True):
            toggle_favorite(entry.ticker)
            st.rerun()


def render_compact_row(entry, key_prefix: str = ""):
    """Compact 1-line row for list views (Favorites, Discover)."""
    col1, col2, col3, col4, col5 = st.columns([1.5, 3, 1.5, 1.5, 1.5])
    with col1:
        st.markdown(f"### {entry.ticker}")
        st.caption(SIZE_LABELS.get(entry.size, ""))
    with col2:
        st.markdown(f"**{entry.company}**")
        st.caption(f"{entry.sector} · " + (", ".join(entry.buying_institutions) or "Held"))
    with col3:
        st.markdown(score_pill_html(entry.score), unsafe_allow_html=True)
        st.caption(f"{int(entry.score)}/100")
    with col4:
        if st.button("Details", key=f"{key_prefix}_row_view_{entry.ticker}", use_container_width=True):
            open_stock_detail(entry.ticker)
    with col5:
        fav = is_favorite(entry.ticker)
        if st.button("⭐" if fav else "☆", key=f"{key_prefix}_row_fav_{entry.ticker}", use_container_width=True):
            toggle_favorite(entry.ticker)
            st.rerun()
    st.divider()
