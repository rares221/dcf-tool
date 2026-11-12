"""Peer ticker suggestions from Finnhub's free "peers" endpoint. Never raises."""
from __future__ import annotations

from typing import Callable

import requests

PEERS_URL = "https://finnhub.io/api/v1/stock/peers"
MAX_PEERS = 5


def fetch_peers(ticker: str, api_key: str | None, get: Callable = requests.get) -> list[str]:
    if not api_key:
        return []
    try:
        resp = get(PEERS_URL, params={"symbol": ticker, "token": api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return [t for t in data if isinstance(t, str) and t.upper() != ticker.upper()][:MAX_PEERS]
    except Exception:
        return []
