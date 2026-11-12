"""The production provider: Yahoo for company data, FRED/defaults for rates, Finnhub for peers."""
from __future__ import annotations

from ..types import CompanyData
from .finnhub import fetch_peers
from .provider import RateResult
from .rates import risk_free_rate


class LiveProvider:
    def __init__(self, yahoo, fred_key: str | None, finnhub_key: str | None):
        self._yahoo, self._fred_key, self._finnhub_key = yahoo, fred_key, finnhub_key

    def fetch_company(self, ticker: str) -> CompanyData | None:
        return self._yahoo.fetch_company(ticker)

    def fx_rate(self, from_ccy: str, to_ccy: str) -> float | None:
        return self._yahoo.fx_rate(from_ccy, to_ccy)

    def risk_free_rate(self, currency: str) -> RateResult:
        return risk_free_rate(currency, self._fred_key)

    def peer_tickers(self, ticker: str) -> list[str]:
        return fetch_peers(ticker, self._finnhub_key)

    def suggest(self, query: str) -> list[str]:
        return self._yahoo.suggest(query)
