"""Defaults and limits. All are labelled assumptions in the UI."""
EQUITY_RISK_PREMIUM = 4.5
DEFAULT_TERMINAL_GROWTH = 2.5
DEFAULT_TAX_RATE = 21.0
DEFAULT_COST_OF_DEBT = 5.0
HORIZONS = (3, 5, 10)
UNEVEN_GROWTH_SPREAD = 15.0  # percentage points between the best and worst year before growth is called uneven
TERMINAL_GROWTH_STEP = 0.25  # the slider step; the cap on terminal growth is rounded down to it
DEFAULT_HORIZON = 5

# Wider than the mockup so more real companies fit (plan decision).
SLIDER_LIMITS: dict[str, tuple[float, float]] = {
    "growth": (-10, 30),
    "fcf_margin": (1, 60),
    "wacc": (5, 16),
    "terminal_growth": (0, 4),
}
