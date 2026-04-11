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

Calibre is the gold standard for ebook management, but its UI is built for librarians, not readers. Calibre-Web adds a browser-based frontend but introduces network latency, authentication overhead, and Docker complexity for what should be a local operation. Hermitage reads your existing Calibre `metadata.db` directly (read-only, `mode=ro`) and presents it as a native desktop application -- zero network calls, zero accounts, zero configuration beyond pointing it at your library.

## Features

| Feature | Description |
|---------|-------------|
| **The Sanctuary** | Edge-to-edge cover art grid with strict 2:3 aspect ratios, hover scale transforms, and fade-in titles. Covers are the only focus -- titles stay hidden until hover/focus. |
| **The Codex** | Sliding detail sidebar with a blurred hero banner, mini cover thumbnail, tag pills, styled synopsis via `Adw.Clamp`, star ratings, publication date, format list, and a one-click "Read" button. |
| **Dynamic color tinting** | Dominant color extracted from each cover via median-cut quantization (5 colors, sorted by vibrancy). Mapped to per-cell hover glows and keyboard focus rings. |
| **Calibre search** | Full Calibre query syntax -- field prefixes, quoted values, exact match (`=`), boolean `and`/`or`/`not`, parentheses, and `vl:` virtual library references. Recursive descent parser with implicit AND for bare text. |
| **Virtual libraries** | Left sidebar listing all Calibre virtual libraries from the `preferences` table. Click any library to filter the grid instantly. |
| **Responsive layout** | `Adw.Breakpoint` rules scale the grid: 2-3 columns on narrow windows, 3-5 on medium, 3-12 on wide desktop. |
| **Thumbnail pipeline** | Pillow-based 360x540 thumbnail cache with BLAKE2b invalidation keys, 4-thread generation pool, and a 512-entry in-memory `Gdk.Texture` LRU. |
| **Native file launch** | "Read" button opens books via `Gtk.FileLauncher` in your system's default reader (Foliate, Papers, Evince). Format priority: EPUB > PDF > MOBI > AZW3 > CBZ > CBR > DJVU > TXT. |
| **Keyboard shortcuts** | Ctrl+F (search), Ctrl+L (libraries), Escape (dismiss codex / search / sidebar). |
| **100% local** | Zero telemetry, zero network calls, zero user accounts. Your library stays on your disk. |

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

On first run, Hermitage will prompt you to select your Calibre library directory. To override via environment variable:

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
  __init__.py       # Version (0.7.1)
  __main__.py       # Entry point
  app.py            # Adw.Application, GridView, dual OverlaySplitViews, search wiring
  codex.py          # Detail sidebar: hero blur, tag pills, synopsis, Read button
  search.py         # Recursive descent parser for Calibre search query language
  database.py       # Read-only Calibre metadata.db parser, virtual library loader
  thumbnailer.py    # Thumbnail disk cache + 512-entry in-memory texture LRU
  colors.py         # Median-cut color quantization, vibrancy sorting, three-tier cache
  verify.py         # CLI library integrity checker
  style.css         # Application stylesheet (grid + codex rules)
```

## Stack

- **Python 3.14** -- deferred annotations (`from __future__ import annotations`), `dataclass(slots=True)`
- **GTK 4.22** / **Libadwaita 1.7** -- `Adw.ToolbarView`, `Adw.OverlaySplitView`, `Adw.Breakpoint`, `Adw.Clamp`
- **SQLite3** in `mode=ro` -- immutable read-only access to Calibre's database
- **Pillow** -- thumbnailing (LANCZOS), hero blur (GaussianBlur r30), color quantization (median-cut)
- **Thread pools** -- 4 threads for thumbnails/colors, 2 threads for hero blur generation
- **Cached assets** in `~/.cache/hermitage/` -- `thumbs/`, `colors/`, `blur/`

## Support

If this saved you time, consider [buying me a coffee](https://ko-fi.com/vrnvctss).
