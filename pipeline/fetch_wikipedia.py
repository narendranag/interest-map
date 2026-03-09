"""
Fetch daily Wikipedia pageviews for each team from the Wikimedia REST API.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import List

import pandas as pd

from pipeline.utils import create_session

log = logging.getLogger(__name__)


def fetch(teams: List[str], days: int = 90) -> pd.DataFrame:
    """Return DataFrame[date, team, wiki_views]."""
    session = create_session()
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    frames: List[pd.DataFrame] = []

    for team in teams:
        page = team.replace(" ", "_")
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia.org/all-access/all-agents/{page}/daily/"
            f"{start_date.strftime('%Y%m%d')}/{end_date.strftime('%Y%m%d')}"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                log.warning("Wiki %s: HTTP %d", team, resp.status_code)
                continue
            items = resp.json().get("items", [])
            rows = []
            for it in items:
                ts = it.get("timestamp")
                dt = datetime.strptime(str(ts), "%Y%m%d%H").date()
                rows.append({"date": dt, "team": team, "wiki_views": it.get("views", 0)})
            if rows:
                frames.append(pd.DataFrame(rows))
        except Exception as exc:
            log.warning("Wiki %s failed: %s", team, exc)
        time.sleep(0.1)

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame(columns=["date", "team", "wiki_views"])
