# DCF tool

A small web app where a retail investor types a ticker and gets a discounted-cash-flow fair value **range**,
how sensitive it is to assumptions, what the current price implies, and a peer comparison, in the
currency the asset trades in.

Design: `docs/superpowers/specs/2026-11-12-dcf-tool-design.md`. Plan: `docs/superpowers/plans/2026-11-12-dcf-tool.md`.
Visual mockup: `docs/mockups/dcf-results-page-mockup.html`.

## Setup

    python -m venv .venv
    .venv\Scripts\python -m pip install -e ".[dev]"

## Tests

    python -m pytest              # unit tests
    python -m pytest -m e2e       # browser tests (needs: python -m playwright install chromium)
    python -m pytest -m network   # hits real services
