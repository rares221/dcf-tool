import json
import math

import pytest

from dcf.data.fake import FakeProvider, load_fake_world
from dcf.service import analyze, model_inputs, normalise_ticker, run_model
from dcf.types import Assumptions, ModelInputs
from tests.helpers import make_company, make_years

PEER_ROWS = {
    "NOVA": make_company(ticker="NOVA", market_cap=380.0, forward_pe=31.0, beta=1.2,
                         years=make_years((90, 99), (20, 23.8), (2, 2))),
    "ORBT": make_company(ticker="ORBT", market_cap=520.0, forward_pe=36.0, beta=1.3,
                         years=make_years((100, 112), (16, 20.2), (2, 2))),
}


def world(**extra):
    companies = {"ACME": make_company(), **PEER_ROWS}
    companies.update(extra.pop("companies", {}))
    return FakeProvider(companies, peers={"ACME": ["NOVA", "ORBT"]}, **extra)


def assert_finite(x, path="payload"):
    if isinstance(x, float):
        assert math.isfinite(x), f"{path} is {x}"
    elif isinstance(x, dict):
        for k, v in x.items():
            assert_finite(v, f"{path}.{k}")
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x):
            assert_finite(v, f"{path}[{i}]")


def test_normalise_ticker():
    assert normalise_ticker(" aapl ") == "AAPL"
    assert normalise_ticker("brk.b") == "BRK.B"
    assert normalise_ticker("BRK-B") == "BRK-B"
    assert normalise_ticker("^gspc") == "^GSPC"
    for bad in ("", "   ", "<script>", "A" * 16, "ap pl", "AAPL;DROP", "...", "-", "^", "=", "^=", ".-"):
        assert normalise_ticker(bad) is None


def test_share_class_ticker_with_a_dot_falls_back_to_yahoos_dash_form():
    brk = make_company(ticker="BRK-B", name="Berkshire-like Class B")
    p = world(companies={"BRK-B": brk})
    out = analyze("brk.b", p)
    assert out["status"] == "ok" and out["company"]["ticker"] == "BRK-B"
    assert p.fetch_log[:2] == ["BRK.B", "BRK-B"]
    assert model_inputs("BRK.B", p)[0] == "ok"


def test_exchange_suffix_tickers_are_not_rewritten_when_found():
    p = world(companies={"LSE.L": make_company(ticker="LSE.L", trading_currency="GBP", statement_currency="GBP")})
    assert analyze("LSE.L", p)["status"] == "ok"
    assert p.fetch_log[0] == "LSE.L" and "LSE-L" not in p.fetch_log


def test_invalid_ticker_never_reaches_provider():
    p = world()
    out = analyze("<script>", p)
    assert out["status"] == "not_found" and p.fetch_log == []


def test_unknown_ticker_has_suggestions():
    out = analyze("ACMX", world())
    assert out["status"] == "not_found" and out["suggestions"] == ["ACME"]
    assert out["company"] is None and out["history"] == []


def test_normal_company():
    out = analyze("acme", world())
    assert out["status"] == "ok" and "non_us" not in out["notes"]
    assert out["company"]["currency"] == "USD" and out["company"]["price"] == 168.0
    assert 5 <= out["suggested"]["wacc"] <= 16
    assert len(out["history"]) == 4
    assert out["peers"]["rows"][0]["ticker"] == "ACME"
    assert [r["ticker"] for r in out["peers"]["rows"][1:]] == ["NOVA", "ORBT"]
    assert out["peers"]["medians"]["growth"] == pytest.approx(11.0, abs=0.1)
    assert out["peers"]["readings"]["growth"]["label"] in {"slower", "in line", "faster"}
    assert list(out["limits"]["growth"]) == [-10, 30]
    assert out["base"]["revenue"] == 100 and out["base"]["sbc_pct"] == pytest.approx(3.0)
    assert out["history_cagr"] == pytest.approx(6.84, abs=0.01)
    assert_finite(out)


def test_share_growth_is_passed_through():
    assert analyze("ACME", world(companies={"ACME": make_company(share_growth=1.3)}))["share_growth"] == 1.3
    assert analyze("ACME", world())["share_growth"] is None
    assert analyze("NOPE", world())["share_growth"] is None


