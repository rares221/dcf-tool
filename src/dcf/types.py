"""Shared data types. Rates and percentages are percent points (8.6 means 8.6%)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Assumptions:
    growth: float
    fcf_margin: float
    wacc: float
    terminal_growth: float


@dataclass(frozen=True)
class ModelInputs:
    revenue: float  # latest fiscal-year revenue
    cash: float
    debt: float
    shares: float
    price: float
    sbc_pct: float  # stock-based pay as % of revenue


@dataclass(frozen=True)
class YearFigures:
    year: int
    revenue: float
    fcf: float
    sbc: float


@dataclass(frozen=True)
class CompanyData:
    ticker: str
    name: str
    sector: str | None
    industry: str | None
    trading_currency: str
    statement_currency: str
    price: float
    market_cap: float
    shares: float | None
    beta: float | None
    forward_pe: float | None
    cash: float
    debt: float
    interest_expense: float | None
    tax_rate: float | None
    years: tuple[YearFigures, ...]  # oldest first, in statement_currency
    data_age_seconds: float = 0.0
    stale: bool = False
    share_growth: float | None = None  # average yearly change in diluted share count, percent
