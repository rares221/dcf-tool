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


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


def cached_provider(monkeypatch, peers_fn, rf_fn, fred_key="fr"):
    from dcf.data.cache import SqliteCache

    clock = Clock()
    cache = SqliteCache(":memory:", ttl_seconds=100, clock=clock)
    monkeypatch.setattr("dcf.data.live.fetch_peers", peers_fn)
    monkeypatch.setattr("dcf.data.live.risk_free_rate", rf_fn)
    return LiveProvider(StubYahoo(), fred_key=fred_key, finnhub_key="fh", cache=cache), clock


def test_peer_lists_are_cached(monkeypatch):
    calls = []
    p, _ = cached_provider(monkeypatch, lambda t, k: calls.append(t) or ["A", "B"], lambda c, k: RateResult(4.0, "default"))
    assert p.peer_tickers("ACME") == ["A", "B"] and p.peer_tickers("ACME") == ["A", "B"]
    assert calls == ["ACME"]


def test_empty_peer_results_are_not_cached_so_a_later_call_can_succeed(monkeypatch):
    calls = []
    p, _ = cached_provider(monkeypatch, lambda t, k: calls.append(t) or [], lambda c, k: RateResult(4.0, "default"))
    p.peer_tickers("ACME")
    p.peer_tickers("ACME")
    assert calls == ["ACME", "ACME"]


def test_old_peer_list_is_used_when_the_source_stops_answering(monkeypatch):
    state = {"down": False}

    def peers(t, k):
        return [] if state["down"] else ["A", "B"]

    p, clock = cached_provider(monkeypatch, peers, lambda c, k: RateResult(4.0, "default"))
    p.peer_tickers("ACME")
    clock.now += 500
    state["down"] = True
    assert p.peer_tickers("ACME") == ["A", "B"]


def test_live_fred_rate_is_cached_but_labelled_defaults_are_not(monkeypatch):
    calls = []

    def rf(cur, key):
        calls.append(cur)
        return RateResult(4.2, "fred", "2026-11-10") if cur == "USD" else RateResult(2.6, "default")

    p, _ = cached_provider(monkeypatch, lambda t, k: [], rf)
    assert p.risk_free_rate("USD") == p.risk_free_rate("USD") == RateResult(4.2, "fred", "2026-11-10")
    p.risk_free_rate("EUR")
    p.risk_free_rate("EUR")
    assert calls == ["USD", "EUR", "EUR"]


def test_old_fred_rate_beats_a_default_when_fred_fails_today(monkeypatch):
    state = {"down": False}

    def rf(cur, key):
        return RateResult(4.3, "default") if state["down"] else RateResult(4.2, "fred", "2026-11-10")

    p, clock = cached_provider(monkeypatch, lambda t, k: [], rf)
    p.risk_free_rate("USD")
    clock.now += 500
    state["down"] = True
    assert p.risk_free_rate("USD").source == "fred"
