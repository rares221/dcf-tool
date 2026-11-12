"""Regenerate tests/fixtures/fake_world.json (fictional companies for the browser tests).

Run: python scripts/make_fake_world.py
"""
import json
from pathlib import Path

B = 1e9


def years(revs, fcfs, sbcs, start=2022):
    return [{"year": start + i, "revenue": r * B, "fcf": f * B, "sbc": s * B}
            for i, (r, f, s) in enumerate(zip(revs, fcfs, sbcs))]


def company(name, price, mcap, shares, ys, *, currency="USD", statement=None, beta=1.0, pe=28.0,
            industry="Software - Application", sector="Technology", cash=30.0, debt=20.0, interest=1.0,
            tax=21.0, stale=False, age=0.0):
    return {
        "name": name, "sector": sector, "industry": industry, "trading_currency": currency,
        "statement_currency": statement or currency, "price": price, "market_cap": mcap * B,
        "shares": shares * B, "beta": beta, "forward_pe": pe, "cash": cash * B, "debt": debt * B,
        "interest_expense": None if interest is None else interest * B, "tax_rate": tax, "years": ys,
        "data_age_seconds": age, "stale": stale,
    }


def peer(name, cap, g, m, fy, pe, beta):
    fcf_last = cap * fy / 100
    rev_last = fcf_last / (m / 100)
    revs = [rev_last / (1 + g / 100) ** (3 - k) for k in range(4)]
    fcfs = [r * m / 100 for r in revs]
    return company(name, 100.0, cap, cap / 100.0, years(revs, fcfs, [r * 0.02 for r in revs]), beta=beta, pe=pe)


acme_years = years((82, 88, 94, 100), (13.94, 16.72, 16.92, 20.0), (1.97, 2.38, 2.73, 3.0))
world = {
    "companies": {
        "ACME": company("ACME Corp", 168.0, 453.6, 2.7, acme_years),
        "NOVA": peer("Nova Systems", 380, 10, 24, 3.9, 31, 1.2),
        "ORBT": peer("Orbit Labs", 520, 12, 18, 3.1, 36, 1.3),
        "KSTL": peer("Kestrel Soft", 210, 6, 22, 5.6, 22, 0.9),
        "LMND": peer("Lumen Data", 95, 9, 15, 4.8, 25, 1.1),
        "SAP.DE": company("Sample Software AG", 210.75, 243.2, 1.154,
                          years((29.5, 31.2, 34.2, 36.8), (4.8, 5.5, 4.4, 8.4), (1.4, 2.2, 2.4, 1.7)),
                          currency="EUR", beta=0.7, pe=24.8, cash=9.8, debt=7.5, interest=0.5, tax=29.0),
        "LSE.L": company("London Goods plc", 48.98, 105.5, 2.153,
                         years((60.0, 51.7, 52.5, 50.5), (5.6, 8.0, 7.9, 6.8), (0.2, 0.2, 0.3, 0.3)),
                         currency="GBP", beta=0.5, pe=16.7, industry="Household & Personal Products",
                         sector="Consumer Defensive", cash=5.0, debt=27.6, interest=1.1, tax=28.5),
        "ADR": company("Taiwan Chips ADR", 413.35, 2143.8, 5.186,
                       years((2264, 2162, 2894, 3809), (521, 287, 861, 992), (0.3, 0.5, 1.2, 1.3)),
                       currency="USD", statement="TWD", beta=1.2, pe=17.7, cash=3128, debt=1065,
                       interest=12.4, tax=17.0),
        "NOFX": company("Unconvertible ADR", 50.0, 20.0, 0.4,
                        years((100, 110, 120, 130), (10, 11, 12, 13), (1, 1, 1, 1)),
                        currency="USD", statement="JPY"),
        "BANK": company("Sample Bank Corp", 343.39, 911.9, 2.656,
                        years((127, 155, 169, 182), (107, 13, -42, -148), (0, 0, 0, 0)),
                        industry="Banks - Diversified", sector="Financial Services", beta=1.0, pe=13.4),
        "LOSS": company("Burn Rate Inc", 13.54, 19.8, 1.456,
                        years((1.7, 4.4, 5.0, 5.4), (-6.4, -5.9, -2.9, -2.5), (1.0, 0.8, 0.7, 0.7)),
                        beta=1.6, pe=None, industry="Auto Manufacturers", cash=3.6, debt=5.2),
        "STALE": company("Stale Data Co", 168.0, 453.6, 2.7, acme_years, stale=True, age=200000.0),
        "PART": company("Partial Data Co", 168.0, 453.6, 2.7, acme_years[1:], beta=None, tax=None,
                        interest=None),
        "DOWN": company("Outage Co", 10.0, 10.0, 1.0, acme_years),
    },
    "fx": {"TWDUSD": 0.031, "EURUSD": 1.08, "GBPUSD": 1.27, "USDEUR": 0.93, "USDGBP": 0.79,
           "EURGBP": 0.85, "GBPEUR": 1.17},
    "peers": {"ACME": ["NOVA", "ORBT", "KSTL", "LMND"], "SAP.DE": ["ACME"], "BANK": ["ACME"],
              "LOSS": ["ACME"], "LSE.L": ["ACME"], "ADR": ["ACME"], "STALE": ["NOVA"], "PART": ["NOVA"]},
    "errors": ["DOWN"],
}

out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "fake_world.json"
out.write_text(json.dumps(world, indent=1), encoding="utf-8")
print("wrote", out)
