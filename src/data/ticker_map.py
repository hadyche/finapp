"""
Maps company names to stock tickers using SEC's public company registry.

Replaces hand-curated name maps: every U.S. public company (~10,000) is
matchable. Matching is precision-first — a missed match is acceptable,
a wrong ticker is not.
"""

import re
import requests
import pandas as pd

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
HEADERS = {"User-Agent": "finapp-research hadycheh@gmail.com"}

# Legal suffixes stripped (repeatedly) from the end of normalized names
_SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "LLC", "LP", "LLP",
    "LTD", "LIMITED", "CO", "COMPANY", "PLC", "SA", "NV", "AG",
    "HOLDINGS", "HOLDING", "GROUP",
}

_PUNCT_RE = re.compile(r"[^A-Z0-9& ]+")
_WS_RE = re.compile(r"\s+")


def normalize_company_name(name: str) -> str:
    """Uppercase, strip punctuation and trailing legal suffixes."""
    s = str(name).upper()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    if s.startswith("THE "):
        s = s[4:]
    tokens = s.split(" ")
    while len(tokens) > 1 and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def load_sec_company_map() -> pd.DataFrame:
    """
    Fetches SEC's registry of all public companies.
    Returns DataFrame[cik, ticker, title, norm_name]; empty on failure.
    """
    try:
        resp = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"SEC company map fetch error: {e}")
        return pd.DataFrame()

    rows = []
    for entry in data.values():
        ticker = str(entry.get("ticker", "")).strip().upper()
        title = str(entry.get("title", "")).strip()
        if not ticker or not title:
            continue
        rows.append({
            "cik": int(entry.get("cik_str", 0)),
            "ticker": ticker,
            "title": title,
            "norm_name": normalize_company_name(title),
        })
    return pd.DataFrame(rows)


def build_name_index(sec_map: pd.DataFrame) -> dict:
    """
    Builds lookup structures for fast matching:
      exact:    norm_name -> row dict (ambiguous names dropped entirely)
      by_token: first token -> list of row dicts (for prefix matching)
    """
    if sec_map is None or sec_map.empty:
        return {"exact": {}, "by_token": {}}

    exact: dict = {}
    ambiguous: set = set()

    for row in sec_map.itertuples(index=False):
        norm = row.norm_name
        if not norm:
            continue
        entry = {
            "ticker": row.ticker,
            "cik": row.cik,
            "matched_name": row.title,
            "norm_name": norm,
        }
        if norm in exact and exact[norm]["ticker"] != row.ticker:
            # Same normalized name, different tickers → unsafe, drop it
            ambiguous.add(norm)
        else:
            exact[norm] = entry

    # Ambiguous names are excluded from BOTH exact and prefix matching
    by_token: dict = {}
    for norm in ambiguous:
        exact.pop(norm, None)
    for entry in exact.values():
        token = entry["norm_name"].split(" ")[0]
        by_token.setdefault(token, []).append(entry)

    return {"exact": exact, "by_token": by_token}


def match_recipient(recipient: str, index: dict) -> dict | None:
    """
    Matches a contract recipient name to a public company.
    Returns {ticker, cik, matched_name, confidence} or None.

    Strategy (precision over recall):
      1. Exact normalized match             → confidence "exact"
      2. SEC name is a word-boundary prefix of the recipient
         (handles subsidiaries like "LOCKHEED MARTIN AERONAUTICS CO")
                                            → confidence "prefix"
    """
    if not recipient or not index or not index.get("exact"):
        return None

    norm = normalize_company_name(recipient)
    if not norm:
        return None

    hit = index["exact"].get(norm)
    if hit:
        return {**{k: hit[k] for k in ("ticker", "cik", "matched_name")},
                "confidence": "exact"}

    first_token = norm.split(" ")[0]
    best = None
    for entry in index["by_token"].get(first_token, []):
        cand = entry["norm_name"]
        # Prefix matching needs a multi-word SEC name: a single word like
        # "EASTERN" would wrongly claim "EASTERN SHIPBUILDING GROUP".
        # Single-word names can still match, but only exactly (above).
        if " " not in cand:
            continue
        if norm == cand or norm.startswith(cand + " "):
            # prefer the longest matching SEC name
            if best is None or len(cand) > len(best["norm_name"]):
                best = entry
    if best:
        return {**{k: best[k] for k in ("ticker", "cik", "matched_name")},
                "confidence": "prefix"}
    return None


def cik_to_ticker(cik: int, sec_map: pd.DataFrame) -> str | None:
    """Resolves an SEC CIK number to its primary ticker."""
    if sec_map is None or sec_map.empty:
        return None
    hits = sec_map[sec_map["cik"] == int(cik)]
    if hits.empty:
        return None
    return str(hits.iloc[0]["ticker"])


def ticker_to_cik(ticker: str, sec_map: pd.DataFrame) -> int | None:
    """Resolves a ticker to its SEC CIK number."""
    if sec_map is None or sec_map.empty or not ticker:
        return None
    hits = sec_map[sec_map["ticker"] == str(ticker).upper()]
    if hits.empty:
        return None
    return int(hits.iloc[0]["cik"])
