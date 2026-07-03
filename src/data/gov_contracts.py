"""
Fetches federal contract award data from USAspending.gov public API.
Groups awards by NAICS sector to show where government money is flowing.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta


USASPENDING_BASE = "https://api.usaspending.gov/api/v2"

DEMO_SECTOR_SUMMARY = [
    {"sector": "Defense & Public Admin", "total_amount": 48_200_000_000, "contract_count": 1204},
    {"sector": "Information Technology", "total_amount": 31_500_000_000, "contract_count": 892},
    {"sector": "Healthcare",             "total_amount": 22_800_000_000, "contract_count": 743},
    {"sector": "Professional Services",  "total_amount": 18_400_000_000, "contract_count": 615},
    {"sector": "Manufacturing",          "total_amount": 14_200_000_000, "contract_count": 387},
    {"sector": "Construction",           "total_amount": 11_800_000_000, "contract_count": 298},
    {"sector": "Transportation",         "total_amount": 7_600_000_000,  "contract_count": 201},
    {"sector": "Mining & Energy",        "total_amount": 5_400_000_000,  "contract_count": 134},
]

DEMO_RECENT_AWARDS = [
    {"award_id": "DEMO-001", "recipient": "Kratos Defense & Security Solutions", "amount": 87_000_000, "date": "2025-04-15", "award_type": "Delivery Order", "agency": "U.S. Army", "naics_code": "336411", "naics_desc": "Aircraft Manufacturing", "sector": "Manufacturing"},
    {"award_id": "DEMO-002", "recipient": "Mercury Systems Inc", "amount": 64_500_000, "date": "2025-04-10", "award_type": "Definitized Contract Action", "agency": "U.S. Navy", "naics_code": "334511", "naics_desc": "Defense Electronics", "sector": "Manufacturing"},
    {"award_id": "DEMO-003", "recipient": "Palantir Technologies", "amount": 178_000_000, "date": "2025-04-08", "award_type": "Contract", "agency": "U.S. Army", "naics_code": "518210", "naics_desc": "Data Processing", "sector": "Information Technology"},
    {"award_id": "DEMO-004", "recipient": "Leidos Holdings Inc", "amount": 312_000_000, "date": "2025-04-05", "award_type": "Contract", "agency": "Department of Defense", "naics_code": "541512", "naics_desc": "Computer Systems Design", "sector": "Professional Services"},
    {"award_id": "DEMO-005", "recipient": "Booz Allen Hamilton", "amount": 95_000_000, "date": "2025-04-03", "award_type": "Contract", "agency": "Department of Homeland Security", "naics_code": "541611", "naics_desc": "Management Consulting", "sector": "Professional Services"},
    {"award_id": "DEMO-006", "recipient": "CACI International", "amount": 56_000_000, "date": "2025-04-01", "award_type": "Delivery Order", "agency": "U.S. Army", "naics_code": "541519", "naics_desc": "IT Consulting", "sector": "Professional Services"},
    {"award_id": "DEMO-007", "recipient": "Parsons Corporation", "amount": 43_200_000, "date": "2025-03-28", "award_type": "Contract", "agency": "U.S. Army Corps of Engineers", "naics_code": "237310", "naics_desc": "Highway Construction", "sector": "Construction"},
    {"award_id": "DEMO-008", "recipient": "Tetra Tech Inc", "amount": 38_700_000, "date": "2025-03-25", "award_type": "Contract", "agency": "U.S. Air Force", "naics_code": "541330", "naics_desc": "Engineering Services", "sector": "Professional Services"},
    {"award_id": "DEMO-009", "recipient": "AeroVironment Inc", "amount": 29_800_000, "date": "2025-03-22", "award_type": "Delivery Order", "agency": "U.S. Army", "naics_code": "336411", "naics_desc": "Aircraft Manufacturing", "sector": "Manufacturing"},
    {"award_id": "DEMO-010", "recipient": "BWX Technologies Inc", "amount": 125_000_000, "date": "2025-03-20", "award_type": "Contract", "agency": "Department of Energy", "naics_code": "325180", "naics_desc": "Nuclear Material", "sector": "Manufacturing"},
    {"award_id": "DEMO-011", "recipient": "ManTech International", "amount": 67_000_000, "date": "2025-03-18", "award_type": "Contract", "agency": "Department of Defense", "naics_code": "541519", "naics_desc": "IT Consulting", "sector": "Professional Services"},
    {"award_id": "DEMO-012", "recipient": "V2X Inc", "amount": 52_000_000, "date": "2025-03-15", "award_type": "Delivery Order", "agency": "U.S. Air Force", "naics_code": "488190", "naics_desc": "Aviation Support", "sector": "Transportation"},
    {"award_id": "DEMO-013", "recipient": "BigBear.ai Holdings", "amount": 21_500_000, "date": "2025-03-12", "award_type": "Contract", "agency": "National Geospatial-Intelligence Agency", "naics_code": "518210", "naics_desc": "Data Processing", "sector": "Information Technology"},
    {"award_id": "DEMO-014", "recipient": "Maximus Federal Services", "amount": 88_000_000, "date": "2025-03-10", "award_type": "Contract", "agency": "Centers for Medicare & Medicaid", "naics_code": "621999", "naics_desc": "Health Services", "sector": "Healthcare"},
    {"award_id": "DEMO-015", "recipient": "Telos Corporation", "amount": 18_300_000, "date": "2025-03-08", "award_type": "Contract", "agency": "Department of Homeland Security", "naics_code": "541512", "naics_desc": "Computer Systems Design", "sector": "Information Technology"},
]

DEMO_TOP_RECIPIENTS = [
    {"recipient": "Lockheed Martin",    "total_amount": 8_400_000_000, "contracts": 42},
    {"recipient": "Raytheon Technologies", "total_amount": 6_200_000_000, "contracts": 38},
    {"recipient": "General Dynamics",   "total_amount": 5_100_000_000, "contracts": 29},
    {"recipient": "Boeing",             "total_amount": 4_800_000_000, "contracts": 31},
    {"recipient": "Northrop Grumman",   "total_amount": 4_100_000_000, "contracts": 24},
    {"recipient": "Leidos Holdings",    "total_amount": 3_200_000_000, "contracts": 18},
    {"recipient": "BAE Systems",        "total_amount": 2_900_000_000, "contracts": 16},
    {"recipient": "L3Harris Technologies", "total_amount": 2_600_000_000, "contracts": 14},
    {"recipient": "SAIC",               "total_amount": 2_100_000_000, "contracts": 22},
    {"recipient": "Booz Allen Hamilton", "total_amount": 1_800_000_000, "contracts": 19},
]

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


def fetch_recent_awards(days_back: int = 30, limit: int = 100) -> pd.DataFrame:
    """Returns recent contract awards with sector labels."""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days_back)

    payload = {
        "filters": {
            "time_period": [
                {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                }
            ],
            "award_type_codes": ["A", "B", "C", "D"],  # contracts only
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
        "limit": limit,
        "page": 1,
    }

    try:
        resp = requests.post(
            f"{USASPENDING_BASE}/search/spending_by_award/",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"USAspending fetch error: {e}")
        return pd.DataFrame()   # caller will use demo data

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
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


def sector_spending_summary(days_back: int = 30) -> pd.DataFrame:
    """Aggregates total contract dollars and count per sector."""
    df = fetch_recent_awards(days_back=days_back, limit=100)
    if df.empty:
        return pd.DataFrame(DEMO_SECTOR_SUMMARY)

    summary = (
        df.groupby("sector")
        .agg(total_amount=("amount", "sum"), contract_count=("amount", "count"))
        .reset_index()
        .sort_values("total_amount", ascending=False)
    )
    return summary


def top_recipients(days_back: int = 30, top_n: int = 10) -> pd.DataFrame:
    """Returns top contract recipients by total award value."""
    df = fetch_recent_awards(days_back=days_back, limit=100)
    if df.empty:
        return pd.DataFrame(DEMO_TOP_RECIPIENTS)

    return (
        df.groupby("recipient")
        .agg(total_amount=("amount", "sum"), contracts=("amount", "count"))
        .reset_index()
        .sort_values("total_amount", ascending=False)
        .head(top_n)
    )


# Ticker → keywords used to match contract recipient names
TICKER_TO_RECIPIENT_KEYWORDS = {
    "LMT":  ["LOCKHEED MARTIN", "LOCKHEED"],
    "RTX":  ["RAYTHEON", "RTX CORP"],
    "BA":   ["BOEING"],
    "NOC":  ["NORTHROP GRUMMAN", "NORTHROP"],
    "GD":   ["GENERAL DYNAMICS"],
    "LHX":  ["L3HARRIS", "L3 HARRIS"],
    "LDOS": ["LEIDOS"],
    "BAH":  ["BOOZ ALLEN"],
    "SAIC": ["SAIC"],
    "HII":  ["HUNTINGTON INGALLS"],
    "CACI": ["CACI"],
    "PSN":  ["PARSONS"],
    "KTOS": ["KRATOS"],
    "BWXT": ["BWX TECHNOLOGIES", "BWXT"],
    "MMS":  ["MAXIMUS"],
    "ICFI": ["ICF "],
    "TTEK": ["TETRA TECH"],
    "ACM":  ["AECOM"],
    "AVAV": ["AEROVIRONMENT"],
    "MOOG": ["MOOG"],
    "V2X":  ["VECTRUS", "V2X"],
    "VSE":  ["VSE CORP"],
    "GVA":  ["GRANITE CONSTRUCTION"],
    "PRIM": ["PRIMORIS"],
    "DY":   ["DYCOM"],
    "MYRG": ["MYR GROUP"],
    "OPCH": ["OPTION CARE"],
    "ADUS": ["ADDUS"],
    "AXON": ["AXON"],
    "MRCY": ["MERCURY SYSTEMS", "MERCURY"],
    "TLS":  ["TELOS"],
    "BBAI": ["BIGBEAR"],
    "LEU":  ["CENTRUS"],
    "SMR":  ["NUSCALE"],
    "DCO":  ["DUCOMMUN"],
    "TGI":  ["TRIUMPH GROUP"],
    "KAMN": ["KAMAN"],
    "MANT": ["MANTECH"],
    "CW":   ["CURTISS"],
    "MSFT": ["MICROSOFT"],
    "AMZN": ["AMAZON"],
    "GOOGL":["GOOGLE", "ALPHABET"],
    "PLTR": ["PALANTIR"],
    "ORCL": ["ORACLE"],
    "IBM":  ["IBM"],
    "UNH":  ["UNITEDHEALTH"],
    "HCA":  ["HCA"],
    "CVS":  ["CVS HEALTH"],
}


def contracts_for_ticker(ticker: str, days_back: int = 365) -> pd.DataFrame:
    """Returns all contract awards matching a ticker's parent company."""
    keywords = TICKER_TO_RECIPIENT_KEYWORDS.get(ticker.upper(), [])
    if not keywords:
        return pd.DataFrame()

    df = fetch_recent_awards(days_back=days_back, limit=500)
    if df.empty:
        return pd.DataFrame()

    df["recipient_upper"] = df["recipient"].astype(str).str.upper()
    mask = df["recipient_upper"].apply(
        lambda r: any(kw in r for kw in keywords)
    )
    return df[mask].drop(columns=["recipient_upper"]).sort_values("amount", ascending=False)


