"""Hermitage GTK 4 / Libadwaita application."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from hermitage.codex import CodexView
from hermitage.database import Book, build_search_index, load_library
from hermitage.colors import get_cached_colors, request_colors, warm_color_cache
from hermitage.thumbnailer import get_cached_texture, request_texture, warm_cache

APP_ID = "dev.hermitage.Hermitage"

# ---------------------------------------------------------------------------
# GObject wrapper — lets Book live inside Gio.ListStore
# ---------------------------------------------------------------------------


class BookObject(GObject.Object):
    """Thin GObject wrapper around a Book dataclass."""

    __gtype_name__ = "BookObject"

    def __init__(self, book: Book):
        super().__init__()
        self.book = book


# ---------------------------------------------------------------------------
# Cover factory for GridView
# ---------------------------------------------------------------------------

COVER_WIDTH = 180
COVER_HEIGHT = 270
COVER_RATIO = COVER_WIDTH / COVER_HEIGHT  # 0.667 (2:3)


def _apply_color_css(overlay: Gtk.Overlay, colors: list[tuple[int, int, int]]):
    """Apply per-cell hover glow using the book's dominant color."""
    # Remove previous provider if any
    old = getattr(overlay, "_color_provider", None)
    if old is not None:
        Gtk.StyleContext.remove_provider_for_display(
            overlay.get_display(), old
        )
        overlay._color_provider = None

    if not colors:
        return

    r, g, b = colors[0]
    provider = Gtk.CssProvider()
    provider.load_from_string(
        f".cover-cell-active:hover {{\n"
        f"    box-shadow: 0 6px 20px rgba({r},{g},{b}, 0.55);\n"
        f"}}\n"
        f".cover-cell-active:focus-within {{\n"
        f"    box-shadow: 0 0 0 3px rgba({r},{g},{b}, 0.6);\n"
        f"}}\n"
    )
    Gtk.StyleContext.add_provider_for_display(
        overlay.get_display(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
    )
    overlay._color_provider = provider
    if not overlay.has_css_class("cover-cell-active"):
        overlay.add_css_class("cover-cell-active")


def _setup_cover(factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
    """Create the widget tree for a single grid cell."""
    # Fixed-ratio frame prevents ragged rows
    frame = Gtk.AspectFrame(ratio=COVER_RATIO, obey_child=False)
    frame.set_halign(Gtk.Align.CENTER)
    frame.set_valign(Gtk.Align.START)
    frame.add_css_class("cover-frame")

    overlay = Gtk.Overlay()
    overlay.set_overflow(Gtk.Overflow.HIDDEN)
    overlay.add_css_class("cover-cell")

    picture = Gtk.Picture()
    picture.set_content_fit(Gtk.ContentFit.COVER)
    picture.add_css_class("cover-art")
    overlay.set_child(picture)

    # Title label — shown on hover via CSS
    label = Gtk.Label(xalign=0.5, wrap=True, wrap_mode=2, lines=2)  # WORD_CHAR
    label.set_ellipsize(3)  # END
    label.add_css_class("cover-title")
    label.set_valign(Gtk.Align.END)
    label.set_halign(Gtk.Align.FILL)
    overlay.add_overlay(label)

    frame.set_child(overlay)

    # Store refs so bind doesn't depend on child ordering
    frame._overlay = overlay
    frame._picture = picture
    frame._label = label

    list_item.set_child(frame)


def _bind_cover(factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
    """Populate a grid cell with data from a BookObject."""
    obj: BookObject = list_item.get_item()
    book = obj.book
    frame: Gtk.AspectFrame = list_item.get_child()
    overlay = frame._overlay
    picture = frame._picture
    label = frame._label

    label.set_text(book.title)

    cover = book.cover_path
    if not cover or not cover.is_file():
        picture.set_paintable(None)
        _apply_color_css(overlay, [])
        return

    # --- Texture ---
    texture = get_cached_texture(cover)
    if texture is not None:
        picture.set_paintable(texture)
    else:
        picture.set_paintable(None)
        book_id = book.id

        def _on_texture_ready(source_cover, tex):
            current = list_item.get_item()
            if current is None or current.book.id != book_id:
                return
            if tex:
                picture.set_paintable(tex)

        request_texture(cover, _on_texture_ready)

    # --- Dynamic color ---
    colors = get_cached_colors(book.id)
    if colors is not None:
        _apply_color_css(overlay, colors)
    else:
        _apply_color_css(overlay, [])
        book_id = book.id

        def _on_colors_ready(bid, cols):
            current = list_item.get_item()
            if current is None or current.book.id != bid:
                return
            _apply_color_css(overlay, cols)

        request_colors(book.id, cover, _on_colors_ready)


def _unbind_cover(factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
    """Release resources when a cell scrolls off-screen."""
    frame: Gtk.AspectFrame = list_item.get_child()
    frame._picture.set_paintable(None)
    # Clean up per-cell CSS provider
    overlay = frame._overlay
    old = getattr(overlay, "_color_provider", None)
    if old is not None:
        Gtk.StyleContext.remove_provider_for_display(
            overlay.get_display(), old
        )
        overlay._color_provider = None
    overlay.remove_css_class("cover-cell-active")


def _create_cover_factory() -> Gtk.SignalListItemFactory:
    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", _setup_cover)
    factory.connect("bind", _bind_cover)
    factory.connect("unbind", _unbind_cover)
    return factory


# ---------------------------------------------------------------------------
# Application CSS
# ---------------------------------------------------------------------------

_CSS = """
.cover-frame {
    margin: 4px;
}

.cover-cell {
    border-radius: 6px;
    background-color: @card_shade_color;
    transition: transform 150ms ease-in-out, box-shadow 200ms ease-in-out;
}

.cover-cell:hover {
    transform: scale(1.04);
    box-shadow: 0 4px 12px alpha(black, 0.3);
}

.cover-art {
    border-radius: 6px;
}

.cover-title {
    background: linear-gradient(to top,
        alpha(black, 0.72),
        alpha(black, 0.0));
    color: white;
    font-weight: bold;
    font-size: 11px;
    padding: 24px 6px 6px 6px;
    border-radius: 0 0 6px 6px;
    opacity: 0;
    transition: opacity 200ms ease-in-out;
}

.cover-cell:hover .cover-title,
.cover-cell:focus-within .cover-title {
    opacity: 1;
}

gridview > child {
    padding: 2px;
}

/* ---- Codex (Detail View) ---- */

.codex-hero {
    min-height: 280px;
    background-color: @card_shade_color;
}

.codex-hero-cover-frame {
    border-radius: 8px;
    box-shadow: 0 4px 16px alpha(black, 0.5);
}

.codex-title {
    font-size: 22px;
    font-weight: 800;
    color: white;
    text-shadow: 0 2px 4px alpha(black, 0.7);
}

.codex-author {
    font-size: 15px;
    font-weight: 500;
    color: alpha(white, 0.85);
    text-shadow: 0 1px 3px alpha(black, 0.5);
}

.codex-series {
    font-size: 13px;
    font-style: italic;
    color: alpha(white, 0.7);
    text-shadow: 0 1px 3px alpha(black, 0.5);
}

.codex-rating {
    font-size: 22px;
    color: @accent_color;
}

.codex-section-title {
    font-size: 11px;
    font-weight: 700;
    color: alpha(@window_fg_color, 0.55);
    letter-spacing: 1.5px;
}

.codex-tags flowboxchild {
    padding: 0;
}

.codex-tag-pill {
    background-color: alpha(@accent_bg_color, 0.15);
    color: @accent_color;
    border-radius: 99px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
}

.codex-synopsis {
    font-size: 14px;
}

.codex-meta {
    font-size: 12px;
    color: alpha(@window_fg_color, 0.5);
    font-weight: 500;
}

.codex-read-btn {
    font-size: 15px;
    padding: 8px 28px;
}
"""


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class HermitageApp(Adw.Application):
    """Main application object."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = self._build_window()
        win.present()

    # -- window construction ------------------------------------------------

    def _build_window(self) -> Adw.ApplicationWindow:
        win = Adw.ApplicationWindow(application=self)
        win.set_title("Hermitage")
        win.set_default_size(1200, 800)

        # Load CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Toolbar view (headerbar + content)
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Hermitage", subtitle=""))
        toolbar_view.add_top_bar(header)

        # Status page shown while loading
        status = Adw.StatusPage(
            title="Loading Library...",
            icon_name="library-symbolic",
        )
        toolbar_view.set_content(status)
        win.set_content(toolbar_view)

        # Codex detail view (sidebar)
        win._codex = CodexView()

        # Store refs for breakpoint and library load
        win._toolbar_view = toolbar_view
        win._header = header

        # Load library in background
        GLib.idle_add(self._load_library, win)

        return win

    def _load_library(self, win: Adw.ApplicationWindow) -> bool:
        toolbar_view = win._toolbar_view
        header = win._header

        try:
            books = load_library()
        except FileNotFoundError as exc:
            status = Adw.StatusPage(
                title="Library Not Found",
                description=str(exc),
                icon_name="dialog-error-symbolic",
            )
            toolbar_view.set_content(status)
            return GLib.SOURCE_REMOVE

        store = Gio.ListStore.new(BookObject)
        for b in books:
            store.append(BookObject(b))

        selection = Gtk.SingleSelection(model=store)
        grid = Gtk.GridView(model=selection, factory=_create_cover_factory())
        grid.set_min_columns(3)
        grid.set_max_columns(12)
        grid.add_css_class("sanctuary-grid")

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_child(grid)

        # OverlaySplitView: grid as content, codex as sidebar
        split = Adw.OverlaySplitView()
        split.set_content(scrolled)
        split.set_sidebar(win._codex)
        split.set_sidebar_position(Gtk.PackType.END)
        split.set_min_sidebar_width(360)
        split.set_max_sidebar_width(460)
        split.set_show_sidebar(False)
        win._split = split

        toolbar_view.set_content(split)

        # Connect grid activation (click / Enter) to open the Codex
        grid.connect("activate", self._on_book_activated, win)

        # Store books list for later reference
        win._books = books

        subtitle = f"{len(books)} books"
        header.set_title_widget(Adw.WindowTitle(title="Hermitage", subtitle=subtitle))

        # --- Breakpoints ---
        self._setup_breakpoints(win, grid)

        # Build FTS5 search index
        build_search_index(books)

        # Pre-generate thumbnails and extract colors in background threads
        covers = [b.cover_path for b in books if b.cover_path and b.cover_path.is_file()]
        warm_cache(covers)
        warm_color_cache(books)

        return GLib.SOURCE_REMOVE

    def _on_book_activated(
        self,
        grid: Gtk.GridView,
        position: int,
        win: Adw.ApplicationWindow,
    ):
        """Handle grid item activation — populate and show the Codex."""
        obj: BookObject = grid.get_model().get_item(position)
        if obj is None:
            return
        win._codex.show_book(obj.book)
        win._split.set_show_sidebar(True)

    def _setup_breakpoints(self, win: Adw.ApplicationWindow, grid: Gtk.GridView):
        """Configure responsive column scaling via Adw.Breakpoint."""
        def _uint(v: int) -> GObject.Value:
            val = GObject.Value(GObject.TYPE_UINT)
            val.set_uint(v)
            return val

        # Narrow: phones / tight tiling (< 500px)
        bp_narrow = Adw.Breakpoint(
            condition=Adw.BreakpointCondition.parse("max-width: 500sp"),
        )
        bp_narrow.add_setter(grid, "min-columns", _uint(2))
        bp_narrow.add_setter(grid, "max-columns", _uint(3))
        win.add_breakpoint(bp_narrow)

        # Medium: tablets / half-screen (< 900px)
        bp_medium = Adw.Breakpoint(
            condition=Adw.BreakpointCondition.parse("max-width: 900sp"),
        )
        bp_medium.add_setter(grid, "min-columns", _uint(3))
        bp_medium.add_setter(grid, "max-columns", _uint(5))
        win.add_breakpoint(bp_medium)


def run():
    app = HermitageApp()
    app.run()
