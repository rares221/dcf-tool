"""The assumptions card comes first below the company strip and explains every default, range and reason to change it."""
import re

import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text, set_slider

pytestmark = pytest.mark.e2e


def open_ticker(page, ticker):
    search(page, ticker)
    base_text(page)
    page.wait_for_selector("#assumpCard .arow .facts p")


def row_text(page, key):
    return page.inner_text(f'.arow[data-k="{key}"]').lower()


def test_assumptions_are_the_first_card_below_a_slim_company_strip(page):
    open_ticker(page, "ACME")
    ids = page.evaluate(
        "[...document.querySelectorAll('#main > *')].filter(e => e.id && e.id !== 'statePanel' && e.offsetParent !== null).map(e => e.id)")
    assert ids == ["company", "assumpCard", "takeaway", "scenCard", "whyCard", "impCard", "torCard",
                   "waccCard", "peersCard", "histRow", "sources"]
    assert page.evaluate("document.querySelector('#main .card').id") == "assumpCard"
    assert not page.evaluate("document.getElementById('company').classList.contains('card')")
    assert "ACME Corp" in page.inner_text("#company") and "$168" in page.inner_text("#company")


def test_growth_row_explains_default_range_and_when_to_change(page):
    open_ticker(page, "ACME")
    t = row_text(page, "g")
    for needle in ["our default", "accepted values", "change it if", "from company data",
                   "average yearly revenue growth over the last 3 years (6.8%)", "-10% to 30%", "peers grew 9.5% last year"]:
        assert needle in t, needle


def test_margin_row_shows_how_the_margin_used_is_built(page):
    open_ticker(page, "ACME")
    t = row_text(page, "m")
    for needle in ["last year's free cash flow divided by revenue", "adds back interest (0.8% of revenue)",
                   "subtracts stock pay (3.0% of revenue)", "actually uses 17.8%", "1% to 60%",
                   "17%, 19%, 18%, 20%"]:
        assert needle in t, needle


def test_discount_rate_row_shows_the_build_up_the_limits_and_the_dollar_effect(page):
    open_ticker(page, "ACME")
    t = row_text(page, "w")
    for needle in ["4.3% risk-free rate", "beta (1.0)", "4.5% risk premium", "is a default", "partly an assumption",
                   "5% to 16%", "at least 1 point above long-term growth"]:
        assert needle in t, needle
    assert re.search(r"1 point moves the base value by about \$\d+", t.replace("$", "$"))


def test_long_term_growth_row_states_the_cap_for_the_currency(page):
    open_ticker(page, "ACME")
    t = row_text(page, "t")
    assert "0% to 4%" in t and "never above the risk-free rate (4.3%" in t and "our assumption" in t
    search(page, "NIPPON")
    page.wait_for_function("document.getElementById('company').textContent.includes('Nihon')")
    base_text(page)
    t = row_text(page, "t")
    assert "0% to 1.5%" in t and "risk-free rate (1.5%" in t


def test_stock_pay_row_explains_the_choice_and_its_effect(page):
    open_ticker(page, "ACME")
    t = row_text(page, "s")
    assert "counted as a cost" in t and "pays about 3.0% of revenue in shares" in t
    assert re.search(r"ignoring it would add about \$\d+\.\d\d a share", t)


def test_changed_values_are_marked_with_their_default_and_counted(page):
    open_ticker(page, "ACME")
    assert page.inner_text("#gw") == "" and not page.is_visible("#edited")
    set_slider(page, "g", 15)
    page.wait_for_function("document.getElementById('gw').textContent !== ''")
    assert page.inner_text("#gw") == "You changed this (default: 7%)"
    assert page.inner_text("#edited") == "1 changed"
    page.click("#sbcSeg button[data-v='0']")
    page.wait_for_function("document.getElementById('edited').textContent === '2 changed'")
    assert "counted as a cost" in page.inner_text("#sw")
    page.click("#reset")
    page.wait_for_function("document.getElementById('gw').textContent === ''")
    assert not page.is_visible("#edited") and page.inner_text("#sw") == ""


def test_live_summary_shows_base_range_and_price_and_follows_the_sliders(page):
    open_ticker(page, "ACME")
    live = page.inner_text("#live")
    assert re.search(r"Base \$\d+", live) and re.search(r"Range \$[\d.]+ to \$[\d.]+", live) and "Price $168" in live
    set_slider(page, "g", 20)
    page.wait_for_function("(t) => document.getElementById('live').textContent !== t", arg=page.evaluate("document.getElementById('live').textContent"))
    assert page.evaluate("getComputedStyle(document.getElementById('live')).position") == "sticky"


def test_card_explains_how_to_use_it_and_why_the_limits_exist(page):
    open_ticker(page, "ACME")
    t = page.inner_text("#assumpCard")
    for needle in ["Everything below is built from these", "ACME Corp", "one at a time", "About the limits",
                   "Start with the defaults", "what would I have to believe"]:
        assert needle in t, needle


def test_dollar_effect_uses_the_assets_currency(page):
    open_ticker(page, "SAP.DE")
    t = page.inner_text("#assumpCard")
    assert "€" in t and "$" not in t
