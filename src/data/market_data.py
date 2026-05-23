"""
Fetches sector ETF performance using yfinance (no API key needed).
Maps SPDR sector ETFs to economic sectors for cross-referencing with
government contracts and institutional flows.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


# Demo data used when live API is unreachable (offline/sandboxed environments)
DEMO_SECTOR_PERFORMANCE = [
    {"sector": "Technology",      "ticker": "XLK",  "return_pct": 4.2,  "latest_price": 224.50, "start_price": 215.45},
    {"sector": "Defense",         "ticker": "ITA",  "return_pct": 3.8,  "latest_price": 138.20, "start_price": 133.14},
    {"sector": "Healthcare",      "ticker": "XLV",  "return_pct": 2.1,  "latest_price": 147.30, "start_price": 144.27},
    {"sector": "Financials",      "ticker": "XLF",  "return_pct": 1.7,  "latest_price": 45.60,  "start_price": 44.84},
    {"sector": "Industrials",     "ticker": "XLI",  "return_pct": 1.5,  "latest_price": 132.10, "start_price": 130.15},
    {"sector": "Energy",          "ticker": "XLE",  "return_pct": 0.8,  "latest_price": 89.40,  "start_price": 88.69},
    {"sector": "Communication",   "ticker": "XLC",  "return_pct": 0.4,  "latest_price": 93.20,  "start_price": 92.83},
    {"sector": "Consumer Disc.",  "ticker": "XLY",  "return_pct": -0.3, "latest_price": 195.80, "start_price": 196.39},
    {"sector": "Consumer Staples","ticker": "XLP",  "return_pct": -0.9, "latest_price": 79.20,  "start_price": 79.92},
    {"sector": "Real Estate",     "ticker": "XLRE", "return_pct": -1.4, "latest_price": 41.30,  "start_price": 41.89},
    {"sector": "Materials",       "ticker": "XLB",  "return_pct": -1.8, "latest_price": 88.70,  "start_price": 90.33},
    {"sector": "Utilities",       "ticker": "XLU",  "return_pct": -2.3, "latest_price": 70.10,  "start_price": 71.75},
]

DEMO_BROAD_MARKET = [
    {"index": "S&P 500",      "ticker": "SPY", "return_pct": 2.1, "latest_price": 536.40},
    {"index": "Nasdaq 100",   "ticker": "QQQ", "return_pct": 3.4, "latest_price": 468.20},
    {"index": "Russell 2000", "ticker": "IWM", "return_pct": 1.2, "latest_price": 208.50},
    {"index": "Total Market", "ticker": "VTI", "return_pct": 2.0, "latest_price": 266.80},
]

SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Disc.": "XLY",
    "Consumer Staples": "XLP",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication": "XLC",
    "Defense": "ITA",       # iShares U.S. Aerospace & Defense
}

BROAD_MARKET = {
    "S&P 500": "SPY",
    "Nasdaq 100": "QQQ",
    "Russell 2000": "IWM",
    "Total Market": "VTI",
}


def fetch_sector_performance(days_back: int = 30) -> pd.DataFrame:
    """Returns % return for each sector ETF over the given window."""
    tickers = list(SECTOR_ETFS.values())
    end = datetime.today()
    start = end - timedelta(days=days_back + 5)

    try:
        raw = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=True)
        close = raw["Close"] if "Close" in raw else raw
    except Exception as e:
        print(f"yfinance error: {e}")
        return pd.DataFrame(DEMO_SECTOR_PERFORMANCE)

    rows = []
    for sector, ticker in SECTOR_ETFS.items():
        if ticker not in close.columns:
            continue
        series = close[ticker].dropna()
        if len(series) < 2:
            continue
        pct_change = (series.iloc[-1] / series.iloc[0] - 1) * 100
        rows.append(
            {
                "sector": sector,
                "ticker": ticker,
                "return_pct": round(float(pct_change), 2),
                "latest_price": round(float(series.iloc[-1]), 2),
                "start_price": round(float(series.iloc[0]), 2),
            }
        )

    if not rows:
        return pd.DataFrame(DEMO_SECTOR_PERFORMANCE)
    return pd.DataFrame(rows).sort_values("return_pct", ascending=False)


def fetch_broad_market(days_back: int = 30) -> pd.DataFrame:
    """Returns performance of broad market indices."""
    tickers = list(BROAD_MARKET.values())
    end = datetime.today()
    start = end - timedelta(days=days_back + 5)

    try:
        raw = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=True)
        close = raw["Close"] if "Close" in raw else raw
    except Exception as e:
        print(f"yfinance error: {e}")
        return pd.DataFrame(DEMO_BROAD_MARKET)

    rows = []
    for name, ticker in BROAD_MARKET.items():
        if ticker not in close.columns:
            continue
        series = close[ticker].dropna()
        if len(series) < 2:
            continue
        pct_change = (series.iloc[-1] / series.iloc[0] - 1) * 100
        rows.append(
            {
                "index": name,
                "ticker": ticker,
                "return_pct": round(float(pct_change), 2),
                "latest_price": round(float(series.iloc[-1]), 2),
            }
        )

    if not rows:
        return pd.DataFrame(DEMO_BROAD_MARKET)
    return pd.DataFrame(rows)


def fetch_sector_history(sector: str, days_back: int = 90) -> pd.DataFrame:
    """Returns daily closing prices for a sector ETF."""
    ticker = SECTOR_ETFS.get(sector)
    if not ticker:
        return pd.DataFrame()

    end = datetime.today()
    start = end - timedelta(days=days_back)

    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df[["Close"]].reset_index()
        df.columns = ["date", "price"]
        df["sector"] = sector
        return df
    except Exception as e:
        print(f"yfinance history error: {e}")
        return pd.DataFrame()
