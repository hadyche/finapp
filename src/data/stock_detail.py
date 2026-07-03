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


def _fast_info_value(fi, dict_key: str, attr_key: str):
    try:
        raw = fi.get(dict_key) if hasattr(fi, "get") else getattr(fi, attr_key, None)
        if raw and float(raw) > 0:
            return float(raw)
    except Exception:
        pass
    return None


def get_market_stats(tickers: list[str]) -> dict[str, dict]:
    """
    Market cap and average daily dollar volume per ticker.
    Values are None for any symbol that fails — callers must treat None
    as 'unknown', never guess.
    """
    stats: dict[str, dict] = {}
    if not tickers:
        return stats
    try:
        batch = yf.Tickers(" ".join(tickers))
    except Exception as e:
        print(f"yfinance batch error: {e}")
        return {t: {"cap": None, "adv_usd": None} for t in tickers}

    for t in tickers:
        cap = adv_usd = None
        try:
            fi = batch.tickers[t.upper()].fast_info
            cap = _fast_info_value(fi, "marketCap", "market_cap")
            price = _fast_info_value(fi, "lastPrice", "last_price")
            avg_vol = _fast_info_value(fi, "threeMonthAverageVolume", "three_month_average_daily_volume") \
                or _fast_info_value(fi, "tenDayAverageVolume", "ten_day_average_volume")
            if price and avg_vol:
                adv_usd = price * avg_vol
        except Exception:
            pass
        stats[t] = {"cap": cap, "adv_usd": adv_usd}
    return stats


def change_since(closes: pd.Series, date_str: str) -> float | None:
    """
    % change from the first close on/after date_str to the latest close.
    Pure logic — unit-testable. None when the date is out of range.
    """
    try:
        s = closes.dropna()
        if s.empty:
            return None
        idx = s.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
            s = pd.Series(s.values, index=idx)
        target = pd.Timestamp(str(date_str)[:10])
        after = s[s.index >= target]
        if after.empty:
            return None
        start = float(after.iloc[0])
        end = float(s.iloc[-1])
        if start <= 0:
            return None
        return (end - start) / start * 100
    except Exception:
        return None


def get_price_changes_since(pairs: list[tuple[str, str]]) -> dict[str, float | None]:
    """
    % price change since a date, per ticker, in ONE batched download.
    pairs: [(ticker, iso_date), ...]. Returns {ticker: pct or None}.
    """
    out: dict[str, float | None] = {}
    valid = [(t, d) for t, d in pairs if t and str(d)[:10] >= "2000-01-01"]
    if not valid:
        return out
    tickers = sorted({t for t, _ in valid})
    start = min(str(d)[:10] for _, d in valid)
    try:
        data = yf.download(tickers, start=start, progress=False, auto_adjust=True)
        closes = data["Close"]
        if isinstance(closes, pd.Series):  # single ticker: no column level
            closes = closes.to_frame(name=tickers[0])
    except Exception as e:
        print(f"yfinance download error: {e}")
        return {t: None for t, _ in valid}

    for t, d in valid:
        try:
            out[t] = change_since(closes[t], d)
        except Exception:
            out[t] = None
    return out


def get_benchmark_changes(dates: list[str], benchmark: str = "SPY") -> dict[str, float | None]:
    """% change of a benchmark since each date. Returns {date: pct or None}."""
    out: dict[str, float | None] = {}
    dates = sorted({str(d)[:10] for d in dates if d})
    if not dates:
        return out
    try:
        data = yf.download(benchmark, start=dates[0], progress=False, auto_adjust=True)
        closes = data["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
    except Exception as e:
        print(f"yfinance benchmark error: {e}")
        return {d: None for d in dates}
    for d in dates:
        out[d] = change_since(closes, d)
    return out


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
