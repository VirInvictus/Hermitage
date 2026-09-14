"""Tests for the in-memory texture LRU's byte budget.

Textures are faked with plain objects exposing get_width/get_height —
_store_texture only consults those — so the eviction math runs headless
with no Gdk surfaces involved.
"""

import unittest
from pathlib import Path
from unittest import mock

from hermitage import thumbnailer


class _FakeTexture:
    def __init__(self, w, h):
        self._w = w
        self._h = h

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h


class TestTextureLruByteCap(unittest.TestCase):
    """The texture cache is bounded by decoded bytes, not entry count.

    Regression (final audit 2026-09-13): the 512-entry ceiling alone let
    the cache reach ~1.6 GB on a 2x display (512 x ~3.1 MB textures).
    """

    def setUp(self):
        # Tiny budget: one 100x100 fake texture accounts 40,000 bytes.
        for target, value in (
            ("_TEXTURE_CACHE_MAX_BYTES", 100_000),
            ("_TEXTURE_CACHE_MAX_ENTRIES", 100),
        ):
            patcher = mock.patch(f"hermitage.thumbnailer.{target}", value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        thumbnailer._texture_cache.clear()
        thumbnailer._texture_bytes_cached = 0
        self.addCleanup(thumbnailer._texture_cache.clear)
        self.addCleanup(setattr, thumbnailer, "_texture_bytes_cached", 0)

    def test_eviction_keeps_bytes_under_budget(self):
        for i in range(5):
            thumbnailer._store_texture(Path(f"/cov/{i}.jpg"), 1, _FakeTexture(100, 100))
        self.assertLessEqual(thumbnailer._texture_bytes_cached, 100_000)
        # Oldest entries evicted, the newest resident.
        self.assertNotIn((Path("/cov/0.jpg"), 1), thumbnailer._texture_cache)
        self.assertIn((Path("/cov/4.jpg"), 1), thumbnailer._texture_cache)

    def test_replacing_a_key_accounts_the_old_size(self):
        thumbnailer._store_texture(Path("/cov/a.jpg"), 1, _FakeTexture(100, 100))
        thumbnailer._store_texture(Path("/cov/a.jpg"), 1, _FakeTexture(10, 10))
        self.assertEqual(thumbnailer._texture_bytes_cached, 400)

    def test_get_cached_texture_roundtrip(self):
        tex = _FakeTexture(10, 10)
        thumbnailer._store_texture(Path("/cov/a.jpg"), 2, tex)
        self.assertIs(thumbnailer.get_cached_texture(Path("/cov/a.jpg"), 2), tex)
        self.assertIsNone(thumbnailer.get_cached_texture(Path("/cov/x.jpg"), 2))


if __name__ == "__main__":
    unittest.main()
