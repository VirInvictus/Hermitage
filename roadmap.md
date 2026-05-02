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
- [x] **Clean Ctrl+C exit:** `SIGINT` handler in `__main__.py` exits cleanly instead of spewing GTK error traces.
- [x] **Search debounce:** 400ms debounce on keystroke — grid doesn't re-filter until you stop typing. Clearing the search bar applies immediately.
- [x] **Clickable Codex metadata:** Clicking the author name, series, or any tag pill in the Codex populates the search bar with the corresponding filter (`authors:"Name"`, `series:"Name"`, `tags:"Tag"`).
- [x] **Tags as genre:** Tags are surfaced as the genre system throughout the UI.
- [x] **Genre browser:** Attractive category page (`GenreBrowser`) showing all tags organized by dot-separated hierarchy with book counts. Top-level categories as cards, sub-genres as clickable pills. Accessible via header bar toggle button.
- [x] **YAML config file:** `~/.config/hermitage/config.yaml` as the single source of truth. Stores library path, default sort order, grid density, and any future preferences. Human-readable and editable in any text editor.
- [x] **First-run wizard:** On launch with no config file, present an `Adw.Window` that walks the user through selecting a Calibre library directory (file chooser) and writes the initial config. No assumptions about where the library lives.
- [x] **Settings page:** In-app `Adw.PreferencesWindow` that reads and writes the same YAML config file. Sections for library path, sort order, and display preferences. Sort changes take effect immediately.
- [x] **Config migration:** `HERMITAGE_DB` environment variable still works as an override, but the wizard and settings page write to the YAML file. Precedence: env var > config file > wizard prompt.

## Phase 6: Sort & Browse
- [x] **Sort options:** Header bar sort menu with six fields (title, author, date added, publication date, rating, series) and ascending/descending toggle. Sort icon updates to reflect direction. Persisted to config. Also accessible from the preferences page.
- [x] **Series browsing:** When filtering by `series:`, the grid auto-sorts by `series_index` regardless of the global sort setting. Clearing the search restores the configured sort.
- [x] **Tag hierarchy browsing:** Genre browser exposes the full dot-separated tag tree (e.g., `Fic.Fantasy.Grimdark`) as nested cards with clickable pills. Clicking any genre filters the grid and switches back to the grid view.
- [x] **Author/series browse via Codex:** Clicking author or series in the detail view populates the search, effectively browsing by that dimension.

## Phase 7: Empty States & Error Resilience
- [x] **Placeholder covers:** Generate a styled placeholder for books without `cover.jpg` — display the title and author on a tinted card using the dominant color of the app accent or a neutral tone. No more invisible cells.
- [x] **No-results state:** When a search returns zero matches, show an `Adw.StatusPage` with a relevant message and suggestion (e.g., "No books match — try a broader search"). Replace the empty grid, don't just leave it blank.
- [x] **Loading progress:** Replace the static "Loading Library..." status page with an indication of progress — book count loaded, thumbnail cache warming percentage, or at minimum a spinner with a subtitle that updates.
- [x] **Graceful degradation:** Handle corrupt covers (truncated JPEG, zero-byte files) without crashing the thumbnail or color pipelines. Surface warnings in the UI or console log rather than silently swallowing them.
- [x] **Database lock handling:** If `metadata.db` is locked by Calibre, transparently fall back to a snapshot copy instead of failing or hanging. Mirror the approach in `../CalibreQuarry/src/cquarry/db.py` (`CalibreDB._open`): try `mode=ro` first; on `OperationalError` containing "locked", `shutil.copy2` the `.db` plus its `-wal` and `-shm` siblings to a `tempfile.mkstemp` path and open the copy. Log a one-line note that we're reading from a snapshot. Clean up the temp files on shutdown.

## Phase 8: Reading History
- [x] **Local history database:** A small SQLite database at `~/.local/share/hermitage/history.db` tracking which books have been opened via the "Read" button, with timestamps. Hermitage never writes to Calibre's database.
- [x] **Recently read shelf:** A "Recently Read" row or section at the top of the grid (or a virtual library entry) showing the last N books opened, sorted by last-opened time.
- [x] **Read indicator:** Subtle visual badge on cover cells for books that have been opened at least once — small dot, checkmark, or opacity shift. Unobtrusive but visible.
- [x] **Codex integration:** Show "Last read: 3 days ago" or similar in the Codex metadata section when a book has history.

