import re

import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text

pytestmark = pytest.mark.e2e

DISCLAIMER = "not financial advice"


def test_unknown_ticker_shows_suggestions_and_nothing_else(page):
    search(page, "ACMX")
    page.wait_for_selector("#blocker .card")
    text = page.inner_text("#blocker")
    assert "couldn't find" in text.lower() and "ACMX" in text and ".DE" in text
    assert not page.is_visible("#main")
    page.click("#blocker .chip:has-text('ACME')")
    page.wait_for_selector("#company", state="visible")
    assert "ACME Corp" in page.inner_text("#company")


def test_invalid_ticker_is_treated_as_not_found(page):
    search(page, "<script>")
    page.wait_for_selector("#blocker .card")
    assert "couldn't find" in page.inner_text("#blocker").lower()


@pytest.mark.parametrize("ticker,phrase", [("BANK", "different model"), ("LOSS", "negative free cash flow"),
                                           ("THIN", "not enough"), ("NOSH", "share count")])
def test_declined_companies_explain_why_but_keep_track_record_and_peers(page, ticker, phrase):
    search(page, ticker)
    page.wait_for_selector("#statePanel .card")
    assert phrase in page.inner_text("#statePanel").lower()
    assert page.is_visible("#company") and page.is_visible("#peersCard") and page.is_visible("#histCard")
    assert page.locator("#hist .col").count() >= 1
    assert not page.is_visible("#scenCard") and not page.is_visible("#takeaway") and not page.is_visible("#impCard")
    assert not re.search(r"\$\d", page.inner_text("#scen"))
    assert DISCLAIMER in page.inner_text("body").lower()


def test_non_us_banner_names_the_currency(page):
    search(page, "SAP.DE")
    page.wait_for_selector("#banners .banner")
    assert "EUR" in page.inner_text("#banners")
    banner = page.inner_text("#banners").lower()
    assert "discount rate slider" in banner  # the only editable control that these defaults feed
    assert "you can edit" not in banner      # the risk-free rate and risk premium themselves are not editable
    assert DISCLAIMER in page.inner_text("body").lower()
    assert page.is_visible("#scenCard")


def test_stale_banner_and_results_still_shown(page):
    search(page, "STALE")
    page.wait_for_selector("#banners .banner")
    text = page.inner_text("#banners").lower()
    assert "may be old" in text and "days ago" in text
    base_text(page)
    assert DISCLAIMER in page.inner_text("body").lower()


def test_partial_banner_lists_what_is_missing(page):
    search(page, "PART")
    page.wait_for_selector("#banners .banner")
    text = page.inner_text("#banners").lower()
    assert "missing" in text and "beta" in text and "rougher" in text
    base_text(page)
    assert DISCLAIMER in page.inner_text("body").lower()


def test_clamped_suggestions_are_announced(page):
    search(page, "WILD")
    page.wait_for_selector("#banners .banner")
    text = page.inner_text("#banners").lower()
    assert "outside" in text and "growth" in text and "margin" in text
    assert page.input_value("#g") == "30" and page.input_value("#m") == "60"


def test_adr_shows_fx_note_with_both_currencies_and_rate(page):
    search(page, "ADR")
    page.wait_for_selector("#banners .banner")
    text = page.inner_text("#banners")
    assert "TWD" in text and "USD" in text
    assert "0.03101" in text and "0.0310123" not in text  # rate shown to 4 significant digits
    base_text(page)


def test_missing_exchange_rate_blocks_with_message_and_no_values(page):
    search(page, "NOFX")
    page.wait_for_selector("#blocker .card")
    text = page.inner_text("#blocker")
    assert "JPY" in text and "USD" in text
    assert not page.is_visible("#main")
    assert not re.search(r"\$\d", page.inner_text("body").replace("USD", ""))


def test_provider_error_is_friendly_with_retry_and_no_stack_trace(page):
    search(page, "DOWN")
    page.wait_for_selector("#blocker .card")
    text = page.inner_text("#blocker")
    assert "try again" in text.lower()
    assert "Traceback" not in text and "simulated" not in text and "Error:" not in text
    page.click("#blocker button:has-text('Retry')")
    page.wait_for_selector("#blocker .card")
    assert "try again" in page.inner_text("#blocker").lower()


def test_loading_skeleton_appears_while_request_is_pending(page):
    held = []
    page.route("**/api/analyze**", lambda route: held.append(route))
    search(page, "ACME")
    page.wait_for_selector("#blocker .sk")
    assert not page.is_visible("#main")
    held[0].continue_()
    base_text(page)
    assert page.locator("#blocker .sk").count() == 0


# ---------- phone width ----------

@pytest.fixture
def phone(browser, base_url):
    ctx = browser.new_context(locale="en-US", viewport={"width": 390, "height": 780}, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    pg.goto(base_url)
    search(pg, "ACME")
    base_text(pg)
    pg.wait_for_selector("#peers th")
    yield pg
    ctx.close()


def test_phone_has_no_horizontal_page_scroll(phone):
    assert phone.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_phone_slider_rows_stack(phone):
    row = phone.locator("#assumpCard .sl").first
    label = row.locator("label").bounding_box()
    slider = row.locator("input").bounding_box()
    assert slider["y"] >= label["y"] + label["height"] - 1


def test_phone_sources_table_stacks_each_input_into_a_block(phone):
    row = phone.locator("#sources tr:nth-child(2)")
    cells = [row.locator("td").nth(i).bounding_box() for i in range(3)]
    assert cells[1]["y"] > cells[0]["y"] and cells[2]["y"] > cells[1]["y"]   # stacked, not side by side
    assert all(c["width"] > 250 for c in cells)
    assert phone.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_phone_track_record_is_two_columns(phone):
    boxes = [phone.locator("#hist .col").nth(i).bounding_box() for i in range(4)]
    assert abs(boxes[0]["y"] - boxes[1]["y"]) < 2 and boxes[2]["y"] > boxes[0]["y"] + 20
    assert boxes[1]["x"] > boxes[0]["x"]


def test_phone_peer_table_scrolls_inside_container_with_first_column_pinned(phone):
    box = phone.locator("#peersCard .scroll")
    assert box.evaluate("el => el.scrollWidth > el.clientWidth")
    box.evaluate("el => { el.scrollLeft = el.scrollWidth; }")
    container = box.bounding_box()
    first = phone.locator("#peers tr:nth-child(2) td:first-child").bounding_box()
    assert first["x"] >= container["x"] - 1 and first["x"] <= container["x"] + 20
    assert phone.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_value_of_zero_per_share_is_explained(page):
    search(page, "DEBT")
    page.wait_for_selector("#scen .scen-card")
    values = page.locator("#scen .scen-card b").all_inner_texts()
    assert all(v == "$0.00" for v in values)
    note = page.inner_text("#verdict").lower()
    assert "zero" in note and "debt" in note
    assert "-100" not in page.inner_text("#verdict")
