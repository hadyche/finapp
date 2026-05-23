"""
Parses actual 13F-HR XML infotable filings from SEC EDGAR.
Tracks quarter-over-quarter position changes for BlackRock, Vanguard, State Street.

13F XML format:
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>20483091</value>           # in thousands USD
    <shrsOrPrnAmt><sshPrnamt>108204</sshPrnamt></shrsOrPrnAmt>
  </infoTable>
"""

import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
from functools import lru_cache

HEADERS = {"User-Agent": "finapp-research hadycheh@gmail.com"}
EDGAR_ARCHIVE = "https://www.sec.gov/Archives/edgar/data"

# CIK → institution name
INSTITUTIONS = {
    "BlackRock":        "0001364742",
    "Vanguard":         "0000102909",
    "State Street":     "0000093751",
}

# CUSIP → ticker (top ~150 holdings of index funds + defense stocks)
CUSIP_TO_TICKER = {
    "037833100": "AAPL",   "594918104": "MSFT",   "023135106": "AMZN",
    "67066G104": "NVDA",   "02079K305": "GOOGL",  "30303M102": "META",
    "92826C839": "TSLA",   "46090E103": "IVZ",    "922908363": "VZ",
    "931142103": "WMT",    "742718109": "PG",     "478160104": "JNJ",
    "172967424": "BRK.B",  "46625H100": "JPM",    "857477103": "TGT",
    "808513105": "SCHW",   "191216100": "KO",     "723254990": "MRK",
    "585055106": "MCD",    "718172109": "PM",     "14272462":  "V",
    "931142103": "WMT",    "037833100": "AAPL",   "88160R101": "TSLA",
    "097023105": "BA",     "526057104": "LMT",    "020286104": "RTX",
    "667491104": "NOC",    "369550108": "GD",     "502413107": "LHX",
    "525327102": "LDOS",   "099614101": "BAH",    "78376A102": "SAIC",
    "44107P104": "HII",    "872589104": "TDG",    "101137107": "BWA",
    "254687106": "DIS",    "29364G103": "ENTG",   "531229854": "LIN",
    "67103H107": "ORCL",   "11135F101": "AVGO",   "46625H100": "JPM",
    "38141G104": "GS",     "073902108": "BAC",    "172967424": "BRK.B",
    "459200101": "IBM",    "345370860": "INTC",   "912093108": "UAL",
    "883556102": "TGT",    "166764100": "CHTR",   "458140100": "ISRG",
    "032654105": "ABBV",   "00287Y109": "ABBV",   "589331107": "MET",
    "260003108": "DVN",    "803649107": "SLB",    "044209104": "APA",
    "278768106": "ELV",    "423074703": "HCA",    "191791104": "CVS",
    "577081102": "MOH",    "716791108": "PFE",    "91324P102": "UNH",
    "742718109": "PG",     "428236103": "HON",    "110122108": "CAT",
    "66987V109": "PCAR",   "012653101": "ALB",    "747525103": "QCOM",
    "45866F104": "INTU",   "09857L108": "BKNG",   "742460009": "NOW",
    "023586100": "AMD",    "404121106": "HAL",    "872589104": "TDG",
    "913017109": "URI",    "92220P105": "VLO",    "867840105": "SWN",
    "693475105": "PNC",    "949746101": "WFC",    "02562E104": "AXP",
    "345370860": "INTC",   "594918104": "MSFT",   "02079K107": "GOOG",
    "717081103": "PHM",    "126650100": "CVX",    "08243Q100": "BLK",
    "22160K105": "COST",   "984121103": "XOM",    "713448108": "PLTR",
}

