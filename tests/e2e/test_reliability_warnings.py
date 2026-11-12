"""Warnings for rough discount-rate inputs: generic risk-free rates and unreliable betas."""
import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text

pytestmark = pytest.mark.e2e


def open_ticker(page, ticker):
    search(page, ticker)
    base_text(page)
    page.wait_for_selector("#flags li")


def discount_row(page):
    return page.inner_text('.arow[data-k="w"]').lower()


def test_currency_without_a_rate_gets_a_clear_unreliable_warning(page):
    open_ticker(page, "RAND")
    banners = page.inner_text("#banners").lower()
    for needle in ["generic", "zar", "probably too high", "discount rate yourself"]:
        assert needle in banners, needle
    row = discount_row(page)
    assert "generic assumption" in row and "generic placeholder" in row and "no government bond rate for zar" in row


def test_currencies_with_a_labelled_rate_do_not_get_the_generic_warning(page):
    open_ticker(page, "SAP.DE")
    assert "generic" not in page.inner_text("#banners").lower()
    assert "partly an assumption" in discount_row(page)
    open_ticker(page, "ACME")
    assert "generic" not in page.inner_text("#banners").lower()


def test_absurd_beta_is_explained_and_replaced(page):
    open_ticker(page, "NEGBETA")
    row = discount_row(page)
    assert "looks unreliable" in row and "beta (1.0" in row and "-0.40" in row
    flags = page.inner_text("#flags").lower()
    assert "beta" in flags and "unreliable" in flags and "market beta of 1.0" in flags


def test_a_normal_beta_shows_no_warning(page):
    open_ticker(page, "ACME")
    assert "unreliable" not in discount_row(page) and "unreliable" not in page.inner_text("#flags").lower()
