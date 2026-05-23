"""
Fetches 13F institutional holding data from SEC EDGAR public API.
Tracks quarter-over-quarter position changes for large institutions.
"""

import requests
import pandas as pd
from functools import lru_cache

EDGAR_BASE = "https://data.sec.gov/submissions"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {"User-Agent": "finapp-research hadycheh@gmail.com"}

# CIK numbers for major institutional filers
INSTITUTIONS = {
    "BlackRock": "0001364742",
    "Vanguard": "0000102909",
    "State Street": "0000093751",
    "Berkshire Hathaway": "0001067983",
    "Citadel": "0001423298",
}


@lru_cache(maxsize=16)
def _get_filings_for_cik(cik: str) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"EDGAR fetch error for CIK {cik}: {e}")
        return {}


def get_recent_13f_filings(institution: str, limit: int = 4) -> pd.DataFrame:
    """Returns the most recent 13F filings for a given institution."""
    cik = INSTITUTIONS.get(institution)
    if not cik:
        return pd.DataFrame()

    data = _get_filings_for_cik(cik)
    if not data:
        return pd.DataFrame()

    filings = data.get("filings", {}).get("recent", {})
    if not filings:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "form": filings.get("form", []),
            "filed_date": filings.get("filingDate", []),
            "accession": filings.get("accessionNumber", []),
            "report_date": filings.get("reportDate", []),
        }
    )

    df_13f = df[df["form"].str.startswith("13F")].head(limit).copy()
    df_13f["institution"] = institution
    df_13f["cik"] = cik
    return df_13f


def get_all_institutions_filings() -> pd.DataFrame:
    """Aggregates recent 13F filing metadata for all tracked institutions."""
    frames = [get_recent_13f_filings(name) for name in INSTITUTIONS]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def search_13f_holdings(institution: str) -> pd.DataFrame:
    """
    Uses EDGAR full-text search to find 13F-HR documents and returns
    a summary of what's available. Actual holdings parsing requires
    XML processing of the primary document.
    """
    cik = INSTITUTIONS.get(institution)
    if not cik:
        return pd.DataFrame()

    search_url = "https://efts.sec.gov/LATEST/search-index?q=%2213F%22&dateRange=custom&startdt=2024-01-01&forms=13F-HR"
    params = {
        "q": "13F-HR",
        "dateRange": "custom",
        "startdt": "2024-01-01",
        "forms": "13F-HR",
        "entity": institution,
    }
    try:
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers=HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
    except Exception as e:
        print(f"EDGAR search error: {e}")
        return pd.DataFrame()

    rows = []
    for hit in hits[:10]:
        src = hit.get("_source", {})
        rows.append(
            {
                "institution": institution,
                "filed_date": src.get("file_date"),
                "period": src.get("period_of_report"),
                "form": src.get("form_type"),
                "entity": src.get("entity_name"),
            }
        )
    return pd.DataFrame(rows)


def get_institution_filing_summary() -> pd.DataFrame:
    """Returns a simple summary table of all institutions and latest 13F dates."""
    rows = []
    for name in INSTITUTIONS:
        df = get_recent_13f_filings(name, limit=1)
        if df.empty:
            rows.append({"institution": name, "latest_13f": "N/A", "filed_date": "N/A"})
        else:
            rows.append(
                {
                    "institution": name,
                    "latest_13f": df.iloc[0]["report_date"],
                    "filed_date": df.iloc[0]["filed_date"],
                    "accession": df.iloc[0]["accession"],
                }
            )
    return pd.DataFrame(rows)
