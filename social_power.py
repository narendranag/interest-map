"""
Streamlit application for calculating and visualising a "social power" score for
NBA, MLB and NHL teams.  The score blends multiple public proxies – Google
Trends search interest, Wikipedia pageviews, social media follower counts,
social engagement metrics, and YouTube channel statistics – to approximate
overall digital attention for each team over a chosen time window.

This app requires a few optional dependencies to pull real data:
* `pytrends` for Google Trends (install via pip).
* `requests` for HTTP calls to the Wikimedia pageviews API.
* Optionally, `googleapiclient.discovery` for YouTube Data API access if you
  supply an API key via the UI.

Usage:
    streamlit run social_power_app.py

The app lets you:
    • Select leagues and a time window (days).
    • Adjust the weight of each proxy metric.
    • Upload a CSV of social media followers and engagement per team.
    • Provide a YouTube API key to fetch channel statistics for each team.
    • View a ranking of teams by the final social power score, along with
      component metrics and interactive trend lines.

Notes:
    • Google Trends scores are relative (0–100 within the query) and not
      absolute search volume【913234186715494†L998-L1004】.
    • The Wikimedia pageviews API returns daily page views for articles【718207153011656†L124-L137】.
    • If a YouTube API key is not provided or the API call fails, the app
      assigns neutral zeros for YouTube metrics.
    • Uploaded follower data should contain columns named 'team', 'followers'
      and optionally 'engagement'.  If engagement is missing, a default
      neutral value of zero is used.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st
import altair as alt

try:
    # pytrends is used to fetch Google Trends data.  It is optional: if not
    # installed the app will warn and skip trends pulling.
    from pytrends.request import TrendReq  # type: ignore
except ImportError:
    TrendReq = None

try:
    # googleapiclient is used for YouTube Data API access.  It is optional and
    # requires a valid API key.  If unavailable the YouTube metrics will be
    # neutralized to zero.
    from googleapiclient.discovery import build  # type: ignore
except ImportError:
    build = None

try:
    # snscrape is used to scrape recent tweets for engagement metrics.  It
    # makes unauthenticated requests to Twitter and therefore may be subject
    # to rate limits.  It is optional; if not available engagement will
    # default to zero.
    import snscrape.modules.twitter as sntwitter  # type: ignore
except ImportError:
    sntwitter = None

# -----------------------------------------------------------------------------
# Team definitions
# -----------------------------------------------------------------------------
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
    "Arizona Diamondbacks", "Atlanta Braves", "Baltimore Orioles", "Boston Red Sox",
    "Chicago Cubs", "Chicago White Sox", "Cincinnati Reds", "Cleveland Guardians",
    "Colorado Rockies", "Detroit Tigers", "Houston Astros", "Kansas City Royals",
    "Los Angeles Angels", "Los Angeles Dodgers", "Miami Marlins", "Milwaukee Brewers",
    "Minnesota Twins", "New York Mets", "New York Yankees", "Oakland Athletics",
    "Philadelphia Phillies", "Pittsburgh Pirates", "San Diego Padres",
    "San Francisco Giants", "Seattle Mariners", "St. Louis Cardinals",
    "Tampa Bay Rays", "Texas Rangers", "Toronto Blue Jays", "Washington Nationals",
]

NHL_TEAMS: List[str] = [
    "Anaheim Ducks", "Arizona Coyotes", "Boston Bruins", "Buffalo Sabres",
    "Calgary Flames", "Carolina Hurricanes", "Chicago Blackhawks",
    "Colorado Avalanche", "Columbus Blue Jackets", "Dallas Stars",
    "Detroit Red Wings", "Edmonton Oilers", "Florida Panthers",
    "Los Angeles Kings", "Minnesota Wild", "Montreal Canadiens",
    "Nashville Predators", "New Jersey Devils", "New York Islanders",
    "New York Rangers", "Ottawa Senators", "Philadelphia Flyers",
    "Pittsburgh Penguins", "San Jose Sharks", "Seattle Kraken",
    "St. Louis Blues", "Tampa Bay Lightning", "Toronto Maple Leafs",
    "Vancouver Canucks", "Vegas Golden Knights", "Washington Capitals",
    "Winnipeg Jets",
]

LEAGUE_TEAMS: Dict[str, List[str]] = {
    "NBA": NBA_TEAMS,
    "MLB": MLB_TEAMS,
    "NHL": NHL_TEAMS,
}

# Mapping from team name to league, used later for league filtering
TEAM_TO_LEAGUE: Dict[str, str] = {t: lg for lg, teams in LEAGUE_TEAMS.items() for t in teams}

# -----------------------------------------------------------------------------
# Twitter handle mappings
# -----------------------------------------------------------------------------
# Many social metrics can be approximated from a team's official X/Twitter
# account.  The functions below use these handles to fetch follower counts and
# basic engagement.  Feel free to adjust or update the mapping if you notice
# newer or more accurate handles for a given team.
TEAM_TWITTER_HANDLES: Dict[str, str] = {
    # NBA
    "Atlanta Hawks": "ATLHawks",
    "Boston Celtics": "celtics",
    "Brooklyn Nets": "BrooklynNets",
    "Charlotte Hornets": "hornets",
    "Chicago Bulls": "chicagobulls",
    "Cleveland Cavaliers": "cavs",
    "Dallas Mavericks": "dallasmavs",
    "Denver Nuggets": "nuggets",
    "Detroit Pistons": "DetroitPistons",
    "Golden State Warriors": "warriors",
    "Houston Rockets": "HoustonRockets",
    "Indiana Pacers": "Pacers",
    "LA Clippers": "LAClippers",
    "Los Angeles Lakers": "Lakers",
    "Memphis Grizzlies": "memgrizz",
    "Miami Heat": "miamiheat",
    "Milwaukee Bucks": "Bucks",
    "Minnesota Timberwolves": "Timberwolves",
    "New Orleans Pelicans": "PelicansNBA",
    "New York Knicks": "nyknicks",
    "Oklahoma City Thunder": "okcthunder",
    "Orlando Magic": "OrlandoMagic",
    "Philadelphia 76ers": "sixers",
    "Phoenix Suns": "suns",
    "Portland Trail Blazers": "trailblazers",
    "Sacramento Kings": "SacramentoKings",
    "San Antonio Spurs": "spurs",
    "Toronto Raptors": "Raptors",
    "Utah Jazz": "utahjazz",
    "Washington Wizards": "WashWizards",
    # MLB
    "Arizona Diamondbacks": "Dbacks",
    "Atlanta Braves": "Braves",
    "Baltimore Orioles": "Orioles",
    "Boston Red Sox": "RedSox",
    "Chicago Cubs": "Cubs",
    "Chicago White Sox": "whitesox",
    "Cincinnati Reds": "Reds",
    "Cleveland Guardians": "CleGuardians",
    "Colorado Rockies": "Rockies",
    "Detroit Tigers": "tigers",
    "Houston Astros": "astros",
    "Kansas City Royals": "Royals",
    "Los Angeles Angels": "Angels",
    "Los Angeles Dodgers": "Dodgers",
    "Miami Marlins": "Marlins",
    "Milwaukee Brewers": "Brewers",
    "Minnesota Twins": "Twins",
    "New York Mets": "Mets",
    "New York Yankees": "Yankees",
    "Oakland Athletics": "Athletics",
    "Philadelphia Phillies": "Phillies",
    "Pittsburgh Pirates": "Pirates",
    "San Diego Padres": "Padres",
    "San Francisco Giants": "SFGiants",
    "Seattle Mariners": "Mariners",
    "St. Louis Cardinals": "Cardinals",
    "Tampa Bay Rays": "RaysBaseball",
    "Texas Rangers": "Rangers",
    "Toronto Blue Jays": "BlueJays",
    "Washington Nationals": "Nationals",
    # NHL
    "Anaheim Ducks": "AnaheimDucks",
    "Arizona Coyotes": "ArizonaCoyotes",
    "Boston Bruins": "NHLBruins",
    "Buffalo Sabres": "BuffaloSabres",
    "Calgary Flames": "NHLFlames",
    "Carolina Hurricanes": "Canes",
    "Chicago Blackhawks": "NHLBlackhawks",
    "Colorado Avalanche": "Avalanche",
    "Columbus Blue Jackets": "BlueJacketsNHL",
    "Dallas Stars": "DallasStars",
    "Detroit Red Wings": "DetroitRedWings",
    "Edmonton Oilers": "EdmontonOilers",
    "Florida Panthers": "FlaPanthers",
    "Los Angeles Kings": "LAKings",
    "Minnesota Wild": "mnwild",
    "Montreal Canadiens": "CanadiensMTL",
    "Nashville Predators": "PredsNHL",
    "New Jersey Devils": "NJDevils",
    "New York Islanders": "NYIslanders",
    "New York Rangers": "NYRangers",
    "Ottawa Senators": "Senators",
    "Philadelphia Flyers": "NHLFlyers",
    "Pittsburgh Penguins": "penguins",
    "San Jose Sharks": "SanJoseSharks",
    "Seattle Kraken": "SeattleKraken",
    "St. Louis Blues": "StLouisBlues",
    "Tampa Bay Lightning": "TBLightning",
    "Toronto Maple Leafs": "MapleLeafs",
    "Vancouver Canucks": "Canucks",
    "Vegas Golden Knights": "GoldenKnights",
    "Washington Capitals": "Capitals",
    "Winnipeg Jets": "NHLJets",
}

# -----------------------------------------------------------------------------
# Helper functions for data retrieval
# -----------------------------------------------------------------------------
def _select_timeframe(days: int) -> str:
    """Map a number of days to a valid Google Trends timeframe string.

    Google Trends only allows certain timeframes.  We approximate by choosing
    the closest available range to the requested number of days【429993507129749†L300-L311】.
    """
    if days <= 1:
        return f"now {min(days, 1)}-d"
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
    """Fetch daily Google Trends interest for a list of terms.

    Parameters
    ----------
    terms : List[str]
        Team names or search terms.
    days : int
        Number of days of history to fetch.  The function selects an appropriate
        timeframe string for Google Trends.

    Returns
    -------
    pd.DataFrame
        A dataframe with columns ['date', 'term', 'trends_score'] where
        `trends_score` is Google’s normalized interest value (0–100)【913234186715494†L998-L1004】.
    """
    if TrendReq is None:
        st.warning("pytrends is not installed. Install it with `pip install pytrends`.")
        return pd.DataFrame(columns=["date", "term", "trends_score"])

    pytrends = TrendReq(hl="en-US", tz=0)
    batch_size = 5
    frames: List[pd.DataFrame] = []
    timeframe = _select_timeframe(days)
    for i in range(0, len(terms), batch_size):
        batch = terms[i:i + batch_size]
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo="")
            data = pytrends.interest_over_time().reset_index()
        except Exception:
            # On error (e.g., HTTP 400), skip this batch
            continue
        if data.empty:
            continue
        melted = data.melt(id_vars=["date"], value_vars=batch, var_name="term", value_name="trends_score")
        melted["date"] = pd.to_datetime(melted["date"]).dt.date
        frames.append(melted[["date", "term", "trends_score"]])
        time.sleep(1.0)  # Respectful delay
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame(columns=["date", "term", "trends_score"])


def fetch_wikipedia_pageviews(team_name: str, start_date: datetime, end_date: datetime) -> pd.Series:
    """Fetch daily Wikipedia pageviews for a given team.

    Parameters
    ----------
    team_name : str
        Name of the team whose Wikipedia page views to fetch.
    start_date, end_date : datetime
        Date range for the pageviews.

    Returns
    -------
    pd.Series
        A series indexed by date with the number of page views for each day.
    """
    # Convert spaces to underscores for article title
    page_title = team_name.replace(" ", "_")
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia.org/all-access/all-agents/{page_title}/daily/"
        f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json().get("items", [])
        rows = []
        for it in data:
            # timestamp is in format YYYYMMDDHH; parse date portion
            ts = str(it.get("timestamp"))
            d = datetime.strptime(ts[:8], "%Y%m%d").date()
            rows.append((d, it.get("views", 0)))
        if rows:
            dates, views = zip(*rows)
            return pd.Series(views, index=dates)
    except Exception:
        pass
    # Return empty series on failure
    return pd.Series(dtype=float)


def fetch_youtube_channel_stats(team_name: str, api_key: Optional[str]) -> Tuple[float, float]:
    """Fetch YouTube view and subscriber counts for the first matching channel.

    Parameters
    ----------
    team_name : str
        The name of the team to search for on YouTube.
    api_key : Optional[str]
        A Google API key with access to the YouTube Data API v3.  If None,
        the function returns zeros.

    Returns
    -------
    (view_count, subscriber_count) : Tuple[float, float]
        The total view count and subscriber count for the channel, or (0, 0) if
        the API cannot be called.【3665824008393†L430-L452】
    """
    if not api_key or build is None:
        return 0.0, 0.0
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        # Search for the official team channel; we search for "team name" filtered by channel type
        search_response = youtube.search().list(
            q=team_name,
            part="id,snippet",
            type="channel",
            maxResults=1,
        ).execute()
        items = search_response.get("items", [])
        if not items:
            return 0.0, 0.0
        channel_id = items[0]["id"]["channelId"]
        # Retrieve statistics
        channel_response = youtube.channels().list(
            id=channel_id,
            part="statistics",
        ).execute()
        stats = channel_response["items"][0]["statistics"]
        view_count = float(stats.get("viewCount", 0))
        subscriber_count = float(stats.get("subscriberCount", 0))
        return view_count, subscriber_count
    except Exception:
        return 0.0, 0.0


def normalize_series(series: pd.Series) -> pd.Series:
    """Normalize a series to 0–100 scale.  Returns zeros if constant or empty."""
    if series.empty or series.max() == series.min():
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.min()) / (series.max() - series.min()) * 100.0


def normalize_frame_per_team(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize each column of a DataFrame to 0–100.  Columns represent teams."""
    return df.apply(normalize_series)

