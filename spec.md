# Specification: Hermitage
**Project Goal:** A flagship, visually immersive, single-user media sanctuary for Calibre libraries, leveraging the Python 3.14 / GNOME 50 "Tokyo" stack to rival modern web-based media servers.

## 1. Core Mandates
- **Platform:** Pure Wayland (GNOME 50+). Optimized for high-DPI and VRR displays.
- **Language:** Python 3.14. Utilization of deferred annotations and optimized asyncio.
- **Privacy:** 100% Local-First. Zero telemetry, zero external network calls, zero user accounts.
- **Performance & Scale:** Engineered to effortlessly scroll a 5,000+ item library with < 150ms initial load time, entirely bypassing network latency.
- **Aesthetic Precision:** The UI must feel curated, not utilitarian. Focus on cover art dominance, dynamic color palettes, and cinematic detail views.

## 2. Technical Stack
- **Frameworks:** Libadwaita 1.7+ (using `AdwToolbarView`, `AdwOverlaySplitView`, and `AdwClamp` for text reading width).
- **Graphics Engine:** GTK 4.22+ utilizing `Gtk.Snapshot` for custom blur effects and the `GtkSvg` native renderer for iconography.
- **Database:** SQLite3 using `mode=ro` (Immutable) and FTS5 for instant full-text search.
- **Concurrency:** Python 3.14 sub-interpreters or TaskGroups for non-blocking cover fetching and color extraction.

## 3. UI/UX "Gallery" Logic
- **The Sanctuary (Grid View):** An edge-to-edge `GtkGridView` with `GtkPicture` widgets. Covers are the only focus. Titles are hidden until hover/focus to maintain visual purity.
- **The Codex (Detail View):** A sliding detail pane featuring a "hero" layout:
    - **Header:** A dynamically blurred representation of the cover art spanning the top.
    - **Actions:** A clear, primary "Read" action.
    - **Metadata:** Series and tags are parsed into visually distinct badges.
    - **Typography:** High-density, meticulously spaced Pango text for the synopsis.
- **Configuration:** No settings menu. Configuration (path to `metadata.db`) is handled via a single local YAML or environment variable. The app is highly opinionated by design.

Important folders for testing:
"/home/bdkl/docs/Calibre\ Library" - Where the metadata.db lives (as well as the library itself). DO NOT EDIT ANYTHING IN THIS FILE. YOU CAN USE THE METADATA.DB TO USE BUT MUST ONLY READ-ONLY ACCESS.
"/tmp/Calibre-Web-Automated" - The source code for Calibre-Web-Automated

