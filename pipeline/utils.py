"""
Shared HTTP session factory with retry logic for all pipeline fetchers.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter, Retry


def create_session(
    user_agent: str = "InterestMap/2.0",
    retries: int = 5,
    backoff: float = 0.5,
) -> requests.Session:
    """Return a ``requests.Session`` configured with retries."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": user_agent})
    return session
