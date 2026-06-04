from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from capacitychecker.cache import CacheError, CacheStore


class CacheStoreTests(unittest.TestCase):
    def test_reads_fresh_entry(self) -> None:
        now = 1000.0
        with TemporaryDirectory() as temp_dir:
            cache = CacheStore(Path(temp_dir), now=lambda: now)
            cache.set("resource-skus", {"region": "eastus"}, [{"name": "Standard_D2s_v5"}], ttl_seconds=60)

            cached = cache.get("resource-skus", {"region": "eastus"})

        self.assertIsNotNone(cached)
        self.assertEqual(cached.value, [{"name": "Standard_D2s_v5"}])
        self.assertEqual(cached.age_seconds, 0)

    def test_expired_entry_returns_miss(self) -> None:
        now = 1000.0
        with TemporaryDirectory() as temp_dir:
            cache = CacheStore(Path(temp_dir), now=lambda: now)
            cache.set("usage", {"region": "eastus"}, [], ttl_seconds=1)
            now = 1002.0

            self.assertIsNone(cache.get("usage", {"region": "eastus"}))

    def test_clear_removes_entries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cache = CacheStore(Path(temp_dir), now=lambda: 1000.0)
            cache.set("usage", {"region": "eastus"}, [], ttl_seconds=60)

            self.assertEqual(cache.clear(), 1)
            self.assertEqual(cache.describe(), [])

    def test_invalid_entry_raises_cache_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            bad_entry = cache_dir / "usage" / "bad.json"
            bad_entry.parent.mkdir(parents=True)
            bad_entry.write_text("{not-json", encoding="utf-8")
            cache = CacheStore(cache_dir, now=lambda: 1000.0)

            with self.assertRaises(CacheError):
                cache.describe()


if __name__ == "__main__":
    unittest.main()
