import pytest

from dcf.wacc import compute_wacc


def test_sample_acme():
    b = compute_wacc(risk_free=4.3, beta=1.0, erp=4.5, cost_of_debt_pre_tax=5.0,
                     tax_rate=21, market_cap=454, debt=20)
    assert b.cost_of_equity == pytest.approx(8.8)
    assert b.cost_of_debt_after_tax == pytest.approx(3.95)
    assert b.equity_weight == pytest.approx(0.9578, abs=1e-4)
    assert b.wacc == pytest.approx(8.5954, abs=1e-3)


def test_no_debt():
    b = compute_wacc(4.3, 1.2, 4.5, 5.0, 21, market_cap=100, debt=0)
    assert b.wacc == pytest.approx(b.cost_of_equity)
    assert b.debt_weight == 0


def test_zero_market_cap_raises():
    with pytest.raises(ValueError):
        compute_wacc(4.3, 1.0, 4.5, 5.0, 21, market_cap=0, debt=10)
