"""Provider interface shared by the live and fake data sources."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..types import CompanyData


class ProviderError(Exception):
    """Transient failure (network, rate limit) with no usable cache."""


@dataclass(frozen=True)
class RateResult:
    rate_pct: float
    source: str  # "fred" | "default"
    as_of: str | None = None


class DataProvider(Protocol):
    def fetch_company(self, ticker: str) -> CompanyData | None: ...
    def fx_rate(self, from_ccy: str, to_ccy: str) -> float | None: ...
    def risk_free_rate(self, currency: str) -> RateResult: ...
    def peer_tickers(self, ticker: str) -> list[str]: ...
    def suggest(self, query: str) -> list[str]: ...
