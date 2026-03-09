"""
Team Interest Dashboard
=======================

Interactive Streamlit dashboard comparing digital attention across NBA, MLB
and NHL teams.  Three public proxy data-sources are blended into a single
*interest score* per team per day:

* **Google Trends** – relative search interest via `pytrends`.
* **Wikipedia Pageviews** – daily article views from the Wikimedia REST API.
* **YouTube** *(optional)* – channel view/subscriber counts from the YouTube
  Data API v3 (requires an API key entered in the sidebar).

Metric weights are fully configurable through sidebar sliders.  When no
YouTube API key is provided the weight is redistributed across the other two
sources automatically.

Usage
-----

.. code-block:: bash

    pip install -r requirements.txt
    streamlit run app.py

Dockerized deployment is also supported via the provided Dockerfile and
docker-compose.yml.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import altair as alt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from pytrends.request import TrendReq
from requests.adapters import HTTPAdapter, Retry

try:
    from googleapiclient.discovery import build  # type: ignore
except ImportError:
    build = None


# ---------------------------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Team Interest Dashboard", layout="wide")

st.title("Team Interest Dashboard")
st.caption(
    "Proxy = Google Trends + Wikipedia Pageviews + YouTube (optional)."
)


# ---------------------------------------------------------------------------
# Static team definitions
# ---------------------------------------------------------------------------

NBA_TEAMS: List[str] = [
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
    "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks",
    "Denver Nuggets", "Detroit Pistons", "Golden State Warriors",
    "Houston Rockets", "Indiana Pacers", "LA Clippers",
    "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
    "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
    "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
    "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
    "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
    "Utah Jazz", "Washington Wizards",
]

MLB_TEAMS: List[str] = [
    "Arizona Diamondbacks", "Atlanta Braves", "Baltimore Orioles",
    "Boston Red Sox", "Chicago Cubs", "Chicago White Sox",
    "Cincinnati Reds", "Cleveland Guardians", "Colorado Rockies",
    "Detroit Tigers", "Houston Astros", "Kansas City Royals",
    "Los Angeles Angels", "Los Angeles Dodgers", "Miami Marlins",
    "Milwaukee Brewers", "Minnesota Twins", "New York Mets",
    "New York Yankees", "Oakland Athletics", "Philadelphia Phillies",
    "Pittsburgh Pirates", "San Diego Padres", "San Francisco Giants",
    "Seattle Mariners", "St. Louis Cardinals", "Tampa Bay Rays",
    "Texas Rangers", "Toronto Blue Jays", "Washington Nationals",
]

NHL_TEAMS: List[str] = [
    "Anaheim Ducks", "Boston Bruins", "Buffalo Sabres",
    "Calgary Flames", "Carolina Hurricanes", "Chicago Blackhawks",
    "Colorado Avalanche", "Columbus Blue Jackets", "Dallas Stars",
    "Detroit Red Wings", "Edmonton Oilers", "Florida Panthers",
    "Los Angeles Kings", "Minnesota Wild", "Montreal Canadiens",
    "Nashville Predators", "New Jersey Devils", "New York Islanders",
    "New York Rangers", "Ottawa Senators", "Philadelphia Flyers",
    "Pittsburgh Penguins", "San Jose Sharks", "Seattle Kraken",
    "St. Louis Blues", "Tampa Bay Lightning", "Toronto Maple Leafs",
    "Utah Hockey Club", "Vancouver Canucks", "Vegas Golden Knights",
    "Washington Capitals", "Winnipeg Jets",
]

LEAGUE_TEAMS: Dict[str, List[str]] = {
    "NBA": NBA_TEAMS,
    "MLB": MLB_TEAMS,
    "NHL": NHL_TEAMS,
}

TEAM_TO_LEAGUE: Dict[str, str] = {
    team: league for league, teams in LEAGUE_TEAMS.items() for team in teams
}


# ---------------------------------------------------------------------------
# HTTP session with retries
# ---------------------------------------------------------------------------

def http_session() -> requests.Session:
    """Create a requests session with retry strategy and headers."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Team-Interest-Dashboard/1.0"})
    return session


# ---------------------------------------------------------------------------
# Data-fetching helpers
# ---------------------------------------------------------------------------

def _select_timeframe(days: int) -> str:
    """Map a number of days to a valid Google Trends timeframe string."""
    if days <= 1:
        return "now 1-d"
    if days <= 7:
        return f"now {min(days, 7)}-d"
    if days <= 30:
        return "today 1-m"
    if days <= 90:
        return "today 3-m"
    if days <= 365:
        return "today 12-m"
    return "today 5-y"


def fetch_google_trends_daily(terms: List[str], days: int) -> pd.DataFrame:
    """Fetch daily Google Trends scores for *terms* in batches of five.

    Returns a long-form DataFrame with columns ``[date, term, trends_score]``.
    """
    pytrends = TrendReq(hl="en-US", tz=0)
    batch_size = 5
    frames: List[pd.DataFrame] = []
    timeframe = _select_timeframe(days)

    for i in range(0, len(terms), batch_size):
        batch = terms[i : i + batch_size]
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo="")
            data = pytrends.interest_over_time().reset_index()
        except Exception:
            continue
        if data.empty:
            continue
        melted = data.melt(
            id_vars=["date"],
            value_vars=batch,
            var_name="term",
            value_name="trends_score",
        )
        melted["date"] = pd.to_datetime(melted["date"]).dt.date
        frames.append(melted[["date", "term", "trends_score"]])
        time.sleep(1.2)

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame(columns=["date", "term", "trends_score"])


