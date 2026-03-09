"""
Shared Altair chart builders for Zeitgeist: The Sports Interest Index.
"""

from __future__ import annotations

from typing import List, Optional

import altair as alt
import pandas as pd

# ---------------------------------------------------------------------------
# Premium theme
# ---------------------------------------------------------------------------

CHART_THEME = {
    "color_scheme": "tableau10",
    "accent": "#1D428A",
    "win_color": "#059669",
    "loss_color": "#DC2626",
    "anomaly_color": "#D97706",
    "category_colors": [
        "#1D428A",  # Deep blue (NBA)
        "#BF0D3E",  # Crimson (MLB)
        "#374151",  # Charcoal
        "#059669",  # Emerald
        "#7C3AED",  # Violet
        "#D97706",  # Amber
        "#0891B2",  # Cyan
        "#BE185D",  # Rose
    ],
    "font": "Inter, -apple-system, sans-serif",
    "axis_color": "#D1D5DB",
    "grid_color": "#F0F1F3",
    "background": "#FFFFFF",
}

# ---------------------------------------------------------------------------
# Register global Altair theme
# ---------------------------------------------------------------------------

def _zeitgeist_theme():
    return {
        "config": {
            "background": CHART_THEME["background"],
            "font": CHART_THEME["font"],
            "title": {
                "font": CHART_THEME["font"],
                "fontSize": 14,
                "fontWeight": 600,
                "color": "#1A1A2E",
                "anchor": "start",
                "offset": 12,
            },
            "axis": {
                "labelFont": CHART_THEME["font"],
                "labelFontSize": 11,
                "labelColor": "#6B7280",
                "titleFont": CHART_THEME["font"],
                "titleFontSize": 12,
                "titleFontWeight": 500,
                "titleColor": "#374151",
                "gridColor": CHART_THEME["grid_color"],
                "gridDash": [3, 3],
                "gridOpacity": 0.8,
                "domainColor": CHART_THEME["axis_color"],
                "tickColor": CHART_THEME["axis_color"],
            },
            "legend": {
                "labelFont": CHART_THEME["font"],
                "labelFontSize": 11,
                "titleFont": CHART_THEME["font"],
                "titleFontSize": 12,
                "titleFontWeight": 500,
                "orient": "bottom",
                "direction": "horizontal",
                "symbolSize": 80,
                "padding": 10,
            },
            "view": {
                "stroke": "transparent",
                "continuousWidth": 600,
                "continuousHeight": 400,
            },
            "range": {
                "category": CHART_THEME["category_colors"],
            },
            "bar": {
                "cornerRadiusTopLeft": 4,
                "cornerRadiusTopRight": 4,
            },
            "line": {
                "strokeWidth": 2.5,
            },
            "point": {
                "filled": True,
                "size": 60,
            },
        }
    }


alt.themes.register("zeitgeist", _zeitgeist_theme)
alt.themes.enable("zeitgeist")


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
    """Ranked bar chart with gradient colour."""
    tooltips = tooltip_cols or [x, alt.Tooltip(f"{y}:Q", format=".1f")]
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(f"{x}:N", sort="-y", title=None),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            color=alt.Color(
                f"{y}:Q",
                scale=alt.Scale(range=["#93C5FD", "#1D428A"]),
                legend=None,
            ),
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
    """Multi-series line chart (one line per team)."""
    tooltips = tooltip_cols or [
        f"{x}:T",
        f"{color}:N",
        alt.Tooltip(f"{y}:Q", format=".1f"),
    ]
    return (
        alt.Chart(df)
        .mark_line(interpolate="monotone", strokeWidth=2.5)
        .encode(
            x=alt.X(f"{x}:T"),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            color=alt.Color(
                f"{color}:N",
                scale=alt.Scale(range=CHART_THEME["category_colors"]),
            ),
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
    """Line chart with W/L game-result annotations.

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
            .mark_point(
                shape="triangle-up", size=120, filled=True,
                stroke="#FFFFFF", strokeWidth=1,
            )
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
            .mark_point(
                shape="triangle-down", size=120, filled=True,
                stroke="#FFFFFF", strokeWidth=1,
            )
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
    """Line chart with anomalous points highlighted."""
    base = (
        alt.Chart(df)
        .mark_line(interpolate="monotone", strokeWidth=2.5)
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
        .mark_circle(size=140, stroke=CHART_THEME["anomaly_color"], strokeWidth=2)
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
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(f"{group}:N", title=None),
            y=alt.Y(f"{y}:Q", title=y.replace("_", " ").title()),
            color=alt.Color(
                f"{x}:N",
                scale=alt.Scale(range=CHART_THEME["category_colors"]),
            ),
            xOffset=alt.XOffset(f"{x}:N"),
            tooltip=[f"{x}:N", f"{group}:N", alt.Tooltip(f"{y}:Q", format=".1f")],
        )
        .properties(height=height, title=title)
    )
