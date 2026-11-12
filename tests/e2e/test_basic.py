import re

import pytest

from tests.e2e.conftest import search

pytestmark = pytest.mark.e2e


def scenario_values(page):
    page.wait_for_selector("#scen .scen-card")
    return page.locator("#scen .scen-card b").all_inner_texts()


def test_acme_results_are_shown(page):
    search(page, "ACME")
    page.wait_for_selector("#takeaway .fine")
    assert "ACME Corp" in page.inner_text("#company")
    assert "not financial advice" in page.inner_text("#takeaway").lower()
    values = scenario_values(page)
    assert len(values) == 3 and all(re.match(r"^\$\d", v) for v in values)
    assert page.is_visible("#rng")
    assert "a year" in page.inner_text("#verdict")


def test_horizon_toggle_changes_values(page):
    search(page, "ACME")
    before = scenario_values(page)
    page.click("#pills button[data-n='10']")
    page.wait_for_function(
        "prev => document.querySelector('#scen .scen-card.base b').textContent !== prev", arg=before[1])
    assert scenario_values(page)[1] != before[1]
    assert page.locator("#pills button.on").inner_text() == "10 yr"


def test_euro_company_uses_euro_symbol_everywhere(page):
    search(page, "SAP.DE")
    page.wait_for_selector("#scen .scen-card")
    text = page.inner_text("body")
    assert "€" in text and "$" not in text
    assert "EUR" in page.inner_text("#company")


def test_pound_company_uses_pound_symbol(page):
    search(page, "LSE.L")
    page.wait_for_selector("#scen .scen-card")
    text = page.inner_text("body")
    assert "£" in text and "$" not in text


def test_ticker_in_url_hash_loads_on_reload(page):
    search(page, "acme")
    page.wait_for_selector("#scen .scen-card")
    assert page.evaluate("location.hash") == "#ACME"
    page.reload()
    page.wait_for_selector("#scen .scen-card")
    assert "ACME Corp" in page.inner_text("#company")
