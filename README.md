<p align="center">
  <b><code>Hermitage</code></b>
</p>
<p align="center">
  A visually immersive, local-first media sanctuary for Calibre libraries.
</p>
<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.14%2B-blue" alt="Python 3.14+"></a>
  <a href="https://gitlab.gnome.org/GNOME/gtk/-/tags/4.22.0"><img src="https://img.shields.io/badge/GTK-4.22%2B-4a86cf" alt="GTK 4.22+"></a>
  <a href="https://gitlab.gnome.org/GNOME/libadwaita/-/tags/1.7.0"><img src="https://img.shields.io/badge/Libadwaita-1.7%2B-57a5e5" alt="Libadwaita 1.7+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-yellow.svg" alt="License: GPL-3.0"></a>
  <a href="https://ko-fi.com/vrnvctss"><img src="https://img.shields.io/badge/support-Ko--fi-ff5f5f?logo=kofi" alt="Ko-fi"></a>
</p>

---

Native GTK 4 / Libadwaita application built for GNOME 50+. Designed to make browsing a 4,000+ book library feel like walking through a curated gallery rather than scrolling a spreadsheet.

Calibre is the gold standard for ebook management, but its UI is built for librarians, not readers. Projects like Calibre-Web and Calibre-Web-Automated add a browser-based frontend, but they're built for multi-user households and server deployments -- Docker containers, authentication layers, network overhead, and configuration complexity for what should be opening a folder on your own machine. Hermitage is built for the loner. One user, one library, one desktop. It reads your existing Calibre `metadata.db` directly (read-only, `mode=ro`) and presents it as a native application -- zero network calls, zero Docker, zero accounts, zero multi-user anything. Just your books.

## Features

| Feature | Description |
|---------|-------------|
| **The Sanctuary** | Edge-to-edge cover art grid with strict 2:3 aspect ratios, hover scale transforms, and fade-in titles. Covers are the only focus -- titles stay hidden until hover/focus. |
| **The Codex** | Sliding detail sidebar with a blurred hero banner, mini cover thumbnail, clickable author/series/tag metadata, styled synopsis, star ratings, publication date, format list, and a one-click "Read" button. |
| **Genre browser** | Full-page category view built from your Calibre tags. Renders the entire dot-separated tag hierarchy as nested cards with clickable pills and book counts. Click any genre to filter the grid. |
| **Dynamic color tinting** | Dominant color extracted from each cover via median-cut quantization (5 colors, sorted by vibrancy). Mapped to per-cell hover glows and keyboard focus rings. |
| **Calibre search** | Full Calibre query syntax -- field prefixes, quoted values, exact match (`=`), boolean `and`/`or`/`not`, parentheses, and `vl:` virtual library references. 400ms debounce for smooth typing. |
| **Virtual libraries** | Left sidebar listing all Calibre virtual libraries from the `preferences` table. Click any library to filter the grid instantly. |
| **Sort options** | Sort by title, author, date added, publication date, rating, or series. Ascending/descending toggle. Series searches auto-sort by reading order. |
| **Responsive layout** | `Adw.Breakpoint` rules scale the grid: 2-3 columns on narrow windows, 3-5 on medium, 3-12 on wide desktop. |
| **Thumbnail pipeline** | Pillow-based 360x540 thumbnail cache with BLAKE2b invalidation keys, 4-thread generation pool, and a 512-entry in-memory `Gdk.Texture` LRU. |
| **Native file launch** | "Read" button opens books via `Gtk.FileLauncher` in your system's default reader (Foliate, Papers, Evince). Format priority: EPUB > PDF > MOBI > AZW3 > CBZ > CBR > DJVU > TXT. |
| **Configuration** | YAML config at `~/.config/hermitage/config.yaml`. First-run wizard for library setup. In-app preferences page. Env var override for scripting. |
| **Keyboard shortcuts** | Ctrl+F (search), Ctrl+L (libraries), Escape (dismiss codex / search / sidebar). |
| **100% local** | Zero telemetry, zero network calls, zero user accounts, zero Docker. Your library stays on your disk. |

## Tag structure

Hermitage uses Calibre's tag system as a genre hierarchy. Tags with dot-separated names are parsed into a navigable tree in the genre browser. The deeper your tag structure, the richer the browsing experience:

