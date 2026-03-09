"""
Fetch Reddit community activity for each team via OAuth2.

Reddit requires OAuth2 authentication for API access.  Set the environment
variables ``REDDIT_CLIENT_ID`` and ``REDDIT_CLIENT_SECRET`` (create a free
"script" app at https://www.reddit.com/prefs/apps).  If credentials are
missing the fetcher is skipped gracefully.

With OAuth2 the rate limit is 60 req/min (vs. blocked for unauthenticated).
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

from lib.teams import REDDIT_SUBREDDITS, TEAM_TO_LEAGUE

log = logging.getLogger(__name__)

_USER_AGENT = "InterestMap/2.0 (by /u/interest-map-bot; github.com/narendranag/interest-map)"


def _get_oauth_token() -> Optional[str]:
    """Obtain a Reddit OAuth2 bearer token using client-credentials flow."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        log.warning(
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set — "
            "skipping Reddit.  Create a free app at "
            "https://www.reddit.com/prefs/apps"
        )
        return None

    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": _USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if token:
            log.info("Reddit OAuth2 token obtained")
        return token
    except Exception as exc:
        log.warning("Reddit OAuth2 token request failed: %s", exc)
        return None


def fetch(teams: List[str], days: int = 7) -> pd.DataFrame:
    """Return DataFrame[date, team, league, post_count, total_score, total_comments]."""
    token = _get_oauth_token()
    if token is None:
        return pd.DataFrame(columns=[
            "date", "team", "league", "post_count", "total_score", "total_comments",
        ])

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "User-Agent": _USER_AGENT,
    })

    cutoff = datetime.utcnow() - timedelta(days=days)
    all_rows: List[Dict] = []

    for team in teams:
        league = TEAM_TO_LEAGUE.get(team, "")
        subreddit = REDDIT_SUBREDDITS.get(league)
        if not subreddit:
            continue

        encoded_team = urllib.parse.quote(team)
        url = (
            f"https://oauth.reddit.com/r/{subreddit}/search"
            f"?q={encoded_team}&sort=new&restrict_sr=on&t=week&limit=100"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 429:
                log.warning("Reddit rate-limited — sleeping 10s")
                time.sleep(10)
                resp = session.get(url, timeout=20)
            if resp.status_code == 401:
                # Token expired — re-auth
                new_token = _get_oauth_token()
                if new_token:
                    session.headers["Authorization"] = f"Bearer {new_token}"
                    resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                log.warning("Reddit %s: HTTP %d", team, resp.status_code)
                time.sleep(1)
                continue

            posts = resp.json().get("data", {}).get("children", [])

            daily: Dict[str, Dict] = {}
            for post in posts:
                d = post.get("data", {})
                created = d.get("created_utc", 0)
                post_date = datetime.utcfromtimestamp(created).date()
                if datetime.combine(post_date, datetime.min.time()) < cutoff:
                    continue
                key = str(post_date)
                if key not in daily:
                    daily[key] = {"post_count": 0, "total_score": 0, "total_comments": 0}
                daily[key]["post_count"] += 1
                daily[key]["total_score"] += d.get("score", 0)
                daily[key]["total_comments"] += d.get("num_comments", 0)

            for date_str, metrics in daily.items():
                all_rows.append({
                    "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                    "team": team,
                    "league": league,
                    **metrics,
                })
        except Exception as exc:
            log.warning("Reddit %s failed: %s", team, exc)

        time.sleep(1)  # 60 req/min = 1s between requests

    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame(columns=[
        "date", "team", "league", "post_count", "total_score", "total_comments",
    ])
