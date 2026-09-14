"""Tests for the cache layers: the texture LRU's byte budget, the disk
budget sweep, the color cache's cover fingerprint, and Pillow's
DecompressionBombError staying inside the image handlers.

Textures are faked with plain objects exposing get_width/get_height —
_store_texture only consults those — so the eviction math runs headless
with no Gdk surfaces involved.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from hermitage import colors, thumbnailer


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


class TestEnforceCacheBudget(unittest.TestCase):
    """The disk sweep deletes oldest-files-first until the dir fits."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _file(self, name, size, mtime):
        p = self.root / name
        p.write_bytes(b"x" * size)
        os.utime(p, (mtime, mtime))
        return p

    def test_evicts_oldest_first_until_under_budget(self):
        old = self._file("old.jpg", 600, 1_000_000_000)
        keep = self._file("new.jpg", 600, 2_000_000_000)
        thumbnailer.enforce_cache_budget(self.root, 1_000)
        self.assertFalse(old.exists())
        self.assertTrue(keep.exists())

    def test_under_budget_is_a_noop(self):
        a = self._file("a.jpg", 10, 1)
        thumbnailer.enforce_cache_budget(self.root, 1_000_000)
        self.assertTrue(a.exists())

    def test_missing_dir_is_fine(self):
        thumbnailer.enforce_cache_budget(self.root / "nope", 100)


class TestColorCacheStaleness(unittest.TestCase):
    """Color caches key on the cover's mtime+size fingerprint.

    Regression (final audit 2026-09-13): keyed by book id alone, a
    replaced cover kept the old glow color forever.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = mock.patch("hermitage.colors.CACHE_DIR", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._old_cache = colors._color_cache
        colors._color_cache = {}
        self.addCleanup(setattr, colors, "_color_cache", self._old_cache)

    def _cover(self, name, rgb):
        p = self.root / name
        Image.new("RGB", (8, 8), rgb).save(p)
        return p

    def test_replaced_cover_gets_new_colors(self):
        cover = self._cover("c.png", (255, 0, 0))
        first = colors.extract_colors_sync(1, cover)
        self.assertEqual(first[0], (255, 0, 0))
        # Replace with a blue cover, bumped past the old mtime: the
        # fingerprint changes, so the red entry is not served again.
        Image.new("RGB", (8, 8), (0, 0, 255)).save(cover)
        st = os.stat(cover)
        os.utime(cover, (st.st_atime, st.st_mtime + 10))
        second = colors.extract_colors_sync(1, cover)
        self.assertEqual(second[0], (0, 0, 255))


class TestDecompressionBombHandled(unittest.TestCase):
    """The image handlers catch DecompressionBombError like other bad
    images instead of letting it escape (it subclasses Exception, not
    any of the previously caught types)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cover = Path(tmp.name) / "c.jpg"
        Image.new("RGB", (2, 2)).save(self.cover)

    def test_thumbnailer(self):
        with mock.patch.object(
            thumbnailer.Image,
            "open",
            side_effect=thumbnailer.Image.DecompressionBombError,
        ):
            self.assertIsNone(thumbnailer._generate_thumbnail(self.cover, 1))

    def test_colors(self):
        with mock.patch.object(
            colors.Image,
            "open",
            side_effect=colors.Image.DecompressionBombError,
        ):
            self.assertEqual(colors.extract_colors_sync(1, self.cover), [])

    def test_codex_blur(self):
        from hermitage import codex

        with mock.patch("PIL.Image.open", side_effect=Image.DecompressionBombError):
            self.assertIsNone(codex._generate_blurred_cover(self.cover))


if __name__ == "__main__":
    unittest.main()
