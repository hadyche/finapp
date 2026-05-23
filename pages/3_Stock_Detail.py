"""Stock Detail — deep dive into a single ticker."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import plotly.graph_objects as go
from src.ui.theme import inject_css, page_header, disclaimer
from src.ui.components import size_badge_html, score_pill_html
from src.data.favorites import is_favorite, toggle_favorite
from src.data.stock_detail import get_price_history, get_quote, get_news
from src.data.gov_contracts import fed_dollar_summary
from src.data.sec_holdings import get_all_institution_changes, TICKER_SIZE
from src.data.market_data import fetch_sector_performance
from src.data.gov_contracts import top_recipients as load_recipients
from src.analysis.watchlist import build_watchlist

inject_css()

ticker = st.session_state.get("selected_ticker")

if not ticker:
    page_header("Stock Detail")
    st.info("👈 Pick a stock from the Home or Favorites page to view its details.")
    manual = st.text_input("Or type a ticker symbol:", placeholder="e.g. MRCY").upper().strip()
    if manual:
        st.session_state.selected_ticker = manual
        st.rerun()
    st.stop()

# ── Top header with ticker, fav button, and quote ─────────────────────────────
@st.cache_data(ttl=900)
def _quote(t): return get_quote(t)

quote = _quote(ticker)
size = TICKER_SIZE.get(ticker, "large")

head_l, head_r = st.columns([3, 1])
with head_l:
    st.markdown(f"""
    <div style="display:flex; align-items:baseline; gap:14px;">
        <div class="ticker-hero">{ticker}</div>
        <div>{size_badge_html(size)}</div>
    </div>
    <div class="company-name" style="font-size:1.1rem;">{quote.get('long_name', ticker)}</div>
    <div class="meta-text">{quote.get('sector') or ''} {('· ' + quote.get('industry')) if quote.get('industry') else ''}</div>
    """, unsafe_allow_html=True)
with head_r:
    fav = is_favorite(ticker)
    if st.button("⭐ Saved" if fav else "☆ Save to Favorites", use_container_width=True, key="detail_fav"):
        toggle_favorite(ticker)
        st.rerun()
    if quote.get("website"):
        st.markdown(f"[🌐 Company website]({quote['website']})")

# ── Live quote stats ───────────────────────────────────────────────────────────
if quote.get("price"):
    cp_class = "stat-delta-up" if quote.get("change", 0) >= 0 else "stat-delta-down"
    cp_sign = "+" if quote.get("change", 0) >= 0 else ""

    def _fmt(v, prefix="", suffix="", divisor=1):
        if v is None: return "—"
        return f"{prefix}{v / divisor:,.2f}{suffix}"

    s1, s2, s3, s4 = st.columns(4)
    s1.markdown(f"""<div class="stat-box">
        <div class="stat-label">Price</div>
        <div class="stat-value">${quote['price']:.2f}</div>
        <div class="{cp_class}">{cp_sign}{quote.get('change',0):.2f} ({cp_sign}{quote.get('change_pct',0):.2f}%)</div>
    </div>""", unsafe_allow_html=True)
    s2.markdown(f"""<div class="stat-box">
        <div class="stat-label">Market Cap</div>
        <div class="stat-value">{_fmt(quote.get('market_cap'), '$', 'B', 1e9)}</div>
    </div>""", unsafe_allow_html=True)
    s3.markdown(f"""<div class="stat-box">
        <div class="stat-label">52-week range</div>
        <div class="stat-value" style="font-size:1.05rem;">${quote.get('fifty_two_low', 0):.2f} – ${quote.get('fifty_two_high', 0):.2f}</div>
    </div>""", unsafe_allow_html=True)
    s4.markdown(f"""<div class="stat-box">
        <div class="stat-label">Volume</div>
        <div class="stat-value">{_fmt(quote.get('volume'), '', 'M', 1e6)}</div>
    </div>""", unsafe_allow_html=True)
else:
    st.warning("Live price data unavailable.")

st.divider()

# ── Price chart with timeframe toggle ──────────────────────────────────────────
st.markdown('<div class="section-h">📈 Price Chart</div>', unsafe_allow_html=True)
tf_cols = st.columns(8)
timeframes = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "Max"]
if "chart_tf" not in st.session_state:
    st.session_state.chart_tf = "3M"
for i, tf in enumerate(timeframes):
    with tf_cols[i]:
        if st.button(tf, key=f"tf_{tf}", use_container_width=True,
                     type="primary" if st.session_state.chart_tf == tf else "secondary"):
            st.session_state.chart_tf = tf
            st.rerun()

@st.cache_data(ttl=600)
def _hist(t, tf): return get_price_history(t, tf)

hist = _hist(ticker, st.session_state.chart_tf)
if not hist.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist["date"], y=hist["Close"],
        mode="lines", line=dict(color="#00E676", width=2.5),
        fill="tozeroy", fillcolor="rgba(0,230,118,0.08)",
        name="Price"
    ))
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=400, margin=dict(t=10, b=30, l=10, r=10),
        yaxis_title=None, xaxis_title=None,
        showlegend=False,
        hovermode="x unified",
    )
    fig.update_yaxes(gridcolor="#1F2937", zerolinecolor="#1F2937")
    fig.update_xaxes(gridcolor="#1F2937")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"Price history for {ticker} unavailable.")

st.divider()

# ── Federal $ breakdown ───────────────────────────────────────────────────────
st.markdown('<div class="section-h">🏛️ Federal Government Money</div>', unsafe_allow_html=True)
st.markdown('<div class="section-s">How much this company has received from federal contracts</div>', unsafe_allow_html=True)

@st.cache_data(ttl=21600)
def _fed(t, days): return fed_dollar_summary(t, days_back=days)

fed_period_col, _ = st.columns([1, 3])
with fed_period_col:
    fed_days = st.selectbox(
        "Period",
        [90, 180, 365, 730],
        index=2,
        format_func=lambda x: f"Last {x} days",
        key="fed_period",
    )

fed = _fed(ticker, fed_days)
if fed["total"] > 0:
    f1, f2, f3 = st.columns(3)
    f1.markdown(f"""<div class="stat-box">
        <div class="stat-label">Total Awarded</div>
        <div class="stat-value">${fed['total']/1e6:.1f}M</div>
    </div>""", unsafe_allow_html=True)
    f2.markdown(f"""<div class="stat-box">
        <div class="stat-label">Contracts</div>
        <div class="stat-value">{fed['count']}</div>
    </div>""", unsafe_allow_html=True)
    f3.markdown(f"""<div class="stat-box">
        <div class="stat-label">Agencies</div>
        <div class="stat-value">{len(fed['agencies'])}</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("**Top funding agencies**")
    ag = fed["agencies"].copy()
    ag["total"] = ag["total"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(ag, hide_index=True, use_container_width=True)

    with st.expander(f"📋 All {fed['count']} contracts"):
        cts = fed["contracts"].copy()
        if "amount" in cts.columns:
            cts["amount"] = cts["amount"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(cts, hide_index=True, use_container_width=True)
else:
    st.info(f"No federal contracts found for {ticker} in the selected period (or data unavailable).")

st.divider()

# ── Who's buying ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-h">🏦 Who\'s Buying</div>', unsafe_allow_html=True)
st.markdown('<div class="section-s">Latest 13F position changes from major institutions</div>', unsafe_allow_html=True)

@st.cache_data(ttl=86400)
def _holdings_for(t):
    df = get_all_institution_changes()
    if df.empty: return df
    return df[df["ticker"].str.upper() == t.upper()]

inst = _holdings_for(ticker)
if not inst.empty:
    st.dataframe(
        inst[["institution", "action", "value_current", "value_prior", "value_change_pct", "shares", "shares_change"]],
        hide_index=True, use_container_width=True,
    )
else:
    st.info(f"No tracked institutional activity for {ticker}.")

st.divider()

# ── FlowSignal score breakdown ────────────────────────────────────────────────
st.markdown('<div class="section-h">⚡ FlowSignal Score</div>', unsafe_allow_html=True)

@st.cache_data(ttl=86400)
def _wl_for_ticker(t):
    h = get_all_institution_changes()
    p = fetch_sector_performance(days_back=30)
    r = load_recipients(days_back=30, top_n=20)
    wl = build_watchlist(h, p, r, hidden_gems_only=False)
    return next((w for w in wl if w.ticker == t.upper()), None)

entry = _wl_for_ticker(ticker)
if entry:
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        st.markdown(score_pill_html(entry.score), unsafe_allow_html=True)
        st.markdown(f"### {int(entry.score)}/100")
        st.caption(f"Signal strength")
    with sc2:
        breakdown = pd.DataFrame({
            "Signal": ["🏦 Institutional", "🏛️ Gov Contracts", "📈 Sector Momentum", "💪 Conviction"],
            "Score": [entry.institutional_score, entry.contract_score, entry.momentum_score, entry.conviction_score],
            "Max": [60, 30, 15, 10],
        })
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=breakdown["Signal"], x=breakdown["Score"],
            orientation="h",
            marker=dict(color=["#00E676", "#4FC3F7", "#FFB74D", "#BA68C8"]),
            text=breakdown["Score"].round(1),
            textposition="outside",
        ))
        fig.update_layout(
            template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=260, margin=dict(t=20, b=20, l=20, r=40),
            xaxis_title="Points", showlegend=False,
        )
        fig.update_xaxes(gridcolor="#1F2937")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Key signals:**")
    for sig in entry.signals:
        st.markdown(f"<div style='color:#D1D5DB;'>✓ {sig}</div>", unsafe_allow_html=True)
else:
    st.info("No FlowSignal score available for this ticker.")

st.divider()

# ── News ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-h">📰 Recent News</div>', unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def _news(t): return get_news(t, limit=8)

news = _news(ticker)
if news:
    for n in news:
        title = n.get("title", "")
        link = n.get("link", "")
        pub = n.get("publisher", "")
        if link:
            st.markdown(f"- [{title}]({link}) · *{pub}*")
        else:
            st.markdown(f"- {title} · *{pub}*")
else:
    st.caption("No recent news.")

if quote.get("summary"):
    with st.expander("ℹ️ About this company"):
        st.write(quote["summary"])

disclaimer()
