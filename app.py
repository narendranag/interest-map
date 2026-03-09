"""
Zeitgeist: The Sports Interest Index — Home page.

A multi-page Streamlit dashboard that compares digital attention across
NBA, MLB, and NHL teams using six proxy data sources fetched by an
automated pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from lib.db import get_pipeline_meta, table_exists
from lib.styles import (
    LEAGUE_COLORS,
    apply_premium_theme,
    data_freshness_badge,
    metric_card,
    nav_card,
    section_header,
)

st.set_page_config(
    page_title="Zeitgeist: The Sports Interest Index",
    page_icon="Z",
    layout="wide",
)
apply_premium_theme()

# ---------------------------------------------------------------------------
# Hero section
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="zg-hero">'
    '  <div class="zg-hero-title">Zeitgeist</div>'
    '  <div class="zg-hero-tagline">'
    "    The Sports Interest Index &mdash; tracking digital attention "
    "    across NBA, MLB &amp; NHL"
    "  </div>"
    "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data freshness (sidebar)
# ---------------------------------------------------------------------------

meta = get_pipeline_meta()
last_run = meta.get("last_run")

if last_run:
    try:
        run_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - run_dt).total_seconds() / 3600
        if age_hours < 7:
            status = "Fresh"
        elif age_hours < 13:
            status = "Aging"
        else:
            status = "Stale"
        st.sidebar.markdown(
            data_freshness_badge(
                run_dt.strftime("%Y-%m-%d %H:%M UTC"), status
            ),
            unsafe_allow_html=True,
        )
    except Exception:
        st.sidebar.info("Pipeline metadata found but could not be parsed.")
else:
    st.sidebar.warning(
        "No pipeline data yet. Run `python -m pipeline.run_pipeline` "
        "to seed initial data."
    )

# ---------------------------------------------------------------------------
# Quick stats (metric cards)
# ---------------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

team_count = "92"
latest_date = "N/A"

if table_exists("trends"):
    from lib.db import query

    stats = query(
        "SELECT COUNT(DISTINCT team) AS teams, MAX(date) AS latest "
        "FROM trends"
    )
    if not stats.empty:
        team_count = str(int(stats["teams"].iloc[0]))
        latest_date = str(stats["latest"].iloc[0])

sources_available = sum(
    1 for t in ("trends", "wikipedia", "espn_games", "reddit", "news")
    if table_exists(t)
)

with col1:
    st.markdown(
        metric_card("Teams Tracked", team_count, accent_color=LEAGUE_COLORS["NBA"]),
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        metric_card("Latest Data", latest_date, accent_color=LEAGUE_COLORS["MLB"]),
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        metric_card(
            "Active Sources",
            f"{sources_available} / 5",
            accent_color=LEAGUE_COLORS["NHL"],
        ),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Navigation cards
# ---------------------------------------------------------------------------

section_header("Explore")

cols = st.columns(4)
nav_items = [
    (
        "League Overview",
        "Rankings, composite scores, and Top Movers across all 92 teams",
        "&#x1F3C6;",
    ),
    (
        "Team Deep Dive",
        "Trendlines, game results, streaming availability, and community buzz",
        "&#x1F50D;",
    ),
    (
        "Head to Head",
        "Compare 2-5 teams side by side across every metric",
        "&#x2694;&#xFE0F;",
    ),
    (
        "Movers &amp; Alerts",
        "Biggest risers, fallers, and statistical anomaly detection",
        "&#x26A1;",
    ),
]

for col, (title, desc, icon) in zip(cols, nav_items):
    with col:
        st.markdown(nav_card(title, desc, icon), unsafe_allow_html=True)

st.caption("Use the sidebar on the left to navigate between pages.")

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

section_header("Data Sources", "Six proxy metrics powering the Interest Index")

st.markdown(
    '<div class="zg-source-grid">'
    '  <div class="zg-source-card">'
    '    <div class="zg-source-name">Google Trends</div>'
    '    <div class="zg-source-desc">Relative search interest (0-100)</div>'
    "  </div>"
    '  <div class="zg-source-card">'
    '    <div class="zg-source-name">Wikipedia</div>'
    '    <div class="zg-source-desc">Daily article pageviews</div>'
    "  </div>"
    '  <div class="zg-source-card">'
    '    <div class="zg-source-name">ESPN</div>'
    '    <div class="zg-source-desc">Schedules, scores, broadcasts</div>'
    "  </div>"
    '  <div class="zg-source-card">'
    '    <div class="zg-source-name">Victory+</div>'
    '    <div class="zg-source-desc">Free streaming availability</div>'
    "  </div>"
    '  <div class="zg-source-card">'
    '    <div class="zg-source-name">Reddit</div>'
    '    <div class="zg-source-desc">Community post volume &amp; engagement</div>'
    "  </div>"
    '  <div class="zg-source-card">'
    '    <div class="zg-source-name">Google News</div>'
    '    <div class="zg-source-desc">Daily article count per team</div>'
    "  </div>"
    "</div>",
    unsafe_allow_html=True,
)
