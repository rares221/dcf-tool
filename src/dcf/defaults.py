"""Defaults and limits. All are labelled assumptions in the UI."""
EQUITY_RISK_PREMIUM = 4.5
DEFAULT_TERMINAL_GROWTH = 2.5
DEFAULT_TAX_RATE = 21.0
DEFAULT_COST_OF_DEBT = 5.0
HORIZONS = (3, 5, 10)
DEFAULT_HORIZON = 5

# Wider than the mockup so more real companies fit (plan decision).
SLIDER_LIMITS: dict[str, tuple[float, float]] = {
    "growth": (-10, 30),
    "fcf_margin": (1, 60),
    "wacc": (5, 16),
    "terminal_growth": (0, 4),
}
