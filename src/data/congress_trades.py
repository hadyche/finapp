"""
Stock trades disclosed by members of Congress under the STOCK Act.

Sources: the Senate/House Stock Watcher community datasets, which mirror
the official disclosure filings (efdsearch.senate.gov and
disclosures-clerk.house.gov) as clean JSON. Members may disclose up to
45 days after trading — the disclosure date is shown so the lag is
always visible.
"""

import re
import requests
import pandas as pd
from datetime import datetime, timedelta

HOUSE_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
HEADERS = {"User-Agent": "finapp-research hadycheh@gmail.com"}

_TICKER_RE = re.compile(r"^[A-Z]{1,5}([.\-][A-Z])?$")


def _parse_date(s) -> str | None:
    """Normalizes '2021-09-27' or '09/27/2021' to ISO. None if unparseable."""
    s = str(s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_amount_range(s) -> tuple[float | None, float | None]:
    """'$1,001 - $15,000' → (1001.0, 15000.0). (None, None) if unparseable."""
    nums = re.findall(r"\$([\d,]+)", str(s or ""))
    if not nums:
        return None, None
    vals = [float(n.replace(",", "")) for n in nums]
    low = vals[0]
    high = vals[1] if len(vals) > 1 else vals[0]
    return low, high


def _clean_ticker(t) -> str | None:
    t = str(t or "").strip().upper()
    return t if _TICKER_RE.match(t) else None


def _norm_action(raw: str) -> str:
    r = str(raw or "").strip().lower()
    if "purchase" in r:
        return "BUY"
    if "sale" in r or "sold" in r:
        return "SELL"
    if "exchange" in r:
        return "EXCHANGE"
    return "OTHER"


def normalize_congress_rows(rows: list[dict], chamber: str) -> pd.DataFrame:
    """
    Normalizes House or Senate Stock Watcher rows to one schema:
    [politician, chamber, ticker, action, amount, amount_low,
     transaction_date, disclosure_date]. Pure logic — unit-testable.
    """
    out = []
    for r in rows or []:
        ticker = _clean_ticker(r.get("ticker"))
        if not ticker:
            continue
        politician = str(r.get("representative") or r.get("senator") or "").strip()
        politician = re.sub(r"^(Hon\.|Mr\.|Ms\.|Mrs\.)\s+", "", politician)
        if not politician:
            continue
        low, _high = parse_amount_range(r.get("amount"))
        out.append({
            "politician": politician,
            "chamber": chamber,
            "ticker": ticker,
            "action": _norm_action(r.get("type")),
            "amount": str(r.get("amount") or "").strip(),
            "amount_low": low,
            "transaction_date": _parse_date(r.get("transaction_date")),
            "disclosure_date": _parse_date(r.get("disclosure_date")),
        })
    return pd.DataFrame(out)


def fetch_congress_trades(days_back: int = 90) -> tuple[pd.DataFrame, str | None]:
    """
    Recent Congress trades from both chambers, newest disclosures first.
    Returns (trades_in_window, newest_disclosure_in_full_dataset) so the
    UI can distinguish 'feed failed' from 'dataset has nothing recent'.
    (empty DataFrame, None) on total failure.
    """
    frames = []
    for url, chamber in ((HOUSE_URL, "House"), (SENATE_URL, "Senate")):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=45)
            resp.raise_for_status()
            frames.append(normalize_congress_rows(resp.json(), chamber))
        except Exception as e:
            print(f"Congress trades fetch error ({chamber}): {e}")

    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(), None

    df = pd.concat(frames, ignore_index=True)
    latest = df["disclosure_date"].dropna().max()
    cutoff = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    df = df[df["disclosure_date"].notna() & (df["disclosure_date"] >= cutoff)]
    return (
        df.sort_values("disclosure_date", ascending=False).reset_index(drop=True),
        latest,
    )


def top_purchased_tickers(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Tickers most bought across Congress in the window."""
    if df is None or df.empty:
        return pd.DataFrame()
    buys = df[df["action"] == "BUY"]
    if buys.empty:
        return pd.DataFrame()
    return (
        buys.groupby("ticker")
        .agg(politicians=("politician", "nunique"), trades=("ticker", "count"))
        .reset_index()
        .sort_values(["politicians", "trades"], ascending=False)
        .head(top_n)
    )
