# Hermitage — Patch Notes

## v0.6.0 (2026-04-10) — Phase 3 Complete

---

### New Features

**The Codex — premium book detail view.** Clicking (activating) any book in
the grid now slides open a detail sidebar via `Adw.OverlaySplitView`. The
sidebar is positioned on the right edge with `min_sidebar_width=360` and
`max_sidebar_width=460`. The split view starts hidden and is shown on grid
item activation (click or Enter). Clicking a different book while the sidebar
is open repopulates it in-place without closing.

**Hero banner with blurred cover background.** The top of the Codex features
a 280px hero section built as a `Gtk.Overlay`. The background is a
Pillow-generated blurred and darkened version of the book's cover art
(GaussianBlur radius 30, brightness reduced to 35%). Blurred images are cached
in `~/.cache/hermitage/blur/` using BLAKE2b hashes of path + mtime + size,
matching the thumbnailer's cache invalidation strategy. Generation runs async
in a 2-thread pool and is delivered to the main thread via `GLib.idle_add`
with a stale-book guard.

Overlaid on the blur: a 110x165 mini cover thumbnail (reusing the existing
texture cache) in a rounded `AspectFrame` with drop shadow, plus title, author,
and series typography rendered in white with text shadows for legibility against
any cover palette.

**Tag pills via `Gtk.FlowBox`.** Tags from the Calibre database are rendered
as individually styled pill badges in a wrapping flow layout. Each pill uses
`border-radius: 99px` with the system accent color at 15% opacity for the
background and full accent for the text. The FlowBox has `selection-mode: none`
and 6px row/column spacing. FlowBoxChild padding is zeroed out so the pills
control their own geometry.

**Styled synopsis with `Adw.Clamp`.** The book's HTML comments are cleaned
(HTML tag stripping, entity decoding, whitespace normalization) and rendered in
a selectable `Gtk.Label` with the Libadwaita `.body` class. The entire body
section is wrapped in `Adw.Clamp(maximum_size=600, tightening_threshold=400)`
for comfortable reading width on wide sidebars.

**"Read" button with `Gtk.FileLauncher`.** A prominent `suggested-action` pill
button labeled "Read" launches the book in the system's default reader. Format
selection follows a priority order (EPUB > PDF > MOBI > AZW3 > CBZ > CBR >
DJVU > TXT) and resolves actual files by globbing the book's Calibre directory.
`Gtk.FileLauncher` delegates to the desktop's registered MIME handler (Foliate,
Papers, Evince, etc.).

