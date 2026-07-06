"""Tests for the v3 redesign: score, convergence, senate ranking, horizons, watchlist."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.analysis.asymmetry import score_signal_row
from src.analysis.convergence import smart_money_tags, congress_buy_set
from src.data.congress_trades import rank_congress_buys, records_to_trades
from src.data.stock_detail import change_over
from src.data.favorites import parse_watchlist_param


# ── score_signal_row ──────────────────────────────────────────────────────────

def test_score_best_case_near_100():
    score, reasons = score_signal_row(
        impact_ratio=0.30, days_since_award=1, pct_change_since=2.0,
        adv_usd=5_000_000, confidence="exact", n_smart_signals=2,
    )
    assert score >= 95
    assert any("Deal = 30%" in r for r in reasons)
    assert any("barely moved" in r for r in reasons)
    assert any("Smart money" in r for r in reasons)


def test_score_already_moved_gets_no_pricing_points_and_warns():
    fresh, _ = score_signal_row(0.10, 5, 2.0, 2_000_000, "exact", 0)
    late, late_reasons = score_signal_row(0.10, 5, 40.0, 2_000_000, "exact", 0)
    assert fresh - late >= 14  # the +15 not-priced-yet component
    assert any("late" in r for r in late_reasons)


def test_score_thin_volume_warns_and_scores_lower():
    liquid, _ = score_signal_row(0.10, 5, 2.0, 2_000_000, "exact", 0)
    thin, thin_reasons = score_signal_row(0.10, 5, 2.0, 100_000, "exact", 0)
    assert liquid - thin == 10
    assert any("Hard to trade" in r for r in thin_reasons)


def test_score_freshness_decays():
    fresh, _ = score_signal_row(0.10, 0, None, None, "", 0)
    stale, _ = score_signal_row(0.10, 90, None, None, "", 0)
    assert fresh > stale


def test_score_capped_at_100():
    score, _ = score_signal_row(5.0, 0, 0.0, 9e9, "exact", 5)
    assert score == 100.0


def test_score_handles_all_unknowns():
    score, reasons = score_signal_row(0.05, None, None, None, "", 0)
    assert 0 < score < 50
    assert reasons  # always at least the deal-size reason


# ── convergence ───────────────────────────────────────────────────────────────

def test_smart_money_tags_both_signals():
    tags = smart_money_tags("MRCY", {"MRCY", "TLS"}, {"n_insiders": 2})
    assert tags["n_signals"] == 2
    assert any("Multiple smart-money" in l for l in tags["labels"])
    assert any("Senators" in l for l in tags["labels"])
    assert any("bosses" in l for l in tags["labels"])


def test_smart_money_tags_none():
    tags = smart_money_tags("MRCY", set(), None)
    assert tags["n_signals"] == 0 and tags["labels"] == []


def test_congress_buy_set():
    df = pd.DataFrame({"ticker": ["mrcy", "AAPL"], "action": ["BUY", "SELL"],
                       "politician": ["A", "B"]})
    assert congress_buy_set(df) == {"MRCY"}
    assert congress_buy_set(pd.DataFrame()) == set()
    assert congress_buy_set(None) == set()


# ── rank_congress_buys ────────────────────────────────────────────────────────

def _senate_trades():
    recs = [
        {"Transaction Date": "06/20/2026", "Ticker": "MRCY", "Asset Type": "Stock",
         "Type": "Purchase", "Amount": "$50,001 - $100,000"},
        {"Transaction Date": "06/21/2026", "Ticker": "AAPL", "Asset Type": "Stock",
         "Type": "Purchase", "Amount": "$1,001 - $15,000"},
    ]
    return pd.concat([
        records_to_trades(recs, "Jane Smith", "2026-06-28"),
        records_to_trades(recs[:1], "Tom Example", "2026-06-29"),
    ], ignore_index=True)


def test_rank_congress_buys_prefers_more_senators_and_small_caps():
    ranked = rank_congress_buys(_senate_trades(), caps={"MRCY": 400e6, "AAPL": 3e12})
    assert ranked.iloc[0]["ticker"] == "MRCY"   # 2 senators + small cap + bigger $
    assert ranked.iloc[0]["n_senators"] == 2
    assert ranked.iloc[0]["score"] > ranked.iloc[1]["score"]


def test_rank_congress_buys_empty():
    assert rank_congress_buys(pd.DataFrame()).empty
    sells = _senate_trades().assign(action="SELL")
    assert rank_congress_buys(sells).empty


# ── change_over (fixed horizons) ──────────────────────────────────────────────

def _closes():
    idx = pd.to_datetime(["2026-05-01", "2026-05-08", "2026-06-01", "2026-06-15"])
    return pd.Series([10.0, 12.0, 15.0, 20.0], index=idx)


def test_change_over_one_week():
    # start 05-01 (10), first close >= 05-08 is 12 → +20%
    assert abs(change_over(_closes(), "2026-05-01", 7) - 20.0) < 0.01


def test_change_over_horizon_not_reached_yet():
    assert change_over(_closes(), "2026-06-15", 30) is None


def test_change_over_bad_inputs():
    assert change_over(pd.Series(dtype=float), "2026-05-01", 7) is None


# ── watchlist URL param ───────────────────────────────────────────────────────

def test_parse_watchlist_param():
    assert parse_watchlist_param("mrcy,tls") == {"MRCY", "TLS"}
    assert parse_watchlist_param(" asle , BRK.B ,junk!!,TOOLONGG") == {"ASLE", "BRK.B"}
    assert parse_watchlist_param("") == set()
    assert parse_watchlist_param(None) == set()
