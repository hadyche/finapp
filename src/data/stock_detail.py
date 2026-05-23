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
