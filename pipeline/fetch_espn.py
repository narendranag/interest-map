"""
Fetch game schedules, scores, and broadcast information from the free ESPN API.

Includes Victory+ streaming detection: a game is flagged ``victory_plus=True``
when any broadcast channel name matches known Victory+ patterns, or when the
team is a known Victory+ partner playing at home.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd

from lib.teams import (
    ESPN_NAME_TO_CANONICAL,
    ESPN_SPORT_PATHS,
    VICTORY_PLUS_BROADCAST_PATTERNS,
    VICTORY_PLUS_TEAMS,
)
from pipeline.utils import create_session

log = logging.getLogger(__name__)


def _parse_game(event: Dict[str, Any], league: str) -> List[Dict[str, Any]]:
    """Parse a single ESPN event into two rows (one per competitor)."""
    rows: List[Dict[str, Any]] = []
    for comp in event.get("competitions", []):
        status_obj = comp.get("status", {}).get("type", {})
        status_name = status_obj.get("name", "")
        if "FINAL" in status_name.upper():
            status = "final"
        elif "PROGRESS" in status_name.upper():
            status = "in_progress"
        else:
            status = "scheduled"

        # Collect broadcast channel names
        channels: List[str] = []
        for gb in comp.get("geoBroadcasts", []):
            media = gb.get("media", {})
            name = media.get("shortName", "")
            if name:
                channels.append(name)
        # Fallback to top-level broadcasts
        if not channels:
            for b in comp.get("broadcasts", []):
                channels.extend(b.get("names", []))

        broadcasts_str = ", ".join(channels)

        # Check Victory+ in broadcast list
        vplus_broadcast = any(
            pat.lower() in broadcasts_str.lower()
            for pat in VICTORY_PLUS_BROADCAST_PATTERNS
        )

        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        # Build lookup by homeAway
        by_side: Dict[str, Dict[str, Any]] = {}
        for c in competitors:
            by_side[c.get("homeAway", "")] = c

        game_date_str = event.get("date", "")[:10]
        try:
            game_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        for side in ("home", "away"):
            me = by_side.get(side, {})
            opp_side = "away" if side == "home" else "home"
            opp = by_side.get(opp_side, {})

            espn_name = me.get("team", {}).get("displayName", "")
            opp_name = opp.get("team", {}).get("displayName", "")
            team = ESPN_NAME_TO_CANONICAL.get(espn_name, espn_name)
            opponent = ESPN_NAME_TO_CANONICAL.get(opp_name, opp_name)

            my_score = me.get("score", "")
            opp_score = opp.get("score", "")

            if status == "final" and my_score and opp_score:
                try:
                    result = "W" if int(my_score) > int(opp_score) else "L"
                except ValueError:
                    result = None
            else:
                result = None

            is_vplus = vplus_broadcast or (
                team in VICTORY_PLUS_TEAMS and side == "home"
            )

            rows.append({
                "date": game_date,
                "league": league,
                "team": team,
                "opponent": opponent,
                "home_away": side,
                "score_team": my_score,
                "score_opponent": opp_score,
                "result": result,
                "status": status,
                "broadcasts": broadcasts_str,
                "victory_plus": is_vplus,
            })
    return rows


def fetch(days: int = 30) -> pd.DataFrame:
    """Return DataFrame of games for all leagues over [today-days, today+7]."""
    session = create_session()
    end_date = datetime.utcnow().date() + timedelta(days=7)
    start_date = datetime.utcnow().date() - timedelta(days=days)

    all_rows: List[Dict[str, Any]] = []

    for league, sport_path in ESPN_SPORT_PATHS.items():
        current = start_date
        while current <= end_date:
            date_str = current.strftime("%Y%m%d")
            url = (
                f"https://site.api.espn.com/apis/site/v2/sports/"
                f"{sport_path}/scoreboard?dates={date_str}"
            )
            try:
                resp = session.get(url, timeout=20)
                if resp.status_code != 200:
                    log.warning("ESPN %s %s: HTTP %d", league, date_str, resp.status_code)
                    current += timedelta(days=1)
                    continue
                data = resp.json()
                for event in data.get("events", []):
                    all_rows.extend(_parse_game(event, league))
            except Exception as exc:
                log.warning("ESPN %s %s failed: %s", league, date_str, exc)
            current += timedelta(days=1)
            time.sleep(0.5)

    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame(columns=[
        "date", "league", "team", "opponent", "home_away",
        "score_team", "score_opponent", "result", "status",
        "broadcasts", "victory_plus",
    ])
