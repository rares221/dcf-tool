# Live check (real Yahoo data, 2026-11-12)

The app was run with the live provider (no FRED or Finnhub keys) and driven in a real browser (Microsoft Edge via Playwright), one fresh lookup per ticker.

| Ticker | What it exercises | Result | Currency symbol correct |
|---|---|---|---|
| MSFT | large US company | Full analysis in 3.0s. Scenarios, reverse DCF, WACC, track record, flags all rendered. No peers (no Finnhub key). | Yes ($) |
| ULVR.L | London listing quoted in pence, statements in EUR | Price shown as pounds (about 48.89), market cap in pounds, statements converted EUR to GBP with a visible banner. | Yes (£) |
| SAP.DE | German listing | Non-US banner naming EUR; all values in euros. | Yes (€) |
| TSM | ADR reporting in TWD, trading in USD | TWD to USD conversion banner; values in dollars. | Yes ($) |
| JPM | bank | "needs a different model" panel; header, track record and peers shown; no fair value. | Yes ($) |
| RIVN | loss-making | "a DCF would be misleading" panel; no fair value. | Yes ($) |
| ZZZZQQ9 | nonsense ticker | "We couldn't find" panel. | n/a |

Lookups took 1.6 to 3.0 seconds each. No page errors.

## Found and fixed during the check

- The exchange rate in the conversion banner printed 16 digits (`0.8361200094223022`). It now shows 4 significant digits (`0.8361`). Test added (RED then GREEN).
- The page requested a missing favicon, producing a browser console error. Fixed with an inline icon. Test added: loading a company must produce no console errors.

## Observations (not defects)

- Without a `FINNHUB_API_KEY` there are no suggested peers, so the peer table shows "n/a" and the note "No peers loaded. Add tickers above to compare." Users can add tickers by hand.
- Suggested growth is the revenue growth over the years shown, so events like demergers distort it. Unilever's reported revenue fell from about 60B to 50.5B EUR, giving a suggested growth of about -5.5%. The reverse-DCF card and the track record make this visible, but the suggestion itself can mislead after spin-offs or acquisitions.
- yfinance prints "Quote not found" lines to the server log for unknown tickers. Harmless.
- On very narrow screens the data-sources table gets cramped (columns wrap heavily). It stays readable and does not cause page-level horizontal scroll.
