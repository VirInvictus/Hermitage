# Hermitage — Patch Notes

## v0.9.1 (2026-05-01) — Bundled Typography

---

### New Features

**Bundled type system.** Hermitage now ships its own fonts in
`hermitage/fonts/` and registers them with the default `PangoCairo.FontMap`
at startup via the new `hermitage/typography.py` module. The look is
identical on every machine, with no dependency on whatever the user has
installed system-wide and no pollution of the user's font directory — the
registration is process-scoped via `Pango.FontMap.add_font_file()` (Pango
1.56+, available since GTK 4.20).

Three families, one role each:

| Role | Family | File(s) |
|---|---|---|
| Display — Codex hero title, placeholder cover title, genre subsection headings, italic series text | **Fraunces** (variable serif) | `Fraunces-Variable.ttf`, `Fraunces-Italic-Variable.ttf` |
| Body — synopsis, author line, Read button, window chrome | **Inter Variable** | `InterVariable.ttf`, `InterVariable-Italic.ttf` |
| Label — tag pills, section labels (uppercase tracked), grid-cell hover title, metadata, genre pills | **IBM Plex Sans Condensed** | `IBMPlexSansCondensed-{Regular,Medium,SemiBold}.ttf` |

All three are licensed under SIL OFL 1.1; the per-family license texts ship
alongside the fonts (`OFL-Inter.txt`, `OFL-Fraunces.txt`,
`OFL-IBMPlex.txt`) along with a `README.md` documenting sources and roles.

**Typography pass across every styled surface.** The stylesheet now defines
explicit `font-family`, weight, size, `letter-spacing`, and (where it
matters) `line-height`, `text-transform`, and `font-feature-settings` for
every text class. Highlights:

- The window-wide default switches from Cantarell to Inter Variable, with
  `font-feature-settings: "ss01", "cv11"` (Inter's modern alternates —
  single-story `g`, open digits).
- `.codex-title` is Fraunces 26px / 700 / `letter-spacing: -0.02em` for
  proper display-size optical compensation.
- `.codex-section-title` and `.codex-meta` adopt Plex Condensed with
  `text-transform: uppercase` and 0.15em / 0.04em tracking respectively —
  the visual hierarchy now matches the conceptual hierarchy without
  shouting.
- `.codex-synopsis` becomes Inter at `line-height: 1.6` for comfortable
  long-form reading inside `Adw.Clamp(maximum_size=600)`.
- `.cover-title` (grid hover label) is Plex Condensed Medium at 11px with
  positive tracking — readable at small sizes against the gradient scrim.
- `.cover-placeholder-title` upgrades to Fraunces 16px so the placeholder
  card reads as an editorial fallback, not a debug rectangle.

### Structural Improvements

**`hermitage/typography.py` (new module).** Single-purpose: enumerate the
bundled `.ttf` files and register them via `add_font_file()`. Idempotent,
catches and logs registration failures per file, gracefully short-circuits
on Pango installations too old to support runtime registration (callers fall
back to the CSS family chain).

**Registration runs from `__main__.main()`** before `hermitage.app` is
imported, so the font map is populated before any `Gtk.Widget` queries
Pango for a face.

**`pyproject.toml`** version bumps to 0.9.0 and adds `fonts/*.ttf`,
`fonts/*.txt`, and `fonts/README.md` to `[tool.setuptools.package-data]`
so wheel installs ship the fonts.

---

## v0.9.0 (2026-05-01) — Phase 7 Complete

---

### New Features

**Database lock fallback.** When Calibre holds a write lock on `metadata.db`,
sqlite refuses even read-only opens — Hermitage previously hard-failed at
launch. The new path mirrors `cquarry`'s `CalibreDB._open`: open with
`mode=ro`, run a probe `SELECT 1 FROM books LIMIT 1`, and on
`OperationalError` containing `"locked"` we `shutil.copy2` the `.db` plus its
`-wal` and `-shm` siblings to a `tempfile.mkstemp` path and reopen against the
snapshot. The snapshot path is cached in module state so the second
`_connect()` (used by `load_virtual_libraries`) reuses it instead of copying
twice. An `atexit` hook unlinks the snapshot files on shutdown. A one-line
note is printed to stderr the first time we fall back so the user knows
they're reading from a snapshot.

