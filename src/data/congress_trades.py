"""
Stock trades disclosed by U.S. Senators under the STOCK Act, fetched
directly from the official source: efdsearch.senate.gov (eFD).

History: two aggregator sources died first — the Stock Watcher S3
buckets were shut down (AccessDenied) and CapitolTrades' CDN blocks
datacenter traffic (503). The official government site is the one
source that can't be discontinued or paywalled.

Coverage is Senate-only for now: the House publishes PTRs as PDFs,
which need a separate parsing effort.
"""

import io
import re
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

EFD_BASE = "https://efdsearch.senate.gov"
EFD_HOME = f"{EFD_BASE}/search/home/"
EFD_DATA = f"{EFD_BASE}/search/report/data/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

_TICKER_RE = re.compile(r"^[A-Z]{1,5}([.\-][A-Z])?$")
_PTR_HREF_RE = re.compile(r'href="(/search/view/ptr/[^"]+)"')


def _clean_ticker(t) -> str | None:
    t = str(t or "").strip().upper()
    return t if _TICKER_RE.match(t) else None


def parse_amount_range(s) -> tuple[float | None, float | None]:
    """'$1,001 - $15,000' → (1001.0, 15000.0). (None, None) if unparseable."""
    nums = re.findall(r"\$([\d,]+)", str(s or ""))
    if not nums:
        return None, None
    vals = [float(n.replace(",", "")) for n in nums]
    low = vals[0]
    high = vals[1] if len(vals) > 1 else vals[0]
    return low, high


def _iso_date(s) -> str | None:
    s = str(s or "").strip()[:10]
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _norm_action(raw) -> str:
    r = str(raw or "").strip().lower()
    if "purchase" in r or "buy" in r:
        return "BUY"
    if "sale" in r or "sell" in r:
        return "SELL"
    if "exchange" in r:
        return "EXCHANGE"
    return "OTHER"


def records_to_trades(records: list[dict], senator: str, disclosure_date: str | None) -> pd.DataFrame:
    """
    Converts rows of a Senate PTR table (dicts keyed by the eFD column
    names: 'Transaction Date', 'Ticker', 'Asset Type', 'Type', 'Amount')
    into the app schema. Non-stock assets and blank tickers are skipped.
    Pure logic — unit-testable.
    """
    out = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        asset_type = str(r.get("Asset Type") or "").strip().lower()
        if asset_type and "stock" not in asset_type:
            continue
        ticker = _clean_ticker(r.get("Ticker"))
        if not ticker:
            continue
        amount = str(r.get("Amount") or "").strip()
        low, _ = parse_amount_range(amount)
        out.append({
            "politician": str(senator).strip(),
            "chamber": "Senate",
            "ticker": ticker,
            "action": _norm_action(r.get("Type")),
            "amount": amount,
            "amount_low": low,
            "transaction_date": _iso_date(r.get("Transaction Date")),
            "disclosure_date": disclosure_date,
        })
    return pd.DataFrame(out)


def _efd_session() -> tuple[requests.Session | None, str | None]:
    """Opens an eFD session by accepting the usage agreement."""
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        home = s.get(EFD_HOME, timeout=20)
        home.raise_for_status()
        token = s.cookies.get("csrftoken", "")
        if not token:
            m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', home.text)
            token = m.group(1) if m else ""
        if not token:
            return None, "No CSRF token on eFD home page"
        resp = s.post(
            EFD_HOME,
            data={"prohibition_agreement": "1", "csrfmiddlewaretoken": token},
            headers={"Referer": EFD_HOME},
            timeout=20,
        )
        if resp.status_code != 200:
            return None, f"Agreement POST returned HTTP {resp.status_code}"
        return s, None
    except Exception as e:
        return None, f"eFD session error: {type(e).__name__}: {e}"


def _recent_ptr_reports(s: requests.Session, days_back: int) -> tuple[list[dict], str | None]:
    """Lists recent electronic Periodic Transaction Reports."""
    token = s.cookies.get("csrftoken", "")
    start = (datetime.today() - timedelta(days=days_back)).strftime("%m/%d/%Y") + " 00:00:00"
    payload = {
        "start": "0",
        "length": "100",
        "report_types": "[11]",   # 11 = Periodic Transaction Report
        "filer_types": "[]",
        "submitted_start_date": start,
        "submitted_end_date": "",
        "candidate_state": "",
        "senator_state": "",
        "office_id": "",
        "first_name": "",
        "last_name": "",
        "csrfmiddlewaretoken": token,
    }
    try:
        resp = s.post(
            EFD_DATA,
            data=payload,
            headers={"Referer": EFD_HOME, "X-CSRFToken": token},
            timeout=30,
        )
        if resp.status_code != 200:
            return [], f"Report list returned HTTP {resp.status_code}: {resp.text[:200]}"
        rows = resp.json().get("data", [])
    except Exception as e:
        return [], f"Report list error: {type(e).__name__}: {e}"

    reports = []
    for row in rows:
        try:
            first, last, _office, link_html, received = row[0], row[1], row[2], row[3], row[4]
        except (IndexError, TypeError):
            continue
        m = _PTR_HREF_RE.search(str(link_html))
        if not m:
            continue  # paper filings (scanned images) can't be parsed
        reports.append({
            "senator": f"{str(first).strip().title()} {str(last).strip().title()}",
            "url": EFD_BASE + m.group(1),
            "disclosure_date": _iso_date(received),
        })
    return reports, None


def _parse_ptr_page(html: str) -> list[dict]:
    """Extracts transaction rows from a PTR detail page."""
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return []
    for table in tables:
        cols = [str(c).strip() for c in table.columns]
        if "Transaction Date" in cols and "Ticker" in cols:
            return table.to_dict("records")
    return []


def fetch_congress_trades(
    days_back: int = 90, max_reports: int = 30
) -> tuple[pd.DataFrame, str | None, str | None]:
    """
    Recent Senate trades from the official eFD site, newest first.
    Returns (trades_in_window, newest_disclosure_seen, error_detail).
    error_detail is None on success.
    """
    s, err = _efd_session()
    if s is None:
        return pd.DataFrame(), None, err

    reports, err = _recent_ptr_reports(s, days_back)
    if err:
        return pd.DataFrame(), None, err
    if not reports:
        return pd.DataFrame(), None, None  # genuinely nothing filed in window

    latest = max((r["disclosure_date"] for r in reports if r["disclosure_date"]), default=None)

    frames = []
    for rep in reports[:max_reports]:
        time.sleep(0.2)  # be polite to the government server
        try:
            page = s.get(rep["url"], headers={"Referer": EFD_HOME}, timeout=20)
            if page.status_code != 200:
                continue
            records = _parse_ptr_page(page.text)
        except Exception as e:
            print(f"PTR fetch error {rep['url']}: {e}")
            continue
        df = records_to_trades(records, rep["senator"], rep["disclosure_date"])
        if not df.empty:
            frames.append(df)

    if not frames:
        # Reports existed but none parsed — surface that distinctly
        return pd.DataFrame(), latest, None

    recent, _ = recent_and_latest(pd.concat(frames, ignore_index=True), days_back)
    return recent, latest, None


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


def top_purchased_tickers(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Tickers most bought across the Senate in the window."""
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