## Phase 9: Polish & Visual Refinement
- [x] **Typography pass:** Bundled type system — Fraunces (display), Inter Variable (body), IBM Plex Sans Condensed (labels/pills). Fonts ship in `hermitage/fonts/` and register at startup via `Pango.FontMap.add_font_file()`; size, weight, tracking, and feature-settings tuned across every styled class. See v0.9.1 patchnotes.
- [x] **About dialog:** `Adw.AboutDialog` with version, description, license (GPL-3.0), author, and links (source repo, Ko-fi).
- [x] **Animations:** Smooth transitions for codex open/close, search bar slide, VL sidebar toggle. Review existing transitions for consistency and timing.
- [x] **Grid scroll position memory:** Remember scroll position when returning from a filtered view or after closing the codex. Don't jump back to the top.
- [x] **Tooltip refinements:** Hover tooltips on cover cells showing full title, author, and format list for long titles that get ellipsized.
- [ ] **High-DPI audit:** Verify thumbnail resolution, blur quality, and CSS shadows render sharply on 2x and 3x displays. Adjust `set_size_request` values if needed.
- [x] **Accessibility:** Ensure keyboard navigation works end-to-end (grid focus, codex navigation, search, VL sidebar). Screen reader labels on interactive elements.

## Phase 10: Packaging & 1.0 Release
- [ ] **Application icon:** Design and ship a scalable SVG icon following the GNOME icon guidelines. Install to the hicolor icon theme.
- [ ] **Desktop entry:** `dev.hermitage.Hermitage.desktop` file with proper categories, icon reference, and `StartupWMClass`.
- [ ] **AppStream metadata:** `dev.hermitage.Hermitage.metainfo.xml` with screenshots, release notes, and OARS content rating for software center listings.
- [ ] **Flatpak manifest:** `dev.hermitage.Hermitage.yml` targeting the GNOME 50 runtime. Bundle all Python dependencies. Test on a clean system.
- [ ] **Final testing:** Full regression pass on a 4,000+ book library. Verify every feature end-to-end: first-run wizard, search, VL sidebar, codex, read button, sort options, reading history, placeholder covers, breakpoints.
- [ ] **Version 1.0.0:** Bump version, write release patchnotes, tag the release, publish Flatpak and PyPI package.

## Phase 11: CalibreQuarry Feature Port

Port as much of `../CalibreQuarry` (the `cquarry` CLI) into Hermitage as makes sense for a GUI library viewer. CalibreQuarry already has battle-tested logic for many things Hermitage will eventually want; rather than rewrite, lift the modules in `../CalibreQuarry/src/cquarry/` and adapt them to our `Book` dataclass and GTK surfaces.

- [x] **DB lock fallback** (see Phase 7 bullet) — port `CalibreDB._open` into `hermitage/database.py`. This is the highest-value port and a prerequisite for the rest, since cquarry runs against the same locked-DB conditions Hermitage will hit.
- [ ] **Custom columns:** port `db.get_custom_columns()` and `db.load_custom_column()`. Surface user-defined Calibre custom columns in the Codex (read-only) and as searchable fields.
- [ ] **Identifiers:** port `db.get_identifiers()` so the Codex can render ISBN / Goodreads / etc. links from the `identifiers` table.
- [ ] **Library analytics & stats:** evaluate `cquarry/modes/{stats,analytics,audit}.py` for a "Library Insights" page (book counts by tag/author/series, missing-cover audit, format coverage).
- [ ] **Catalog / export:** evaluate `cquarry/modes/{catalog,export}.py` for an in-app export (OPDS-style catalog, JSON/CSV dump). Hermitage stays read-only against Calibre's DB; exports go to the user's chosen path.
- [ ] **Series view:** port `db.get_all_series()` (ordered series with index runs and titles) for a dedicated series browser sibling to the genre browser.
- [ ] **Search-expression parity:** cross-check our `hermitage/search.py` parser against cquarry's `_parse_or` / `_match_tags` / `_match_authors` semantics (especially `tags:Foo` matching `Foo.*` as a hierarchy prefix, which Hermitage does not currently do). Align behaviour so the same query returns the same set in both tools.
