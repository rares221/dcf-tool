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
    for bad in ("", "   ", "<script>", "A" * 16, "ap pl", "AAPL;DROP"):
        assert normalise_ticker(bad) is None


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


def test_requested_peers_override_suggested_peers():
    out = analyze("ACME", world(), peer_tickers=["ORBT"])
    assert [r["ticker"] for r in out["peers"]["rows"]] == ["ACME", "ORBT"]


ACME_INPUTS = ModelInputs(revenue=100, cash=30, debt=20, shares=2.7, price=168, sbc_pct=3)
BASE = Assumptions(7, 20, 8.6, 2.5)


def test_run_model_matches_reference_values():
    out = run_model(ACME_INPUTS, BASE, 5, True)
    assert out["scenarios"]["base"] == pytest.approx(127.49, abs=0.01)
    assert out["scenarios"]["bear"] == pytest.approx(75.75, abs=0.01)
    assert out["position"] == "upper"
    assert out["implied_growth"] == pytest.approx(15.44, abs=0.01)
    assert out["implied_return"]["base"] == pytest.approx(-5.37, abs=0.01)
    assert out["sbc_effect"] == pytest.approx(21.84, abs=0.02)
    assert out["pv_of_100"] == pytest.approx(66.2, abs=0.1)
    assert out["margin_used"] == pytest.approx(17.0)
    assert {s["key"] for s in out["sensitivity"]} == {"wacc", "growth", "margin", "terminal_growth"}
    assert_finite(out)


def test_margin_used_ignores_stock_pay_when_switched_off():
    assert run_model(ACME_INPUTS, BASE, 5, False)["margin_used"] == pytest.approx(20.0)
    low = run_model(ACME_INPUTS, Assumptions(7, 2, 8.6, 2.5), 5, True)
    assert low["margin_used"] == 0.0


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
