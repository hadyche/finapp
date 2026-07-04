"""
Market-wide leaderboard of the biggest open-market insider BUYS.

Source: OpenInsider's screener (a free view over SEC Form 4 filings).
Only purchases (transaction code P) — insider sales are routine and
carry no signal. Fails to an empty DataFrame, never fake rows.
"""

import io
import re
import requests
import pandas as pd

SCREENER_URL = "http://openinsider.com/screener"
HEADERS = {"User-Agent": "Mozilla/5.0 (finapp-research hadycheh@gmail.com)"}


def parse_money(s) -> float | None:
    """'+$1,234,567' / '$12.50' → float. None if unparseable."""
    m = re.search(r"-?\$?([\d,]+(?:\.\d+)?)", str(s or "").replace("+", ""))
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
        return -v if str(s).strip().startswith("-") else v
    except ValueError:
        return None


def normalize_openinsider_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes the raw screener HTML table to
    [filing_date, trade_date, ticker, company, insider, title, price,
     qty, value], biggest value first. Pure logic — unit-testable.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    colmap = {
        "Filing Date": "filing_date",
        "Trade Date": "trade_date",
        "Ticker": "ticker",
        "Company Name": "company",
        "Insider Name": "insider",
        "Title": "title",
        "Trade Type": "trade_type",
        "Price": "price",
        "Qty": "qty",
        "Value": "value",
    }
    missing = [c for c in ("Ticker", "Insider Name", "Value") if c not in df.columns]
    if missing:
        return pd.DataFrame()
    df = df.rename(columns=colmap)

    if "trade_type" in df.columns:
        df = df[df["trade_type"].astype(str).str.contains("P - Purchase", na=False)]

    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df = df[df["ticker"].str.match(r"^[A-Z]{1,5}([.\-][A-Z])?$", na=False)]
    df["value"] = df["value"].map(parse_money)
    df["price"] = df.get("price", pd.Series(dtype=object)).map(parse_money)
    df["qty"] = df.get("qty", pd.Series(dtype=object)).map(parse_money)
    df = df[df["value"].notna() & (df["value"] > 0)]
    if df.empty:
        return pd.DataFrame()

    keep = ["filing_date", "trade_date", "ticker", "company", "insider",
            "title", "price", "qty", "value"]
    for k in keep:
        if k not in df.columns:
            df[k] = None
    df["filing_date"] = df["filing_date"].astype(str).str.slice(0, 10)
    df["trade_date"] = df["trade_date"].astype(str).str.slice(0, 10)
    return (
        df[keep]
        .sort_values("value", ascending=False)
        .reset_index(drop=True)
    )


def fetch_top_insider_buys(days: int = 7, min_value_k: int = 100, limit: int = 100) -> pd.DataFrame:
    """
    Biggest insider purchases filed in the last `days` days, min trade
    value `min_value_k` thousand dollars. Empty DataFrame on failure.
    """
    params = {
        "xp": 1,                 # purchases only
        "fd": days,              # filing date within N days
        "td": 0,                 # any trade date
        "vl": min_value_k,       # min value, $ thousands
        "cnt": 1000,             # fetch wide, rank locally
        "page": 1,
        "sic1": -1, "sicl": 100, "sich": 9999,
    }
    try:
        resp = requests.get(SCREENER_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
    except Exception as e:
        print(f"OpenInsider fetch error: {e}")
        return pd.DataFrame()

    for table in tables:
        cols = [re.sub(r"\s+", " ", str(c)).strip() for c in table.columns]
        if "Insider Name" in cols and "Ticker" in cols:
            return normalize_openinsider_table(table).head(limit)
    return pd.DataFrame()
