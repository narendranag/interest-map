"""
Fetch YouTube channel metrics for NBA teams via the YouTube Data API v3.

Requires a ``YOUTUBE_API_KEY`` environment variable.  When the key is
missing, the fetcher logs a warning and returns an empty DataFrame.

**Discovery flow**:  Rather than relying on hardcoded channel IDs (which
go stale), this fetcher first tries a batch lookup with stored IDs, then
uses the YouTube Search API to discover channels for any teams not found.
Discovered IDs are cached in ``data/youtube_channel_cache.json`` so that
subsequent runs cost only **1 quota unit** (batch ``channels.list``).

Quota cost:
  - Batch channels.list = 1 unit per call (handles 50 IDs)
  - search.list = 100 units per call (used only for discovery)
  - Daily quota = 10,000 units → 97 teams discoverable per day
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from lib.teams import NBA_TEAMS, TEAM_TO_LEAGUE
from pipeline.utils import create_session

log = logging.getLogger(__name__)

_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "youtube_channel_cache.json"


def _load_cache() -> Dict[str, str]:
    """Load team -> channel_id cache from disk."""
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict[str, str]) -> None:
    """Persist team -> channel_id cache to disk."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _discover_channel(
    team: str, api_key: str, session: Any,
) -> Optional[str]:
    """Use YouTube Search API to find the official channel for a team.

    Costs 100 quota units per call.  Returns channel_id or None.
    """
    query = f"{team} official NBA"
    url = (
        f"{_SEARCH_URL}?part=snippet&type=channel"
        f"&q={query}&maxResults=3&key={api_key}"
    )
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 403:
            log.warning("YouTube search quota exceeded — stopping discovery")
            return None
        if resp.status_code != 200:
            log.warning("YouTube search for %s: HTTP %d", team, resp.status_code)
            return None

        items = resp.json().get("items", [])
        if not items:
            log.warning("YouTube search for %s: no results", team)
            return None

        # Pick the first channel result
        channel_id = items[0].get("snippet", {}).get("channelId") or items[0].get("id", {}).get("channelId")
        if channel_id:
            log.info("Discovered YouTube channel for %s: %s", team, channel_id)
            return channel_id

    except Exception as exc:
        log.warning("YouTube search for %s failed: %s", team, exc)
    return None


def fetch() -> pd.DataFrame:
    """Return DataFrame[date, team, league, subscribers, total_views, video_count]."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        log.warning("YOUTUBE_API_KEY not set — skipping YouTube fetch")
        return _empty()

    session = create_session()
    today = datetime.utcnow().date()

    # Load cached channel IDs
    cache = _load_cache()

    # ------------------------------------------------------------------
    # Step 1: Batch-fetch stats for all cached channel IDs
    # ------------------------------------------------------------------
    id_to_team: Dict[str, str] = {}
    for team in NBA_TEAMS:
        cid = cache.get(team)
        if cid:
            id_to_team[cid] = team

    rows: List[Dict[str, Any]] = []
    found_teams: set = set()

    if id_to_team:
        channel_ids = ",".join(id_to_team.keys())
        url = f"{_CHANNELS_URL}?part=statistics&id={channel_ids}&key={api_key}"
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    cid = item.get("id", "")
                    team = id_to_team.get(cid)
                    if not team:
                        continue
                    found_teams.add(team)
                    stats = item.get("statistics", {})
                    rows.append(_make_row(today, team, stats))
            elif resp.status_code == 403:
                log.error("YouTube API quota exceeded on batch lookup")
                return _empty()
            else:
                log.error("YouTube batch lookup: HTTP %d", resp.status_code)
        except Exception as exc:
            log.error("YouTube batch fetch failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 2: Discover missing teams via Search API
    # ------------------------------------------------------------------
    missing = [t for t in NBA_TEAMS if t not in found_teams]
    if missing:
        log.info("YouTube: %d/%d teams missing — discovering via search", len(missing), len(NBA_TEAMS))

    discovered = 0
    for team in missing:
        cid = _discover_channel(team, api_key, session)
        if not cid:
            continue

        # Fetch stats for the discovered channel
        url = f"{_CHANNELS_URL}?part=statistics&id={cid}&key={api_key}"
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    stats = items[0].get("statistics", {})
                    rows.append(_make_row(today, team, stats))
                    cache[team] = cid
                    discovered += 1
                    found_teams.add(team)
        except Exception as exc:
            log.warning("YouTube stats for %s failed: %s", team, exc)

    if discovered > 0:
        log.info("YouTube: discovered %d new channels, saving cache", discovered)
        _save_cache(cache)

    log.info("YouTube: %d/%d teams fetched", len(found_teams), len(NBA_TEAMS))

    # Log results
    for r in rows:
        log.info(
            "YouTube %s: %s subs, %s views",
            r["team"],
            f"{r['subscribers']:,}",
            f"{r['total_views']:,}",
        )

    if rows:
        return pd.DataFrame(rows)
    return _empty()


def _make_row(today, team: str, stats: Dict) -> Dict[str, Any]:
    return {
        "date": today,
        "team": team,
        "league": TEAM_TO_LEAGUE.get(team, ""),
        "subscribers": int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
    }


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "date", "team", "league",
        "subscribers", "total_views", "video_count",
    ])
