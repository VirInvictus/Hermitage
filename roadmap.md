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
- [ ] **Gestures & Navigation:** Enable Wayland-native pinch-to-zoom for the grid, and swipe-to-dismiss for the detail pane.
- [ ] **Flatpak:** Prepare the manifest for the GNOME 50 runtime, ensuring sandbox permissions allow read access to the external Calibre directory.
