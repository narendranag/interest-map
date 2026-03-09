"""
DuckDB in-memory database backed by parquet files in ``data/``.

The ``get_db()`` function is the single entry point used by all Streamlit
pages.  On first call it creates an in-memory DuckDB connection, discovers
every ``*.parquet`` file under ``data/``, and loads each one as a table
whose name matches the file stem (e.g. ``data/trends.parquet`` -> table
``trends``).  The connection is cached for the lifetime of the Streamlit
server process via ``@st.cache_resource``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import duckdb
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_resource
def get_db() -> duckdb.DuckDBPyConnection:
    """Return a cached in-memory DuckDB connection with all parquet tables."""
    conn = duckdb.connect(":memory:")
    if DATA_DIR.is_dir():
        for pq in sorted(DATA_DIR.glob("*.parquet")):
            table_name = pq.stem  # e.g. "trends"
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} "
                f"AS SELECT * FROM read_parquet('{pq}')"
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
    tables = conn.execute("SHOW TABLES").fetchdf()
    return name in tables["name"].values


@st.cache_data(ttl=120)
def get_pipeline_meta() -> Dict[str, Any]:
    """Read ``data/pipeline_meta.json`` for freshness info."""
    meta_path = DATA_DIR / "pipeline_meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return {}
