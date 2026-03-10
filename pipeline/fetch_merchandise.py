"""
Fetch NBA merchandise / jersey rankings from NBA.com (web scraping).

This is the most fragile data source by design.  NBA.com publishes
jersey and merchandise sales rankings periodically (often quarterly).
The scraper attempts to find ranking data from known URLs and regex
patterns.  On any failure it returns an empty DataFrame — the pipeline
will continue without merchandise data.

No API key required.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import requests

from lib.teams import NBA_TEAMS

log = logging.getLogger(__name__)

# Known NBA.com URLs that have published merchandise rankings.
# Updated manually each season — add new URLs as NBA publishes them.
_MERCH_URLS: List[str] = [
    "https://www.nba.com/news/top-selling-jerseys-2025-26-season",
    "https://www.nba.com/news/top-selling-jerseys-2024-25-season",
    "https://www.nba.com/news/most-popular-team-merchandise-2025-26",
    "https://www.nba.com/news/most-popular-team-merchandise-2024-25",
]

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _try_scrape_rankings(url: str, session: requests.Session) -> List[Dict[str, Any]]:
    """Attempt to extract team rankings from a single URL."""
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        text = resp.text

        # Pattern: look for numbered lists like "1. Team Name" or "1. City Team"
        # Also handles variations like "1) Team Name"
        pattern = re.compile(
            r"(?:^|\n)\s*(\d{1,2})[.)]\s+(.+?)(?:\n|<|$)",
            re.MULTILINE,
        )
        matches = pattern.findall(text)

        if len(matches) < 5:
            return []

        results: List[Dict[str, Any]] = []
        for rank_str, name_raw in matches:
            rank = int(rank_str)
            if rank < 1 or rank > 30:
                continue
            name = name_raw.strip().rstrip(".")
            # Try to match to a canonical team name
            matched_team = _match_team(name)
            if matched_team:
                results.append({"team": matched_team, "rank": rank})

        return results

    except Exception as exc:
        log.debug("Scrape %s failed: %s", url, exc)
        return []


def _match_team(text: str) -> str | None:
    """Best-effort match of scraped text to a canonical NBA team name."""
    text_lower = text.lower()
    for team in NBA_TEAMS:
        # Match full name or city + nickname fragments
        if team.lower() in text_lower:
            return team
        parts = team.split()
        # Match nickname (last word, e.g. "Lakers", "Celtics")
        if len(parts) >= 2 and parts[-1].lower() in text_lower:
            return team
    return None


def fetch() -> pd.DataFrame:
    """Return DataFrame[date, team, league, merch_rank] or empty on failure."""
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    today = datetime.utcnow().date()

    for url in _MERCH_URLS:
        log.info("Trying merchandise URL: %s", url)
        rankings = _try_scrape_rankings(url, session)
        if len(rankings) >= 5:
            log.info("Found %d team rankings from %s", len(rankings), url)
            rows: List[Dict[str, Any]] = []
            for item in rankings:
                rows.append({
                    "date": today,
                    "team": item["team"],
                    "league": "NBA",
                    "merch_rank": item["rank"],
                })
            return pd.DataFrame(rows)

    log.warning("Merchandise scraping: no valid data found from any URL")
    return pd.DataFrame(columns=["date", "team", "league", "merch_rank"])
