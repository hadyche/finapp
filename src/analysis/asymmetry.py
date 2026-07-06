"""
The core FlowSignal idea: surface events that are LARGE relative to the
company. An $84M contract is noise to Lockheed but 22% of a $380M
company's entire market value.

Pure logic — no network calls — so it is fully unit-testable offline.
"""

import math
import pandas as pd

# Hard ceiling: no company above this market cap is ever shown.
# The S&P 500 minimum is ~$15B+, so $5B guarantees zero household names.
DEFAULT_MAX_CAP = 5_000_000_000
# An award must be at least this fraction of market cap to matter.
DEFAULT_MIN_RATIO = 0.01
# Awards above this multiple of market cap are near-certainly a
# name-matching error (a $1.6B contract does not go to a $176M company),
# so they are dropped rather than shown as a 900% "opportunity".
DEFAULT_MAX_RATIO = 2.0


def compute_impact_ratio(award_amount, market_cap) -> float | None:
    """award $ ÷ market cap. None when either side is missing/invalid."""
    try:
        if award_amount is None or market_cap is None:
            return None
        if pd.isna(award_amount) or pd.isna(market_cap):
            return None
        award = float(award_amount)
        cap = float(market_cap)
        if award <= 0 or cap <= 0:
            return None
        return award / cap
    except (TypeError, ValueError):
        return None


def build_contract_signals(
    awards: pd.DataFrame,
    caps: dict,
    max_cap: float = DEFAULT_MAX_CAP,
    min_ratio: float = DEFAULT_MIN_RATIO,
    max_ratio: float = DEFAULT_MAX_RATIO,
) -> pd.DataFrame:
    """
    Aggregates matched contract awards into per-ticker signals.

    awards: DataFrame with columns [ticker, matched_name, confidence,
            recipient, amount, agency, date, award_id]
            (rows with no ticker are ignored)
    caps:   {ticker: market_cap or None} — tickers with unknown caps are
            EXCLUDED, never guessed.

    Returns DataFrame sorted by impact_ratio desc with columns:
      ticker, matched_name, confidence, market_cap, total_awarded,
      largest_award, agency, date, n_awards, impact_ratio
    """
    empty_cols = ["ticker", "matched_name", "confidence", "market_cap",
                  "total_awarded", "largest_award", "agency", "date",
                  "n_awards", "impact_ratio"]
    if awards is None or awards.empty or "ticker" not in awards.columns:
        return pd.DataFrame(columns=empty_cols)

    df = awards.dropna(subset=["ticker"]).copy()
    if df.empty:
        return pd.DataFrame(columns=empty_cols)

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df = df[df["amount"] > 0]
    if "award_id" in df.columns:
        df = df.drop_duplicates(subset=["ticker", "award_id"])

    rows = []
    for ticker, grp in df.groupby("ticker"):
        cap = caps.get(ticker)
        ratio = compute_impact_ratio(grp["amount"].sum(), cap)
        if ratio is None:
            continue  # unknown market cap → excluded
        if float(cap) > max_cap or ratio < min_ratio or ratio > max_ratio:
            continue
        top = grp.loc[grp["amount"].idxmax()]

        def _s(key):  # None/NaN → "" so the UI never shows the word "None"
            v = top.get(key)
            return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

        rows.append({
            "ticker": ticker,
            "matched_name": _s("matched_name"),
            "confidence": _s("confidence"),
            "market_cap": float(cap),
            "total_awarded": float(grp["amount"].sum()),
            "largest_award": float(top["amount"]),
            "agency": _s("agency"),
            "date": _s("date"),
            "n_awards": int(len(grp)),
            "impact_ratio": float(ratio),
        })

    out = pd.DataFrame(rows, columns=empty_cols)
    if out.empty:
        return out
    return out.sort_values("impact_ratio", ascending=False).reset_index(drop=True)


def score_signal_row(
    impact_ratio: float,
    days_since_award: float | None,
    pct_change_since: float | None,
    adv_usd: float | None,
    confidence: str = "",
    n_smart_signals: int = 0,
) -> tuple[float, list[str]]:
    """
    Combines everything we know about a pick into one 0-100 Signal
    Strength score, with plain-language reasons. Pure — unit-testable.

    Components:
      deal size vs company   up to 45  (25%+ of company value maxes it)
      freshness              up to 15  (decays over ~a month)
      not priced in yet      up to 15  (0 if the stock already jumped 25%+)
      easy to trade          up to 10
      exact name match       up to  5
      smart money agrees     up to 20  (insiders / senators buying too)
    """
    score = 0.0
    reasons: list[str] = []

    ratio_pts = min(float(impact_ratio) / 0.25, 1.0) * 45
    score += ratio_pts
    reasons.append(f"Deal = {impact_ratio*100:.0f}% of the whole company")

    if days_since_award is not None and days_since_award >= 0:
        fresh_pts = 15 * math.exp(-float(days_since_award) / 30)
        score += fresh_pts
        if days_since_award <= 7:
            reasons.append(f"Signed {int(days_since_award)} day{'s' if days_since_award != 1 else ''} ago — very fresh")

    if pct_change_since is None:
        score += 5  # unknown reaction — mildly positive (nobody noticed?)
    elif pct_change_since < 10:
        score += 15
        reasons.append("Stock has barely moved yet — the market may not have noticed")
    elif pct_change_since < 25:
        score += 7
    else:
        reasons.append(f"Already jumped +{pct_change_since:.0f}% — you may be late")

    if adv_usd is not None and adv_usd >= 1_000_000:
        score += 10
    elif adv_usd is not None:
        reasons.append("⚠ Hard to trade — very few daily buyers/sellers")

    if str(confidence) == "exact":
        score += 5

    if n_smart_signals > 0:
        score += min(int(n_smart_signals), 2) * 10
        reasons.append("🎯 Smart money is buying this too")

    return min(round(score, 1), 100.0), reasons


def rank_signals(*frames: pd.DataFrame) -> pd.DataFrame:
    """Merges signal frames (contract, insider, activist...) and re-ranks."""
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    return merged.sort_values("impact_ratio", ascending=False).reset_index(drop=True)


def _fmt_dollars(v: float) -> str:
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v/1e3:.0f}K"


def format_asymmetry_line(row) -> str:
    """One sentence stating why this matters: the size mismatch."""
    total = float(row["total_awarded"])
    ratio = float(row["impact_ratio"])
    n = int(row.get("n_awards", 1))
    what = f"{_fmt_dollars(total)} in federal awards" if n > 1 else \
           f"Won a {_fmt_dollars(total)} federal contract"
    return f"{what} = {ratio*100:.0f}% of its market cap"
