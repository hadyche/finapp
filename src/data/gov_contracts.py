"""
Fetches federal contract award data from USAspending.gov public API.
No demo fallbacks: on failure, callers receive an empty DataFrame and
must surface the error to the user.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta

from src.data.ticker_map import match_recipient, normalize_company_name

USASPENDING_BASE = "https://api.usaspending.gov/api/v2"

SECTOR_MAP = {
    "11": "Agriculture",
    "21": "Mining & Energy",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",
    "32": "Manufacturing",
    "33": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade",
    "45": "Retail Trade",
    "48": "Transportation",
    "49": "Transportation",
    "51": "Information Technology",
    "52": "Finance & Insurance",
    "53": "Real Estate",
    "54": "Professional Services",
    "55": "Management",
    "56": "Admin & Support",
    "61": "Education",
    "62": "Healthcare",
    "71": "Arts & Entertainment",
    "72": "Hospitality",
    "81": "Other Services",
    "92": "Defense & Public Admin",
}


def _naics_to_sector(naics) -> str:
    try:
        s = str(naics).strip()
        if not s or s in ("nan", "None", "<NA>", "") or len(s) < 2:
            return "Other"
        return SECTOR_MAP.get(s[:2], "Other")
    except Exception:
        return "Other"


def _award_payload(start_date, end_date, min_amount, page_size, page, new_awards_only):
    time_period = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }
    if new_awards_only:
        # Only contracts SIGNED in the window — without this, USAspending
        # returns decade-old contracts that merely had a recent modification,
        # with lifetime totals masquerading as fresh money.
        time_period["date_type"] = "new_awards_only"
    return {
        "filters": {
            "time_period": [time_period],
            "award_type_codes": ["A", "B", "C", "D"],  # contracts only
            "award_amounts": [{"lower_bound": min_amount}],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Start Date",
            "Award Type",
            "Awarding Agency",
            "NAICS Code",
            "NAICS Description",
        ],
        "sort": "Award Amount",
        "order": "desc",
        "limit": page_size,
        "page": page,
    }


def fetch_recent_awards(
    days_back: int = 30,
    limit: int = 500,
    min_amount: float = 5_000_000,
    new_awards_only: bool = True,
) -> pd.DataFrame:
    """
    Contract awards newly signed in the window, paginated up to `limit`
    rows, prefiltered server-side to >= min_amount. Empty DataFrame on
    failure.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days_back)
    page_size = 100

    results: list[dict] = []
    page = 1
    while len(results) < limit:
        payload = _award_payload(start_date, end_date, min_amount,
                                 page_size, page, new_awards_only)
        try:
            resp = requests.post(
                f"{USASPENDING_BASE}/search/spending_by_award/",
                json=payload,
                timeout=30,
            )
            if resp.status_code == 400 and new_awards_only and page == 1:
                # Older API revision rejects the date_type — degrade once
                new_awards_only = False
                continue
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:
            print(f"USAspending fetch error (page {page}): {e}")
            break

        batch = body.get("results", [])
        if not batch:
            break
        results.extend(batch)
        if not body.get("page_metadata", {}).get("hasNext", False):
            break
        page += 1

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results[:limit])
    df.rename(
        columns={
            "Award ID": "award_id",
            "Recipient Name": "recipient",
            "Award Amount": "amount",
            "Start Date": "date",
            "Award Type": "award_type",
            "Awarding Agency": "agency",
            "NAICS Code": "naics_code",
            "NAICS Description": "naics_desc",
        },
        inplace=True,
    )
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["sector"] = df["naics_code"].fillna("").astype(str).apply(_naics_to_sector)
    return df


def match_awards_to_tickers(awards: pd.DataFrame, name_index: dict) -> pd.DataFrame:
    """
    Adds ticker/matched_name/confidence columns by matching each unique
    recipient against the SEC company registry. Unmatched rows keep
    ticker=None so callers can inspect what was skipped.
    """
    if awards is None or awards.empty:
        return awards

    df = awards.copy()
    unique = df["recipient"].dropna().unique()
    lookup = {}
    for name in unique:
        hit = match_recipient(str(name), name_index)
        lookup[name] = hit

    df["ticker"] = df["recipient"].map(lambda r: (lookup.get(r) or {}).get("ticker"))
    df["matched_name"] = df["recipient"].map(lambda r: (lookup.get(r) or {}).get("matched_name"))
    df["confidence"] = df["recipient"].map(lambda r: (lookup.get(r) or {}).get("confidence"))
    return df


def contracts_for_ticker(
    ticker: str,
    name_index: dict,
    days_back: int = 365,
) -> pd.DataFrame:
    """All recent awards whose recipient matches this ticker's company."""
    df = fetch_recent_awards(days_back=days_back, limit=1000, min_amount=1_000_000)
    if df.empty:
        return pd.DataFrame()
    matched = match_awards_to_tickers(df, name_index)
    hits = matched[matched["ticker"] == ticker.upper()]
    return hits.sort_values("amount", ascending=False).reset_index(drop=True)


def fed_dollar_summary(ticker: str, name_index: dict, days_back: int = 365) -> dict:
    """Total $, contract count, and agency breakdown for a ticker."""
    df = contracts_for_ticker(ticker, name_index, days_back=days_back)
    if df.empty:
        return {"total": 0, "count": 0, "agencies": pd.DataFrame(), "contracts": df}

    agencies = (
        df.groupby("agency")
        .agg(total=("amount", "sum"), count=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
    )
    return {
        "total": float(df["amount"].sum()),
        "count": len(df),
        "agencies": agencies,
        "contracts": df,
    }
