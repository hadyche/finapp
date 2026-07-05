"""Tests for Congress-trade and insider-leaderboard normalization (pure logic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.data.congress_trades import (
    records_to_trades,
    parse_amount_range,
    top_purchased_tickers,
    recent_and_latest,
)
from src.data.insider_leaderboard import parse_money, normalize_openinsider_table


# ── Congress (official Senate eFD PTR tables) ─────────────────────────────────

PTR_RECORDS = [
    {"#": 1, "Transaction Date": "06/20/2026", "Owner": "Self", "Ticker": "MRCY",
     "Asset Name": "Mercury Systems Inc", "Asset Type": "Stock",
     "Type": "Purchase", "Amount": "$15,001 - $50,000", "Comment": "--"},
    {"#": 2, "Transaction Date": "06/18/2026", "Owner": "Spouse", "Ticker": "AAPL",
     "Asset Name": "Apple Inc", "Asset Type": "Stock",
     "Type": "Sale (Full)", "Amount": "$1,001 - $15,000", "Comment": "--"},
    # Non-stock assets and blank tickers must be dropped
    {"#": 3, "Transaction Date": "06/15/2026", "Owner": "Self", "Ticker": "--",
     "Asset Name": "US Treasury Note", "Asset Type": "Other Securities",
     "Type": "Purchase", "Amount": "$50,001 - $100,000", "Comment": "--"},
    {"#": 4, "Transaction Date": "06/15/2026", "Owner": "Self", "Ticker": "--",
     "Asset Name": "Municipal Bond", "Asset Type": "Municipal Security",
     "Type": "Purchase", "Amount": "$15,001 - $50,000", "Comment": "--"},
]


def test_parse_amount_range():
    assert parse_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert parse_amount_range("$50,000,001 +") == (50000001.0, 50000001.0)
    assert parse_amount_range(None) == (None, None)
    assert parse_amount_range("Unknown") == (None, None)


def test_records_to_trades_maps_ptr_rows():
    df = records_to_trades(PTR_RECORDS, "Jane Smith", "2026-06-28")
    assert len(df) == 2  # bonds and blank tickers dropped
    buy = df[df["ticker"] == "MRCY"].iloc[0]
    assert buy["politician"] == "Jane Smith"
    assert buy["chamber"] == "Senate"
    assert buy["action"] == "BUY"
    assert buy["amount"] == "$15,001 - $50,000"
    assert buy["amount_low"] == 15001.0
    assert buy["transaction_date"] == "2026-06-20"  # US format normalized
    assert buy["disclosure_date"] == "2026-06-28"


def test_records_to_trades_sale_full_maps_to_sell():
    df = records_to_trades(PTR_RECORDS, "Jane Smith", "2026-06-28")
    assert df[df["ticker"] == "AAPL"].iloc[0]["action"] == "SELL"


def test_records_to_trades_garbage():
    assert records_to_trades([], "X", "2026-01-01").empty
    assert records_to_trades([None, "x", 42], "X", "2026-01-01").empty


def test_top_purchased_tickers_counts_distinct_politicians():
    df = pd.concat([
        records_to_trades(PTR_RECORDS, "Jane Smith", "2026-06-28"),
        records_to_trades(PTR_RECORDS[:1], "Thomas Example", "2026-07-01"),
    ], ignore_index=True)
    top = top_purchased_tickers(df)
    assert top.iloc[0]["ticker"] == "MRCY"
    assert top.iloc[0]["politicians"] == 2  # Smith + Example; AAPL sale excluded
    assert "AAPL" not in top["ticker"].tolist()


def test_recent_and_latest_handles_missing_dates():
    # None / pd.NA disclosure dates crash vectorized string comparisons on
    # PyArrow-backed pandas (the live Streamlit Cloud crash) — must not raise
    df = pd.DataFrame({
        "politician": ["A", "B", "C"],
        "chamber": ["House"] * 3,
        "ticker": ["MRCY", "TLS", "BBAI"],
        "action": ["BUY"] * 3,
        "amount": [""] * 3,
        "amount_low": [None] * 3,
        "transaction_date": ["2026-06-01", None, "2026-06-20"],
        "disclosure_date": pd.array(["2020-01-01", pd.NA, "2099-12-31"], dtype="string"),
    })
    recent, latest = recent_and_latest(df, days_back=90)
    assert latest == "2099-12-31"
    assert recent["ticker"].tolist() == ["BBAI"]  # NA row and 2020 row excluded


def test_recent_and_latest_empty_frame():
    recent, latest = recent_and_latest(pd.DataFrame(), 90)
    assert recent.empty and latest is None


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
