from dcf.detect import assess
from tests.helpers import make_company, make_years


def test_banks_and_insurers_are_declined():
    assert assess(make_company(industry="Banks - Regional")).status == "bank"
    assert assess(make_company(industry="Insurance - Life")).status == "bank"


def test_payments_company_is_not_a_bank():
    assert assess(make_company(industry="Credit Services")).status == "ok"


def test_bank_with_one_year_is_still_bank():
    c = make_company(industry="Banks - Diversified", years=make_years((1,), (1,), (0,)))
    assert assess(c).status == "bank"


def test_one_year_is_insufficient():
    c = make_company(years=make_years((100,), (10,), (1,)))
    assert assess(c).status == "insufficient_data"


def test_latest_negative_fcf_is_loss_making():
    c = make_company(years=make_years(fcfs=(10, 12, 14, -1)))
    assert assess(c).status == "loss_making"


def test_two_negative_years_is_loss_making_even_if_latest_positive():
    c = make_company(years=make_years(fcfs=(-5, -2, 8, 20)))
    assert assess(c).status == "loss_making"


def test_one_negative_year_is_ok():
    c = make_company(years=make_years(fcfs=(-5, 12, 14, 20)))
    assert assess(c).status == "ok"


def test_three_years_is_partial():
    c = make_company(years=make_years((88, 94, 100), (16, 17, 20), (2, 2, 3)))
    a = assess(c)
    assert a.status == "partial" and "years_missing" in a.reasons


def test_missing_beta_is_partial():
    a = assess(make_company(beta=None))
    assert a.status == "partial" and "beta_missing" in a.reasons


def test_missing_tax_and_interest_are_partial():
    a = assess(make_company(tax_rate=None, interest_expense=None))
    assert a.status == "partial" and {"tax_missing", "interest_missing"} <= set(a.reasons)


def test_all_zero_sbc_is_reported_as_missing():
    c = make_company(years=make_years(sbcs=(0, 0, 0, 0)))
    a = assess(c)
    assert a.status == "partial" and "sbc_missing" in a.reasons


def test_shares_derivable_from_market_cap_and_price():
    assert assess(make_company(shares=None)).status == "ok"


def test_shares_not_derivable_means_no_per_share_value_is_possible():
    a = assess(make_company(shares=None, market_cap=0))
    assert a.status == "insufficient_data" and "shares_missing" in a.reasons
