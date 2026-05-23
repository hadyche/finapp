"""
Cross-references government contract recipients with institutional buying
to produce a ranked stock watchlist with signal explanations.

Scoring (0-100 base, small/mid caps get size multipliers):
  - Institutional buying pressure  : up to 45 pts
      +15 per institution with INCREASED/NEW position
      +5  per institution with HELD (large position)
      Small caps get 1.5x multiplier on NEW positions (more meaningful signal)
      Mid caps get 1.2x multiplier on NEW positions
  - Government contract exposure   : up to 30 pts
  - Market momentum (sector ETF)   : up to 15 pts
  - Position conviction (size)     : up to 10 pts

DISCLAIMER: Informational only. Not financial advice.
"""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field
from typing import List

from src.data.sec_holdings import TICKER_SIZE


TICKER_SECTOR = {
    # Defense & Gov IT
    "LMT": "Defense",  "RTX": "Defense",  "NOC": "Defense",  "GD": "Defense",
    "BA":  "Defense",  "LHX": "Defense",  "LDOS": "Defense", "BAH": "Defense",
    "SAIC":"Defense",  "HII": "Defense",  "TDG": "Defense",  "CW":  "Defense",
    "CACI":"Defense",  "PSN": "Defense",  "KTOS":"Defense",  "MRCY":"Defense",
    "BWXT":"Defense",  "AVAV":"Defense",  "MOOG":"Defense",  "V2X": "Defense",
    "VSE": "Defense",  "TLS": "Defense",  "BBAI":"Defense",  "MANT":"Defense",
    "DCO": "Defense",  "TGI": "Defense",  "KAMN":"Defense",  "LEU": "Defense",
    # Technology
    "AAPL":"Technology","MSFT":"Technology","NVDA":"Technology","AVGO":"Technology",
    "ORCL":"Technology","IBM": "Technology","INTC":"Technology","AMD": "Technology",
    "QCOM":"Technology","PLTR":"Technology","NOW": "Technology","INTU":"Technology",
    "SMR": "Technology",
    # Healthcare & Gov Health Services
    "UNH": "Healthcare","JNJ": "Healthcare","LLY": "Healthcare","ABBV":"Healthcare",
    "PFE": "Healthcare","MRK": "Healthcare","HCA": "Healthcare","CVS": "Healthcare",
    "ELV": "Healthcare","MOH": "Healthcare","ISRG":"Healthcare","MMS": "Healthcare",
    "ICFI":"Healthcare","OPCH":"Healthcare","ADUS":"Healthcare",
    # Financials
    "JPM": "Financials","BAC": "Financials","GS":  "Financials","WFC": "Financials",
    "AXP": "Financials","PNC": "Financials","SCHW":"Financials","BLK": "Financials",
    # Industrials & Construction
    "HON": "Industrials","CAT":"Industrials","URI": "Industrials","PCAR":"Industrials",
    "ACM": "Industrials","GVA":"Industrials","PRIM":"Industrials","DY":  "Industrials",
    "MYRG":"Industrials","TTEK":"Industrials","BBCP":"Industrials",
    # Consumer
    "AMZN":"Consumer Disc.","TSLA":"Consumer Disc.","MCD":"Consumer Staples",
    "WMT": "Consumer Staples","KO":"Consumer Staples","PG":"Consumer Staples",
    "COST":"Consumer Staples",
    # Energy
    "XOM": "Energy","CVX":"Energy","SLB":"Energy","HAL":"Energy",
    # Communication
    "META":"Communication","GOOGL":"Communication","GOOG":"Communication",
    "VZ":  "Communication",
}

# Known government contract parent companies → their public tickers
CONTRACT_COMPANY_TO_TICKER = {
    # Large / well-known
    "LOCKHEED MARTIN": "LMT",  "LOCKHEED": "LMT",
    "RAYTHEON": "RTX",         "RTX CORP": "RTX",
    "BOEING": "BA",
    "NORTHROP GRUMMAN": "NOC", "NORTHROP": "NOC",
    "GENERAL DYNAMICS": "GD",
    "L3HARRIS": "LHX",         "L3 HARRIS": "LHX",
    "LEIDOS": "LDOS",
    "BOOZ ALLEN": "BAH",
    "SAIC": "SAIC",
    "HUNTINGTON INGALLS": "HII",
    "BAE SYSTEMS": "HII",      # BAE US subsidiary, proxy
    "MICROSOFT": "MSFT",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",         "ALPHABET": "GOOGL",
    "PALANTIR": "PLTR",
    "ORACLE": "ORCL",
    "IBM": "IBM",
    # Mid cap — the ones most people don't know
    "CACI": "CACI",            "CACI INTERNATIONAL": "CACI",
    "PARSONS": "PSN",          "PARSONS CORP": "PSN",
    "KRATOS": "KTOS",          "KRATOS DEFENSE": "KTOS",
    "BWX TECHNOLOGIES": "BWXT","BWXT": "BWXT",
    "MAXIMUS": "MMS",
    "ICF": "ICFI",             "ICF INTERNATIONAL": "ICFI",
    "TETRA TECH": "TTEK",
    "AECOM": "ACM",
    "AEROVIRONMENT": "AVAV",
    "MOOG": "MOOG",            "MOOG INC": "MOOG",
    "VECTRUS": "V2X",          "V2X": "V2X",
    "VSE CORP": "VSE",         "VSE CORPORATION": "VSE",
    "GRANITE CONSTRUCTION": "GVA",
    "PRIMORIS": "PRIM",
    "DYCOM": "DY",
    "MYR GROUP": "MYRG",
    "OPTION CARE": "OPCH",
    "ADDUS": "ADUS",
    "AXON": "AXON",
    # Small cap — the real hidden gems
    "MERCURY SYSTEMS": "MRCY", "MERCURY": "MRCY",
    "TELOS": "TLS",            "TELOS CORP": "TLS",
    "BIGBEAR": "BBAI",         "BIGBEAR.AI": "BBAI",
    "CENTRUS ENERGY": "LEU",   "CENTRUS": "LEU",
    "NUSCALE": "SMR",          "NUSCALE POWER": "SMR",
    "DUCOMMUN": "DCO",
    "TRIUMPH GROUP": "TGI",
    "KAMAN": "KAMN",
    "MANTECH": "MANT",         "MANTECH INTERNATIONAL": "MANT",
    "CURTISS-WRIGHT": "CW",    "CURTISS WRIGHT": "CW",
    "KFORCE": "KFRC",
    "ACCENTURE FEDERAL": "ACN",
    "HUMANA": "HUM",
    "UNITEDHEALTH": "UNH",
    "HCA": "HCA",
    "EXLSERVICE": "EXLS",
}

