"""Orchestration: turn a ticker into the JSON payloads the API serves."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace

from .currency import convert_statements
from .data.provider import DataProvider, ProviderError
from .defaults import (DEFAULT_COST_OF_DEBT, DEFAULT_TAX_RATE, DEFAULT_TERMINAL_GROWTH,
                       EQUITY_RISK_PREMIUM, SLIDER_LIMITS)
from .detect import Assessment, assess
from .peers import DIRECTION, PeerMetrics, metrics_for, peer_median, reading
from .scenarios import (build_scenarios, implied_growth, implied_return, present_value_of_100,
                        price_position, sbc_effect, sensitivity)
from .types import Assumptions, CompanyData, ModelInputs
from .wacc import compute_wacc

TICKER_RE = re.compile(r"^[A-Z0-9.\-^=]{1,15}$")
MAX_PEERS = 8


def normalise_ticker(raw: str) -> str | None:
    t = (raw or "").strip().upper()
    return t if TICKER_RE.match(t) else None


@dataclass
class Prepared:
    status: str
    company: CompanyData | None = None
    notes: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    fx: dict | None = None


def _convert_if_needed(company: CompanyData, provider: DataProvider) -> tuple[CompanyData | None, dict | None]:
    """Statements into the trading currency. Returns (company, fx info); company is None when no rate exists."""
    if company.statement_currency == company.trading_currency:
        return company, None
    rate = provider.fx_rate(company.statement_currency, company.trading_currency)
    if rate is None or rate <= 0:
        return None, None
    fx = {"from": company.statement_currency, "to": company.trading_currency, "rate": rate}
    return convert_statements(company, rate), fx


def _prepare(raw_ticker: str, provider: DataProvider) -> Prepared:
    ticker = normalise_ticker(raw_ticker)
    if ticker is None:
        return Prepared("not_found")
    try:
        company = provider.fetch_company(ticker)
    except ProviderError:
        return Prepared("error")
    if company is None:
        return Prepared("not_found", suggestions=provider.suggest(ticker))

    notes: list[str] = []
    if company.stale:
        notes.append("stale")
    if company.trading_currency != "USD" or "." in ticker:
        notes.append("non_us")
    converted, fx = _convert_if_needed(company, provider)
    if converted is None:
        return Prepared("no_fx", company=company, notes=notes)
    if fx:
        notes.append("fx_converted")
    company = converted
    if (company.shares or 0) <= 0 and company.market_cap > 0 and company.price > 0:
        company = replace(company, shares=company.market_cap / company.price)

    assessment: Assessment = assess(company)
    notes.extend(r for r in assessment.reasons if r not in notes)
    return Prepared(assessment.status, company=company, notes=notes, fx=fx)


def _inputs_from(company: CompanyData) -> ModelInputs:
    latest = company.years[-1]
    sbc_pct = latest.sbc / latest.revenue * 100 if latest.revenue > 0 else 0.0
    return ModelInputs(revenue=latest.revenue, cash=company.cash, debt=company.debt,
                       shares=company.shares or 0.0, price=company.price, sbc_pct=sbc_pct)


def model_inputs(raw_ticker: str, provider: DataProvider) -> tuple[str, ModelInputs | None]:
    prepared = _prepare(raw_ticker, provider)
    if prepared.status in ("ok", "partial") and prepared.company is not None:
        return prepared.status, _inputs_from(prepared.company)
    return prepared.status, None


def _history(company: CompanyData) -> list[dict]:
    rows = []
    for y in company.years:
        margin = y.fcf / y.revenue * 100 if y.revenue > 0 else None
        after = (y.fcf - y.sbc) / y.revenue * 100 if y.revenue > 0 else None
        rows.append({"year": y.year, "revenue": y.revenue, "fcf_margin": margin, "fcf_margin_after_sbc": after})
    return rows


def _cagr(company: CompanyData) -> float | None:
    ys = company.years
    if len(ys) < 2 or ys[0].revenue <= 0 or ys[-1].revenue <= 0:
        return None
    return ((ys[-1].revenue / ys[0].revenue) ** (1 / (len(ys) - 1)) - 1) * 100


def _clamp(key: str, value: float, notes: list[str]) -> float:
    lo, hi = SLIDER_LIMITS[key]
    if value < lo or value > hi:
        notes.append(f"suggestion_clamped:{key}")
    return min(max(value, lo), hi)


def _suggested(company: CompanyData, provider: DataProvider, cagr: float | None, notes: list[str]) -> dict:
    latest = company.years[-1]
    inputs = _inputs_from(company)
    rf = provider.risk_free_rate(company.trading_currency)
    kd = DEFAULT_COST_OF_DEBT
    if company.interest_expense is not None and company.debt > 0:
        implied = company.interest_expense / company.debt * 100
        if 0 < implied <= 25:
            kd = implied
    tax = company.tax_rate if company.tax_rate is not None and 0 <= company.tax_rate <= 60 else DEFAULT_TAX_RATE
    market_cap = company.market_cap if company.market_cap > 0 else company.price * inputs.shares
    breakdown = compute_wacc(rf.rate_pct, company.beta if company.beta is not None else 1.0,
                             EQUITY_RISK_PREMIUM, kd, tax, market_cap, company.debt)

    growth = _clamp("growth", cagr if cagr is not None else 0.0, notes)
    margin = _clamp("fcf_margin", latest.fcf / latest.revenue * 100 if latest.revenue > 0 else 0.0, notes)
    wacc = _clamp("wacc", breakdown.wacc, notes)
    return {
        "growth": round(growth * 2) / 2,
        "fcf_margin": round(margin * 2) / 2,
        "wacc": round(wacc, 1),
        "terminal_growth": DEFAULT_TERMINAL_GROWTH,
        "sbc_pct": inputs.sbc_pct,
        "wacc_breakdown": asdict(breakdown),
        "risk_free_source": rf.source,
    }


def _peer_rows(subject: CompanyData, provider: DataProvider, tickers: list[str]) -> list[PeerMetrics]:
    rows: list[PeerMetrics] = [metrics_for(subject, subject.market_cap)]
    seen = {subject.ticker.upper()}
    for raw in tickers:
        t = normalise_ticker(raw)
        if t is None or t in seen:
            continue
        seen.add(t)
        if len(rows) > MAX_PEERS:
            break
        try:
            peer = provider.fetch_company(t)
        except ProviderError:
            continue
        if peer is None:
            continue
        converted, _ = _convert_if_needed(peer, provider)
        if converted is None:
            continue
        to_subject = provider.fx_rate(converted.trading_currency, subject.trading_currency)
        if to_subject is None:
            continue
        rows.append(metrics_for(converted, converted.market_cap * to_subject))
    return rows


def _peers_payload(rows: list[PeerMetrics]) -> dict:
    others = rows[1:]
    medians = {k: peer_median(others, k) for k in DIRECTION}
    readings = {k: reading(k, getattr(rows[0], k), medians[k]) for k in DIRECTION}
    return {"rows": [asdict(r) for r in rows], "medians": medians, "readings": readings}


def _empty_payload(status: str) -> dict:
    return {
        "status": status, "notes": [], "suggestions": [], "company": None, "history": [], "history_cagr": None,
        "suggested": None, "limits": {k: list(v) for k, v in SLIDER_LIMITS.items()}, "base": None,
        "peers": {"rows": [], "medians": {}, "readings": {}}, "data_age_seconds": 0.0, "fx": None,
    }


def analyze(raw_ticker: str, provider: DataProvider, peer_tickers: list[str] | None = None) -> dict:
    prepared = _prepare(raw_ticker, provider)
    out = _empty_payload(prepared.status)
    out["notes"] = prepared.notes
    out["suggestions"] = prepared.suggestions
    company = prepared.company
    if company is None:
        return out

    out["company"] = {
        "ticker": company.ticker, "name": company.name, "sector": company.sector, "industry": company.industry,
        "currency": company.trading_currency, "price": company.price, "market_cap": company.market_cap,
        "shares": company.shares,
    }
    out["data_age_seconds"] = company.data_age_seconds
    out["fx"] = prepared.fx
    if prepared.status == "no_fx":
        return out

    out["history"] = _history(company)
    cagr = _cagr(company)
    out["history_cagr"] = cagr
    tickers = peer_tickers if peer_tickers is not None else provider.peer_tickers(company.ticker)
    out["peers"] = _peers_payload(_peer_rows(company, provider, tickers))

    if prepared.status in ("ok", "partial"):
        out["suggested"] = _suggested(company, provider, cagr, out["notes"])
        out["base"] = asdict(_inputs_from(company))
    return out


def run_model(inputs: ModelInputs, a: Assumptions, horizon: int, count_sbc: bool) -> dict:
    s = build_scenarios(inputs, a, horizon, count_sbc)  # raises ValueError for invalid combinations
    return {
        "scenarios": {"bear": s.bear, "base": s.base, "bull": s.bull},
        "terminal_share": s.terminal_share,
        "position": price_position(inputs.price, s.bear, s.bull),
        "implied_return": {
            "bear": implied_return(s.bear, inputs.price, horizon),
            "base": implied_return(s.base, inputs.price, horizon),
            "bull": implied_return(s.bull, inputs.price, horizon),
        },
        "implied_growth": implied_growth(inputs, a, horizon, count_sbc),
        "sensitivity": [asdict(b) for b in sensitivity(inputs, a, horizon, count_sbc)],
        "sbc_effect": sbc_effect(inputs, a, horizon),
        "pv_of_100": present_value_of_100(a.wacc, horizon),
    }
