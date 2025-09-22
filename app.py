"""
NBA/MLB/NHL Interest Dashboard
================================

This Streamlit app builds an interactive dashboard to compare interest in
professional sports teams across the NBA, MLB and NHL. It uses publicly
available proxies—Google Trends and Wikipedia Pageviews—to estimate
advertiser interest. The app can be easily modified to use your own
bidstream metrics (e.g., daily bid volume and bid rate per team) by
replacing the data loader.

Running the app locally
-----------------------

.. code-block:: bash

    pip install -r requirements.txt
    streamlit run app.py

Dockerized deployment is also supported via the provided Dockerfile and
docker-compose.yml. See the README for deployment instructions.

"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List

import altair as alt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from pytrends.request import TrendReq
from requests.adapters import HTTPAdapter, Retry


# ---------------------------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="NBA/MLB/NHL Interest Dashboard",
    layout="wide",
)

st.title("Advertiser Interest – Team Comparison")
st.caption(
    "Proxy = Google Trends + Wikipedia Pageviews (daily)."
)


# ---------------------------------------------------------------------------
# Static team definitions
# ---------------------------------------------------------------------------

# Complete list of NBA teams
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

# Complete list of MLB teams
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

# Complete list of NHL teams
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
    "Utah Mammoth", "Vancouver Canucks", "Vegas Golden Knights", 
    "Washington Capitals","Winnipeg Jets",
]

# Mapping of league to teams
LEAGUE_TEAMS: Dict[str, List[str]] = {
    "NBA": NBA_TEAMS,
    "MLB": MLB_TEAMS,
    "NHL": NHL_TEAMS,
}

# Reverse mapping from team to league
TEAM_TO_LEAGUE: Dict[str, str] = {
    team: league for league, teams in LEAGUE_TEAMS.items() for team in teams
}


# ---------------------------------------------------------------------------
# HTTP session configuration with retries
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
    session.headers.update({"User-Agent": "Laminar-Interest-Dashboard/1.0"})
    return session


# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------

def fetch_google_trends_daily(
    terms: List[str],
    tz: int = 0,
    timeframe: str = "90d",
    batch_size: int = 5,
) -> pd.DataFrame:
    """Fetch daily Google Trends scores for a list of terms.

    Google Trends restricts daily resolution to five terms per request.
    This function fetches terms in batches and returns a long-form
    DataFrame with columns [date, term, trends_score]. Each batch is
    normalized separately by Google.

    Parameters
    ----------
    terms : list of str
        List of team names to query.
    tz : int
        Timezone offset for pytrends requests.
    timeframe : str
        Pytrends timeframe string, e.g. "90d".
    batch_size : int
        Number of terms per pytrends request (max 5).

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns ``date``, ``term``, and ``trends_score``.
    """
    pytrends = TrendReq(hl="en-US", tz=tz)
    frames: List[pd.DataFrame] = []
    for i in range(0, len(terms), batch_size):
        batch = terms[i : i + batch_size]
        try:
            # Build the payload for this batch. If Google rejects the timeframe
            # or another error occurs (e.g. a 400 response), skip this batch.
            pytrends.build_payload(batch, timeframe=timeframe, geo="")
            data = pytrends.interest_over_time().reset_index()
        except Exception:
            # Skip batches that raise exceptions (e.g. pytrends.exceptions.ResponseError)
            continue
        if data.empty:
            continue
        # Reshape into long form
        melted = data.melt(
            id_vars=["date"],
            value_vars=batch,
            var_name="term",
            value_name="trends_score",
        )
        melted["date"] = pd.to_datetime(melted["date"]).dt.date
        frames.append(melted)
        time.sleep(1.2)  # rate limiting
    if not frames:
        return pd.DataFrame(columns=["date", "term", "trends_score"])
    return pd.concat(frames, ignore_index=True)


def fetch_wikipedia_daily(
    session: requests.Session,
    team: str,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """Fetch daily Wikipedia pageviews for a team.

    Parameters
    ----------
    session : requests.Session
        Configured HTTP session with retry logic.
    team : str
        Team name.
    start_date : datetime
        Start date (inclusive).
    end_date : datetime
        End date (inclusive).

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns ``date``, ``term``, ``wiki_views``.
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
        # Timestamp is like YYYYMMDD00
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


