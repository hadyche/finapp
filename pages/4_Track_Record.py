"""Report Card — what happened to past picks. Honesty page."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from datetime import datetime
from src.ui.theme import inject_css, page_header, disclaimer
from src.data.gov_contracts import fetch_awards_wide, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index
from src.data.stock_detail import (
    get_market_stats,
    get_price_changes_since,
    get_price_changes_over,
    get_benchmark_changes,
)
from src.analysis.asymmetry import build_contract_signals

inject_css()
page_header("📜 Report Card", "Did our past picks actually go up? We check — and we show you the losers too.")


@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    return build_name_index(load_sec_company_map())

@st.cache_data(ttl=86400, show_spinner=False)
def _past_signals(start_days: int, end_days: int):
    """Signals as they would have appeared for deals signed start–end days ago."""
    awards = fetch_awards_wide(days_back=start_days, end_days_back=end_days)
    if awards.empty:
        return pd.DataFrame()
    matched = match_awards_to_tickers(awards, _name_index())
    tickers = sorted(matched["ticker"].dropna().unique())
    stats = get_market_stats(tickers)
    caps_now = {t: s.get("cap") for t, s in stats.items()}

    # Look-ahead-bias fix: judging a PAST pick with TODAY's market cap is
    # cheating (a stock that doubled might only pass the size filter
    # because we saw the future). Back-calculate the cap at award time
    # from the price change since the award, assuming the share count is
    # roughly constant over these ~2-4 months.
    pairs = []
    for _, r in matched.dropna(subset=["ticker"]).iterrows():
        if r["date"]:
            pairs.append((r["ticker"], str(r["date"])[:10]))
    changes = get_price_changes_since(pairs)
    caps_then = {}
    for t, cap in caps_now.items():
        chg = changes.get(t)
        if cap is None:
            caps_then[t] = None
        elif chg is None or chg <= -100:
            caps_then[t] = cap
        else:
            caps_then[t] = cap / (1 + chg / 100)

    return build_contract_signals(matched, caps_then)

@st.cache_data(ttl=86400, show_spinner=False)
def _outcomes(pairs: tuple):
    return get_price_changes_since(list(pairs))

@st.cache_data(ttl=86400, show_spinner=False)
def _outcomes_over(pairs: tuple, horizon: int):
    return get_price_changes_over(list(pairs), horizon)

@st.cache_data(ttl=86400, show_spinner=False)
def _benchmark(dates: tuple):
    # IWM = the Russell 2000 small-cap index fund — a fair yardstick for
    # small companies (comparing tiny stocks to the S&P 500 giants isn't)
    return get_benchmark_changes(list(dates), benchmark="IWM")


window = st.selectbox(
    "Grade the picks from…",
    [(60, 30), (90, 30), (120, 60)],
    format_func=lambda w: f"{w[1]} to {w[0]} days ago",
    help="We look at picks from a while back so there's been time to see what happened.",
)

with st.spinner("Finding old picks and checking what happened to them…"):
    past = _past_signals(window[0], window[1])

if past.empty:
    st.info("No picks from that time window (or the government website isn't answering). "
            "Truly big wins are rare — try a wider window.")
else:
    pairs = tuple((r["ticker"], str(r["date"])[:10]) for _, r in past.iterrows() if r["date"])
    changes = _outcomes(pairs)
    week1 = _outcomes_over(pairs, 7)
    month1 = _outcomes_over(pairs, 30)
    bench = _benchmark(tuple(str(r["date"])[:10] for _, r in past.iterrows() if r["date"]))

    rows = []
    for _, r in past.iterrows():
        t = r["ticker"]
        d = str(r["date"])[:10]
        rows.append({
            "Stock": t,
            "Company": str(r["matched_name"])[:32],
            "Deal signed": d,
            "Deal size": f"${r['total_awarded']/1e6:.0f}M",
            "vs company value": f"{r['impact_ratio']*100:.0f}%",
            "+1 week": week1.get(t),
            "+1 month": month1.get(t),
            "Since then": changes.get(t),
            "Small caps overall": bench.get(d),
        })
    df = pd.DataFrame(rows)

    scored = df.dropna(subset=["Since then"])
    if not scored.empty:
        wins = (scored["Since then"] > 0).sum()
        beat = scored.dropna(subset=["Small caps overall"])
        beat_n = (beat["Since then"] > beat["Small caps overall"]).sum()

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="stat-box">
            <div class="stat-label">Picks we graded</div>
            <div class="stat-value">{len(scored)}</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="stat-box">
            <div class="stat-label">Went up</div>
            <div class="stat-value">{wins} of {len(scored)}</div>
        </div>""", unsafe_allow_html=True)
        median = scored["Since then"].median()
        med_cls = "stat-delta-up" if median >= 0 else "stat-delta-down"
        c3.markdown(f"""<div class="stat-box">
            <div class="stat-label">Typical result</div>
            <div class="stat-value {med_cls}" style="font-size:1.4rem;">{median:+.1f}%</div>
        </div>""", unsafe_allow_html=True)
        if len(beat):
            st.caption(
                f"{beat_n} of {len(beat)} beat small caps overall (the Russell 2000 index — "
                f"the fair comparison group for companies this size) over the same time."
            )

    show = df.copy()
    for col in ["+1 week", "+1 month", "Since then", "Small caps overall"]:
        show[col] = show[col].map(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.caption("**+1 week / +1 month** = what the stock did in exactly that time after the deal was signed. "
               "**Since then** = from the deal until today.")

st.markdown("""
<div style="background: rgba(180,83,9,0.08); border: 1px solid rgba(180,83,9,0.3);
border-radius: 10px; padding: 14px 18px; margin-top: 20px; color: #92400E; font-size: 0.82rem;">
<strong>Being honest with you:</strong> company sizes for past picks are back-calculated
from price history (we assume the share count didn't change much — usually true over a
few months, not always). The number of picks is small and short windows are noisy.
This page exists so YOU can see whether the idea actually works — not to promise it does.
A bad report card is useful information too: it tells you not to bet money on this yet.
</div>
""", unsafe_allow_html=True)

disclaimer()
