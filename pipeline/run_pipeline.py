"""
Pipeline orchestrator.

Runs all data fetchers, writes parquet files to ``data/``, and records
metadata in ``data/pipeline_meta.json``.

Usage::

    python -m pipeline.run_pipeline
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _save(df: pd.DataFrame, name: str) -> int:
    """Write *df* to parquet and return the row count."""
    path = DATA_DIR / f"{name}.parquet"

    # Merge with existing data if present (keeps historical rows)
    if path.exists():
        try:
            existing = pd.read_parquet(path)
            df = pd.concat([existing, df], ignore_index=True)
            # De-duplicate: keep most recent row per natural key
            if "team" in df.columns and "date" in df.columns:
                extra_keys = []
                if "opponent" in df.columns:
                    extra_keys.append("opponent")
                dedup_cols = ["date", "team"] + extra_keys
                df = df.drop_duplicates(subset=dedup_cols, keep="last")
        except Exception:
            pass  # if existing file is corrupt, overwrite

    # Keep only last 90 days
    if "date" in df.columns and not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        cutoff = (datetime.utcnow() - pd.Timedelta(days=90)).date()
        df = df[df["date"] >= cutoff]

    df.to_parquet(path, index=False)
    return len(df)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    from lib.teams import ALL_TEAMS
    from pipeline import (
        fetch_espn, fetch_news, fetch_wikipedia,
        fetch_attendance, fetch_tickets,
        fetch_youtube, fetch_betting,
    )

    sources: Dict[str, Dict[str, Any]] = {}

    # ---------------------------------------------------------------
    # Removed sources (kept as files for local use):
    #   - Google Trends: 100% 429s from GitHub Actions (IP blocked)
    #   - Reddit (league): 100% 403s from CI (IP blocked)
    #   - Team Subreddits: 100% 403s from CI (same Reddit block)
    #   - Merchandise: no reliable public scraping source
    # ---------------------------------------------------------------

    # --- Wikipedia ---
    log.info("=== Wikipedia ===")
    try:
        df = fetch_wikipedia.fetch(ALL_TEAMS, days=90)
        rows = _save(df, "wikipedia")
        sources["wikipedia"] = {"rows": rows, "status": "ok"}
        log.info("Wikipedia: %d rows", rows)
    except Exception as exc:
        log.error("Wikipedia failed: %s", exc)
        sources["wikipedia"] = {"rows": 0, "status": str(exc)}

    # --- ESPN ---
    log.info("=== ESPN ===")
    try:
        df = fetch_espn.fetch(days=30)
        rows = _save(df, "espn_games")
        sources["espn_games"] = {"rows": rows, "status": "ok"}
        log.info("ESPN: %d rows", rows)
    except Exception as exc:
        log.error("ESPN failed: %s", exc)
        sources["espn_games"] = {"rows": 0, "status": str(exc)}

    # --- News ---
    log.info("=== News ===")
    try:
        df = fetch_news.fetch(ALL_TEAMS, days=7)
        rows = _save(df, "news")
        sources["news"] = {"rows": rows, "status": "ok"}
        log.info("News: %d rows", rows)
    except Exception as exc:
        log.error("News failed: %s", exc)
        sources["news"] = {"rows": 0, "status": str(exc)}

    # --- Attendance ---
    log.info("=== Attendance ===")
    try:
        df = fetch_attendance.fetch(days=30)
        rows = _save(df, "attendance")
        sources["attendance"] = {"rows": rows, "status": "ok"}
        log.info("Attendance: %d rows", rows)
    except Exception as exc:
        log.error("Attendance failed: %s", exc)
        sources["attendance"] = {"rows": 0, "status": str(exc)}

    # --- Tickets (SeatGeek) ---
    log.info("=== Tickets (SeatGeek) ===")
    try:
        df = fetch_tickets.fetch()
        rows = _save(df, "tickets")
        sources["tickets"] = {"rows": rows, "status": "ok"}
        log.info("Tickets: %d rows", rows)
    except Exception as exc:
        log.error("Tickets failed: %s", exc)
        sources["tickets"] = {"rows": 0, "status": str(exc)}

    # --- YouTube ---
    log.info("=== YouTube ===")
    try:
        df = fetch_youtube.fetch()
        rows = _save(df, "youtube")
        sources["youtube"] = {"rows": rows, "status": "ok"}
        log.info("YouTube: %d rows", rows)
    except Exception as exc:
        log.error("YouTube failed: %s", exc)
        sources["youtube"] = {"rows": 0, "status": str(exc)}

    # --- Betting (Odds API) ---
    log.info("=== Betting Odds ===")
    try:
        df = fetch_betting.fetch()
        rows = _save(df, "betting")
        sources["betting"] = {"rows": rows, "status": "ok"}
        log.info("Betting: %d rows", rows)
    except Exception as exc:
        log.error("Betting failed: %s", exc)
        sources["betting"] = {"rows": 0, "status": str(exc)}

    # --- Meta ---
    meta = {
        "last_run": datetime.utcnow().isoformat() + "Z",
        "status": "success" if all(s["status"] == "ok" for s in sources.values()) else "partial",
        "sources": sources,
    }
    (DATA_DIR / "pipeline_meta.json").write_text(json.dumps(meta, indent=2))
    log.info("Pipeline complete: %s", meta["status"])


if __name__ == "__main__":
    main()
