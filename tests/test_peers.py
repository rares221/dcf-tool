import pytest

from dcf.peers import PeerMetrics, metrics_for, peer_median, reading
from tests.helpers import make_company, make_years


def pm(t, g, m, fy, pe, b, cap=100.0):
    return PeerMetrics(t, cap, g, m, fy, pe, b)


PEERS = [pm("NOVA", 10, 24, 3.9, 31, 1.2), pm("ORBT", 12, 18, 3.1, 36, 1.3),
         pm("KSTL", 6, 22, 5.6, 22, 0.9), pm("LMND", 9, 15, 4.8, 25, 1.1)]


def test_medians_match_mockup():
    assert peer_median(PEERS, "growth") == 9.5
    assert peer_median(PEERS, "fcf_margin") == 20
    assert peer_median(PEERS, "fcf_yield") == pytest.approx(4.35)


def test_readings_use_words_and_in_line_band():
    r = reading("growth", 7, 9.5)
    assert r["label"] == "slower" and r["diff_pct"] == pytest.approx(-26, abs=1)
    assert reading("fcf_yield", 4.4, 4.35)["label"] == "in line"
    assert reading("forward_pe", 28, 28)["label"] == "in line"
    assert reading("forward_pe", 40, 28)["label"] == "pricier"
    assert reading("fcf_yield", 6, 4.35)["label"] == "cheaper"
    assert reading("beta", 1.5, 1.1)["label"] == "jumpier"
    assert reading("fcf_margin", 30, 20)["label"] == "higher"


def test_missing_values_are_na_and_market_cap_has_no_label():
    assert reading("growth", None, 9.5)["label"] == "n/a"
    assert reading("growth", 7, None)["label"] == "n/a"
    assert reading("market_cap", 5, 4)["label"] == ""


def test_none_skipped_and_empty_median_is_none():
    rows = [pm("A", None, 20, 4, 25, 1), pm("B", 8, 20, 4, 25, 1)]
    assert peer_median(rows, "growth") == 8
    assert peer_median([], "growth") is None
    assert reading("growth", 7, peer_median([], "growth"))["label"] == "n/a"


def test_metrics_for_computes_from_latest_year():
    c = make_company(years=make_years((80, 100), (10, 20), (1, 2)), market_cap=400.0)
    m = metrics_for(c, market_cap_in_subject_ccy=300.0)
    assert m.growth == pytest.approx(25.0)
    assert m.fcf_margin == pytest.approx(20.0)
    assert m.fcf_yield == pytest.approx(5.0)  # 20 / 400
    assert m.market_cap == 300.0 and m.forward_pe == 28.0 and m.beta == 1.0


def test_metrics_for_handles_missing_inputs():
    c = make_company(years=make_years((100,), (10,), (1,)), market_cap=0.0, forward_pe=None, beta=None)
    m = metrics_for(c, 0.0)
    assert m.growth is None and m.fcf_yield is None and m.forward_pe is None and m.beta is None
