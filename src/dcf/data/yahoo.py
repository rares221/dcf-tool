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


def fetch_raw(ticker: str) -> dict | None:
    """Raw payload (JSON-serialisable) or None when the ticker doesn't exist. Failures raise ProviderError."""
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        if not any(info.get(k) is not None for k in ("currentPrice", "regularMarketPrice", "previousClose")):
            return None
        keep = {k: v for k, v in info.items() if v is None or isinstance(v, (str, int, float, bool))}
        return {
            "info": keep,
            "income": _frame_to_dict(t.income_stmt),
            "cashflow": _frame_to_dict(t.cashflow),
            "balance": _frame_to_dict(t.balance_sheet),
        }
    except Exception as exc:  # network, rate limit, parsing: all transient from the user's point of view
        text = f"{type(exc).__name__}: {exc}"
        if "404" in text or "Not Found" in text:
            return None
        raise ProviderError(text) from exc


def _row(section: dict, aliases: tuple[str, ...]) -> dict[str, float]:
    for label in aliases:
        if section.get(label):
            return section[label]
    return {}


def _latest(row: dict[str, float]) -> float | None:
    return row[max(row)] if row else None


def parse_company(raw: dict) -> CompanyData:
    info, income, cashflow, balance = raw["info"], raw.get("income", {}), raw.get("cashflow", {}), raw.get("balance", {})
    price_raw = next((info[k] for k in ("currentPrice", "regularMarketPrice", "previousClose")
                      if info.get(k) is not None), None)
    if price_raw is None:
        raise ValueError("no price in data")
    quote_ccy = info.get("currency") or "USD"
    trading_ccy, price = normalise_quote(quote_ccy, float(price_raw))
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
    forward_pe = info.get("forwardPE")
    return CompanyData(
        ticker=info.get("symbol") or "",
        name=info.get("longName") or info.get("shortName") or info.get("symbol") or "",
        sector=info.get("sector"), industry=info.get("industry"),
        trading_currency=trading_ccy, statement_currency=statement_ccy,
        price=price, market_cap=float(info.get("marketCap") or 0.0),
        shares=float(info["sharesOutstanding"]) if info.get("sharesOutstanding") else None,
        beta=info.get("beta"),
        forward_pe=forward_pe if isinstance(forward_pe, (int, float)) and forward_pe > 0 else None,
        cash=_latest(_row(balance, CASH)) or 0.0, debt=_latest(_row(balance, DEBT)) or 0.0,
        interest_expense=abs(interest) if interest is not None else None,
        tax_rate=tax * 100 if tax is not None else None,
        years=years,
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
            return None
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
        try:
            rate = self._fx_fetch(fx_symbol(a, b))
        except Exception:
            return None
        return rate if rate and rate > 0 else None

    def suggest(self, query: str) -> list[str]:
        try:
            return list(self._search(query))[:5]
        except Exception:
            return []
