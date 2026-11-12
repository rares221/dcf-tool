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
- **Adjustments to the margin:** stock-based pay is subtracted (it can be switched off), and after-tax interest is added back so the cash flow matches a discount rate that already prices the debt. When Yahoo's interest figure is older than the cash-flow year, it is estimated from the last reported rate and today's debt, and flagged.
- **Discounting:** end-of-year, at a WACC built from the risk-free rate, beta and a 4.5% equity risk premium. Terminal value uses Gordon growth, with long-term growth capped at the risk-free rate (so a low-rate currency such as the yen or franc gets a lower default than 2.5%).
- **Equity bridge:** plus cash, short-term investments and long-term investments (non-current marketable securities); minus total debt (Yahoo's total already includes lease obligations), minority interest and preferred stock; divided by the share count that matches the market cap.
- **Range:** bear/base/bull move growth by 4 points, margin by 3 and the discount rate by 1 (bear up, bull down). It is a "what if I'm a bit wrong" band, not a confidence interval.
- **Reverse DCF:** the growth rate, and separately the discount rate, that would make the model equal today's price.

## Observed data-source behaviour (checked 2026-11-12)

- **yfinance** (no key): unofficial, so it can still break or rate-limit; the cache serves stale data when it does. Unknown tickers return "not found". FX pairs such as `EURUSD=X` and ticker search work.
- London listings quote prices in pence (`GBp`) while `marketCap` is already in pounds; statements can be in a third currency (Unilever: trades in GBP, reports in EUR). Both handled in `dcf.data.yahoo` and `dcf.currency`.
- Statement row labels used: Total Revenue, Free Cash Flow (fallback: Operating Cash Flow + Capital Expenditure), Stock Based Compensation, Total Debt, cash and short-term investments, Investments And Advances (long-term investments), Interest Expense, Tax Rate For Calcs (a fraction in the feed).
- `ZAc` and `ILA` quotes (South Africa, Israel) are in cents and agorot while market cap is in rand and shekels. Verified on 2026-11-12 with live JSE and TASE tickers (SOL.JO, TEVA.TA); price × shares matches market cap after conversion, and the `USDZAR=X` and `USDILS=X` FX pairs work. Regression fixtures: `tests/fixtures/yahoo_jse.json`, `yahoo_tase.json`.
- **Finnhub peers** (`FINNHUB_API_KEY`, optional): verified working end to end on 2026-11-12 (peers loaded in parallel and cached). Which Finnhub plan the key was on is not known, so the free tier's limits are still unconfirmed. Without a key, or if the call fails, the app shows no suggested peers and the user adds tickers manually.
- **FRED** (`FRED_API_KEY`, optional): used for the USD risk-free rate. Not yet verified against the real service (no key was available). Without a key a labelled default is used. Free keys: https://fred.stlouisfed.org/docs/api/api_key.html

Live-check results: `docs/superpowers/plans/live-check.md`.

## Known limitations

- No accounts, saved analyses, watchlists or shareable links.
- Banks, insurers and loss-making companies are declined with an explanation (no fair value); a DCF is the wrong tool for them.
- Annual statements only. Analyst consensus estimates are not used yet (Yahoo does publish them), so suggested growth is history-based and can mislead after demergers or acquisitions.
- Non-USD risk-free rates are labelled default assumptions (placeholder values in `src/dcf/data/rates.py`; refresh them). Set `FRED_API_KEY` for a live US rate.
- Peers need `FINNHUB_API_KEY`; without it users add peer tickers by hand.
- Educational estimate, not financial advice.

## What's left to do

A living list. Pick something, open an issue to say so, and follow [integration.md](integration.md). Items marked
**(needs a decision)** should be discussed in an issue before any code is written.

**Valuation accuracy**
- [ ] Growth fade: use a full fade (or a fixed explicit period) so the 3/5/10-year toggle does not change the answer mainly through how growth fades. **(needs a decision)**
- [ ] Optional mid-year discounting toggle (adds roughly 4% to values). **(needs a decision)**
- [ ] Tie terminal growth to reinvestment (growth versus margin). Terminal growth is already capped at the risk-free rate.
- [ ] Equity bridge: options and RSUs (stock pay is already deducted as a cost; existing grants are not valued separately).
- [ ] Verify the FRED path with a real key; refresh the placeholder risk-free defaults; consider Damodaran's monthly implied equity risk premium instead of a fixed 4.5%.
- [ ] **Unreliable discount rates for some listings** (found 2026-11-12). Currencies without a table entry fall back to a generic 5% risk-free rate, far below typical emerging-market yields (Sasol, in rand, is valued at about four times its price). Warn clearly when the rate is the generic default, or source real government yields.
- [ ] **Negative or tiny betas** (Sasol's Yahoo beta is -0.37) push the discount rate down to the 5% floor. Treat betas below a sensible floor as unreliable, use a fallback, and say so.
- [ ] **Companies with finance arms** (Toyota: Yahoo free cash flow is negative in 3 of 4 years because car financing sits in operating cash flow) are declined as loss-making. Detect captive-finance cash flows or use a different cash-flow measure.
- [ ] Wider coverage: a dividend or excess-return model for banks and insurers, and something sensible for loss-making companies, REITs and ETFs. **(needs a decision)**

**Data and integrations**
- [ ] A curated sector peer list for common tickers, so peers work without a Finnhub key; confirm Finnhub's free-tier limits.
- [ ] Use analyst consensus revenue estimates to inform the suggested growth. Yahoo publishes current- and next-year estimates for free (checked 2026-11-12: Apple about +10.3% and +8.2% from 32 to 35 analysts, against 7.7% history). **(needs a decision)**

**Product**
- [ ] Share an analysis by URL (assumptions encoded in the link).
- [ ] Hosting: rate limiting, hide `/docs`, CORS, key handling, and a production server. The app is local-only for now.

**Project health**
- [ ] Prove the CI workflow (`.github/workflows/ci.yml`) on its first run; the browser-test job is informational until it passes on Linux.
- [ ] Branch protection on `integration` and `main`, and run `python scripts/sync_labels.py` once (see the maintainer checklist in [integration.md](integration.md)).
- [ ] Screenshots in this README, and pinned dependency versions (a lock file).
