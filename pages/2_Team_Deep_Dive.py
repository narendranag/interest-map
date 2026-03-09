"""
Team Deep Dive — single-team analysis with game results, Victory+
availability, Reddit buzz, and news volume.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.charts import anomaly_highlight_chart, line_chart_with_annotations
from lib.db import query, table_exists
from lib.scoring import detect_anomalies, normalize_min_max
from lib.teams import ALL_TEAMS, TEAM_TO_LEAGUE, VICTORY_PLUS_TEAMS

st.set_page_config(page_title="Team Deep Dive", layout="wide")
st.title("Team Deep Dive")

# ---------------------------------------------------------------------------
# Team selector
# ---------------------------------------------------------------------------

team = st.selectbox("Select a team", ALL_TEAMS, index=0)
league = TEAM_TO_LEAGUE.get(team, "")

col_a, col_b = st.columns(2)
col_a.markdown(f"**League:** {league}")
if team in VICTORY_PLUS_TEAMS:
    col_b.markdown(":tv: **Victory+ partner** — some home games stream free on Victory+")

# ---------------------------------------------------------------------------
# Trendlines — all metrics overlaid
# ---------------------------------------------------------------------------

st.subheader("Interest Trendlines")

frames = []

if table_exists("trends"):
    t = query(
        f"SELECT date, trends_score AS value, 'Google Trends' AS metric "
        f"FROM trends WHERE team = '{team}' ORDER BY date"
    )
    if not t.empty:
        t["value"] = normalize_min_max(t["value"])
        frames.append(t)

if table_exists("wikipedia"):
    w = query(
        f"SELECT date, wiki_views AS value, 'Wikipedia' AS metric "
        f"FROM wikipedia WHERE team = '{team}' ORDER BY date"
    )
    if not w.empty:
        w["value"] = normalize_min_max(w["value"])
        frames.append(w)

if table_exists("reddit"):
    r = query(
        f"SELECT date, (post_count + total_comments) AS value, 'Reddit' AS metric "
        f"FROM reddit WHERE team = '{team}' ORDER BY date"
    )
    if not r.empty:
        r["value"] = normalize_min_max(r["value"])
        frames.append(r)

if table_exists("news"):
    n = query(
        f"SELECT date, article_count AS value, 'News' AS metric "
        f"FROM news WHERE team = '{team}' ORDER BY date"
    )
    if not n.empty:
        n["value"] = normalize_min_max(n["value"])
        frames.append(n)

if frames:
    all_metrics = pd.concat(frames, ignore_index=True)

    # Build annotations from ESPN game results
    annotations = pd.DataFrame()
    if table_exists("espn_games"):
        games = query(
            f"SELECT date, opponent, result FROM espn_games "
            f"WHERE team = '{team}' AND result IS NOT NULL ORDER BY date"
        )
        if not games.empty:
            # Place annotations at the midpoint of the y-axis
            games["value"] = 50.0
            annotations = games

    chart = line_chart_with_annotations(
        all_metrics, "date", "value", "metric",
        annotations_df=annotations,
        title=f"{team} — Normalised Metrics (0-100)",
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No metric data available for this team yet.")

# ---------------------------------------------------------------------------
# Game results & upcoming schedule
# ---------------------------------------------------------------------------

if table_exists("espn_games"):
    st.subheader("Recent Results")
    results = query(
        f"SELECT date, opponent, home_away, score_team, score_opponent, result "
        f"FROM espn_games "
        f"WHERE team = '{team}' AND status = 'final' "
        f"ORDER BY date DESC LIMIT 15"
    )
    if not results.empty:
        st.dataframe(results.reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.caption("No recent results found.")

    st.subheader("Upcoming Schedule")
    upcoming = query(
        f"SELECT date, opponent, home_away, broadcasts, victory_plus "
        f"FROM espn_games "
        f"WHERE team = '{team}' AND status = 'scheduled' "
        f"ORDER BY date LIMIT 10"
    )
    if not upcoming.empty:
        # Highlight Victory+ games
        def _fmt_vplus(row):
            return "\u2705 Victory+" if row["victory_plus"] else ""

        upcoming["streaming"] = upcoming.apply(_fmt_vplus, axis=1)
        st.dataframe(
            upcoming[["date", "opponent", "home_away", "broadcasts", "streaming"]]
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

        vplus_games = upcoming[upcoming["victory_plus"]]
        if not vplus_games.empty:
            st.success(
                f"**{len(vplus_games)} upcoming game(s) available on Victory+** "
                f"([victoryplus.com](https://victoryplus.com)) — a free sports streaming platform."
            )
    else:
        st.caption("No upcoming games found.")

# ---------------------------------------------------------------------------
# Reddit buzz
# ---------------------------------------------------------------------------

if table_exists("reddit"):
    st.subheader("Reddit Community Buzz")
    reddit_data = query(
        f"SELECT date, post_count, total_score, total_comments "
        f"FROM reddit WHERE team = '{team}' ORDER BY date"
    )
    if not reddit_data.empty:
        import altair as alt

        reddit_long = reddit_data.melt(
            id_vars=["date"],
            value_vars=["post_count", "total_comments"],
            var_name="metric",
            value_name="count",
        )
        chart = (
            alt.Chart(reddit_long)
            .mark_bar()
            .encode(
                x="date:T",
                y="count:Q",
                color="metric:N",
                tooltip=["date:T", "metric:N", "count:Q"],
            )
            .properties(height=300, title=f"r/{league.lower() if league else 'sports'} activity for {team}")
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("No Reddit data for this team yet.")

# ---------------------------------------------------------------------------
# News volume
# ---------------------------------------------------------------------------

if table_exists("news"):
    st.subheader("News Volume")
    news_data = query(
        f"SELECT date, article_count FROM news "
        f"WHERE team = '{team}' ORDER BY date"
    )
    if not news_data.empty:
        import altair as alt

        chart = (
            alt.Chart(news_data)
            .mark_bar(color="#1f77b4")
            .encode(
                x="date:T",
                y="article_count:Q",
                tooltip=["date:T", "article_count:Q"],
            )
            .properties(height=250, title=f"Daily news articles mentioning {team}")
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("No news data for this team yet.")
