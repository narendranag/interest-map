"""
Scoring, normalisation, and anomaly detection utilities.
"""

from __future__ import annotations

import datetime
from typing import Dict

import numpy as np
import pandas as pd

from lib.teams import SEASON_RANGES, TEAM_TO_LEAGUE


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalize_min_max(series: pd.Series) -> pd.Series:
    """Min-max normalise a numeric series to 0--100."""
    if series.empty or series.max() == series.min():
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.min()) / (series.max() - series.min()) * 100.0


def compute_weighted_score(
    df: pd.DataFrame,
    weights: Dict[str, float],
) -> pd.Series:
    """Return weighted sum of *columns* listed in *weights*.

    Weights are auto-normalised to sum to 1.  Missing columns are ignored.
    """
    total = sum(weights.values())
    if total == 0:
        return pd.Series(np.zeros(len(df)), index=df.index)
    result = pd.Series(np.zeros(len(df)), index=df.index)
    for col, w in weights.items():
        if col in df.columns:
            result += (w / total) * df[col].fillna(0)
    return result


# ---------------------------------------------------------------------------
# Momentum weighting
# ---------------------------------------------------------------------------

def apply_momentum_weighting(
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "score",
    recent_days: int = 7,
    recent_weight: float = 2.0,
) -> pd.Series:
    """Weight recent rows more heavily than older ones.

    Rows within the most recent *recent_days* get *recent_weight* multiplied;
    older rows get weight 1.0.  Returns the weighted value series.
    """
    if df.empty:
        return pd.Series(dtype=float)
    max_date = pd.to_datetime(df[date_col]).max()
    cutoff = max_date - pd.Timedelta(days=recent_days)
    is_recent = pd.to_datetime(df[date_col]) > cutoff
    weights = is_recent.map({True: recent_weight, False: 1.0})
    return df[value_col] * weights


# ---------------------------------------------------------------------------
# Seasonal adjustment
# ---------------------------------------------------------------------------

def is_in_season(league: str, date: datetime.date) -> bool:
    """Return True when *league* is in-season on *date*."""
    rng = SEASON_RANGES.get(league)
    if rng is None:
        return True
    start_month, end_month = rng
    m = date.month
    if start_month <= end_month:
        return start_month <= m <= end_month
    # Wraps around year-end (e.g. Oct-Apr)
    return m >= start_month or m <= end_month


def apply_seasonal_adjustment(
    df: pd.DataFrame,
    date_col: str = "date",
    team_col: str = "team",
    score_col: str = "interest_score",
    floor_score: float = 10.0,
) -> pd.DataFrame:
    """Set a floor for off-season teams so they do not collapse to zero."""
    out = df.copy()
    for idx, row in out.iterrows():
        league = TEAM_TO_LEAGUE.get(row[team_col])
        if league and not is_in_season(league, row[date_col]):
            out.at[idx, score_col] = max(row[score_col], floor_score)
    return out


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    df: pd.DataFrame,
    team_col: str = "team",
    value_col: str = "interest_score",
    window: int = 30,
    threshold: float = 2.0,
) -> pd.DataFrame:
    """Flag rows where the value exceeds mean + threshold * std.

    Adds ``is_anomaly`` (bool) and ``z_score`` (float) columns.
    """
    out = df.copy()
    out["z_score"] = 0.0
    out["is_anomaly"] = False

    for team, grp in out.groupby(team_col):
        idx = grp.index
        rolling_mean = grp[value_col].rolling(window, min_periods=3).mean()
        rolling_std = grp[value_col].rolling(window, min_periods=3).std()
        z = (grp[value_col] - rolling_mean) / rolling_std.replace(0, np.nan)
        out.loc[idx, "z_score"] = z.fillna(0)
        out.loc[idx, "is_anomaly"] = z.abs() > threshold

    return out
