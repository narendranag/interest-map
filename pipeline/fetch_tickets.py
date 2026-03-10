"""
Fetch ticket demand data from the SeatGeek API (NBA only).

Requires ``SEATGEEK_CLIENT_ID`` and optionally ``SEATGEEK_CLIENT_SECRET``
environment variables.  SeatGeek's v2 API may require both credentials.
When the client_id is missing, the fetcher logs a warning and returns an
empty DataFrame, keeping the pipeline non-breaking.

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
    client_secret = os.environ.get("SEATGEEK_CLIENT_SECRET", "").strip()
    if not client_id:
        log.warning("SEATGEEK_CLIENT_ID not set — skipping ticket demand fetch")
        return _empty()

    session = create_session()
    today = datetime.utcnow().date()
    rows: List[Dict[str, Any]] = []

    # Build auth params — SeatGeek may require both id + secret
    auth_params = f"client_id={client_id}"
    if client_secret:
        auth_params += f"&client_secret={client_secret}"

    # Quick auth check with first team before iterating all 30
    first_slug = next(iter(SEATGEEK_SLUGS.values()))
    test_url = f"{_BASE_URL}?performers.slug={first_slug}&{auth_params}&per_page=1"
    try:
        test_resp = session.get(test_url, timeout=15)
        if test_resp.status_code == 403:
            if not client_secret:
                log.error(
                    "SeatGeek returned 403 — try setting SEATGEEK_CLIENT_SECRET "
                    "in addition to SEATGEEK_CLIENT_ID"
                )
            else:
                log.error("SeatGeek returned 403 — check that your API credentials are valid")
            return _empty()
        if test_resp.status_code == 401:
            log.error("SeatGeek returned 401 — invalid credentials")
            return _empty()
    except Exception as exc:
        log.error("SeatGeek auth check failed: %s", exc)
        return _empty()

    for team, slug in SEATGEEK_SLUGS.items():
        league = TEAM_TO_LEAGUE.get(team, "")
        url = (
            f"{_BASE_URL}?performers.slug={slug}"
            f"&{auth_params}"
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
    return _empty()


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "date", "team", "league",
        "avg_price", "lowest_price", "listing_count", "num_events",
    ])
