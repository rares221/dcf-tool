"""HTTP API: two JSON endpoints plus the static page."""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, model_validator

from .data.provider import DataProvider
from .defaults import HORIZONS, SLIDER_LIMITS
from .service import analyze, model_inputs, run_model
from .settings import build_provider, load_settings
from .types import Assumptions

log = logging.getLogger("dcf")

# Some Windows registries map .js to text/plain, which browsers reject for module scripts.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
WEB_DIR = Path(__file__).parent / "web"


class ModelRequest(BaseModel):
    ticker: str
    horizon: int
    growth: float
    fcf_margin: float
    wacc: float
    terminal_growth: float
    count_sbc: bool = True

    @model_validator(mode="after")
    def _check(self):
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        for key in ("growth", "fcf_margin", "wacc", "terminal_growth"):
            lo, hi = SLIDER_LIMITS[key]
            if not lo <= getattr(self, key) <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}")
        if self.wacc < self.terminal_growth + 1:
            raise ValueError("discount rate must be at least 1 point above long-term growth")
        return self


def create_app(provider: DataProvider | None = None) -> FastAPI:
    provider = provider or build_provider(load_settings())
    app = FastAPI(title="DCF tool")

    @app.get("/api/analyze")
    def api_analyze(ticker: str, peers: str | None = Query(default=None)):
        peer_list = None if peers is None else [p for p in (s.strip() for s in peers.split(",")) if p]
        try:
            return analyze(ticker, provider, peer_list)
        except Exception:  # designed error state instead of a stack trace
            log.exception("analyze failed for %r", ticker)
            return {"status": "error"}

    @app.post("/api/model")
    def api_model(req: ModelRequest):
        try:
            status, inputs = model_inputs(req.ticker, provider)
            if inputs is None:
                return {"status": status}
            a = Assumptions(req.growth, req.fcf_margin, req.wacc, req.terminal_growth)
            return {"status": "ok", **run_model(inputs, a, req.horizon, req.count_sbc)}
        except Exception:
            log.exception("model failed for %r", req.ticker)
            return {"status": "error"}

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app
