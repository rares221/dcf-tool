import pytest

from dcf.currency import convert_statements, fx_symbol, normalise_quote
from tests.helpers import make_company


def test_pence_become_pounds():
    assert normalise_quote("GBp", 1250.0) == ("GBP", 12.5)
    assert normalise_quote("GBX", 100.0) == ("GBP", 1.0)


def test_other_codes_pass_through_uppercased():
    assert normalise_quote("EUR", 10.0) == ("EUR", 10.0)
    assert normalise_quote("usd", 5.0) == ("USD", 5.0)


def test_fx_symbol():
    assert fx_symbol("TWD", "USD") == "TWDUSD=X"


def test_convert_statements_scales_statement_figures_only():
    c = make_company(statement_currency="TWD", trading_currency="USD", interest_expense=4.0)
    out = convert_statements(c, 0.5)
    assert out.statement_currency == "USD"
    assert out.cash == c.cash * 0.5 and out.debt == c.debt * 0.5 and out.interest_expense == 2.0
    for before, after in zip(c.years, out.years):
        assert after.revenue == before.revenue * 0.5
        assert after.fcf == before.fcf * 0.5 and after.sbc == before.sbc * 0.5
    assert (out.price, out.market_cap, out.shares, out.beta) == (c.price, c.market_cap, c.shares, c.beta)


def test_convert_keeps_missing_interest_missing():
    out = convert_statements(make_company(interest_expense=None), 2.0)
    assert out.interest_expense is None


@pytest.mark.parametrize("rate", [0, -1.0])
def test_bad_rate_raises(rate):
    with pytest.raises(ValueError):
        convert_statements(make_company(), rate)
