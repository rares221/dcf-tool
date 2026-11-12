"""In-memory provider for tests and the browser tests (DCF_PROVIDER=fake)."""
from __future__ import annotations

import json

from ..types import CompanyData, YearFigures
from .provider import ProviderError, RateResult


class FakeProvider:
    def __init__(self, companies: dict[str, CompanyData], fx: dict[str, float] | None = None,
                 peers: dict[str, list[str]] | None = None, errors: set[str] | None = None,
                 risk_free: dict[str, float] | None = None):
        self.companies = companies
        self.fx = fx or {}
        self.peers = peers or {}
        self.errors = errors or set()
        self.risk_free = risk_free or {}
        self.fetch_log: list[str] = []

    def fetch_company(self, ticker: str) -> CompanyData | None:
        self.fetch_log.append(ticker)
        if ticker in self.errors:
            raise ProviderError(f"{ticker}: simulated outage")
        return self.companies.get(ticker)

    def fx_rate(self, from_ccy: str, to_ccy: str) -> float | None:
        if from_ccy.upper() == to_ccy.upper():
            return 1.0
        return self.fx.get(f"{from_ccy.upper()}{to_ccy.upper()}")

    def risk_free_rate(self, currency: str) -> RateResult:
        return RateResult(self.risk_free.get(currency.upper(), 4.3), "default", None)

    def peer_tickers(self, ticker: str) -> list[str]:
        return list(self.peers.get(ticker, []))

    def suggest(self, query: str) -> list[str]:
        q = query.upper()[:3]
        return [t for t in self.companies if q and t.startswith(q)][:5]


def company_from_dict(d: dict) -> CompanyData:
    years = tuple(YearFigures(**y) for y in d["years"])
    return CompanyData(**{**d, "years": years})


def load_fake_world(path: str) -> FakeProvider:
    with open(path, encoding="utf-8") as f:
        world = json.load(f)
    companies = {t: company_from_dict({"ticker": t, **c}) for t, c in world["companies"].items()}
    return FakeProvider(companies, fx=world.get("fx"), peers=world.get("peers"),
                        errors=set(world.get("errors", [])), risk_free=world.get("risk_free"))
