"""Stock Detail — deep dive into a single ticker."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import plotly.graph_objects as go
from src.ui.theme import inject_css, page_header, disclaimer, ACCENT, DOWN
from src.ui.components import glossary_popover
from src.data.favorites import is_favorite, toggle_favorite
from src.data.stock_detail import get_price_history, get_quote, get_news, get_fundamental_context
from src.data.gov_contracts import fed_dollar_summary
from src.data.ticker_map import load_sec_company_map, build_name_index, ticker_to_cik
from src.data.insider_trades import insider_buys_for_cik

inject_css()

# Resolve the ticker from navigation state OR the URL, so refreshing,
# bookmarking, and sharing a detail page all work
_qp = ""
try:
    _qp = str(st.query_params.get("t", "")).upper().strip()
except Exception:
    pass
# URL wins: feed rows navigate by link, so the URL is always the fresh intent
ticker = _qp or st.session_state.get("selected_ticker") or None
if ticker:
    st.session_state.selected_ticker = ticker

if not ticker:
    page_header("🔍 Look Up a Stock")
    st.markdown('<div class="feed-section-sub">Type any stock\'s nickname (ticker) to see its price, '
                'government money, insider buying, and how easy it is to trade.</div>', unsafe_allow_html=True)
    manual = st.text_input("Ticker", placeholder="e.g. MRCY", label_visibility="collapsed").upper().strip()
    if manual:
        st.session_state.selected_ticker = manual
        st.query_params["t"] = manual
        st.rerun()
    st.caption("Or pick a stock from 💰 Today's Picks or 🎩 Smart Money — every row links here.")
    st.stop()

# Keep the URL in sync so refresh/share always work
try:
    if st.query_params.get("t", "") != ticker:
        st.query_params["t"] = ticker
except Exception:
    pass

st.page_link("pages/1_Home.py", label="← Back to Today's Picks")
st.caption("🔗 This page has its own web address — copy it from your browser bar to share or bookmark this stock.")

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
                 help="Saved until you refresh the page"):
        toggle_favorite(ticker)
        st.rerun()
    glossary_popover()

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
        <div class="stat-label">What the whole company is worth</div>
        <div class="stat-value">{_fmt(quote.get('market_cap'), '$', 'B', 1e9)}</div>
    </div>""", unsafe_allow_html=True)
    s3.markdown(f"""<div class="stat-box">
        <div class="stat-label">Lowest–highest price this year</div>
        <div class="stat-value" style="font-size:1.05rem;">${(quote.get('fifty_two_low') or 0):.2f} – ${(quote.get('fifty_two_high') or 0):.2f}</div>
    </div>""", unsafe_allow_html=True)
    s4.markdown(f"""<div class="stat-box">
        <div class="stat-label">Shares traded today</div>
        <div class="stat-value">{_fmt(quote.get('volume'), '', 'M', 1e6)}</div>
    </div>""", unsafe_allow_html=True)
else:
    st.warning("Live price data unavailable right now.")

st.divider()

