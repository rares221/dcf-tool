# DCF Tool for Retail Investors: Design

Date: 2026-11-12
Status: Draft for approval
Reference mockup: `docs/mockups/dcf-results-page-mockup.html` (open in a browser; the calculations and all page states are live with fictional "ACME Corp" data)

Notes on markings: statements without a marker come from the person who commissioned this. Anything marked **[My call]** is a choice made while writing the design, not something they agreed to, so check it.

## 1. Intent

Build a lightweight web tool where a retail investor types a stock ticker and gets an honest, understandable discounted cash flow (DCF) analysis.

The point is to help people make educated decisions "to the best of our capabilities". That means the tool is built around being honest about uncertainty: a DCF answer depends heavily on assumptions nobody can know exactly, so the page shows a fair value **range**, shows **how sensitive** that range is to the assumptions, and shows **realistic timelines** (3, 5 and 10 year horizons). It also explains finance terms in plain language because the audience will not know them.

Constraints on scope: it should stay lightweight, run in Python with a web page as the interface, and use free data sources.

## 2. Audience

Retail investors, mostly not finance professionals. They may not know what WACC, free cash flow, beta or terminal value mean, and many will use a phone.

## 3. Goals

- A user enters a ticker and gets a results page in seconds (first lookup a few seconds; repeat lookups instant from cache).
- The headline is a **fair value range** (bear / base / bull) compared with the current price, never a single precise number.
- The user sees **how sensitive** the answer is to each assumption.
- The user can **change assumptions** and watch the answer update immediately.
- The user can see **what the current price already assumes** (reverse DCF).
- The user can **compare the company to peers**.
- Finance terms are explained in plain language where they appear, and the discount rate (WACC) has its own explainer.
- The tool says clearly when a DCF is **not** appropriate rather than producing a misleading number.
- Works well at phone width.
- All money is shown in the **currency the asset trades in**, with the correct symbol (see section 7).

## 4. Non-goals (not in the first version)

- User accounts, saved analyses, shareable links, watchlists, portfolios.
- Valuing banks and insurers (a different model is needed), or loss-making companies.
- Real-time prices or intraday data.
- Alternative valuation methods (multiples-only valuation, dividend discount models).
- Buy / sell / hold recommendations.
- Paid data sources.

## 5. Anti-goals (would be a failure even if it technically works)

- Showing a single precise-looking "fair value" that users over-trust.
- Producing a confident number for a company where a DCF is a poor fit.
- Hiding assumptions: every assumption that drives the answer must be visible and changeable.
- Mixing currencies silently, so that numbers look right but are wrong.
- Jargon without explanation.
- Wording that reads as financial advice.

## 6. What the page contains

The mockup is the visual source of truth. In order, the results page has:

1. **Company header:** name, ticker, sector, market cap, current price, where each kind of data came from.
2. **Takeaway sentence:** one sentence stating where the price sits in the range, which assumption swings the answer most, and the growth the market is pricing in. Updates live. Ends with a "not financial advice" line.
3. **Forecast horizon and scenarios:** 3 / 5 / 10 year toggle; bear, base and bull fair values; a range bar with the current price marked; a line giving the implied yearly return if the price moved to the base estimate over the horizon.
4. **"What is the market already assuming?" (reverse DCF):** the starting growth rate that makes the model equal today's price, compared with the user's assumption, the company's last-3-year growth and the peer median, with a plain sentence interpreting the gap and a button to adopt the implied growth as the user's assumption.
5. **Assumptions panel:** sliders for revenue growth, FCF margin (reported), discount rate, long-term growth; a stock-based-pay toggle; the margin actually used by the model; a "Reset to suggested" button and an "Edited" indicator.
6. **Sensitivity ("what moves the answer most"):** each assumption nudged down and up with the others at base, ranked by effect.
7. **Discount rate (WACC) explainer:** plain-words explanation, a live "$100 in N years is worth $X today" example, the step-by-step estimate (risk-free rate + beta x equity risk premium, after-tax cost of debt, equity/debt mix), and a live line showing how much one point of discount rate moves the answer.
8. **Peer comparison:** company vs a peer set on market cap, revenue growth, FCF margin, FCF yield, forward P/E and beta, with peer median and a words-not-just-colour reading ("cheaper (+12%)"). Peers shown as chips the user can add or remove. A live note compares the user's growth and margin assumptions with the peer median.
9. **Track record (4 years):** revenue, FCF margin and margin after stock pay per year, laid out so labels never overlap bars.
10. **Heads-up flags (live):** terminal value share of the estimate; whether free cash flow was positive; stock-based pay treatment and its dollar effect per share; share-count growth (dilution); analyst-estimate availability; the "DCF not suitable" note.
11. **Data sources panel:** each input, where it comes from, and how reliable it is.
12. **Plain-language tooltips** on dotted terms (FCF, FCF margin, terminal value, beta, equity risk premium, WACC, long-term growth, stock-based pay, dilution, reverse DCF, forecast horizon). Must work on hover, keyboard focus and tap.

