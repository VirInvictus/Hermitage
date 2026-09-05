# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hermitage is a Python 3.14 / GTK 4 desktop app that reads a Calibre `metadata.db` **read-only** and renders the library as a cover-art grid with a sliding detail pane ("Codex") and tag-tree genre browser. It is single-user and 100% local — no network, no accounts, no telemetry. Read `spec.md` and `roadmap.md` for the design intent and what's done vs. planned.

**No libadwaita (as of v0.17.0, Phases 13/14).** Hermitage is Hyprland-native: plain GTK 4 + PyGObject, a stylesheet it owns (`style.css` + the Kanagawa Dragon palette in `theme.py`), and portal-based follow-system dark/light. The owned successors to the adwaita widgets live in `hermitage/widgets.py` (`Clamp`, `WindowTitle`, `ToastOverlay`, `StatusPage`, `value_row`/`boxed_list`). Don't reintroduce `Adw` — a guard test (`tests/test_guards.py`) fails if you do. See spec.md §2a for the design language.

**Every toplevel must be registered with the `Gtk.Application`.** Pass `application=` when constructing any `Gtk.Window` / `Gtk.AboutDialog` (or call `app.add_window`). A window that skips it does not inherit the app id: GTK falls back to `g_get_prgname()`, the Wayland surface reports `python`, and a Hyprland `windowrulev2` keyed on the app id silently misses it. That was a real bug in all four secondary windows until v0.18.1. `tests/test_guards.py::TestSecondaryWindowAppId` walks the package AST and fails on any construction that omits it.

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

The test suite lives in `tests/` (stdlib-unittest, CalibreQuarry style: temp sqlite fixtures, no display needed): `python -m unittest discover -s tests`. Run it with the **system** python or a venv that has PyGObject/PyYAML installed — a bare venv without `gi` will report import errors for the GUI-touching modules. Lint is `ruff check hermitage/` (config in `pyproject.toml`; E402 is per-file-ignored for the `gi.require_version` pattern). There is still no build step. For anything the tests can't see (GTK surfaces), the verification path is `hermitage-verify` against the real library plus a manual GTK smoke run. If you change DB queries, cover resolution, or color/thumb pipelines, run the tests **and** `hermitage-verify` before declaring done.

System deps on Fedora: `gtk4`, `python3-gobject` (already installed; libadwaita is no longer imported). PyPI deps: `PyGObject`, `Pillow`, `PyYAML`, `cquarry`. The cquarry dependency is declared as an unpinned git dep on `main` (pyproject enforces no version; CI installs `@main` fresh), and the Flatpak manifest separately pins an exact cquarry commit that must be bumped with each cquarry release. APIs the tree calls today need cquarry ≥1.8 (`get_comments`, `tag_rollup`, `cquarry.integrity`, on top of 1.6's `get_user_categories` and `@Name` search); patchnotes record the per-release floors.

## Hard constraints

- **The Calibre DB is read-only.** All connections go through `database.get_cquarry_db()`, which opens via cquarry's read-only URI. Do not add write paths and do not modify anything under `/home/bdkl/docs/Calibre Library/`. The test library lives there with 4,000+ books.
- **No reach-ins.** Nothing outside cquarry touches `db.conn` — bulk comments come from `get_comments()` (1.8), bulk identifiers from the hydrated rows, and path/cover logic from `get_cover_path()`/`get_formats()`. If cquarry lacks a read you need, add it there (the Cross-Repo Implementation Rule), never reach around it.
- **cquarry ≥1.1 field contract:** `get_all_books()` rows expose `authors`, `tags`, `languages`, `formats` as native `list[str]`. Never `.split(",")` them; author names may contain literal commas. The only legacy transform still applied is restoring Calibre's historical `|` pipe-escaped comma in author display names (`database.load_library`).
- **Sidebar wiring:** `win._vl_defs` is populated in `app._load_library()` from `load_virtual_libraries()`; `_build_vl_sidebar` applies Calibre's stored order/hidden state via `database.load_vl_ui_state()`. Saved-search rows carry the sentinel `__saved__:<name>` on `row._vl_name` and are expanded to `search:"<name>"` in `_on_vl_activated`; user-category rows carry `__usercat__:<name>` and resolve to cquarry's native `@<name>:true` location (cquarry ≥1.6; exact member semantics upstream parity).
- **Ratings render through cquarry:** use `normalize_rating()` (from `cquarry.helpers`) for star conversion — no local `/2` integer division; half-stars are expected.
- **Library path resolution precedence** (`database._resolve_library_path`): `HERMITAGE_DB` env var → `library_path` in `~/.config/hermitage/config.yaml` → raise `FileNotFoundError` so `app.do_activate` can launch the first-run wizard. Preserve this order.
- **Caches are user-scoped, not repo-scoped:** `~/.cache/hermitage/{thumbs,colors,blur}/`. Safe to delete by hand for testing; the app regenerates them.

## Architecture (the parts that span multiple files)

Entry point chain: `__main__.main` (installs SIGINT handler) → `app.run` → `HermitageApp.do_activate`. If no config and no `HERMITAGE_DB`, the wizard runs first; otherwise `_build_window` shows a "Loading…" status page and `GLib.idle_add`s `_load_library`, which calls `database.load_library()` (a single joined SQL query, sorted by `b.sort COLLATE NOCASE`) and then assembles the UI.
- **Comments are JIT (1.8.0).** `load_library()` does NOT fetch comments; `Book.comment is None` means "not yet fetched", `""` means the library has none. The Codex fetches on activation via `database.get_comment_for()` (short-lived read) and memoizes onto the Book; exports pass `database.get_all_comments()` explicitly (pure export_books stays DB-free). Never reintroduce a whole-library `get_comments()` at startup — it was the slowest line of the load on five-figure libraries.
- **Insights computes off the UI thread (1.8.0).** `InsightsWindow` opens on a placeholder and runs `summarize()` on a worker thread that opens its OWN short-lived CalibreDB (`_resolve_library_path()`), never the shared `get_cquarry_db()` singleton — cquarry connections are single-threaded by design, and the UI thread queries its own. Results land via `GLib.idle_add`; a `destroy` flag guards post-close callbacks.

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

