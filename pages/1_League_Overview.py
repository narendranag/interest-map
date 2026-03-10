"""
Zeitgeist | League Overview — rankings, composite scores, bar chart, and Top Movers.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from lib.charts import bar_chart, line_chart
from lib.db import query, table_exists
from lib.scoring import (
    compute_weighted_score,
    normalize_min_max,
)
from lib.styles import apply_premium_theme, section_header, LEAGUE_COLORS
from lib.teams import ALL_TEAMS, LEAGUE_TEAMS, TEAM_TO_LEAGUE

st.set_page_config(page_title="Zeitgeist | League Overview", layout="wide")
apply_premium_theme()

st.markdown('<h1>League Overview</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="zg-subtitle">Rankings, composite scores, and trend analysis '
    "across NBA, MLB &amp; NHL</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

selected_leagues = st.sidebar.multiselect(
    "Leagues",
    options=list(LEAGUE_TEAMS.keys()),
    default=list(LEAGUE_TEAMS.keys()),
)

window = st.sidebar.slider("Time window (days)", 7, 90, 30, step=7)

st.sidebar.markdown(
    '<div style="margin-top:1rem;font-size:0.75rem;font-weight:600;'
    'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;">'
    "Metric Weights</div>",
    unsafe_allow_html=True,
)
w_trends = st.sidebar.slider("Google Trends", 0.0, 1.0, 0.25, step=0.05)
w_wiki = st.sidebar.slider("Wikipedia", 0.0, 1.0, 0.25, step=0.05)
w_espn = st.sidebar.slider("Win rate (ESPN)", 0.0, 1.0, 0.20, step=0.05)
w_reddit = st.sidebar.slider("Reddit buzz", 0.0, 1.0, 0.15, step=0.05)
w_news = st.sidebar.slider("News coverage", 0.0, 1.0, 0.15, step=0.05)

st.sidebar.markdown(
    '<div style="margin-top:0.5rem;font-size:0.7rem;font-weight:600;'
    'text-transform:uppercase;letter-spacing:0.05em;color:#9CA3AF;">'
    "New Sources (default 0)</div>",
    unsafe_allow_html=True,
)
w_subreddit = st.sidebar.slider("Team Subreddits", 0.0, 1.0, 0.0, step=0.05)
w_attendance = st.sidebar.slider("Attendance", 0.0, 1.0, 0.0, step=0.05)
w_tickets = st.sidebar.slider("Ticket Demand", 0.0, 1.0, 0.0, step=0.05)
w_youtube = st.sidebar.slider("YouTube", 0.0, 1.0, 0.0, step=0.05)
w_betting = st.sidebar.slider("Betting Odds", 0.0, 1.0, 0.0, step=0.05)
w_merch = st.sidebar.slider("Merchandise", 0.0, 1.0, 0.0, step=0.05)

_all_metrics = [
    "interest_score", "trends_norm", "wiki_norm", "espn_norm",
    "reddit_norm", "news_norm", "subreddit_norm", "attendance_norm",
    "tickets_norm", "youtube_norm", "betting_norm", "merch_norm",
]
metric = st.selectbox(
    "Rank by",
    _all_metrics,
    format_func=lambda m: m.replace("_", " ").title(),
)

if not selected_leagues:
    st.warning("Select at least one league.")
    st.stop()

# ---------------------------------------------------------------------------
# Build the selected team list
# ---------------------------------------------------------------------------

selected_teams = [t for lg in selected_leagues for t in LEAGUE_TEAMS[lg]]
team_list_sql = ", ".join(f"'{t}'" for t in selected_teams)

# ---------------------------------------------------------------------------
# Load data from DuckDB
# ---------------------------------------------------------------------------

# Google Trends
if table_exists("trends"):
    trends = query(
        f"SELECT date, team, trends_score FROM trends "
        f"WHERE team IN ({team_list_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY"
    )
else:
    trends = pd.DataFrame(columns=["date", "team", "trends_score"])

# Wikipedia
if table_exists("wikipedia"):
    wiki = query(
        f"SELECT date, team, wiki_views FROM wikipedia "
        f"WHERE team IN ({team_list_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY"
    )
else:
    wiki = pd.DataFrame(columns=["date", "team", "wiki_views"])

# ESPN — aggregate win rate per team
if table_exists("espn_games"):
    espn = query(
        f"SELECT team, "
        f"  COUNT(*) FILTER (WHERE result='W') * 1.0 / NULLIF(COUNT(*) FILTER (WHERE result IS NOT NULL), 0) AS win_rate "
        f"FROM espn_games "
        f"WHERE team IN ({team_list_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY "
        f"GROUP BY team"
    )
else:
    espn = pd.DataFrame(columns=["team", "win_rate"])

# Reddit — total daily engagement
if table_exists("reddit"):
    reddit = query(
        f"SELECT date, team, (post_count + total_comments) AS reddit_engagement "
        f"FROM reddit "
        f"WHERE team IN ({team_list_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY"
    )
else:
    reddit = pd.DataFrame(columns=["date", "team", "reddit_engagement"])

# News
if table_exists("news"):
    news = query(
        f"SELECT date, team, article_count FROM news "
        f"WHERE team IN ({team_list_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY"
    )
else:
    news = pd.DataFrame(columns=["date", "team", "article_count"])

# --- New sources (team-level aggregates, mapped onto base) ---

# Team Subreddits — subscribers as engagement proxy
if table_exists("team_subreddits"):
    team_sub = query(
        f"SELECT team, MAX(subscribers) AS sub_subscribers, "
        f"MAX(active_users) AS sub_active "
        f"FROM team_subreddits "
        f"WHERE team IN ({team_list_sql}) "
        f"GROUP BY team"
    )
else:
    team_sub = pd.DataFrame(columns=["team", "sub_subscribers", "sub_active"])

# Attendance — average attendance %
if table_exists("attendance"):
    attend = query(
        f"SELECT team, AVG(attendance_pct) AS avg_attendance_pct "
        f"FROM attendance "
        f"WHERE team IN ({team_list_sql}) "
        f"AND attendance_pct IS NOT NULL "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY "
        f"GROUP BY team"
    )
else:
    attend = pd.DataFrame(columns=["team", "avg_attendance_pct"])

# Tickets — average ticket price as demand proxy
if table_exists("tickets"):
    tickets = query(
        f"SELECT team, AVG(avg_price) AS avg_ticket_price "
        f"FROM tickets "
        f"WHERE team IN ({team_list_sql}) "
        f"AND avg_price IS NOT NULL "
        f"GROUP BY team"
    )
else:
    tickets = pd.DataFrame(columns=["team", "avg_ticket_price"])

# YouTube — subscriber count
if table_exists("youtube"):
    yt = query(
        f"SELECT team, MAX(subscribers) AS yt_subscribers "
        f"FROM youtube "
        f"WHERE team IN ({team_list_sql}) "
        f"GROUP BY team"
    )
else:
    yt = pd.DataFrame(columns=["team", "yt_subscribers"])

# Betting — implied win probability
if table_exists("betting"):
    betting = query(
        f"SELECT team, AVG(implied_win_prob) AS avg_win_prob "
        f"FROM betting "
        f"WHERE team IN ({team_list_sql}) "
        f"AND implied_win_prob IS NOT NULL "
        f"AND date >= CURRENT_DATE - INTERVAL '{window}' DAY "
        f"GROUP BY team"
    )
else:
    betting = pd.DataFrame(columns=["team", "avg_win_prob"])

# Merchandise — rank (lower is better, invert later)
if table_exists("merchandise"):
    merch = query(
        f"SELECT team, MIN(merch_rank) AS merch_rank "
        f"FROM merchandise "
        f"WHERE team IN ({team_list_sql}) "
        f"GROUP BY team"
    )
else:
    merch = pd.DataFrame(columns=["team", "merch_rank"])

# ---------------------------------------------------------------------------
# Merge & normalise into a daily panel
# ---------------------------------------------------------------------------

if not trends.empty:
    base = trends.copy()
elif not wiki.empty:
    base = wiki.rename(columns={"wiki_views": "trends_score"})
    base["trends_score"] = 0
else:
    st.info("No data available yet. Run the pipeline to populate data.")
    st.stop()

if not wiki.empty:
    base = base.merge(wiki, on=["date", "team"], how="outer")
else:
    base["wiki_views"] = 0

base["trends_score"] = base["trends_score"].fillna(0)
base["wiki_views"] = base["wiki_views"].fillna(0)

if not reddit.empty:
    reddit_agg = reddit.groupby(["date", "team"])["reddit_engagement"].sum().reset_index()
    base = base.merge(reddit_agg, on=["date", "team"], how="left")
else:
    base["reddit_engagement"] = 0
base["reddit_engagement"] = base["reddit_engagement"].fillna(0)

if not news.empty:
    base = base.merge(news, on=["date", "team"], how="left")
else:
    base["article_count"] = 0
base["article_count"] = base["article_count"].fillna(0)

for col_in, col_out in [
    ("trends_score", "trends_norm"),
    ("wiki_views", "wiki_norm"),
    ("reddit_engagement", "reddit_norm"),
    ("article_count", "news_norm"),
]:
    base[col_out] = base.groupby("team")[col_in].transform(normalize_min_max)

espn_map = espn.set_index("team")["win_rate"].fillna(0)
espn_norm = normalize_min_max(espn_map)
base["espn_norm"] = base["team"].map(espn_norm).fillna(0)

# --- Normalise new sources (team-level, mapped onto base) ---

# Team Subreddits
if not team_sub.empty:
    sub_map = normalize_min_max(team_sub.set_index("team")["sub_subscribers"].fillna(0))
    base["subreddit_norm"] = base["team"].map(sub_map).fillna(0)
else:
    base["subreddit_norm"] = 0.0

# Attendance
if not attend.empty:
    att_map = normalize_min_max(attend.set_index("team")["avg_attendance_pct"].fillna(0))
    base["attendance_norm"] = base["team"].map(att_map).fillna(0)
else:
    base["attendance_norm"] = 0.0

# Tickets
if not tickets.empty:
    tix_map = normalize_min_max(tickets.set_index("team")["avg_ticket_price"].fillna(0))
    base["tickets_norm"] = base["team"].map(tix_map).fillna(0)
else:
    base["tickets_norm"] = 0.0

# YouTube
if not yt.empty:
    yt_map = normalize_min_max(yt.set_index("team")["yt_subscribers"].fillna(0))
    base["youtube_norm"] = base["team"].map(yt_map).fillna(0)
else:
    base["youtube_norm"] = 0.0

# Betting
if not betting.empty:
    bet_map = normalize_min_max(betting.set_index("team")["avg_win_prob"].fillna(0))
    base["betting_norm"] = base["team"].map(bet_map).fillna(0)
else:
    base["betting_norm"] = 0.0

# Merchandise (invert: rank 1 = best = 100, rank 30 = worst = 0)
if not merch.empty:
    merch_inv = merch.set_index("team")["merch_rank"].fillna(30)
    merch_inv = merch_inv.max() + 1 - merch_inv  # invert
    merch_normed = normalize_min_max(merch_inv)
    base["merch_norm"] = base["team"].map(merch_normed).fillna(0)
else:
    base["merch_norm"] = 0.0

weights = {
    "trends_norm": w_trends,
    "wiki_norm": w_wiki,
    "espn_norm": w_espn,
    "reddit_norm": w_reddit,
    "news_norm": w_news,
    "subreddit_norm": w_subreddit,
    "attendance_norm": w_attendance,
    "tickets_norm": w_tickets,
    "youtube_norm": w_youtube,
    "betting_norm": w_betting,
    "merch_norm": w_merch,
}
base["interest_score"] = compute_weighted_score(base, weights)
base["league"] = base["team"].map(TEAM_TO_LEAGUE)

# ---------------------------------------------------------------------------
# Rankings table (latest date)
# ---------------------------------------------------------------------------

if base.empty:
    st.warning("No data after merging. Try a wider time window.")
    st.stop()

latest = base["date"].max()
snapshot = base[base["date"] == latest].sort_values(metric, ascending=False)

section_header("Rankings", f"Snapshot for {latest}")

display_cols = [
    "league", "team", "interest_score",
    "trends_norm", "wiki_norm", "espn_norm", "reddit_norm", "news_norm",
    "subreddit_norm", "attendance_norm", "tickets_norm",
    "youtube_norm", "betting_norm", "merch_norm",
]
# Only show columns that have nonzero data
active_cols = [c for c in display_cols if c in ("league", "team", "interest_score")
               or (c in snapshot.columns and snapshot[c].sum() > 0)]

st.dataframe(
    snapshot[active_cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    column_config={
        "league": st.column_config.TextColumn("League", width="small"),
        "team": st.column_config.TextColumn("Team", width="medium"),
        "interest_score": st.column_config.ProgressColumn(
            "Interest Score", format="%.1f", min_value=0, max_value=100,
        ),
        "trends_norm": st.column_config.NumberColumn("Trends", format="%.1f"),
        "wiki_norm": st.column_config.NumberColumn("Wiki", format="%.1f"),
        "espn_norm": st.column_config.NumberColumn("ESPN", format="%.1f"),
        "reddit_norm": st.column_config.NumberColumn("Reddit", format="%.1f"),
        "news_norm": st.column_config.NumberColumn("News", format="%.1f"),
        "subreddit_norm": st.column_config.NumberColumn("Subreddit", format="%.1f"),
        "attendance_norm": st.column_config.NumberColumn("Attendance", format="%.1f"),
        "tickets_norm": st.column_config.NumberColumn("Tickets", format="%.1f"),
        "youtube_norm": st.column_config.NumberColumn("YouTube", format="%.1f"),
        "betting_norm": st.column_config.NumberColumn("Betting", format="%.1f"),
        "merch_norm": st.column_config.NumberColumn("Merch", format="%.1f"),
    },
)

# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------

st.altair_chart(
    bar_chart(
        snapshot, "team", metric,
        title=f"{metric.replace('_', ' ').title()} by Team",
    ),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Metric breakdown (expandable)
# ---------------------------------------------------------------------------

with st.expander("Metric breakdown per team"):
    st.dataframe(
        snapshot[active_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Trendlines
# ---------------------------------------------------------------------------

section_header("Trendlines")

focus_league = st.selectbox("Focus league", selected_leagues)
subset = base[base["league"] == focus_league]

if not subset.empty:
    st.altair_chart(
        line_chart(
            subset, "date", metric, "team",
            title=f"{focus_league} — {metric.replace('_', ' ').title()}",
        ),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Top Movers (7-day delta)
# ---------------------------------------------------------------------------

section_header("Top Movers", "7-day change in selected metric")

dmax = base["date"].max()
cur = base[(base["date"] <= dmax) & (base["date"] > dmax - timedelta(days=7))]
prev = base[
    (base["date"] <= dmax - timedelta(days=7))
    & (base["date"] > dmax - timedelta(days=14))
]

if not cur.empty and not prev.empty:
    w1 = cur.groupby("team")[metric].mean()
    w0 = prev.groupby("team")[metric].mean()
    movers = (w1 - w0).sort_values(ascending=False).rename("delta").reset_index()
    movers["league"] = movers["team"].map(TEAM_TO_LEAGUE)

    col_rise, col_fall = st.columns(2)

    with col_rise:
        st.markdown(
            '<div class="league-accent-nba">'
            '<h3 style="color:#059669;margin:0">Biggest Risers</h3></div>',
            unsafe_allow_html=True,
        )
        risers = movers.head(10)
        st.dataframe(
            risers[["league", "team", "delta"]].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "delta": st.column_config.NumberColumn("Change", format="+%.2f"),
            },
        )

    with col_fall:
        st.markdown(
            '<div class="league-accent-mlb">'
            '<h3 style="color:#DC2626;margin:0">Biggest Fallers</h3></div>',
            unsafe_allow_html=True,
        )
        fallers = movers.tail(10).sort_values("delta")
        st.dataframe(
            fallers[["league", "team", "delta"]].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "delta": st.column_config.NumberColumn("Change", format="%+.2f"),
            },
        )
else:
    st.info("Not enough historical data for Top Movers yet.")
