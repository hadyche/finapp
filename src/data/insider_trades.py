"""
Insider open-market purchases from SEC Form 4 filings.

Officers and directors buying their own company's stock with their own
money (transaction code "P") is the strongest free signal for small caps —
especially right after a big contract award.

Scoped as a confirmation layer: we check the specific companies already
in the signals feed, not the whole market, keeping EDGAR traffic tiny.
"""

import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "finapp-research hadycheh@gmail.com"}
EDGAR_ARCHIVE = "https://www.sec.gov/Archives/edgar/data"


def parse_form4_xml(content: str) -> list[dict]:
    """
    Extracts open-market purchases (code P, acquired) from a Form 4 XML.
    Pure string → list logic, unit-testable offline.
    Returns [{owner, date, shares, price, value}, ...]
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    owners = [
        (o.findtext("reportingOwnerId/rptOwnerName") or "").strip()
        for o in root.iter("reportingOwner")
    ]
    owner = owners[0] if owners else ""

    buys = []
    for txn in root.iter("nonDerivativeTransaction"):
        code = (txn.findtext("transactionCoding/transactionCode") or "").strip()
        acq = (txn.findtext(
            "transactionAmounts/transactionAcquiredDisposedCode/value") or "").strip()
        if code != "P" or acq != "A":
            continue
        date = (txn.findtext("transactionDate/value") or "").strip()
        try:
            shares = float(txn.findtext("transactionAmounts/transactionShares/value") or 0)
        except ValueError:
            shares = 0.0
        try:
            price = float(txn.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            price = 0.0
        if shares <= 0:
            continue
        buys.append({
            "owner": owner,
            "date": date,
            "shares": shares,
            "price": price,
            "value": shares * price,
        })
    return buys


def _recent_form4_docs(cik: int, days_back: int, max_filings: int) -> list[str]:
    """URLs of this issuer's most recent Form 4 primary documents."""
    url = f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        recent = resp.json().get("filings", {}).get("recent", {})
    except Exception as e:
        print(f"EDGAR submissions error CIK {cik}: {e}")
        return []

    cutoff = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    docs = []
    for form, acc, fdate, doc in zip(
        recent.get("form", []),
        recent.get("accessionNumber", []),
        recent.get("filingDate", []),
        recent.get("primaryDocument", []),
    ):
        if form != "4" or fdate < cutoff or not doc:
            continue
        acc_clean = acc.replace("-", "")
        # primaryDocument may carry a viewer prefix like "xslF345X05/x.xml"
        doc = doc.split("/")[-1]
        docs.append(f"{EDGAR_ARCHIVE}/{int(cik)}/{acc_clean}/{doc}")
        if len(docs) >= max_filings:
            break
    return docs


def insider_buys_for_cik(cik: int, days_back: int = 90, max_filings: int = 6) -> dict | None:
    """
    Summary of recent open-market insider buys for one company.
    Returns {n_buys, n_insiders, total_usd, last_date} or None if no buys
    were found (which also covers EDGAR being unreachable).
    """
    all_buys = []
    for url in _recent_form4_docs(cik, days_back, max_filings):
        time.sleep(0.15)  # SEC rate-limit politeness
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            all_buys.extend(parse_form4_xml(resp.text))
        except Exception as e:
            print(f"Form 4 fetch error {url}: {e}")

    if not all_buys:
        return None
    return {
        "n_buys": len(all_buys),
        "n_insiders": len({b["owner"] for b in all_buys if b["owner"]}),
        "total_usd": sum(b["value"] for b in all_buys),
        "last_date": max(b["date"] for b in all_buys if b["date"]) if any(b["date"] for b in all_buys) else "",
    }
