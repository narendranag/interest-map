"""
Fetch NBA betting odds from The Odds API and compute implied win probabilities.

Requires an ``ODDS_API_KEY`` environment variable (free tier: 500 req/month).
When missing, the fetcher logs a warning and returns an empty DataFrame.

NBA only to conserve the free-tier budget (~4 runs/day * 30 days = 120 req/month,
well within the 500 limit).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from lib.teams import NBA_TEAMS, ODDS_API_TO_CANONICAL
from pipeline.utils import create_session

log = logging.getLogger(__name__)

_BASE_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"


def _implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied win probability (0-1)."""
    if decimal_odds <= 1.0:
        return 0.0
    return 1.0 / decimal_odds


def fetch() -> pd.DataFrame:
    """Return DataFrame[date, team, league, implied_win_prob, num_bookmakers]."""
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        log.warning("ODDS_API_KEY not set — skipping betting odds fetch")
        return pd.DataFrame(columns=[
            "date", "team", "league", "implied_win_prob", "num_bookmakers",
        ])

    session = create_session()
    today = datetime.utcnow().date()

    url = (
        f"{_BASE_URL}?apiKey={api_key}"
        f"&regions=us"
        f"&markets=h2h"
        f"&oddsFormat=decimal"
    )

    try:
        resp = session.get(url, timeout=30)

        # Log remaining quota
        remaining = resp.headers.get("x-requests-remaining")
        used = resp.headers.get("x-requests-used")
        if remaining:
            log.info("Odds API quota: %s remaining, %s used", remaining, used)

        if resp.status_code == 401:
            log.error("Odds API: invalid API key")
            return _empty()
        if resp.status_code == 429:
            log.error("Odds API: quota exceeded")
            return _empty()
        if resp.status_code != 200:
            log.error("Odds API: HTTP %d — %s", resp.status_code, resp.text[:200])
            return _empty()

        events = resp.json()

    except Exception as exc:
        log.error("Odds API fetch failed: %s", exc)
        return _empty()

    # Aggregate implied probabilities per team across all games & bookmakers
    team_probs: Dict[str, List[float]] = {t: [] for t in NBA_TEAMS}
    team_bookmakers: Dict[str, int] = {t: 0 for t in NBA_TEAMS}

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    canonical = ODDS_API_TO_CANONICAL.get(name)
                    if not canonical:
                        continue
                    price = outcome.get("price", 0)
                    if price > 1.0:
                        team_probs[canonical].append(_implied_probability(price))
                        team_bookmakers[canonical] += 1

    rows: List[Dict[str, Any]] = []
    for team in NBA_TEAMS:
        probs = team_probs[team]
        if probs:
            avg_prob = sum(probs) / len(probs)
            rows.append({
                "date": today,
                "team": team,
                "league": "NBA",
                "implied_win_prob": round(avg_prob, 4),
                "num_bookmakers": team_bookmakers[team],
            })
            log.info("Odds %s: %.1f%% implied win prob (%d bookmaker entries)",
                     team, avg_prob * 100, team_bookmakers[team])
        else:
            rows.append({
                "date": today,
                "team": team,
                "league": "NBA",
                "implied_win_prob": None,
                "num_bookmakers": 0,
            })

    return pd.DataFrame(rows)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "date", "team", "league", "implied_win_prob", "num_bookmakers",
    ])
