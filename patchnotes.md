# Hermitage — Patch Notes

## v1.6.0 (2026-08-26)

### cquarry 1.6.0 Adoption
- **User Categories search natively through the grammar:** clicking a user-category row now
  sets `@Name:true` (cquarry ≥1.6's `get_user_category_matches` parity) instead of expanding
  members into an OR of contains-queries. Results now match Calibre exactly: each member is
  matched exactly on its own location, so a member "Tor" no longer substring-matches
  "Tor.com" books. Spaced category names work (upstream's `@...:` lexer word rule).
- **Runtime library refreshed 1.3.0 → 1.6.0:** brings everything v1.4/v1.5 already
  documented plus v1.6's fixes — `get_book()`/`get_all_books()` rows are shape-identical
  (both carry `uuid`, `identifiers`, `size`), languages honor `books_languages_link.item_order`,
  and the new `get_feeds()` / `get_annotations_dirtied_books()` / `get_tag_browser_counts()`
  APIs are available (the latter exposes Calibre's own `tag_browser_*` sidebar rollups with
  `avg_rating` — a candidate for future browse-sidebar count badges).
- **Requires cquarry ≥1.6.1** (picks up the empty-numeric-query parity fix — `rating:` with no
  value now matches nothing instead of raising, relevant to free-text entry in the search bar).

## v1.5.0 (2026-08-26)

### cquarry 1.4.0 Adoption
- **Author cards by true sort name:** `Book` gains `author_sorts`/`author_links` (cquarry's parallel arrays). The Codex author line now orders multi-author books by their real sort keys and lists author-page URLs in the tooltip.
- **Colored enumeration badges:** custom-column pills read Calibre's `display.enum_colors` (via cquarry's decoded display config) and tint themselves accordingly — the `#reading_status` showcase column now renders exactly as colored in the desktop GUI.
- **User Categories sidebar:** a third sidebar section lists Calibre's hand-built tag-browser categories (`user_categories`). Clicking one expands its members into an OR expression over their locations (`#column:"value"` / `tags:"value"`) and runs it through cquarry's grammar.
- **Requires cquarry ≥1.4.**

## v1.4.0 (2026-08-26)

### cquarry 1.3.0 Adoption
- **Page counts in the Codex:** `Book` gains a `pages` field sourced from Calibre's native `books_pages_link` table (cquarry ≥1.3 reads it directly, falling back to a `#pages` custom column on older schemas). The Codex meta row now shows "N pages" beside the formats line.
- **Canonical cover resolution:** `Book.cover_path` is built through cquarry's `get_cover_path()` instead of hand-assembling `<root>/<path>/cover.jpg`, so the storage-layout logic lives in exactly one place across the ecosystem. Behavior is unchanged (unverified `.jpg` path, `None` when `has_cover=0`); the returned type stays a `Path`.
- **Exact format-file resolution:** the Codex reader launcher (`_find_format_file`) resolves paths through cquarry's `get_formats(book_id)` first — the catalogued filename stem beats globbing the directory — with the historical glob kept as a fallback for lagging catalogs.
- **Requires cquarry ≥1.3.**

## v1.3.0 (2026-08-25)

### cquarry 1.1.0 Adoption
- **List-typed fields:** `load_library()` now consumes the native `list[str]` `authors`/`tags`/`formats` arrays that cquarry ≥1.1 exposes instead of comma-splitting strings. Author names containing literal commas ("Strunk, Jr.") no longer split in half; the historical `|` pipe-escape is still restored for display.
- **Half-star ratings:** The Codex rating row uses cquarry's `normalize_rating()` upstream conversion, so a Calibre rating of 5/10 renders as ★★½ instead of being truncated down by integer division.
- **Saved Searches sidebar:** A second sidebar section under "Libraries" lists Calibre's saved searches (from `preferences.saved_searches`). Clicking one runs it through cquarry's `search:"Name"` interpolation.
- **Calibre-exact tab layout:** The virtual-library sidebar now honors Calibre's own stored ordering (`virt_libs_order`) and hidden list (`virt_libs_hidden`) via `database.load_vl_ui_state()`, so Hermitage's Libraries panel mirrors the desktop GUI exactly.
- **Annotations & reading progress:** New wrappers `database.get_annotations(book_id)` and `database.get_reading_progress(book_id)` expose e-reader highlights and per-device progress fractions for UI consumption.
- **Fixed:** `_build_vl_sidebar` referenced `win._vl_defs` without it ever being assigned (latent AttributeError on first Ctrl+L). It is now populated during `_load_library()`.

## v1.1.0 (2026-08-23)

### Core Integration
- **cquarry Shared Backend:** Ripped out the custom, hand-rolled Calibre database connection and search parser from `hermitage/database.py` and `hermitage/search.py`. Hermitage now uses the `cquarry` library as its single source of truth for all Calibre data.
- **Search Grammar Parity:** By adopting `cquarry.db.CalibreDB.search()`, Hermitage natively supports every Calibre search feature (implicit ANDs, regex, date math, custom columns, identifiers, nested Virtual Libraries) rather than its previous limited subset.
- **Dependency Update:** Added `cquarry` to the required packages.
# Hermitage — Patch Notes


## v1.0.0 (2026-08-21) — 1.0 Milestone and Stable Release

This release marks the completion of Phase 10 and graduation to a stable 1.0.0 milestone. After extensive regression testing on a live 7,600+ book library, all core end-to-end features — the first-run wizard, search syntax, virtual library sidebars, dynamic covers, reading history, and OS document hooks — are verified stable under Wayland and Hyprland.

---

### Enhancements

**Graduation to Stable:** Hermitage officially ships its 1.0.0 milestone. The application is now fully packaged for release via PyPI and as a Flatpak targeting the GNOME 50 runtime. No new features are introduced in this build; it is a direct promotion of the v0.18 code after clearing the Phase 10 regression gauntlet.

## v0.18.1 (2026-08-09) — Secondary Windows Report the Right `app_id`
The three findings the Phase 13 visual pass turned up on 2026-07-28 and
deliberately left unactioned (so that audit's commit stayed free of unrelated
edits) are fixed here. The first is the one with user-visible consequences.

---

### Bug Fixes

**Every secondary window reported the Wayland `app_id` `python`.** The main
window has always been correct, but Preferences, Library Insights, Keyboard
Shortcuts, and About were plain `Gtk.Window`s that were never registered with
the `Gtk.Application`, so GTK fell back to `g_get_prgname()` — `python` under
`python -m hermitage`, `hermitage` under the console script, and never the app
id in either case. That matters more here than it would in a GNOME app, because
`app_id` is exactly what a Hyprland `windowrulev2` keys on: a user rule written
against `class:^(io.github.virinvictus.hermitage)$` silently missed all four
windows. All four now pass `application=` at construction, which is what
`SetupWizard` already did and is the pattern to follow for any new toplevel.

Both candidate fixes named in the roadmap were checked against a live compositor
before committing, rather than picked by reading the docs: a four-window probe
under one `Gtk.Application` confirmed that `application=` at construction and a
later `app.add_window()` both produce the correct class, while the plain
construction reproduces the bug exactly. The construction kwarg won on being
one line at the point of definition.

**No more `PyGIWarning` on every launch.** `app.py` imported `Gdk` alongside
`Gtk` but version-pinned only `Gtk`, so each start printed `Gdk was imported
without specifying a version first`. Harmless — GTK 4 pulls in Gdk 4 regardless
— but it was noise on every run, and the project's `E402` per-file-ignore exists
precisely to accommodate the `gi.require_version` pattern this line skipped.

**Stale module docstring.** `app.py` still described itself as a "GTK 4 /
Libadwaita application" three phases after v0.17.0 removed libadwaita and after
`tests/test_guards.py` started failing on any `Adw` import.

---

### Structural Improvements

**A guard test that can see this class of bug.** `TestAppIdLockstep` compares
`APP_ID` against `StartupWMClass` and is structurally incapable of noticing a
window that never reaches the application, which is why the bug survived it. The
new `TestSecondaryWindowAppId` walks the package AST and fails on any
`Gtk.Window` / `Gtk.AboutDialog` / `Gtk.ApplicationWindow` construction, and any
`super().__init__` inside a toplevel subclass, that omits `application=`. It
reports offenders by file and line.

It also carries a test asserting the detector itself fires on the offending
pattern, and it was confirmed against the real thing: reverting the fixes makes
it fail naming all three sites. A guard nobody has watched fail is not a guard.

---

## v0.18.0 (2026-07-17) — Custom Columns in the Codex

Roadmap Phase 11's last open item lands: Calibre custom columns. Hermitage now
reads the user-defined columns from `metadata.db` (the same read-only path as
everything else) and surfaces them in the Codex detail view and the search
grammar. This closes Phase 11 (the CalibreQuarry feature port); the port
follows cquarry's `get_custom_columns()` / `load_custom_column()` logic, adapted
to Hermitage's `Book` dataclass and GTK surfaces.

---

### New Features

**Custom columns in the Codex "Details" section.** Any user-defined Calibre
column (Status, Source, Translators, Date Read, Audience, whatever the library
has) now renders read-only in a new Details section between Tags and the
"Find this book on" links. Text and enumeration columns render as clickable
pills; clicking one filters the library to that value. Datetime, number, and
boolean columns render as plain metadata lines, with datetimes formatted the
same way the publication date already is (and Calibre's year-101 "undefined"
sentinel suppressed). The section hides itself entirely when a book has no
custom values, so it never leaves an empty header behind.

**`#label:` search.** Custom columns are searchable with Calibre's own syntax,
for example `#reading_status:Read`, `#source:"Standard Ebooks"`, or
`#translators:Rubin`. Multi-valued text columns match on any of their values.
The tokenizer already kept a leading `#` inside a word, so this needed only the
field-value lookup, not new grammar. Bare (unprefixed) search is unchanged and
still spans title/authors/tags/series only, to avoid surprising matches.

**Exact-match pills.** A pill click emits an exact match (`#label:"=value"`)
rather than a substring search, so clicking "Read" does not also pull in
"To Read". This mirrors what Calibre itself generates when you click a
custom-column value in its own UI. Typing an unprefixed value in the search bar
still does Calibre's substring-contains matching.

---

### Structural Improvements

**Bulk-loaded, no N+1.** `database.load_library()` loads each custom column's
values in one query per column (mirroring the existing identifiers bulk-load)
and attaches them to `Book.custom`, keyed by column label. Multi-valued columns
hold a `list[str]`; every other datatype holds a single scalar; only columns
that actually have a value for a given book appear. The column schema (id,
label, display name, datatype, multiplicity) is exposed via
`database.load_custom_columns()` as a list of `CustomColumn`, cached after the
first library load so the Codex never reopens the database just to learn the
display names.

**Both Calibre storage shapes handled.** Following cquarry, the loader detects
how a column is stored by whether its `books_custom_column_N_link` join table
exists, not by the `is_multiple` flag: normalized text/enumeration/series
columns come from a value table joined through the link table (even
single-valued enumerations), while int/float/bool/datetime/comments columns are
read directly from `custom_column_N`. Composite (computed) columns have no value
table and are skipped gracefully.

**Tests.** Eleven new tests. `test_database.py` gains a fixture with all three
shapes (a normalized enumeration, a multi-valued text column, and a
directly-stored datetime) and asserts the schema, per-book values, the
empty-dict case for a book with none, and that the schema cache is warmed by a
library load. `test_search.py` covers `#label:` tokenizing/parsing, scalar and
multi-valued matching, exact match, a missing column, and end-to-end
`filter_books`. Full suite is 84 tests; `ruff check` is clean; `hermitage-verify`
reads all 7,210 books from the live library unchanged.

---

## v0.17.0 (2026-07-11) — Hyprland-Native: De-adwaita, Owned Stylesheet, Tiling Ergonomics

Phases 13 and 14 landed together. Brandon's desktop moved from GNOME Shell to
Hyprland, and Hermitage moved with it: not "runs politely under a tiling
compositor" but "fully belongs on one." Libadwaita is gone. GTK 4 and PyGObject
stay (GTK 4 is Wayland-native); what left is the GNOME identity layer, replaced
by plain GTK 4 widgets and a stylesheet Hermitage owns outright. Following the
Colophon pilot's proven patterns, translated from Rust to PyGObject. Nothing
regresses: every surface works the same, and the app still runs under a GNOME
fallback session. The look stops being GNOME's; the compatibility does not.

---

### New Features

**Owned dark/light theming via the desktop portal.** With `Adw.StyleManager`
gone, `hermitage/theme.py` is now the single theme-resolution path: it reads
`org.freedesktop.portal.Settings` directly over D-Bus, maps the system
preference to an owned Kanagawa Dragon (dark) or Kanagawa Lotus (light)
palette injected as GTK named colours, and re-applies live when the portal
reports a change. No new dependency (Gio ships with PyGObject); it degrades to
the dark default when no portal answers. The palette provider registers just
above `PRIORITY_USER` so a stray `~/.config/gtk-4.0/gtk.css` can no longer
half-override the app's own colours.

**Floating overlay sidebars.** The Codex detail pane and the virtual-library
list are now `Gtk.Revealer` panels stacked over the grid in a `Gtk.Overlay`,
sliding in over the covers rather than squeezing the grid. On a half or quarter
Hyprland tile the grid keeps its width instead of collapsing to a sliver. The
Escape cascade (codex, then search, then sidebar) and Ctrl+L are unchanged.

**Keyboard shortcuts window.** A new owned dialog (Ctrl+? or the primary menu)
lists every binding: search, virtual libraries, genres, series, insights,
preferences, quit, and the Escape cascade. Built from the same boxed-list rows
as Preferences so it matches the owned look rather than importing GNOME's.

**Keyboard triggers for genre and series browsing.** `Ctrl+G` toggles the genre
browser and `Ctrl+R` the series browser; both were pointer-only before.

**Type-ahead find in the grid.** Typing letters over the Sanctuary jumps
selection to the first book whose sort title starts with what you typed, with a
one-second buffer reset mirroring the search debounce. The match logic is a
pure function (`first_index_with_prefix`) covered by headless tests.

**HiDPI-aware cover thumbnails.** Thumbnails are now generated per display scale
tier (`thumbs/<scale>/`), sized from the cell's actual `get_scale_factor()` at
bind time, so a 2x or 3x display (or the integer GTK renders at under Hyprland
fractional scaling) gets a denser thumbnail instead of an upscaled 1x one. This
closes the long-open Phase 9 High-DPI audit alongside the fractional-scale item.

**Ctrl+Q quits, and the window wears no title buttons.** The compositor draws
no titlebar of its own on Hyprland, so window controls are hidden and Ctrl+Q is
the in-app quit; a GNOME fallback session still closes the window its own way.

### Enhancements

**A true one-column floor.** The grid's density is left to `Gtk.GridView`'s own
column fitting between one and twelve columns; the `Adw.Breakpoint` machinery is
gone. A narrow quarter-tile now renders one clean strip of covers instead of two
crushed ones, and a wide window fills out exactly as before.

### Structural Improvements

**`hermitage/widgets.py`: owned successors to the adwaita widgets.** A
width-clamping `Clamp` (a real measure/allocate `Gtk.Widget`, since GTK CSS has
no max-width), a two-line `WindowTitle`, an auto-hiding `ToastOverlay`, a
centred `StatusPage` (API-compatible with `Adw.StatusPage` so mutating callers
were untouched), and the boxed-list `value_row` shared by Preferences and the
Insights audit. Preferences and Insights are now plain `Gtk.Window`s; the
first-run wizard and About dialog likewise.

**The stylesheet owns its GNOME vocabulary.** `style.css` now defines the
adwaita style classes it used to inherit (`.card`, `.boxed-list`, `.pill`,
`.title-*`, `.dim-label`, `.suggested-action`, and friends) plus the new widget
classes. Deliberately flat but not squared off: Hermitage keeps its rounded,
immersive identity (rounded cover cells, pill tags, the blurred hero), because
the spec's "curated, not utilitarian" mandate governs over a generic flat look.

**Regression guards.** New headless tests assert the package imports no
libadwaita, reads no GNOME-only `Gio.Settings`, and keeps `APP_ID` in lockstep
with the `.desktop` `StartupWMClass` (so a Hyprland `windowrulev2` keeps
matching after any rename). The suite grew from 63 to 75 tests. CI drops
`libadwaita-devel`; the Flatpak stays on the GNOME runtime (that is where GTK 4
and PyGObject come from) and simply stops importing `Adw`.

---

## v0.16.0 (2026-07-04) — Audit Sweep: Bugfixes, Test Suite, Lint Hygiene

---

### New Features

**Test suite: 63 unittest tests under `tests/`.** The Phase 12 headline.
Hermitage was the only portfolio Python project with zero tests; the
non-GTK layers are now covered in the CalibreQuarry style (stdlib
`unittest`, temp-sqlite fixtures): the full search grammar
(tokenizer, parser, evaluator, `filter_books` fallback), the database
layer against a hand-built `metadata.db` fixture (joined-query fields,
author ordering, the locked-DB snapshot fallback exercised with a real
`BEGIN EXCLUSIVE` lock), config round-trips, JSON/CSV export, reading
history (including `humanize` buckets), and the pure aggregation
builders behind the genre/series/insights surfaces. Run with
`python -m unittest discover -s tests`.

**Keyboard accelerators for app actions.** `Ctrl+,` opens Preferences
(the GNOME standard binding) and `Ctrl+I` opens Library Insights.
Ctrl+F / Ctrl+L keep working as window-level shortcuts.

### Bug Fixes

**Per-cell hover glow no longer bleeds across the grid.** Every cell's
dynamic color provider defined the same `.cover-cell-active:hover`
selector display-wide, so whichever cell bound last set the glow color
for *all* visible cells. The class is now namespaced per book
(`cover-glow-<id>`), mirroring the placeholder-tint pattern, and both
the provider and the class are dropped on unbind and rebind.

**Search parser: trailing clauses are no longer silently dropped.**
`dragons magic and epic` parsed as `dragons AND magic` and discarded
`and epic`: the implicit-AND loop ran after the explicit one, and
`parse()` never checked that the token stream was fully consumed. One
unified loop now handles explicit and implicit AND in any order, and
`parse()` requires EOF, so malformed queries (stray `)`) raise
`ParseError` and fall back to "match all" instead of evaluating a
truncated AST.

**Recently Read and All Books no longer fight the search entry.** Two
related defects: (1) leaving Recently Read via "All Books" did nothing
when the search entry was already empty, because `set_text("")` emits
no `search-changed` signal, stranding the recency filter; (2) entering
Recently Read *with* a search active queued a delayed `search-changed`
clear (`GtkSearchEntry` emits ~150 ms after `set_text`) that then
clobbered the recency reorder. Both flows now reset the view directly
through a shared `_clear_search_view()` path and suppress the stale
signal-driven clear with a one-shot flag. The no-results page copy
("Nothing here yet") is also restored to its default on every reset.

**Responsive breakpoints applied in the wrong precedence order.**
libadwaita applies the *last added* breakpoint whose condition
matches. Narrow (max-width 500sp) was added before medium (900sp), so
a sub-500sp window matched both and got medium's 3–5 columns instead
of narrow's 2–3. The broad condition is now added first.

**Cold-cache cover starvation fixed.** `warm_cache()` submitted every
cover in the library to the same 4-thread executor that serves visible
cells, so on a cold cache the first screen's thumbnails queued behind
thousands of warm jobs and the grid sat on placeholders for the whole
warm pass. Warm sweeps (thumbnails and colors) now run on their own
2-thread executors; interactive requests never wait behind them.

**Coalesced texture requests deliver every callback.** `_pending` was
a set: if the grid cell had already requested a cover, a second
request for the same file (the Codex hero, reliably, since opening a
book means its cell just bound) returned without registering its
callback and that surface never got the texture. `_pending` is now a
path → callback-list map; one decode, every caller notified.

**Cover-warming progress can no longer stall below 100%.** If a
thumbnail job threw (cover deleted mid-scan), the done-counter never
advanced and the "indexing covers (N%)" subtitle stuck forever. The
counter now increments in a `finally`. The zero-byte-file check also
moved inside the existing try so a cover vanishing between stat calls
warns instead of raising.

**Read badge appears immediately after clicking Read.** The old
refresh nudged the filter with `Gtk.FilterChange.DIFFERENT`, but
`GtkFilterListModel` only signals items whose match status changed, so
nothing rebound and the badge waited for a scroll. The store now emits
`items_changed(pos, 1, 1)` for just that book's position, forcing a
rebind of the one cell.

**Sort menu stays in sync with Preferences.** Changing sort field or
direction in the Preferences window wrote config and re-sorted the
grid but left the header menu's stateful actions (radio selection,
Ascending check) and the direction icon stale. The settings-changed
callback now pushes config state back into both actions and the icon.
The icon also reflects the configured direction at startup instead of
always starting as "descending".

**Author list preserves Calibre's credit order and comma names.**
`GROUP_CONCAT(DISTINCT a.name)` returned authors in an unspecified
order, so `authors[0]` (used for author sort and the Codex author
link) could be the wrong name on multi-author books. The query now
uses cquarry's ordered-subquery approach (`ORDER BY bal.id`), and
Calibre's pipe-escaped commas in author names ("Gaiman| Neil") are
restored to real commas for display.

**Escape propagates when there is nothing to close.** The shortcut
handler returned `True` unconditionally, swallowing Escape even with
no codex, search bar, or sidebar open.

**`load_virtual_libraries()` closes its connection on error** (the
cursor read is now wrapped in `try/finally` inside the broad guard).

### Structural Improvements

**Single source of truth for the version restored.**
`hermitage/__init__.py` had drifted to 0.8.0 while `pyproject.toml`
said 0.15.0. The pyproject now declares `dynamic = ["version"]` and
reads `hermitage.__version__`, so the drift class is gone; the About
dialog falls back to `__version__` (instead of "0.0.0+dev") when
running from a source checkout without an installed dist.

**Lint hygiene: `ruff check` is clean.** The Phase 12 sweep items: the
four F811 shadowed re-imports in `app.py` (`cfg_get`, `set_value`,
`os` were imported at module level, then re-imported locally) now use
the module-level bindings; the 11 F401 unused imports are gone; the
E741 ambiguous `l` in `insights.py` is renamed; and a
`[tool.ruff.lint.per-file-ignores]` entry silences E402 for the
`gi.require_version()` import pattern so real violations stay visible.
The wizard's magic `set_ellipsize(2)` is now
`Pango.EllipsizeMode.MIDDLE`.

**Redundant `series:` prefix check collapsed** in the search handler
(`startswith("series:")` already covers `series:"`), and the empty-
debounce branch now routes through the same `_clear_search_view()`
path as the immediate clear, fixing a subtle inconsistency where it
checked only the genre toggle and not the series toggle.

---

## v0.15.0 (2026-05-01) — Flatpak Manifest

---

### New Features

**Flatpak manifest** at `data/io.github.virinvictus.hermitage.yml`,
targeting the `org.gnome.Platform//50` runtime. Builds end-to-end with
`flatpak-builder` and produces an 8 MB installable that runs the GUI
and the bundled `hermitage-verify` reads the host library through the
sandbox in ~195 ms (110 ms DB load + 85 ms path scan against the
4,272-book library — about 2× the native time, well within the
<200 ms spec).

Module chain (offline-buildable, sdist sources pinned by sha256):

| Module | Version | Notes |
|---|---|---|
| `python3-cython` | 3.2.4 | Build dep — PyYAML's `_yaml` extension on Py 3.13+ |
| `python3-pyyaml` | 6.0.3 | `--no-build-isolation` so the SDK's setuptools is visible |
| `python3-pillow` | 11.3.0 | Pinned at 11.x to avoid Pillow 12's pybind11 → scikit-build-core dep cascade |
| `hermitage` | 0.15.0 | local `dir` source, install plus icon/desktop/metainfo placement |

Sandbox permissions (`finish-args`) are intentionally minimal:
`--share=ipc`, `--socket=wayland --socket=fallback-x11`,
`--device=dri`, `--filesystem=home`. Arbitrary library paths outside
`$HOME` reach the app via the GNOME file-chooser portal — no extra
permission needed. Read-button file launches use the OpenURI portal.

### Enhancements

**`requires-python` relaxed from `>= 3.14` to `>= 3.13`.** GNOME 50
runtime ships Python 3.13.13. The codebase uses no 3.14-only syntax
(`from __future__ import annotations` + `@dataclass(slots=True)` are
both 3.10+), so 3.13 runs cleanly. The local Fedora dev environment
still uses 3.14 — this just opens the sandboxed runtime.

**`build-backend` switched to `setuptools.build_meta`.** The previous
`setuptools.backends._legacy:_Backend` is too new for the SDK's
setuptools 80.x; the standard `build_meta` is universally supported
and identical in behaviour for our pyproject.

**Pre-rendered PNG icons at 32 / 48 / 64 / 128 / 256 / 512 px.**
Generated from `logo.svg` via `rsvg-convert` during the build. The
master SVG is intentionally **not** installed — flatpak-builder's
export step validates icons via `gdk-pixbuf`, and the `librsvg2-pixbuf`
loader is no longer shipped on Fedora 44+ (GTK4 renders SVG natively
without it). Software centers prefer PNGs anyway.

**`appstream-compose: false`.** The metainfo.xml ships verbatim to
`/share/metainfo`; in-build `appstreamcli compose` is skipped to
avoid the same gdk-pixbuf SVG-loader issue. Flathub re-runs compose
at submission time against its own toolchain.

### Structural Improvements

**`.gitignore`** picks up `.flatpak-builder/`, `build-flatpak/`, and
`*.flatpak` so the build cache and produced bundle don't get tracked.

---

## v0.14.0 (2026-05-01) — Application Icon

---

### New Features

**App icon.** A high-contrast Fraunces-inspired serif H monogram on a
deep aubergine rounded card with a warm candlelight glow from above
and a thin gilt shelf line below. Hand-traced as a small set of
overlapping rectangles painted with a cream → amber vertical gradient
so the lower half catches the shelf accent — same warm/dark palette
the codex hero uses.

Designed at 128×128. Stem-to-crossbar contrast (16 px stem vs 6 px
crossbar) and bracket-style serif extensions echo the Fraunces
display face; the rounded-card corner radius (~22 %) matches Adwaita
app icon convention. Renders cleanly from 24 px (the H reads as a
warm-toned monogram silhouette) up through 256 px (full ink gradient,
glow, and shelf detail visible).

Shipped at `data/icons/hicolor/scalable/apps/io.github.virinvictus.hermitage.svg`
for system-wide hicolor installation, plus mirrored at `logo.svg` in
the project root per the standard repo layout.

### Enhancements

**AppStream `<icon type="stock">` hint.** Explicit
`<icon type="stock">io.github.virinvictus.hermitage</icon>` in
`metainfo.xml` so software centers (GNOME Software, Flathub, etc.)
have a direct lookup for the icon name in addition to the desktop-id
launchable.

**AppStream branding colours updated to match the icon palette.** The
prior placeholder colours (`#fbf3e6` / `#241c14`) were a brown-toned
guess; replaced with `#f7e7d3` (warm cream sampled from the H ink) for
the light scheme and `#2c1424` (mid-aubergine sampled from the card
mid-tone) for the dark scheme, so the icon sits flush against software-
center backgrounds.

---

## v0.13.3 (2026-05-01) — App ID Rename

---

### Structural Improvements

**App ID renamed to `io.github.virinvictus.hermitage`.** The original
`dev.hermitage.Hermitage` ID assumed ownership of the `hermitage.dev`
domain, which would have blocked Flathub submission. The new ID follows
Flathub's canonical fallback convention for GitHub-hosted projects:
`io.github.<lowercased-username>.<lowercased-project>`.

Touched:

- `hermitage/app.py` — `APP_ID` constant. Also fixes the about-dialog
  `application_icon` reference.
- `data/dev.hermitage.Hermitage.desktop` → renamed via `git mv` to
  `data/io.github.virinvictus.hermitage.desktop`. Internal `Icon=` and
  `StartupWMClass=` updated.
- `data/dev.hermitage.Hermitage.metainfo.xml` → renamed similarly.
  `<id>`, `<launchable>`, and `<developer id>` updated.
- `roadmap.md` — Flatpak manifest entry updated to the new filename.

Both packaging files re-validate clean under `desktop-file-validate`
and `appstreamcli validate`.

---

## v0.13.2 (2026-05-01) — Packaging Metadata Scaffold

---

### Structural Improvements

**`data/dev.hermitage.Hermitage.desktop`.** Standard freedesktop entry —
Name, GenericName, Comment, Exec, Icon, Terminal=false, StartupWMClass,
and a Categories=GTK;Office;Viewer; chain. Validates clean under
`desktop-file-validate`. Ready to be installed to
`/usr/share/applications/` (or shipped via Flatpak).

**`data/dev.hermitage.Hermitage.metainfo.xml`.** AppStream metainfo
component for software-center listings (GNOME Software, KDE Discover,
Flathub). Includes summary, full feature description, GPL-3.0 license,
GitHub URLs (homepage, bugtracker, vcs), `oars-1.1` content rating,
control supports (pointing/keyboard/touch), `offline-only` internet
recommendation, brand colours for light/dark, and a release-notes
history back to v0.9.0. Validates clean under `appstreamcli validate`
(one pedantic note about screenshots — TODO once we have the icon and
a release build to capture against).

The icon (`dev.hermitage.Hermitage.svg`) remains the only outstanding
Phase 10 artifact before screenshots and a Flatpak manifest can land.

---

## v0.13.1 (2026-05-01) — Library Export

---

### New Features

**Export Library…** New menu item between Insights and Preferences.
Opens a `Gtk.FileDialog` save dialog with JSON and CSV filters; format
is inferred from the chosen extension (`.csv` → CSV, anything else →
JSON). Default name `hermitage-library.json`. On 4,272 books a JSON
export weighs ~8.5 MB and a CSV ~1.5 MB, written in well under a
second.

**Toast notifications.** New `Adw.ToastOverlay` wraps the main window
content. Export success/failure surfaces as a transient toast
("Exported 4,272 books → hermitage-library.json (JSON)") instead of a
modal dialog. Future async work (warming progress, history actions,
etc.) can hang notifications off `win._toast_overlay.add_toast()` with
no further plumbing.

### Structural Improvements

**`hermitage/export.py` (new module).** Two public functions —
`detect_format(path)` and `export_books(books, path, fmt=None)`. Pure
read-only reformatting of the in-memory `list[Book]`. CSV flattens
list-typed fields with `; ` and JSON-encodes the `identifiers` dict so
each row stays single-line. JSON keeps lists/dicts as native structure
for downstream tooling.

**Loading + error pages now go through the toast overlay.** The
loading StatusPage and the "Library Not Found" fallback both set the
overlay's child instead of replacing the toolbar's content directly,
so the overlay's toast capability is available the moment the window
appears.

---

## v0.13.0 (2026-05-01) — Library Insights

---

### New Features

**Library Insights window.** `Adw.Window` opened from the hamburger menu's
new "Library Insights" item. Lives in `hermitage/insights.py` and operates
entirely on the in-memory book list — no extra DB query, no background
work — so it pops open instantly on a 4,272-book library.

Sections, top to bottom:

- **At a glance** — five FlowBox tiles (Fraunces 28px display number on
  top, Plex Condensed uppercase label below): Books, Authors, Series,
  Tags, Identifiers. Plus a one-line dim-label note for the rated count
  and average rating when any books carry one.
- **Top Tags** — top 15 tags by book count, each row a name + proportional
  `Gtk.LevelBar` + count. Bars share a single `max_value` so visual
  weight is comparable.
- **Top Authors** — same pattern, top 15 authors.
- **Formats** — every format in the library, sorted by frequency.
- **Audit** — `Adw.ActionRow` + `boxed-list` rows for the four hygiene
  checks: missing cover files, books with no format files, books with no
  tags, books with no external IDs. Each row shows `N books (P%) — first,
  second, third, +X more` so the user can see what they'd be fixing.

### Structural Improvements

**`hermitage/insights.py`.** New module exposing `LibrarySummary`
dataclass (slots) and a single `summarize(books)` function that does all
aggregation in one pass with `collections.Counter`. The window is dumb —
it reads pre-computed values and renders. Splitting compute from render
keeps the constructor predictable and makes the summary easy to unit
test or repurpose.

**Reusable tile + bar-row helpers.** Internal `_make_tile`,
`_make_bar_row`, `_make_audit_row`, and `_section_title` keep render
code uniform; future sections (decade distribution, identifier-type
breakdown, etc.) can hang off the same primitives.

---

## v0.12.0 (2026-05-01) — Series Browser

---

### New Features

**Series browser.** Sibling page to the existing GenreBrowser, accessible
from a new `view-paged-symbolic` toggle in the header bar (next to the
genre toggle). The two are mutually exclusive — flipping one untoggles the
other so the view stack only ever shows one browse page at a time. Closing
either drops back to the grid (or the no-results page if a search is
active).

The page lists every series in the library as a clickable card. Each card
shows:

- **Name** (Fraunces 17px, weight 700, slight negative tracking) —
  the editorial focal point.
- **Index range** (Plex Condensed, accent color, uppercase tracking) —
  `#1 → #7` for contiguous runs, `#1 → #20 (incomplete)` when there are
  gaps in `series_index`.
- **Title hint** — `First Title  →  Last Title  (N books)` for series of
  3+, simpler renderings for 1- and 2-book series. Ellipsises tightly so
  long titles don't blow out the row.

Whole card is the click target; clicking sets the search to
`series:"<name>"` which the existing search pipeline already auto-sorts by
`series_index` (Phase 6 behaviour). Hover lifts the card with an accent
tint via `cubic-bezier(0.32, 0.72, 0, 1)` matching the cover-cell easing.

If the library has no series at all, the page renders an `Adw.StatusPage`
explaining how to set series in Calibre rather than an empty list.

### Structural Improvements

**`hermitage/series.py` (new module).** Single dataclass
`SeriesEntry(name, books)` plus a `_build_series_index()` aggregator that
groups the loaded library in pure Python — no extra DB query needed since
`Book.series` and `Book.series_index` already come down with the main
load. The aggregator computes `count` and a smart `index_range` property
(detects contiguous integer runs vs. gaps).

**Shared "default view" predicate.** `_show_default_view()` inside
`_build_layout` collapses the grid-vs-no-results decision into one place,
called from both browser-toggle handlers. Search-clear paths and the
no-results swap now check `not (genre or series)` so clearing a search
while on a browser page leaves you on that browser page.

---

## v0.11.0 (2026-05-01) — Identifiers & Tag Hierarchy Parity

---

### New Features

**Identifier links in the Codex.** A new "Find this book on" section
between Tags and Synopsis renders one pill button per known identifier
type. Clicking a pill opens the corresponding external page via
`Gtk.UriLauncher`. Twelve types currently URL-formatted: `isbn` →
Open Library, `goodreads`, `google` Books, `amazon`/`asin`/`mobi-asin` →
Amazon, `barnesnoble`, `storygraph`, `hardcover`, `fictiondb`, `doi`,
and bare `url`/`uri`. Unknown types are silently skipped — they remain
in the underlying data, they just don't get a pill until we know how to
turn them into a URL. With 14,275 identifier rows across the test
library this surface is meaningful; about 75% of books get at least one
clickable pill.

### Enhancements

**Tag-hierarchy search parity with cquarry.** `hermitage/search.py`
previously did naive substring matching on each tag, so `tags:Fic`
matched any tag containing the letters "Fic" (including, absurdly,
"Sci-Fi"). The matcher now follows cquarry's `_match_tags` semantics
exactly: non-exact `tags:Foo` matches the literal tag `Foo`
(case-insensitive) **or** any tag prefixed by `Foo.`. Substring
matching is gone for tags only — the dot-separated tag tree is
hierarchical by convention so this is the right semantic. Verified
against the live library:
- `tags:Fic` → 2008 books (entire `Fic.*` subtree)
- `tags:Fantasy` → 0 (no top-level "Fantasy" tag in this library)
- `tags:"Fic.Fantasy"` → 929 (all `Fic.Fantasy.*` descendants)

`tags:"=Foo"` exact match remains exact and case-insensitive. Other
field semantics (authors, title, series, formats) are unchanged.

### Structural Improvements

**`Book.identifiers: dict[str, str]`.** New field on the dataclass.
Bulk-loaded in `database.load_library()` via a single
`SELECT book, type, val FROM identifiers` after the main books query —
zero N+1 risk on a 4,272-book library (DB load stays at ~60 ms).
The merge happens in Python with one dict per book, attached during
Book construction.

**`_IDENTIFIER_LINKS` table.** Module-level dict in `codex.py` mapping
identifier scheme → (display label, URL format). Adding a new scheme is
a one-line edit; no other code changes needed.

---

## v0.10.1 (2026-05-01) — Phase 9 Polish (almost)

---

### New Features

**About dialog.** `Adw.AboutDialog` reachable from the hamburger menu's new
"About Hermitage" item. Pulls the running version via
`importlib.metadata.version("hermitage")` so it's always in sync with
`pyproject.toml`. Lists GPL-3.0, the GitHub URL, and an issue tracker link.

**Cover-cell tooltips.** Each grid cell now gets a multi-line tooltip on
hover with title, "by …" author list, series + index when present, and the
format list — useful when the hover-label ellipsises and for users on
touchpads who can't reliably trigger `:hover`. Also doubles as the
accessible name for AT-SPI screen readers.

**Grid scroll position memory.** Applying a filter (typing in the search,
clicking a Calibre virtual library, switching to Recently Read) now
captures the current `Gtk.ScrolledWindow` vadjustment value into
`win._saved_scroll`. Clearing back to All Books restores it on the next
idle tick (after the GridView re-lays out the unfiltered store). Subsequent
filters keep the same saved value until a clear consumes it.

### Enhancements

**Animations consistency pass.** The view-stack crossfade between grid /
genre browser / no-results bumped from 200 ms to 240 ms for slightly more
ceremony when switching modes. Cover-cell hover transitions converted from
symmetric `ease-in-out` to a Cocoa-style `cubic-bezier(0.32, 0.72, 0, 1)`
spring — feels closer to a flick than a fade. Hover lift extended from
4 px / 12 px shadow to 6 px / 16 px so the lifted card reads more
clearly against the gradient placeholder backgrounds.

**Accessibility tooltips.** Added explicit tooltips to icon-only and
ambiguous controls: the Codex dismiss button (with the Esc shortcut hint),
the Read button, the author / series link buttons, and every dynamically-
created tag pill. GTK 4 uses `tooltip-text` as the default accessible name
when no explicit label is set, so this doubles as the screen-reader pass.

### Structural Improvements

**`HermitageApp._save_scroll_if_unfiltered` / `_restore_scroll`.** Two
small static helpers keep the scroll-memory logic in one place; both filter
entry points (debounced search apply, Recently Read activation) call them
and the clear paths trigger the restore. The restore is dispatched via
`GLib.idle_add` so the vadjustment has a valid upper bound by the time we
write to it.

---

## v0.10.0 (2026-05-01) — Phase 8: Reading History

---

### New Features

**Local reading-history database.** New `hermitage/history.py` module backed
by SQLite at `~/.local/share/hermitage/history.db`. The schema is
intentionally minimal — a single `opens(book_id, opened_at)` event-log table
with indexes on both columns — so future stats (books-this-week, streaks,
etc.) can be derived without a migration. Critically, Hermitage **never**
writes to Calibre's `metadata.db`; this file lives in the user's data dir
and is independent of any Calibre library you point at. Public API:
`record_open(book_id)`, `is_opened(book_id)` (O(1) via in-memory cache),
`opened_book_ids()`, `last_opened_for(book_id)`, `recently_read(limit=50)`,
and `humanize(ts)` for "3 days ago"-style strings.

**Read button now writes history.** `CodexView._on_read_clicked` records the
open event the moment the launcher fires (don't wait for the launcher to
race a window-close — the click itself is the user signal we care about).
A new `CodexView.on_book_opened` callback is wired by `app.py` to
`Gtk.FilterListModel`'s filter so the grid rebinds visible cells and the
read indicator appears immediately.

**Read indicator on the grid.** Each cover cell now overlays a small green
`emblem-ok-symbolic` badge in the top-right when the book has at least one
open event. Sized 14px with a 4px pad and a soft drop shadow so it reads
against any cover artwork without dominating it. Badge visibility is
recomputed on every bind (cells recycle), gated on `history.is_opened()`.

**"Last read" line in the Codex.** A new label in the meta block surfaces
`Last read:  3 days ago` (or "just now", "15 minutes ago", "1 month ago",
etc.) for any book with open history. Refreshes immediately after a Read
click so the user sees their action confirmed without leaving the Codex.

**"Recently Read" virtual library.** Synthetic VL row inserted into the
sidebar between "All Books" and the Calibre-defined VLs. Bypasses the
Calibre search expression mechanism — it's handled directly by the new
`HermitageApp._apply_recently_read()` which reorders the store by recency
and applies a set-membership filter. With zero history, the no-results page
shows tailored copy ("Open a book and it'll appear in Recently Read.").
Title subtitle reads `Recently Read · N of M books` while the VL is active.
Switching back to All Books restores the configured sort.

### Enhancements

**Search-clear path now restores configured sort.** `_on_search_changed`'s
immediate clear branch previously left whatever ordering the prior filter
had imposed (Recently Read or `series:` queries mutate the store). It now
calls `_resort_grid(win)` so emptying the search bar always returns the
grid to the user's preferred sort.

### Structural Improvements

**Module-level opened-id cache in `history.py`.** `_opened_cache`
populated lazily by the first `opened_book_ids()` or `is_opened()` call,
updated synchronously by `record_open()`. Keeps the grid's bind hot path
out of SQLite — 4,272 cells × `is_opened()` per scroll would otherwise hit
the DB on every keystroke that re-filters the model.

---

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
