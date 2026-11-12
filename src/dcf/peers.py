"""Peer comparison statistics."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .types import CompanyData

IN_LINE_BAND = 0.05  # within 5% of the median counts as "in line"

# metric -> (word when above median, word when below median); None = no judgement
DIRECTION: dict[str, tuple[str, str] | None] = {
    "market_cap": None,
    "growth": ("faster", "slower"),
    "fcf_margin": ("higher", "lower"),
    "fcf_yield": ("cheaper", "pricier"),
    "forward_pe": ("pricier", "cheaper"),
    "beta": ("jumpier", "steadier"),
}


@dataclass(frozen=True)
class PeerMetrics:
    ticker: str
    market_cap: float  # in the subject company's currency
    growth: float | None
    fcf_margin: float | None
    fcf_yield: float | None
    forward_pe: float | None
    beta: float | None


def metrics_for(company: CompanyData, market_cap_in_subject_ccy: float) -> PeerMetrics:
    """Statements must already be in the company's trading currency so yield = FCF / market cap is consistent."""
    years = company.years
    latest = years[-1] if years else None
    growth = None
    if len(years) >= 2 and years[-2].revenue > 0:
        growth = (years[-1].revenue / years[-2].revenue - 1) * 100
    margin = latest.fcf / latest.revenue * 100 if latest and latest.revenue > 0 else None
    fcf_yield = latest.fcf / company.market_cap * 100 if latest and company.market_cap > 0 else None
    return PeerMetrics(
        ticker=company.ticker, market_cap=market_cap_in_subject_ccy, growth=growth,
        fcf_margin=margin, fcf_yield=fcf_yield, forward_pe=company.forward_pe, beta=company.beta,
    )


def peer_median(rows: list[PeerMetrics], key: str) -> float | None:
    values = [getattr(r, key) for r in rows if getattr(r, key) is not None]
    return median(values) if values else None


def reading(key: str, value: float | None, med: float | None) -> dict:
    if key not in DIRECTION:
        raise KeyError(key)
    words = DIRECTION[key]
    if words is None:
        return {"label": "", "diff_pct": None}
    if value is None or med is None or med == 0:
        return {"label": "n/a", "diff_pct": None}
    diff = (value - med) / abs(med)
    label = "in line" if abs(diff) < IN_LINE_BAND else words[0] if diff > 0 else words[1]
    return {"label": label, "diff_pct": round(diff * 100, 1)}
