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


THUMB_BASE_WIDTH = 360  # 2x the 180px grid cell — scale-1 / HiDPI-ready
THUMB_BASE_HEIGHT = 540
THUMB_QUALITY = 85
CACHE_DIR = Path.home() / ".cache" / "hermitage" / "thumbs"

# Display scale factor (1 on a standard display; 2/3 on HiDPI, and the integer
# GTK renders at under Hyprland fractional scaling — get_scale_factor() is
# always an integer). Covers are cached per-tier under thumbs/<scale>/ so a 2x
# display gets 2x-denser thumbnails instead of an upscaled 1x cache. app.py
# seeds this from the window; individual binds pass their own cell's scale.
_default_scale = 1
_default_scale_lock = threading.Lock()


def set_default_scale(scale: int) -> None:
    """Set the fallback scale used when a request omits one (from the window)."""
    global _default_scale
    with _default_scale_lock:
        _default_scale = max(1, int(scale))


def _resolve_scale(scale: int | None) -> int:
    if scale is None:
        with _default_scale_lock:
            return _default_scale
    return max(1, int(scale))


def _thumb_dims(scale: int) -> tuple[int, int]:
    """Thumbnail pixel size for an integer display scale factor (pure)."""
    s = max(1, int(scale))
    return (THUMB_BASE_WIDTH * s, THUMB_BASE_HEIGHT * s)


# In-memory texture cache — holds decoded Gdk.Textures so bind() never
# touches disk for recently-seen covers. Bounded by BYTES, not entries:
# one 2x texture is ~3.1 MB decoded (720x1080x4) against ~0.8 MB at 1x,
# so the old 512-entry ceiling alone let the cache reach ~1.6 GB on a
# HiDPI display. 512 MiB keeps several screenfuls resident at any scale.
# Keyed by (cover, scale): the same cover at 1x and 2x are distinct
# textures.
_TEXTURE_CACHE_MAX_BYTES = 512 * 1024 * 1024
# Secondary ceiling for tiny textures, so the LRU cannot grow without
# bound on entries alone either.
_TEXTURE_CACHE_MAX_ENTRIES = 4096
_texture_cache: OrderedDict[tuple[Path, int], Gdk.Texture] = OrderedDict()
_texture_bytes_cached = 0
_texture_lock = threading.Lock()

# Interactive requests (visible cells, Codex hero) get their own pool so they
# never queue behind the few thousand fire-and-forget warm_cache() jobs — on a
# cold cache that starvation kept the first screen of covers blank for minutes.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hermitage-thumb")
_warm_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="hermitage-thumb-warm"
)

# In-flight async requests: (cover, scale) -> callbacks awaiting it. Duplicate
# requests coalesce into one decode, but every caller still gets its callback
# (the grid cell and the Codex hero can race for the same cover).
_pending: dict[tuple[Path, int], list] = {}
_pending_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


def _thumb_path(cover: Path, scale: int) -> Path:
    """Deterministic cache path based on source path + mtime, per scale tier."""
    stat = cover.stat()
    key = f"{cover}:{stat.st_mtime_ns}:{stat.st_size}"
    digest = hashlib.blake2b(key.encode(), digest_size=16).hexdigest()
    return CACHE_DIR / str(scale) / f"{digest}.jpg"


def _generate_thumbnail(cover: Path, scale: int) -> Path | None:
    """Write a thumbnail to disk if it doesn't already exist."""
    try:
        thumb = _thumb_path(cover, scale)
    except OSError as exc:
        _warn_once(cover, f"stat failed ({exc})")
        return None

    if thumb.is_file():
        return thumb

    try:
        if cover.stat().st_size == 0:
            _warn_once(cover, "zero-byte file")
            return None
        thumb.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(cover) as img:
            img.thumbnail(_thumb_dims(scale), Image.LANCZOS)
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


def get_cached_texture(cover: Path, scale: int | None = None) -> Gdk.Texture | None:
    """Return a cached texture if available. O(1), no I/O, main-thread safe."""
    key = (cover, _resolve_scale(scale))
    with _texture_lock:
        tex = _texture_cache.get(key)
        if tex is not None:
            _texture_cache.move_to_end(key)
        return tex


def _texture_size_bytes(texture) -> int:
    """Approximate decoded size of a texture (RGBA in video memory)."""
    return texture.get_width() * texture.get_height() * 4


def _store_texture(cover: Path, scale: int, texture):
    """Insert a texture into the byte-bounded LRU, evicting oldest-first."""
    global _texture_bytes_cached
    key = (cover, scale)
    size = _texture_size_bytes(texture)
    with _texture_lock:
        replaced = _texture_cache.pop(key, None)
        if replaced is not None:
            _texture_bytes_cached -= _texture_size_bytes(replaced)
        _texture_cache[key] = texture
        _texture_cache.move_to_end(key)
        _texture_bytes_cached += size
        while _texture_cache and (
            _texture_bytes_cached > _TEXTURE_CACHE_MAX_BYTES
            or len(_texture_cache) > _TEXTURE_CACHE_MAX_ENTRIES
        ):
            _, evicted = _texture_cache.popitem(last=False)
            _texture_bytes_cached -= _texture_size_bytes(evicted)


# ---------------------------------------------------------------------------
# Async pipeline: generate thumbnail -> decode texture -> deliver to main
# ---------------------------------------------------------------------------


def request_texture(cover: Path, callback, scale: int | None = None):
    """Request a Gdk.Texture for *cover* asynchronously.

    *callback(cover, texture_or_None)* is invoked on the **main thread**
    via GLib.idle_add.  Duplicate requests for the same cover+scale coalesce
    into a single decode, but every registered callback is delivered.
    """
    scale = _resolve_scale(scale)
    key = (cover, scale)
    with _pending_lock:
        waiters = _pending.get(key)
        if waiters is not None:
            waiters.append(callback)
            return
        _pending[key] = [callback]

    def _work():
        try:
            thumb = _generate_thumbnail(cover, scale)
            texture = _load_texture(thumb) if thumb else None
            if texture:
                _store_texture(cover, scale, texture)
        except Exception:
            texture = None
        finally:
            with _pending_lock:
                callbacks = _pending.pop(key, [])

        def _deliver():
            for cb in callbacks:
                cb(cover, texture)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(_deliver)

    _executor.submit(_work)


def warm_cache(covers: list[Path], progress=None, scale: int | None = None):
    """Pre-generate disk thumbnails for a batch of covers (fire-and-forget).

    If *progress* is given, it is invoked on the **main thread** as
    ``progress(done, total)`` — once per ~32 completions plus a final call.
    """
    scale = _resolve_scale(scale)
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
            _generate_thumbnail(cover, scale)
        finally:
            if progress is not None:
                with counter_lock:
                    counter["done"] += 1
                    done = counter["done"]
                if done == total or done % 32 == 0:
                    GLib.idle_add(progress, done, total)

    for cover in covers:
        _warm_executor.submit(_track, cover)


def shutdown() -> None:
    """Stop both pools, cancelling queued work (called on app shutdown).

    concurrent.futures joins its workers at interpreter exit, so without
    this a quit drains the whole multi-thousand-job warm_cache() queue
    before the process dies.
    """
    _executor.shutdown(cancel_futures=True)
    _warm_executor.shutdown(cancel_futures=True)
