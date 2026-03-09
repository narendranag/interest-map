"""
Fetch Reddit community activity for each team via public JSON endpoints.

Reddit's public JSON API (appending .json to any URL) works without
authentication.  A custom User-Agent is required to avoid 429 errors.
Rate-limited to ~2 s between requests to stay well within limits.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import requests

from lib.teams import REDDIT_SUBREDDITS, TEAM_TO_LEAGUE

log = logging.getLogger(__name__)

_USER_AGENT = (
    "InterestMap/2.0 (github.com/narendranag/interest-map) "
    "Python/requests"
)


def fetch(teams: List[str], days: int = 7) -> pd.DataFrame:
    """Return DataFrame[date, team, league, post_count, total_score, total_comments]."""
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    cutoff = datetime.utcnow() - timedelta(days=days)
    all_rows: List[Dict] = []

    for team in teams:
        league = TEAM_TO_LEAGUE.get(team, "")
        subreddit = REDDIT_SUBREDDITS.get(league)
        if not subreddit:
            continue

        encoded_team = urllib.parse.quote(team)
        url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            f"?q={encoded_team}&sort=new&restrict_sr=on&t=week&limit=100"
        )
        try:
            resp = session.get(url, timeout=20)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                log.warning("Reddit rate-limited — sleeping %ds", retry_after)
                time.sleep(retry_after)
                resp = session.get(url, timeout=20)

            if resp.status_code != 200:
                log.warning("Reddit %s: HTTP %d", team, resp.status_code)
                time.sleep(2)
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

        time.sleep(2)  # Conservative rate limiting for public endpoints

    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame(columns=[
        "date", "team", "league", "post_count", "total_score", "total_comments",
    ])
