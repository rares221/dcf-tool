"""Risk-free rates: FRED for USD when a key is set, labelled defaults otherwise."""
from __future__ import annotations

from typing import Callable

import requests

from .provider import RateResult

# PLACEHOLDER 10-year government yields (percent), approximate and NOT verified against live data.
# They are shown in the UI as editable assumptions (source="default"); refresh them periodically.
DEFAULT_RISK_FREE: dict[str, float] = {
    "USD": 4.3, "EUR": 2.6, "GBP": 4.5, "JPY": 1.5, "CHF": 0.5, "CAD": 3.3, "AUD": 4.3, "OTHER": 5.0,
}

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_10y(api_key: str, get: Callable = requests.get) -> RateResult:
    resp = get(FRED_URL, params={"series_id": "DGS10", "api_key": api_key, "file_type": "json",
                                 "sort_order": "desc", "limit": 10}, timeout=10)
    resp.raise_for_status()
    for obs in resp.json().get("observations", []):
        if obs.get("value") not in (None, "", "."):
            return RateResult(float(obs["value"]), "fred", obs.get("date"))
    raise ValueError("FRED returned no usable observation")


def risk_free_rate(currency: str, fred_key: str | None,
                   fetch: Callable[[str], RateResult] = fetch_fred_10y) -> RateResult:
    cur = currency.upper()
    if cur == "USD" and fred_key:
        try:
            return fetch(fred_key)
        except Exception:
            pass
    return RateResult(DEFAULT_RISK_FREE.get(cur, DEFAULT_RISK_FREE["OTHER"]), "default", None)
