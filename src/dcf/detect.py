"""Decide whether a DCF is appropriate for a company (spec section 9)."""
from __future__ import annotations

from dataclasses import dataclass

from .types import CompanyData


@dataclass(frozen=True)
class Assessment:
    status: str  # ok | partial | bank | loss_making | insufficient_data
    reasons: tuple[str, ...] = ()


def _is_bank_or_insurer(company: CompanyData) -> bool:
    industry = (company.industry or "").lower()
    return "bank" in industry or "insurance" in industry


def assess(company: CompanyData) -> Assessment:
    if _is_bank_or_insurer(company):
        return Assessment("bank")
    years = company.years
    if len(years) < 2:
        return Assessment("insufficient_data", ("years_missing",))
    recent = years[-4:]
    if recent[-1].fcf <= 0 or sum(1 for y in recent if y.fcf < 0) >= 2:
        return Assessment("loss_making")

    reasons: list[str] = []
    if len(years) < 4:
        reasons.append("years_missing")
    if company.beta is None:
        reasons.append("beta_missing")
    shares_ok = (company.shares or 0) > 0 or (company.market_cap > 0 and company.price > 0)
    if not shares_ok:
        reasons.append("shares_missing")
    if company.tax_rate is None:
        reasons.append("tax_missing")
    if company.interest_expense is None:
        reasons.append("interest_missing")
    # A provider that has no SBC row yields zeros; all-zero is treated as unknown (may flag a company that truly pays none).
    if all(y.sbc == 0 for y in years):
        reasons.append("sbc_missing")
    return Assessment("partial" if reasons else "ok", tuple(reasons))
