import pytest

from dcf.model import dcf_value
from dcf.types import Assumptions, ModelInputs

ACME = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=168, sbc_pct=3)
BASE = Assumptions(growth=7, fcf_margin=20, wacc=8.6, terminal_growth=2.5)


def test_perpetuity_sanity():
    inputs = ModelInputs(revenue=100, cash=0, debt=0, shares=1, price=1, sbc_pct=0)
    a = Assumptions(growth=0, fcf_margin=10, wacc=10, terminal_growth=0)
    r = dcf_value(inputs, a, horizon=5, count_sbc=False)
    assert r.value_per_share == pytest.approx(100.0, abs=1e-6)
    assert r.terminal_share == pytest.approx(0.62092, abs=1e-4)


def test_acme_without_sbc():
    r = dcf_value(ACME, BASE, horizon=5, count_sbc=False)
    assert r.value_per_share == pytest.approx(149.33, abs=0.01)
    assert r.terminal_share == pytest.approx(0.7607, abs=1e-3)


def test_acme_with_sbc():
    r = dcf_value(ACME, BASE, horizon=5, count_sbc=True)
    assert r.value_per_share == pytest.approx(127.49, abs=0.01)


def test_acme_other_horizons():
    assert dcf_value(ACME, BASE, 3, True).value_per_share == pytest.approx(120.95, abs=0.01)
    assert dcf_value(ACME, BASE, 10, True).value_per_share == pytest.approx(142.81, abs=0.01)


def test_wacc_must_exceed_terminal_growth():
    a = Assumptions(growth=7, fcf_margin=20, wacc=2.5, terminal_growth=2.5)
    with pytest.raises(ValueError):
        dcf_value(ACME, a, 5, False)


def test_value_floored_at_zero():
    inputs = ModelInputs(revenue=100, cash=0, debt=10_000, shares=2.7, price=168, sbc_pct=0)
    assert dcf_value(inputs, BASE, 5, False).value_per_share == 0.0


def test_margin_after_sbc_never_negative():
    a = Assumptions(growth=7, fcf_margin=2, wacc=8.6, terminal_growth=2.5)
    r = dcf_value(ACME, a, 5, True)
    assert r.value_per_share == pytest.approx((30 - 20) / 2.7)


def test_interest_addback_acts_like_a_higher_margin():
    # Yahoo's free cash flow is after interest; adding back after-tax interest (as % of revenue) keeps it consistent
    # with a discount rate that already prices the debt.
    with_interest = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=168, sbc_pct=3, interest_pct=1.0)
    for count_sbc in (True, False):
        plain = dcf_value(ACME, Assumptions(7, 21, 8.6, 2.5), 5, count_sbc).value_per_share
        added = dcf_value(with_interest, Assumptions(7, 20, 8.6, 2.5), 5, count_sbc).value_per_share
        assert added == pytest.approx(plain)


def test_interest_addback_defaults_to_nothing():
    assert ModelInputs(100, 30, 20, 2.7, 168, 3).interest_pct == 0.0
