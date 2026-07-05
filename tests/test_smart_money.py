"""Tests for Congress-trade and insider-leaderboard normalization (pure logic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.data.congress_trades import (
    normalize_capitoltrades_rows,
    top_purchased_tickers,
    recent_and_latest,
)
from src.data.insider_leaderboard import parse_money, normalize_openinsider_table


# ── Congress (CapitolTrades schema) ───────────────────────────────────────────

CT_ROWS = [
    # Fully embedded shape
    {"txType": "buy", "value": 32500, "txDate": "2026-06-20", "pubDate": "2026-06-28",
     "asset": {"assetTicker": "MRCY:US"},
     "politician": {"firstName": "Jane", "lastName": "Smith", "chamber": "house"}},
    # Sell, senate, fullName variant
    {"txType": "sell", "value": 8000, "txDate": "2026-06-18", "pubDate": "2026-06-25",
     "asset": {"assetTicker": "AAPL:US"},
     "politician": {"fullName": "Thomas Example", "chamber": "senate"}},
    # Flat/minimal shape (schema drift tolerance)
    {"txType": "buy", "value": None, "txDate": "2026-06-15", "pubDate": "2026-07-01",
     "ticker": "MRCY", "politicianName": "Bob Jones", "chamber": "house"},
    # Non-stock asset → dropped
    {"txType": "buy", "value": 1000, "txDate": "2026-06-15", "pubDate": "2026-07-01",
     "asset": {"assetTicker": None},
     "politician": {"fullName": "Bob Jones", "chamber": "house"}},
    # No politician name → dropped
    {"txType": "buy", "value": 1000, "txDate": "2026-06-15", "pubDate": "2026-07-01",
     "asset": {"assetTicker": "TLS:US"}},
]


def test_normalize_capitoltrades_shapes():
    df = normalize_capitoltrades_rows(CT_ROWS)
    assert len(df) == 3  # two invalid rows dropped
    buy = df[(df["ticker"] == "MRCY") & (df["politician"] == "Jane Smith")].iloc[0]
    assert buy["action"] == "BUY"
    assert buy["chamber"] == "House"
    assert buy["amount"] == "≈$32K"  # 32.5 rounds half-to-even
    assert buy["disclosure_date"] == "2026-06-28"


def test_normalize_capitoltrades_ticker_suffix_stripped():
    df = normalize_capitoltrades_rows(CT_ROWS)
    assert "AAPL" in df["ticker"].tolist()  # ":US" stripped
    assert df[df["ticker"] == "AAPL"].iloc[0]["action"] == "SELL"


def test_normalize_capitoltrades_flat_shape_and_null_value():
    df = normalize_capitoltrades_rows(CT_ROWS)
    flat = df[df["politician"] == "Bob Jones"].iloc[0]
    assert flat["ticker"] == "MRCY"
    assert flat["amount"] == ""  # null value → empty, never fake
    assert flat["amount_low"] is None or pd.isna(flat["amount_low"])


def test_normalize_capitoltrades_garbage():
    assert normalize_capitoltrades_rows([]).empty
    assert normalize_capitoltrades_rows([None, "x", 42]).empty


def test_top_purchased_tickers_counts_distinct_politicians():
    df = normalize_capitoltrades_rows(CT_ROWS)
    top = top_purchased_tickers(df)
    assert top.iloc[0]["ticker"] == "MRCY"
    assert top.iloc[0]["politicians"] == 2  # Smith + Jones; AAPL sale excluded
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
