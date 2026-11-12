"""Small SQLite key/value cache with a TTL and stale reads."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CacheEntry:
    value: dict
    age_seconds: float


class SqliteCache:
    def __init__(self, path: str, ttl_seconds: float = 86400, clock: Callable[[], float] = time.time):
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, stored_at REAL NOT NULL)"
        )
        self._db.commit()

    def get(self, key: str, allow_stale: bool = False) -> CacheEntry | None:
        with self._lock:
            row = self._db.execute("SELECT value, stored_at FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        age = self._clock() - row[1]
        if age > self._ttl and not allow_stale:
            return None
        return CacheEntry(json.loads(row[0]), age)

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO cache (key, value, stored_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, stored_at = excluded.stored_at",
                (key, json.dumps(value), self._clock()),
            )
            self._db.commit()
