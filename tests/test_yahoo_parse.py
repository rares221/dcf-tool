import copy
import json
from pathlib import Path

import pytest

from dcf.data.cache import SqliteCache
from dcf.data.provider import ProviderError
from dcf.data.yahoo import YahooProvider, parse_company

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / f"yahoo_{name}.json").read_text(encoding="utf-8"))


def test_us_company():
    raw = load("us")
    c = parse_company(raw)
    assert c.trading_currency == c.statement_currency == "USD"
    assert c.price == raw["info"]["currentPrice"]
    assert len(c.years) == 4
    assert [y.year for y in c.years] == sorted(y.year for y in c.years)
    assert all(y.revenue > 0 and y.fcf > 0 and y.sbc > 0 for y in c.years)
    assert c.shares > 0 and c.market_cap > 0 and c.cash > 0 and c.debt > 0
    assert 5 < c.tax_rate < 40  # fraction in the feed, percent here
    assert c.beta == raw["info"]["beta"]


def test_adr_statements_in_different_currency():
    c = parse_company(load("adr"))
    assert c.trading_currency == "USD" and c.statement_currency == "TWD"


def test_london_listing_prices_in_pounds_not_pence():
    raw = load("london")
    c = parse_company(raw)
    assert raw["info"]["currency"] == "GBp"
    assert c.trading_currency == "GBP"
    assert c.price == pytest.approx(raw["info"]["currentPrice"] / 100)
    assert c.statement_currency == "EUR"
    # market cap is already in main-unit currency in the feed: price(GBP) x shares
    assert c.market_cap == pytest.approx(c.price * c.shares, rel=0.01)


def test_german_listing_in_euros():
    c = parse_company(load("german"))
    assert c.trading_currency == c.statement_currency == "EUR"


def test_bank_industry_is_carried_through():
    assert "Bank" in parse_company(load("bank")).industry


def test_loss_maker_has_negative_fcf_and_no_forward_pe():
    c = parse_company(load("lossmaker"))
    assert all(y.fcf < 0 for y in c.years)
    assert c.forward_pe is None  # negative forward P/E is meaningless


def test_share_count_growth_from_diluted_average_shares():
    assert parse_company(load("us")).share_growth == pytest.approx(-2.35, abs=0.1)   # buybacks
    assert parse_company(load("lossmaker")).share_growth > 5                          # heavy dilution
    assert parse_company(load("adr")).share_growth == pytest.approx(0.0, abs=0.01)


def test_share_growth_is_none_without_share_rows():
    raw = copy.deepcopy(load("us"))
    del raw["income"]["Diluted Average Shares"]
    del raw["income"]["Basic Average Shares"]
    assert parse_company(raw).share_growth is None


def test_missing_rows_become_defaults_not_errors():
    raw = copy.deepcopy(load("us"))
    del raw["cashflow"]["Stock Based Compensation"]
    del raw["info"]["beta"]
    del raw["income"]["Interest Expense"]
    del raw["income"]["Tax Rate For Calcs"]
    c = parse_company(raw)
    assert all(y.sbc == 0.0 for y in c.years)
    assert c.beta is None and c.interest_expense is None and c.tax_rate is None


def test_fcf_falls_back_to_operating_cash_flow_plus_capex():
    raw = copy.deepcopy(load("us"))
    del raw["cashflow"]["Free Cash Flow"]
    c = parse_company(raw)
    ocf, capex = raw["cashflow"]["Operating Cash Flow"], raw["cashflow"]["Capital Expenditure"]
    last = str(c.years[-1].year)
    assert c.years[-1].fcf == pytest.approx(ocf[last] + capex[last])


def test_no_price_is_an_error():
    raw = copy.deepcopy(load("us"))
    for k in ("currentPrice", "regularMarketPrice", "previousClose"):
        raw["info"].pop(k, None)
    with pytest.raises(ValueError):
        parse_company(raw)


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


def make_provider(fetch, clock=None):
    clock = clock or Clock()
    return YahooProvider(SqliteCache(":memory:", ttl_seconds=100, clock=clock), fetch=fetch), clock


def test_fetch_company_caches_within_ttl():
    calls = []
    provider, _ = make_provider(lambda t: calls.append(t) or load("us"))
    provider.fetch_company("AAPL")
    c = provider.fetch_company("AAPL")
    assert calls == ["AAPL"] and not c.stale


def test_stale_cache_served_when_live_fetch_fails():
    state = {"fail": False}

    def fetch(t):
        if state["fail"]:
            raise ProviderError("rate limited")
        return load("us")

    provider, clock = make_provider(fetch)
    provider.fetch_company("AAPL")
    clock.now += 500
    state["fail"] = True
    c = provider.fetch_company("AAPL")
    assert c.stale and c.data_age_seconds == pytest.approx(500)


def test_fetch_raises_without_cache():
    def fetch(t):
        raise ProviderError("down")

    provider, _ = make_provider(fetch)
    with pytest.raises(ProviderError):
        provider.fetch_company("AAPL")


def test_not_found_returns_none_and_is_not_cached():
    provider, _ = make_provider(lambda t: None)
    assert provider.fetch_company("ZZZZZ") is None


def test_fx_rate_same_currency_needs_no_fetch():
    provider = YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None, fx_fetch=lambda s: 1 / 0)
    assert provider.fx_rate("usd", "USD") == 1.0


def test_fx_rate_uses_pair_symbol_and_handles_missing():
    seen = []
    provider = YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None,
                             fx_fetch=lambda s: seen.append(s) or 0.031)
    assert provider.fx_rate("TWD", "USD") == 0.031 and seen == ["TWDUSD=X"]
    none_provider = YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None, fx_fetch=lambda s: None)
    assert none_provider.fx_rate("TWD", "USD") is None


def test_suggest_caps_at_five_and_swallows_errors():
    p = YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None, search=lambda q: list("ABCDEFG"))
    assert p.suggest("x") == list("ABCDE")

    def boom(q):
        raise RuntimeError("x")

    assert YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None, search=boom).suggest("x") == []
