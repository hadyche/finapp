"""Tests for since-award price math and Form 4 parsing (pure logic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.data.stock_detail import change_since
from src.data.insider_trades import parse_form4_xml


# ── change_since ──────────────────────────────────────────────────────────────

def _closes():
    idx = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-10", "2026-06-20"])
    return pd.Series([10.0, 11.0, 12.0, 14.0, 15.0], index=idx)


def test_change_since_from_award_date():
    # award on 06-02: first close 11 → latest 15 = +36.36%
    assert abs(change_since(_closes(), "2026-06-02") - 36.3636) < 0.01


def test_change_since_weekend_uses_next_trading_day():
    # 06-05 has no bar; first close on/after is 06-10 (14) → +7.14%
    assert abs(change_since(_closes(), "2026-06-05") - (15 - 14) / 14 * 100) < 0.01


def test_change_since_future_date_is_none():
    assert change_since(_closes(), "2026-07-01") is None


def test_change_since_handles_tz_aware_index():
    s = _closes()
    s.index = s.index.tz_localize("America/New_York")
    assert change_since(s, "2026-06-02") is not None


def test_change_since_empty_series():
    assert change_since(pd.Series(dtype=float), "2026-06-01") is None


# ── parse_form4_xml ───────────────────────────────────────────────────────────

FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-06-15</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>5000</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-06-16</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>9000</value></transactionShares>
        <transactionPricePerShare><value>13.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_form4_keeps_only_open_market_purchases():
    buys = parse_form4_xml(FORM4)
    assert len(buys) == 1  # the sale (code S) is excluded
    b = buys[0]
    assert b["owner"] == "DOE JANE"
    assert b["date"] == "2026-06-15"
    assert b["shares"] == 5000
    assert b["value"] == 5000 * 12.50


def test_parse_form4_award_grants_excluded():
    # Code A (grant/award of equity) is compensation, not a conviction buy
    grant = FORM4.replace(">P<", ">A<")
    assert parse_form4_xml(grant) == []


def test_parse_form4_garbage_input():
    assert parse_form4_xml("not xml at all") == []
    assert parse_form4_xml("<ownershipDocument></ownershipDocument>") == []
