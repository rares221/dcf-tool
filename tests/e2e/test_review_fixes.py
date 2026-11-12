"""Regression tests for issues found in the whole-branch review."""
import json

import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text

pytestmark = pytest.mark.e2e


def test_failed_model_call_shows_message_with_retry_instead_of_calculating_forever(page):
    def fail(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"status": "error"}))

    page.route("**/api/model", fail)
    search(page, "ACME")
    page.wait_for_selector("#takeaway button[data-retry-model]")
    assert "couldn't recalculate" in page.inner_text("#takeaway").lower()
    assert "Calculating" not in page.inner_text("#main")
    assert not page.is_visible("#impCard") and not page.is_visible("#waccCard") and not page.is_visible("#torCard")
    page.unroute("**/api/model")
    page.click("#takeaway button[data-retry-model]")
    base_text(page)
    assert page.is_visible("#impCard") and page.is_visible("#waccCard")


def test_model_validation_error_body_is_also_handled(page):
    page.route("**/api/model", lambda route: route.fulfill(
        status=422, content_type="application/json", body=json.dumps({"detail": [{"msg": "bad"}]})))
    search(page, "ACME")
    page.wait_for_selector("#takeaway button[data-retry-model]")


def test_declined_company_still_shows_currency_conversion_note(page):
    search(page, "ADRLOSS")
    page.wait_for_selector("#statePanel .card")
    banners = page.inner_text("#banners")
    assert "TWD" in banners and "USD" in banners
    assert "negative free cash flow" in page.inner_text("#statePanel").lower()


def test_late_peer_response_for_previous_company_is_ignored(page):
    held = []
    search(page, "ACME")
    page.wait_for_selector("#peers th")
    page.route("**/api/analyze**", lambda route: held.append(route) if "peers=" in route.request.url else route.continue_())
    page.click("#chips button[aria-label='Remove NOVA']")
    page.wait_for_timeout(200)
    assert len(held) == 1
    search(page, "SAP.DE")
    page.wait_for_function("document.getElementById('company').textContent.includes('Sample Software')")
    held[0].continue_()
    page.wait_for_timeout(800)
    headers = page.locator("#peers tr:first-child th").all_inner_texts()
    assert "ORBT" not in headers and "KSTL" not in headers and "LMND" not in headers
    assert "Sample Software" in page.inner_text("#company")