# ── Price chart with timeframe toggle ──────────────────────────────────────────
st.markdown('<div class="feed-section">📈 The Price Over Time</div>', unsafe_allow_html=True)
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
    closes = hist["Close"].astype(float)
    start_p, end_p = float(closes.iloc[0]), float(closes.iloc[-1])
    chg = end_p - start_p
    chg_pct = (chg / start_p * 100) if start_p else 0.0
    up = chg >= 0
    line_color = ACCENT if up else DOWN
    fill_color = "rgba(0, 178, 93, 0.07)" if up else "rgba(229, 72, 77, 0.07)"
    arrow = "▲" if up else "▼"
    cls = "stat-delta-up" if up else "stat-delta-down"
    st.markdown(
        f'<div class="{cls}" style="font-size:0.95rem; margin:2px 0 0 2px;">'
        f'{arrow} ${abs(chg):.2f} ({chg_pct:+.1f}%) over {st.session_state.chart_tf}</div>',
        unsafe_allow_html=True,
    )

    # Robinhood-style: zoom the y-axis to the price action instead of $0,
    # so a $6 stock's real movement isn't squashed into a flat line
    ymin, ymax = float(closes.min()), float(closes.max())
    pad = (ymax - ymin) * 0.08 or max(ymax * 0.01, 0.01)
    baseline = ymin - pad

    fig = go.Figure()
    # invisible floor trace so the soft fill hugs the visible range, not zero
    fig.add_trace(go.Scatter(
        x=hist["date"], y=[baseline] * len(hist),
        mode="lines", line=dict(width=0),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=hist["date"], y=closes,
        mode="lines", line=dict(color=line_color, width=2.2),
        fill="tonexty", fillcolor=fill_color,
        name="", hovertemplate="$%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=360, margin=dict(t=16, b=24, l=8, r=8),
        showlegend=False,
        hovermode="x unified",
        yaxis=dict(range=[baseline, ymax + pad]),
    )
    fig.update_yaxes(
        showgrid=False, zeroline=False, side="right",
        nticks=4, tickprefix="$",
        tickfont=dict(size=11, color="#878E96"),
    )
    fig.update_xaxes(
        showgrid=False, nticks=6,
        tickfont=dict(size=11, color="#878E96"),
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikecolor="#C7CCD1", spikethickness=1, spikedash="solid",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info(f"Price history for {ticker} unavailable.")

st.divider()

# ── Federal $ breakdown ───────────────────────────────────────────────────────
st.markdown('<div class="feed-section">🏛️ Money From the Government</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">Every deal the U.S. government makes is public. Here\'s what this company has won recently.</div>', unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def _sec_map():
    return load_sec_company_map()

@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    return build_name_index(_sec_map())

@st.cache_data(ttl=21600, show_spinner=False)
def _awards_pool(days):
    # One shared pull for all tickers — not one 1000-row fetch per ticker
    from src.data.gov_contracts import fetch_recent_awards
    return fetch_recent_awards(days_back=days, limit=1000, min_amount=1_000_000)

@st.cache_data(ttl=21600)
def _fed(t, days):
    return fed_dollar_summary(t, _name_index(), days_back=days, awards=_awards_pool(days))

fed_period_col, _ = st.columns([1, 3])
with fed_period_col:
    fed_days = st.selectbox(
        "How far back to look",
        [90, 180, 365],
        index=2,
        format_func=lambda x: f"Last {x} days",
        key="fed_period",
    )

with st.spinner("Reading government records…"):
    fed = _fed(ticker, fed_days)

if fed["total"] > 0:
    cap = quote.get("market_cap")

    @st.cache_data(ttl=86400, show_spinner=False)
    def _fundamentals(t):
        return get_fundamental_context([t]).get(t, {})

    fund = _fundamentals(ticker)
    revenue = fund.get("revenue")

    f1, f2, f3, f4 = st.columns(4)
    f1.markdown(f"""<div class="stat-box">
        <div class="stat-label">Money won</div>
        <div class="stat-value">${fed['total']/1e6:.1f}M</div>
    </div>""", unsafe_allow_html=True)
    f2.markdown(f"""<div class="stat-box">
        <div class="stat-label">Number of deals</div>
        <div class="stat-value">{fed['count']}</div>
    </div>""", unsafe_allow_html=True)
    impact = f"{fed['total']/cap*100:.1f}%" if cap else "—"
    f3.markdown(f"""<div class="stat-box">
        <div class="stat-label">Compared to company's value</div>
        <div class="stat-value">{impact}</div>
    </div>""", unsafe_allow_html=True)
    vs_rev = f"{fed['total']/revenue*100:.0f}%" if revenue else "—"
    f4.markdown(f"""<div class="stat-box">
        <div class="stat-label">Compared to a year of sales</div>
        <div class="stat-value">{vs_rev}</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("**Which parts of the government paid them**")
    ag = fed["agencies"].copy()
    ag["total"] = ag["total"].apply(lambda x: f"${x:,.0f}")
    ag = ag.rename(columns={"agency": "Government agency", "total": "Paid", "count": "Deals"})
    st.dataframe(ag, hide_index=True, use_container_width=True)

    with st.expander(f"📋 See all {fed['count']} deals"):
        cts = fed["contracts"][["date", "recipient", "amount", "agency", "award_type"]].copy()
        cts["amount"] = cts["amount"].apply(lambda x: f"${x:,.0f}")
        cts = cts.rename(columns={"date": "Signed", "recipient": "Who won it",
                                  "amount": "Worth", "agency": "Paid by", "award_type": "Deal type"})
        st.dataframe(cts, hide_index=True, use_container_width=True)
else:
    st.info(f"We didn't find any government deals for {ticker} in this time window (or the government website isn't answering).")

st.divider()

# ── Liquidity & Trading ───────────────────────────────────────────────────────
st.markdown('<div class="feed-section">💧 How easy is it to buy & sell?</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">If very few people trade a stock, buying or selling it can be tricky.</div>', unsafe_allow_html=True)

avg_vol = quote.get("avg_volume")
price = quote.get("price")
adv_usd = (avg_vol * price) if (avg_vol and price) else None

l1, l2, l3 = st.columns(3)
l1.markdown(f"""<div class="stat-box">
    <div class="stat-label">Shares traded per day</div>
    <div class="stat-value">{f"{avg_vol/1e6:.2f}M" if avg_vol else "—"}</div>
</div>""", unsafe_allow_html=True)
l2.markdown(f"""<div class="stat-box">
    <div class="stat-label">Dollars traded per day</div>
    <div class="stat-value">{f"${adv_usd/1e6:.1f}M" if adv_usd else "—"}</div>
</div>""", unsafe_allow_html=True)
if adv_usd is not None and adv_usd < 1_000_000:
    l3.markdown("""<div class="stat-box">
        <div class="stat-label">Verdict</div>
        <div class="stat-value stat-delta-down" style="font-size:1.05rem;">⚠ Hard to trade — be careful</div>
    </div>""", unsafe_allow_html=True)
elif adv_usd is not None:
    l3.markdown("""<div class="stat-box">
        <div class="stat-label">Verdict</div>
        <div class="stat-value stat-delta-up" style="font-size:1.05rem;">✓ Easy enough for normal amounts</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ── Insider activity (SEC Form 4) ─────────────────────────────────────────────
st.markdown('<div class="feed-section">👤 Are the bosses buying?</div>', unsafe_allow_html=True)
st.markdown('<div class="feed-section-sub">When a company\'s own executives spend their personal money on its stock, they believe it\'s going up. (From official SEC filings, last 90 days.)</div>', unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def _insider(t):
    cik = ticker_to_cik(t, _sec_map())
    if cik is None:
        return None
    return insider_buys_for_cik(cik, days_back=90)

with st.spinner("Checking SEC Form 4 filings…"):
    ins = _insider(ticker)

if ins:
    i1, i2, i3 = st.columns(3)
    i1.markdown(f"""<div class="stat-box">
        <div class="stat-label">Times they bought</div>
        <div class="stat-value">{ins['n_buys']}</div>
    </div>""", unsafe_allow_html=True)
    i2.markdown(f"""<div class="stat-box">
        <div class="stat-label">Different bosses buying</div>
        <div class="stat-value">{ins['n_insiders']}</div>
    </div>""", unsafe_allow_html=True)
    i3.markdown(f"""<div class="stat-box">
        <div class="stat-label">Their own money spent</div>
        <div class="stat-value">${ins['total_usd']/1e3:,.0f}K</div>
    </div>""", unsafe_allow_html=True)
    if ins.get("last_date"):
        st.caption(f"Most recent buy: {ins['last_date']}. Several bosses buying at the same time is the strongest good sign there is.")
else:
    st.caption("No bosses bought their own stock in the last 90 days (or the SEC website isn't answering). Note: bosses *selling* is normal — everyone needs cash sometimes. It's the *buying* that means something.")

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
    with st.expander("ℹ️ What does this company actually do?"):
        st.write(quote["summary"])

disclaimer()