# Realistic demo holdings for when EDGAR is unreachable
DEMO_HOLDINGS = {
    "BlackRock": [
        ("AAPL", "Apple Inc",           245_800_000, 238_200_000, 1_420_000, 1_380_000),
        ("MSFT", "Microsoft Corp",      198_400_000, 190_100_000, 740_000,   712_000),
        ("NVDA", "Nvidia Corp",         187_200_000, 142_600_000, 1_920_000, 1_460_000),
        ("AMZN", "Amazon.com Inc",      162_300_000, 158_700_000, 880_000,   860_000),
        ("META", "Meta Platforms",       98_400_000,  82_100_000, 240_000,   202_000),
        ("GOOGL","Alphabet Inc",         94_200_000,  96_800_000, 620_000,   640_000),
        ("LMT",  "Lockheed Martin",      18_400_000,  14_200_000,  42_000,    32_000),
        ("RTX",  "RTX Corp",             16_800_000,  14_600_000, 180_000,   160_000),
        ("NOC",  "Northrop Grumman",     12_200_000,   9_800_000,  29_000,    23_000),
        ("BA",   "Boeing Co",            11_400_000,  13_200_000, 102_000,   118_000),
        ("GD",   "General Dynamics",      9_800_000,   8_100_000,  41_000,    34_000),
        ("UNH",  "UnitedHealth Group",   44_200_000,  42_800_000, 100_000,    97_000),
        ("JPM",  "JPMorgan Chase",       62_800_000,  58_400_000, 358_000,   334_000),
        ("AVGO", "Broadcom Inc",         48_200_000,  36_400_000, 408_000,   312_000),
        ("PLTR", "Palantir Tech",         8_200_000,   4_100_000, 420_000,   210_000),
        ("BAH",  "Booz Allen Hamilton",   4_800_000,   3_200_000,  42_000,    28_000),
        ("LDOS", "Leidos Holdings",       3_600_000,   3_800_000,  34_000,    36_000),
        ("LHX",  "L3Harris Tech",         6_200_000,   5_100_000,  42_000,    34_000),
    ],
    "Vanguard": [
        ("AAPL", "Apple Inc",           312_400_000, 308_100_000, 1_820_000, 1_800_000),
        ("MSFT", "Microsoft Corp",      248_200_000, 244_800_000, 920_000,   908_000),
        ("NVDA", "Nvidia Corp",         224_600_000, 182_400_000, 2_320_000, 1_880_000),
        ("AMZN", "Amazon.com Inc",      198_400_000, 194_200_000, 1_080_000, 1_060_000),
        ("META", "Meta Platforms",      118_200_000,  98_400_000,  288_000,   242_000),
        ("LMT",  "Lockheed Martin",      22_400_000,  18_600_000,   52_000,    43_000),
        ("RTX",  "RTX Corp",             20_100_000,  17_200_000,  216_000,   186_000),
        ("NOC",  "Northrop Grumman",     14_800_000,  11_200_000,   35_000,    27_000),
        ("GD",   "General Dynamics",     11_200_000,   9_400_000,   47_000,    39_000),
        ("SAIC", "SAIC Inc",              2_400_000,   1_800_000,   22_000,    16_000),
        ("HCA",  "HCA Healthcare",       18_400_000,  16_800_000,   74_000,    68_000),
        ("AVGO", "Broadcom Inc",         58_400_000,  44_200_000,  492_000,   378_000),
    ],
    "State Street": [
        ("AAPL", "Apple Inc",           198_200_000, 194_800_000, 1_160_000, 1_140_000),
        ("MSFT", "Microsoft Corp",      162_400_000, 158_200_000,  604_000,   590_000),
        ("NVDA", "Nvidia Corp",         148_600_000, 118_200_000, 1_540_000, 1_220_000),
        ("LMT",  "Lockheed Martin",      14_200_000,  11_800_000,   33_000,    27_000),
        ("RTX",  "RTX Corp",             12_800_000,  10_400_000,  138_000,   112_000),
        ("BA",   "Boeing Co",             8_200_000,  10_400_000,   74_000,    94_000),
        ("NOC",  "Northrop Grumman",      9_200_000,   7_400_000,   22_000,    18_000),
        ("BAH",  "Booz Allen Hamilton",   2_800_000,   1_900_000,   24_000,    17_000),
        ("PLTR", "Palantir Tech",          3_400_000,   1_600_000,  174_000,    82_000),
        ("JPM",  "JPMorgan Chase",        48_200_000,  44_800_000,  276_000,   257_000),
    ],
}


def _cik_int(cik: str) -> str:
    return str(int(cik))


def _get_recent_13f_accessions(cik: str, n: int = 2) -> list[dict]:
    """Returns the last n 13F-HR accession numbers and filing dates."""
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"EDGAR submissions error: {e}")
        return []

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    accessions = filings.get("accessionNumber", [])
    dates = filings.get("filingDate", [])

    results = []
    for form, acc, date in zip(forms, accessions, dates):
        if form == "13F-HR":
            results.append({"accession": acc, "date": date})
        if len(results) >= n:
            break
    return results


