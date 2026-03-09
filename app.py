"""
Team Interest Dashboard v2.0 — Home page.

A multi-page Streamlit dashboard that compares digital attention across
NBA, MLB, and NHL teams using six proxy data sources fetched by an
automated pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from lib.db import get_pipeline_meta, table_exists

st.set_page_config(
    page_title="Team Interest Dashboard",
    page_icon="\u26be",
    layout="wide",
)

st.title("Team Interest Dashboard")
st.caption(
    "Compare advertiser interest across NBA, MLB & NHL teams using "
    "six proxy data sources."
)

# ---------------------------------------------------------------------------
# Data freshness indicator
# ---------------------------------------------------------------------------

meta = get_pipeline_meta()
last_run = meta.get("last_run")

if last_run:
    try:
        run_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - run_dt).total_seconds() / 3600
        if age_hours < 7:
            colour, label = "\U0001f7e2", "Fresh"
        elif age_hours < 13:
            colour, label = "\U0001f7e1", "Aging"
        else:
            colour, label = "\U0001f534", "Stale"
        st.sidebar.markdown(
            f"**Data** {colour} {label}  \n"
            f"Last pipeline run: {run_dt.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    except Exception:
        st.sidebar.info("Pipeline metadata found but could not be parsed.")
else:
    st.sidebar.warning(
        "No pipeline data yet. Run `python -m pipeline.run_pipeline` "
        "to seed initial data."
    )

# ---------------------------------------------------------------------------
# Quick stats
# ---------------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

if table_exists("trends"):
    from lib.db import query

    stats = query(
        "SELECT COUNT(DISTINCT team) AS teams, MAX(date) AS latest "
        "FROM trends"
    )
    if not stats.empty:
        col1.metric("Teams tracked", int(stats["teams"].iloc[0]))
        col2.metric("Latest data", str(stats["latest"].iloc[0]))
else:
    col1.metric("Teams tracked", "92")
    col2.metric("Latest data", "N/A")

sources_available = sum(
    1 for t in ("trends", "wikipedia", "espn_games", "reddit", "news")
    if table_exists(t)
)
col3.metric("Active sources", f"{sources_available} / 5")

# ---------------------------------------------------------------------------
# Navigation guide
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Pages")

st.markdown(
    """
| Page | What it shows |
|---|---|
| **League Overview** | Rankings, bar chart, weighted composite scores, Top Movers |
| **Team Deep Dive** | Single-team trendlines, game results (W/L), upcoming schedule, **Victory+ streaming**, Reddit buzz, news volume |
| **Head to Head** | Compare 2-5 teams side by side across all metrics |
| **Movers & Alerts** | Biggest risers/fallers and anomaly detection (statistical spikes) |

Use the **sidebar** on the left to navigate between pages.
"""
)

st.markdown("---")
st.subheader("Data Sources")
st.markdown(
    """
1. **Google Trends** — relative search interest (0-100)
2. **Wikipedia Pageviews** — daily article views from Wikimedia API
3. **ESPN** — game schedules, scores, and broadcast channels
4. **Victory+** — free streaming availability detected from ESPN broadcasts
5. **Reddit** — community post volume and engagement (r/nba, r/baseball, r/hockey)
6. **Google News** — daily article count per team
"""
)