def _normalize(series: pd.Series) -> pd.Series:
    """Normalize a numeric series to the 0–100 range.

    If all values are equal, returns a zero-valued series of the same length.
    """
    if series.max() == series.min():
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.min()) / (series.max() - series.min()) * 100.0


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_interest_proxies(
    leagues: List[str] = ("NBA", "MLB", "NHL"),
    days: int = 90,
) -> pd.DataFrame:
    """Fetch and blend proxy interest metrics.

    Combines daily Google Trends and Wikipedia Pageviews into a single
    ``interest_score`` per team per day. Results are cached for one hour.

    Parameters
    ----------
    leagues : list of str
        Leagues to include. Default includes all three.
    days : int
        Number of days of history.

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns [date, term, trends_score, wiki_views,
        trends_norm, wiki_norm, interest_score, league].
    """
    session = http_session()
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    # Gather all teams from selected leagues
    all_terms: List[str] = [team for lg in leagues for team in LEAGUE_TEAMS[lg]]
    # Select a valid timeframe string for pytrends based on the window length.
    # Pytrends only accepts a handful of timeframe formats; see
    # https://pypi.org/project/pytrends/ for details. Using an invalid timeframe
    # will result in a 400 response from Google. The logic below attempts to
    # choose the closest supported window for the requested number of days:
    #  - up to 7 days: "now X-d" (daily resolution for 1 or 7 days)
    #  - up to 1 month: "today 1-m" (monthly resolution; used for 2–30 days)
    #  - up to 3 months: "today 3-m" (monthly resolution)
    #  - up to 12 months: "today 12-m" (monthly resolution)
    #  - longer: "today 5-y" (multi-year resolution)
    if days <= 7:
        timeframe_str = f"now {min(days, 7)}-d"
    elif days <= 30:
        timeframe_str = "today 1-m"
    elif days <= 90:
        timeframe_str = "today 3-m"
    elif days <= 365:
        timeframe_str = "today 12-m"
    else:
        timeframe_str = "today 5-y"
    # Fetch Google Trends using the computed timeframe.
    trends = fetch_google_trends_daily(all_terms, tz=0, timeframe=timeframe_str, batch_size=5)
    # Fetch Wikipedia pageviews
    wiki_frames = []
    for term in all_terms:
        wiki_frames.append(fetch_wikipedia_daily(session, term, start_date, end_date))
    wiki = pd.concat(wiki_frames, ignore_index=True) if wiki_frames else pd.DataFrame(columns=["date", "term", "wiki_views"])
    # Merge and sort
    df = pd.merge(trends, wiki, on=["date", "term"], how="outer").sort_values(["term", "date"])
    # Fill missing trends_score values by interpolation/forward/back fill within team
    df["trends_score"] = df.groupby("term")["trends_score"].transform(
        lambda s: s.interpolate().fillna(method="bfill").fillna(method="ffill")
    )
    df["wiki_views"] = df["wiki_views"].fillna(0)
    # Normalize each metric per team
    df["trends_norm"] = df.groupby("term")["trends_score"].transform(_normalize)
    df["wiki_norm"] = df.groupby("term")["wiki_views"].transform(_normalize)
    # Weighted interest score
    TRENDS_W, WIKI_W = 0.6, 0.4
    df["interest_score"] = TRENDS_W * df["trends_norm"] + WIKI_W * df["wiki_norm"]
    # Map league
    df["league"] = df["term"].map(TEAM_TO_LEAGUE)
    return df


# ---------------------------------------------------------------------------
# Streamlit interface
# ---------------------------------------------------------------------------

def render_dashboard() -> None:
    """Render the Streamlit UI for the dashboard."""
    # Selection widgets
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        selected_leagues = st.multiselect(
            "Leagues",
            options=list(LEAGUE_TEAMS.keys()),
            default=list(LEAGUE_TEAMS.keys()),
        )
    with col2:
        # Choose timeframe in days
        window = st.slider("Window (days)", 30, 365, 90, step=15)
    with col3:
        # Choose metric to rank by
        metric = st.selectbox(
            "Rank by",
            ["interest_score", "trends_norm", "wiki_norm"],
            index=0,
            format_func=lambda m: m.replace("_", " ").title(),
        )
    # Fetch data
    data = fetch_interest_proxies(leagues=tuple(selected_leagues), days=window)
    if data.empty:
        st.warning("No data returned. Try widening the timeframe or reducing the number of teams.")
        return
    latest = data["date"].max()
    snapshot = data[data["date"] == latest].sort_values(metric, ascending=False)
    st.subheader(f"Rankings – {latest}")
    st.dataframe(
        snapshot[["league", "term", metric]].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )
    # Trendlines
    focus_league = st.selectbox("Focus League", selected_leagues)
    subset = data[data["league"] == focus_league]
    line_chart = alt.Chart(subset).mark_line().encode(
        x="date:T",
        y=alt.Y(f"{metric}:Q", title=metric.replace("_", " ").title()),
        color="term:N",
        tooltip=["date:T", "term:N", alt.Tooltip(f"{metric}:Q", format=".1f")],
    ).properties(height=420)
    st.altair_chart(line_chart, use_container_width=True)
    # Top movers
    st.subheader("Top Movers (7-day Δ)")
    dmax = data["date"].max()
    current_week = data[(data["date"] <= dmax) & (data["date"] > dmax - timedelta(days=7))]
    prev_week = data[(data["date"] <= dmax - timedelta(days=7)) & (data["date"] > dmax - timedelta(days=14))]
    w1 = current_week.groupby("term")[metric].mean()
    w0 = prev_week.groupby("term")[metric].mean()
    movers = (w1 - w0).sort_values(ascending=False).rename("delta").reset_index()
    movers["league"] = movers["term"].map(TEAM_TO_LEAGUE)
    st.dataframe(
        movers[["league", "term", "delta"]].head(12).reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    render_dashboard()