## 7. Currency (requirement)

Every monetary value on the page (price, fair values, market cap, revenue, per-share figures, sensitivity labels, tooltips and takeaway text) must use the **currency the asset trades in**, with the correct symbol and number formatting. A UK, European or Japanese listing must not show "$".

The mockup uses "$" throughout because the sample company is a US one; the builder must not copy that hard-coding.

Details that need handling:

- **No silent mixing.** If the currency the financial statements are reported in differs from the currency the stock trades in (common for foreign companies listed as ADRs), the model must not combine them unconverted. **[My call]** Convert statement figures to the trading currency at the current spot rate, and show a visible note saying so. If a reliable rate can't be obtained, show the "partial data" state rather than a number.
- **Quotation units.** Some markets quote prices in a sub-unit (for example London prices in pence rather than pounds). The builder must verify how the data source reports these and normalise before any calculation. **[Builder to verify]**
- **Rates by currency.** The risk-free rate and equity risk premium should match the currency of the cash flows. Where a free, reliable series isn't available, use a clearly labelled default per currency and show it as an assumption the user can edit. **[My call]**
- **Peers** are compared on ratios (growth, margins, multiples), which are currency-neutral; market cap in the peer table is shown in the asset's own currency, converted if needed.
- Show the currency code once near the price (for example "EUR") so it is never ambiguous.

## 8. Model behaviour

Starting rules taken from the mockup. The builder should implement these, test them against hand-calculated cases, and may refine details as long as users are told what the model does.

- **Method:** free-cash-flow DCF. Project revenue, apply an FCF margin, discount at the user's rate, add a terminal value, then add cash and subtract debt and divide by shares.
- **Growth path:** starts at the user's growth rate and fades toward long-term growth over the horizon (mockup: fades half-way over the horizon).
- **Terminal value:** growth in perpetuity from the final year. The discount rate must always exceed long-term growth; the UI limits must enforce this.
- **Scenarios (mockup defaults, shown and editable):** bear = growth -4 points, margin -3 points, discount rate +1, long-term growth -0.5 (not below 0); bull = growth +4, margin +3, discount rate -0.5 (but at least 2 points above long-term growth).
- **Sensitivity flex (mockup defaults):** discount rate +/-1, revenue growth +/-3, FCF margin +/-3, long-term growth +/-1.
- **Starting values from data:** growth = revenue growth over the last 3 years; margin = latest reported FCF margin; discount rate = WACC as built in section 6 item 7. Default equity risk premium about 4.5%, default tax rate and cost of debt used when the data is missing, all labelled as assumptions.
- **Stock-based pay:** on by default, subtracting stock pay (as % of revenue) from the margin used. The user can switch it off; the page then shows the dollar-per-share effect of doing so.
- **Reverse DCF:** solve for the starting growth that makes the model's base value equal the current price, holding the user's other assumptions fixed. If no reasonable value reaches the price, say so instead of showing a number.
- **Implied return line:** (base value / price)^(1/horizon) - 1, labelled as assuming the price moves to the base estimate, before dividends.
- **Sliders must feel instant.**

## 9. States and edge cases

Each must be a designed state, not an error dump (see the "Preview a state" bar in the mockup):

