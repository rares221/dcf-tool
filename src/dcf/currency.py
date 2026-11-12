"""Currency helpers: quotation sub-units and statement conversion (spec section 7)."""
from __future__ import annotations

from dataclasses import replace

from .types import CompanyData, YearFigures

# Sub-unit quote codes -> (main currency, divisor). To be confirmed against live data (plan Task 8).
SUBUNITS: dict[str, tuple[str, int]] = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ZAc": ("ZAR", 100),
    "ILA": ("ILS", 100),
}


def normalise_quote(currency: str, amount: float) -> tuple[str, float]:
    if currency in SUBUNITS:
        main, divisor = SUBUNITS[currency]
        return main, amount / divisor
    return currency.upper(), amount


def fx_symbol(from_ccy: str, to_ccy: str) -> str:
    return f"{from_ccy.upper()}{to_ccy.upper()}=X"


def convert_statements(company: CompanyData, rate: float) -> CompanyData:
    if rate <= 0:
        raise ValueError("exchange rate must be positive")
    years = tuple(
        YearFigures(y.year, y.revenue * rate, y.fcf * rate, y.sbc * rate) for y in company.years
    )
    return replace(
        company,
        years=years,
        cash=company.cash * rate,
        debt=company.debt * rate,
        long_term_investments=company.long_term_investments * rate,
        interest_expense=None if company.interest_expense is None else company.interest_expense * rate,
        statement_currency=company.trading_currency,
    )
