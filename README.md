<p align="center">
  <b><code>Hermitage</code></b>
</p>
<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.14%2B-blue" alt="Python 3.14+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-yellow.svg" alt="License: GPL-3.0"></a>
  <a href="https://ko-fi.com/vrnvctss"><img src="https://img.shields.io/badge/support-Ko--fi-ff5f5f?logo=kofi" alt="Ko-fi"></a>
</p>

A visually immersive, local-first media sanctuary for Calibre libraries. Native GTK 4 / Libadwaita application built for GNOME 50+, designed to make browsing a 4,000+ book library feel like walking through a curated gallery rather than scrolling a spreadsheet.

## Why this exists

Calibre is the gold standard for ebook management, but its UI is built for librarians, not readers. Calibre-Web adds a browser-based frontend but introduces network latency, authentication overhead, and Docker complexity for what should be a local operation. Hermitage reads your existing Calibre `metadata.db` directly (read-only) and presents it as a native desktop application — zero network calls, zero accounts, zero configuration beyond pointing it at your library.

## Features

| Feature | Description |
|---------|-------------|
| **The Sanctuary** | Edge-to-edge cover art grid with strict 2:3 aspect ratios, hover scale transforms, and fade-in titles |
| **The Codex** | Sliding detail sidebar with blurred hero banner, tag pills, styled synopsis, star ratings, and a one-click "Read" button |
| **Dynamic color tinting** | Dominant color extracted from each cover via median-cut quantization, mapped to per-cell hover glows and focus rings |
| **FTS5 search** | In-memory full-text index across titles, authors, tags, and series with prefix matching and BM25 ranking |
| **Responsive breakpoints** | `Adw.Breakpoint` rules scale the grid from 2-3 columns (phones) to 3-12 columns (desktop) |
| **Thumbnail pipeline** | Pillow-based 360x540 thumbnail cache with BLAKE2b keys, 4-thread pool, and 512-entry in-memory LRU |
| **Native file launch** | "Read" button opens books in your system's default reader (Foliate, Papers, Evince) via `Gtk.FileLauncher` |
| **100% local** | Zero telemetry, zero network calls, zero user accounts. Your library stays on your disk. |

## Requirements

**Python 3.14+** with the following packages:

```
pip install PyGObject Pillow PyYAML
```

**System libraries:**

- GTK 4.22+
- Libadwaita 1.7+
- GObject Introspection

On Fedora 43+: `sudo dnf install gtk4 libadwaita python3-gobject`
On Arch: `sudo pacman -S gtk4 libadwaita python-gobject`

## Usage

```bash
# Run directly
python -m hermitage

# Or install and run via console script
pip install -e .
hermitage
```

By default, Hermitage looks for `metadata.db` at `~/docs/Calibre Library/metadata.db`. To point it elsewhere:

```bash
export HERMITAGE_DB="/path/to/your/Calibre Library/metadata.db"
hermitage
```

### Library verification

```bash
hermitage-verify
```

Validates every book's directory path, cover file integrity, and format file presence. Reports issues and benchmarks path resolution time.

## Architecture

```
hermitage/
  __init__.py       # Version
  __main__.py       # Entry point
  app.py            # Adw.Application, GridView, OverlaySplitView, CSS
  codex.py          # Detail view: hero banner, tag pills, synopsis, Read button
  database.py       # Read-only Calibre metadata.db parser, FTS5 search index
  thumbnailer.py    # Thumbnail disk cache + in-memory texture LRU
  colors.py         # Dominant color extraction via median-cut quantization
  verify.py         # CLI library integrity checker
```

## Stack

- **Python 3.14** with deferred annotations and optimized asyncio
- **GTK 4.22** / **Libadwaita 1.7** — `AdwToolbarView`, `AdwOverlaySplitView`, `AdwBreakpoint`, `AdwClamp`
- **SQLite3** in `mode=ro` with FTS5 for full-text search
- **Pillow** for thumbnailing, blur generation, and color quantization
- Cached assets in `~/.cache/hermitage/` (thumbs, colors, blur)

## Support

If this saved you time, consider [buying me a coffee](https://ko-fi.com/vrnvctss).
