"""
Stock trades disclosed by members of Congress under the STOCK Act.

Source: CapitolTrades' public trade feed (aggregates the official
efdsearch.senate.gov and disclosures-clerk.house.gov filings). The
previous source (Stock Watcher S3 datasets) was shut down — AWS now
returns AccessDenied for those buckets.

Members may disclose up to 45 days after trading — the disclosure date
is shown so the lag is always visible.
"""

import re
import requests
import pandas as pd
from datetime import datetime, timedelta

CAPITOLTRADES_URL = "https://bff.capitoltrades.com/trades"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.capitoltrades.com",
    "Referer": "https://www.capitoltrades.com/",
}

_TICKER_RE = re.compile(r"^[A-Z]{1,5}([.\-][A-Z])?$")


def _clean_ticker(t) -> str | None:
    t = str(t or "").strip().upper()
    t = t.split(":")[0]  # CapitolTrades uses "AAPL:US"
    return t if _TICKER_RE.match(t) else None


def _iso_date(s) -> str | None:
    s = str(s or "").strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fmt_value(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v <= 0:
        return ""
    if v >= 1e6:
        return f"≈${v/1e6:.1f}M"
    if v >= 1e3:
        return f"≈${v/1e3:.0f}K"
    return f"≈${v:.0f}"


def _norm_action(raw) -> str:
    r = str(raw or "").strip().lower()
    if "buy" in r or "purchase" in r:
        return "BUY"
    if "sell" in r or "sale" in r:
        return "SELL"
    if "exchange" in r:
        return "EXCHANGE"
    return "OTHER"


def normalize_capitoltrades_rows(rows: list[dict]) -> pd.DataFrame:
    """
    Normalizes CapitolTrades trade items to the app schema:
    [politician, chamber, ticker, action, amount, amount_low,
     transaction_date, disclosure_date].
    Tolerates schema variation (embedded politician/asset objects or
    flat ids) — unparseable rows are skipped, never guessed.
    Pure logic — unit-testable.
    """
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue

        asset = r.get("asset") if isinstance(r.get("asset"), dict) else {}
        ticker = _clean_ticker(
            asset.get("assetTicker") or r.get("assetTicker") or r.get("ticker")
        )
        if not ticker:
            continue

        pol = r.get("politician") if isinstance(r.get("politician"), dict) else {}
        name = str(
            pol.get("fullName")
            or " ".join(x for x in (pol.get("firstName"), pol.get("lastName")) if x)
            or r.get("politicianName")
            or ""
        ).strip()
        if not name:
            continue

        chamber = str(pol.get("chamber") or r.get("chamber") or "").strip().title()
        if chamber not in ("House", "Senate"):
            chamber = "—"

        try:
            value = float(r.get("value")) if r.get("value") is not None else None
        except (TypeError, ValueError):
            value = None

        out.append({
            "politician": name,
            "chamber": chamber,
            "ticker": ticker,
            "action": _norm_action(r.get("txType") or r.get("type")),
            "amount": _fmt_value(value),
            "amount_low": value,
            "transaction_date": _iso_date(r.get("txDate") or r.get("transactionDate")),
            "disclosure_date": _iso_date(r.get("pubDate") or r.get("disclosureDate")),
        })
    return pd.DataFrame(out)


def recent_and_latest(df: pd.DataFrame, days_back: int) -> tuple[pd.DataFrame, str | None]:
    """
    Splits a normalized trades frame into (rows disclosed in the window,
    newest disclosure date in the full frame). Comparison happens on
    plain Python values — vectorized string comparisons on columns with
    missing values raise under PyArrow-backed pandas. Pure, testable.
    """
    if df is None or df.empty:
        return pd.DataFrame(), None
    dates = [v for v in df["disclosure_date"].tolist() if isinstance(v, str) and v]
    latest = max(dates) if dates else None
    cutoff = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    keep = df["disclosure_date"].map(lambda v: isinstance(v, str) and v >= cutoff)
    out = df[keep.astype(bool)]
    return (
        out.sort_values("disclosure_date", ascending=False).reset_index(drop=True),
        latest,
    )


def fetch_congress_trades(
    days_back: int = 90, max_pages: int = 8
) -> tuple[pd.DataFrame, str | None, str | None]:
    """
    Recent Congress trades, newest disclosures first.
    Returns (trades_in_window, newest_disclosure_seen, error_detail).
    error_detail is None on success; on failure it carries a diagnostic
    string (HTTP status, exception, or schema info) so the UI can show
    exactly what went wrong instead of a generic banner.
    """
    cutoff = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    frames = []
    detail = None
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(
                CAPITOLTRADES_URL,
                params={"page": page, "pageSize": 96},
                headers=HEADERS,
                timeout=30,
            )
            if resp.status_code != 200:
                detail = f"HTTP {resp.status_code} from {CAPITOLTRADES_URL} (page {page}): {resp.text[:200]}"
                break
            body = resp.json()
            batch = body.get("data", [])
        except Exception as e:
            detail = f"{type(e).__name__} on page {page}: {e}"
            break

        if not batch:
            if page == 1:
                keys = sorted(body.keys()) if isinstance(body, dict) else type(body).__name__
                detail = f"Empty 'data' in response; top-level keys: {keys}"
            break

        df = normalize_capitoltrades_rows(batch)
        if df.empty and page == 1:
            sample = sorted(batch[0].keys()) if isinstance(batch[0], dict) else type(batch[0]).__name__
            detail = f"Parsed 0/{len(batch)} items — schema mismatch. First item keys: {sample}"
            break
        frames.append(df)

        # Feed is newest-first: stop paging once past the window
        page_dates = [v for v in df["disclosure_date"].tolist() if isinstance(v, str)] if not df.empty else []
        if page_dates and max(page_dates) < cutoff:
            break

    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(), None, detail or "No data returned"

    recent, latest = recent_and_latest(pd.concat(frames, ignore_index=True), days_back)
    return recent, latest, None


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
