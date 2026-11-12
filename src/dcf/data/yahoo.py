"""Yahoo Finance adapter (via yfinance). fetch_raw is the only network code for company data; parse_company is pure."""
from __future__ import annotations

import math
from typing import Callable

from ..currency import fx_symbol, normalise_quote
from ..types import CompanyData, YearFigures
from .cache import SqliteCache
from .provider import ProviderError

# Row-label aliases (first present wins). Confirmed against recorded fixtures for US, ADR, London, German, bank, loss-maker.
REVENUE = ("Total Revenue", "Operating Revenue")
FCF = ("Free Cash Flow",)
OPERATING_CF = ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
CAPEX = ("Capital Expenditure",)
SBC = ("Stock Based Compensation",)
CASH = ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Federal Funds Sold")
DEBT = ("Total Debt",)
INTEREST = ("Interest Expense",)
TAX_RATE = ("Tax Rate For Calcs",)  # a fraction in the feed
SHARE_COUNT = ("Diluted Average Shares", "Basic Average Shares")


def _finite(value) -> float | None:
    """A real, finite number or None (the feed sometimes carries NaN/inf or strings)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _frame_to_dict(df) -> dict:
    """DataFrame (rows=labels, columns=period ends) -> {label: {"YYYY": value}}, NaN dropped."""
    out: dict = {}
    if df is None or getattr(df, "empty", True):
        return out
    for label in df.index:
        row = {}
        for col in df.columns:
            try:
                f = float(df.at[label, col])
            except (TypeError, ValueError):
                continue
            if not math.isnan(f):
                row[str(col)[:4]] = f
        if row:
            out[str(label)] = row
    return out


def fetch_raw(ticker: str, ticker_factory: Callable | None = None) -> dict | None:
    """Raw payload (JSON-serialisable) or None when the ticker doesn't exist. Failures raise ProviderError.

    yfinance hides some rate-limit errors by returning empty statement tables, so an equity with missing statements
    is treated as a failed fetch (never cached) rather than as a real company with no history."""
    if ticker_factory is None:
        import yfinance as yf

        ticker_factory = yf.Ticker
    try:
        t = ticker_factory(ticker)
        info = t.info or {}
        if not any(_finite(info.get(k)) is not None for k in ("currentPrice", "regularMarketPrice", "previousClose")):
            return None
        keep = {k: v for k, v in info.items() if v is None or isinstance(v, (str, int, float, bool))}
        payload = {
            "info": keep,
            "income": _frame_to_dict(t.income_stmt),
            "cashflow": _frame_to_dict(t.cashflow),
            "balance": _frame_to_dict(t.balance_sheet),
        }
    except ProviderError:
        raise
    except Exception as exc:  # network, rate limit, parsing: all transient from the user's point of view
        text = f"{type(exc).__name__}: {exc}"
        if "404" in text or "Not Found" in text:
            return None
        raise ProviderError(text) from exc
    if not keep.get("currency"):  # never guess the currency symbol the user will see
        raise ProviderError(f"{ticker}: no price currency in data")
    if keep.get("quoteType") == "EQUITY" and not (payload["income"] and payload["cashflow"] and payload["balance"]):
        raise ProviderError(f"{ticker}: incomplete financial statements (likely rate limited)")
    return payload


def _row(section: dict, aliases: tuple[str, ...]) -> dict[str, float]:
    for label in aliases:
        if section.get(label):
            return section[label]
    return {}


def _latest(row: dict[str, float]) -> float | None:
    return row[max(row)] if row else None


def _share_growth(income: dict) -> float | None:
    series = _row(income, SHARE_COUNT)
    if len(series) < 2:
        return None
    first, last = min(series), max(series)
    span = int(last) - int(first)
    if span <= 0 or series[first] <= 0 or series[last] <= 0:
        return None
    return ((series[last] / series[first]) ** (1 / span) - 1) * 100


def _consistent_shares(reported: float | None, market_cap: float, price: float) -> float | None:
    """Per-share maths needs the share count that matches market cap. Yahoo's sharesOutstanding can count a single
    share class (Alphabet, Berkshire) while marketCap covers all classes, so prefer market_cap / price when they disagree."""
    derived = market_cap / price if market_cap > 0 and price > 0 else None
    if not reported:
        return derived
    if derived is not None and abs(float(reported) / derived - 1) > 0.05:
        return derived
    return float(reported)


def parse_company(raw: dict) -> CompanyData:
    info, income, cashflow, balance = raw["info"], raw.get("income", {}), raw.get("cashflow", {}), raw.get("balance", {})
    price_raw = next((_finite(info.get(k)) for k in ("currentPrice", "regularMarketPrice", "previousClose")
                      if _finite(info.get(k)) is not None), None)
    if price_raw is None:
        raise ValueError("no price in data")
    quote_ccy = info.get("currency")
    if not quote_ccy:
        raise ValueError("no price currency in data")
    trading_ccy, price = normalise_quote(quote_ccy, price_raw)
    statement_ccy = (info.get("financialCurrency") or trading_ccy).upper()
    if statement_ccy in ("GBP", "GBX"):
        statement_ccy = "GBP"

    revenue, fcf = _row(income, REVENUE), _row(cashflow, FCF)
    if not fcf:
        ocf, capex = _row(cashflow, OPERATING_CF), _row(cashflow, CAPEX)
        fcf = {y: ocf[y] + capex[y] for y in ocf if y in capex}
    sbc = _row(cashflow, SBC)
    year_keys = sorted(set(revenue) & set(fcf))[-4:]
    years = tuple(YearFigures(int(y), revenue[y], fcf[y], sbc.get(y, 0.0)) for y in year_keys)

    tax = _latest(_row(income, TAX_RATE))
    interest = _latest(_row(income, INTEREST))
    forward_pe = _finite(info.get("forwardPE"))
    reported_shares = _finite(info.get("sharesOutstanding"))
    market_cap = _finite(info.get("marketCap")) or (price * reported_shares if reported_shares else 0.0)
    return CompanyData(
        ticker=info.get("symbol") or "",
        name=info.get("longName") or info.get("shortName") or info.get("symbol") or "",
        sector=info.get("sector"), industry=info.get("industry"),
        trading_currency=trading_ccy, statement_currency=statement_ccy,
        price=price, market_cap=market_cap,
        shares=_consistent_shares(reported_shares, market_cap, price),
        beta=_finite(info.get("beta")),
        forward_pe=forward_pe if forward_pe is not None and forward_pe > 0 else None,
        cash=_latest(_row(balance, CASH)) or 0.0, debt=_latest(_row(balance, DEBT)) or 0.0,
        interest_expense=abs(interest) if interest is not None else None,
        tax_rate=tax * 100 if tax is not None else None,
        years=years, share_growth=_share_growth(income),
    )


def _live_fx(symbol: str) -> float | None:
    import yfinance as yf

    hist = yf.Ticker(symbol).history(period="5d")
    if hist is None or hist.empty:
        return None
    return float(hist["Close"].dropna().iloc[-1])


def _live_search(query: str) -> list[str]:
    import yfinance as yf

    return [q["symbol"] for q in yf.Search(query, max_results=5).quotes if q.get("symbol")]


class YahooProvider:
    """Company data, FX and ticker suggestions from Yahoo, with a 24h raw-payload cache and stale fallback."""

    def __init__(self, cache: SqliteCache, fetch: Callable[[str], dict | None] = fetch_raw,
                 fx_fetch: Callable[[str], float | None] = _live_fx,
                 search: Callable[[str], list[str]] = _live_search):
        self._cache, self._fetch, self._fx_fetch, self._search = cache, fetch, fx_fetch, search

    def fetch_company(self, ticker: str) -> CompanyData | None:
        key = f"yahoo:{ticker}"
        fresh = self._cache.get(key)
        if fresh is not None:
            return self._parse(fresh.value, ticker, fresh.age_seconds, False)
        try:
            raw = self._fetch(ticker)
        except ProviderError:
            stale = self._cache.get(key, allow_stale=True)
            if stale is None:
                raise
            return self._parse(stale.value, ticker, stale.age_seconds, True)
        if raw is None:
            # yfinance can hide an HTTP outage as "no price", which looks like an unknown ticker. A company we have
            # seen before does not disappear: serve the saved copy and say it is old.
            stale = self._cache.get(key, allow_stale=True)
            return self._parse(stale.value, ticker, stale.age_seconds, True) if stale else None
        self._cache.put(key, raw)
        return self._parse(raw, ticker, 0.0, False)

    @staticmethod
    def _parse(raw: dict, ticker: str, age: float, stale: bool) -> CompanyData:
        from dataclasses import replace

        company = parse_company(raw)
        return replace(company, ticker=company.ticker or ticker, data_age_seconds=age, stale=stale)

    def fx_rate(self, from_ccy: str, to_ccy: str) -> float | None:
        a, b = from_ccy.upper(), to_ccy.upper()
        if a == b:
            return 1.0
        symbol = fx_symbol(a, b)
        key = f"fx:{symbol}"
        fresh = self._cache.get(key)
        if fresh is not None:
            return fresh.value["rate"]
        try:
            rate = self._fx_fetch(symbol)
        except Exception:
            rate = None
        if rate and rate > 0:
            self._cache.put(key, {"rate": float(rate)})
            return float(rate)
        stale = self._cache.get(key, allow_stale=True)
        return stale.value["rate"] if stale else None

    def suggest(self, query: str) -> list[str]:
        try:
            return list(self._search(query))[:5]
        except Exception:
            return []
