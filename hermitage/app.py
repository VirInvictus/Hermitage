"""Hermitage GTK 4 / Libadwaita application."""

from __future__ import annotations

import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from hermitage.codex import CodexView
from hermitage.config import config_exists, get as cfg_get, set_value as cfg_set
from hermitage.database import Book, load_library, load_virtual_libraries
from hermitage.colors import get_cached_colors, request_colors, warm_color_cache
from hermitage.genres import GenreBrowser
from hermitage.search import filter_books, parse_query
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
    frame.set_halign(Gtk.Align.FILL)
    frame.set_valign(Gtk.Align.START)
    frame.add_css_class("cover-frame")

    overlay = Gtk.Overlay()
    overlay.set_overflow(Gtk.Overflow.HIDDEN)
    overlay.add_css_class("cover-cell")

    picture = Gtk.Picture()
    picture.set_content_fit(Gtk.ContentFit.COVER)
    picture.set_size_request(COVER_WIDTH, COVER_HEIGHT)
    picture.add_css_class("cover-art")
    overlay.set_child(picture)

    # Title label — shown on hover via CSS
    label = Gtk.Label(
        xalign=0.5, wrap=True,
        wrap_mode=Pango.WrapMode.WORD_CHAR, lines=2,
    )
    label.set_ellipsize(Pango.EllipsizeMode.END)
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

_CSS_PATH = Path(__file__).parent / "style.css"


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def _sort_key(book: Book, field: str):
    """Return a comparable sort key for the given field."""
    if field == "title":
        return book.sort.lower()
    elif field == "author":
        return (book.authors[0].lower() if book.authors else "")
    elif field == "date_added":
        return book.timestamp or ""
    elif field == "pubdate":
        return book.pubdate or ""
    elif field == "rating":
        return book.rating or 0
    elif field == "series":
        return (book.series or "", book.series_index)
    return book.sort.lower()


