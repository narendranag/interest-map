"""
Fetch ticket demand data from the SeatGeek API (NBA only).

Requires a ``SEATGEEK_CLIENT_ID`` environment variable.  When the key
is missing the fetcher logs a warning and returns an empty DataFrame,
keeping the pipeline non-breaking.

Free tier: no hard rate limit; we stay conservative with 1-second delays.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from lib.teams import SEATGEEK_SLUGS, TEAM_TO_LEAGUE
from pipeline.utils import create_session

log = logging.getLogger(__name__)

_BASE_URL = "https://api.seatgeek.com/2/events"


def fetch() -> pd.DataFrame:
    """Return DataFrame[date, team, league, avg_price, lowest_price, listing_count, num_events]."""
    client_id = os.environ.get("SEATGEEK_CLIENT_ID", "").strip()
    if not client_id:
        log.warning("SEATGEEK_CLIENT_ID not set — skipping ticket demand fetch")
        return pd.DataFrame(columns=[
            "date", "team", "league",
            "avg_price", "lowest_price", "listing_count", "num_events",
        ])

    session = create_session()
    today = datetime.utcnow().date()
    rows: List[Dict[str, Any]] = []

    for team, slug in SEATGEEK_SLUGS.items():
        league = TEAM_TO_LEAGUE.get(team, "")
        url = (
            f"{_BASE_URL}?performers.slug={slug}"
            f"&client_id={client_id}"
            f"&per_page=10"
            f"&sort=datetime_utc.asc"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                log.warning("SeatGeek %s: HTTP %d", team, resp.status_code)
                time.sleep(1)
                continue

            events = resp.json().get("events", [])
            if not events:
                log.info("SeatGeek %s: no upcoming events", team)
                time.sleep(1)
                continue

            prices: List[float] = []
            lows: List[float] = []
            listings: List[int] = []

            for ev in events:
                stats = ev.get("stats", {})
                avg = stats.get("average_price")
                low = stats.get("lowest_price")
                count = stats.get("listing_count")
                if avg is not None:
                    prices.append(float(avg))
                if low is not None:
                    lows.append(float(low))
                if count is not None:
                    listings.append(int(count))

            rows.append({
                "date": today,
                "team": team,
                "league": league,
                "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
                "lowest_price": min(lows) if lows else None,
                "listing_count": sum(listings) if listings else 0,
                "num_events": len(events),
            })

            log.info(
                "SeatGeek %s: %d events, avg $%.0f, low $%.0f, %d listings",
                team,
                len(events),
                rows[-1]["avg_price"] or 0,
                rows[-1]["lowest_price"] or 0,
                rows[-1]["listing_count"],
            )

        except Exception as exc:
            log.warning("SeatGeek %s failed: %s", team, exc)

        time.sleep(1)

    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=[
        "date", "team", "league",
        "avg_price", "lowest_price", "listing_count", "num_events",
    ])
