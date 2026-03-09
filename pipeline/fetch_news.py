"""
Count daily news articles per team using Google News RSS feeds.

Google News RSS is free, requires no API key, and has no documented rate
limits.  We add a small delay between requests out of courtesy.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

log = logging.getLogger(__name__)


def fetch(teams: List[str], days: int = 7) -> pd.DataFrame:
    """Return DataFrame[date, team, article_count]."""
    try:
        import feedparser
    except ImportError:
        log.warning("feedparser not installed — skipping news")
        return pd.DataFrame(columns=["date", "team", "article_count"])

    cutoff = (datetime.utcnow() - timedelta(days=days)).date()
    all_rows: List[Dict] = []

    for team in teams:
        encoded = urllib.parse.quote(f'"{team}"')
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            feed = feedparser.parse(url)
            daily_counts: Dict[str, int] = {}
            for entry in feed.get("entries", []):
                published = entry.get("published_parsed")
                if not published:
                    continue
                pub_date = datetime(*published[:3]).date()
                if pub_date < cutoff:
                    continue
                key = str(pub_date)
                daily_counts[key] = daily_counts.get(key, 0) + 1

            for date_str, count in daily_counts.items():
                all_rows.append({
                    "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                    "team": team,
                    "article_count": count,
                })
        except Exception as exc:
            log.warning("News %s failed: %s", team, exc)

        time.sleep(0.2)

    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame(columns=["date", "team", "article_count"])
