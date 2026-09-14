"""Dominant color extraction from cover art for UI tinting."""

from __future__ import annotations

import colorsys
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageFile, UnidentifiedImageError

# Match thumbnailer: don't bail on truncated JPEGs.
ImageFile.LOAD_TRUNCATED_IMAGES = True

_warned_books: set[int] = set()
_warn_lock = threading.Lock()


def _warn_once(book_id: int, cover: Path, reason: str) -> None:
    with _warn_lock:
        if book_id in _warned_books:
            return
        _warned_books.add(book_id)
    print(
        f"hermitage: color extraction skipped for book {book_id} ({cover}): {reason}",
        file=sys.stderr,
    )


CACHE_DIR = Path.home() / ".cache" / "hermitage" / "colors"
SAMPLE_SIZE = (64, 64)  # Downsample before analysis for speed
NUM_COLORS = 5  # Top N dominant colors to extract

# Like the thumbnailer: interactive requests get their own pool so visible
# cells never queue behind the whole-library warm_color_cache() sweep.
# Both pools live until HermitageApp.do_shutdown calls shutdown().
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hermitage-color")
_warm_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="hermitage-color-warm"
)
# In-flight extraction results, keyed by book id and holding the cover
# fingerprint the colors were computed from: (fingerprint, colors). A
# replaced cover changes the fingerprint and the next extraction
# recomputes instead of serving the stale glow.
_color_cache: dict[int, tuple[str | None, list[tuple[int, int, int]]]] = {}
_cache_lock = threading.Lock()


def _quantize_colors(cover: Path) -> list[tuple[int, int, int]]:
    """Extract dominant colors via Pillow's quantize (median-cut)."""
    with Image.open(cover) as img:
        img = img.convert("RGB").resize(SAMPLE_SIZE, Image.LANCZOS)
        quantized = img.quantize(colors=NUM_COLORS, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette() or []
        # Palette is a flat [R,G,B, R,G,B, ...] list. Pillow may shrink it
        # below NUM_COLORS for a uniform image, so stop at what is really
        # there instead of indexing into the void.
        colors = []
        for i in range(NUM_COLORS):
            offset = i * 3
            if offset + 2 >= len(palette):
                break
            colors.append((palette[offset], palette[offset + 1], palette[offset + 2]))
    return colors


def _sort_by_vibrancy(colors: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Sort colors by saturation * value (most vibrant first)."""

    def score(rgb):
        h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
        return s * v

    return sorted(colors, key=score, reverse=True)


def _cover_fingerprint(cover: Path) -> str | None:
    """mtime+size fingerprint of a cover file, or None when it cannot stat.

    Keys the color caches so a replaced cover regenerates its palette
    instead of keeping the old glow color forever.
    """
    try:
        stat = cover.stat()
    except OSError:
        return None
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def _cache_path(book_id: int, fingerprint: str) -> Path:
    return CACHE_DIR / f"{book_id}-{fingerprint}.json"


def _load_disk_cache(
    book_id: int, fingerprint: str
) -> list[tuple[int, int, int]] | None:
    p = _cache_path(book_id, fingerprint)
    if p.is_file():
        try:
            data = json.loads(p.read_text())
            return [tuple(c) for c in data]
        except Exception:
            return None
    return None


def _save_disk_cache(
    book_id: int, fingerprint: str, colors: list[tuple[int, int, int]]
):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(book_id, fingerprint).write_text(json.dumps(colors))


def extract_colors_sync(book_id: int, cover: Path) -> list[tuple[int, int, int]]:
    """Extract and cache dominant colors. Safe to call from any thread.

    Both caches are keyed by the cover's mtime+size fingerprint: a cover
    replaced on disk gets fresh colors instead of the old glow.
    """
    fingerprint = _cover_fingerprint(cover)

    # Memory cache
    with _cache_lock:
        hit = _color_cache.get(book_id)
        if hit is not None and hit[0] == fingerprint:
            return hit[1]

    # Disk cache
    if fingerprint is not None:
        cached = _load_disk_cache(book_id, fingerprint)
        if cached is not None:
            with _cache_lock:
                _color_cache[book_id] = (fingerprint, cached)
            return cached

    # Extract
    if not cover.is_file():
        return []
    try:
        if cover.stat().st_size == 0:
            _warn_once(book_id, cover, "zero-byte file")
            return []
        colors = _sort_by_vibrancy(_quantize_colors(cover))
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as exc:
        _warn_once(book_id, cover, f"{type(exc).__name__}: {exc}")
        return []
    if fingerprint is not None:
        _save_disk_cache(book_id, fingerprint, colors)
    with _cache_lock:
        _color_cache[book_id] = (fingerprint, colors)
    return colors


def get_cached_colors(book_id: int) -> list[tuple[int, int, int]] | None:
    """Return colors if already in memory. No I/O."""
    with _cache_lock:
        hit = _color_cache.get(book_id)
        return hit[1] if hit is not None else None


def request_colors(book_id: int, cover: Path, callback):
    """Extract colors async. callback(book_id, colors) on the main thread."""
    from gi.repository import GLib

    def _work():
        colors = extract_colors_sync(book_id, cover)

        def _deliver():
            callback(book_id, colors)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(_deliver)

    _executor.submit(_work)


def warm_color_cache(books):
    """Pre-extract colors for all books with covers (fire-and-forget)."""
    for b in books:
        cover = b.cover_path
        if cover and cover.is_file():
            _warm_executor.submit(extract_colors_sync, b.id, cover)


def shutdown() -> None:
    """Stop both pools, cancelling queued work (called on app shutdown).

    concurrent.futures joins its workers at interpreter exit, so without
    this a quit drains the whole-library warm queue before the process
    dies.
    """
    _executor.shutdown(cancel_futures=True)
    _warm_executor.shutdown(cancel_futures=True)
