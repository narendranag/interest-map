"""
Fetch daily Google Trends scores for a list of team names.

Uses *pytrends* (unofficial Google Trends client) in batches of five with a
1.2-second delay between requests to avoid rate limiting.
"""

from __future__ import annotations

import logging
import time
from typing import List

import pandas as pd

log = logging.getLogger(__name__)


def _select_timeframe(days: int) -> str:
    """Map *days* to a valid pytrends timeframe string."""
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


def fetch(teams: List[str], days: int = 90) -> pd.DataFrame:
    """Return DataFrame[date, team, trends_score]."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.warning("pytrends not installed — skipping Google Trends")
        return pd.DataFrame(columns=["date", "team", "trends_score"])

    pytrends = TrendReq(hl="en-US", tz=0)
    batch_size = 5
    timeframe = _select_timeframe(days)
    frames: List[pd.DataFrame] = []

    for i in range(0, len(teams), batch_size):
        batch = teams[i : i + batch_size]
        log.info("Trends batch %d/%d: %s", i // batch_size + 1,
                 -(-len(teams) // batch_size), batch)
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo="")
            data = pytrends.interest_over_time().reset_index()
        except Exception as exc:
            log.warning("Trends batch failed: %s", exc)
            continue
        if data.empty:
            continue
        melted = data.melt(
            id_vars=["date"],
            value_vars=batch,
            var_name="team",
            value_name="trends_score",
        )
        melted["date"] = pd.to_datetime(melted["date"]).dt.date
        frames.append(melted[["date", "team", "trends_score"]])
        time.sleep(1.2)

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame(columns=["date", "team", "trends_score"])
