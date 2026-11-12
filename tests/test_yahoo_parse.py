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


def test_multi_class_company_shares_follow_market_cap_not_one_share_class():
    # Alphabet: Yahoo reports ~5.9B shares for one class while market cap covers all classes (~12.3B shares).
    c = parse_company(load("multiclass"))
    assert c.shares == pytest.approx(c.market_cap / c.price, rel=0.001)
    assert c.shares > 1.2e10


def test_reported_shares_kept_when_consistent_with_market_cap():
    raw = load("us")
    c = parse_company(raw)
    assert c.shares == raw["info"]["sharesOutstanding"]


def test_long_term_investments_are_read_from_the_balance_sheet():
    # Apple: 80.21B of non-current marketable securities, separate from the 56.72B of cash and short-term investments.
    us = parse_company(load("us"))
    assert us.long_term_investments == pytest.approx(80.21e9, rel=0.001)
    assert us.cash == pytest.approx(56.72e9, rel=0.001)
    assert parse_company(load("multiclass")).long_term_investments == pytest.approx(68.69e9, rel=0.001)


def test_missing_long_term_investments_row_means_zero():
    raw = copy.deepcopy(load("us"))
    for label in ("Investments And Advances", "Available For Sale Securities", "Investmentin Financial Assets"):
        raw["balance"].pop(label, None)
    assert parse_company(raw).long_term_investments == 0.0


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


# ---------- fetch_raw error mapping (stubbed yfinance.Ticker) ----------

def _frame(label="Total Revenue"):
    import pandas as pd

    return pd.DataFrame({pd.Timestamp("2025-12-31"): {label: 100.0}, pd.Timestamp("2024-12-31"): {label: 90.0}})


def _empty():
    import pandas as pd

    return pd.DataFrame()


class StubTicker:
    def __init__(self, info, income=None, cashflow=None, balance=None):
        self.info = info
        self.income_stmt = _empty() if income is None else income
        self.cashflow = _empty() if cashflow is None else cashflow
        self.balance_sheet = _empty() if balance is None else balance


PRICED = {"currentPrice": 10.0, "currency": "USD"}


def test_equity_with_all_statements_empty_is_treated_as_a_failed_fetch():
    from dcf.data.yahoo import fetch_raw

    stub = StubTicker({**PRICED, "quoteType": "EQUITY"})
    with pytest.raises(ProviderError):
        fetch_raw("X", ticker_factory=lambda t: stub)


def test_equity_missing_balance_sheet_is_treated_as_a_failed_fetch():
    from dcf.data.yahoo import fetch_raw

    stub = StubTicker({**PRICED, "quoteType": "EQUITY"}, income=_frame(), cashflow=_frame("Free Cash Flow"))
    with pytest.raises(ProviderError):
        fetch_raw("X", ticker_factory=lambda t: stub)


def test_etf_without_statements_is_a_normal_payload():
    from dcf.data.yahoo import fetch_raw

    raw = fetch_raw("SPY", ticker_factory=lambda t: StubTicker({**PRICED, "quoteType": "ETF"}))
    assert raw is not None and raw["income"] == {}


def test_complete_equity_payload_is_returned():
    from dcf.data.yahoo import fetch_raw

    stub = StubTicker({**PRICED, "quoteType": "EQUITY"}, income=_frame(), cashflow=_frame("Free Cash Flow"),
                      balance=_frame("Total Debt"))
    raw = fetch_raw("X", ticker_factory=lambda t: stub)
    assert raw["income"]["Total Revenue"]["2025"] == 100.0


def test_info_without_price_is_not_found():
    from dcf.data.yahoo import fetch_raw

    assert fetch_raw("X", ticker_factory=lambda t: StubTicker({"quoteType": "EQUITY"})) is None


def test_incomplete_fetch_is_not_cached_so_retry_reaches_the_source():
    calls = []

    def fetch(t):
        calls.append(t)
        raise ProviderError("incomplete")

    provider, _ = make_provider(fetch)
    for _ in range(2):
        with pytest.raises(ProviderError):
            provider.fetch_company("AAPL")
    assert calls == ["AAPL", "AAPL"]


def test_stale_cache_served_when_live_lookup_claims_not_found():
    # yfinance swallows some HTTP errors and returns info without a price, which looks like "not found".
    state = {"missing": False}
    provider, clock = make_provider(lambda t: None if state["missing"] else load("us"))
    provider.fetch_company("AAPL")
    clock.now += 500
    state["missing"] = True
    c = provider.fetch_company("AAPL")
    assert c is not None and c.stale and c.data_age_seconds == pytest.approx(500)


def test_fx_rate_is_cached_between_calls():
    calls = []
    provider = YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None,
                             fx_fetch=lambda s: calls.append(s) or 0.031)
    assert [provider.fx_rate("TWD", "USD") for _ in range(5)] == [0.031] * 5
    assert calls == ["TWDUSD=X"]


def test_fx_rate_falls_back_to_stale_value_when_source_fails():
    clock = Clock()
    state = {"fail": False}

    def fx(symbol):
        if state["fail"]:
            raise RuntimeError("down")
        return 0.031

    provider = YahooProvider(SqliteCache(":memory:", ttl_seconds=100, clock=clock), fetch=lambda t: None, fx_fetch=fx)
    provider.fx_rate("TWD", "USD")
    clock.now += 500
    state["fail"] = True
    assert provider.fx_rate("TWD", "USD") == 0.031


def test_fx_rate_is_none_when_source_fails_and_nothing_cached():
    def fx(symbol):
        raise RuntimeError("down")

    provider = YahooProvider(SqliteCache(":memory:"), fetch=lambda t: None, fx_fetch=fx)
    assert provider.fx_rate("TWD", "USD") is None


# ---------- bad provider values ----------

def test_missing_price_currency_is_an_error_not_a_guessed_dollar():
    raw = copy.deepcopy(load("german"))
    del raw["info"]["currency"]
    with pytest.raises(ValueError):
        parse_company(raw)


def test_fetch_treats_missing_currency_as_a_failed_fetch():
    from dcf.data.yahoo import fetch_raw

    stub = StubTicker({"currentPrice": 10.0, "quoteType": "EQUITY"}, income=_frame(),
                      cashflow=_frame("Free Cash Flow"), balance=_frame("Total Debt"))
    with pytest.raises(ProviderError):
        fetch_raw("X", ticker_factory=lambda t: stub)


def test_nan_numbers_from_the_provider_become_missing_values():
    raw = copy.deepcopy(load("us"))
    raw["info"]["beta"] = float("nan")
    raw["info"]["forwardPE"] = float("inf")
    raw["info"]["marketCap"] = float("nan")
    c = parse_company(raw)
    assert c.beta is None and c.forward_pe is None
    assert c.market_cap == pytest.approx(c.shares * c.price, rel=0.001)  # derived, not NaN


def test_nan_price_is_treated_as_no_price():
    raw = copy.deepcopy(load("us"))
    for k in ("currentPrice", "regularMarketPrice", "previousClose"):
        raw["info"][k] = float("nan")
    with pytest.raises(ValueError):
        parse_company(raw)
