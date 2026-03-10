"""
Fetch game attendance data from the ESPN scoreboard API.

Extends the existing ESPN integration to capture attendance and venue
capacity from completed games.  Records home-team rows only (attendance
is a venue property).  No API key required.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd

from lib.teams import ESPN_NAME_TO_CANONICAL, ESPN_SPORT_PATHS
from pipeline.utils import create_session

log = logging.getLogger(__name__)


def fetch(days: int = 30) -> pd.DataFrame:
    """Return DataFrame[date, team, league, opponent, attendance, capacity, attendance_pct]."""
    session = create_session()
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

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
                    current += timedelta(days=1)
                    continue
                data = resp.json()
                for event in data.get("events", []):
                    rows = _parse_attendance(event, league)
                    all_rows.extend(rows)
            except Exception as exc:
                log.warning("Attendance %s %s failed: %s", league, date_str, exc)
            current += timedelta(days=1)
            time.sleep(0.5)

    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame(columns=[
        "date", "team", "league", "opponent",
        "attendance", "capacity", "attendance_pct",
    ])


def _parse_attendance(event: Dict[str, Any], league: str) -> List[Dict[str, Any]]:
    """Extract attendance data from a single ESPN event."""
    rows: List[Dict[str, Any]] = []

    for comp in event.get("competitions", []):
        # Only completed games have attendance data
        status_name = comp.get("status", {}).get("type", {}).get("name", "")
        if "FINAL" not in status_name.upper():
            continue

        attendance = comp.get("attendance")
        if not attendance:
            continue
        try:
            attendance = int(attendance)
        except (ValueError, TypeError):
            continue

        # Venue capacity
        venue = comp.get("venue", {})
        capacity = venue.get("capacity")
        if capacity:
            try:
                capacity = int(capacity)
            except (ValueError, TypeError):
                capacity = None

        attendance_pct = (
            round(attendance / capacity * 100, 1) if capacity else None
        )

        game_date_str = event.get("date", "")[:10]
        try:
            game_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Find home team and away team
        competitors = comp.get("competitors", [])
        home_team = None
        away_team = None
        for c in competitors:
            espn_name = c.get("team", {}).get("displayName", "")
            canonical = ESPN_NAME_TO_CANONICAL.get(espn_name, espn_name)
            if c.get("homeAway") == "home":
                home_team = canonical
            else:
                away_team = canonical

        if home_team:
            rows.append({
                "date": game_date,
                "team": home_team,
                "league": league,
                "opponent": away_team or "",
                "attendance": attendance,
                "capacity": capacity,
                "attendance_pct": attendance_pct,
            })

    return rows
