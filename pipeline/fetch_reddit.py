"""
Fetch Reddit community activity for each team from the public JSON API.

Uses unauthenticated access (~10 req/min) with a 6-second delay between
requests.  Each team is searched within its league's subreddit for posts
from the past week.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

from lib.teams import REDDIT_SUBREDDITS, TEAM_TO_LEAGUE
from pipeline.utils import create_session

log = logging.getLogger(__name__)

_REDDIT_UA = "InterestMap/2.0 (sports dashboard; github.com/narendranag/interest-map)"


def fetch(teams: List[str], days: int = 7) -> pd.DataFrame:
    """Return DataFrame[date, team, league, post_count, total_score, total_comments]."""
    session = create_session(user_agent=_REDDIT_UA)
    cutoff = datetime.utcnow() - timedelta(days=days)
    all_rows: List[Dict] = []

    for team in teams:
        league = TEAM_TO_LEAGUE.get(team, "")
        subreddit = REDDIT_SUBREDDITS.get(league)
        if not subreddit:
            continue

        url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            f"?q={team}&sort=new&restrict_sr=on&t=week&limit=100"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 429:
                log.warning("Reddit rate-limited — sleeping 30s")
                time.sleep(30)
                resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                log.warning("Reddit %s: HTTP %d", team, resp.status_code)
                time.sleep(6)
                continue

            posts = resp.json().get("data", {}).get("children", [])

            # Aggregate per day
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

        time.sleep(6)  # respect ~10 req/min

    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame(columns=[
        "date", "team", "league", "post_count", "total_score", "total_comments",
    ])
