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

## Observed data-source behaviour (checked 2026-11-12)

- **yfinance** (no key): 5 uncached company lookups in a row took about 4 seconds with no rate limiting. Unknown tickers return "not found". FX pairs such as `EURUSD=X` and ticker search work. Unofficial, so it can still break or rate-limit; the cache serves stale data when it does.
- London listings quote prices in pence (`GBp`) while `marketCap` is already in pounds; statements can be in a third currency (Unilever: trades in GBP, reports in EUR). Both handled in `dcf.data.yahoo` and `dcf.currency`.
- Statement row labels used: Total Revenue, Free Cash Flow (fallback: Operating Cash Flow + Capital Expenditure), Stock Based Compensation, Total Debt, cash and short-term investments, Interest Expense, Tax Rate For Calcs (a fraction in the feed).
- `ZAc` and `ILA` sub-unit handling (South Africa, Israel) is implemented from the plan but not yet verified against live quotes.
- **Finnhub peers** (`FINNHUB_API_KEY`, optional): I could not confirm from Finnhub's public pages whether `/stock/peers` is on the free plan or what the free rate limit is. Treat it as unverified. Without a key, or if the call fails, the app shows no suggested peers and the user adds tickers manually.
- **FRED** (`FRED_API_KEY`, optional): used for the USD risk-free rate. Without a key the labelled default is used.

## Run

    .venv\Scripts\python -m uvicorn dcf.api:create_app --factory --reload

Then open http://127.0.0.1:8000. Environment variables (all optional): `FRED_API_KEY`, `FINNHUB_API_KEY`,
`DCF_CACHE_PATH` (default `./dcf-cache.sqlite`), `DCF_PROVIDER` (`live` or `fake`), `DCF_FAKE_WORLD` (JSON file for `fake`).

Browser tests use your installed Microsoft Edge through Playwright (no download); if Edge is missing they fall back to
Playwright's Chromium (`python -m playwright install chromium`).
