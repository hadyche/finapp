"""Tests for Congress-trade and insider-leaderboard normalization (pure logic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.data.congress_trades import (
    parse_amount_range,
    normalize_congress_rows,
    top_purchased_tickers,
)
from src.data.insider_leaderboard import parse_money, normalize_openinsider_table


# ── Congress ──────────────────────────────────────────────────────────────────

HOUSE_ROWS = [
    {"representative": "Hon. Jane Smith", "ticker": "MRCY", "type": "purchase",
     "amount": "$15,001 - $50,000", "transaction_date": "2026-06-20",
     "disclosure_date": "06/28/2026"},
    {"representative": "Hon. Bob Jones", "ticker": "AAPL", "type": "sale_full",
     "amount": "$1,001 - $15,000", "transaction_date": "2026-06-18",
     "disclosure_date": "06/25/2026"},
    # non-stock rows must be dropped
    {"representative": "Hon. Bob Jones", "ticker": "--", "type": "purchase",
     "amount": "$1,001 - $15,000", "transaction_date": "2026-06-18",
     "disclosure_date": "06/25/2026"},
]

SENATE_ROWS = [
    {"senator": "Thomas Example", "ticker": "MRCY", "type": "Purchase",
     "amount": "$50,001 - $100,000", "transaction_date": "06/15/2026",
     "disclosure_date": "07/01/2026"},
]


def test_parse_amount_range():
    assert parse_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert parse_amount_range("$50,000,001 +") == (50000001.0, 50000001.0)
    assert parse_amount_range(None) == (None, None)
    assert parse_amount_range("Unknown") == (None, None)


def test_normalize_house_rows():
    df = normalize_congress_rows(HOUSE_ROWS, "House")
    assert len(df) == 2  # "--" ticker dropped
    buy = df[df["ticker"] == "MRCY"].iloc[0]
    assert buy["politician"] == "Jane Smith"  # "Hon." stripped
    assert buy["action"] == "BUY"
    assert buy["disclosure_date"] == "2026-06-28"  # US format normalized
    assert df[df["ticker"] == "AAPL"].iloc[0]["action"] == "SELL"


def test_normalize_senate_rows():
    df = normalize_congress_rows(SENATE_ROWS, "Senate")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["politician"] == "Thomas Example"
    assert row["chamber"] == "Senate"
    assert row["action"] == "BUY"
    assert row["transaction_date"] == "2026-06-15"


def test_top_purchased_tickers_counts_distinct_politicians():
    df = pd.concat([
        normalize_congress_rows(HOUSE_ROWS, "House"),
        normalize_congress_rows(SENATE_ROWS, "Senate"),
    ], ignore_index=True)
    top = top_purchased_tickers(df)
    assert top.iloc[0]["ticker"] == "MRCY"
    assert top.iloc[0]["politicians"] == 2  # Smith + Example, AAPL sale excluded
    assert "AAPL" not in top["ticker"].tolist()


def test_normalize_congress_empty():
    assert normalize_congress_rows([], "House").empty
    assert top_purchased_tickers(pd.DataFrame()).empty


# ── Insider leaderboard ───────────────────────────────────────────────────────

def _openinsider_df():
    return pd.DataFrame({
        "X": ["", ""],
        "Filing\xa0Date": ["2026-07-01 16:04:11", "2026-07-02 09:12:00"],
        "Trade\xa0Date": ["2026-06-30", "2026-07-01"],
        "Ticker": ["MRCY", "BAD TICKER"],
        "Company\xa0Name": ["Mercury Systems", "Broken Co"],
        "Insider\xa0Name": ["Doe Jane", "Smith Bob"],
        "Title": ["CEO", "CFO"],
        "Trade\xa0Type": ["P - Purchase", "P - Purchase"],
        "Price": ["$41.20", "$10.00"],
        "Qty": ["+25,000", "+1,000"],
        "Value": ["+$1,030,000", "+$10,000"],
    })


def test_parse_money():
    assert parse_money("+$1,030,000") == 1_030_000.0
    assert parse_money("$41.20") == 41.20
    assert parse_money("-$5,000") == -5000.0
    assert parse_money("") is None


def test_normalize_openinsider_table():
    out = normalize_openinsider_table(_openinsider_df())
    assert len(out) == 1  # invalid ticker dropped
    row = out.iloc[0]
    assert row["ticker"] == "MRCY"
    assert row["value"] == 1_030_000.0
    assert row["qty"] == 25_000.0
    assert row["filing_date"] == "2026-07-01"


def test_normalize_openinsider_excludes_sales():
    df = _openinsider_df()
    df["Trade\xa0Type"] = ["S - Sale", "S - Sale"]
    assert normalize_openinsider_table(df).empty


def test_normalize_openinsider_missing_columns():
    assert normalize_openinsider_table(pd.DataFrame({"Foo": [1]})).empty
    assert normalize_openinsider_table(pd.DataFrame()).empty
