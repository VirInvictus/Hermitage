"""Thumbnail cache for cover art — disk cache + in-memory texture LRU."""

from __future__ import annotations

import hashlib
import sys
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib

from PIL import Image, ImageFile, UnidentifiedImageError

# Tolerate partially-downloaded / truncated cover JPEGs — Pillow will yield
# whatever scanlines it managed to decode rather than throwing.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Paths we've already warned about, so a recycled cell doesn't spam stderr.
_warned_paths: set[Path] = set()
_warn_lock = threading.Lock()


def _warn_once(cover: Path, reason: str) -> None:
    with _warn_lock:
        if cover in _warned_paths:
            return
        _warned_paths.add(cover)
    print(f"hermitage: skipping cover {cover}: {reason}", file=sys.stderr)


THUMB_WIDTH = 360  # 2x grid cell for HiDPI
THUMB_HEIGHT = 540
THUMB_QUALITY = 85
CACHE_DIR = Path.home() / ".cache" / "hermitage" / "thumbs"

# In-memory texture cache — holds decoded Gdk.Textures so bind() never
# touches disk for recently-seen covers.  512 entries ≈ 4-5 screenfuls.
_TEXTURE_CACHE_MAX = 512
_texture_cache: OrderedDict[Path, Gdk.Texture] = OrderedDict()
_texture_lock = threading.Lock()

# Interactive requests (visible cells, Codex hero) get their own pool so they
# never queue behind the few thousand fire-and-forget warm_cache() jobs — on a
# cold cache that starvation kept the first screen of covers blank for minutes.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hermitage-thumb")
_warm_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="hermitage-thumb-warm"
)

# In-flight async requests: cover path -> callbacks awaiting it. Duplicate
# requests coalesce into one decode, but every caller still gets its callback
# (the grid cell and the Codex hero can race for the same cover).
_pending: dict[Path, list] = {}
_pending_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


def _thumb_path(cover: Path) -> Path:
    """Deterministic cache path based on source path + mtime."""
    stat = cover.stat()
    key = f"{cover}:{stat.st_mtime_ns}:{stat.st_size}"
    digest = hashlib.blake2b(key.encode(), digest_size=16).hexdigest()
    return CACHE_DIR / f"{digest}.jpg"


def _generate_thumbnail(cover: Path) -> Path | None:
    """Write a thumbnail to disk if it doesn't already exist."""
    try:
        thumb = _thumb_path(cover)
    except OSError as exc:
        _warn_once(cover, f"stat failed ({exc})")
        return None

    if thumb.is_file():
        return thumb

    try:
        if cover.stat().st_size == 0:
            _warn_once(cover, "zero-byte file")
            return None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with Image.open(cover) as img:
            img.thumbnail((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(thumb, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return thumb
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        _warn_once(cover, f"thumbnail failed ({type(exc).__name__}: {exc})")
        return None


def _load_texture(thumb: Path) -> Gdk.Texture | None:
    """Load a thumbnail into a Gdk.Texture (thread-safe)."""
    try:
        return Gdk.Texture.new_from_filename(str(thumb))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# In-memory texture cache
# ---------------------------------------------------------------------------


def get_cached_texture(cover: Path) -> Gdk.Texture | None:
    """Return a cached texture if available. O(1), no I/O, main-thread safe."""
    with _texture_lock:
        tex = _texture_cache.get(cover)
        if tex is not None:
            _texture_cache.move_to_end(cover)
        return tex


def _store_texture(cover: Path, texture: Gdk.Texture):
    """Insert a texture into the LRU cache, evicting the oldest if full."""
    with _texture_lock:
        _texture_cache[cover] = texture
        _texture_cache.move_to_end(cover)
        while len(_texture_cache) > _TEXTURE_CACHE_MAX:
            _texture_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Async pipeline: generate thumbnail -> decode texture -> deliver to main
# ---------------------------------------------------------------------------


def request_texture(cover: Path, callback):
    """Request a Gdk.Texture for *cover* asynchronously.

    *callback(cover, texture_or_None)* is invoked on the **main thread**
    via GLib.idle_add.  Duplicate requests for the same cover coalesce into a
    single decode, but every registered callback is delivered.
    """
    with _pending_lock:
        waiters = _pending.get(cover)
        if waiters is not None:
            waiters.append(callback)
            return
        _pending[cover] = [callback]

    def _work():
        try:
            thumb = _generate_thumbnail(cover)
            texture = _load_texture(thumb) if thumb else None
            if texture:
                _store_texture(cover, texture)
        except Exception:
            texture = None
        finally:
            with _pending_lock:
                callbacks = _pending.pop(cover, [])

        def _deliver():
            for cb in callbacks:
                cb(cover, texture)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(_deliver)

    _executor.submit(_work)


def warm_cache(covers: list[Path], progress=None):
    """Pre-generate disk thumbnails for a batch of covers (fire-and-forget).

    If *progress* is given, it is invoked on the **main thread** as
    ``progress(done, total)`` — once per ~32 completions plus a final call.
    """
    total = len(covers)
    if total == 0:
        if progress:
            GLib.idle_add(progress, 0, 0)
        return

    counter = {"done": 0}
    counter_lock = threading.Lock()

    def _track(cover: Path):
        # The counter must advance even if generation throws, or the
        # "indexing covers (N%)" subtitle sticks below 100% forever.
        try:
            _generate_thumbnail(cover)
        finally:
            if progress is not None:
                with counter_lock:
                    counter["done"] += 1
                    done = counter["done"]
                if done == total or done % 32 == 0:
                    GLib.idle_add(progress, done, total)

    for cover in covers:
        _warm_executor.submit(_track, cover)
