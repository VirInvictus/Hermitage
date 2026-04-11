# Roadmap: Hermitage (Tokyo/3.14 Edition)

## Phase 1: The Engine (Python 3.14 Foundation)
- [x] **Repository Setup:** Modern Python 3.14 structure with `pyproject.toml`.
- [x] **Database Logic:** `database.py` with read-only Calibre `metadata.db` parser.
    - Implement the `Book` data model with PEP 649 annotations.
    - Joined query for books, authors, series, tags, ratings, comments, formats.
- [x] **FTS5 Search:** In-memory FTS5 index built from loaded books — prefix matching across titles, authors, tags, and series.
- [x] **Data Verification:** `hermitage-verify` CLI tool. Validates all book directories, cover files, and format presence. Bench-tests path resolution (69ms load + 59ms scan for 4,014 books).
- [x] **Asset Processing Worker:** Pillow median-cut color quantizer extracts 5 dominant colors per cover, sorted by vibrancy. Thread-pooled with disk + memory caching in `~/.cache/hermitage/colors/`.

## Phase 2: The Sanctuary (GNOME 50 Grid)
- [x] **Window Architecture:** Initialize `Adw.Application` with `AdwToolbarView` and `AdwHeaderBar`.
- [x] **The Gallery Grid:** Implement `Gtk.GridView` with `Gtk.SignalListItemFactory`.
    - Cover art cells with `Gtk.Picture` + `Gtk.Overlay` title labels.
    - CSS hover transforms (scale up) and fade-in title on hover/focus.
- [x] **Strict Aspect Ratios:** `Gtk.AspectFrame` with fixed 2:3 ratio and `overflow: hidden` clipping on the overlay. Cells don't stretch.
- [x] **Dynamic Styling:** Per-cell `CssProvider` maps dominant cover color to hover `box-shadow` glow and focus ring. Async color delivery for cold cache.
- [x] **Tokyo Breakpoints:** `Adw.Breakpoint` rules — narrow (<500sp): 2-3 cols, medium (<900sp): 3-5 cols, wide (default): 3-12 cols.

## Phase 3: The Codex (Premium Detail View)
- [x] **Layout:** Implement `Adw.OverlaySplitView` for the book sidebar.
- [x] **The Hero Banner:** Build a custom header widget that uses a heavily blurred, darkened version of the book cover as the background behind the title/author typography.
- [x] **Metadata Density:** Implement a wrapping flow box (`Gtk.FlowBox`) to render tags (e.g., Grimdark, Fantasy, Sci-Fi) as styled Libadwaita "pills" or chips.
    - Style the synopsis view using Libadwaita `.body` class and `Adw.Clamp` for high legibility.
- [x] **Native Handlers:** Connect a prominent, styled "Read" button to `Gtk.FileLauncher` to launch system PDF/EPUB readers (e.g., Foliate, Papers).

## Phase 4: Polish & Caching
- [x] **Thumbnailing:** Pillow-based thumbnail cache in `~/.cache/hermitage/thumbs/` with async generation and cache warming.
- [x] **Keyboard Navigation / Shortcuts:** Escape (dismiss codex/search/sidebar), Ctrl+F (toggle search), Ctrl+L (toggle virtual library sidebar).
- [x] **Search Parameters:** Calibre-compatible search bar with field prefixes (`tags:`, `title:`, `authors:`, `series:`, `formats:`, `rating:`), quoted values, exact match (`=`), boolean operators (`and`/`or`/`not`), parentheses, and `vl:` virtual library references. Slides below header via GNOME `Gtk.SearchBar` pattern.
- [x] **Virtual Library Support:** Left sidebar reading `virtual_libraries` from the Calibre `preferences` table. Clicking a library applies its search expression. Toggle via header button or Ctrl+L.
- [x] **Dismiss details button:** Close button overlaid on the Codex hero banner (top-right, circular, semi-transparent).

## Phase 5: Configuration & First Run
- [ ] **YAML config file:** `~/.config/hermitage/config.yaml` as the single source of truth. Stores library path, default sort order, grid density, and any future preferences. Human-readable and editable in any text editor.
- [ ] **First-run wizard:** On launch with no config file, present an `Adw.Window` that walks the user through selecting a Calibre library directory (file chooser) and writes the initial config. No assumptions about where the library lives.
- [ ] **Settings page:** In-app `Adw.PreferencesWindow` that reads and writes the same YAML config file. Sections for library path, sort order, and display preferences. Changes take effect immediately where possible, or prompt a restart.
- [ ] **Config migration:** `HERMITAGE_DB` environment variable still works as an override, but the wizard and settings page write to the YAML file. Precedence: env var > config file > wizard prompt.