def test_suggestions_are_rounded_to_slider_steps():
    s = analyze("ACME", world())["suggested"]
    assert (s["growth"] * 2) == round(s["growth"] * 2)
    assert (s["fcf_margin"] * 2) == round(s["fcf_margin"] * 2)
    assert round(s["wacc"], 1) == s["wacc"]


def test_london_style_company_is_non_us():
    p = world(companies={"LSE.L": make_company(ticker="LSE.L", trading_currency="GBP", statement_currency="GBP")})
    out = analyze("LSE.L", p)
    assert "non_us" in out["notes"] and out["company"]["currency"] == "GBP"


def test_adr_converted_with_fx_note():
    adr = make_company(ticker="ADR", trading_currency="USD", statement_currency="TWD",
                       years=make_years((2000, 2200, 2500, 3000), (400, 500, 600, 800), (1, 1, 1, 1)),
                       cash=1000.0, debt=500.0, interest_expense=20.0)
    out = analyze("ADR", world(companies={"ADR": adr}, fx={"TWDUSD": 0.03}))
    assert "fx_converted" in out["notes"]
    assert out["fx"] == {"from": "TWD", "to": "USD", "rate": 0.03}
    assert out["base"]["revenue"] == pytest.approx(3000 * 0.03)
    assert out["base"]["cash"] == pytest.approx(30.0)


def test_adr_without_rate_is_blocking():
    adr = make_company(ticker="ADR", trading_currency="USD", statement_currency="TWD")
    out = analyze("ADR", world(companies={"ADR": adr}))
    assert out["status"] == "no_fx" and out["suggested"] is None and out["base"] is None
    assert out["company"]["currency"] == "USD" and out["company"]["statement_currency"] == "TWD"


def test_extreme_company_is_clamped_with_notes():
    c = make_company(ticker="WILD", years=make_years((10, 20, 50, 100), (7, 14, 35, 70), (1, 1, 1, 1)))
    out = analyze("WILD", world(companies={"WILD": c}))
    s = out["suggested"]
    assert s["growth"] == 30 and s["fcf_margin"] == 60
    assert {"suggestion_clamped:growth", "suggestion_clamped:fcf_margin"} <= set(out["notes"])
    assert_finite(out)


def test_shrinking_company_growth_within_limits():
    c = make_company(ticker="SHRK", years=make_years((100, 90, 80, 70), (10, 9, 8, 7), (1, 1, 1, 1)))
    s = analyze("SHRK", world(companies={"SHRK": c}))["suggested"]
    assert s["growth"] == -10


def test_missing_fields_use_defaults_and_flag_partial():
    c = make_company(ticker="GAPS", beta=None, tax_rate=None, interest_expense=None,
                     years=make_years(sbcs=(0, 0, 0, 0)))
    out = analyze("GAPS", world(companies={"GAPS": c}))
    assert out["status"] == "partial"
    assert {"beta_missing", "tax_missing", "interest_missing", "sbc_missing"} <= set(out["notes"])
    assert out["suggested"]["wacc_breakdown"]["beta"] == 1.0
    assert_finite(out)


def test_shares_derived_from_market_cap():
    out = analyze("ACME", world(companies={"ACME": make_company(shares=None)}))
    assert out["status"] == "ok" and out["base"]["shares"] == pytest.approx(454 / 168)


def test_no_share_count_and_no_market_cap_is_a_designed_state_not_an_error():
    c = make_company(ticker="NOSH", shares=None, market_cap=0.0)
    out = analyze("NOSH", world(companies={"NOSH": c}))
    assert out["status"] == "insufficient_data" and "shares_missing" in out["notes"]
    assert out["suggested"] is None and len(out["history"]) == 4
    assert model_inputs("NOSH", world(companies={"NOSH": c}))[1] is None


def test_non_finite_numbers_never_reach_the_payload_or_break_serialisation():
    nan = float("nan")
    c = make_company(ticker="NANS", beta=nan, tax_rate=nan, interest_expense=float("inf"), forward_pe=nan)
    out = analyze("NANS", world(companies={"NANS": c}))
    assert out["status"] == "partial" and {"beta_missing", "tax_missing", "interest_missing"} <= set(out["notes"])
    assert out["suggested"]["wacc_breakdown"]["beta"] == 1.0
    assert_finite(out)
    json.dumps(out, allow_nan=False)  # must be valid JSON


