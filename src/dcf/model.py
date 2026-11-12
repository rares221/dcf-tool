"""Free-cash-flow DCF. Growth starts at the user's rate and fades half-way toward
long-term growth over the horizon; terminal value is perpetuity growth."""
from __future__ import annotations

from dataclasses import dataclass

from .types import Assumptions, ModelInputs


@dataclass(frozen=True)
class DcfResult:
    value_per_share: float
    terminal_share: float


def margin_used(inputs: ModelInputs, fcf_margin: float, count_sbc: bool) -> float:
    """The cash margin the model applies: reported margin, plus after-tax interest added back, minus stock pay if counted."""
    return max(0.0, fcf_margin + inputs.interest_pct - (inputs.sbc_pct if count_sbc else 0.0))


def dcf_value(inputs: ModelInputs, a: Assumptions, horizon: int, count_sbc: bool) -> DcfResult:
    if a.wacc <= a.terminal_growth:
        raise ValueError("discount rate must exceed long-term growth")
    if inputs.shares <= 0:
        raise ValueError("shares must be positive")
    if horizon < 1:
        raise ValueError("horizon must be at least 1")

    margin = margin_used(inputs, a.fcf_margin, count_sbc)
    w = a.wacc / 100
    rev = inputs.revenue
    pv_fcf = 0.0
    fcf = 0.0
    for i in range(1, horizon + 1):
        g_i = a.growth + (a.terminal_growth - a.growth) * ((i - 1) / horizon) * 0.5
        rev *= 1 + g_i / 100
        fcf = rev * margin / 100
        pv_fcf += fcf / (1 + w) ** i

    terminal_value = fcf * (1 + a.terminal_growth / 100) / (w - a.terminal_growth / 100)
    pv_terminal = terminal_value / (1 + w) ** horizon
    total = pv_fcf + pv_terminal
    equity = total + inputs.cash - inputs.debt - inputs.other_claims
    return DcfResult(
        value_per_share=max(0.0, equity / inputs.shares),
        terminal_share=pv_terminal / total if total > 0 else 0.0,
    )
