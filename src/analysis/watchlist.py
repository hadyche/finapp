"""
Cross-references government contract recipients with institutional buying
to produce a ranked stock watchlist with signal explanations.

Scoring (0-100):
  - Institutional buying pressure  : up to 45 pts
      +15 per institution with INCREASED/NEW position
      +5  per institution with HELD (large position)
  - Government contract exposure   : up to 30 pts
      Scaled by parent company's estimated contract share
  - Market momentum (ETF proxy)    : up to 15 pts
      Sector ETF return mapped onto individual stock
  - Position size (conviction)     : up to 10 pts
      Larger absolute positions = higher conviction signal

DISCLAIMER: Informational only. Not financial advice.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List


# Maps ticker → sector ETF sector label
TICKER_SECTOR = {
    # Defense
    "LMT": "Defense", "RTX": "Defense", "NOC": "Defense", "GD": "Defense",
    "BA": "Defense",  "LHX": "Defense", "LDOS": "Defense", "BAH": "Defense",
    "SAIC": "Defense", "HII": "Defense", "TDG": "Defense",
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AVGO": "Technology", "ORCL": "Technology", "IBM": "Technology",
    "INTC": "Technology", "AMD": "Technology",  "QCOM": "Technology",
    "PLTR": "Technology", "NOW": "Technology",  "INTU": "Technology",
    # Healthcare
    "UNH": "Healthcare", "JNJ": "Healthcare",  "LLY": "Healthcare",
    "ABBV": "Healthcare","PFE": "Healthcare",  "MRK": "Healthcare",
    "HCA": "Healthcare", "CVS": "Healthcare",  "ELV": "Healthcare",
    "MOH": "Healthcare", "ISRG": "Healthcare",
    # Financials
    "JPM": "Financials", "BAC": "Financials",  "GS": "Financials",
    "WFC": "Financials", "AXP": "Financials",  "PNC": "Financials",
    "SCHW": "Financials","MET": "Financials",  "BLK": "Financials",
    # Consumer
    "AMZN": "Consumer Disc.", "TSLA": "Consumer Disc.", "MCD": "Consumer Disc.",
    "BKNG": "Consumer Disc.", "WMT": "Consumer Staples","KO": "Consumer Staples",
    "PG": "Consumer Staples", "PM": "Consumer Staples", "COST": "Consumer Staples",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "SLB": "Energy", "HAL": "Energy",
    "DVN": "Energy", "VLO": "Energy",
    # Industrials
    "HON": "Industrials", "CAT": "Industrials", "URI": "Industrials",
    "PCAR": "Industrials",
    # Communication / Other
    "META": "Communication", "GOOGL": "Communication", "GOOG": "Communication",
    "DIS": "Communication", "VZ": "Communication", "CHTR": "Communication",
    "LIN": "Materials",
}

# Known government contract parent companies → their public tickers
CONTRACT_COMPANY_TO_TICKER = {
    "LOCKHEED MARTIN": "LMT", "LOCKHEED": "LMT",
    "RAYTHEON": "RTX",        "RTX": "RTX",
    "BOEING": "BA",
    "NORTHROP GRUMMAN": "NOC","NORTHROP": "NOC",
    "GENERAL DYNAMICS": "GD",
    "L3HARRIS": "LHX",        "L3 HARRIS": "LHX",
    "LEIDOS": "LDOS",
    "BOOZ ALLEN": "BAH",
    "SAIC": "SAIC",
    "BAE SYSTEMS": "BA",      # BAE is UK-listed; approximate with Boeing for US proxy
    "HUNTINGTON INGALLS": "HII",
    "GENERAL ELECTRIC": "GE",
    "HUMANA": "HUM",
    "UNITEDHEALTH": "UNH",    "UNITED HEALTH": "UNH",
    "CVS HEALTH": "CVS",      "CVS": "CVS",
    "HCA": "HCA",
    "MICROSOFT": "MSFT",      "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",        "ALPHABET": "GOOGL",
    "PALANTIR": "PLTR",
    "ORACLE": "ORCL",
    "IBM": "IBM",
    "ACCENTURE": "ACN",
}


@dataclass
class WatchlistEntry:
    ticker: str
    company: str
    sector: str
    score: float
    institutional_score: float
    contract_score: float
    momentum_score: float
    conviction_score: float
    buying_institutions: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    recommendation: str = ""
    value_current_total: float = 0.0   # $ held across all 3 institutions
    shares_change_total: int = 0


def _normalize(series: pd.Series, max_val: float) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([max_val / 2] * len(series), index=series.index)
    return (series - mn) / (mx - mn) * max_val


def build_watchlist(
    holdings_changes: pd.DataFrame,
    sector_perf: pd.DataFrame,
    contract_recipients: pd.DataFrame | None = None,
) -> List[WatchlistEntry]:
    """
    Main cross-reference function.
    Returns ranked WatchlistEntry list, highest score first.
    """
    if holdings_changes.empty:
        return []

    # ── Step 1: aggregate institutional signals per ticker ─────────────────────
    buying = holdings_changes[holdings_changes["action"].isin(["NEW", "INCREASED"])]
    held = holdings_changes[holdings_changes["action"] == "HELD"]

    inst_scores: dict[str, dict] = {}

    for _, row in holdings_changes.iterrows():
        ticker = row.get("ticker", "")
        if not ticker or ticker == "nan":
            continue

        if ticker not in inst_scores:
            inst_scores[ticker] = {
                "company": row.get("company", ""),
                "institutions_buying": [],
                "institutions_holding": [],
                "value_total": 0.0,
                "shares_change_total": 0,
                "inst_score": 0.0,
            }

        entry = inst_scores[ticker]
        entry["value_total"] += float(row.get("value_current", 0) or 0)
        entry["shares_change_total"] += int(row.get("shares_change", 0) or 0)

        action = row.get("action", "")
        institution = row.get("institution", "")
        if action in ("NEW", "INCREASED"):
            entry["institutions_buying"].append(institution)
            entry["inst_score"] += 15
        elif action == "HELD":
            entry["institutions_holding"].append(institution)
            entry["inst_score"] += 3

    if not inst_scores:
        return []

    # ── Step 2: contract recipient bonus ──────────────────────────────────────
    contract_tickers: dict[str, float] = {}
    if contract_recipients is not None and not contract_recipients.empty:
        for _, row in contract_recipients.iterrows():
            name_upper = str(row.get("recipient", "")).upper()
            for key, ticker in CONTRACT_COMPANY_TO_TICKER.items():
                if key in name_upper:
                    amount = float(row.get("total_amount", 0) or 0)
                    contract_tickers[ticker] = contract_tickers.get(ticker, 0) + amount

        # Normalize contract amounts to 0-30
        if contract_tickers:
            max_amt = max(contract_tickers.values())
            contract_tickers = {
                t: (v / max_amt) * 30 for t, v in contract_tickers.items()
            }

    # ── Step 3: sector momentum bonus ─────────────────────────────────────────
    sector_score_map: dict[str, float] = {}
    if not sector_perf.empty and "return_pct" in sector_perf.columns:
        perf = sector_perf.copy()
        normalized = _normalize(perf["return_pct"], 15.0)
        for i, row in perf.iterrows():
            sector_score_map[row["sector"]] = float(normalized.iloc[i])  # type: ignore

    # ── Step 4: conviction (position size) bonus ──────────────────────────────
    values = [e["value_total"] for e in inst_scores.values() if e["value_total"] > 0]
    max_val = max(values) if values else 1.0

    # ── Step 5: build final entries ───────────────────────────────────────────
    entries = []
    for ticker, data in inst_scores.items():
        sector = TICKER_SECTOR.get(ticker, "Other")
        inst_score = min(data["inst_score"], 45.0)
        contract_score = contract_tickers.get(ticker, 0.0)
        momentum_score = sector_score_map.get(sector, 5.0)
        conviction_score = (data["value_total"] / max_val) * 10

        total = inst_score + contract_score + momentum_score + conviction_score

        signals = []
        buying_inst = data["institutions_buying"]
        if buying_inst:
            signals.append(f"{'  +  '.join(buying_inst)} {'buying' if len(buying_inst)==1 else 'all buying'}")
        if ticker in contract_tickers:
            signals.append("Major government contractor")
        if momentum_score >= 10:
            signals.append(f"{sector} ETF momentum strong")
        elif momentum_score >= 6:
            signals.append(f"{sector} ETF trending positive")
        if data["shares_change_total"] > 0:
            signals.append(f"+{data['shares_change_total']:,} shares added this quarter")

        if total >= 60:
            rec = "STRONG SIGNAL — converging money flows"
        elif total >= 40:
            rec = "POSITIVE SIGNAL — monitor closely"
        elif total >= 25:
            rec = "MILD SIGNAL — early watch"
        else:
            rec = "WEAK SIGNAL"

        entries.append(WatchlistEntry(
            ticker=ticker,
            company=data["company"],
            sector=sector,
            score=round(total, 1),
            institutional_score=round(inst_score, 1),
            contract_score=round(contract_score, 1),
            momentum_score=round(momentum_score, 1),
            conviction_score=round(conviction_score, 1),
            buying_institutions=buying_inst,
            signals=signals if signals else ["Institutional hold — no new activity"],
            recommendation=rec,
            value_current_total=data["value_total"],
            shares_change_total=data["shares_change_total"],
        ))

    entries.sort(key=lambda x: x.score, reverse=True)
    return entries


def watchlist_to_dataframe(entries: List[WatchlistEntry]) -> pd.DataFrame:
    rows = []
    for e in entries:
        rows.append({
            "Ticker": e.ticker,
            "Company": e.company,
            "Sector": e.sector,
            "Score": e.score,
            "Inst. Score (0-45)": e.institutional_score,
            "Contract Score (0-30)": e.contract_score,
            "Momentum (0-15)": e.momentum_score,
            "Conviction (0-10)": e.conviction_score,
            "Buying Institutions": ", ".join(e.buying_institutions) if e.buying_institutions else "—",
            "Key Signals": " | ".join(e.signals),
            "Recommendation": e.recommendation,
            "Total Held ($)": f"${e.value_current_total:,.0f}",
            "Shares Added": f"+{e.shares_change_total:,}" if e.shares_change_total > 0 else f"{e.shares_change_total:,}",
        })
    return pd.DataFrame(rows)