```
Fic.Fantasy.Epic          -> Fic > Fantasy > Epic
Fic.Fantasy.Grimdark      -> Fic > Fantasy > Grimdark
Gaming.TTRPG.OSR          -> Gaming > TTRPG > OSR
Gaming.TTRPG.OSR.Megadungeon -> Gaming > TTRPG > OSR > Megadungeon
NonFic.History.Military    -> NonFic > History > Military
```

Top-level categories appear as cards. Mid-level branches appear as labeled subsections. Leaf genres appear as clickable accent-colored pills with book counts. Every level is clickable and filters the grid. If your Calibre tags are flat (no dots), the genre browser still works -- each tag gets its own pill under a single section.

## Screenshot

<p align="center">
  <img src="https://github.com/user-attachments/assets/abad1033-2ba3-4ce2-92d8-a283b8e9d5ed" alt="DeaDBeeF CUI Plugin Screenshot" style="max-width: 100%; border-radius: 8px;">
</p>

## Requirements

**Python 3.14+** with:

```
pip install PyGObject Pillow PyYAML
```

**System libraries:**

- GTK 4.22+
- Libadwaita 1.7+
- GObject Introspection

```bash
# Fedora 43+
sudo dnf install gtk4 libadwaita python3-gobject

# Arch
sudo pacman -S gtk4 libadwaita python-gobject
```

## Usage

```bash
# Run directly
python -m hermitage

# Or install and run via console script
pip install -e .
hermitage
```

On first run, Hermitage will prompt you to select your Calibre library directory. Settings are stored in `~/.config/hermitage/config.yaml` and can be edited in any text editor or through the in-app preferences page.

To override the library path via environment variable:

```bash
export HERMITAGE_DB="/path/to/your/Calibre Library/metadata.db"
```

## Search syntax

The search bar (Ctrl+F) supports Calibre's full query language:

```bash
# Field-specific search
tags:Fantasy
title:"The Lord of the Rings"
authors:Tolkien
series:Discworld
formats:EPUB
rating:5

# Exact match (= prefix inside quotes)
tags:"=Fic.Fantasy"

# Boolean operators
tags:Fantasy and not tags:Romance
(tags:SciFi or tags:Fantasy) and rating:5

# Virtual library references
vl:"Fantasy Wing"
```

Bare text searches across title, authors, tags, and series. Multiple words are implicitly ANDed.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+F   | Toggle search bar |
| Ctrl+L   | Toggle virtual library sidebar |
| Escape   | Dismiss codex, then search, then VL sidebar (priority order) |

## Library verification

```bash
hermitage-verify
```

Standalone CLI tool that validates every book's directory path, cover file integrity, and format file presence. Reports issues grouped by category and benchmarks path resolution time.

## Architecture

```
hermitage/
  __init__.py       # Version (0.8.0)
  __main__.py       # Entry point + SIGINT handler
  app.py            # Adw.Application, GridView, dual OverlaySplitViews, sorting, search
  codex.py          # Detail sidebar: hero blur, clickable metadata, synopsis, Read button
  config.py         # YAML config load/save (~/.config/hermitage/config.yaml)
  genres.py         # Genre browser: recursive tag hierarchy with cards and pills
  preferences.py    # Adw.PreferencesWindow for in-app settings
  search.py         # Recursive descent parser for Calibre search query language
  wizard.py         # First-run setup wizard with Calibre folder picker
  database.py       # Read-only Calibre metadata.db parser, virtual library loader
  thumbnailer.py    # Thumbnail disk cache + 512-entry in-memory texture LRU
  colors.py         # Median-cut color quantization, vibrancy sorting, three-tier cache
  verify.py         # CLI library integrity checker
  style.css         # Application stylesheet (grid, codex, genre browser)
```

## Stack

- **Python 3.14** -- deferred annotations (`from __future__ import annotations`), `dataclass(slots=True)`
- **GTK 4.22** / **Libadwaita 1.7** -- `Adw.ToolbarView`, `Adw.OverlaySplitView`, `Adw.Breakpoint`, `Adw.Clamp`, `Adw.PreferencesWindow`
- **SQLite3** in `mode=ro` -- immutable read-only access to Calibre's database
- **Pillow** -- thumbnailing (LANCZOS), hero blur (GaussianBlur r30), color quantization (median-cut)
- **PyYAML** -- config file at `~/.config/hermitage/config.yaml`
- **Thread pools** -- 4 threads for thumbnails/colors, 2 threads for hero blur generation
- **Cached assets** in `~/.cache/hermitage/` -- `thumbs/`, `colors/`, `blur/`

## Support

If this saved you time, consider [buying me a coffee](https://ko-fi.com/vrnvctss).
