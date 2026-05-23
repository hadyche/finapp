"""Reusable Plotly chart builders for the Streamlit dashboard."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


SCORE_COLORS = {
    "STRONG BUY SIGNAL": "#00C853",
    "POSITIVE SIGNAL": "#64DD17",
    "NEUTRAL — monitor": "#FFD600",
    "WEAK SIGNAL": "#FF6D00",
}


def sector_bar_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str = None):
    fig = px.bar(
        df,
        x=x,
        y=y,
        title=title,
        color=color or y,
        color_continuous_scale="RdYlGn",
        template="plotly_dark",
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=400,
    )
    return fig


def score_heatmap(scores_df: pd.DataFrame):
    cols = ["Gov Contracts (0-40)", "Market Momentum (0-40)", "Institutional Activity (0-20)"]
    available = [c for c in cols if c in scores_df.columns]
    if not available:
        return go.Figure()

    z = scores_df[available].values.tolist()
    y = scores_df["Sector"].tolist()

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=available,
            y=y,
            colorscale="RdYlGn",
            zmin=0,
            zmax=40,
        )
    )
    fig.update_layout(
        title="Signal Heatmap by Sector",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=500,
    )
    return fig


def sector_momentum_chart(perf_df: pd.DataFrame):
    if perf_df.empty:
        return go.Figure()
    sorted_df = perf_df.sort_values("return_pct")
    colors = ["#00C853" if v >= 0 else "#FF6D00" for v in sorted_df["return_pct"]]

    fig = go.Figure(
        go.Bar(
            x=sorted_df["return_pct"],
            y=sorted_df["sector"],
            orientation="h",
            marker_color=colors,
        )
    )
    fig.update_layout(
        title="Sector ETF Performance (%)",
        xaxis_title="Return %",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
    )
    return fig


def price_history_chart(history_df: pd.DataFrame, sector: str):
    if history_df.empty:
        return go.Figure()

    fig = px.line(
        history_df,
        x="date",
        y="price",
        title=f"{sector} ETF Price History",
        template="plotly_dark",
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=350,
    )
    return fig


def contract_treemap(sector_summary: pd.DataFrame):
    if sector_summary.empty:
        return go.Figure()

    fig = px.treemap(
        sector_summary,
        path=["sector"],
        values="total_amount",
        title="Government Contract $ by Sector",
        color="total_amount",
        color_continuous_scale="Blues",
        template="plotly_dark",
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
    )
    return fig


def indicators_gauge_row(indicators_df: pd.DataFrame):
    """Returns a figure with small gauges for key indicators."""
    key_indicators = ["Unemployment", "Fed Funds Rate", "10Y Treasury", "Consumer Sentiment"]
    rows = indicators_df[indicators_df["indicator"].isin(key_indicators)]
    if rows.empty:
        return go.Figure()

    fig = go.Figure()
    for i, (_, row) in enumerate(rows.iterrows()):
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=row["value"],
                title={"text": row["indicator"], "font": {"size": 12}},
                domain={"row": 0, "column": i},
            )
        )

    fig.update_layout(
        grid={"rows": 1, "columns": len(rows), "pattern": "independent"},
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=200,
    )
    return fig