def test_bank_returns_history_but_no_suggestions():
    bank = make_company(ticker="BANK", industry="Banks - Regional")
    out = analyze("BANK", world(companies={"BANK": bank}))
    assert out["status"] == "bank" and out["suggested"] is None
    assert len(out["history"]) == 4 and out["company"]["ticker"] == "BANK"


def test_loss_maker_returns_history_and_peers_but_no_suggestions():
    c = make_company(ticker="LOSS", years=make_years(fcfs=(-5, -4, -3, -2)))
    out = analyze("LOSS", world(companies={"LOSS": c}), peer_tickers=["NOVA"])
    assert out["status"] == "loss_making" and out["suggested"] is None and out["base"] is None
    assert out["peers"]["rows"][0]["ticker"] == "LOSS"


def test_stale_data_is_flagged():
    c = make_company(stale=True, data_age_seconds=5000.0)
    out = analyze("ACME", world(companies={"ACME": c}))
    assert "stale" in out["notes"] and out["data_age_seconds"] == 5000.0


def test_provider_outage_is_an_error_status():
    out = analyze("ACME", world(errors={"ACME"}))
    assert out["status"] == "error" and out["company"] is None


def test_peer_in_other_currency_is_converted_and_failures_are_dropped():
    euro = make_company(ticker="EURO", trading_currency="EUR", statement_currency="EUR", market_cap=100.0)
    p = world(companies={"EURO": euro}, fx={"EURUSD": 1.1}, errors={"ORBT"})
    out = analyze("ACME", p, peer_tickers=["EURO", "ORBT", "GHOST", "ACME"])
    tickers = [r["ticker"] for r in out["peers"]["rows"]]
    assert tickers == ["ACME", "EURO"]
    assert out["peers"]["rows"][1]["market_cap"] == pytest.approx(110.0)


def test_a_peer_that_breaks_in_an_unexpected_way_is_skipped_not_fatal():
    class Flaky(FakeProvider):
        def fetch_company(self, ticker):
            if ticker == "BAD":
                raise ValueError("unparseable peer")
            return super().fetch_company(ticker)

    p = Flaky({"ACME": make_company(), **PEER_ROWS})
    out = analyze("ACME", p, peer_tickers=["BAD", "NOVA"])
    assert out["status"] == "ok"
    assert [r["ticker"] for r in out["peers"]["rows"]] == ["ACME", "NOVA"]


def test_interest_is_added_back_after_tax_as_a_share_of_revenue():
    _, inputs = model_inputs("ACME", world())              # interest 1.0 on revenue 100, tax 21%
    assert inputs.interest_pct == pytest.approx(0.79)


def test_interest_addback_uses_default_tax_when_missing_and_nothing_when_interest_is_unknown_or_odd():
    no_tax = make_company(ticker="NT", tax_rate=None)
    assert model_inputs("NT", world(companies={"NT": no_tax}))[1].interest_pct == pytest.approx(0.79)
    for odd in (None, float("nan"), -5.0):
        c = make_company(ticker="ODD", interest_expense=odd)
        assert model_inputs("ODD", world(companies={"ODD": c}))[1].interest_pct == 0.0


def test_long_term_investments_count_as_cash_like_assets_in_the_bridge():
    c = make_company(ticker="LTI", long_term_investments=10.0)       # cash is 30, debt 20, shares 2.7
    _, inputs = model_inputs("LTI", world(companies={"LTI": c}))
    assert inputs.cash == pytest.approx(40.0)
    base = analyze("LTI", world(companies={"LTI": c}))["base"]
    assert base["long_term_investments"] == 10.0
    assert base["long_term_investments_per_share"] == pytest.approx(10.0 / 2.7)
    assert analyze("ACME", world())["base"]["long_term_investments"] == 0.0


def test_peers_are_fetched_concurrently_and_keep_their_order():
    import threading

    barrier = threading.Barrier(4, timeout=3)

    class Concurrent(FakeProvider):
        def fetch_company(self, ticker):
            if ticker.startswith("P"):
                barrier.wait()  # only passes if all four peers are being fetched at the same moment
            return super().fetch_company(ticker)

    companies = {"ACME": make_company(), **{f"P{i}": make_company(ticker=f"P{i}") for i in range(1, 5)}}
    out = analyze("ACME", Concurrent(companies), peer_tickers=["P1", "P2", "P3", "P4"])
    assert [r["ticker"] for r in out["peers"]["rows"]] == ["ACME", "P1", "P2", "P3", "P4"]


