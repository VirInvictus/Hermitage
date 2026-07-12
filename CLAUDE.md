# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hermitage is a Python 3.14 / GTK 4 desktop app that reads a Calibre `metadata.db` **read-only** and renders the library as a cover-art grid with a sliding detail pane ("Codex") and tag-tree genre browser. It is single-user and 100% local — no network, no accounts, no telemetry. Read `spec.md` and `roadmap.md` for the design intent and what's done vs. planned.

**No libadwaita (as of v0.17.0, Phases 13/14).** Hermitage is Hyprland-native: plain GTK 4 + PyGObject, a stylesheet it owns (`style.css` + the Kanagawa Dragon palette in `theme.py`), and portal-based follow-system dark/light. The owned successors to the adwaita widgets live in `hermitage/widgets.py` (`Clamp`, `WindowTitle`, `ToastOverlay`, `StatusPage`, `value_row`/`boxed_list`). Don't reintroduce `Adw` — a guard test (`tests/test_guards.py`) fails if you do. See spec.md §2a for the design language.

## Run / verify

```bash
# Run the app (uses ~/.config/hermitage/config.yaml; first run launches the wizard)
python -m hermitage

# Override the library path without touching the config
HERMITAGE_DB="/home/bdkl/docs/Calibre Library/metadata.db" python -m hermitage

# Console scripts (after `pip install -e .`)
hermitage
hermitage-verify   # integrity check + path-resolution benchmark, exits non-zero on issues
```

The test suite lives in `tests/` (63 stdlib-unittest tests, CalibreQuarry style: temp sqlite fixtures, no display needed): `python -m unittest discover -s tests`. Lint is `ruff check hermitage/` (config in `pyproject.toml`; E402 is per-file-ignored for the `gi.require_version` pattern). There is still no build step. For anything the tests can't see (GTK surfaces), the verification path is `hermitage-verify` against the real library plus a manual GTK smoke run. If you change DB queries, cover resolution, or color/thumb pipelines, run the tests **and** `hermitage-verify` before declaring done.

System deps on Fedora: `gtk4`, `python3-gobject` (already installed; libadwaita is no longer imported). PyPI deps: `PyGObject`, `Pillow`, `PyYAML` (declared in `pyproject.toml`).

## Hard constraints

- **The Calibre DB is read-only.** All connections go through `database._connect()`, which opens `file:...?mode=ro`. Do not add write paths and do not modify anything under `/home/bdkl/docs/Calibre Library/`. The test library lives there with 4,000+ books.
- **Library path resolution precedence** (`database._resolve_library_path`): `HERMITAGE_DB` env var → `library_path` in `~/.config/hermitage/config.yaml` → raise `FileNotFoundError` so `app.do_activate` can launch the first-run wizard. Preserve this order.
- **Caches are user-scoped, not repo-scoped:** `~/.cache/hermitage/{thumbs,colors,blur}/`. Safe to delete by hand for testing; the app regenerates them.

## Architecture (the parts that span multiple files)

Entry point chain: `__main__.main` (installs SIGINT handler) → `app.run` → `HermitageApp.do_activate`. If no config and no `HERMITAGE_DB`, the wizard runs first; otherwise `_build_window` shows a "Loading…" status page and `GLib.idle_add`s `_load_library`, which calls `database.load_library()` (a single joined SQL query, sorted by `b.sort COLLATE NOCASE`) and then assembles the UI.

The window is a **titlebar + overlay stack** (`app._build_chrome` / `_build_layout`). The two sidebars are `Gtk.Revealer` panels floated over the grid (they slide in over the covers, not pushing the grid), and the search bar sits in a column below the titlebar:

```
Gtk.ApplicationWindow
├─ titlebar = Gtk.HeaderBar (show-title-buttons off; Ctrl+Q quits)
└─ widgets.ToastOverlay
   └─ Gtk.Box (vertical)
      ├─ Gtk.SearchBar
      └─ Gtk.Overlay (main content)
         ├─ child   = Gtk.Stack (grid / genres / series / no-results)
         │            └─ ScrolledWindow → Gtk.GridView (the Sanctuary)
         ├─ overlay = Gtk.Revealer (START, vl_revealer = virtual libraries)
         └─ overlay = Gtk.Revealer (END, codex_revealer = CodexView)
```

Grid column density is `Gtk.GridView`'s own fitting between `min_columns=1` and `max_columns=12` (no `Adw.Breakpoint`). Dark/light and the palette come from `theme.init()` (the single theme path).

