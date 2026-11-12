import pytest

from dcf.model import dcf_value
from dcf.scenarios import (build_scenarios, implied_growth, implied_return, present_value_of_100,
                           price_position, sbc_effect, sensitivity)
from dcf.types import Assumptions, ModelInputs

ACME = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=168, sbc_pct=3)
BASE = Assumptions(growth=7, fcf_margin=20, wacc=8.6, terminal_growth=2.5)


def test_build_scenarios_matches_reference_values():
    s = build_scenarios(ACME, BASE, 5, True)
    assert s.bear == pytest.approx(75.75, abs=0.01)
    assert s.base == pytest.approx(127.49, abs=0.01)
    assert s.bull == pytest.approx(185.82, abs=0.01)
    assert 0 < s.terminal_share < 1


def test_implied_growth_round_trips_to_price():
    g = implied_growth(ACME, BASE, 5, True)
    assert g == pytest.approx(15.44, abs=0.01)
    a = Assumptions(g, BASE.fcf_margin, BASE.wacc, BASE.terminal_growth)
    assert dcf_value(ACME, a, 5, True).value_per_share == pytest.approx(168, abs=0.01)


def test_implied_growth_none_when_unreachable():
    inputs = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=100_000, sbc_pct=3)
    assert implied_growth(inputs, BASE, 5, True) is None


def test_implied_return():
    assert implied_return(127.49, 168, 5) == pytest.approx(-5.37, abs=0.01)


def test_price_position():
    assert price_position(168, 75.75, 185.82) == "upper"
    assert price_position(50, 75.75, 185.82) == "below"
    assert price_position(200, 75.75, 185.82) == "above"
    assert price_position(130, 75.75, 185.82) == "middle"
    assert price_position(90, 75.75, 185.82) == "lower"


def test_sensitivity_sorted_and_wacc_bar_values():
    bars = sensitivity(ACME, BASE, 5, True)
    assert {b.key for b in bars} == {"wacc", "growth", "margin", "terminal_growth"}
    widths = [b.high - b.low for b in bars]
    assert widths == sorted(widths, reverse=True)
    wacc = next(b for b in bars if b.key == "wacc")
    assert wacc.low == pytest.approx(109.82, abs=0.01)
    assert wacc.high == pytest.approx(152.11, abs=0.01)


def test_sensitivity_clamps_flex_near_terminal_growth():
    a = Assumptions(growth=7, fcf_margin=20, wacc=5, terminal_growth=4)
    bars = sensitivity(ACME, a, 5, True)  # must not raise
    assert len(bars) == 4


def test_sbc_effect():
    assert sbc_effect(ACME, BASE, 5) == pytest.approx(21.84, abs=0.02)


def test_present_value_of_100():
    assert present_value_of_100(8.6, 5) == pytest.approx(66.2, abs=0.1)


def test_bull_is_never_below_base_and_bear_never_above_base_across_the_slider_grid():
    # Review finding: wacc 5 with long-term growth 4 once gave bear 214 / base 736 / bull 500.
    for growth in (-10, 0, 7, 15, 30):
        for margin in (1, 20, 60):
            for wacc in (5, 5.5, 6, 6.5, 8.6, 12, 16):
                for terminal in (0, 2.5, 4):
                    if wacc < terminal + 1:
                        continue
                    a = Assumptions(growth, margin, wacc, terminal)
                    for sbc in (True, False):
                        s = build_scenarios(ACME, a, 5, sbc)
                        assert s.bear <= s.base + 1e-9, (a, sbc, s)
                        assert s.base <= s.bull + 1e-9, (a, sbc, s)


def test_bull_discount_rate_never_exceeds_base_discount_rate():
    a = Assumptions(7, 20, 5, 4)
    s = build_scenarios(ACME, a, 5, True)
    assert s.bull >= s.base