def fed_dollar_summary(ticker: str, days_back: int = 365) -> dict:
    """Returns total $, contract count, and agency breakdown for a ticker."""
    df = contracts_for_ticker(ticker, days_back=days_back)
    if df.empty:
        return {"total": 0, "count": 0, "agencies": pd.DataFrame()}

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


def recent_award_feed(days_back: int = 30, min_amount: float = 5_000_000, top_n: int = 25) -> pd.DataFrame:
    """Recent big federal awards as a chronological feed for the home page."""
    df = fetch_recent_awards(days_back=days_back, limit=200)
    if df.empty:
        demo = pd.DataFrame(DEMO_RECENT_AWARDS)
        demo["ticker"] = None
        from src.analysis.watchlist import CONTRACT_COMPANY_TO_TICKER
        def _map_demo(name):
            u = str(name).upper()
            for key, t in CONTRACT_COMPANY_TO_TICKER.items():
                if key in u:
                    return t
            return None
        demo["ticker"] = demo["recipient"].apply(_map_demo)
        return demo[demo["amount"] >= min_amount].head(top_n).reset_index(drop=True)

    df = df[df["amount"] >= min_amount].copy()

    # Late import to avoid circular import
    from src.analysis.watchlist import CONTRACT_COMPANY_TO_TICKER

    def _map(name):
        u = str(name).upper()
        for key, t in CONTRACT_COMPANY_TO_TICKER.items():
            if key in u:
                return t
        return None

    df["ticker"] = df["recipient"].apply(_map)
    return df.sort_values("amount", ascending=False).head(top_n).reset_index(drop=True)
