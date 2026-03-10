"""
Fetch YouTube channel metrics for NBA teams via the YouTube Data API v3.

Requires a ``YOUTUBE_API_KEY`` environment variable.  When the key is
missing, the fetcher logs a warning and returns an empty DataFrame.

All 30 NBA channels are batched into a single API call (the ``channels``
endpoint allows up to 50 IDs), costing just **1 quota unit** per run.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from lib.teams import TEAM_TO_LEAGUE, YOUTUBE_CHANNEL_IDS
from pipeline.utils import create_session

log = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/youtube/v3/channels"


def fetch() -> pd.DataFrame:
    """Return DataFrame[date, team, league, subscribers, total_views, video_count]."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        log.warning("YOUTUBE_API_KEY not set — skipping YouTube fetch")
        return pd.DataFrame(columns=[
            "date", "team", "league",
            "subscribers", "total_views", "video_count",
        ])

    session = create_session()
    today = datetime.utcnow().date()

    # Build reverse map: channel_id -> team name
    id_to_team: Dict[str, str] = {cid: team for team, cid in YOUTUBE_CHANNEL_IDS.items()}

    # Batch all channel IDs in one call (max 50 per request, we have 30)
    channel_ids = ",".join(YOUTUBE_CHANNEL_IDS.values())
    url = (
        f"{_BASE_URL}?part=statistics&id={channel_ids}&key={api_key}"
    )

    rows: List[Dict[str, Any]] = []

    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 403:
            log.error("YouTube API returned 403 — quota exceeded or key invalid")
            return pd.DataFrame(columns=[
                "date", "team", "league",
                "subscribers", "total_views", "video_count",
            ])
        if resp.status_code != 200:
            log.error("YouTube API: HTTP %d — %s", resp.status_code, resp.text[:200])
            return pd.DataFrame(columns=[
                "date", "team", "league",
                "subscribers", "total_views", "video_count",
            ])

        items = resp.json().get("items", [])
        for item in items:
            channel_id = item.get("id", "")
            team = id_to_team.get(channel_id)
            if not team:
                continue

            stats = item.get("statistics", {})
            rows.append({
                "date": today,
                "team": team,
                "league": TEAM_TO_LEAGUE.get(team, ""),
                "subscribers": int(stats.get("subscriberCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "video_count": int(stats.get("videoCount", 0)),
            })

            log.info(
                "YouTube %s: %s subs, %s views",
                team,
                f"{rows[-1]['subscribers']:,}",
                f"{rows[-1]['total_views']:,}",
            )

    except Exception as exc:
        log.error("YouTube fetch failed: %s", exc)

    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=[
        "date", "team", "league",
        "subscribers", "total_views", "video_count",
    ])
