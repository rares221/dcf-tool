"""Hits real Yahoo endpoints. Run with: python -m pytest -m network"""
import time

import pytest

from dcf.data.cache import SqliteCache
from dcf.data.yahoo import YahooProvider

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def provider():
    return YahooProvider(SqliteCache(":memory:"))


def test_real_us_ticker_parses(provider):
    c = provider.fetch_company("MSFT")
    assert c is not None and c.trading_currency == "USD" and len(c.years) >= 2 and c.price > 0


def test_nonsense_ticker_is_not_found(provider):
    assert provider.fetch_company("ZZZZQQ9") is None


def test_fx_rate_available(provider):
    rate = provider.fx_rate("EUR", "USD")
    assert rate is not None and 0.5 < rate < 2.5


def test_suggest_finds_something(provider):
    assert provider.suggest("apple")


def test_sequential_lookup_pace(provider, capsys):
    start = time.time()
    for t in ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"):
        provider.fetch_company(t)
    print(f"5 uncached lookups took {time.time() - start:.1f}s")