def test_peer_list_is_capped_before_any_fetching():
    p = world()
    analyze("ACME", p, peer_tickers=[f"JUNK{i}" for i in range(300)])
    assert len(p.fetch_log) <= 1 + 8  # the company itself plus at most 8 peers


def test_requested_peers_override_suggested_peers():
    out = analyze("ACME", world(), peer_tickers=["ORBT"])
    assert [r["ticker"] for r in out["peers"]["rows"]] == ["ACME", "ORBT"]


ACME_INPUTS = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=168, sbc_pct=3)
BASE = Assumptions(7, 20, 8.6, 2.5)


def test_run_model_matches_reference_values():
    out = run_model(ACME_INPUTS, BASE, 5, True)
    assert out["scenarios"]["base"] == pytest.approx(127.49, abs=0.01)
    assert out["scenarios"]["bear"] == pytest.approx(75.75, abs=0.01)
    assert out["scenarios"]["bull"] == pytest.approx(204.10, abs=0.01)
    assert out["position"] == "upper"
    assert out["implied_growth"] == pytest.approx(15.44, abs=0.01)
    assert out["implied_wacc"] == pytest.approx(7.112, abs=0.01)
    assert out["implied_return"]["base"] == pytest.approx(-5.37, abs=0.01)
    assert out["sbc_effect"] == pytest.approx(21.84, abs=0.02)
    assert out["pv_of_100"] == pytest.approx(66.2, abs=0.1)
    assert out["margin_used"] == pytest.approx(17.0)
    assert out["spreads"] == {"growth": 4.0, "margin": 3.0, "wacc_bear": 1.0, "wacc_bull": 1.0}
    assert {s["key"] for s in out["sensitivity"]} == {"wacc", "growth", "margin", "terminal_growth"}
    assert_finite(out)


def test_margin_used_ignores_stock_pay_when_switched_off():
    assert run_model(ACME_INPUTS, BASE, 5, False)["margin_used"] == pytest.approx(20.0)
    low = run_model(ACME_INPUTS, Assumptions(7, 2, 8.6, 2.5), 5, True)
    assert low["margin_used"] == 0.0


def test_margin_used_includes_the_interest_addback():
    inputs = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=168, sbc_pct=3, interest_pct=0.8)
    assert run_model(inputs, BASE, 5, True)["margin_used"] == pytest.approx(20 + 0.8 - 3)
    assert run_model(inputs, BASE, 5, False)["margin_used"] == pytest.approx(20.8)


def test_run_model_rejects_discount_rate_at_or_below_terminal_growth():
    with pytest.raises(ValueError):
        run_model(ACME_INPUTS, Assumptions(7, 20, 2.5, 2.5), 5, True)


def test_model_inputs_for_ticker():
    status, inputs = model_inputs("ACME", world())
    assert status == "ok" and inputs.revenue == 100 and inputs.shares == 2.7
    assert model_inputs("NOPE", world())[1] is None
    bank = world(companies={"BANK": make_company(ticker="BANK", industry="Banks - Regional")})
    assert model_inputs("BANK", bank)[0] == "bank"


def test_load_fake_world_roundtrip(tmp_path):
    c = make_company()
    d = {k: v for k, v in c.__dict__.items() if k != "years"}
    d["years"] = [y.__dict__ for y in c.years]
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"companies": {"ACME": d}, "fx": {"EURUSD": 1.1}}), encoding="utf-8")
    p = load_fake_world(str(path))
    assert p.fetch_company("ACME").price == 168.0 and p.fx_rate("EUR", "USD") == 1.1


def test_minority_interest_and_preferred_stock_are_subtracted_in_the_bridge():
    c = make_company(ticker="MIN", minority_interest=4.0, preferred_stock=2.0)       # shares 2.7
    status, inputs = model_inputs("MIN", world(companies={"MIN": c}))
    assert inputs.other_claims == pytest.approx(6.0) and inputs.debt == 20.0
    base = analyze("MIN", world(companies={"MIN": c}))["base"]
    assert base["minority_interest"] == 4.0 and base["preferred_stock"] == 2.0
    assert base["other_claims_per_share"] == pytest.approx(6.0 / 2.7)
    assert analyze("ACME", world())["base"]["other_claims_per_share"] == 0.0