def fetch_wikipedia_daily(
    session: requests.Session,
    team: str,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """Fetch daily Wikipedia pageviews for a single team.

    Returns a DataFrame with columns ``[date, term, wiki_views]``.
    """
    page = team.replace(" ", "_")
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia.org/all-access/all-agents/{page}/daily/"
        f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
    )
    resp = session.get(url, timeout=20)
    if resp.status_code != 200:
        return pd.DataFrame(columns=["date", "term", "wiki_views"])
    items = resp.json().get("items", [])
    rows = []
    for it in items:
        ts = it.get("timestamp")
        ts_dt = datetime.strptime(str(ts), "%Y%m%d%H")
        rows.append(
            {
                "date": ts_dt.date(),
                "term": team,
                "wiki_views": it.get("views", 0),
            }
        )
    return pd.DataFrame(rows)


def fetch_youtube_channel_stats(
    team_name: str, api_key: Optional[str]
) -> Tuple[float, float]:
    """Return ``(view_count, subscriber_count)`` for the first matching YouTube channel.

    Returns ``(0.0, 0.0)`` when no API key is provided or the call fails.
    """
    if not api_key or build is None:
        return 0.0, 0.0
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        search_response = (
            youtube.search()
            .list(q=team_name, part="id,snippet", type="channel", maxResults=1)
            .execute()
        )
        items = search_response.get("items", [])
        if not items:
            return 0.0, 0.0
        channel_id = items[0]["id"]["channelId"]
        channel_response = (
            youtube.channels().list(id=channel_id, part="statistics").execute()
        )
        stats = channel_response["items"][0]["statistics"]
        return float(stats.get("viewCount", 0)), float(
            stats.get("subscriberCount", 0)
        )
    except Exception:
        return 0.0, 0.0


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a numeric series to 0--100."""
    if series.empty or series.max() == series.min():
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.min()) / (series.max() - series.min()) * 100.0


# ---------------------------------------------------------------------------
# Main data pipeline
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_interest_proxies(
    leagues: Tuple[str, ...],
    days: int,
    yt_api_key: str = "",
    w_trends: float = 0.4,
    w_wiki: float = 0.4,
    w_youtube: float = 0.2,
) -> pd.DataFrame:
    """Fetch, normalise and blend proxy interest metrics.

    Returns a DataFrame with columns ``[date, term, trends_score, wiki_views,
    trends_norm, wiki_norm, youtube_norm, interest_score, league]``.
    """
    session = http_session()
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    all_terms: List[str] = [
        team for lg in leagues for team in LEAGUE_TEAMS[lg]
    ]

    # -- Google Trends -------------------------------------------------------
    trends = fetch_google_trends_daily(all_terms, days)

    # -- Wikipedia Pageviews -------------------------------------------------
    wiki_frames: List[pd.DataFrame] = []
    for term in all_terms:
        wiki_frames.append(
            fetch_wikipedia_daily(session, term, start_date, end_date)
        )
    wiki = (
        pd.concat(wiki_frames, ignore_index=True)
        if wiki_frames
        else pd.DataFrame(columns=["date", "term", "wiki_views"])
    )

    # -- Merge & clean -------------------------------------------------------
    df = pd.merge(trends, wiki, on=["date", "term"], how="outer").sort_values(
        ["term", "date"]
    )
    df["trends_score"] = df.groupby("term")["trends_score"].transform(
        lambda s: s.interpolate().bfill().ffill()
    )
    df["wiki_views"] = df["wiki_views"].fillna(0)

    # -- Normalise per team --------------------------------------------------
    df["trends_norm"] = df.groupby("term")["trends_score"].transform(
        _normalize
    )
    df["wiki_norm"] = df.groupby("term")["wiki_views"].transform(_normalize)

    # -- YouTube (optional, point-in-time) -----------------------------------
    yt_scores: Dict[str, float] = {}
    if yt_api_key:
        for term in all_terms:
            views, subs = fetch_youtube_channel_stats(term, yt_api_key)
            yt_scores[term] = (views + subs) / 2.0

    if yt_scores:
        yt_series = pd.Series(yt_scores)
        yt_norm = _normalize(yt_series)
        df["youtube_norm"] = df["term"].map(yt_norm).fillna(0.0)
    else:
        df["youtube_norm"] = 0.0

    # -- Weighted interest score ---------------------------------------------
    if yt_api_key and yt_scores:
        df["interest_score"] = (
            w_trends * df["trends_norm"]
            + w_wiki * df["wiki_norm"]
            + w_youtube * df["youtube_norm"]
        )
    else:
        total = w_trends + w_wiki
        if total > 0:
            df["interest_score"] = (
                (w_trends / total) * df["trends_norm"]
                + (w_wiki / total) * df["wiki_norm"]
            )
        else:
            df["interest_score"] = 0.0

    df["league"] = df["term"].map(TEAM_TO_LEAGUE)
    return df


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def render_dashboard() -> None:
    """Render the full dashboard."""

    # -- Sidebar configuration -----------------------------------------------
    st.sidebar.header("Configuration")

    selected_leagues = st.sidebar.multiselect(
        "Leagues",
        options=list(LEAGUE_TEAMS.keys()),
        default=list(LEAGUE_TEAMS.keys()),
    )

    window = st.sidebar.slider("Time window (days)", 7, 365, 90, step=7)

    st.sidebar.subheader("Metric Weights")
    w_trends = st.sidebar.slider("Google Trends", 0.0, 1.0, 0.4, step=0.05)
    w_wiki = st.sidebar.slider("Wikipedia", 0.0, 1.0, 0.4, step=0.05)
    w_youtube = st.sidebar.slider("YouTube", 0.0, 1.0, 0.2, step=0.05)

    total_w = w_trends + w_wiki + w_youtube
    if total_w > 0:
        w_trends, w_wiki, w_youtube = (
            w_trends / total_w,
            w_wiki / total_w,
            w_youtube / total_w,
        )

    yt_api_key = st.sidebar.text_input(
        "YouTube API key (optional)", type="password"
    )

    # -- Metric selector -----------------------------------------------------
    available_metrics = ["interest_score", "trends_norm", "wiki_norm"]
    if yt_api_key:
        available_metrics.append("youtube_norm")

    metric = st.selectbox(
        "Rank by",
        available_metrics,
        index=0,
        format_func=lambda m: m.replace("_", " ").title(),
    )

    if not selected_leagues:
        st.warning("Select at least one league.")
        return

    # -- Fetch data ----------------------------------------------------------
    with st.spinner("Fetching data ..."):
        data = fetch_interest_proxies(
            leagues=tuple(selected_leagues),
            days=window,
            yt_api_key=yt_api_key,
            w_trends=w_trends,
            w_wiki=w_wiki,
            w_youtube=w_youtube,
        )

    if data.empty:
        st.warning(
            "No data returned. Try widening the timeframe or selecting "
            "different leagues."
        )
        return

    # -- Rankings table ------------------------------------------------------
    latest = data["date"].max()
    snapshot = data[data["date"] == latest].sort_values(
        metric, ascending=False
    )

    st.subheader(f"Rankings \u2014 {latest}")
    display_cols = ["league", "term", "trends_norm", "wiki_norm"]
    if yt_api_key:
        display_cols.append("youtube_norm")
    display_cols.append("interest_score")

    st.dataframe(
        snapshot[display_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )

    # -- Bar chart -----------------------------------------------------------
    bar = (
        alt.Chart(snapshot)
        .mark_bar()
        .encode(
            x=alt.X("term:N", sort="-y", title="Team"),
            y=alt.Y(
                f"{metric}:Q",
                title=metric.replace("_", " ").title(),
            ),
            tooltip=[
                "term:N",
                "league:N",
                alt.Tooltip(f"{metric}:Q", format=".2f"),
            ],
            color=alt.Color(
                f"{metric}:Q", scale=alt.Scale(scheme="blues")
            ),
        )
        .properties(height=400)
    )
    st.altair_chart(bar, use_container_width=True)

    # -- Metric breakdown (expandable) ---------------------------------------
    with st.expander("Metric breakdown for each team"):
        breakdown_cols = [
            "league",
            "term",
            "trends_norm",
            "wiki_norm",
            "youtube_norm",
            "interest_score",
        ]
        st.dataframe(
            snapshot[breakdown_cols].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

    # -- Trendlines ----------------------------------------------------------
    st.subheader("Trendlines")
    focus_league = st.selectbox("Focus League", selected_leagues)
    subset = data[data["league"] == focus_league]

    line = (
        alt.Chart(subset)
        .mark_line()
        .encode(
            x="date:T",
            y=alt.Y(
                f"{metric}:Q",
                title=metric.replace("_", " ").title(),
            ),
            color="term:N",
            tooltip=[
                "date:T",
                "term:N",
                alt.Tooltip(f"{metric}:Q", format=".1f"),
            ],
        )
        .properties(height=420)
    )
    st.altair_chart(line, use_container_width=True)

    # -- Top Movers ----------------------------------------------------------
    st.subheader("Top Movers (7-day \u0394)")
    dmax = data["date"].max()
    current_week = data[
        (data["date"] <= dmax) & (data["date"] > dmax - timedelta(days=7))
    ]
    prev_week = data[
        (data["date"] <= dmax - timedelta(days=7))
        & (data["date"] > dmax - timedelta(days=14))
    ]
    w1 = current_week.groupby("term")[metric].mean()
    w0 = prev_week.groupby("term")[metric].mean()
    movers = (
        (w1 - w0).sort_values(ascending=False).rename("delta").reset_index()
    )
    movers["league"] = movers["term"].map(TEAM_TO_LEAGUE)
    st.dataframe(
        movers[["league", "term", "delta"]].head(12).reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    render_dashboard()
