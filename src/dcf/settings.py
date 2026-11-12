"""Environment-driven settings and provider construction."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from .data.provider import DataProvider


@dataclass(frozen=True)
class Settings:
    fred_key: str | None
    finnhub_key: str | None
    cache_path: str
    provider: str  # "live" | "fake"
    fake_world: str | None


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        fred_key=env.get("FRED_API_KEY") or None,
        finnhub_key=env.get("FINNHUB_API_KEY") or None,
        cache_path=env.get("DCF_CACHE_PATH", "./dcf-cache.sqlite"),
        provider=env.get("DCF_PROVIDER", "live"),
        fake_world=env.get("DCF_FAKE_WORLD") or None,
    )


def build_provider(settings: Settings) -> DataProvider:
    if settings.provider == "fake":
        from .data.fake import load_fake_world

        if not settings.fake_world:
            raise ValueError("DCF_FAKE_WORLD must point to a world JSON file when DCF_PROVIDER=fake")
        return load_fake_world(settings.fake_world)
    from .data.cache import SqliteCache
    from .data.live import LiveProvider
    from .data.yahoo import YahooProvider

    cache = SqliteCache(settings.cache_path)
    return LiveProvider(YahooProvider(cache), settings.fred_key, settings.finnhub_key, cache)
