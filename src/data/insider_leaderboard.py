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

SCREENER_URL = "https://openinsider.com/screener"
SCREENER_URL_HTTP = "http://openinsider.com/screener"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://openinsider.com/",
}


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


def fetch_top_insider_buys(
    days: int = 7, min_value_k: int = 100, limit: int = 100
) -> tuple[pd.DataFrame, str | None]:
    """
    Biggest insider purchases filed in the last `days` days, min trade
    value `min_value_k` thousand dollars.
    Returns (df, error_detail); error_detail is None on success and a
    precise diagnostic string on failure so the UI can show the cause.
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

    html = None
    detail = None
    for url in (SCREENER_URL, SCREENER_URL_HTTP):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                detail = f"HTTP {resp.status_code} from {url}: {resp.text[:200]}"
                continue
            html = resp.text
            break
        except Exception as e:
            detail = f"{type(e).__name__} from {url}: {e}"
            continue

    if html is None:
        return pd.DataFrame(), detail or "No response"

    try:
        tables = pd.read_html(io.StringIO(html))
    except Exception as e:
        return pd.DataFrame(), f"HTML parse failed ({type(e).__name__}: {e}); page starts: {html[:150]}"

    for table in tables:
        cols = [re.sub(r"\s+", " ", str(c)).strip() for c in table.columns]
        if "Insider Name" in cols and "Ticker" in cols:
            out = normalize_openinsider_table(table).head(limit)
            if out.empty:
                return out, f"Table found but 0 rows survived normalization (raw rows: {len(table)})"
            return out, None

    first_cols = [str(c) for c in tables[0].columns][:8] if tables else []
    return pd.DataFrame(), f"No screener table among {len(tables)} tables; first table columns: {first_cols}"
