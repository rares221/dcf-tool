import pytest
from fastapi.testclient import TestClient

from dcf.api import create_app
from dcf.data.fake import FakeProvider
from dcf.settings import Settings, build_provider, load_settings
from tests.helpers import make_company

MODEL_BODY = {"ticker": "ACME", "horizon": 5, "growth": 7, "fcf_margin": 20, "wacc": 8.6,
              "terminal_growth": 2.5, "count_sbc": True}


def client(**provider_kwargs):
    provider = FakeProvider({"ACME": make_company()}, **provider_kwargs)
    return TestClient(create_app(provider))


def test_analyze_returns_documented_keys():
    r = client().get("/api/analyze", params={"ticker": "acme"})
    assert r.status_code == 200
    body = r.json()
    assert {"status", "notes", "suggestions", "company", "history", "history_cagr", "suggested", "limits",
            "base", "peers", "data_age_seconds", "fx"} <= set(body)
    assert body["status"] == "ok"


def test_analyze_unknown_ticker_is_200_not_found():
    r = client().get("/api/analyze", params={"ticker": "NOPE"})
    assert r.status_code == 200 and r.json()["status"] == "not_found"


def test_analyze_peers_param_overrides_and_empty_means_none():
    c = TestClient(create_app(FakeProvider({"ACME": make_company(), "B": make_company(ticker="B")},
                                           peers={"ACME": ["B"]})))
    assert len(c.get("/api/analyze", params={"ticker": "ACME"}).json()["peers"]["rows"]) == 2
    assert len(c.get("/api/analyze", params={"ticker": "ACME", "peers": ""}).json()["peers"]["rows"]) == 1


def test_model_returns_documented_keys():
    r = client().post("/api/model", json=MODEL_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {"scenarios", "terminal_share", "position", "implied_return", "implied_growth", "sensitivity",
            "sbc_effect", "pv_of_100"} <= set(body)


def test_model_unknown_ticker_is_200_not_found():
    r = client().post("/api/model", json={**MODEL_BODY, "ticker": "NOPE"})
    assert r.status_code == 200 and r.json() == {"status": "not_found"}


@pytest.mark.parametrize("override", [
    {"wacc": 3, "terminal_growth": 4},      # discount rate not above long-term growth
    {"wacc": 5, "terminal_growth": 4.5},    # outside limit and too close
    {"wacc": 3.5, "terminal_growth": 2.5},  # less than 1 point above long-term growth
    {"horizon": 7},
    {"growth": 99},
    {"fcf_margin": 0},
])
def test_model_rejects_invalid_values_with_422(override):
    assert client().post("/api/model", json={**MODEL_BODY, **override}).status_code == 422


def test_provider_outage_is_designed_error_not_traceback():
    r = client(errors={"ACME"}).get("/api/analyze", params={"ticker": "ACME"})
    assert r.status_code == 200 and r.json()["status"] == "error"
    assert "Traceback" not in r.text and "simulated" not in r.text
    m = client(errors={"ACME"}).post("/api/model", json=MODEL_BODY)
    assert m.status_code == 200 and m.json()["status"] == "error"


def test_unexpected_provider_bug_still_returns_error_status():
    class Broken(FakeProvider):
        def fetch_company(self, ticker):
            raise RuntimeError("boom")

    c = TestClient(create_app(Broken({})), raise_server_exceptions=False)
    r = c.get("/api/analyze", params={"ticker": "ACME"})
    assert r.status_code == 200 and r.json()["status"] == "error" and "boom" not in r.text


def test_index_served_as_html():
    r = client().get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_settings_from_env_and_fake_provider(tmp_path):
    s = load_settings({"FRED_API_KEY": "f", "FINNHUB_API_KEY": "h", "DCF_PROVIDER": "fake",
                       "DCF_FAKE_WORLD": "w.json", "DCF_CACHE_PATH": "c.sqlite"})
    assert s == Settings(fred_key="f", finnhub_key="h", cache_path="c.sqlite", provider="fake", fake_world="w.json")
    assert load_settings({}).provider == "live" and load_settings({}).fred_key is None

    import json
    d = {k: v for k, v in make_company().__dict__.items() if k != "years"}
    d["years"] = [y.__dict__ for y in make_company().years]
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"companies": {"ACME": d}}), encoding="utf-8")
    p = build_provider(Settings(None, None, ":memory:", "fake", str(path)))
    assert p.fetch_company("ACME").price == 168.0


@pytest.mark.parametrize("path,expected", [("/static/app.js", "javascript"), ("/static/styles.css", "text/css")])
def test_static_assets_have_browser_safe_content_types(path, expected):
    # Windows registries can map .js to text/plain, which browsers refuse for module scripts.
    r = client().get(path)
    assert r.status_code == 200 and expected in r.headers["content-type"]
