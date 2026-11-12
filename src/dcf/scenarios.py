"""Scenarios, sensitivity and reverse DCF built on the core model."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .model import dcf_value
from .types import Assumptions, ModelInputs

# Spec section 8 starting values (bear/bull spreads and sensitivity flex).
SENSITIVITY_FLEX = (("wacc", 1.0), ("growth", 3.0), ("margin", 3.0), ("terminal_growth", 1.0))
WACC_GAP = 0.5  # flexed discount rate must stay this far above long-term growth


@dataclass(frozen=True)
class Scenarios:
    bear: float
    base: float
    bull: float
    terminal_share: float


@dataclass(frozen=True)
class SensitivityBar:
    key: str
    delta: float
    low: float
    high: float


def _value(inputs: ModelInputs, a: Assumptions, horizon: int, count_sbc: bool) -> float:
    return dcf_value(inputs, a, horizon, count_sbc).value_per_share


def build_scenarios(inputs: ModelInputs, a: Assumptions, horizon: int, count_sbc: bool) -> Scenarios:
    bear_a = Assumptions(
        growth=a.growth - 4, fcf_margin=a.fcf_margin - 3, wacc=a.wacc + 1,
        terminal_growth=max(a.terminal_growth - 0.5, 0.0),
    )
    bull_a = Assumptions(
        growth=a.growth + 4, fcf_margin=a.fcf_margin + 3,
        wacc=max(a.wacc - 0.5, a.terminal_growth + 2), terminal_growth=a.terminal_growth,
    )
    base = dcf_value(inputs, a, horizon, count_sbc)
    return Scenarios(
        bear=_value(inputs, bear_a, horizon, count_sbc),
        base=base.value_per_share,
        bull=_value(inputs, bull_a, horizon, count_sbc),
        terminal_share=base.terminal_share,
    )


def _flexed(a: Assumptions, key: str, amount: float) -> Assumptions:
    if key == "wacc":
        return replace(a, wacc=max(a.wacc + amount, a.terminal_growth + WACC_GAP))
    if key == "growth":
        return replace(a, growth=a.growth + amount)
    if key == "margin":
        return replace(a, fcf_margin=a.fcf_margin + amount)
    return replace(a, terminal_growth=min(a.terminal_growth + amount, a.wacc - WACC_GAP))


def sensitivity(inputs: ModelInputs, a: Assumptions, horizon: int, count_sbc: bool) -> list[SensitivityBar]:
    bars = []
    for key, delta in SENSITIVITY_FLEX:
        x = _value(inputs, _flexed(a, key, -delta), horizon, count_sbc)
        y = _value(inputs, _flexed(a, key, delta), horizon, count_sbc)
        bars.append(SensitivityBar(key=key, delta=delta, low=min(x, y), high=max(x, y)))
    return sorted(bars, key=lambda b: b.high - b.low, reverse=True)


def implied_growth(inputs: ModelInputs, a: Assumptions, horizon: int, count_sbc: bool) -> float | None:
    """Starting growth that makes the base value equal the current price, or None if unreachable."""
    lo, hi = -15.0, 45.0

    def at(g: float) -> float:
        return _value(inputs, replace(a, growth=g), horizon, count_sbc)

    if at(lo) > inputs.price or at(hi) < inputs.price:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if at(mid) < inputs.price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def implied_return(value: float, price: float, horizon: int) -> float:
    return ((value / price) ** (1 / horizon) - 1) * 100


def price_position(price: float, bear: float, bull: float) -> str:
    if price < bear:
        return "below"
    if price > bull:
        return "above"
    if bull <= bear:
        return "middle"
    p = (price - bear) / (bull - bear)
    return "lower" if p < 1 / 3 else "upper" if p > 2 / 3 else "middle"


def sbc_effect(inputs: ModelInputs, a: Assumptions, horizon: int) -> float:
    return _value(inputs, a, horizon, False) - _value(inputs, a, horizon, True)


def present_value_of_100(wacc: float, horizon: int) -> float:
    return 100 / (1 + wacc / 100) ** horizon