| State | Behaviour |
|---|---|
| Loading | Skeleton blocks and a note that repeat lookups are faster |
| Ticker not found | Message, closest-match suggestions, reminder about exchange suffixes (for example `.DE`); nothing else shown |
| Non-US listing | Banner explaining currency and default rates; rest of page shown |
| Partial or stale data | Banner naming what is missing or old, with a retry; the range is described as rougher |
| Loss-making company | No fair value range; explain why; still show track record and peers |
| Bank or insurer | No fair value range; explain why a different model is needed; still show track record and peers |

Also: currency mismatch between statements and trading (section 7).

Detection rules **[My call]** (starting values; the builder may tune them, and the page always says why a DCF was declined):

- **Bank or insurer:** identified from the sector and industry the data source reports.
- **Loss-making:** latest fiscal-year free cash flow is zero or negative, or free cash flow is negative in 2 or more of the last 4 years.
- **Enough history:** at least 2 years of statements are needed to proceed (with the "partial data" banner if fewer than 4). Fewer than 2 is treated as a blocking "not enough data" message in the same style as the states above.
- **Annual figures:** the model uses annual statements and the latest fiscal year, not trailing-twelve-month or quarterly figures, to keep sources consistent.

## 10. Data (free sources; limits to be verified at build time)

| Input | Planned source | Notes |
|---|---|---|
| Price, market cap, shares, beta, 4 years of statements, stock pay, share-count history, cost of debt and tax | yfinance | Free, no key, unofficial so it can break or rate-limit |
| Backup for statements | Financial Modeling Prep free tier or SEC EDGAR (US only) | Free tiers are capped; EDGAR data needs normalising |
| Risk-free rate | FRED API (10-year Treasury) | Free key. Non-USD rates need a source or labelled defaults |
| Peer list | Finnhub free peers endpoint, or a curated sector list | yfinance has no peer list |
| Peer metrics | yfinance, one fetch per peer | Caching is essential |
| Analyst growth estimates | Partial on free sources | Fall back to history; say so on the page |

Cache results for about 24 hours (SQLite or similar) to stay within limits and make repeat lookups instant. Data freshness is shown on the page.

Free-tier limits quoted in conversation were from memory and unverified; the builder confirms them first and designs a fallback if a source is unavailable.

## 11. Constraints and platform

- **Language:** Python (stated by the commissioner). A web page is the interface (stated).
- **Free data only** (stated). No budget for paid APIs.
- **Lightweight:** no accounts, no database of users, small footprint.
- **Phone-friendly:** the mockup defines the phone layout (stacked sliders, two-column track record, scrollable peer table with pinned first column). A "Preview on phone" control in the mockup shows it at 390px wide.
- **Accessibility basics:** meaning is never carried by colour alone (the peer reading uses words), tooltips work by keyboard and touch, animations respect reduced-motion, works in light and dark mode.
- **Legal framing:** every results page carries an "educational estimate, not financial advice" line. **[My call]**
- **Where it runs:** **[My call]** run locally first. Deploying publicly is a separate later decision.

## 12. Left to the builder

- Web framework and project structure.
- Whether the model runs in the browser (instant sliders, as in the mockup) or on the server (single implementation, easier to test), or both, provided sliders stay instant and the model is unit-tested.
- Cache store and refresh logic.
- How to obtain peers and reliable per-currency rates, given the limits above.
- Test strategy, including a set of known tickers (large US, foreign ADR, bank, loss-making, tiny company, bad ticker).
- Exact wording of the plain-language definitions (the mockup text is a starting point, not final).

## 13. Success looks like

- A non-expert can enter a ticker and, within a minute, say what range the model gives, what the price implies, and which assumption matters most.
- Changing any slider updates every number and sentence consistently.
- A bank, a loss-making company, a bad ticker and a foreign listing each get a sensible, non-misleading result.
- A non-US listing shows the right currency symbol everywhere.
- Works comfortably on a phone.

## 14. Calls made while writing this (please check)

1. Convert statements to the trading currency at spot FX and show a note, when the two currencies differ (section 7).
2. Use labelled, editable default rates per currency where a free source for the risk-free rate isn't available (section 7).
3. Keep the "not financial advice" line on every results page.
4. Run locally first; deployment is a later decision.
5. The model rules and spread values in section 8 are the mockup's starting values, not tuned or validated numbers.
6. The detection rules for banks, loss-making companies and thin history, and the use of annual rather than trailing figures (section 9).
