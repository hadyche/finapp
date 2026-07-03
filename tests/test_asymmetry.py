"""Tests for the asymmetric-signal engine (pure logic, no network)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.analysis.asymmetry import (
    compute_impact_ratio,
    build_contract_signals,
    rank_signals,
    format_asymmetry_line,
)


def _awards():
    return pd.DataFrame([
        # Small company, huge award — MUST surface
        {"ticker": "MRCY", "matched_name": "Mercury Systems Inc", "confidence": "exact",
         "recipient": "MERCURY SYSTEMS INC", "amount": 84_000_000,
         "agency": "Department of Defense", "date": "2026-06-20", "award_id": "A1"},
        # Mega-cap, huge award — must NEVER surface (cap ceiling)
        {"ticker": "LMT", "matched_name": "Lockheed Martin Corp", "confidence": "exact",
         "recipient": "LOCKHEED MARTIN CORP", "amount": 900_000_000,
         "agency": "U.S. Navy", "date": "2026-06-18", "award_id": "A2"},
        # Small company, tiny award — below min ratio, filtered
        {"ticker": "TLS", "matched_name": "Telos Corp", "confidence": "exact",
         "recipient": "TELOS CORP", "amount": 100_000,
         "agency": "DHS", "date": "2026-06-15", "award_id": "A3"},
        # Unmatched recipient — ignored
        {"ticker": None, "matched_name": None, "confidence": None,
         "recipient": "SOME PRIVATE LLC", "amount": 50_000_000,
         "agency": "GSA", "date": "2026-06-14", "award_id": "A4"},
        # Two awards to same small company — aggregated
        {"ticker": "BBAI", "matched_name": "BigBear.ai Holdings", "confidence": "prefix",
         "recipient": "BIGBEAR.AI", "amount": 12_000_000,
         "agency": "NGA", "date": "2026-06-10", "award_id": "A5"},
        {"ticker": "BBAI", "matched_name": "BigBear.ai Holdings", "confidence": "prefix",
         "recipient": "BIGBEAR.AI", "amount": 9_000_000,
         "agency": "U.S. Army", "date": "2026-06-12", "award_id": "A6"},
        # Duplicate award_id — deduped, counted once
        {"ticker": "BBAI", "matched_name": "BigBear.ai Holdings", "confidence": "prefix",
         "recipient": "BIGBEAR.AI", "amount": 12_000_000,
         "agency": "NGA", "date": "2026-06-10", "award_id": "A5"},
    ])


CAPS = {
    "MRCY": 380_000_000,        # small
    "LMT": 110_000_000_000,     # mega
    "TLS": 250_000_000,         # small
    "BBAI": 500_000_000,        # small
}


def test_impact_ratio_basic():
    assert compute_impact_ratio(84_000_000, 380_000_000) == 84 / 380


def test_impact_ratio_invalid_inputs():
    assert compute_impact_ratio(None, 100) is None
    assert compute_impact_ratio(100, None) is None
    assert compute_impact_ratio(pd.NA, 100) is None
    assert compute_impact_ratio(0, 100) is None
    assert compute_impact_ratio(100, 0) is None
    assert compute_impact_ratio(-5, 100) is None
    assert compute_impact_ratio("abc", 100) is None


def test_mega_caps_never_surface():
    out = build_contract_signals(_awards(), CAPS)
    assert "LMT" not in out["ticker"].tolist()


def test_small_cap_big_award_surfaces_first():
    out = build_contract_signals(_awards(), CAPS)
    assert out.iloc[0]["ticker"] == "MRCY"
    assert abs(out.iloc[0]["impact_ratio"] - 84 / 380) < 1e-9


def test_below_min_ratio_filtered():
    out = build_contract_signals(_awards(), CAPS)
    assert "TLS" not in out["ticker"].tolist()


def test_awards_aggregate_and_dedupe():
    out = build_contract_signals(_awards(), CAPS)
    bbai = out[out["ticker"] == "BBAI"].iloc[0]
    assert bbai["total_awarded"] == 21_000_000  # A5 counted once + A6
    assert bbai["n_awards"] == 2


def test_unknown_market_cap_excluded():
    awards = _awards()
    caps = {k: v for k, v in CAPS.items() if k != "MRCY"}  # MRCY cap unknown
    out = build_contract_signals(awards, caps)
    assert "MRCY" not in out["ticker"].tolist()


def test_empty_and_all_unmatched():
    empty = build_contract_signals(pd.DataFrame(), CAPS)
    assert empty.empty
    unmatched_only = _awards()[_awards()["ticker"].isna()]
    assert build_contract_signals(unmatched_only, CAPS).empty


def test_rank_signals_merges_and_sorts():
    a = build_contract_signals(_awards(), CAPS)
    merged = rank_signals(a, pd.DataFrame(), None)
    assert list(merged["impact_ratio"]) == sorted(merged["impact_ratio"], reverse=True)


def test_format_asymmetry_line():
    out = build_contract_signals(_awards(), CAPS)
    line = format_asymmetry_line(out.iloc[0])
    assert "$84M" in line and "22% of its market cap" in line
    bbai_line = format_asymmetry_line(out[out["ticker"] == "BBAI"].iloc[0])
    assert "in federal awards" in bbai_line  # multi-award phrasing