def _sort_books(books: list[BookObject], field: str, ascending: bool):
    """Sort a list of BookObjects in place."""
    books.sort(
        key=lambda obj: _sort_key(obj.book, field),
        reverse=not ascending,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class HermitageApp(Adw.Application):
    """Main application object."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

        prefs_action = Gio.SimpleAction(name="preferences")
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)

        # Sort field action (stateful string)
        from hermitage.config import get as cfg_get
        sort_field_action = Gio.SimpleAction.new_stateful(
            "sort-field",
            GLib.VariantType.new("s"),
            GLib.Variant("s", cfg_get("sort_field", "title")),
        )
        sort_field_action.connect("activate", self._on_sort_field_action)
        self.add_action(sort_field_action)

        # Sort ascending action (stateful toggle)
        sort_asc_action = Gio.SimpleAction.new_stateful(
            "sort-ascending",
            None,
            GLib.Variant("b", cfg_get("sort_ascending", True)),
        )
        sort_asc_action.connect("activate", self._on_sort_ascending_action)
        self.add_action(sort_asc_action)

    def _on_sort_field_action(self, action, param):
        field = param.get_string()
        action.set_state(param)
        from hermitage.config import set_value
        set_value("sort_field", field)
        win = self.props.active_window
        if win and hasattr(win, "_store"):
            self._resort_grid(win)

    def _on_sort_ascending_action(self, action, param):
        current = action.get_state().get_boolean()
        new_val = not current
        action.set_state(GLib.Variant("b", new_val))
        from hermitage.config import set_value
        set_value("sort_ascending", new_val)
        win = self.props.active_window
        if win and hasattr(win, "_store"):
            self._resort_grid(win)
            # Update sort icon direction
            icon = "view-sort-ascending-symbolic" if new_val else "view-sort-descending-symbolic"
            win._sort_btn.set_icon_name(icon)

    def _on_preferences(self, action, param):
        win = self.props.active_window
        if not win:
            return

        from hermitage.preferences import PreferencesWindow

        def _on_settings_changed():
            if hasattr(win, "_books"):
                self._resort_grid(win)

        prefs = PreferencesWindow(win, on_settings_changed=_on_settings_changed)
        prefs.present()

    def do_activate(self):
        win = self.props.active_window
        if win:
            win.present()
            return

        import os
        if not config_exists() and not os.environ.get("HERMITAGE_DB"):
            from hermitage.wizard import SetupWizard
            wizard = SetupWizard(self)
            wizard.present()
            return

        win = self._build_window()
        win.present()

    # -- window construction ------------------------------------------------

    def _build_window(self) -> Adw.ApplicationWindow:
        win = Adw.ApplicationWindow(application=self)
        win.set_title("Hermitage")
        win.set_default_size(1200, 800)

        self._load_css()
        self._build_chrome(win)
        self._setup_shortcuts(win)

        # Codex detail view (created before library loads)
        win._codex = CodexView()

        # Loading state
        status = Adw.StatusPage(
            title="Loading Library...",
            icon_name="library-symbolic",
        )
        win._toolbar_view.set_content(status)

        GLib.idle_add(self._load_library, win)
        return win

    @staticmethod
    def _load_css():
        """Load the application stylesheet."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_file(Gio.File.new_for_path(str(_CSS_PATH)))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    @staticmethod
    def _build_chrome(win: Adw.ApplicationWindow):
        """Build the header bar, search bar, and toolbar view shell."""
        toolbar_view = Adw.ToolbarView()

        # Header bar
        header = Adw.HeaderBar()
        win._title_widget = Adw.WindowTitle(title="Hermitage", subtitle="")
        header.set_title_widget(win._title_widget)

        win._vl_btn = Gtk.ToggleButton(icon_name="view-list-symbolic")
        win._vl_btn.set_tooltip_text("Virtual libraries (Ctrl+L)")
        header.pack_start(win._vl_btn)

        win._search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic")
        win._search_btn.set_tooltip_text("Search library (Ctrl+F)")
        header.pack_start(win._search_btn)

        win._genre_btn = Gtk.ToggleButton(icon_name="user-bookmarks-symbolic")
        win._genre_btn.set_tooltip_text("Browse genres")
        header.pack_start(win._genre_btn)

        toolbar_view.add_top_bar(header)

        # Search bar (slides below header)
        search_bar = Gtk.SearchBar()
        search_bar.set_show_close_button(True)

        win._search_entry = Gtk.SearchEntry()
        win._search_entry.set_placeholder_text(
            "Search\u2026  title: authors: tags: series: formats: rating:",
        )
        win._search_entry.set_hexpand(True)
        win._search_entry.set_size_request(300, -1)

        entry_clamp = Adw.Clamp(maximum_size=600)
        entry_clamp.set_child(win._search_entry)
        search_bar.set_child(entry_clamp)
        search_bar.connect_entry(win._search_entry)

        win._search_btn.bind_property(
            "active", search_bar, "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        toolbar_view.add_top_bar(search_bar)

        # Sort menu button (right side)
        sort_menu = Gio.Menu()
        sort_section = Gio.Menu()
        for key, label in [
            ("title", "Title"),
            ("author", "Author"),
            ("date_added", "Date Added"),
            ("pubdate", "Publication Date"),
            ("rating", "Rating"),
            ("series", "Series"),
        ]:
            sort_section.append(label, f"app.sort-field::{key}")
        sort_menu.append_section("Sort By", sort_section)

        dir_section = Gio.Menu()
        dir_section.append("Ascending", "app.sort-ascending")
        sort_menu.append_section(None, dir_section)

        sort_btn = Gtk.MenuButton(icon_name="view-sort-descending-symbolic")
        sort_btn.set_tooltip_text("Sort order")
        sort_btn.set_menu_model(sort_menu)
        header.pack_end(sort_btn)
        win._sort_btn = sort_btn

        # Menu button (right side)
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_tooltip_text("Main menu")
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        win._toolbar_view = toolbar_view
        win.set_content(toolbar_view)

    def _setup_shortcuts(self, win: Adw.ApplicationWindow):
        """Register keyboard shortcuts."""
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)

        # Ctrl+F — toggle search
        ctrl.add_shortcut(Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>f"),
            action=Gtk.CallbackAction.new(
                lambda *_: win._search_btn.set_active(
                    not win._search_btn.get_active(),
                ) or True,
            ),
        ))

        # Ctrl+L — toggle virtual library sidebar
        ctrl.add_shortcut(Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>l"),
            action=Gtk.CallbackAction.new(
                lambda *_: win._vl_btn.set_active(
                    not win._vl_btn.get_active(),
                ) or True,
            ),
        ))

        # Escape — close codex, then search, then VL sidebar
        def _on_escape(*_args):
            if hasattr(win, "_split") and win._split.get_show_sidebar():
                win._split.set_show_sidebar(False)
                return True
            if win._search_btn.get_active():
                win._search_btn.set_active(False)
                return True
            if win._vl_btn.get_active():
                win._vl_btn.set_active(False)
                return True
            return True

        ctrl.add_shortcut(Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
            action=Gtk.CallbackAction.new(_on_escape),
        ))

        win.add_controller(ctrl)

    # -- library loading ----------------------------------------------------

    def _load_library(self, win: Adw.ApplicationWindow) -> bool:
        """Load the Calibre database and build the full UI."""
        try:
            books = load_library()
        except FileNotFoundError as exc:
            win._toolbar_view.set_content(Adw.StatusPage(
                title="Library Not Found",
                description=str(exc),
                icon_name="dialog-error-symbolic",
            ))
            return GLib.SOURCE_REMOVE

        win._books = books

        grid = self._build_grid(win, books)
        self._build_layout(win, grid)
        self._wire_search(win)

        win._title_widget.set_subtitle(f"{len(books)} books")
        self._setup_breakpoints(win, grid)

        # Pre-generate thumbnails and extract colors in background threads
        covers = [b.cover_path for b in books if b.cover_path and b.cover_path.is_file()]
        warm_cache(covers)
        warm_color_cache(books)

        return GLib.SOURCE_REMOVE

    def _build_grid(
        self, win: Adw.ApplicationWindow, books: list[Book],
    ) -> Gtk.GridView:
        """Create the grid view with a filtered list model."""
        from hermitage.config import get as cfg_get

        # Build sorted list of BookObjects
        book_objects = [BookObject(b) for b in books]
        sort_field = cfg_get("sort_field", "title")
        sort_asc = cfg_get("sort_ascending", True)
        _sort_books(book_objects, sort_field, sort_asc)

        store = Gio.ListStore.new(BookObject)
        for obj in book_objects:
            store.append(obj)
        win._store = store

        win._filter = Gtk.CustomFilter()
        win._filtered_model = Gtk.FilterListModel(model=store, filter=win._filter)
        selection = Gtk.SingleSelection(model=win._filtered_model)

        grid = Gtk.GridView(model=selection, factory=_create_cover_factory())
        grid.set_min_columns(3)
        grid.set_max_columns(12)
        grid.add_css_class("sanctuary-grid")
        grid.connect("activate", self._on_book_activated, win)

        return grid

    def _build_layout(self, win: Adw.ApplicationWindow, grid: Gtk.GridView):
        """Assemble the nested split-view layout."""
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_child(grid)

        # Genre browser (stacked behind the grid)
        win._genre_browser = GenreBrowser()
        win._genre_browser.populate(win._books)

        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        stack.set_transition_duration(200)
        stack.add_named(scrolled, "grid")
        stack.add_named(win._genre_browser, "genres")
        win._view_stack = stack

        def _on_genre_toggled(btn):
            if btn.get_active():
                stack.set_visible_child_name("genres")
            else:
                stack.set_visible_child_name("grid")

        win._genre_btn.connect("toggled", _on_genre_toggled)

        # Right sidebar: codex detail view
        codex_split = Adw.OverlaySplitView()
        codex_split.set_content(stack)
        codex_split.set_sidebar(win._codex)
        codex_split.set_sidebar_position(Gtk.PackType.END)
        codex_split.set_min_sidebar_width(360)
        codex_split.set_max_sidebar_width(460)
        codex_split.set_show_sidebar(False)
        win._split = codex_split
        win._codex.on_dismiss = lambda: codex_split.set_show_sidebar(False)

        def _codex_search(query: str):
            win._search_entry.set_text(query)
            win._search_btn.set_active(True)

        win._codex.on_search = _codex_search

        def _genre_search(query: str):
            win._search_entry.set_text(query)
            win._search_btn.set_active(True)
            win._genre_btn.set_active(False)  # switch back to grid

        win._genre_browser.on_search = _genre_search

        # Left sidebar: virtual library list
        vl_defs = load_virtual_libraries()
        win._vl_defs = vl_defs
        vl_cache: dict[str, object] = {}

        def _vl_resolver(name: str):
            from hermitage.search import parse_query as _parse
            if name not in vl_cache:
                expr_str = vl_defs.get(name)
                vl_cache[name] = _parse(expr_str) if expr_str else None
            return vl_cache.get(name)

        win._vl_resolver = _vl_resolver

        vl_sidebar = self._build_vl_sidebar(win)
        vl_split = Adw.OverlaySplitView()
        vl_split.set_content(codex_split)
        vl_split.set_sidebar(vl_sidebar)
        vl_split.set_sidebar_position(Gtk.PackType.START)
        vl_split.set_min_sidebar_width(200)
        vl_split.set_max_sidebar_width(260)
        vl_split.set_show_sidebar(False)

        win._vl_btn.bind_property(
            "active", vl_split, "show-sidebar",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        win._toolbar_view.set_content(vl_split)

    def _wire_search(self, win: Adw.ApplicationWindow):
        """Connect the search entry to the filter pipeline with debounce."""
        win._search_debounce_id = 0
        win._search_entry.connect("search-changed", self._on_search_changed, win)

    # -- event handlers -----------------------------------------------------

    @staticmethod
    def _on_book_activated(
        grid: Gtk.GridView, position: int, win: Adw.ApplicationWindow,
    ):
        """Handle grid item activation — populate and show the Codex."""
        obj: BookObject = grid.get_model().get_item(position)
        if obj is None:
            return
        win._codex.show_book(obj.book)
        win._split.set_show_sidebar(True)

    @staticmethod
    def _on_vl_activated(
        listbox: Gtk.ListBox, row: Gtk.ListBoxRow,
        win: Adw.ApplicationWindow,
    ):
        """Apply a virtual library filter when a sidebar row is clicked."""
        vl_name = row._vl_name
        if vl_name is None:
            win._search_entry.set_text("")
        else:
            win._search_entry.set_text(f'vl:"{vl_name}"')
            win._search_btn.set_active(True)

    @staticmethod
    def _on_search_changed(
        entry: Gtk.SearchEntry, win: Adw.ApplicationWindow,
    ):
        """Debounce search — wait 400ms after last keystroke before filtering."""
        if win._search_debounce_id:
            GLib.source_remove(win._search_debounce_id)
            win._search_debounce_id = 0

        query = entry.get_text().strip()

        # Clear filter immediately when the search bar is emptied
        if not query:
            win._filter.set_filter_func(None)
            win._title_widget.set_subtitle(f"{len(win._books)} books")
            return

        def _apply_filter():
            win._search_debounce_id = 0
            text = entry.get_text().strip()
            if not text:
                win._filter.set_filter_func(None)
                win._title_widget.set_subtitle(f"{len(win._books)} books")
                # Restore default sort
                HermitageApp._resort_grid(win)
                return GLib.SOURCE_REMOVE

            matched = filter_books(text, win._books, win._vl_resolver)
            matching_ids = {b.id for b in matched}
            win._filter.set_filter_func(
                lambda item: item.book.id in matching_ids,
            )

            # Auto-sort by series_index when filtering by series
            low = text.lower()
            if low.startswith("series:") or low.startswith('series:"'):
                items = [win._store.get_item(i)
                         for i in range(win._store.get_n_items())]
                _sort_books(items, "series", True)
                win._store.remove_all()
                for obj in items:
                    win._store.append(obj)

            count = win._filtered_model.get_n_items()
            win._title_widget.set_subtitle(
                f"{count} of {len(win._books)} books",
            )
            return GLib.SOURCE_REMOVE

        win._search_debounce_id = GLib.timeout_add(400, _apply_filter)

    @staticmethod
    def _resort_grid(win: Adw.ApplicationWindow):
        """Re-sort the grid store based on current config values."""
        from hermitage.config import get as cfg_get

        store = win._store
        field = cfg_get("sort_field", "title")
        ascending = cfg_get("sort_ascending", True)

        # Extract, sort, and repopulate
        items = [store.get_item(i) for i in range(store.get_n_items())]
        _sort_books(items, field, ascending)
        store.remove_all()
        for obj in items:
            store.append(obj)

    # -- builders -----------------------------------------------------------

    def _build_vl_sidebar(self, win: Adw.ApplicationWindow) -> Gtk.Widget:
        """Build the virtual library sidebar list."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        vl_header = Gtk.Label(label="Libraries", xalign=0)
        vl_header.add_css_class("codex-section-title")
        vl_header.set_margin_start(16)
        vl_header.set_margin_top(12)
        vl_header.set_margin_bottom(8)
        box.append(vl_header)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.add_css_class("navigation-sidebar")

        # "All Books" row
        all_row = self._make_vl_row("All Books", None)
        listbox.append(all_row)

        for name in sorted(win._vl_defs.keys()):
            listbox.append(self._make_vl_row(name, name))

        listbox.select_row(all_row)
        listbox.connect("row-activated", self._on_vl_activated, win)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(listbox)
        box.append(scrolled)

        return box

    @staticmethod
    def _make_vl_row(label_text: str, vl_name: str | None) -> Gtk.ListBoxRow:
        """Create a single virtual library sidebar row."""
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=label_text, xalign=0)
        label.set_margin_start(12)
        label.set_margin_end(12)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        row.set_child(label)
        row._vl_name = vl_name
        return row

    @staticmethod
    def _setup_breakpoints(win: Adw.ApplicationWindow, grid: Gtk.GridView):
        """Configure responsive column scaling via Adw.Breakpoint."""
        def _uint(v: int) -> GObject.Value:
            val = GObject.Value(GObject.TYPE_UINT)
            val.set_uint(v)
            return val

        bp_narrow = Adw.Breakpoint(
            condition=Adw.BreakpointCondition.parse("max-width: 500sp"),
        )
        bp_narrow.add_setter(grid, "min-columns", _uint(2))
        bp_narrow.add_setter(grid, "max-columns", _uint(3))
        win.add_breakpoint(bp_narrow)

        bp_medium = Adw.Breakpoint(
            condition=Adw.BreakpointCondition.parse("max-width: 900sp"),
        )
        bp_medium.add_setter(grid, "min-columns", _uint(3))
        bp_medium.add_setter(grid, "max-columns", _uint(5))
        win.add_breakpoint(bp_medium)


def run():
    app = HermitageApp()
    app.run()
