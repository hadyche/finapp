"""
Fetches key macroeconomic indicators from FRED (St. Louis Fed).
Falls back to cached/demo data if no API key is set.
"""

import os
import pandas as pd
from datetime import datetime, timedelta

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False


FRED_SERIES = {
    "GDP Growth": "A191RL1Q225SBEA",       # Real GDP % change QoQ
    "CPI Inflation": "CPIAUCSL",            # Consumer Price Index
    "Unemployment": "UNRATE",               # Unemployment rate
    "Fed Funds Rate": "FEDFUNDS",           # Federal funds rate
    "10Y Treasury": "DGS10",               # 10-year treasury yield
    "2Y Treasury": "DGS2",                 # 2-year treasury yield
    "Consumer Sentiment": "UMCSENT",        # U of Michigan consumer sentiment
    "Industrial Production": "INDPRO",      # Industrial production index
    "Retail Sales": "RSXFS",              # Retail sales ex food services
    "Housing Starts": "HOUST",            # New housing starts
}

# Hardcoded recent values for fallback when no API key exists
FALLBACK_DATA = {
    "GDP Growth": 2.8,
    "CPI Inflation": 313.5,
    "Unemployment": 4.1,
    "Fed Funds Rate": 5.33,
    "10Y Treasury": 4.42,
    "2Y Treasury": 4.71,
    "Consumer Sentiment": 68.2,
    "Industrial Production": 103.4,
    "Retail Sales": 625000,
    "Housing Starts": 1354,
}

INDICATOR_DESCRIPTIONS = {
    "GDP Growth": "Real GDP quarterly growth rate (%)",
    "CPI Inflation": "Consumer Price Index (all urban consumers)",
    "Unemployment": "Unemployment rate (%)",
    "Fed Funds Rate": "Federal Reserve target interest rate (%)",
    "10Y Treasury": "10-Year Treasury yield (%) — key risk benchmark",
    "2Y Treasury": "2-Year Treasury yield (%) — Fed expectations proxy",
    "Consumer Sentiment": "U of Michigan consumer confidence index",
    "Industrial Production": "Industrial output index (2017=100)",
    "Retail Sales": "Retail & food services sales ex autos ($M)",
    "Housing Starts": "New residential construction starts (thousands)",
}


def _get_fred_client():
    api_key = os.getenv("FRED_API_KEY")
    if not api_key or not FRED_AVAILABLE:
        return None
    try:
        return Fred(api_key=api_key)
    except Exception:
        return None


def fetch_indicator(series_name: str, periods: int = 12) -> pd.DataFrame:
    """Returns recent observations for a single FRED series."""
    fred = _get_fred_client()
    series_id = FRED_SERIES.get(series_name)
    if not series_id or not fred:
        return pd.DataFrame()

    try:
        data = fred.get_series(series_id)
        df = data.reset_index()
        df.columns = ["date", "value"]
        df = df.dropna().tail(periods)
        df["series"] = series_name
        return df
    except Exception as e:
        print(f"FRED fetch error for {series_name}: {e}")
        return pd.DataFrame()


def fetch_all_indicators_latest() -> pd.DataFrame:
    """Returns the latest value for every tracked indicator."""
    fred = _get_fred_client()
    rows = []

    for name, series_id in FRED_SERIES.items():
        value = None
        date = None

        if fred:
            try:
                data = fred.get_series(series_id)
                data = data.dropna()
                if not data.empty:
                    value = round(float(data.iloc[-1]), 3)
                    date = str(data.index[-1].date())
            except Exception as e:
                print(f"FRED error {name}: {e}")

        if value is None:
            value = FALLBACK_DATA.get(name, 0)
            date = "2024-Q4 (cached)"

        rows.append(
            {
                "indicator": name,
                "value": value,
                "date": date,
                "description": INDICATOR_DESCRIPTIONS.get(name, ""),
            }
        )

    return pd.DataFrame(rows)


def yield_curve_signal() -> str:
    """
    Simple yield curve inversion check.
    Inverted (2Y > 10Y) historically precedes recessions.
    """
    fred = _get_fred_client()
    try:
        if fred:
            t10 = float(fred.get_series("DGS10").dropna().iloc[-1])
            t2 = float(fred.get_series("DGS2").dropna().iloc[-1])
        else:
            t10 = FALLBACK_DATA["10Y Treasury"]
            t2 = FALLBACK_DATA["2Y Treasury"]

        spread = t10 - t2
        if spread < 0:
            return f"INVERTED (spread: {spread:.2f}%) — Recession risk elevated"
        elif spread < 0.5:
            return f"FLAT (spread: {spread:.2f}%) — Watch for slowdown"
        else:
            return f"NORMAL (spread: {spread:.2f}%) — Healthy"
    except Exception:
        return "Data unavailable"
