"""The conclusion card ("why the range looks like this"), softer wording, and the implied discount rate."""
import json
import re

import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text

pytestmark = pytest.mark.e2e


def open_ticker(page, ticker):
    search(page, ticker)
    base_text(page)
    page.wait_for_selector("#whyCard li")


def test_price_far_above_the_range_is_described_as_market_optimism_not_a_verdict(page):
    open_ticker(page, "RICH")
    takeaway = page.inner_text("#takeaway")
    assert "more optimistic than your assumptions" in takeaway
    assert "expensive" not in takeaway.lower() and "cheap" not in takeaway.lower()
    assert re.search(r"discount rate of about \d+\.\d% instead of your \d+\.\d%", takeaway)
    verdict = page.inner_text("#verdict")
    assert "more optimistic" in verdict and "expensive" not in verdict.lower()


def test_price_far_below_the_range_is_described_as_market_caution(page):
    open_ticker(page, "CHEAP")
    assert "more cautious than your assumptions" in page.inner_text("#takeaway")
    assert "cheap" not in page.inner_text("#verdict").lower().replace("cheaper", "")


def test_reverse_card_shows_the_discount_rate_the_price_needs(page):
    open_ticker(page, "RICH")
    text = page.inner_text("#impWacc")
    assert re.search(r"would have to be about \d+\.\d%", text)
    assert "risk-free rate is 4.3%" in text and re.search(r"yours: \d+\.\d%", text)
    assert "at or below the risk-free rate" in text  # a price this rich needs less than the risk-free rate


def test_reverse_discount_rate_for_a_cheap_price_is_higher_than_yours(page):
    open_ticker(page, "CHEAP")
    text = page.inner_text("#impWacc")
    assert re.search(r"would have to be about (\d+)\.\d%", text)
    assert "higher than yours" in text


def test_conclusion_card_is_specific_to_the_asset_and_light(page):
    open_ticker(page, "RICH")
    why = page.inner_text("#whyCard")
    assert "why the range looks like this" in why.lower()  # headings are shown in capitals
    assert "not a forecast" in why.lower()
    assert "Richly Valued Inc" in why                       # asset-specific bottom line
    assert re.search(r"about \d+ times", why)               # free cash flow multiple the market pays
    assert "free cash flow" in why.lower()
    assert "moves the answer most" in why
    assert "Bottom line" in why and "more optimistic" in why
    assert 3 <= page.locator("#whyCard li").count() <= 5   # light: a handful of short points


def test_conclusion_card_changes_with_where_the_price_sits(page):
    open_ticker(page, "CHEAP")
    why = page.inner_text("#whyCard")
    assert "Bargain Corp" in why and "more cautious" in why
    open_ticker(page, "ACME")
    assert "pricier" in page.inner_text("#whyCard")


def test_conclusion_card_follows_the_assumptions(page):
    open_ticker(page, "ACME")
    before = page.inner_text("#whyCard")
    page.eval_on_selector("#g", "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", "20")
    page.wait_for_function("(t) => document.getElementById('whyCard').textContent !== t", arg=before)
    assert "20%" in page.inner_text("#whyCard")


def test_conclusion_card_uses_the_assets_currency(page):
    search(page, "SAP.DE")
    base_text(page)
    page.wait_for_selector("#whyCard li")
    why = page.inner_text("#whyCard")
    assert "€" in why and "$" not in why


def test_conclusion_card_is_hidden_when_the_model_call_fails(page):
    page.route("**/api/model", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps({"status": "error"})))
    search(page, "ACME")
    page.wait_for_selector("#takeaway button[data-retry-model]")
    assert not page.is_visible("#whyCard")


def test_growth_note_stresses_a_price_that_needs_more_than_double_recent_growth_even_without_peers(page):
    open_ticker(page, "LONELY")  # no peers available: the note must not understate the gap
    note = page.inner_text("#impNote")
    assert "more than double" in note and "acceleration" not in note
