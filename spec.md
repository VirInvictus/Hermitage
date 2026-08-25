# Specification: Hermitage
**Project Goal:** A flagship, visually immersive, single-user media sanctuary for Calibre libraries, leveraging the Python 3.14 / GTK 4 "Tokyo" stack to rival modern web-based media servers.

## 1. Core Mandates
- **Platform:** Pure Wayland, Hyprland-native (works under a GNOME fallback session too). Optimized for high-DPI, fractional-scale, and VRR displays.
- **Language:** Python 3.14. Utilization of deferred annotations and optimized asyncio.
- **Privacy:** 100% Local-First. Zero telemetry, zero external network calls, zero user accounts.
- **Performance & Scale:** Engineered to effortlessly scroll a 5,000+ item library with < 150ms initial load time, entirely bypassing network latency.
- **Aesthetic Precision:** The UI must feel curated, not utilitarian. Focus on cover art dominance, dynamic color palettes, and cinematic detail views.

## 2. Technical Stack
- **Frameworks:** GTK 4 only (PyGObject). **No libadwaita.** The GNOME identity layer (the adwaita stylesheet, the adaptive widgets, `Adw.StyleManager`) is dropped in favour of plain GTK 4 widgets and a stylesheet Hermitage owns outright. A small `hermitage/widgets.py` supplies the owned successors to the adwaita widgets that earned their keep: a width-clamping `Clamp`, a `WindowTitle`, a `ToastOverlay`, and a `status_page` composite.
- **Graphics Engine:** GTK 4.22+ utilizing `Gtk.Snapshot` for custom blur effects and the `GtkSvg` native renderer for iconography.
- **Database:** Shared `cquarry` (≥1.1) backend engine for canonical Calibre metadata.db read access and search evaluation. `hermitage/database.py` is a thin wrapper layer: `load_library()` consumes cquarry's list-typed `authors`/`tags`/`formats` arrays directly (never comma-split them), and the wrappers `load_saved_searches()`, `load_vl_ui_state()`, `get_annotations(book_id)` and `get_reading_progress(book_id)` expose saved searches, Calibre's sidebar layout state, e-reader highlights, and per-device progress fractions.
- **Concurrency:** Python 3.14 sub-interpreters or TaskGroups for non-blocking cover fetching and color extraction.

## 2a. Design Language (Hyprland-native)

Hermitage dropped libadwaita to *fully belong on Hyprland* rather than merely tolerate it. GTK 4 is Wayland-native and stays; the GNOME look does not. The following are the load-bearing decisions.

- **Decoration posture:** window buttons are hidden (`show-title-buttons` off); the compositor draws no titlebar of its own. **Ctrl+Q** quits; otherwise the compositor's own binds close the window. Under a GNOME fallback session the window still works (Super+drag, the overview close).
- **Sidebars float, they do not push.** Both the Codex (right) and the virtual-library list (left) are `Gtk.Revealer` panels stacked over the grid in a `Gtk.Overlay`, preserving the slide-over, immersive feel. They overlay the covers rather than squeezing the grid, so a half or quarter Hyprland tile never shrinks the grid to a sliver. No auto-collapse; the app never reshuffles its own layout on resize. Toggled by the header buttons / Ctrl+L / activation, dismissed by the Escape cascade. The Libraries panel mirrors Calibre's own sidebar: entries follow `virt_libs_order`, hidden libraries are suppressed, and a second section lists saved searches (`search:"Name"`).
- **Grid density** is left to `Gtk.GridView`'s own column fitting between `min-columns=1` and `max-columns=12` (no `Adw.Breakpoint`). A narrow quarter-tile reaches a clean single strip of covers; a wide window fills out.
- **Palette:** Kanagawa Dragon (dark) and a Kanagawa-derived light, owned by the stylesheet rather than inherited from Adwaita. **Follow-system** dark/light is preserved by reading `org.freedesktop.portal.Settings` directly over D-Bus (`hermitage/theme.py`, the single theme-resolution path), no new dependency, degrading to the dark default when no portal answers.
- **Visual identity is preserved, not squared off.** "Owned stylesheet" flattens the GNOME-isms (the adwaita `.card`/`.boxed-list`/`.pill`/`.title-*` classes get owned definitions), but Hermitage keeps its rounded, immersive vocabulary: rounded cover cells, pill-shaped tags, the blurred hero. The spec's "curated, not utilitarian" mandate (§1) governs over any generic flat-and-square styling.
- **Preferences** live in a plain `Gtk.Window` (a `.boxed-list` of owned rows), not `Adw.PreferencesWindow`. The first-run wizard, Insights, and the About dialog are likewise plain `Gtk.Window` / `Gtk.AboutDialog`.

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

