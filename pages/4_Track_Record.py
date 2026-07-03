"""Track Record — what happened to past signals. Honesty page."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from datetime import datetime
from src.ui.theme import inject_css, page_header, disclaimer
from src.data.gov_contracts import fetch_recent_awards, match_awards_to_tickers
from src.data.ticker_map import load_sec_company_map, build_name_index
from src.data.stock_detail import get_market_stats, get_price_changes_since, get_benchmark_changes
from src.analysis.asymmetry import build_contract_signals

inject_css()
page_header("📜 Track Record", "What actually happened to past signals — judge us by this")


@st.cache_data(ttl=86400, show_spinner=False)
def _name_index():
    return build_name_index(load_sec_company_map())

@st.cache_data(ttl=86400, show_spinner=False)
def _past_signals(start_days: int, end_days: int):
    """Signals as they would have appeared for awards signed start–end days ago."""
    awards = fetch_recent_awards(
        days_back=start_days, end_days_back=end_days,
        limit=500, min_amount=5_000_000,
    )
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
    "Signals from…",
    [(60, 30), (90, 30), (120, 60)],
    format_func=lambda w: f"{w[1]}–{w[0]} days ago",
)

with st.spinner("Rebuilding past signals and checking what happened…"):
    past = _past_signals(window[0], window[1])

if past.empty:
    st.info("No qualifying signals in that window (or USAspending is unavailable). "
            "Genuine asymmetric events are rare — try a wider window.")
else:
    pairs = tuple((r["ticker"], str(r["date"])[:10]) for _, r in past.iterrows() if r["date"])
    changes = _outcomes(pairs)
    spy = _benchmark(tuple(str(r["date"])[:10] for _, r in past.iterrows() if r["date"]))

    rows = []
    for _, r in past.iterrows():
        chg = changes.get(r["ticker"])
        bench = spy.get(str(r["date"])[:10])
        rows.append({
            "Ticker": r["ticker"],
            "Company": str(r["matched_name"])[:36],
            "Signed": str(r["date"])[:10],
            "Award": f"${r['total_awarded']/1e6:.0f}M",
            "Impact": f"{r['impact_ratio']*100:.0f}%",
            "Return since": chg,
            "S&P 500 same period": bench,
        })
    df = pd.DataFrame(rows)

    scored = df.dropna(subset=["Return since"])
    if not scored.empty:
        wins = (scored["Return since"] > 0).sum()
        beat = scored.dropna(subset=["S&P 500 same period"])
        beat_n = (beat["Return since"] > beat["S&P 500 same period"]).sum()

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="stat-box">
            <div class="stat-label">Signals</div>
            <div class="stat-value">{len(scored)}</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="stat-box">
            <div class="stat-label">Went up</div>
            <div class="stat-value">{wins}/{len(scored)}</div>
        </div>""", unsafe_allow_html=True)
        median = scored["Return since"].median()
        med_cls = "stat-delta-up" if median >= 0 else "stat-delta-down"
        c3.markdown(f"""<div class="stat-box">
            <div class="stat-label">Median return</div>
            <div class="stat-value {med_cls}" style="font-size:1.4rem;">{median:+.1f}%</div>
        </div>""", unsafe_allow_html=True)
        if len(beat):
            st.caption(f"{beat_n} of {len(beat)} beat the S&P 500 over the same period.")

    show = df.copy()
    for col in ["Return since", "S&P 500 same period"]:
        show[col] = show[col].map(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")
    st.dataframe(show, hide_index=True, use_container_width=True)

st.markdown("""
<div style="background: rgba(255,183,77,0.06); border: 1px solid rgba(255,183,77,0.25);
border-radius: 10px; padding: 14px 18px; margin-top: 20px; color: #FFCC80; font-size: 0.82rem;">
<strong>Read this honestly:</strong> this page uses today's market caps to reconstruct
past signals (caps at signal time aren't stored yet), the sample sizes are small,
and short windows are noisy. It exists so you can see whether the idea works —
not to promise it does. A losing window is real information too.
</div>
""", unsafe_allow_html=True)

disclaimer()
