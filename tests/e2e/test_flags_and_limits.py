"""Heads-up flags for bridge claims, estimated interest and uneven growth; terminal growth capped at the risk-free rate."""
import re

import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text

pytestmark = pytest.mark.e2e


def flags_for(page, ticker):
    search(page, ticker)
    base_text(page)
    page.wait_for_selector("#flags li")
    return page.inner_text("#flags")


def test_minority_interest_flag_is_in_the_assets_currency(page):
    flags = flags_for(page, "SAP.DE")
    assert re.search(r"\u20ac500M of minority interest and preferred stock \(about \u20ac0\.\d\d a share\) is subtracted", flags)
    assert "$" not in flags


def test_no_minority_flag_when_there_are_no_other_claims(page):
    assert "minority interest" not in flags_for(page, "ACME")


def test_estimated_interest_is_flagged(page):
    flags = flags_for(page, "LONELY")
    assert "interest expense was not reported" in flags and "estimated" in flags
    assert "estimated from the last reported interest" not in flags_for(page, "ACME")


def test_uneven_revenue_growth_is_flagged_with_the_range(page):
    flags = flags_for(page, "UNEVEN")
    assert "Revenue growth has been uneven" in flags
    assert re.search(r"ranged from -7\.7% to 30\.0%", flags)
    assert "uneven" not in flags_for(page, "ACME")


def test_terminal_growth_slider_stops_at_the_risk_free_rate(page):
    search(page, "NIPPON")
    base_text(page)
    assert page.get_attribute("#t", "max") == "1.5" and page.input_value("#t") == "1.5"
    search(page, "ACME")
    page.wait_for_function("document.getElementById('company').textContent.includes('ACME Corp')")
    base_text(page)
    assert page.get_attribute("#t", "max") == "4" and page.input_value("#t") == "2.5"
