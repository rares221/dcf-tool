import re

import pytest

from tests.e2e.conftest import search
from tests.e2e.test_assumptions import base_text, set_slider

pytestmark = pytest.mark.e2e

SPEC_TERMS = ["fcf", "fcfm", "tv", "beta", "erp", "wacc", "ltg", "sbc", "dilution", "impl", "horizon"]


@pytest.fixture
def acme(page):
    search(page, "ACME")
    base_text(page)
    page.wait_for_selector("#peers th")
    return page


def peer_headers(page):
    return page.locator("#peers tr:first-child th").all_inner_texts()


def test_peer_table_has_subject_peers_median_and_word_readings(acme):
    headers = peer_headers(acme)
    assert headers[:6] == ["Metric", "ACME", "NOVA", "ORBT", "KSTL", "LMND"]
    assert "Peer median" in headers and any("vs peers" in h for h in headers)
    text = acme.inner_text("#peers")
    assert "slower" in text  # growth reading is words, not only colour
    assert "$" in text      # market cap row uses the asset currency


def test_peer_note_compares_assumptions_with_peer_median(acme):
    assert re.search(r"growth assumption is 7% against a peer median of 9\.5%", acme.inner_text("#peerNote"))


def test_remove_and_add_peers_updates_table_and_keeps_assumptions(acme):
    set_slider(acme, "g", 12)
    acme.wait_for_selector("#edited", state="visible")
    acme.click("#chips button[aria-label='Remove NOVA']")
    acme.wait_for_function("!document.getElementById('peers').textContent.includes('NOVA')")
    assert acme.input_value("#g") == "12"
    acme.click("#addPeerBtn")
    acme.fill("#addPeer", "sap.de")
    acme.press("#addPeer", "Enter")
    acme.wait_for_function("document.getElementById('peers').textContent.includes('SAP.DE')")
    assert "$262.7B" in acme.inner_text("#peers")  # EUR market cap converted into the subject currency
    assert acme.input_value("#g") == "12"


def test_track_record_labels_do_not_overlap_bars(acme):
    cols = acme.locator("#hist .col")
    assert cols.count() == 4
    for i in range(4):
        plot = cols.nth(i).locator(".plot").bounding_box()
        label = cols.nth(i).locator(".lab").bounding_box()
        assert plot["y"] + plot["height"] <= label["y"] + 0.5
    text = acme.inner_text("#hist")
    assert "FCF margin" in text and "after stock pay" in text and "$100B" in text


def test_flags_show_terminal_share_stock_pay_effect_and_dilution(acme):
    flags = acme.inner_text("#flags")
    assert re.search(r"Terminal value is \d+% of the base estimate", flags)
    assert re.search(r"counted as a cost.*\$\d+\.\d\d", flags)
    assert "Share count grew about 1.3% a year" in flags
    acme.click("#sbcSeg button[data-v='0']")
    acme.wait_for_function("document.getElementById('flags').textContent.includes('not counted')")


def test_sources_table_covers_every_input(acme):
    text = acme.inner_text("#sources")
    for name in ["Price, market cap, shares, beta", "Revenue, FCF, cash, debt", "Stock-based pay",
                 "Risk-free rate", "Equity risk premium", "Analyst growth estimates", "Bear / base / bull",
                 "Peer list", "Peer growth, margin", "Cost of debt, tax rate", "Forecasts beyond"]:
        assert name in text, name
    assert "not financial advice" in text.lower()


def test_every_spec_term_has_a_glossary_entry(acme):
    keys = acme.evaluate("import('/static/glossary.js').then(m => Object.keys(m.GLOSSARY))")
    assert set(SPEC_TERMS) <= set(keys)
    assert all(text.strip() for text in acme.evaluate("import('/static/glossary.js').then(m => Object.values(m.GLOSSARY))"))


def test_all_spec_terms_are_marked_up_on_the_page(acme):
    used = set(acme.evaluate("[...document.querySelectorAll('[data-g]')].map(e => e.dataset.g)"))
    assert set(SPEC_TERMS) <= used


def test_terms_show_definitions_on_hover_and_keyboard_focus(acme):
    terms = acme.locator("[data-g]")
    count = terms.count()
    assert count >= len(SPEC_TERMS)
    for i in range(count):
        term = terms.nth(i)
        assert term.get_attribute("tabindex") == "0"
        term.scroll_into_view_if_needed()
        term.focus()
        content = term.evaluate("el => getComputedStyle(el, '::after').content")
        assert content not in ("none", "normal", '""'), term.get_attribute("data-g")
        term.evaluate("el => el.blur()")
    first = terms.first
    first.hover()
    assert first.evaluate("el => getComputedStyle(el, '::after').content") not in ("none", "normal", '""')
