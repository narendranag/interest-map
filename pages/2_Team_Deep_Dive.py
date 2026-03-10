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

# ---------------------------------------------------------------------------
# Team Subreddit
# ---------------------------------------------------------------------------

if table_exists("team_subreddits"):
    sub_data = query(
        f"SELECT date, subreddit, subscribers, active_users, posts_24h, avg_score "
        f"FROM team_subreddits WHERE team = '{team}' ORDER BY date DESC LIMIT 1"
    )
    if not sub_data.empty:
        section_header("Team Subreddit", f"r/{sub_data['subreddit'].iloc[0]}")
        sc1, sc2, sc3, sc4 = st.columns(4)
        row = sub_data.iloc[0]
        sc1.metric("Subscribers", f"{int(row['subscribers']):,}")
        sc2.metric("Active Now", f"{int(row['active_users']):,}")
        sc3.metric("Posts (24h)", int(row["posts_24h"]))
        sc4.metric("Avg Post Score", f"{row['avg_score']:.0f}")

# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

if table_exists("attendance"):
    att_data = query(
        f"SELECT date, opponent, attendance, capacity, attendance_pct "
        f"FROM attendance WHERE team = '{team}' ORDER BY date DESC LIMIT 10"
    )
    if not att_data.empty:
        section_header("Attendance")
        st.dataframe(
            att_data.reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date"),
                "opponent": st.column_config.TextColumn("Opponent"),
                "attendance": st.column_config.NumberColumn("Attendance", format="%d"),
                "capacity": st.column_config.NumberColumn("Capacity", format="%d"),
                "attendance_pct": st.column_config.NumberColumn("Fill %", format="%.1f%%"),
            },
        )

# ---------------------------------------------------------------------------
# Ticket Demand
# ---------------------------------------------------------------------------

if table_exists("tickets"):
    tix_data = query(
        f"SELECT date, avg_price, lowest_price, listing_count, num_events "
        f"FROM tickets WHERE team = '{team}' ORDER BY date DESC LIMIT 1"
    )
    if not tix_data.empty:
        section_header("Ticket Demand", "SeatGeek market data")
        tc1, tc2, tc3, tc4 = st.columns(4)
        trow = tix_data.iloc[0]
        tc1.metric("Avg Price", f"${trow['avg_price']:.0f}" if pd.notna(trow["avg_price"]) else "N/A")
        tc2.metric("Lowest Price", f"${trow['lowest_price']:.0f}" if pd.notna(trow["lowest_price"]) else "N/A")
        tc3.metric("Listings", f"{int(trow['listing_count']):,}" if pd.notna(trow["listing_count"]) else "N/A")
        tc4.metric("Events", int(trow["num_events"]) if pd.notna(trow["num_events"]) else "N/A")

# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

if table_exists("youtube"):
    yt_data = query(
        f"SELECT date, subscribers, total_views, video_count "
        f"FROM youtube WHERE team = '{team}' ORDER BY date DESC LIMIT 1"
    )
    if not yt_data.empty:
        section_header("YouTube Channel")
        yc1, yc2, yc3 = st.columns(3)
        yrow = yt_data.iloc[0]
        yc1.metric("Subscribers", f"{int(yrow['subscribers']):,}")
        yc2.metric("Total Views", f"{int(yrow['total_views']):,}")
        yc3.metric("Videos", f"{int(yrow['video_count']):,}")

# ---------------------------------------------------------------------------
# Betting Odds
# ---------------------------------------------------------------------------

if table_exists("betting"):
    bet_data = query(
        f"SELECT date, implied_win_prob, num_bookmakers "
        f"FROM betting WHERE team = '{team}' "
        f"AND implied_win_prob IS NOT NULL ORDER BY date DESC LIMIT 1"
    )
    if not bet_data.empty:
        section_header("Betting Odds")
        bc1, bc2 = st.columns(2)
        brow = bet_data.iloc[0]
        bc1.metric("Implied Win Prob", f"{brow['implied_win_prob'] * 100:.1f}%")
        bc2.metric("Bookmaker Entries", int(brow["num_bookmakers"]))

# ---------------------------------------------------------------------------
# Merchandise
# ---------------------------------------------------------------------------

if table_exists("merchandise"):
    merch_data = query(
        f"SELECT date, merch_rank "
        f"FROM merchandise WHERE team = '{team}' ORDER BY date DESC LIMIT 1"
    )
    if not merch_data.empty:
        section_header("Merchandise Ranking")
        st.metric("NBA Merchandise Rank", f"#{int(merch_data['merch_rank'].iloc[0])}")
