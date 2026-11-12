import pytest

from dcf.data.provider import RateResult
from dcf.data.rates import DEFAULT_RISK_FREE, fetch_fred_10y, risk_free_rate


class Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_fred_skips_missing_observations():
    payload = {"observations": [{"date": "2026-11-11", "value": "."}, {"date": "2026-11-10", "value": "4.21"}]}
    r = fetch_fred_10y("key", get=lambda *a, **k: Resp(payload))
    assert r == RateResult(4.21, "fred", "2026-11-10")


def test_fred_with_no_usable_observation_raises():
    with pytest.raises(ValueError):
        fetch_fred_10y("key", get=lambda *a, **k: Resp({"observations": [{"date": "d", "value": "."}]}))


def test_usd_with_key_uses_fred():
    r = risk_free_rate("USD", "key", fetch=lambda key: RateResult(4.2, "fred", "2026-11-10"))
    assert r.source == "fred" and r.rate_pct == 4.2


def test_usd_falls_back_to_default_when_fred_fails():
    def boom(key):
        raise RuntimeError("down")

    r = risk_free_rate("USD", "key", fetch=boom)
    assert r.source == "default" and r.rate_pct == DEFAULT_RISK_FREE["USD"]


def test_usd_without_key_uses_default():
    assert risk_free_rate("USD", None, fetch=lambda k: 1 / 0).source == "default"


def test_other_currencies_use_default_table():
    r = risk_free_rate("EUR", "key", fetch=lambda k: 1 / 0)
    assert r.source == "default" and r.rate_pct == DEFAULT_RISK_FREE["EUR"]


def test_unknown_currency_uses_the_generic_default_and_says_so():
    r = risk_free_rate("BRL", None)
    assert r.rate_pct == DEFAULT_RISK_FREE["OTHER"] and r.source == "generic"   # distinct from a labelled table default
    assert risk_free_rate("EUR", None).source == "default"
