"""Weighted average cost of capital. Rates are percent points."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaccBreakdown:
    risk_free: float
    beta: float
    erp: float
    cost_of_equity: float
    cost_of_debt_pre_tax: float
    tax_rate: float
    cost_of_debt_after_tax: float
    equity_weight: float
    debt_weight: float
    wacc: float


def compute_wacc(risk_free: float, beta: float, erp: float, cost_of_debt_pre_tax: float,
                 tax_rate: float, market_cap: float, debt: float) -> WaccBreakdown:
    if market_cap <= 0:
        raise ValueError("market cap must be positive")
    debt = max(debt, 0.0)
    cost_of_equity = risk_free + beta * erp
    kd_after = cost_of_debt_pre_tax * (1 - tax_rate / 100)
    equity_weight = market_cap / (market_cap + debt)
    debt_weight = 1 - equity_weight
    return WaccBreakdown(
        risk_free=risk_free, beta=beta, erp=erp, cost_of_equity=cost_of_equity,
        cost_of_debt_pre_tax=cost_of_debt_pre_tax, tax_rate=tax_rate,
        cost_of_debt_after_tax=kd_after, equity_weight=equity_weight,
        debt_weight=debt_weight, wacc=equity_weight * cost_of_equity + debt_weight * kd_after,
    )