SIZE_LABELS = {"small": "🔹 Small Cap", "mid": "🔸 Mid Cap", "large": "⬜ Large Cap"}

# How much to multiply institutional NEW position score by size tier
SIZE_MULTIPLIER = {"small": 2.0, "mid": 1.4, "large": 1.0}


@dataclass
class WatchlistEntry:
    ticker: str
    company: str
    sector: str
    size: str                  # small / mid / large
    score: float
    institutional_score: float
    contract_score: float
    momentum_score: float
    conviction_score: float
    buying_institutions: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    recommendation: str = ""
    value_current_total: float = 0.0
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
    hidden_gems_only: bool = False,
) -> List[WatchlistEntry]:
    """
    Returns ranked WatchlistEntry list, highest score first.
    hidden_gems_only: if True, excludes large-cap stocks.
    """
    if holdings_changes.empty:
        return []

    # ── Step 1: aggregate institutional signals per ticker ─────────────────────
    inst_scores: dict[str, dict] = {}

    for _, row in holdings_changes.iterrows():
        ticker = str(row.get("ticker", "") or "").strip()
        if not ticker or ticker == "nan":
            continue

        size = TICKER_SIZE.get(ticker, "large")
        if hidden_gems_only and size == "large":
            continue

        if ticker not in inst_scores:
            inst_scores[ticker] = {
                "company": str(row.get("company", "") or ticker),
                "institutions_buying": [],
                "value_total": 0.0,
                "shares_change_total": 0,
                "inst_score": 0.0,
                "size": size,
            }

        entry = inst_scores[ticker]
        entry["value_total"] += float(row.get("value_current", 0) or 0)
        entry["shares_change_total"] += int(row.get("shares_change", 0) or 0)

        action = str(row.get("action", ""))
        institution = str(row.get("institution", ""))
        multiplier = SIZE_MULTIPLIER.get(size, 1.0)

        if action == "NEW":
            entry["institutions_buying"].append(institution)
            entry["inst_score"] += 15 * multiplier   # small cap NEW = 30pts each!
        elif action == "INCREASED":
            entry["institutions_buying"].append(institution)
            entry["inst_score"] += 12 * multiplier
        elif action == "HELD":
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

        if contract_tickers:
            max_amt = max(contract_tickers.values())
            contract_tickers = {t: (v / max_amt) * 30 for t, v in contract_tickers.items()}

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
        size = data["size"]
        sector = TICKER_SECTOR.get(ticker, "Other")
        inst_score = min(data["inst_score"], 60.0)   # allow small caps to score higher
        contract_score = contract_tickers.get(ticker, 0.0)
        momentum_score = sector_score_map.get(sector, 5.0)
        conviction_score = (data["value_total"] / max_val) * 10

        total = inst_score + contract_score + momentum_score + conviction_score

        signals = []
        buying_inst = data["institutions_buying"]
        if buying_inst:
            verb = "opening NEW position" if len(buying_inst) == 1 else "all opening/increasing"
            signals.append(f"{' + '.join(buying_inst)} {verb}")
        if ticker in contract_tickers:
            signals.append("Government contract recipient")
        if size == "small":
            signals.append("Small cap — under-the-radar")
        elif size == "mid":
            signals.append("Mid cap — less covered")
        if momentum_score >= 10:
            signals.append(f"{sector} sector momentum strong")
        if data["shares_change_total"] > 0:
            signals.append(f"+{data['shares_change_total']:,} shares added this quarter")

        if total >= 60:
            rec = "STRONG SIGNAL"
        elif total >= 40:
            rec = "POSITIVE SIGNAL"
        elif total >= 25:
            rec = "WATCH"
        else:
            rec = "WEAK"

        entries.append(WatchlistEntry(
            ticker=ticker,
            company=data["company"],
            sector=sector,
            size=size,
            score=round(min(total, 100), 1),
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
            "Size": SIZE_LABELS.get(e.size, e.size),
            "Sector": e.sector,
            "Score": e.score,
            "Inst. Score": e.institutional_score,
            "Contract": e.contract_score,
            "Momentum": e.momentum_score,
            "Conviction": e.conviction_score,
            "Buying Institutions": ", ".join(e.buying_institutions) if e.buying_institutions else "—",
            "Key Signals": " | ".join(e.signals),
            "Signal": e.recommendation,
            "Total Held ($)": f"${e.value_current_total:,.0f}",
            "Shares Added": f"+{e.shares_change_total:,}" if e.shares_change_total > 0 else f"{e.shares_change_total:,}",
        })
    return pd.DataFrame(rows)
