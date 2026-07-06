"""Track Record — what happened to past signals. Honesty page."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from datetime import datetime
from src.ui.theme import inject_css, page_header, disclaimer
from src.data.gov_contracts import fetch_awards_wide, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index
from src.data.stock_detail import get_market_stats, get_price_changes_since, get_benchmark_changes
from src.analysis.asymmetry import build_contract_signals

inject_css()
page_header("📜 Report Card", "Did our past picks actually go up? We check — and we show you the losers too.")


@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    return build_name_index(load_sec_company_map())

@st.cache_data(ttl=86400, show_spinner=False)
def _past_signals(start_days: int, end_days: int):
    """Signals as they would have appeared for awards signed start–end days ago."""
    awards = fetch_awards_wide(days_back=start_days, end_days_back=end_days)
    if awards.empty:
        return pd.DataFrame()
    matched = match_awards_to_tickers(awards, _name_index())
    tickers = sorted(matched["ticker"].dropna().unique())
    stats = get_market_stats(tickers)
    caps = {t: s.get("cap") for t, s in stats.items()}
    return build_contract_signals(matched, caps)

@st.cache_data(ttl=86400, show_spinner=False)
def _outcomes(pairs: tuple):
    return get_price_changes_since(list(pairs))

@st.cache_data(ttl=86400, show_spinner=False)
def _benchmark(dates: tuple):
    return get_benchmark_changes(list(dates))


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
    spy = _benchmark(tuple(str(r["date"])[:10] for _, r in past.iterrows() if r["date"]))

    rows = []
    for _, r in past.iterrows():
        chg = changes.get(r["ticker"])
        bench = spy.get(str(r["date"])[:10])
        rows.append({
            "Stock": r["ticker"],
            "Company": str(r["matched_name"])[:36],
            "Deal signed": str(r["date"])[:10],
            "Deal size": f"${r['total_awarded']/1e6:.0f}M",
            "vs company value": f"{r['impact_ratio']*100:.0f}%",
            "Stock since then": chg,
            "Stock market average": bench,
        })
    df = pd.DataFrame(rows)

    scored = df.dropna(subset=["Stock since then"])
    if not scored.empty:
        wins = (scored["Stock since then"] > 0).sum()
        beat = scored.dropna(subset=["Stock market average"])
        beat_n = (beat["Stock since then"] > beat["Stock market average"]).sum()

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="stat-box">
            <div class="stat-label">Picks we graded</div>
            <div class="stat-value">{len(scored)}</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="stat-box">
            <div class="stat-label">Went up</div>
            <div class="stat-value">{wins} of {len(scored)}</div>
        </div>""", unsafe_allow_html=True)
        median = scored["Stock since then"].median()
        med_cls = "stat-delta-up" if median >= 0 else "stat-delta-down"
        c3.markdown(f"""<div class="stat-box">
            <div class="stat-label">Typical result</div>
            <div class="stat-value {med_cls}" style="font-size:1.4rem;">{median:+.1f}%</div>
        </div>""", unsafe_allow_html=True)
        if len(beat):
            st.caption(
                f"{beat_n} of {len(beat)} did better than the stock market average "
                f"(the S&P 500 — the 500 biggest U.S. companies) over the same time."
            )

    show = df.copy()
    for col in ["Stock since then", "Stock market average"]:
        show[col] = show[col].map(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")
    st.dataframe(show, hide_index=True, use_container_width=True)

st.markdown("""
<div style="background: rgba(180,83,9,0.08); border: 1px solid rgba(180,83,9,0.3);
border-radius: 10px; padding: 14px 18px; margin-top: 20px; color: #92400E; font-size: 0.82rem;">
<strong>Being honest with you:</strong> this report card is young, the number of picks
is small, and short time windows are noisy. It exists so YOU can see whether this
idea actually works — not to promise it does. A bad report card is useful
information too: it tells you not to bet money on this yet.
</div>
""", unsafe_allow_html=True)

disclaimer()
