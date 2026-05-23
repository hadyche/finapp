"""
Simple file-based cache using pandas parquet files.
Avoids hammering public APIs on every Streamlit rerun.
"""

import os
import time
import pandas as pd
from pathlib import Path

CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/finapp_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TTL = {
    "gov_contracts": 6 * 3600,       # 6 hours
    "sector_perf": 1 * 3600,         # 1 hour
    "economic_indicators": 12 * 3600, # 12 hours
    "sec_filings": 24 * 3600,        # 24 hours (quarterly data)
}


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.parquet"


def _meta_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.ts"


def cache_get(key: str) -> pd.DataFrame | None:
    """Returns cached DataFrame if fresh, else None."""
    cp = _cache_path(key)
    mp = _meta_path(key)
    if not cp.exists() or not mp.exists():
        return None

    ttl = DEFAULT_TTL.get(key, 3600)
    age = time.time() - float(mp.read_text())
    if age > ttl:
        return None

    try:
        return pd.read_parquet(cp)
    except Exception:
        return None


def cache_set(key: str, df: pd.DataFrame) -> None:
    """Writes DataFrame to cache with current timestamp."""
    if df.empty:
        return
    try:
        df.to_parquet(_cache_path(key), index=False)
        _meta_path(key).write_text(str(time.time()))
    except Exception as e:
        print(f"Cache write error ({key}): {e}")


def cache_bust(key: str) -> None:
    """Invalidates a cache entry."""
    mp = _meta_path(key)
    if mp.exists():
        mp.write_text("0")
