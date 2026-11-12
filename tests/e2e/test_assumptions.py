import re

import pytest

from tests.e2e.conftest import search

pytestmark = pytest.mark.e2e


def set_slider(page, sid, value):
    page.eval_on_selector(
        f"#{sid}", "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", str(value))


def base_text(page):
    page.wait_for_selector("#scen .scen-card.base b")
    return page.inner_text("#scen .scen-card.base b")


def number(text):
    return float(re.sub(r"[^\d.\-]", "", text))


def wait_base_change(page, previous):
    page.wait_for_function(
        "prev => { const e = document.querySelector('#scen .scen-card.base b'); return e && e.textContent !== prev; }",
        arg=previous)


@pytest.fixture
def acme(page):
    search(page, "ACME")
    base_text(page)
    return page


def test_growth_slider_changes_base_value(acme):
    before = number(base_text(acme))
    set_slider(acme, "g", 15)
    wait_base_change(acme, f"${int(before)}")
    assert number(base_text(acme)) > before
    assert acme.inner_text("#gv") == "15%"


def test_reset_button_and_edited_tag(acme):
    assert acme.is_disabled("#reset") and not acme.is_visible("#edited")
    original = base_text(acme)
    set_slider(acme, "g", 15)
    acme.wait_for_selector("#edited", state="visible")
    assert not acme.is_disabled("#reset")
    acme.click("#reset")
    acme.wait_for_function("document.getElementById('g').value === '7'")
    acme.wait_for_function("(t) => document.querySelector('#scen .scen-card.base b').textContent === t", arg=original)
    assert acme.is_disabled("#reset") and not acme.is_visible("#edited")


def test_ignoring_stock_pay_raises_value_and_updates_margin_line(acme):
    before = number(base_text(acme))
    assert "17.8%" in acme.inner_text("#mEff")  # 20.0 reported + 0.8 interest add-back - 3.0 stock pay
    acme.click("#sbcSeg button[data-v='0']")
    acme.wait_for_function("document.getElementById('mEff').textContent.includes('ignored')")
    assert number(base_text(acme)) > before
    assert "20.8%" in acme.inner_text("#mEff")


def test_use_implied_growth_sets_slider(acme):
    acme.wait_for_selector("#impBig")
    assert re.match(r"^14\.1% a year", acme.inner_text("#impBig"))
    acme.click("#setImp")
    acme.wait_for_function("document.getElementById('g').value === '14'")


def test_reverse_dcf_card_content(acme):
    acme.wait_for_selector("#impCmp .t")
    rows = acme.locator("#impCmp > span:nth-child(3n+1)").all_inner_texts()
    assert rows == ["Implied by price", "Your base assumption", "ACME Corp, last 3 years", "Peer median"]
    assert "faster than it has recently" in acme.inner_text("#impNote")


def test_sensitivity_bars_show_currency_amounts(acme):
    acme.wait_for_selector("#tor .t")
    assert acme.locator("#tor .t").count() == 4
    labels = acme.locator("#tor .t em").all_inner_texts()
    assert len(labels) == 8 and all(re.match(r"^\$\d", t) for t in labels)


def test_wacc_explainer_is_live_and_in_currency(acme):
    acme.wait_for_selector("#wPV:not(:empty)")
    assert re.search(r"^\$100 received in 5 years is worth about \$\d+\.\d\d today at a 8\.6% discount rate", acme.inner_text("#wPV"))
    assert "8.6%" in acme.inner_text("#waccCalc")
    assert "1 point" in acme.inner_text("#waccSens")
    acme.click("#pills button[data-n='10']")
    acme.wait_for_function("document.getElementById('wPV').textContent.includes('10 years')")


def test_extreme_slider_values_never_cause_a_bad_request(page):
    statuses = []
    page.on("response", lambda r: statuses.append(r.status) if "/api/model" in r.url else None)
    search(page, "ACME")
    base_text(page)
    set_slider(page, "t", 4)
    set_slider(page, "w", 5)
    set_slider(page, "g", 30)
    set_slider(page, "m", 60)
    page.wait_for_timeout(600)
    assert statuses and set(statuses) == {200}


def test_rapid_slider_events_show_only_the_newest_result(page):
    # Hold every model request, then release them newest-first so the oldest response arrives last.
    # A page that did not drop superseded responses would end up showing the oldest result.
    held = []
    search(page, "ACME")
    base_text(page)
    page.route("**/api/model", lambda route: held.append(route))
    for g in range(1, 21):
        set_slider(page, "g", g)
        page.wait_for_timeout(30)
    page.wait_for_timeout(300)
    assert len(held) >= 2
    for route in reversed(held):
        route.continue_()
    page.wait_for_timeout(1500)
    expected = page.request.post(page.url.split("#")[0] + "api/model", data={
        "ticker": "ACME", "horizon": 5, "growth": 20, "fcf_margin": 20, "wacc": 8.6,
        "terminal_growth": 2.5, "count_sbc": True}).json()["scenarios"]["base"]
    assert page.inner_text("#gv") == "20%"
    assert number(base_text(page)) == round(expected)


def test_margin_line_explains_the_interest_addback(acme):
    line = acme.inner_text("#mEff")
    assert "interest add-back" in line and "reported 20.0%" in line and "stock pay" in line
