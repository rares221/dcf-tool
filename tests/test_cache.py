from dcf.data.cache import SqliteCache


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_get_within_ttl_returns_value_and_age():
    clock = Clock()
    cache = SqliteCache(":memory:", ttl_seconds=100, clock=clock)
    cache.put("k", {"a": 1})
    clock.now += 40
    entry = cache.get("k")
    assert entry.value == {"a": 1} and entry.age_seconds == 40


def test_expired_entry_hidden_unless_stale_allowed():
    clock = Clock()
    cache = SqliteCache(":memory:", ttl_seconds=100, clock=clock)
    cache.put("k", {"a": 1})
    clock.now += 500
    assert cache.get("k") is None
    stale = cache.get("k", allow_stale=True)
    assert stale.value == {"a": 1} and stale.age_seconds == 500


def test_missing_key_is_none():
    assert SqliteCache(":memory:").get("nope", allow_stale=True) is None


def test_overwrite_replaces_value_and_resets_age():
    clock = Clock()
    cache = SqliteCache(":memory:", ttl_seconds=100, clock=clock)
    cache.put("k", {"v": 1})
    clock.now += 90
    cache.put("k", {"v": 2})
    clock.now += 50
    assert cache.get("k").value == {"v": 2}


def test_two_caches_share_a_file(tmp_path):
    path = str(tmp_path / "c.sqlite")
    SqliteCache(path).put("k", {"x": 1})
    assert SqliteCache(path).get("k").value == {"x": 1}
