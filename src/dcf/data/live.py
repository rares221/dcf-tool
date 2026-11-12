"""The production provider: Yahoo for company data, FRED/defaults for rates, Finnhub for peers."""
from __future__ import annotations

from dataclasses import asdict

from ..types import CompanyData
from .cache import SqliteCache
from .finnhub import fetch_peers
from .provider import RateResult
from .rates import risk_free_rate


class LiveProvider:
    def __init__(self, yahoo, fred_key: str | None, finnhub_key: str | None, cache: SqliteCache | None = None):
        self._yahoo, self._fred_key, self._finnhub_key, self._cache = yahoo, fred_key, finnhub_key, cache

    def fetch_company(self, ticker: str) -> CompanyData | None:
        return self._yahoo.fetch_company(ticker)

    def fx_rate(self, from_ccy: str, to_ccy: str) -> float | None:
        return self._yahoo.fx_rate(from_ccy, to_ccy)

    def risk_free_rate(self, currency: str) -> RateResult:
        key = f"rf:{currency.upper()}"
        if self._cache is not None:
            fresh = self._cache.get(key)
            if fresh is not None:
                return RateResult(**fresh.value)
        rate = risk_free_rate(currency, self._fred_key)
        if self._cache is None:
            return rate
        if rate.source == "fred":  # only live rates are worth remembering; labelled defaults are cheap to recompute
            self._cache.put(key, asdict(rate))
            return rate
        stale = self._cache.get(key, allow_stale=True)
        return RateResult(**stale.value) if stale else rate  # an older live rate beats a placeholder default

    def peer_tickers(self, ticker: str) -> list[str]:
        key = f"peers:{ticker.upper()}"
        if self._cache is not None:
            fresh = self._cache.get(key)
            if fresh is not None:
                return list(fresh.value["tickers"])
        peers = fetch_peers(ticker, self._finnhub_key)
        if self._cache is None:
            return peers
        if peers:
            self._cache.put(key, {"tickers": peers})
            return peers
        stale = self._cache.get(key, allow_stale=True)
        return list(stale.value["tickers"]) if stale else peers

    def suggest(self, query: str) -> list[str]:
        return self._yahoo.suggest(query)
