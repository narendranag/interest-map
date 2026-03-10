"""
Zeitgeist | Head to Head — compare 2-5 teams side by side across all metrics.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.charts import grouped_bar_chart, line_chart
from lib.db import query, table_exists
from lib.scoring import normalize_min_max
from lib.styles import apply_premium_theme, section_header
from lib.teams import ALL_TEAMS, TEAM_TO_LEAGUE

st.set_page_config(page_title="Zeitgeist | Head to Head", layout="wide")
apply_premium_theme()

st.markdown('<h1>Head to Head</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="zg-subtitle">Compare 2-5 teams side by side across every metric</p>',
    unsafe_allow_html=True,
)

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

if table_exists("news"):
    df = query(
        f"SELECT team, SUM(article_count) AS articles "
        f"FROM news WHERE team IN ({team_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY GROUP BY team"
    )
    if not df.empty:
        metric_series["News"] = normalize_min_max(df.set_index("team")["articles"])

# --- Additional sources ---

if table_exists("attendance"):
    df = query(
        f"SELECT team, AVG(attendance_pct) AS att "
        f"FROM attendance WHERE team IN ({team_sql}) "
        f"AND attendance_pct IS NOT NULL "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY GROUP BY team"
    )
    if not df.empty:
        metric_series["Attendance"] = normalize_min_max(df.set_index("team")["att"])

if table_exists("tickets"):
    df = query(
        f"SELECT team, AVG(avg_price) AS price "
        f"FROM tickets WHERE team IN ({team_sql}) "
        f"AND avg_price IS NOT NULL GROUP BY team"
    )
    if not df.empty:
        metric_series["Tickets"] = normalize_min_max(df.set_index("team")["price"])

if table_exists("youtube"):
    df = query(
        f"SELECT team, MAX(subscribers) AS yt_subs "
        f"FROM youtube WHERE team IN ({team_sql}) GROUP BY team"
    )
    if not df.empty:
        metric_series["YouTube"] = normalize_min_max(df.set_index("team")["yt_subs"])

if table_exists("betting"):
    df = query(
        f"SELECT team, AVG(implied_win_prob) AS prob "
        f"FROM betting WHERE team IN ({team_sql}) "
        f"AND implied_win_prob IS NOT NULL "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY GROUP BY team"
    )
    if not df.empty:
        metric_series["Betting"] = normalize_min_max(df.set_index("team")["prob"])

# ---------------------------------------------------------------------------
# Side-by-side metric table
# ---------------------------------------------------------------------------

if metric_series:
    section_header("Metric Comparison", f"Averages over the last {window} days")

    comparison = pd.DataFrame(metric_series).reindex(selected).fillna(0)
    comparison.index.name = "Team"

    st.dataframe(
        comparison.style.format("{:.1f}"),
        use_container_width=True,
    )

    # Grouped bar chart
    bar_data = comparison.reset_index().melt(
        id_vars="Team", var_name="Metric", value_name="Score"
    )
    st.altair_chart(
        grouped_bar_chart(
            bar_data, "Team", "Score", "Metric",
            title="Head-to-Head Comparison",
        ),
        use_container_width=True,
    )
else:
    st.info("No metric data available yet for the selected teams.")

# ---------------------------------------------------------------------------
# Trendline tabs
# ---------------------------------------------------------------------------

section_header("Trendlines")

trend_sources = {
    "Wikipedia": ("wikipedia", "wiki_views"),
    "News": ("news", "article_count"),
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
