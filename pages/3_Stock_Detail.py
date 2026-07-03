"""Stock Detail — deep dive into a single ticker."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.graph_objects as go
from src.ui.theme import inject_css, page_header, disclaimer
from src.data.favorites import is_favorite, toggle_favorite
from src.data.stock_detail import get_price_history, get_quote, get_news
from src.data.gov_contracts import fed_dollar_summary
from src.data.ticker_map import load_sec_company_map, build_name_index, ticker_to_cik
from src.data.insider_trades import insider_buys_for_cik

inject_css()

ticker = st.session_state.get("selected_ticker")

if not ticker:
    page_header("Stock Detail")
    st.info("👈 Pick a stock from the Signals feed to view its details.")
    manual = st.text_input("Or type a ticker symbol:", placeholder="e.g. MRCY").upper().strip()
    if manual:
        st.session_state.selected_ticker = manual
        st.rerun()
    st.stop()

# ── Top header with ticker, fav button, and quote ─────────────────────────────
@st.cache_data(ttl=900)
def _quote(t): return get_quote(t)

quote = _quote(ticker)

head_l, head_r = st.columns([3, 1])
with head_l:
    st.markdown(f"""
    <div class="detail-ticker">{ticker}</div>
    <div class="detail-name">{quote.get('long_name', ticker)}</div>
    <div style="margin-top:8px;">
        <span class="pill pill-gray">{quote.get('sector') or 'Stock'}</span>
    </div>
    """, unsafe_allow_html=True)
with head_r:
    fav = is_favorite(ticker)
    if st.button("⭐ Saved" if fav else "☆ Save", use_container_width=True, key="detail_fav",
                 help="Saved for this browser session only — resets on refresh"):
        toggle_favorite(ticker)
        st.rerun()

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
    st.warning("Live price data unavailable right now.")

st.divider()

# ── Price chart with timeframe toggle ──────────────────────────────────────────
st.markdown('<div class="feed-section">📈 Price Chart</div>', unsafe_allow_html=True)
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
        mode="lines", line=dict(color="#00C805", width=2.5),
        fill="tozeroy", fillcolor="rgba(0,200,5,0.08)",
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
    fig.update_yaxes(gridcolor="#141414", zerolinecolor="#141414")
    fig.update_xaxes(gridcolor="#141414")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"Price history for {ticker} unavailable.")

st.divider()

# ── Federal $ breakdown ───────────────────────────────────────────────────────
st.markdown('<div class="feed-section">🏛️ Federal Government Money</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">Recent federal contracts matched to this company</div>', unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    return build_name_index(load_sec_company_map())

@st.cache_data(ttl=21600)
def _fed(t, days):
    return fed_dollar_summary(t, _name_index(), days_back=days)

fed_period_col, _ = st.columns([1, 3])
with fed_period_col:
    fed_days = st.selectbox(
        "Period",
        [90, 180, 365],
        index=2,
        format_func=lambda x: f"Last {x} days",
        key="fed_period",
    )

with st.spinner("Scanning USAspending…"):
    fed = _fed(ticker, fed_days)

if fed["total"] > 0:
    cap = quote.get("market_cap")
    f1, f2, f3 = st.columns(3)
    f1.markdown(f"""<div class="stat-box">
        <div class="stat-label">Total Awarded</div>
        <div class="stat-value">${fed['total']/1e6:.1f}M</div>
    </div>""", unsafe_allow_html=True)
    f2.markdown(f"""<div class="stat-box">
        <div class="stat-label">Contracts</div>
        <div class="stat-value">{fed['count']}</div>
    </div>""", unsafe_allow_html=True)
    impact = f"{fed['total']/cap*100:.1f}%" if cap else "—"
    f3.markdown(f"""<div class="stat-box">
        <div class="stat-label">vs Market Cap</div>
        <div class="stat-value">{impact}</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("**Top funding agencies**")
    ag = fed["agencies"].copy()
    ag["total"] = ag["total"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(ag, hide_index=True, use_container_width=True)

    with st.expander(f"📋 All {fed['count']} contracts"):
        cts = fed["contracts"][["date", "recipient", "amount", "agency", "award_type"]].copy()
        cts["amount"] = cts["amount"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(cts, hide_index=True, use_container_width=True)
else:
    st.info(f"No federal contracts matched to {ticker} in the selected period (or USAspending is unavailable).")

st.divider()

# ── Liquidity & Trading ───────────────────────────────────────────────────────
st.markdown('<div class="feed-section">💧 Liquidity & Trading</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">Can you actually get in and out of this stock?</div>', unsafe_allow_html=True)

avg_vol = quote.get("avg_volume")
price = quote.get("price")
adv_usd = (avg_vol * price) if (avg_vol and price) else None

l1, l2, l3 = st.columns(3)
l1.markdown(f"""<div class="stat-box">
    <div class="stat-label">Avg daily volume</div>
    <div class="stat-value">{f"{avg_vol/1e6:.2f}M" if avg_vol else "—"}</div>
</div>""", unsafe_allow_html=True)
l2.markdown(f"""<div class="stat-box">
    <div class="stat-label">Avg daily $ traded</div>
    <div class="stat-value">{f"${adv_usd/1e6:.1f}M" if adv_usd else "—"}</div>
</div>""", unsafe_allow_html=True)
if adv_usd is not None and adv_usd < 1_000_000:
    l3.markdown("""<div class="stat-box">
        <div class="stat-label">Tradability</div>
        <div class="stat-value stat-delta-down" style="font-size:1.05rem;">⚠ Thin — orders can move the price</div>
    </div>""", unsafe_allow_html=True)
elif adv_usd is not None:
    l3.markdown("""<div class="stat-box">
        <div class="stat-label">Tradability</div>
        <div class="stat-value stat-delta-up" style="font-size:1.05rem;">OK for retail size</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Insider activity (SEC Form 4) ─────────────────────────────────────────────
st.markdown('<div class="feed-section">👤 Insider Buying</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">Officers &amp; directors buying with their own money — SEC Form 4, last 90 days</div>', unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def _insider(t):
    cik = ticker_to_cik(t, load_sec_company_map())
    if cik is None:
        return None
    return insider_buys_for_cik(cik, days_back=90)

with st.spinner("Checking SEC Form 4 filings…"):
    ins = _insider(ticker)

if ins:
    i1, i2, i3 = st.columns(3)
    i1.markdown(f"""<div class="stat-box">
        <div class="stat-label">Open-market buys</div>
        <div class="stat-value">{ins['n_buys']}</div>
    </div>""", unsafe_allow_html=True)
    i2.markdown(f"""<div class="stat-box">
        <div class="stat-label">Distinct insiders</div>
        <div class="stat-value">{ins['n_insiders']}</div>
    </div>""", unsafe_allow_html=True)
    i3.markdown(f"""<div class="stat-box">
        <div class="stat-label">Total invested</div>
        <div class="stat-value">${ins['total_usd']/1e3:,.0f}K</div>
    </div>""", unsafe_allow_html=True)
    if ins.get("last_date"):
        st.caption(f"Most recent buy: {ins['last_date']}. Multiple insiders buying together is the strongest version of this signal.")
else:
    st.caption("No open-market insider purchases found in the last 90 days (or EDGAR is unavailable). Insider *sales* are normal and not tracked — buys are the signal.")

st.divider()

# ── News ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="feed-section">📰 Recent News</div>', unsafe_allow_html=True)

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
