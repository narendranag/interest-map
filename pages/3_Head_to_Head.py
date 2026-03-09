"""
Head to Head — compare 2-5 teams side by side across all metrics.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.charts import grouped_bar_chart, line_chart
from lib.db import query, table_exists
from lib.scoring import normalize_min_max
from lib.teams import ALL_TEAMS, TEAM_TO_LEAGUE

st.set_page_config(page_title="Head to Head", layout="wide")
st.title("Head to Head")

# ---------------------------------------------------------------------------
# Team selection
# ---------------------------------------------------------------------------

selected = st.multiselect(
    "Select 2-5 teams to compare",
    ALL_TEAMS,
    default=ALL_TEAMS[:2],
    max_selections=5,
)

if len(selected) < 2:
    st.info("Pick at least two teams to compare.")
    st.stop()

window = st.sidebar.slider("Time window (days)", 7, 90, 30, step=7)
team_sql = ", ".join(f"'{t}'" for t in selected)

# ---------------------------------------------------------------------------
# Load & normalise metrics
# ---------------------------------------------------------------------------

metric_series = {}

if table_exists("trends"):
    df = query(
        f"SELECT date, team, trends_score FROM trends "
        f"WHERE team IN ({team_sql}) AND date >= CURRENT_DATE - INTERVAL '{window}' DAY"
    )
    if not df.empty:
        avg = df.groupby("team")["trends_score"].mean()
        metric_series["Google Trends"] = normalize_min_max(avg)

if table_exists("wikipedia"):
    df = query(
        f"SELECT date, team, wiki_views FROM wikipedia "
        f"WHERE team IN ({team_sql}) AND date >= CURRENT_DATE - INTERVAL '{window}' DAY"
    )
    if not df.empty:
        avg = df.groupby("team")["wiki_views"].mean()
        metric_series["Wikipedia"] = normalize_min_max(avg)

if table_exists("espn_games"):
    df = query(
        f"SELECT team, "
        f"  COUNT(*) FILTER (WHERE result='W') * 100.0 / NULLIF(COUNT(*) FILTER (WHERE result IS NOT NULL), 0) AS win_pct "
        f"FROM espn_games WHERE team IN ({team_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY GROUP BY team"
    )
    if not df.empty:
        metric_series["Win %"] = df.set_index("team")["win_pct"].fillna(0)

if table_exists("reddit"):
    df = query(
        f"SELECT team, SUM(post_count + total_comments) AS engagement "
        f"FROM reddit WHERE team IN ({team_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY GROUP BY team"
    )
    if not df.empty:
        metric_series["Reddit"] = normalize_min_max(df.set_index("team")["engagement"])

if table_exists("news"):
    df = query(
        f"SELECT team, SUM(article_count) AS articles "
        f"FROM news WHERE team IN ({team_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY GROUP BY team"
    )
    if not df.empty:
        metric_series["News"] = normalize_min_max(df.set_index("team")["articles"])

# ---------------------------------------------------------------------------
# Side-by-side metric table
# ---------------------------------------------------------------------------

if metric_series:
    st.subheader("Metric Comparison (latest window)")
    comparison = pd.DataFrame(metric_series).reindex(selected).fillna(0)
    comparison.index.name = "Team"
    st.dataframe(comparison.style.format("{:.1f}"), use_container_width=True)

    # Grouped bar chart
    bar_data = comparison.reset_index().melt(
        id_vars="Team", var_name="Metric", value_name="Score"
    )
    st.altair_chart(
        grouped_bar_chart(bar_data, "Team", "Score", "Metric",
                          title="Head-to-Head Comparison"),
        use_container_width=True,
    )
else:
    st.info("No metric data available yet for the selected teams.")

# ---------------------------------------------------------------------------
# Trendline tabs
# ---------------------------------------------------------------------------

st.subheader("Trendlines")

trend_sources = {
    "Google Trends": ("trends", "trends_score"),
    "Wikipedia": ("wikipedia", "wiki_views"),
}

tabs = st.tabs(list(trend_sources.keys()))

for tab, (label, (tbl, col)) in zip(tabs, trend_sources.items()):
    with tab:
        if table_exists(tbl):
            df = query(
                f"SELECT date, team, {col} AS value FROM {tbl} "
                f"WHERE team IN ({team_sql}) "
                f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY "
                f"ORDER BY date"
            )
            if not df.empty:
                st.altair_chart(
                    line_chart(df, "date", "value", "team", title=label),
                    use_container_width=True,
                )
            else:
                st.caption(f"No {label} data in this window.")
        else:
            st.caption(f"{label} data not loaded.")