## Phase 6: Sort & Browse
- [ ] **Sort options:** Header bar dropdown or menu to sort by title (current default), author, date added, publication date, rating, and series order. Sort direction toggle (ascending/descending). Persisted to config.
- [ ] **Series browsing:** When browsing a series, books are sorted by `series_index` regardless of the global sort. Series name shown as a group header or badge.
- [ ] **Author grouping:** Option to group the grid by author, with author name as a section header above their books.
- [ ] **Tag hierarchy browsing:** Calibre tags use dot-separated hierarchies (e.g., `Fic.Fantasy.Grimdark`). Expose this tree structure in the VL sidebar or a dedicated tag browser, allowing drill-down filtering.

## Phase 7: Empty States & Error Resilience
- [ ] **Placeholder covers:** Generate a styled placeholder for books without `cover.jpg` — display the title and author on a tinted card using the dominant color of the app accent or a neutral tone. No more invisible cells.
- [ ] **No-results state:** When a search returns zero matches, show an `Adw.StatusPage` with a relevant message and suggestion (e.g., "No books match — try a broader search"). Replace the empty grid, don't just leave it blank.
- [ ] **Loading progress:** Replace the static "Loading Library..." status page with an indication of progress — book count loaded, thumbnail cache warming percentage, or at minimum a spinner with a subtitle that updates.
- [ ] **Graceful degradation:** Handle corrupt covers (truncated JPEG, zero-byte files) without crashing the thumbnail or color pipelines. Surface warnings in the UI or console log rather than silently swallowing them.
- [ ] **Database lock handling:** If `metadata.db` is locked by Calibre (write lock during import), show a clear error with a retry option instead of hanging or crashing.

## Phase 8: Reading History
- [ ] **Local history database:** A small SQLite database at `~/.local/share/hermitage/history.db` tracking which books have been opened via the "Read" button, with timestamps. Hermitage never writes to Calibre's database.
- [ ] **Recently read shelf:** A "Recently Read" row or section at the top of the grid (or a virtual library entry) showing the last N books opened, sorted by last-opened time.
- [ ] **Read indicator:** Subtle visual badge on cover cells for books that have been opened at least once — small dot, checkmark, or opacity shift. Unobtrusive but visible.
- [ ] **Codex integration:** Show "Last read: 3 days ago" or similar in the Codex metadata section when a book has history.

## Phase 9: Polish & Visual Refinement
- [ ] **About dialog:** `Adw.AboutDialog` with version, description, license (GPL-3.0), author, and links (source repo, Ko-fi).
- [ ] **Animations:** Smooth transitions for codex open/close, search bar slide, VL sidebar toggle. Review existing transitions for consistency and timing.
- [ ] **Grid scroll position memory:** Remember scroll position when returning from a filtered view or after closing the codex. Don't jump back to the top.
- [ ] **Tooltip refinements:** Hover tooltips on cover cells showing full title, author, and format list for long titles that get ellipsized.
- [ ] **High-DPI audit:** Verify thumbnail resolution, blur quality, and CSS shadows render sharply on 2x and 3x displays. Adjust `set_size_request` values if needed.
- [ ] **Accessibility:** Ensure keyboard navigation works end-to-end (grid focus, codex navigation, search, VL sidebar). Screen reader labels on interactive elements.

## Phase 10: Packaging & 1.0 Release
- [ ] **Application icon:** Design and ship a scalable SVG icon following the GNOME icon guidelines. Install to the hicolor icon theme.
- [ ] **Desktop entry:** `dev.hermitage.Hermitage.desktop` file with proper categories, icon reference, and `StartupWMClass`.
- [ ] **AppStream metadata:** `dev.hermitage.Hermitage.metainfo.xml` with screenshots, release notes, and OARS content rating for software center listings.
- [ ] **Flatpak manifest:** `dev.hermitage.Hermitage.yml` targeting the GNOME 50 runtime. Bundle all Python dependencies. Test on a clean system.
- [ ] **Final testing:** Full regression pass on a 4,000+ book library. Verify every feature end-to-end: first-run wizard, search, VL sidebar, codex, read button, sort options, reading history, placeholder covers, breakpoints.
- [ ] **Version 1.0.0:** Bump version, write release patchnotes, tag the release, publish Flatpak and PyPI package.
