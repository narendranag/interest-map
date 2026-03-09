"""
Zeitgeist | About — what this app does and how to use it.
"""

from __future__ import annotations

import streamlit as st

from lib.styles import apply_premium_theme, section_header, LEAGUE_COLORS

st.set_page_config(page_title="Zeitgeist | About", layout="wide")
apply_premium_theme()

st.markdown('<h1>About Zeitgeist</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="zg-subtitle">The Sports Interest Index</p>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# What is Zeitgeist?
# ---------------------------------------------------------------------------

section_header("What is Zeitgeist?")

st.markdown(
    """
Zeitgeist tracks and compares **digital attention** across all 92 teams in
the NBA, MLB, and NHL. Instead of relying on a single metric, it combines
six independent data sources into a composite **Interest Score** that
reflects how much buzz each team is generating online.

Whether you work in sports media, sponsorship, advertising, or are simply a
curious fan, Zeitgeist gives you a data-driven answer to the question:
**"Which teams are people paying attention to right now?"**
"""
)

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

section_header("Data Sources", "Six proxy metrics updated every six hours")

sources = [
    (
        "Google Trends",
        "Relative search interest on a 0-100 scale. Captures how often "
        "people are actively searching for a team.",
    ),
    (
        "Wikipedia Pageviews",
        "Daily article views from the Wikimedia API. A spike usually "
        "signals a notable event (trade, record, controversy).",
    ),
    (
        "ESPN Scores & Schedules",
        "Game results (W/L), upcoming schedules, and broadcast channels "
        "pulled from ESPN's public scoreboard API.",
    ),
    (
        "Victory+",
        "Free streaming availability detected from ESPN broadcast data. "
        "Games on Victory+ are flagged in the Team Deep Dive.",
    ),
    (
        "Reddit",
        "Post volume and comment engagement from r/nba, r/baseball, and "
        "r/hockey. Measures community conversation.",
    ),
    (
        "Google News",
        "Daily article count from Google News RSS. Tracks mainstream "
        "media coverage for each team.",
    ),
]

st.markdown('<div class="zg-source-grid">', unsafe_allow_html=True)
for name, desc in sources:
    st.markdown(
        f'<div class="zg-source-card">'
        f'  <div class="zg-source-name">{name}</div>'
        f'  <div class="zg-source-desc">{desc}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# How to use the app
# ---------------------------------------------------------------------------

section_header("How to Use the App")

st.markdown(
    """
**Zeitgeist has four main pages**, each designed for a different use case.
Navigate between them using the sidebar on the left.
"""
)

pages_info = [
    (
        "League Overview",
        "The big picture. See every team ranked by a **weighted composite "
        "score** that you control. Adjust the sliders in the sidebar to "
        "weight Google Trends, Wikipedia, ESPN win rate, Reddit buzz, and "
        "News coverage however you like. Scroll down for **Top Movers** "
        "(biggest 7-day risers and fallers) and league-filtered trendlines.",
    ),
    (
        "Team Deep Dive",
        "Pick a single team and see all its metrics overlaid on one chart, "
        "with **W/L game annotations** from ESPN. Below that: recent results, "
        "upcoming schedule (with **Victory+ streaming** flags), Reddit "
        "community activity, and news volume over time.",
    ),
    (
        "Head to Head",
        "Select 2-5 teams and compare them side by side. A metric "
        "comparison table and grouped bar chart show how they stack up. "
        "Switch between Google Trends and Wikipedia trendline tabs to see "
        "how attention has shifted over time.",
    ),
    (
        "Movers & Alerts",
        "Spot the teams gaining or losing momentum. Choose a 7-day or "
        "30-day window to see the biggest changes. The **anomaly "
        "detection** section flags any data points that are more than "
        "2 standard deviations from the 30-day rolling mean, helping "
        "you catch sudden spikes in interest.",
    ),
]

for title, desc in pages_info:
    st.markdown(
        f'<div class="zg-card" style="margin-bottom:0.75rem">'
        f'  <div style="font-weight:600;font-size:1rem;color:#1A1A2E;'
        f'margin-bottom:0.25rem">{title}</div>'
        f'  <div style="font-size:0.875rem;color:#374151;line-height:1.6">'
        f"{desc}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# How the Interest Score works
# ---------------------------------------------------------------------------

section_header("How the Interest Score Works")

st.markdown(
    """
The **Interest Score** on the League Overview page is a weighted average of
five normalised metrics:

1. Each raw metric (Trends, Wikipedia, ESPN win rate, Reddit, News) is
   normalised to a **0-100 scale** using min-max scaling across all teams.
2. You set the **weights** via sidebar sliders. The weights are
   automatically re-normalised so they sum to 1.0.
3. The composite score is simply:
"""
)

st.latex(
    r"\text{Interest Score} = \sum_{i} w_i \times \text{metric}_i^{\text{norm}}"
)

st.markdown(
    """
This means you can tune the score to emphasise whatever matters most to
your analysis. Setting the Reddit slider to zero, for example, removes
community buzz from the ranking entirely.
"""
)

# ---------------------------------------------------------------------------
# Data freshness
# ---------------------------------------------------------------------------

section_header("Data Freshness")

st.markdown(
    """
An automated pipeline runs **every six hours** via GitHub Actions. It
fetches the latest data from all sources, saves it as Parquet files, and
commits them to the deployment branch. The app loads these files into an
in-memory DuckDB database on startup, so page loads are fast.

The **sidebar indicator** on the Home page shows data freshness:

- **Fresh** (green) — data is less than 7 hours old
- **Aging** (yellow) — data is 7-13 hours old
- **Stale** (red) — data is more than 13 hours old
"""
)

# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

section_header("Coverage")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f'<div class="zg-card" style="border-top:3px solid {LEAGUE_COLORS["NBA"]};'
        f'text-align:center">'
        f'  <div style="font-size:2rem;font-weight:700;color:#1A1A2E">30</div>'
        f'  <div style="font-size:0.8rem;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:0.05em">NBA Teams</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f'<div class="zg-card" style="border-top:3px solid {LEAGUE_COLORS["MLB"]};'
        f'text-align:center">'
        f'  <div style="font-size:2rem;font-weight:700;color:#1A1A2E">30</div>'
        f'  <div style="font-size:0.8rem;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:0.05em">MLB Teams</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f'<div class="zg-card" style="border-top:3px solid {LEAGUE_COLORS["NHL"]};'
        f'text-align:center">'
        f'  <div style="font-size:2rem;font-weight:700;color:#1A1A2E">32</div>'
        f'  <div style="font-size:0.8rem;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:0.05em">NHL Teams</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    '<div style="text-align:center;font-size:0.8rem;color:#9CA3AF;padding:1rem 0">'
    "Built with Streamlit, DuckDB, and Altair. "
    "Data sourced from Google Trends, Wikipedia, ESPN, Reddit, and Google News."
    "</div>",
    unsafe_allow_html=True,
)