The grid uses `Gio.ListStore[BookObject]` → `Gtk.FilterListModel` (with a `Gtk.CustomFilter` that the search wires up) → `Gtk.SingleSelection` → `Gtk.GridView`. `BookObject` is a thin `GObject.Object` wrapper because `Gio.ListStore` cannot hold plain dataclasses. Sorting is done by **rebuilding** the `ListStore` (`_resort_grid`), not by a `Gtk.Sorter`, because the same store also feeds the filter model.

**Cover pipeline** (`thumbnailer.py` + `colors.py`, both 4-thread `ThreadPoolExecutor`s):

1. `warm_cache(covers)` and `warm_color_cache(books)` fire after library load to pre-generate the disk caches.
2. `_bind_cover` calls `get_cached_texture` / `get_cached_colors` (O(1), main-thread). On miss, it requests async work; the callback re-checks `list_item.get_item().book.id` against the captured `book_id` because cells are recycled — without that guard, scrolling fast paints stale covers.
3. `_apply_color_css` attaches a per-cell `Gtk.CssProvider` keyed off the dominant color for hover glow / focus ring. `_unbind_cover` must remove the provider, or providers leak across the display every scroll.

**Search** (`search.py`) is a hand-written tokenizer + recursive-descent parser for the Calibre query language. AST nodes: `FieldExpr`, `BareExpr`, `AndExpr`, `OrExpr`, `NotExpr`. Implicit AND between adjacent primaries is handled in `_and_expr`. `vl:"Name"` resolves through a `VirtualLibraryResolver` callback that the app builds from `database.load_virtual_libraries()` (Calibre stores these as JSON in the `preferences` table). The search entry has a 400 ms debounce in `_on_search_changed`; clearing it bypasses the debounce.

**The Codex** (`codex.py`) is the END sidebar. The hero banner is a Pillow `GaussianBlur(r=30)` of the cover, generated by a separate 2-thread executor and cached in `~/.cache/hermitage/blur/`. Clicking author / series / tag pills calls `on_search`, which the app wires to populate the search bar — this is also the `genres.GenreBrowser` integration point (`on_search` hides the genre view and applies the filter).

**Config** (`config.py`) is module-level cached (`_config`); `reload_config()` exists for the rare case the file changes underneath. Only three keys today: `library_path`, `sort_field`, `sort_ascending`. Sort field/direction are also exposed as `Gio.SimpleAction`s (`app.sort-field`, `app.sort-ascending`) so menu toggling persists through `cfg_set` and triggers `_resort_grid`.

**Styling** is a single `style.css` shipped as package data (`pyproject.toml` `package-data`). It's loaded once via `Gtk.CssProvider` at app priority; per-cell color glow is layered on top at `APPLICATION + 1`.

## Sister project: CalibreQuarry

`../CalibreQuarry/` (the `cquarry` CLI) reads the same `metadata.db` and has battle-tested logic Hermitage wants. Roadmap **Phase 11** tracks porting as much of it as makes sense into `hermitage/`. When you touch `database.py` or search, check `../CalibreQuarry/src/cquarry/db.py` first — don't reinvent code that already exists there.

The **locked-DB fallback** from `CalibreDB._open` is already ported into `database._connect()` (snapshot copy of the `.db` plus `-wal`/`-shm` siblings when Calibre holds the lock, one stderr note, atexit cleanup) and is covered by a test that takes a real `BEGIN EXCLUSIVE` lock. The author query also follows cquarry's ordered-subquery approach (`ORDER BY bal.id`, pipe-escaped commas restored). The main Phase 11 item still open is **custom columns** (`db.get_custom_columns()` / `db.load_custom_column()`).

## Conventions specific to this project

- Python 3.14 with `from __future__ import annotations` and `@dataclass(slots=True)` everywhere. Match it.
- Errors that should fall through to the wizard or status page are raised as `FileNotFoundError` in `database` and caught at the app boundary — don't swallow them lower.
- New modules go in `hermitage/` and are wired from `app.py`. Keep `database.py` schema-only; don't put UI logic there.
- **Update `patchnotes.md` for every code change.** Style is the `getMusic` patchnotes format: versioned headers with dates, categorized sections (New Features, Enhancements, Bug Fixes, Structural Improvements), bold lead-ins, and technical prose explaining *what* and *why*. Keep a running log so prior work doesn't have to be re-explained.
- The home `~/CLAUDE.md` (terse responses, no destructive git, etc.) still applies.
