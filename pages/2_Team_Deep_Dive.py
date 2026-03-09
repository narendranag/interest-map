"""
Zeitgeist | Team Deep Dive — single-team analysis with game results, Victory+
availability, Reddit buzz, and news volume.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.charts import CHART_THEME, line_chart_with_annotations
from lib.db import query, table_exists
from lib.scoring import normalize_min_max
from lib.styles import LEAGUE_COLORS, apply_premium_theme, section_header
from lib.teams import ALL_TEAMS, TEAM_TO_LEAGUE, VICTORY_PLUS_TEAMS

st.set_page_config(page_title="Zeitgeist | Team Deep Dive", layout="wide")
apply_premium_theme()

# ---------------------------------------------------------------------------
# Team selector
# ---------------------------------------------------------------------------

team = st.selectbox("Select a team", ALL_TEAMS, index=0)
league = TEAM_TO_LEAGUE.get(team, "")
league_color = LEAGUE_COLORS.get(league, "#374151")

# Styled team header card
vplus_badge = ""
if team in VICTORY_PLUS_TEAMS:
    vplus_badge = (
        '&nbsp;&nbsp;<span class="zg-badge zg-badge-success">'
        "Victory+ Partner</span>"
    )

st.markdown(
    f'<div class="zg-card" style="border-left:4px solid {league_color};'
    f'padding:1rem 1.5rem;margin-bottom:1.5rem">'
    f'  <h1 style="margin:0;font-size:1.5rem">{team}</h1>'
    f'  <span class="zg-badge" style="background:{league_color}18;'
    f'color:{league_color};margin-top:0.5rem">{league}</span>'
    f"  {vplus_badge}"
    f"</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Trendlines — all metrics overlaid
# ---------------------------------------------------------------------------

section_header("Interest Trendlines", "Normalised metrics (0-100) with game annotations")

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

    annotations = pd.DataFrame()
    if table_exists("espn_games"):
        games = query(
            f"SELECT date, opponent, result FROM espn_games "
            f"WHERE team = '{team}' AND result IS NOT NULL ORDER BY date"
        )
        if not games.empty:
            games["value"] = 50.0
            annotations = games

    chart = line_chart_with_annotations(
        all_metrics, "date", "value", "metric",
        annotations_df=annotations,
        title=f"{team} — Normalised Metrics",
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No metric data available for this team yet.")

# ---------------------------------------------------------------------------
# Game results & upcoming schedule
# ---------------------------------------------------------------------------

if table_exists("espn_games"):
    section_header("Recent Results")
    results = query(
        f"SELECT date, opponent, home_away, score_team, score_opponent, result "
        f"FROM espn_games "
        f"WHERE team = '{team}' AND status = 'final' "
        f"ORDER BY date DESC LIMIT 15"
    )
    if not results.empty:
        st.dataframe(
            results.reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date"),
                "opponent": st.column_config.TextColumn("Opponent"),
                "home_away": st.column_config.TextColumn("H/A", width="small"),
                "score_team": st.column_config.NumberColumn("Score", format="%d"),
                "score_opponent": st.column_config.NumberColumn("Opp", format="%d"),
                "result": st.column_config.TextColumn("Result", width="small"),
            },
        )
    else:
        st.caption("No recent results found.")

    section_header("Upcoming Schedule")
    upcoming = query(
        f"SELECT date, opponent, home_away, broadcasts, victory_plus "
        f"FROM espn_games "
        f"WHERE team = '{team}' AND status = 'scheduled' "
        f"ORDER BY date LIMIT 10"
    )
    if not upcoming.empty:
        def _fmt_vplus(row):
            return "Victory+" if row["victory_plus"] else ""

        upcoming["streaming"] = upcoming.apply(_fmt_vplus, axis=1)
        st.dataframe(
            upcoming[["date", "opponent", "home_away", "broadcasts", "streaming"]]
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date"),
                "opponent": st.column_config.TextColumn("Opponent"),
                "home_away": st.column_config.TextColumn("H/A", width="small"),
                "broadcasts": st.column_config.TextColumn("Broadcasts"),
                "streaming": st.column_config.TextColumn("Streaming", width="small"),
            },
        )

        vplus_games = upcoming[upcoming["victory_plus"]]
        if not vplus_games.empty:
            st.markdown(
                f'<div class="zg-alert" style="background:#ECFDF5;border-color:#A7F3D0;color:#065F46">'
                f"<strong>{len(vplus_games)} upcoming game(s) on Victory+</strong> &mdash; "
                f'stream free at <a href="https://victoryplus.com" style="color:#059669">'
                f"victoryplus.com</a></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No upcoming games found.")

# ---------------------------------------------------------------------------
# Reddit buzz
# ---------------------------------------------------------------------------

if table_exists("reddit"):
    section_header("Reddit Community Buzz")
    reddit_data = query(
        f"SELECT date, post_count, total_score, total_comments "
        f"FROM reddit WHERE team = '{team}' ORDER BY date"
    )
    if not reddit_data.empty:
        reddit_long = reddit_data.melt(
            id_vars=["date"],
            value_vars=["post_count", "total_comments"],
            var_name="metric",
            value_name="count",
        )
        chart = (
            alt.Chart(reddit_long)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x="date:T",
                y="count:Q",
                color=alt.Color(
                    "metric:N",
                    scale=alt.Scale(range=[CHART_THEME["accent"], "#93C5FD"]),
                ),
                tooltip=["date:T", "metric:N", "count:Q"],
            )
            .properties(
                height=300,
                title=f"r/{league.lower() if league else 'sports'} activity for {team}",
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("No Reddit data for this team yet.")

# ---------------------------------------------------------------------------
# News volume
# ---------------------------------------------------------------------------

if table_exists("news"):
    section_header("News Volume")
    news_data = query(
        f"SELECT date, article_count FROM news "
        f"WHERE team = '{team}' ORDER BY date"
    )
    if not news_data.empty:
        chart = (
            alt.Chart(news_data)
            .mark_bar(
                color=CHART_THEME["accent"],
                cornerRadiusTopLeft=3,
                cornerRadiusTopRight=3,
            )
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
