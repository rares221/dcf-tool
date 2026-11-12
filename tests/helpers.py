"""Shared test builders."""
from __future__ import annotations

from dataclasses import replace

from dcf.types import CompanyData, YearFigures


def make_years(revenues=(82, 88, 94, 100), fcfs=(14, 16.7, 16.9, 20), sbcs=(2.0, 2.4, 2.7, 3.0), start=2022):
    return tuple(YearFigures(start + i, r, f, s) for i, (r, f, s) in enumerate(zip(revenues, fcfs, sbcs)))


def make_company(**overrides) -> CompanyData:
    base = CompanyData(
        ticker="ACME", name="ACME Corp", sector="Technology", industry="Software - Application",
        trading_currency="USD", statement_currency="USD", price=168.0, market_cap=454.0, shares=2.7,
        beta=1.0, forward_pe=28.0, cash=30.0, debt=20.0, interest_expense=1.0, tax_rate=21.0,
        years=make_years(),
    )
    return replace(base, **overrides)
