from dcf.data.finnhub import fetch_peers


class Resp:
    def __init__(self, payload, status=200, bad_json=False):
        self._p, self.status_code, self._bad = payload, status, bad_json

    def json(self):
        if self._bad:
            raise ValueError("bad json")
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_self_removed_and_capped_at_five():
    resp = Resp(["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"])
    assert fetch_peers("AAPL", "key", get=lambda *a, **k: resp) == ["MSFT", "GOOGL", "AMZN", "META", "NVDA"]


def test_no_key_returns_empty_without_calling():
    def get(*a, **k):
        raise AssertionError("must not be called")

    assert fetch_peers("AAPL", None, get=get) == []


def test_http_error_and_bad_json_return_empty():
    assert fetch_peers("AAPL", "k", get=lambda *a, **k: Resp([], status=429)) == []
    assert fetch_peers("AAPL", "k", get=lambda *a, **k: Resp(None, bad_json=True)) == []
    assert fetch_peers("AAPL", "k", get=lambda *a, **k: Resp({"error": "x"})) == []
