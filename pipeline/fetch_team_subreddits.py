"""
Fetch team-specific subreddit metrics via Reddit's public JSON endpoints.

Collects subscribers, active users, recent post volume, and average post
score for each team's dedicated subreddit.  No API key required — uses the
same public JSON pattern as ``fetch_reddit.py``.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, List

import pandas as pd
import requests

from lib.teams import TEAM_SUBREDDITS, TEAM_TO_LEAGUE

log = logging.getLogger(__name__)

_USER_AGENT = (
    "InterestMap/2.0 (github.com/narendranag/interest-map) "
    "Python/requests"
)


def fetch() -> pd.DataFrame:
    """Return DataFrame[date, team, league, subreddit, subscribers, active_users, posts_24h, avg_score]."""
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    today = datetime.utcnow().date()
    rows: List[Dict] = []

    for team, subreddit in TEAM_SUBREDDITS.items():
        league = TEAM_TO_LEAGUE.get(team, "")

        # --- Subreddit about info (subscribers, active users) ---
        about_url = f"https://www.reddit.com/r/{subreddit}/about.json"
        subscribers = 0
        active_users = 0
        try:
            resp = session.get(about_url, timeout=20)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                log.warning("Rate-limited on %s — sleeping %ds", subreddit, retry_after)
                time.sleep(retry_after)
                resp = session.get(about_url, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                subscribers = data.get("subscribers", 0)
                active_users = data.get("accounts_active", 0) or data.get("active_user_count", 0)
            else:
                log.warning("r/%s about: HTTP %d", subreddit, resp.status_code)
        except Exception as exc:
            log.warning("r/%s about failed: %s", subreddit, exc)

        time.sleep(2)

        # --- Recent hot posts (post volume and engagement) ---
        hot_url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
        posts_24h = 0
        total_score = 0
        post_count = 0
        try:
            resp = session.get(hot_url, timeout=20)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                log.warning("Rate-limited on %s — sleeping %ds", subreddit, retry_after)
                time.sleep(retry_after)
                resp = session.get(hot_url, timeout=20)
            if resp.status_code == 200:
                children = resp.json().get("data", {}).get("children", [])
                cutoff = datetime.utcnow().timestamp() - 86400  # 24 hours
                for child in children:
                    d = child.get("data", {})
                    if d.get("stickied"):
                        continue
                    post_count += 1
                    total_score += d.get("score", 0)
                    if d.get("created_utc", 0) >= cutoff:
                        posts_24h += 1
            else:
                log.warning("r/%s hot: HTTP %d", subreddit, resp.status_code)
        except Exception as exc:
            log.warning("r/%s hot failed: %s", subreddit, exc)

        avg_score = total_score / max(post_count, 1)

        rows.append({
            "date": today,
            "team": team,
            "league": league,
            "subreddit": subreddit,
            "subscribers": subscribers,
            "active_users": active_users,
            "posts_24h": posts_24h,
            "avg_score": round(avg_score, 1),
        })

        log.info(
            "r/%s: %d subs, %d active, %d posts/24h, avg score %.1f",
            subreddit, subscribers, active_users, posts_24h, avg_score,
        )

        time.sleep(2)

    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=[
        "date", "team", "league", "subreddit",
        "subscribers", "active_users", "posts_24h", "avg_score",
    ])
