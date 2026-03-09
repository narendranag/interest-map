"""
Movers & Alerts — biggest risers/fallers and anomaly detection.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from lib.charts import anomaly_highlight_chart
from lib.db import query, table_exists
from lib.scoring import compute_weighted_score, detect_anomalies, normalize_min_max
from lib.teams import ALL_TEAMS, LEAGUE_TEAMS, TEAM_TO_LEAGUE

st.set_page_config(page_title="Movers & Alerts", layout="wide")
st.title("Movers & Alerts")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")
selected_leagues = st.sidebar.multiselect(
    "Leagues",
    list(LEAGUE_TEAMS.keys()),
    default=list(LEAGUE_TEAMS.keys()),
)
period = st.sidebar.radio("Delta period", ["7 days", "30 days"], index=0)
anomaly_threshold = st.sidebar.slider(
    "Anomaly threshold (\u03c3)", 1.0, 4.0, 2.0, step=0.5
)

if not selected_leagues:
    st.warning("Select at least one league.")
    st.stop()

selected_teams = [t for lg in selected_leagues for t in LEAGUE_TEAMS[lg]]
team_sql = ", ".join(f"'{t}'" for t in selected_teams)
delta_days = 7 if period == "7 days" else 30

# ---------------------------------------------------------------------------
# Load composite score over time
# ---------------------------------------------------------------------------

# Build a simple composite from trends + wiki (most reliable time-series)
if table_exists("trends"):
    trends = query(
        f"SELECT date, team, trends_score FROM trends "
        f"WHERE team IN ({team_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '90' DAY"
    )
else:
    trends = pd.DataFrame(columns=["date", "team", "trends_score"])

if table_exists("wikipedia"):
    wiki = query(
        f"SELECT date, team, wiki_views FROM wikipedia "
        f"WHERE team IN ({team_sql}) "
        f"AND date >= CURRENT_DATE - INTERVAL '90' DAY"
    )
else:
    wiki = pd.DataFrame(columns=["date", "team", "wiki_views"])

if trends.empty and wiki.empty:
    st.info("No data available yet. Run the pipeline first.")
    st.stop()

# Merge
if not trends.empty and not wiki.empty:
    base = trends.merge(wiki, on=["date", "team"], how="outer")
elif not trends.empty:
    base = trends.copy()
    base["wiki_views"] = 0
else:
    base = wiki.copy()
    base["trends_score"] = 0

base["trends_score"] = base["trends_score"].fillna(0)
base["wiki_views"] = base["wiki_views"].fillna(0)

# Normalise per team
base["trends_norm"] = base.groupby("team")["trends_score"].transform(normalize_min_max)
base["wiki_norm"] = base.groupby("team")["wiki_views"].transform(normalize_min_max)
base["interest_score"] = compute_weighted_score(
    base, {"trends_norm": 0.5, "wiki_norm": 0.5}
)
base["league"] = base["team"].map(TEAM_TO_LEAGUE)

# ---------------------------------------------------------------------------
# Top Movers
# ---------------------------------------------------------------------------

st.subheader(f"Top Movers ({period})")

dmax = base["date"].max()
cur = base[(base["date"] <= dmax) & (base["date"] > dmax - timedelta(days=delta_days))]
prev = base[
    (base["date"] <= dmax - timedelta(days=delta_days))
    & (base["date"] > dmax - timedelta(days=delta_days * 2))
]

if not cur.empty and not prev.empty:
    w1 = cur.groupby("team")["interest_score"].mean()
    w0 = prev.groupby("team")["interest_score"].mean()
    deltas = (w1 - w0).rename("delta").reset_index()
    deltas["league"] = deltas["team"].map(TEAM_TO_LEAGUE)

    col_rise, col_fall = st.columns(2)

    with col_rise:
        st.markdown("**Biggest Risers** \u2B06\uFE0F")
        risers = deltas.sort_values("delta", ascending=False).head(10)
        st.dataframe(
            risers[["league", "team", "delta"]].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

    with col_fall:
        st.markdown("**Biggest Fallers** \u2B07\uFE0F")
        fallers = deltas.sort_values("delta", ascending=True).head(10)
        st.dataframe(
            fallers[["league", "team", "delta"]].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("Not enough historical data for delta calculations yet.")

# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

st.subheader("Anomaly Alerts")

anomalies_df = detect_anomalies(
    base,
    team_col="team",
    value_col="interest_score",
    window=30,
    threshold=anomaly_threshold,
)

flagged = anomalies_df[anomalies_df["is_anomaly"]].sort_values(
    "z_score", ascending=False
)

if not flagged.empty:
    st.markdown(
        f"**{len(flagged)} anomalous data point(s)** detected "
        f"(>{anomaly_threshold}\u03c3 from 30-day rolling mean)."
    )
    st.dataframe(
        flagged[["date", "league", "team", "interest_score", "z_score"]]
        .head(20)
        .reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )

    # Let user pick a team to visualise
    flagged_teams = flagged["team"].unique().tolist()
    pick = st.selectbox("Inspect anomaly for team", flagged_teams)

    team_data = anomalies_df[anomalies_df["team"] == pick].sort_values("date")
    if not team_data.empty:
        st.altair_chart(
            anomaly_highlight_chart(
                team_data,
                title=f"{pick} — Interest Score with Anomalies",
            ),
            use_container_width=True,
        )
else:
    st.success(
        f"No anomalies detected at the {anomaly_threshold}\u03c3 threshold. "
        "All teams are within normal ranges."
    )
