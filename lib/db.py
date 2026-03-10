"""
DuckDB in-memory database backed by parquet files in ``data/``.

The ``get_db()`` function is the single entry point used by all Streamlit
pages.  On first call it creates an in-memory DuckDB connection, discovers
every ``*.parquet`` file under ``data/``, and loads each one as a table
whose name matches the file stem (e.g. ``data/wikipedia.parquet`` -> table
``wikipedia``).  The connection is refreshed hourly via ``@st.cache_resource``
with a TTL, so new pipeline data is picked up automatically.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import duckdb
import pandas as pd
import streamlit as st

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_resource(ttl=3600)
def get_db() -> duckdb.DuckDBPyConnection:
    """Return a cached in-memory DuckDB connection with all parquet tables."""
    conn = duckdb.connect(":memory:")
    loaded = []
    failed = []

    if not DATA_DIR.is_dir():
        log.warning("Data directory not found: %s", DATA_DIR)
        return conn

    for pq in sorted(DATA_DIR.glob("*.parquet")):
        table_name = pq.stem
        try:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS \"{table_name}\" "
                f"AS SELECT * FROM read_parquet('{pq}')"
            )
            loaded.append(table_name)
        except Exception as exc:
            log.warning("Failed to load %s: %s", table_name, exc)
            failed.append(table_name)

    log.info(
        "DuckDB loaded %d tables: %s%s",
        len(loaded),
        ", ".join(loaded),
        f" (failed: {', '.join(failed)})" if failed else "",
    )
    return conn


def query(sql: str) -> pd.DataFrame:
    """Run *sql* against the cached DB and return a DataFrame."""
    conn = get_db()
    try:
        return conn.execute(sql).fetchdf()
    except Exception:
        return pd.DataFrame()


def table_exists(name: str) -> bool:
    """Return True when table *name* has been loaded."""
    conn = get_db()
    try:
        tables = conn.execute("SHOW TABLES").fetchdf()
        return name in tables["name"].values
    except Exception:
        return False


@st.cache_data(ttl=120)
def get_pipeline_meta() -> Dict[str, Any]:
    """Read ``data/pipeline_meta.json`` for freshness info."""
    meta_path = DATA_DIR / "pipeline_meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return {}