# -----------------------------------------------------------------------------
# Twitter helpers
# -----------------------------------------------------------------------------
def fetch_twitter_followers(handle: str) -> float:
    """
    Fetch the follower count for a Twitter/X account via an unofficial endpoint.

    This function calls the public endpoint used by Twitter's follow button
    widgets.  It returns a JSON list with follower counts and other metadata.
    If the request fails or the expected field is missing, the function
    returns 0.0.

    Parameters
    ----------
    handle : str
        The Twitter username without the leading '@'.

    Returns
    -------
    float
        The follower count for the account, or 0 if unavailable.
    """
    url = (
        "https://cdn.syndication.twimg.com/widgets/followbutton/info.json"
        f"?screen_names={handle}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            info = data[0]
            # Twitter uses both 'followers_count' and 'followersCount' in its
            # endpoints; handle either case.
            return float(
                info.get("followers_count")
                or info.get("followersCount")
                or 0
            )
    except Exception:
        pass
    return 0.0


def fetch_twitter_engagement(handle: str, max_tweets: int = 30) -> float:
    """
    Estimate engagement for a Twitter account by averaging likes, retweets and
    replies across recent tweets.

    The function uses snscrape (if installed) to pull recent tweets from the
    account and computes the average engagement per tweet.  Engagement per
    tweet is defined as (likes + retweets + replies).  The function
    normalizes the result by the follower count to get a relative rate.

    If snscrape is not installed or an error occurs, the function returns 0.

    Parameters
    ----------
    handle : str
        Twitter username without '@'.
    max_tweets : int, optional
        Maximum number of recent tweets to analyze (default is 30).

    Returns
    -------
    float
        The average engagement per follower for the account, or 0 on failure.
    """
    if sntwitter is None:
        return 0.0
    try:
        query = f"from:{handle}"
        tweets = []
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i >= max_tweets:
                break
            tweets.append(tweet)
        if not tweets:
            return 0.0
        total_engagement = 0
        for t in tweets:
            likes = getattr(t, "likeCount", 0)
            retweets = getattr(t, "retweetCount", 0)
            replies = getattr(t, "replyCount", 0)
            total_engagement += likes + retweets + replies
        avg_engagement = total_engagement / len(tweets)
        followers = fetch_twitter_followers(handle)
        if followers > 0:
            return avg_engagement / followers
        return 0.0
    except Exception:
        return 0.0


def compute_social_power(
    trends_df: pd.DataFrame,
    wiki_df: pd.DataFrame,
    followers_df: pd.DataFrame,
    youtube_views: pd.Series,
    youtube_subs: pd.Series,
    weights: Dict[str, float],
) -> pd.DataFrame:
    """Combine proxy metrics into a social power score.

    Parameters
    ----------
    trends_df : pd.DataFrame
        DataFrame of normalized Google Trends scores indexed by date with team
        columns.
    wiki_df : pd.DataFrame
        DataFrame of normalized Wikipedia pageviews indexed by date with team
        columns.
    followers_df : pd.DataFrame
        DataFrame with index of team names and columns 'followers' and
        optional 'engagement'.
    youtube_views, youtube_subs : pd.Series
        Series of normalized YouTube metrics indexed by team names.
    weights : Dict[str, float]
        Weights for each metric: keys are 'trends', 'wiki', 'followers',
        'engagement', 'youtube'.  Values should sum to 1.0.

    Returns
    -------
    pd.DataFrame
        A DataFrame with rows for teams and columns for each metric and the
        final social power score.
    """
    # Use the latest date for time series metrics
    latest_date = trends_df.index.max() if not trends_df.empty else None
    results = []
    for team in followers_df.index:
        # Retrieve normalized values; default to zero if missing
        trends_val = trends_df.loc[latest_date, team] if latest_date is not None and team in trends_df.columns else 0.0
        wiki_val = wiki_df.loc[latest_date, team] if latest_date is not None and team in wiki_df.columns else 0.0
        followers_val = followers_df.loc[team, "followers_norm"] if "followers_norm" in followers_df.columns else 0.0
        engagement_val = followers_df.loc[team, "engagement_norm"] if "engagement_norm" in followers_df.columns else 0.0
        youtube_val = (youtube_views.get(team, 0.0) + youtube_subs.get(team, 0.0)) / 2.0
        # Compute weighted sum
        score = (
            weights.get("trends", 0.0) * trends_val +
            weights.get("wiki", 0.0) * wiki_val +
            weights.get("followers", 0.0) * followers_val +
            weights.get("engagement", 0.0) * engagement_val +
            weights.get("youtube", 0.0) * youtube_val
        )
        results.append(
            {
                "team": team,
                "trends": trends_val,
                "wiki": wiki_val,
                "followers": followers_val,
                "engagement": engagement_val,
                "youtube": youtube_val,
                "social_power_score": score,
            }
        )
    return pd.DataFrame(results)


# -----------------------------------------------------------------------------
# Streamlit application
# -----------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Team Social Power Dashboard", layout="wide")
    st.title("Team Social Power Dashboard")
    st.caption(
        "Combine Google Trends, Wikipedia pageviews, social followers, engagement and YouTube metrics to "
        "approximate digital attention for NBA, MLB and NHL teams."
    )

    # Sidebar controls
    st.sidebar.header("Configuration")
    selected_leagues = st.sidebar.multiselect(
        "Leagues", list(LEAGUE_TEAMS.keys()), default=list(LEAGUE_TEAMS.keys())
    )
    days = st.sidebar.slider("Time window (days)", 7, 365, 90, step=7)
    # Weight inputs
    st.sidebar.subheader("Weights (sum to 1)")
    default_weights = {"trends": 0.3, "wiki": 0.2, "followers": 0.3, "engagement": 0.1, "youtube": 0.1}
    weights = {}
    for metric in ["trends", "wiki", "followers", "engagement", "youtube"]:
        weights[metric] = st.sidebar.number_input(
            f"Weight for {metric}", min_value=0.0, max_value=1.0, value=float(default_weights[metric]), step=0.05
        )
    # Normalize weights to sum to 1
    total_w = sum(weights.values())
    if total_w > 0:
        weights = {k: v / total_w for k, v in weights.items()}

    # Option to automatically fetch Twitter metrics
    fetch_twitter = st.sidebar.checkbox(
        "Automatically fetch Twitter metrics (followers & engagement)", value=True
    )
    # File uploader for social media metrics: used as override or fallback when
    # automatic fetching is disabled.
    uploaded_file = st.sidebar.file_uploader(
        "Upload social media metrics CSV (columns: team, followers, engagement)",
        type=["csv"],
    )
    # YouTube API key input for retrieving channel statistics
    yt_api_key = st.sidebar.text_input("YouTube API key (optional)", type="password")

    # Filter teams based on selected leagues
    all_selected_teams = [t for lg in selected_leagues for t in LEAGUE_TEAMS[lg]]

    # Data retrieval with caching
    @st.cache_data(ttl=3600, show_spinner=False)
    def load_trends(teams: Tuple[str, ...], days: int) -> pd.DataFrame:
        return fetch_google_trends_daily(list(teams), days)

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_wiki(team: str, days: int) -> pd.Series:
        end = datetime.utcnow().date()
        start = end - timedelta(days=days)
        return fetch_wikipedia_pageviews(team, start, end)

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_youtube_stats(team: str, api_key: Optional[str]) -> Tuple[float, float]:
        return fetch_youtube_channel_stats(team, api_key)

    # Retrieve trends data
    if all_selected_teams:
        trends_raw = load_trends(tuple(all_selected_teams), days)
    else:
        trends_raw = pd.DataFrame(columns=["date", "term", "trends_score"])

    # Pivot and normalize trends
    if not trends_raw.empty:
        trends_pivot = trends_raw.pivot_table(index="date", columns="term", values="trends_score")
        trends_norm = normalize_frame_per_team(trends_pivot)
    else:
        trends_norm = pd.DataFrame()

    # Retrieve wiki data and build DataFrame
    wiki_dict: Dict[str, pd.Series] = {}
    for team in all_selected_teams:
        wiki_series = load_wiki(team, days)
        if not wiki_series.empty:
            wiki_dict[team] = wiki_series
    if wiki_dict:
        wiki_df = pd.DataFrame(wiki_dict)
        wiki_norm = normalize_frame_per_team(wiki_df)
    else:
        wiki_norm = pd.DataFrame()

    # Prepare followers and engagement data
    if fetch_twitter:
        # Use Twitter handles to fetch real-time follower and engagement metrics
        @st.cache_data(ttl=3600, show_spinner=False)
        def load_twitter_metrics(team: str) -> Tuple[float, float]:
            handle = TEAM_TWITTER_HANDLES.get(team)
            if not handle:
                return (0.0, 0.0)
            followers = fetch_twitter_followers(handle)
            engagement = fetch_twitter_engagement(handle, max_tweets=30)
            return (followers, engagement)
        followers_list: List[float] = []
        engagement_list: List[float] = []
        for team in all_selected_teams:
            f_val, e_val = load_twitter_metrics(team)
            followers_list.append(f_val)
            engagement_list.append(e_val)
        followers_df = pd.DataFrame(
            {
                "team": all_selected_teams,
                "followers": followers_list,
                "engagement": engagement_list,
            }
        ).set_index("team")
    else:
        # Load from uploaded CSV; fallback to zeros
        if uploaded_file is not None:
            try:
                tmp_df = pd.read_csv(uploaded_file)
            except Exception:
                tmp_df = pd.DataFrame(columns=["team", "followers", "engagement"])
        else:
            tmp_df = pd.DataFrame(columns=["team", "followers", "engagement"])
        followers_df = tmp_df.set_index("team") if not tmp_df.empty else pd.DataFrame(index=all_selected_teams)
        if "followers" not in followers_df.columns:
            followers_df["followers"] = 0.0
        if "engagement" not in followers_df.columns:
            followers_df["engagement"] = 0.0
        followers_df = followers_df.reindex(all_selected_teams).fillna(0.0)
    # Normalize followers and engagement across teams
    followers_df["followers_norm"] = normalize_series(followers_df["followers"])
    followers_df["engagement_norm"] = normalize_series(followers_df["engagement"])

    # Retrieve YouTube statistics
    yt_views: Dict[str, float] = {}
    yt_subs: Dict[str, float] = {}
    for team in all_selected_teams:
        v, s = load_youtube_stats(team, yt_api_key) if yt_api_key else (0.0, 0.0)
        yt_views[team] = v
        yt_subs[team] = s
    # Normalize YouTube metrics across teams
    yt_views_norm = normalize_series(pd.Series(yt_views))
    yt_subs_norm = normalize_series(pd.Series(yt_subs))

    # Compute social power scores
    if not followers_df.empty:
        scores_df = compute_social_power(
            trends_norm,
            wiki_norm,
            followers_df,
            yt_views_norm,
            yt_subs_norm,
            weights,
        )
    else:
        scores_df = pd.DataFrame()

    # Display results
    if scores_df.empty:
        st.warning("No data available for the selected configuration.")
        return

    latest_date = trends_norm.index.max() if not trends_norm.empty else "N/A"
    st.subheader(f"Social Power Rankings – {latest_date}")
    rankings = scores_df.sort_values("social_power_score", ascending=False)
    st.dataframe(
        rankings[["team", "social_power_score", "trends", "wiki", "followers", "engagement", "youtube"]].reset_index(drop=True),
        use_container_width=True,
    )

    # Chart: Social Power Score by Team
    chart = alt.Chart(rankings).mark_bar().encode(
        x=alt.X("team:N", sort="-y", title="Team"),
        y=alt.Y("social_power_score:Q", title="Social Power Score"),
        tooltip=["team:N", alt.Tooltip("social_power_score:Q", format=".2f")],
        color=alt.Color("social_power_score:Q", scale=alt.Scale(scheme="blues")),
    ).properties(
        height=400,
        title="Team Social Power Scores",
    )
    st.altair_chart(chart, use_container_width=True)

    # Detailed metrics breakdown on expand
    with st.expander("Metric breakdown for each team"):
        st.dataframe(
            rankings[["team", "trends", "wiki", "followers", "engagement", "youtube", "social_power_score"]].reset_index(drop=True),
            use_container_width=True,
        )

    # Trendlines if time series available
    if not trends_norm.empty:
        st.subheader("Trendlines (Google Trends + Wikipedia)")
        pick_team = st.selectbox("Select a team", rankings["team"])
        if pick_team in trends_norm.columns:
            ts_df = pd.DataFrame({
                "date": trends_norm.index,
                "trends": trends_norm[pick_team],
                "wiki": wiki_norm[pick_team] if pick_team in wiki_norm.columns else 0.0,
            })
            ts_df = ts_df.melt(id_vars="date", value_vars=["trends", "wiki"], var_name="metric", value_name="value")
            line_chart = alt.Chart(ts_df).mark_line().encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("value:Q", title="Normalized Score (0–100)"),
                color="metric:N",
                tooltip=["date:T", "metric:N", alt.Tooltip("value:Q", format=".1f")],
            ).properties(height=400)
            st.altair_chart(line_chart, use_container_width=True)


if __name__ == "__main__":
    main()