**Placeholder covers.** Books without a `cover.jpg` (or whose thumbnail
generation fails) used to render as blank cells. The grid factory now builds
a `Gtk.Stack` with two pages: the existing `Gtk.Picture` and a new
`.cover-placeholder` `Gtk.Box` that displays the title and author centred on
a tinted card. The tint is a stable per-book gradient — hue derived from a
Knuth-multiplier hash of `book.id`, fixed mid-saturation HSV — so a missing
cover is still visually distinct and consistent across sessions. The
placeholder is also shown transiently while a thumbnail is decoding, so first
paint is never blank. CSS provider lifecycle is handled in `_unbind_cover`
alongside the existing per-cell color provider cleanup.

**No-results state.** When a search returns zero matches, the grid is
swapped for an `Adw.StatusPage` ("No matches — Try a broader search or clear
the query.") via the existing view stack. The status page interpolates the
current query into its description so users immediately see what they
searched for. The genre toggle still wins — opening the genre browser hides
the no-results page until you toggle back. Clearing the search bar restores
the grid in either case.

**Loading progress.** The static "Loading Library…" page now hosts a
`Gtk.Spinner` for visible motion during the initial DB read. After the grid
appears, thumbnail cache warming reports progress in the title bar subtitle:
`"4272 books · indexing covers (62%)"`. The subtitle drops the suffix once
warming hits 100%, and never overrides an active search count.

### Enhancements

**Corrupt-cover hardening.** `thumbnailer._generate_thumbnail`,
`colors.extract_colors_sync`, and `codex._generate_blurred_cover` previously
swallowed every exception silently (`except Exception: return None`),
which made corrupt or zero-byte cover files invisible to debugging. They now
catch the specific Pillow exceptions (`UnidentifiedImageError`, `OSError`,
`ValueError`), explicitly check for zero-byte files, and emit a one-line
warning to stderr per offending path (deduplicated via a `set` + lock so
recycled cells don't spam). All three modules also enable
`PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True` so partially-readable JPEGs
still produce something rather than failing outright.

### Structural Improvements

**`thumbnailer.warm_cache` accepts a progress callback.** Optional
`progress(done, total)` parameter, dispatched on the main thread via
`GLib.idle_add` once per ~32 completions plus a final call. The throttling
keeps the title-bar update from saturating the GTK main loop on a 4,272-book
library while still feeling responsive.

**Snapshot cleanup.** New module-level `_snapshot_path`, `_snapshot_notified`,
`_make_snapshot()`, `_open_ro()`, and `_cleanup_snapshot()` in `database.py`.
The atexit registration is unconditional — cleanup short-circuits when no
snapshot was created, so there is no cost in the common case.

---

## v0.8.0 (2026-04-11) — Phases 5 & 6 Complete

---

### New Features

**YAML configuration system.** All settings are stored in
`~/.config/hermitage/config.yaml` — human-readable and editable in any text
editor. The config file stores library path, sort field, and sort direction.
The `HERMITAGE_DB` environment variable still works as a highest-priority
override. Precedence: env var > config file > first-run wizard.

**New module: `hermitage/config.py`.** Manages loading, saving, and caching
the YAML config file. Provides `load_config()`, `save_config()`, `get()`,
`set_value()`, and `reload_config()` APIs. Defaults are merged on first load.

**First-run setup wizard.** On launch with no config file and no
`HERMITAGE_DB` env var, an `Adw.Window` prompts the user to select their
Calibre library folder via `Gtk.FileDialog.select_folder()`. Validates that
`metadata.db` exists in the chosen directory before writing the config and
proceeding to the main window. No more hardcoded library path assumptions.

**New module: `hermitage/wizard.py`.** Self-contained `SetupWizard` window
with folder picker, path validation, error display, and config write-through.

**Settings page.** `Adw.PreferencesWindow` accessible from the header bar's
hamburger menu (Preferences). Sections for library path (with a "Change"
button and folder picker) and display settings (sort field dropdown, ascending
toggle). Sort changes take effect immediately without restart. Library path
changes require a restart (shown as a toast notification).

**New module: `hermitage/preferences.py`.** `PreferencesWindow` reads and
writes the same YAML config file. Fires an `on_settings_changed` callback
that triggers an immediate grid re-sort.

**Sort options.** Header bar sort menu button (`view-sort-descending-symbolic`)
with six sort fields:

| Field | Sorts by |
|-------|----------|
| Title | `book.sort` (Calibre's sort-friendly title) |
| Author | First author name, alphabetical |
| Date Added | `books.timestamp` (Calibre's date-added field) |
| Publication Date | `book.pubdate` |
| Rating | Calibre rating (0-10 scale) |
| Series | Series name, then `series_index` within series |

Ascending/descending toggle updates the sort icon in the header bar. Sort
preference is persisted to config. Implemented via stateful `Gio.SimpleAction`
with `GLib.Variant` state management.

**Auto-sort by series order.** When the search query starts with `series:`,
the grid automatically re-sorts by `series_index` so books appear in reading
order regardless of the global sort setting. Clearing the search restores
the configured sort.

**Genre browser.** A new full-page view (`GenreBrowser`) accessible via the
bookmarks toggle button in the header bar. Displays all Calibre tags organized
by their dot-separated hierarchy:

- Top-level categories (Fic, NonFic, Gaming, etc.) as `Adw.Card`-styled
  sections with total book counts
- Sub-genres as clickable accent-colored pills with individual counts
- Tooltips on pills that have further sub-categories
- Clicking any genre pill populates the search bar with `tags:"path"` and
  switches back to the grid view
- Crossfade transition between grid and genre views via `Gtk.Stack`

**New module: `hermitage/genres.py`.** Builds a tag tree from dot-separated
Calibre tags, counts books at each level, and renders the tree as an
attractive card-based layout with `Gtk.FlowBox` pill buttons.

**Clickable metadata in the Codex.** Author names, series names, and tag
pills in the detail sidebar are now buttons. Clicking them populates the
search bar with the corresponding field filter:

- Author → `authors:"Author Name"`
- Series → `series:"Series Name"`
- Tag pill → `tags:"Tag.Path"`

Styled with a new `.codex-link-btn` CSS class that removes button chrome
(background, border, shadow) and adds a subtle hover opacity effect.

**Search debounce.** Search filtering now waits 400ms after the last keystroke
before re-filtering the grid, preventing jarring visual updates during
typing. Clearing the search bar applies immediately (no debounce on empty).
The debounce timer is reset on each keystroke via `GLib.timeout_add` /
`GLib.source_remove`.

**Clean Ctrl+C exit.** `SIGINT` is now handled in `__main__.py` with
`signal.signal(signal.SIGINT, ...)` — pressing Ctrl+C in the terminal exits
the process cleanly instead of printing a wall of GTK error traces.

### Data Model Changes

**`Book.timestamp` field added.** The `books.timestamp` column (Calibre's
"date added" field) is now included in the SQL query and stored on the `Book`
dataclass. Used by the "Date Added" sort option.

### Structural Changes

**`database.py` library path resolution rewritten.** `_resolve_library_path()`
now follows the precedence chain: `HERMITAGE_DB` env var > `library_path`
from config file > `FileNotFoundError` (triggers the wizard). The hardcoded
fallback to `~/docs/Calibre Library/` has been removed.

**Header bar expanded.** Four buttons on the left (VL sidebar, search, genre
browser), sort menu and hamburger menu on the right. Sort menu uses
`Gio.Menu` with a stateful radio-style action for field selection and a
toggle action for ascending/descending.

---

## v0.7.1 (2026-04-10) — Structural Cleanup

---

### Structural Changes

**`app.py` decomposed into focused methods.** The monolithic `_load_library`
method (~200 lines) has been split into purpose-named sub-methods:

- `_build_grid()` — creates `ListStore`, `CustomFilter`, `FilterListModel`,
  `GridView`, and wires the activation handler.
- `_build_layout()` — assembles the nested `OverlaySplitView` stack (codex
  right, VL left) and sets up the virtual library resolver.
- `_wire_search()` — connects the search entry to the filter pipeline.
- `_make_vl_row()` — extracted helper for VL sidebar row creation, replacing
  two identical inline blocks.

Event handlers (`_on_book_activated`, `_on_vl_activated`, `_on_search_changed`)
converted to `@staticmethod` where possible.

**Dead state tracking removed.** `_active_query` (str), `_active_vl` (str),
`_store` (duplicate reference), and `_vl_listbox` (unused after build) were
tracked as window attributes but never read. All four removed.

**CSS extracted to `hermitage/style.css`.** The `_CSS` string literal
(120 lines) was moved to a standalone `.css` file loaded via
`Gio.File.new_for_path`. Added `[tool.setuptools.package-data]` in
`pyproject.toml` to ensure the stylesheet is included in distributions.

**`database.py` — public `library_root()` API.** The private `_library_root()`
function renamed to `library_root()` since it's used by both `codex.py` and
`verify.py`. `_library_root_cache` remains module-private.

**`load_virtual_libraries()` moved to `database.py`.** Previously an inline
lambda in `_load_library`, now a proper function in the database module
alongside `load_library()`.

**Dead FTS5 code removed.** The entire FTS5 full-text search subsystem
(`build_search_index`, `search`, `_fts_conn`, `_fts_book_index`) was superseded
by the recursive descent parser in v0.7.0 and has been removed from
`database.py`.

### Bug Fixes

**`codex.py` — `on_dismiss` was a class variable.** `on_dismiss = None` on the
class body meant all `CodexView` instances shared one callback slot. Moved to
`__init__` as an instance variable.

**`search.py` — mid-file import.** `from hermitage.database import Book` was
inside a function body. Moved to the module's top-level imports.

**`app.py` — magic numbers.** `wrap_mode=2` and `set_ellipsize(3)` replaced
with `Pango.WrapMode.WORD_CHAR` and `Pango.EllipsizeMode.END`.

**`codex.py` — unused `threading` import removed.**

**`codex.py` — `_library_root` → `library_root`.** Updated to match the
renamed public API in `database.py`.

---

## v0.7.0 (2026-04-10) — Phase 4 Complete

---

### New Features

**Calibre-compatible search bar.** A `Gtk.SearchBar` slides below the header
bar, triggered by the search toggle button or Ctrl+F. The search entry accepts
Calibre's full query syntax:

- Field prefixes: `tags:Fantasy`, `title:"1984"`, `authors:King`,
  `series:`, `formats:EPUB`, `rating:5`
- Exact match: `tags:"=Fic.Fantasy"` (prefix `=` inside quotes)
- Boolean operators: `and`, `or`, `not` (case-insensitive)
- Parentheses for grouping
- Virtual library references: `vl:"Fantasy Wing"`
- Bare text: searches across title, authors, tags, and series (implicit AND)

The search bar is wrapped in an `Adw.Clamp(600px)` to keep it visually
centered. The header subtitle updates to show `N of M books` while a filter
is active.

**New module: `hermitage/search.py`.** Self-contained recursive descent parser
and evaluator for Calibre's search query language. Tokenizer splits input into
words, quoted strings, colons, parens, and boolean keywords. Parser produces
an AST of `FieldExpr`, `BareExpr`, `AndExpr`, `OrExpr`, and `NotExpr` nodes.
Evaluator matches each node against `Book` fields with substring (default) or
exact (`=` prefix) matching. `vl:` references are resolved lazily via a
callback that loads and caches parsed expressions from the Calibre preferences
table. Implicit AND handles multi-word bare searches
(`stephen king` -> `stephen AND king`).

Filtering uses `Gtk.CustomFilter` with `Gtk.FilterListModel` wrapping the
`Gio.ListStore`. The filter function pre-computes a matching ID set via
`filter_books()` for O(1) per-item lookup.

**Virtual library sidebar.** A left-side `Adw.OverlaySplitView` (200-260px)
presents all 19 virtual libraries loaded from the Calibre `preferences` table.
The sidebar uses `Gtk.ListBox` with `navigation-sidebar` styling. An "All
Books" row at the top clears the filter. Clicking a library populates the
search bar with `vl:"Library Name"` and applies the corresponding search
expression. Toggle via the header button or Ctrl+L.

The sidebar nests inside the existing layout: `ToolbarView > VL SplitView
(left) > Codex SplitView (right) > ScrolledWindow > GridView`.

**Codex dismiss button.** A circular close button (`window-close-symbolic`)
overlaid in the top-right corner of the hero banner with a semi-transparent
dark background. Clicking it hides the codex sidebar.

**Keyboard shortcuts.** Registered via `Gtk.ShortcutController` on the window:

| Shortcut | Action |
|----------|--------|
| Ctrl+F   | Toggle search bar |
| Ctrl+L   | Toggle virtual library sidebar |
| Escape   | Close codex, then search, then VL sidebar (priority order) |

---

## v0.6.1 (2026-04-10) — Phase 3 Complete

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

**Grid covers collapsed to dots on first render.** `Gtk.Picture` with no
paintable set (before async thumbnail delivery) has zero intrinsic size.
`AspectFrame` computed its layout from that zero, so every cell collapsed to a
tiny dot. Added `set_size_request(180, 270)` on the picture to guarantee a
minimum cell size matching the 2:3 cover ratio, independent of texture load
state.

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

- Library path is resolved via the `HERMITAGE_DB` environment variable or
  the config file at `~/.config/hermitage/config.yaml`.
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