def _get_infotable_url(cik: str, accession: str) -> str | None:
    """Finds the infotable XML document URL within a 13F filing."""
    acc_clean = accession.replace("-", "")
    index_url = f"{EDGAR_ARCHIVE}/{_cik_int(cik)}/{acc_clean}/{accession}-index.json"
    try:
        resp = requests.get(index_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("directory", {}).get("item", [])
    except Exception as e:
        print(f"EDGAR index error: {e}")
        return None

    for item in items:
        name = item.get("name", "").lower()
        if "infotable" in name and name.endswith(".xml"):
            return f"{EDGAR_ARCHIVE}/{_cik_int(cik)}/{acc_clean}/{item['name']}"
    # fallback: look for any xml that isn't the primary doc
    for item in items:
        name = item.get("name", "").lower()
        if name.endswith(".xml") and "form13f" not in name and "primary" not in name:
            return f"{EDGAR_ARCHIVE}/{_cik_int(cik)}/{acc_clean}/{item['name']}"
    return None


def _parse_infotable_xml(url: str) -> pd.DataFrame:
    """Downloads and parses a 13F infotable XML into a DataFrame."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        content = resp.text
    except Exception as e:
        print(f"EDGAR XML download error: {e}")
        return pd.DataFrame()

    # Strip namespace for easier parsing
    content = content.replace(' xmlns="', ' xmlnsx="').replace("xmlns:", "xmlnsx:")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"XML parse error: {e}")
        return pd.DataFrame()

    rows = []
    for entry in root.iter("infoTable"):
        name = (entry.findtext("nameOfIssuer") or "").strip()
        cusip = (entry.findtext("cusip") or "").strip()
        value_text = entry.findtext("value") or "0"
        shares_node = entry.find("shrsOrPrnAmt")
        shares_text = "0"
        if shares_node is not None:
            shares_text = shares_node.findtext("sshPrnamt") or "0"

        try:
            value = int(value_text.replace(",", "")) * 1000  # stored in thousands
        except ValueError:
            value = 0
        try:
            shares = int(shares_text.replace(",", ""))
        except ValueError:
            shares = 0

        ticker = CUSIP_TO_TICKER.get(cusip, "")
        rows.append({
            "ticker": ticker,
            "company": name,
            "cusip": cusip,
            "value_usd": value,
            "shares": shares,
        })

    return pd.DataFrame(rows)


def get_holdings(institution: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (current_quarter, prior_quarter) holdings DataFrames.
    Falls back to demo data if EDGAR is unreachable.
    """
    cik = INSTITUTIONS.get(institution)
    if not cik:
        return pd.DataFrame(), pd.DataFrame()

    accessions = _get_recent_13f_accessions(cik, n=2)

    if len(accessions) >= 2:
        time.sleep(0.5)  # be polite to SEC servers
        url_current = _get_infotable_url(cik, accessions[0]["accession"])
        time.sleep(0.5)
        url_prior = _get_infotable_url(cik, accessions[1]["accession"])

        current = _parse_infotable_xml(url_current) if url_current else pd.DataFrame()
        prior = _parse_infotable_xml(url_prior) if url_prior else pd.DataFrame()

        if not current.empty and not prior.empty:
            return current, prior

    # Fallback to demo data
    return _demo_holdings(institution)


def _demo_holdings(institution: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = DEMO_HOLDINGS.get(institution, [])
    current_rows, prior_rows = [], []
    for ticker, company, val_cur, val_pri, sh_cur, sh_pri in data:
        current_rows.append({"ticker": ticker, "company": company,
                             "value_usd": val_cur, "shares": sh_cur})
        prior_rows.append({"ticker": ticker, "company": company,
                           "value_usd": val_pri, "shares": sh_pri})
    return pd.DataFrame(current_rows), pd.DataFrame(prior_rows)


def get_position_changes(institution: str) -> pd.DataFrame:
    """
    Returns a DataFrame of position changes with columns:
    ticker, company, value_current, value_prior, value_change_pct,
    shares_current, shares_prior, shares_change, action, institution
    """
    current, prior = get_holdings(institution)
    if current.empty:
        return pd.DataFrame()

    merged = current.merge(
        prior[["ticker", "value_usd", "shares"]].rename(
            columns={"value_usd": "value_prior", "shares": "shares_prior"}
        ),
        on="ticker",
        how="outer",
    )
    merged["value_usd"] = merged["value_usd"].fillna(0)
    merged["value_prior"] = merged["value_prior"].fillna(0)
    merged["shares"] = merged["shares"].fillna(0)
    merged["shares_prior"] = merged["shares_prior"].fillna(0)

    def _action(row):
        if row["value_prior"] == 0:
            return "NEW"
        if row["value_usd"] == 0:
            return "SOLD"
        pct = (row["value_usd"] - row["value_prior"]) / row["value_prior"] * 100
        if pct >= 5:
            return "INCREASED"
        if pct <= -5:
            return "DECREASED"
        return "HELD"

    merged["action"] = merged.apply(_action, axis=1)
    merged["value_change_pct"] = (
        (merged["value_usd"] - merged["value_prior"])
        / merged["value_prior"].replace(0, float("nan"))
        * 100
    ).round(1)
    merged["shares_change"] = (merged["shares"] - merged["shares_prior"]).astype(int)
    merged["institution"] = institution

    return merged.rename(columns={"value_usd": "value_current"})[
        ["ticker", "company", "institution", "action",
         "value_current", "value_prior", "value_change_pct",
         "shares_change", "shares"]
    ].sort_values("value_current", ascending=False)


def get_all_institution_changes() -> pd.DataFrame:
    """Combines position changes across all tracked institutions."""
    frames = [get_position_changes(name) for name in INSTITUTIONS]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