**Metadata density.** The Codex body displays:
- Star rating (Calibre's 0-10 scale mapped to 5 Unicode stars)
- Series name with index (e.g., "The First Law #1")
- Available formats as a dot-separated list
- Publication date (when present and after 101 AD)

### Structural Changes

**New module: `hermitage/codex.py`.** Self-contained detail view widget
(`CodexView`) with hero blur generation, HTML cleaning, format file resolution,
and the `Gtk.FileLauncher` integration. The module owns its own 2-thread
executor for blur generation, separate from the thumbnailer's pool.

**`app.py` architecture change.** The toolbar view's content is now an
`Adw.OverlaySplitView` wrapping the scrolled grid (content) and the
`CodexView` (sidebar), replacing the previous flat `ScrolledWindow`. A new
`_on_book_activated` handler bridges grid activation to the codex.

### Bug Fixes

**Breakpoint `add_setter` crash with `GLib.Variant`.** `add_setter` expects
`GObject.Value`, not `GLib.Variant`. The signed-int variant (`"i"`) was
silently accepted on some GTK builds but crashed with an `Adwaita-ERROR` on
GNOME 50 / Libadwaita 1.7. Replaced with `GObject.Value(GObject.TYPE_UINT)`
constructed via `set_uint()`.

---

## v0.5.0 (2026-04-10) — Phase 2 Complete

---

### New Features

**Strict cover aspect ratios — no ragged rows.** Each grid cell is now
wrapped in a `Gtk.AspectFrame` with a fixed 2:3 ratio (`obey_child=False`).
The frame is centered horizontally and top-aligned vertically, so covers of
any source dimension are uniformly constrained. The inner `Gtk.Overlay` has
`overflow: hidden` set, giving clean rounded-corner clipping without any
content bleeding past the frame boundary.

The cell widget hierarchy is now: `AspectFrame` > `Overlay` > `Picture` +
`Label`. Widget references (`_picture`, `_label`, `_overlay`) are stored on
the frame rather than the overlay, since the frame is now the `list_item`
child. Bind, unbind, and the color system all reference through `frame._*`.

**Dynamic per-cover color tinting.** The dominant color extracted by
`colors.py` is now mapped to a per-cell hover glow effect. On bind, if colors
are in the memory cache (`get_cached_colors`, zero I/O), a `CssProvider` is
created with a `box-shadow` rule using `rgba(R,G,B, 0.55)` and attached to
the display. The cell gets a `.cover-cell-active` class so the provider's
rules target only that cell.

- If colors aren't cached yet, `request_colors` fires an async extraction.
  When the callback arrives, the provider is created and applied — same
  stale-cell guard as the texture pipeline (book ID check).
- On unbind, the provider is removed from the display and the class is
  stripped. This prevents leaked providers from accumulating.
- Focus state gets a separate treatment: `box-shadow: 0 0 0 3px` ring in the
  dominant color at 60% opacity, giving keyboard navigation a per-book accent.
- The fallback (no colors) uses the global CSS `alpha(black, 0.3)` shadow.

**Responsive breakpoints via `Adw.Breakpoint`.** Two breakpoints scale the
grid to the window width:

| Condition | min-columns | max-columns | Use case |
|-----------|-------------|-------------|----------|
| < 500sp   | 2           | 3           | Phones, tight tiling |
| < 900sp   | 3           | 5           | Tablets, half-screen |
| Default   | 3           | 12          | Desktop, full-width |

Breakpoints are registered on the `Adw.ApplicationWindow` after the grid is
constructed, using `add_setter` to modify the grid's `min-columns` and
`max-columns` GObject properties reactively.

### Structural Changes

**CSS reorganized.** Hover transforms and transitions moved from `gridview >
child` to `.cover-cell` (the overlay), since the overlay is now the visual
boundary. The `.cover-frame` class handles margin. Grid child padding reduced
to 2px since the frame margin provides the spacing.

**`_load_library` refactored.** Now accepts the window directly and reads
`_toolbar_view` / `_header` from stored attributes, enabling `_setup_breakpoints`
to access both the window (for `add_breakpoint`) and the grid.

---

## v0.4.1 (2026-04-10)

---

### Bug Fixes

**Double path resolution in `load_library()`.** `_resolve_library_path()` was
called twice per load — once inside `_connect()` and once explicitly to set
`_library_root_cache`. Reordered so the cache is set first and `_connect()`
reuses it via `_library_root()`.

**FTS5 query injection via double quotes.** User input containing `"` produced
malformed FTS5 syntax (e.g., searching `he"llo` built `"he"llo"*`), causing a
silent `OperationalError` that returned zero results. Double quotes are now
stripped from search terms before query construction. An all-punctuation query
that reduces to an empty string returns early instead of hitting the database.

**`_generate_thumbnail` unhandled stat() on missing file.** `_thumb_path()`
calls `cover.stat()` to build the cache key. This was outside the try/except
block, so a cover deleted between the `is_file()` check and `stat()` raised
an unhandled `FileNotFoundError`. Moved `_thumb_path()` inside the try/except.

**`request_texture` leaked pending entries on error.** If `_generate_thumbnail`
or `_load_texture` raised, the `_pending` set was never cleaned up and the
callback never fired. That cover was silently blacklisted for the rest of the
session. Wrapped the work function in try/except/finally so `_pending` is
always cleaned and the callback always fires (with `None` on error).

**Corrupt cover images crashed color extraction threads.** `_quantize_colors()`
could raise on truncated or malformed images (Pillow `DecompressionBombError`,
`UnidentifiedImageError`, etc.), and there was no try/except in
`extract_colors_sync`. The exception propagated into the thread pool, silently
killing the task. Added a try/except around the quantize call that returns an
empty list on failure.

**Fragile widget lookup in `_bind_cover`.** `overlay.get_last_child()` was
used to find the title label, depending on the internal child insertion order
of `Gtk.Overlay`. If a second overlay child were ever added, bind would
silently cast the wrong widget. Replaced with explicit `_picture` and `_label`
attributes stored on the overlay during setup.

---

## v0.4.0 (2026-04-10) — Phase 1 Complete

---

### New Features

**FTS5 full-text search index.** `build_search_index()` constructs an
in-memory SQLite FTS5 virtual table from the loaded book list. The Calibre
database is opened read-only so the index cannot live there — instead a
separate `:memory:` connection hosts a contentless FTS5 table with
`unicode61 remove_diacritics 2` tokenization.

- Indexes four fields: title, authors, tags (dot-separated hierarchy flattened
  to spaces), and series name.
- `search()` supports prefix matching — partial words work via implicit `*`
  suffix on each term. Multiple terms are ANDed.
- Results are ranked by FTS5's built-in BM25 relevance scoring, capped at 50
  by default.
- The search index is built after library load in `_load_library()`, before
  the grid is presented.

**`hermitage-verify` CLI tool.** Standalone library integrity checker
registered as a console script in `pyproject.toml`. Validates every book's
directory path, cover file (when `has_cover=True`), and format availability.

- Reports total book count, DB load time, and path scan time.
- Groups issues into three categories: missing directories, missing cover
  files (has_cover flag disagrees with disk), and books with no format files.
- Exits with code 1 if any issues are found, 0 otherwise.
- Bench-tested: 69ms load + 59ms scan for 4,014 books, all paths OK.

**Dominant color extraction worker.** `hermitage/colors.py` extracts 5
dominant colors from each cover using Pillow's median-cut quantizer. Covers
are downsampled to 64x64 before quantization for speed (~37ms cold, 0.015ms
memory cache hit).

- Colors are sorted by vibrancy (HSV saturation * value), so the most
  visually impactful color is always first — suitable for UI accent tinting.
- Three-tier caching: in-memory dict, JSON disk cache in
  `~/.cache/hermitage/colors/`, cold extraction.
- `warm_color_cache()` submits all covers to the thread pool at startup
  (fire-and-forget), same pattern as thumbnail warming.
- `request_colors()` provides async extraction with `GLib.idle_add` delivery
  for use in grid cell binding.
- `get_cached_colors()` is a zero-I/O memory lookup for the bind fast path.

### Integration

The app's `_load_library()` now calls `build_search_index(books)` and
`warm_color_cache(books)` alongside the existing `warm_cache(covers)`,
so all three background systems begin populating as soon as the library
is loaded.

---

## v0.3.0 (2026-04-10)

---

### Performance

**In-memory `Gdk.Texture` LRU cache — bind never touches disk.** The v0.2.0
thumbnail cache reduced file sizes by 92% but `set_filename()` still decoded
JPEGs synchronously in the main thread on every bind. During fast scrolling
through a 4,000-item library this produced visible jank around the 1,000-book
mark as hundreds of disk reads queued up in the render loop.

The thumbnailer now maintains a 512-entry `OrderedDict` LRU cache of decoded
`Gdk.Texture` objects. The bind callback calls `get_cached_texture()` first —
a dictionary lookup with zero I/O. Cache hits call `set_paintable()` directly
with the pre-decoded texture, bypassing GTK's file loading pipeline entirely.

- **LRU capacity:** 512 textures (covers ~4-5 screenfuls of grid). At 360x540
  RGBA that's ~380 MB of GPU-resident texture data worst case, though GTK
  manages the actual VRAM lifecycle.
- **Cache miss path:** `request_texture()` submits work to the 4-thread pool,
  which generates the disk thumbnail (if needed), decodes it into a
  `Gdk.Texture` via `new_from_filename()`, stores it in the LRU, then delivers
  via `GLib.idle_add` with a book ID stale-cell guard.
- **Deduplication:** A `_pending` set coalesces duplicate requests for the same
  cover during rapid scroll, preventing thread pool flooding.
- **API change:** `_bind_cover` now uses `set_paintable(texture)` instead of
  `set_filename(path)` — the texture is either from LRU (instant) or delivered
  async (one-time cost).

---

## v0.2.0 (2026-04-10)

---

### Performance

**Thumbnail disk cache eliminates full-resolution cover decoding.**
The grid was loading raw `cover.jpg` files (often 100KB+, 1400x2100px) via
`Gtk.Picture.set_filename()` on every bind, forcing GTK to decode and
downscale each cover in the render thread. With 4,000+ books this made
scrolling visibly sluggish.

`hermitage/thumbnailer.py` pre-scales covers to 360x540 (2x grid cell for
HiDPI) using Pillow's LANCZOS resampler and caches the result as an optimized
JPEG in `~/.cache/hermitage/thumbs/`. Cache keys are BLAKE2b hashes of the
source path + mtime + size, so thumbnails auto-invalidate when covers change.

- **Cache warming:** After the library loads, `warm_cache()` submits every
  cover to the 4-thread pool fire-and-forget, pre-populating the disk cache.
- On a sample cover: 99,319 bytes original -> 8,371 bytes thumbnail (92%
  reduction). At 4,014 books the entire cache is ~34 MB vs ~400 MB of raw
  covers decoded into GPU textures.

---

## v0.1.0 (2026-04-10)

---

### Initial Framework

First functional skeleton: database parser, application shell, and cover grid.

**`pyproject.toml`.** Modern Python 3.14 project configuration with
`setuptools` build backend. Declares `PyGObject >= 3.54`, `Pillow >= 11.0`,
and `PyYAML >= 6.0` as dependencies. Entry point registered as
`hermitage` console script via `hermitage.__main__:main`.

**`hermitage/database.py` — Calibre metadata.db parser.** Read-only SQLite
interface that opens the database in `mode=ro` (immutable URI). A single
joined query loads books with their authors, series, tags, ratings, comments,
and available formats in one pass. Results are mapped to a `Book` dataclass
using `slots=True` for memory efficiency.

- Library path is resolved via the `HERMITAGE_DB` environment variable, falling
  back to `~/docs/Calibre Library/metadata.db`.
- `Book.cover_path` property computes the absolute path to `cover.jpg` from
  the Calibre-relative `path` column.
- The query uses `GROUP_CONCAT(DISTINCT ...)` to collapse the many-to-many
  link tables (authors, tags, formats) into delimited strings, then splits
  them at load time.
- Tested against a 4,014-book production Calibre library.

**`hermitage/app.py` — Adw.Application and GridView.** Libadwaita application
with `AdwToolbarView`, `AdwHeaderBar`, and a `Gtk.GridView` backed by a
`Gio.ListStore` of `BookObject` wrappers.

- `BookObject` is a thin `GObject.Object` subclass that lets `Book` dataclass
  instances live inside `Gio.ListStore` (which requires GObject typing).
- `Gtk.SignalListItemFactory` with `setup`/`bind`/`unbind` callbacks:
  - **Setup** creates a `Gtk.Overlay` containing a `Gtk.Picture` (cover art)
    and a `Gtk.Label` (title) pinned to the bottom edge.
  - **Bind** loads the cover image via `set_filename()` and sets the title text.
  - **Unbind** releases the paintable to free texture memory as cells recycle.
- Inline CSS provides: 6px rounded cover corners, a bottom-edge gradient
  overlay for title legibility, fade-in title on hover/focus (`opacity 0 -> 1`,
  200ms ease), and a `scale(1.04)` hover transform on grid children.
- Grid is configured with `min_columns=3`, `max_columns=12`.
- Library loading runs via `GLib.idle_add` to avoid blocking the first frame;
  an `Adw.StatusPage` is shown during load and replaced once the store is
  populated. A second status page with error details is shown if the database
  cannot be found.
- The header bar subtitle updates to show the total book count after loading.

**`hermitage/__main__.py`.** Entry point for both `python -m hermitage` and
the `hermitage` console script. Delegates to `hermitage.app.run()`.
