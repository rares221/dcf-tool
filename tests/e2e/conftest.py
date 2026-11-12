"""Browser test harness: the real app served over HTTP with the fake data provider.

Uses the system Edge via Playwright (no browser download); falls back to bundled Chromium.
"""
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from dcf.api import create_app
from dcf.data.fake import load_fake_world

WORLD = Path(__file__).resolve().parents[1] / "fixtures" / "fake_world.json"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(load_fake_world(str(WORLD))), host="127.0.0.1",
                                           port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception:
            try:
                b = p.chromium.launch()
            except Exception as exc:  # pragma: no cover
                pytest.skip(f"no browser available: {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    ctx = browser.new_context(locale="en-US", viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    pg.goto(base_url)
    yield pg
    ctx.close()


def search(page, ticker: str):
    page.fill("#ticker", ticker)
    page.press("#ticker", "Enter")