def test_terminal_growth_is_capped_at_the_risk_free_rate():
    jp = make_company(ticker="JP", trading_currency="JPY", statement_currency="JPY")
    out = analyze("JP", FakeProvider({"JP": jp}, risk_free={"JPY": 1.5}))
    assert out["suggested"]["terminal_growth"] == 1.5
    assert list(out["limits"]["terminal_growth"]) == [0, 1.5]
    usd = analyze("ACME", world())
    assert usd["suggested"]["terminal_growth"] == 2.5 and list(usd["limits"]["terminal_growth"]) == [0, 4]


def test_cap_follows_the_slider_step_and_leaves_a_usable_slider_when_rates_are_tiny():
    def run(rate):
        c = make_company(ticker="X", trading_currency="CHF", statement_currency="CHF")
        return analyze("X", FakeProvider({"X": c}, risk_free={"CHF": rate}))
    assert list(run(3.3)["limits"]["terminal_growth"]) == [0, 3.25]
    tiny = run(0.1)
    assert list(tiny["limits"]["terminal_growth"]) == [0, 0.25] and tiny["suggested"]["terminal_growth"] == 0.25


def test_uneven_yearly_growth_is_reported_and_flagged():
    steady = analyze("ACME", world())
    assert steady["growth_range"]["max"] == pytest.approx(7.3, abs=0.1) and steady["growth_range"]["min"] == pytest.approx(6.4, abs=0.1)
    assert "growth_uneven" not in steady["notes"]
    c = make_company(ticker="UNE", years=make_years((100, 86, 87.3, 84), (10, 9, 9, 9), (1, 1, 1, 1)))
    out = analyze("UNE", world(companies={"UNE": c}))
    assert out["growth_range"]["min"] == pytest.approx(-14.0) and out["growth_range"]["max"] == pytest.approx(1.5, abs=0.1)
    assert "growth_uneven" in out["notes"]


def test_growth_range_needs_at_least_two_yearly_changes():
    c = make_company(ticker="TWO", years=make_years((100, 130), (10, 13), (1, 1)))
    out = analyze("TWO", world(companies={"TWO": c}))
    assert out["growth_range"] is None and "growth_uneven" not in out["notes"]


def test_estimated_interest_is_reported_to_the_page():
    c = make_company(ticker="EST", interest_estimated=True)
    assert "interest_estimated" in analyze("EST", world(companies={"EST": c}))["notes"]
    assert "interest_estimated" not in analyze("ACME", world())["notes"]


def test_currency_without_a_table_rate_is_flagged_as_a_generic_risk_free_rate():
    zar = make_company(ticker="ZA", trading_currency="ZAR", statement_currency="ZAR")
    out = analyze("ZA", FakeProvider({"ZA": zar}))
    assert "risk_free_generic" in out["notes"] and out["suggested"]["risk_free_source"] == "generic"
    jp = make_company(ticker="JP", trading_currency="JPY", statement_currency="JPY")
    tabled = analyze("JP", FakeProvider({"JP": jp}, risk_free={"JPY": 1.5}))
    assert "risk_free_generic" not in tabled["notes"] and tabled["suggested"]["risk_free_source"] == "default"
    assert "risk_free_generic" not in analyze("ACME", world())["notes"]


@pytest.mark.parametrize("beta", [-0.4, 0.0, 0.29, 3.01, 5.0])
def test_unreliable_beta_is_replaced_by_the_market_beta_and_flagged(beta):
    out = analyze("BET", world(companies={"BET": make_company(ticker="BET", beta=beta)}))
    assert "beta_unreliable" in out["notes"]
    assert out["suggested"]["wacc_breakdown"]["beta"] == 1.0 and out["suggested"]["beta_reported"] == beta


@pytest.mark.parametrize("beta", [0.3, 0.8, 1.0, 3.0])
def test_plausible_betas_are_kept(beta):
    out = analyze("BET", world(companies={"BET": make_company(ticker="BET", beta=beta)}))
    assert "beta_unreliable" not in out["notes"]
    assert out["suggested"]["wacc_breakdown"]["beta"] == beta and out["suggested"]["beta_reported"] == beta


def test_missing_beta_is_reported_as_missing_not_unreliable():
    out = analyze("BET", world(companies={"BET": make_company(ticker="BET", beta=None)}))
    assert "beta_missing" in out["notes"] and "beta_unreliable" not in out["notes"]
    assert out["suggested"]["beta_reported"] is None and out["suggested"]["wacc_breakdown"]["beta"] == 1.0
