"""Thumbnail cache for cover art — disk cache + in-memory texture LRU."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib

from PIL import Image

THUMB_WIDTH = 360   # 2x grid cell for HiDPI
THUMB_HEIGHT = 540
THUMB_QUALITY = 85
CACHE_DIR = Path.home() / ".cache" / "hermitage" / "thumbs"

# In-memory texture cache — holds decoded Gdk.Textures so bind() never
# touches disk for recently-seen covers.  512 entries ≈ 4-5 screenfuls.
_TEXTURE_CACHE_MAX = 512
_texture_cache: OrderedDict[Path, Gdk.Texture] = OrderedDict()
_texture_lock = threading.Lock()

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hermitage-thumb")

# Tracks in-flight async requests to avoid duplicate work
_pending: set[Path] = set()
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
        if thumb.is_file():
            return thumb
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with Image.open(cover) as img:
            img.thumbnail((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(thumb, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return thumb
    except Exception:
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
    via GLib.idle_add.  Duplicate requests for the same cover are coalesced.
    """
    with _pending_lock:
        if cover in _pending:
            return
        _pending.add(cover)

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
                _pending.discard(cover)

        def _deliver():
            callback(cover, texture)
            return GLib.SOURCE_REMOVE
        GLib.idle_add(_deliver)

    _executor.submit(_work)


def warm_cache(covers: list[Path]):
    """Pre-generate disk thumbnails for a batch of covers (fire-and-forget)."""
    for cover in covers:
        _executor.submit(_generate_thumbnail, cover)
