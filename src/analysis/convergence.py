"""
Cross-references FlowSignal's three independent signals per ticker:
government deals, insider (boss) buying, and senators' buying.

When more than one kind of smart money points at the same small company,
that's the highest-conviction setup this app can detect — and the thing
no single-source tracker shows. Pure logic — unit-testable offline.
"""


def smart_money_tags(
    ticker: str,
    congress_buy_tickers: set | None = None,
    insider_summary: dict | None = None,
) -> dict:
    """
    Returns {"n_signals": int, "labels": [str, ...]} for one ticker.
    n_signals counts smart-money confirmations BEYOND the gov deal itself.
    """
    labels: list[str] = []
    n = 0

    if insider_summary and insider_summary.get("n_insiders", 0) >= 1:
        n += 1
        who = insider_summary["n_insiders"]
        labels.append(f"🔥 {who} boss{'es' if who > 1 else ''} bought their own stock")

    if congress_buy_tickers and str(ticker).upper() in congress_buy_tickers:
        n += 1
        labels.append("🏛️ Senators bought this too")

    if n >= 2:
        labels.insert(0, "🎯 Multiple smart-money signals agree")

    return {"n_signals": n, "labels": labels}


def congress_buy_set(congress_df) -> set:
    """Tickers senators BOUGHT, from a normalized congress trades frame."""
    if congress_df is None or getattr(congress_df, "empty", True):
        return set()
    if "action" not in congress_df.columns or "ticker" not in congress_df.columns:
        return set()
    buys = congress_df[congress_df["action"] == "BUY"]
    return set(buys["ticker"].astype(str).str.upper())
