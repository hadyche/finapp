"""Live stock data: prices, history, fundamentals via yfinance."""
import pandas as pd
import yfinance as yf
from datetime import datetime


PERIOD_MAP = {
    "1D":  ("1d",  "5m"),
    "5D":  ("5d",  "30m"),
    "1M":  ("1mo", "1d"),
    "3M":  ("3mo", "1d"),
    "6M":  ("6mo", "1d"),
    "1Y":  ("1y",  "1d"),
    "5Y":  ("5y",  "1wk"),
    "Max": ("max", "1mo"),
}


def get_price_history(ticker: str, timeframe: str = "3M") -> pd.DataFrame:
    period, interval = PERIOD_MAP.get(timeframe, ("3mo", "1d"))
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        date_col = "Datetime" if "Datetime" in df.columns else "Date"
        df = df.rename(columns={date_col: "date"})
        return df
    except Exception as e:
        print(f"yfinance error for {ticker}: {e}")
        return pd.DataFrame()


def get_quote(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="5d")
        last_price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_price
        change = last_price - prev if last_price and prev else 0
        change_pct = (change / prev * 100) if prev else 0
        return {
            "price": last_price,
            "change": change,
            "change_pct": change_pct,
            "market_cap": info.get("marketCap"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "avg_volume": info.get("averageVolume"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "fifty_two_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_low": info.get("fiftyTwoWeekLow"),
            "long_name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "summary": info.get("longBusinessSummary"),
        }
    except Exception as e:
        print(f"Quote error {ticker}: {e}")
        return {}


def get_market_caps(tickers: list[str]) -> dict[str, float | None]:
    """
    Market caps for a batch of tickers. None for any symbol that fails —
    callers must treat None as 'unknown', never guess.
    """
    caps: dict[str, float | None] = {}
    if not tickers:
        return caps
    try:
        batch = yf.Tickers(" ".join(tickers))
    except Exception as e:
        print(f"yfinance batch error: {e}")
        return {t: None for t in tickers}

    for t in tickers:
        cap = None
        try:
            fi = batch.tickers[t.upper()].fast_info
            raw = fi.get("marketCap") if hasattr(fi, "get") else getattr(fi, "market_cap", None)
            if raw and float(raw) > 0:
                cap = float(raw)
        except Exception:
            cap = None
        caps[t] = cap
    return caps


INDEX_INSTITUTIONS = ("BLACKROCK", "VANGUARD", "STATE STREET")


def get_index_fund_holders(ticker: str) -> list[str]:
    """
    Which of the big index institutions appear in this stock's top
    institutional holders. Confirmation badge only — passive funds hold
    nearly everything, so this is not a discovery signal.
    """
    try:
        t = yf.Ticker(ticker)
        df = t.institutional_holders
        if df is None or df.empty or "Holder" not in df.columns:
            return []
        holders = df["Holder"].astype(str).str.upper().tolist()
        found = []
        for name in INDEX_INSTITUTIONS:
            if any(name in h for h in holders):
                found.append(name.title().replace("Blackrock", "BlackRock"))
        return found
    except Exception as e:
        print(f"Institutional holders error {ticker}: {e}")
        return []


def get_news(ticker: str, limit: int = 5) -> list[dict]:
    try:
        t = yf.Ticker(ticker)
        items = t.news or []
        out = []
        for n in items[:limit]:
            content = n.get("content") or n
            out.append({
                "title": content.get("title", ""),
                "publisher": (content.get("provider") or {}).get("displayName", ""),
                "link": (content.get("canonicalUrl") or {}).get("url") or content.get("link", ""),
                "published": content.get("pubDate", ""),
            })
        return out
    except Exception:
        return []
