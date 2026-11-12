# DCF tool

A small web app where a retail investor types a ticker and gets a discounted-cash-flow fair value **range**,
how sensitive it is to assumptions, what the current price implies, and a peer comparison, in the
currency the asset trades in.

- **Contributing:** anyone is welcome. Read [integration.md](integration.md); all pull requests go to the `integration` branch.
- **What's left to do:** see [What's left to do](#whats-left-to-do) below.
- **License:** [MIT](LICENSE).
- **Not financial advice.** This is an educational estimate. A DCF is only as good as its assumptions.

Design: `docs/superpowers/specs/2026-11-12-dcf-tool-design.md`. Plan: `docs/superpowers/plans/2026-11-12-dcf-tool.md`.
Visual mockup: `docs/mockups/dcf-results-page-mockup.html`.

## Setup

    python -m venv .venv
    .venv\Scripts\python -m pip install -e ".[dev]"

## Run

    .venv\Scripts\python -m uvicorn dcf.api:create_app --factory --reload

Then open http://127.0.0.1:8000. Environment variables (all optional): `FRED_API_KEY`, `FINNHUB_API_KEY`,
`DCF_CACHE_PATH` (default `./dcf-cache.sqlite`), `DCF_PROVIDER` (`live` or `fake`), `DCF_FAKE_WORLD` (JSON file for `fake`).
Never commit keys; `.env` files are git-ignored.

## Tests

    python -m pytest              # unit tests
    python -m pytest -m e2e       # browser tests
    python -m pytest -m network   # hits real services

Browser tests use your installed Microsoft Edge through Playwright (no download); if Edge is missing they fall back to
Playwright's Chromium (`python -m playwright install chromium`).

## How the numbers are built

- **Cash flow:** the latest fiscal year's free cash flow margin (Yahoo's "Free Cash Flow", which is after interest) is applied to revenue that grows at a rate fading half-way toward long-term growth over the horizon (3, 5 or 10 years).
- **Adjustments to the margin:** stock-based pay is subtracted (it can be switched off), and after-tax interest is added back so the cash flow matches a discount rate that already prices the debt.
- **Discounting:** end-of-year, at a WACC built from the risk-free rate, beta and a 4.5% equity risk premium. Terminal value uses Gordon growth.
- **Equity bridge:** plus cash and short-term investments and long-term investments (non-current marketable securities), minus total debt, divided by the share count that matches the market cap.
- **Range:** bear/base/bull move growth by 4 points, margin by 3 and the discount rate by 1 (bear up, bull down). It is a "what if I'm a bit wrong" band, not a confidence interval.
- **Reverse DCF:** the growth rate, and separately the discount rate, that would make the model equal today's price.

## Observed data-source behaviour (checked 2026-11-12)

- **yfinance** (no key): unofficial, so it can still break or rate-limit; the cache serves stale data when it does. Unknown tickers return "not found". FX pairs such as `EURUSD=X` and ticker search work.
- London listings quote prices in pence (`GBp`) while `marketCap` is already in pounds; statements can be in a third currency (Unilever: trades in GBP, reports in EUR). Both handled in `dcf.data.yahoo` and `dcf.currency`.
- Statement row labels used: Total Revenue, Free Cash Flow (fallback: Operating Cash Flow + Capital Expenditure), Stock Based Compensation, Total Debt, cash and short-term investments, Investments And Advances (long-term investments), Interest Expense, Tax Rate For Calcs (a fraction in the feed).
- `ZAc` and `ILA` sub-unit handling (South Africa, Israel) is implemented but not yet verified against live quotes.
- **Finnhub peers** (`FINNHUB_API_KEY`, optional): verified working end to end on 2026-11-12 (peers loaded in parallel and cached). Which Finnhub plan the key was on is not known, so the free tier's limits are still unconfirmed. Without a key, or if the call fails, the app shows no suggested peers and the user adds tickers manually.
- **FRED** (`FRED_API_KEY`, optional): used for the USD risk-free rate. Not yet verified against the real service (no key was available). Without a key a labelled default is used. Free keys: https://fred.stlouisfed.org/docs/api/api_key.html

Live-check results: `docs/superpowers/plans/live-check.md`.

## Known limitations

- No accounts, saved analyses, watchlists or shareable links.
- Banks, insurers and loss-making companies are declined with an explanation (no fair value); a DCF is the wrong tool for them.
- Annual statements only; analyst growth estimates are not used (not available on free sources), so suggested growth is history-based and can mislead after demergers or acquisitions.
- Non-USD risk-free rates are labelled default assumptions (placeholder values in `src/dcf/data/rates.py`; refresh them). Set `FRED_API_KEY` for a live US rate.
- Peers need `FINNHUB_API_KEY`; without it users add peer tickers by hand.
- Educational estimate, not financial advice.

## What's left to do

A living list. Pick something, open an issue to say so, and follow [integration.md](integration.md). Items marked
**(needs a decision)** should be discussed in an issue before any code is written.

**Valuation accuracy**
- [ ] Growth fade: use a full fade (or a fixed explicit period) so the 3/5/10-year toggle does not change the answer mainly through how growth fades. **(needs a decision)**
- [ ] Optional mid-year discounting toggle (adds roughly 4% to values). **(needs a decision)**
- [ ] Cap terminal growth at the risk-free rate, and tie terminal growth to reinvestment (growth versus margin).
- [ ] Equity bridge: leases, minority interest, preferred stock, options and RSUs.
- [ ] Interest expense from Yahoo can be a year or two old (Apple's latest is 2023). Match it to the cash-flow year, or estimate it from debt and a cost of debt.
- [ ] Verify the FRED path with a real key; refresh the placeholder risk-free defaults; consider Damodaran's monthly implied equity risk premium instead of a fixed 4.5%.
- [ ] Warn when the suggested growth is distorted (for example after a demerger): the 3-year growth and last-year growth disagree sharply.
- [ ] Wider coverage: a dividend or excess-return model for banks and insurers, and something sensible for loss-making companies, REITs and ETFs. **(needs a decision)**

**Data and integrations**
- [ ] A curated sector peer list for common tickers, so peers work without a Finnhub key; confirm Finnhub's free-tier limits.
- [ ] Verify `ZAc` and `ILA` quote units against live prices.
- [ ] A free source of analyst growth estimates, if one exists.

**Product**
- [ ] Share an analysis by URL (assumptions encoded in the link).
- [ ] Phone layout: the data-sources table is cramped on narrow screens.
- [ ] Hosting: rate limiting, hide `/docs`, CORS, key handling, and a production server. The app is local-only for now.

**Project health**
- [ ] CI: a GitHub Actions workflow running the unit tests on every pull request (browser tests need Edge or Chromium).
- [ ] Issue templates, the label set from [integration.md](integration.md), and branch protection on `integration` and `main`.
- [ ] Screenshots in this README, and pinned dependency versions (a lock file).
