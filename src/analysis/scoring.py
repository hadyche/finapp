"""
Rules-based scoring engine that combines government contracts,
institutional filings activity, and market momentum to surface
sectors with converging positive signals.

DISCLAIMER: For informational/educational purposes only.
Not financial advice. Past signals do not guarantee future returns.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List


SECTOR_ALIAS = {
    "Information Technology": "Technology",
    "Professional Services": "Technology",
    "Defense & Public Admin": "Defense",
    "Healthcare": "Healthcare",
    "Finance & Insurance": "Financials",
    "Manufacturing": "Industrials",
    "Construction": "Industrials",
    "Mining & Energy": "Energy",
    "Agriculture": "Consumer Staples",
    "Retail Trade": "Consumer Disc.",
    "Utilities": "Utilities",
    "Transportation": "Industrials",
}


@dataclass
class SectorSignal:
    sector: str
    contract_score: float       # 0-40: government money flowing in
    market_score: float         # 0-40: ETF momentum
    filing_activity: float      # 0-20: institutional filing recency
    total_score: float
    signals: List[str]
    recommendation: str


def _normalize(series: pd.Series, max_val: float = 1.0) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - mn) / (mx - mn) * max_val


def score_contracts(sector_summary: pd.DataFrame) -> pd.Series:
    """Scores sectors 0-40 based on contract dollar volume."""
    if sector_summary.empty:
        return pd.Series(dtype=float)
    s = sector_summary.set_index("sector")["total_amount"]
    return _normalize(s, 40.0)


def score_market(sector_perf: pd.DataFrame) -> pd.Series:
    """Scores sectors 0-40 based on ETF return momentum."""
    if sector_perf.empty:
        return pd.Series(dtype=float)
    s = sector_perf.set_index("sector")["return_pct"]
    return _normalize(s, 40.0)


def build_sector_scores(
    sector_contracts: pd.DataFrame,
    sector_perf: pd.DataFrame,
) -> List[SectorSignal]:
    """
    Merges contract and market data into a unified sector scorecard.
    Returns a list of SectorSignal objects sorted by total score desc.
    """
    contract_scores = score_contracts(sector_contracts)
    market_scores = score_market(sector_perf)

    all_sectors = set(contract_scores.index.tolist()) | set(market_scores.index.tolist())

    # Map government sectors to ETF sectors
    mapped_contract: dict[str, float] = {}
    for gov_sector, score in contract_scores.items():
        etf_sector = SECTOR_ALIAS.get(gov_sector, gov_sector)
        existing = mapped_contract.get(etf_sector, 0.0)
        mapped_contract[etf_sector] = max(existing, score)

    results = []
    etf_sectors = set(market_scores.index.tolist()) | set(mapped_contract.keys())

    for sector in etf_sectors:
        cs = mapped_contract.get(sector, 0.0)
        ms = float(market_scores.get(sector, 0.0))
        filing = 10.0  # Base 10/20 — full 13F analysis requires XML parsing

        total = cs + ms + filing
        signals = []

        if cs > 25:
            signals.append("High government contract flow")
        elif cs > 12:
            signals.append("Moderate government contract activity")

        if ms > 25:
            signals.append("Strong ETF momentum")
        elif ms > 12:
            signals.append("Positive ETF trend")
        elif ms < 5:
            signals.append("Weak ETF performance")

        if total >= 55:
            rec = "STRONG BUY SIGNAL"
        elif total >= 40:
            rec = "POSITIVE SIGNAL"
        elif total >= 25:
            rec = "NEUTRAL — monitor"
        else:
            rec = "WEAK SIGNAL"

        results.append(
            SectorSignal(
                sector=sector,
                contract_score=round(cs, 1),
                market_score=round(ms, 1),
                filing_activity=filing,
                total_score=round(total, 1),
                signals=signals if signals else ["Insufficient signal"],
                recommendation=rec,
            )
        )

    results.sort(key=lambda x: x.total_score, reverse=True)
    return results


def signals_to_dataframe(signals: List[SectorSignal]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Sector": s.sector,
                "Gov Contracts (0-40)": s.contract_score,
                "Market Momentum (0-40)": s.market_score,
                "Institutional Activity (0-20)": s.filing_activity,
                "Total Score (0-100)": s.total_score,
                "Key Signals": " | ".join(s.signals),
                "Recommendation": s.recommendation,
            }
            for s in signals
        ]
    )
