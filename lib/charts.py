"""
Shared Altair chart builders for all dashboard pages.
"""

from __future__ import annotations

from typing import List, Optional

import altair as alt
import pandas as pd

# ---------------------------------------------------------------------------
# Global theme
# ---------------------------------------------------------------------------

CHART_THEME = {
    "color_scheme": "tableau10",
    "accent": "#1f77b4",
    "win_color": "#2ca02c",
    "loss_color": "#d62728",
    "anomaly_color": "#ff7f0e",
}


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    tooltip_cols: Optional[List[str]] = None,
    height: int = 400,
    title: str = "",
) -> alt.Chart:
    """Horizontal or vertical ranked bar chart."""
    tooltips = tooltip_cols or [x, alt.Tooltip(f"{y}:Q", format=".2f")]
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(f"{x}:N", sort="-y", title=None),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            color=alt.Color(f"{y}:Q", scale=alt.Scale(scheme="blues"), legend=None),
            tooltip=tooltips,
        )
        .properties(height=height, title=title)
    )


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    tooltip_cols: Optional[List[str]] = None,
    height: int = 420,
    title: str = "",
) -> alt.Chart:
    """Multi-series line chart (e.g. one line per team)."""
    tooltips = tooltip_cols or [
        f"{x}:T",
        f"{color}:N",
        alt.Tooltip(f"{y}:Q", format=".1f"),
    ]
    return (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X(f"{x}:T"),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            color=alt.Color(f"{color}:N"),
            tooltip=tooltips,
        )
        .properties(height=height, title=title)
    )


def line_chart_with_annotations(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    annotations_df: Optional[pd.DataFrame] = None,
    height: int = 420,
    title: str = "",
) -> alt.LayerChart:
    """Line chart with optional W/L game-result annotations.

    *annotations_df* should have columns: ``date``, ``result`` ("W" or "L"),
    and a *y* column for vertical placement.
    """
    base = line_chart(df, x, y, color, height=height, title=title)

    if annotations_df is None or annotations_df.empty:
        return base

    wins = annotations_df[annotations_df["result"] == "W"]
    losses = annotations_df[annotations_df["result"] == "L"]

    layers = [base]

    if not wins.empty:
        win_pts = (
            alt.Chart(wins)
            .mark_point(shape="triangle-up", size=100, filled=True)
            .encode(
                x=f"{x}:T",
                y=alt.Y(f"{y}:Q"),
                color=alt.value(CHART_THEME["win_color"]),
                tooltip=["date:T", "opponent:N", "result:N"],
            )
        )
        layers.append(win_pts)

    if not losses.empty:
        loss_pts = (
            alt.Chart(losses)
            .mark_point(shape="triangle-down", size=100, filled=True)
            .encode(
                x=f"{x}:T",
                y=alt.Y(f"{y}:Q"),
                color=alt.value(CHART_THEME["loss_color"]),
                tooltip=["date:T", "opponent:N", "result:N"],
            )
        )
        layers.append(loss_pts)

    return alt.layer(*layers).properties(height=height)


def anomaly_highlight_chart(
    df: pd.DataFrame,
    x: str = "date",
    y: str = "interest_score",
    anomaly_col: str = "is_anomaly",
    height: int = 400,
    title: str = "",
) -> alt.LayerChart:
    """Line chart with anomalous points highlighted in orange."""
    base = (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X(f"{x}:T"),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            tooltip=[f"{x}:T", alt.Tooltip(f"{y}:Q", format=".1f")],
        )
    )

    anomalies = df[df[anomaly_col]]
    if anomalies.empty:
        return base.properties(height=height, title=title)

    pts = (
        alt.Chart(anomalies)
        .mark_circle(size=120)
        .encode(
            x=f"{x}:T",
            y=f"{y}:Q",
            color=alt.value(CHART_THEME["anomaly_color"]),
            tooltip=[
                f"{x}:T",
                alt.Tooltip(f"{y}:Q", format=".1f"),
                alt.Tooltip("z_score:Q", format=".2f"),
            ],
        )
    )

    return alt.layer(base, pts).properties(height=height, title=title)


def grouped_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    group: str,
    height: int = 400,
    title: str = "",
) -> alt.Chart:
    """Grouped bar chart for head-to-head metric comparison."""
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(f"{group}:N", title=None),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            color=alt.Color(f"{x}:N"),
            xOffset=alt.XOffset(f"{x}:N"),
            tooltip=[f"{x}:N", f"{group}:N", alt.Tooltip(f"{y}:Q", format=".1f")],
        )
        .properties(height=height, title=title)
    )
