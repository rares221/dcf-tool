from dcf.data.live import LiveProvider
from dcf.data.provider import RateResult
from tests.helpers import make_company


class StubYahoo:
    def __init__(self):
        self.calls = []

    def fetch_company(self, t):
        self.calls.append(("fetch_company", t))
        return make_company()

    def fx_rate(self, a, b):
        self.calls.append(("fx_rate", a, b))
        return 0.5

    def suggest(self, q):
        self.calls.append(("suggest", q))
        return ["ACME"]


def test_live_provider_delegates_every_method(monkeypatch):
    yahoo = StubYahoo()
    monkeypatch.setattr("dcf.data.live.fetch_peers", lambda t, key: ["A", "B"] if key == "fh" else [])
    monkeypatch.setattr("dcf.data.live.risk_free_rate", lambda cur, key: RateResult(4.0, "default"))
    p = LiveProvider(yahoo, fred_key="fr", finnhub_key="fh")
    assert p.fetch_company("ACME").ticker == "ACME"
    assert p.fx_rate("EUR", "USD") == 0.5
    assert p.suggest("acm") == ["ACME"]
    assert p.risk_free_rate("USD").rate_pct == 4.0
    assert p.peer_tickers("ACME") == ["A", "B"]
    assert [c[0] for c in yahoo.calls] == ["fetch_company", "fx_rate", "suggest"]
