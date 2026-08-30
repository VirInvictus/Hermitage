"""The Codex — premium detail view for a single book."""

from __future__ import annotations

import hashlib
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from cquarry.helpers import normalize_rating
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from hermitage import widgets
from hermitage.database import Book, CustomColumn, get_cquarry_db, library_root
from hermitage.thumbnailer import get_cached_texture, request_texture

# ---------------------------------------------------------------------------
# Hero banner blur generator
# ---------------------------------------------------------------------------

_BLUR_CACHE_DIR = Path.home() / ".cache" / "hermitage" / "blur"
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hermitage-blur")


def _generate_blurred_cover(cover: Path) -> Path | None:
    """Create a heavily blurred, darkened cover for the hero banner background."""
    import sys

    from PIL import Image, ImageEnhance, ImageFile, ImageFilter, UnidentifiedImageError

    ImageFile.LOAD_TRUNCATED_IMAGES = True

    try:
        stat = cover.stat()
        if stat.st_size == 0:
            return None
        key = f"blur:{cover}:{stat.st_mtime_ns}:{stat.st_size}"
        digest = hashlib.blake2b(key.encode(), digest_size=16).hexdigest()
        blur_path = _BLUR_CACHE_DIR / f"{digest}.jpg"

        if blur_path.is_file():
            return blur_path

        _BLUR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with Image.open(cover) as img:
            img = img.convert("RGB").resize((800, 400), Image.LANCZOS)
            img = img.filter(ImageFilter.GaussianBlur(radius=30))
            img = ImageEnhance.Brightness(img).enhance(0.35)
            img.save(blur_path, "JPEG", quality=80)

        return blur_path
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        print(
            f"hermitage: hero blur failed for {cover}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


# ---------------------------------------------------------------------------
# Synopsis text cleaning
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
# Block-level boundaries become newlines before the generic strip; without
# this a multi-paragraph Calibre comment collapsed into one wall of text.
_BLOCK_RE = re.compile(r"(?i)<\s*/?\s*(br|p|div|li|tr|h[1-6]|blockquote)\b[^>]*>")


def _clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities from Calibre comments.

    Paragraph breaks (<p>, <br>, div, headings, list/table rows) survive as
    newlines; everything else strips to spaces.
    """
    text = _BLOCK_RE.sub("\n", raw)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    # Collapse whitespace runs but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Format file resolution
# ---------------------------------------------------------------------------

_FORMAT_PRIORITY = ["EPUB", "PDF", "MOBI", "AZW3", "CBZ", "CBR", "DJVU", "TXT"]


# ---------------------------------------------------------------------------
# Identifier → external URL map
# ---------------------------------------------------------------------------
#
# Calibre stores book identifiers as (type, value) tuples. We render them as
# "Find this book on …" link buttons in the Codex; only types we know how to
# turn into a URL get a button. Display label first, URL formatter second —
# the formatter receives the raw value with no escaping (every site we link
# uses opaque ids or already-encoded paths).

_IDENTIFIER_LINKS: dict[str, tuple[str, str]] = {
    "isbn": ("Open Library", "https://openlibrary.org/isbn/{}"),
    "goodreads": ("Goodreads", "https://www.goodreads.com/book/show/{}"),
    "google": ("Google Books", "https://books.google.com/books?id={}"),
    "amazon": ("Amazon", "https://www.amazon.com/dp/{}"),
    "asin": ("Amazon", "https://www.amazon.com/dp/{}"),
    "mobi-asin": ("Amazon", "https://www.amazon.com/dp/{}"),
    "barnesnoble": ("Barnes & Noble", "https://www.barnesandnoble.com/s/{}"),
    "storygraph": ("StoryGraph", "https://app.thestorygraph.com/books/{}"),
    "hardcover": ("Hardcover", "https://hardcover.app/books/{}"),
    "fictiondb": ("FictionDB", "https://www.fictiondb.com/title/{}"),
    "doi": ("DOI", "https://doi.org/{}"),
    "url": ("Link", "{}"),
    "uri": ("Link", "{}"),
}


def _find_format_file(book: Book) -> Path | None:
    """Locate the best readable file for a book, preferring EPUB > PDF > etc.

    Exact paths come from cquarry's get_formats() (the canonical storage
    layout); the historical directory glob remains as a fallback for
    databases whose catalogued rows lag the files on disk.
    """
    try:
        fmt_map = get_cquarry_db().get_formats(book.id)
    except Exception:
        fmt_map = {}

    for fmt in _FORMAT_PRIORITY:
        if fmt in book.formats:
            entry = fmt_map.get(fmt)
            if entry and os.path.exists(entry["path"]):
                return Path(entry["path"])
            candidates = list((library_root() / book.path).glob(f"*.{fmt.lower()}"))
            if not candidates:
                candidates = list((library_root() / book.path).glob(f"*.{fmt}"))
            if candidates:
                return candidates[0]

    # Fallback: try any format present
    for fmt in book.formats:
        entry = fmt_map.get(fmt)
        if entry and os.path.exists(entry["path"]):
            return Path(entry["path"])
        candidates = list((library_root() / book.path).glob(f"*.{fmt.lower()}"))
        if candidates:
            return candidates[0]

    return None


# ---------------------------------------------------------------------------
# CodexView widget
# ---------------------------------------------------------------------------


class CodexView(Gtk.Box):
    """Detail view sidebar for a single book — the Codex."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._current_book: Book | None = None
        self._custom_columns: list[CustomColumn] = []
        self.on_dismiss = None
        self.on_search = None  # callback(query_str) — populate search bar
        self.on_book_opened = None  # callback(book_id) — fired after Read launch
        self._build_ui()

    # Datatypes rendered as clickable filter pills; everything else is a line.
    _PILL_DATATYPES = frozenset({"text", "enumeration", "series"})

    def _build_ui(self):
        # Scrollable container for the full detail view
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(content)
        self.append(scrolled)

        # ---- Hero Banner ----
        self._hero = Gtk.Overlay()
        self._hero.set_size_request(-1, 280)
        self._hero.add_css_class("codex-hero")

        # Blurred background
        self._hero_bg = Gtk.Picture()
        self._hero_bg.set_content_fit(Gtk.ContentFit.COVER)
        self._hero_bg.add_css_class("codex-hero-bg")
        self._hero.set_child(self._hero_bg)

        # Dismiss button (top-right of hero)
        dismiss_btn = Gtk.Button(icon_name="window-close-symbolic")
        dismiss_btn.add_css_class("circular")
        dismiss_btn.add_css_class("codex-dismiss")
        dismiss_btn.set_tooltip_text("Close detail view (Esc)")
        dismiss_btn.set_valign(Gtk.Align.START)
        dismiss_btn.set_halign(Gtk.Align.END)
        dismiss_btn.set_margin_top(8)
        dismiss_btn.set_margin_end(8)
        dismiss_btn.connect("clicked", self._on_dismiss_clicked)
        self._hero.add_overlay(dismiss_btn)

        # Content overlay: cover + text
        hero_content = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=20,
        )
        hero_content.set_valign(Gtk.Align.END)
        hero_content.set_halign(Gtk.Align.FILL)
        hero_content.set_margin_start(24)
        hero_content.set_margin_end(24)
        hero_content.set_margin_bottom(20)

        # Mini cover thumbnail
        hero_cover_frame = Gtk.AspectFrame(ratio=2 / 3, obey_child=False)
        hero_cover_frame.set_size_request(110, 165)
        hero_cover_frame.set_overflow(Gtk.Overflow.HIDDEN)
        hero_cover_frame.add_css_class("codex-hero-cover-frame")

        self._hero_cover = Gtk.Picture()
        self._hero_cover.set_content_fit(Gtk.ContentFit.COVER)
        hero_cover_frame.set_child(self._hero_cover)
        hero_content.append(hero_cover_frame)

        # Title / Author / Series column
        hero_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hero_text.set_valign(Gtk.Align.END)
        hero_text.set_hexpand(True)

        self._title_label = Gtk.Label(xalign=0)
        self._title_label.set_wrap(True)
        self._title_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._title_label.set_lines(3)
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.add_css_class("codex-title")
        hero_text.append(self._title_label)

        self._author_btn = Gtk.Button()
        self._author_btn.add_css_class("codex-author")
        self._author_btn.add_css_class("codex-link-btn")
        self._author_btn.set_tooltip_text("Show all books by this author")
        self._author_btn.set_halign(Gtk.Align.START)
        self._author_label = Gtk.Label(xalign=0)
        self._author_label.set_wrap(True)
        self._author_label.set_lines(2)
        self._author_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._author_btn.set_child(self._author_label)
        self._author_btn.connect("clicked", self._on_author_clicked)
        hero_text.append(self._author_btn)

        self._series_btn = Gtk.Button()
        self._series_btn.add_css_class("codex-series")
        self._series_btn.add_css_class("codex-link-btn")
        self._series_btn.set_tooltip_text("Show every book in this series")
        self._series_btn.set_halign(Gtk.Align.START)
        self._series_label = Gtk.Label(xalign=0)
        self._series_label.set_wrap(True)
        self._series_btn.set_child(self._series_label)
        self._series_btn.connect("clicked", self._on_series_clicked)
        hero_text.append(self._series_btn)

        hero_content.append(hero_text)
        self._hero.add_overlay(hero_content)

        content.append(self._hero)

        # ---- Body (below hero) ----
        body = widgets.Clamp(maximum_size=600)
        body_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        body_inner.set_margin_start(24)
        body_inner.set_margin_end(24)
        body_inner.set_margin_top(20)
        body_inner.set_margin_bottom(24)
        body.set_child(body_inner)

        # Rating
        self._rating_label = Gtk.Label(xalign=0)
        self._rating_label.add_css_class("codex-rating")
        body_inner.append(self._rating_label)

        # Read button
        self._read_btn = Gtk.Button(label="Read")
        self._read_btn.add_css_class("suggested-action")
        self._read_btn.add_css_class("pill")
        self._read_btn.add_css_class("codex-read-btn")
        self._read_btn.set_tooltip_text("Open in your default reader")
        self._read_btn.set_halign(Gtk.Align.START)
        self._read_btn.connect("clicked", self._on_read_clicked)
        body_inner.append(self._read_btn)

        # Tags section
        self._tags_header = Gtk.Label(label="Tags", xalign=0)
        self._tags_header.add_css_class("codex-section-title")
        body_inner.append(self._tags_header)

        self._tags_flow = Gtk.FlowBox()
        self._tags_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._tags_flow.set_homogeneous(False)
        self._tags_flow.set_max_children_per_line(20)
        self._tags_flow.set_min_children_per_line(1)
        self._tags_flow.set_row_spacing(6)
        self._tags_flow.set_column_spacing(6)
        self._tags_flow.add_css_class("codex-tags")
        body_inner.append(self._tags_flow)

        # Custom columns section ("Details") — user-defined Calibre columns
        self._custom_header = Gtk.Label(label="Details", xalign=0)
        self._custom_header.add_css_class("codex-section-title")
        body_inner.append(self._custom_header)

        self._custom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._custom_box.add_css_class("codex-custom")
        body_inner.append(self._custom_box)

        # Identifiers section ("Find this book on …")
        self._idents_header = Gtk.Label(label="Find this book on", xalign=0)
        self._idents_header.add_css_class("codex-section-title")
        body_inner.append(self._idents_header)

        self._idents_flow = Gtk.FlowBox()
        self._idents_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._idents_flow.set_homogeneous(False)
        self._idents_flow.set_max_children_per_line(20)
        self._idents_flow.set_min_children_per_line(1)
        self._idents_flow.set_row_spacing(6)
        self._idents_flow.set_column_spacing(6)
        self._idents_flow.add_css_class("codex-tags")
        body_inner.append(self._idents_flow)

        # Synopsis section
        self._synopsis_header = Gtk.Label(label="Synopsis", xalign=0)
        self._synopsis_header.add_css_class("codex-section-title")
        body_inner.append(self._synopsis_header)

        self._synopsis = Gtk.Label(xalign=0)
        self._synopsis.set_wrap(True)
        self._synopsis.set_wrap_mode(Pango.WrapMode.WORD)
        self._synopsis.set_selectable(True)
        self._synopsis.add_css_class("codex-synopsis")
        self._synopsis.add_css_class("body")
        body_inner.append(self._synopsis)

        # Formats
        self._formats_label = Gtk.Label(xalign=0)
        self._formats_label.add_css_class("codex-meta")
        body_inner.append(self._formats_label)

        # Publication date
        self._pubdate_label = Gtk.Label(xalign=0)
        self._pubdate_label.add_css_class("codex-meta")
        body_inner.append(self._pubdate_label)

        # Last read (populated from hermitage.history)
        self._last_read_label = Gtk.Label(xalign=0)
        self._last_read_label.add_css_class("codex-meta")
        body_inner.append(self._last_read_label)

        content.append(body)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_custom_columns(self, columns: list[CustomColumn]):
        """Provide the custom-column schema (display names, datatypes, order)."""
        self._custom_columns = columns

    def show_book(self, book: Book):
        """Populate the Codex with a book's details."""
        self._current_book = book

        # Title & Author — display names ordered by their true sort keys
        # (cquarry >=1.4 `author_sorts`), with author links in the tooltip.
        if book.authors:
            sorts = book.author_sorts or []
            links = book.author_links or []
            paired = [
                (
                    name,
                    sorts[i] if i < len(sorts) else "",
                    links[i] if i < len(links) else "",
                )
                for i, name in enumerate(book.authors)
            ]
            # Sort by the true sort key when present, display order otherwise.
            ordered = sorted(paired, key=lambda p: p[1].lower() or p[0].lower())
            self._author_label.set_text(", ".join(p[0] for p in ordered))
            link_bits = [f"{name} — {url}" for name, _, url in ordered if url]
            if link_bits:
                self._author_label.set_tooltip_text("\n".join(link_bits))
        else:
            self._author_label.set_text("Unknown Author")

        # Series
        if book.series:
            idx = (
                int(book.series_index)
                if book.series_index == int(book.series_index)
                else book.series_index
            )
            self._series_label.set_text(f"{book.series} #{idx}")
            self._series_btn.set_visible(True)
        else:
            self._series_btn.set_visible(False)

        # Rating (Calibre stores 0-10, display as 5-star with half stars)
        if book.rating:
            stars_val = normalize_rating(book.rating) or 0.0
            full = int(stars_val)
            half = stars_val - full >= 0.5
            stars = (
                "\u2605" * full
                + ("\u00bd" if half else "")
                + "\u2606" * (5 - full - (1 if half else 0))
            )
            self._rating_label.set_text(stars)
            self._rating_label.set_visible(True)
        else:
            self._rating_label.set_visible(False)

        # Tags
        self._clear_flow_box(self._tags_flow)
        if book.tags:
            self._tags_header.set_visible(True)
            self._tags_flow.set_visible(True)
            for tag in book.tags:
                t = tag.strip()
                pill = Gtk.Button(label=t)
                pill.add_css_class("codex-tag-pill")
                pill.add_css_class("codex-link-btn")
                pill.set_tooltip_text(f"Filter library to “{t}”")
                pill.connect("clicked", self._on_tag_clicked, t)
                self._tags_flow.append(pill)
        else:
            self._tags_header.set_visible(False)
            self._tags_flow.set_visible(False)

        # Identifiers — link buttons for the types we know how to URL-format
        self._clear_flow_box(self._idents_flow)
        linkable = [
            (key, val)
            for key, val in book.identifiers.items()
            if key in _IDENTIFIER_LINKS and val
        ]
        if linkable:
            self._idents_header.set_visible(True)
            self._idents_flow.set_visible(True)
            for key, val in linkable:
                label, url_fmt = _IDENTIFIER_LINKS[key]
                btn = Gtk.Button(label=label)
                btn.add_css_class("codex-tag-pill")
                btn.add_css_class("codex-link-btn")
                btn.set_tooltip_text(f"Open {label} ({key}: {val})")
                btn.connect("clicked", self._on_identifier_clicked, url_fmt.format(val))
                self._idents_flow.append(btn)
        else:
            self._idents_header.set_visible(False)
            self._idents_flow.set_visible(False)

        # Custom columns ("Details")
        self._populate_custom(book)

        # Synopsis
        if book.comment:
            text = _clean_html(book.comment)
            self._synopsis.set_text(text)
            self._synopsis_header.set_visible(True)
            self._synopsis.set_visible(True)
        else:
            self._synopsis_header.set_visible(False)
            self._synopsis.set_visible(False)

        # Formats & page count (pages come from Calibre's native
        # books_pages_link via cquarry >=1.3)
        meta_bits: list[str] = []
        if book.formats:
            meta_bits.append("Formats:  " + "  \u00b7  ".join(book.formats))
        if book.pages:
            meta_bits.append(f"{book.pages} pages")
        if meta_bits:
            self._formats_label.set_text("   \u00b7   ".join(meta_bits))
            self._formats_label.set_visible(True)
        else:
            self._formats_label.set_visible(False)

        # Publication date
        self._pubdate_label.set_visible(False)
        if book.pubdate:
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(book.pubdate)
                if dt.year > 101:
                    self._pubdate_label.set_text(
                        f"Published:  {dt.strftime('%B %d, %Y')}",
                    )
                    self._pubdate_label.set_visible(True)
            except (ValueError, TypeError):
                pass

        # Read button
        self._read_btn.set_visible(bool(book.formats))

        # Last-read line — populated from local history database
        self._refresh_last_read()

        # ---- Hero visuals ----
        cover = book.cover_path
        if cover and cover.is_file():
            self._load_hero_cover(book, cover)
            self._load_hero_blur(book, cover)
        else:
            self._hero_cover.set_paintable(None)
            self._hero_bg.set_paintable(None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clear_flow_box(flow: Gtk.FlowBox):
        while True:
            child = flow.get_first_child()
            if child is None:
                break
            flow.remove(child)

    def _populate_custom(self, book: Book):
        """Render the user's Calibre custom columns as the Details section."""
        while (child := self._custom_box.get_first_child()) is not None:
            self._custom_box.remove(child)

        rows = [
            (col, book.custom[col.label])
            for col in self._custom_columns
            if book.custom.get(col.label) not in (None, "", [])
        ]
        if not rows:
            self._custom_header.set_visible(False)
            self._custom_box.set_visible(False)
            return

        self._custom_header.set_visible(True)
        self._custom_box.set_visible(True)
        for col, value in rows:
            self._custom_box.append(self._custom_row(col, value))

    def _custom_row(self, col: CustomColumn, value) -> Gtk.Box:
        """One Details row: the column name beside its value(s)."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("codex-custom-row")

        name = Gtk.Label(label=col.name, xalign=0)
        name.add_css_class("codex-custom-name")
        name.set_valign(Gtk.Align.START)
        row.append(name)

        if col.datatype in self._PILL_DATATYPES:
            flow = Gtk.FlowBox()
            flow.set_selection_mode(Gtk.SelectionMode.NONE)
            flow.set_homogeneous(False)
            flow.set_max_children_per_line(20)
            flow.set_min_children_per_line(1)
            flow.set_row_spacing(6)
            flow.set_column_spacing(6)
            flow.set_hexpand(True)
            flow.add_css_class("codex-tags")
            values = value if isinstance(value, list) else [value]
            for v in values:
                vs = str(v).strip()
                if not vs:
                    continue
                pill = Gtk.Button(label=vs)
                pill.add_css_class("codex-tag-pill")
                pill.add_css_class("codex-link-btn")
                pill.set_tooltip_text(f"Filter library to {col.name}: “{vs}”")
                pill.connect("clicked", self._on_custom_clicked, col.label, vs)
                self._apply_enum_color(pill, col, vs)
                flow.append(pill)
            row.append(flow)
        else:
            vlabel = Gtk.Label(label=self._format_scalar(col, value), xalign=0)
            vlabel.add_css_class("codex-custom-value")
            vlabel.set_wrap(True)
            vlabel.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            vlabel.set_hexpand(True)
            row.append(vlabel)

        return row

    _enum_css_provider: Gtk.CssProvider | None = None
    _enum_classes_issued: set[str] = set()

    @classmethod
    def _apply_enum_color(cls, pill: Gtk.Button, col: CustomColumn, value: str):
        """Tint an enumeration pill with its Calibre ``enum_colors`` entry.

        Colors come from the column's ``display`` JSON (cquarry >=1.4). Each
        distinct value gets one generated CSS class registered once on the
        default screen; unknown values keep the theme's default pill look.
        """
        colors = (col.display or {}).get("enum_colors") or {}
        color = colors.get(value)
        if not isinstance(color, str) or not color.startswith("#"):
            return
        css_class = "enum-color-" + "".join(
            c if c.isalnum() else "-" for c in value.lower()
        )
        if css_class not in cls._enum_classes_issued:
            provider = cls._enum_css_provider
            if provider is None:
                provider = Gtk.CssProvider()
                cls._enum_css_provider = provider
            provider.load_from_string(
                f".{css_class} {{ background-image: none; background-color: {color}; }}"
            )
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            cls._enum_classes_issued.add(css_class)
        pill.add_css_class(css_class)

    @staticmethod
    def _format_scalar(col: CustomColumn, value) -> str:
        """Human-format a non-pill custom value by its Calibre datatype."""
        dt = col.datatype
        if dt == "datetime":
            from datetime import datetime

            try:
                parsed = datetime.fromisoformat(str(value))
                if parsed.year > 101:  # Calibre's "undefined date" sentinel is year 101
                    return parsed.strftime("%B %d, %Y")
            except (ValueError, TypeError):
                pass
            return str(value)
        if dt == "bool":
            return "Yes" if value else "No"
        if dt == "comments":
            return _clean_html(str(value))
        if dt == "float":
            try:
                f = float(value)
                return str(int(f)) if f == int(f) else str(f)
            except (ValueError, TypeError):
                return str(value)
        return str(value)

    def _load_hero_cover(self, book: Book, cover: Path):
        """Set the mini cover in the hero from the thumbnail cache."""
        scale = self._hero_cover.get_scale_factor()
        tex = get_cached_texture(cover, scale)
        if tex:
            self._hero_cover.set_paintable(tex)
            return

        self._hero_cover.set_paintable(None)
        book_id = book.id

        def _on_tex(src, texture):
            if self._current_book and self._current_book.id == book_id and texture:
                self._hero_cover.set_paintable(texture)

        request_texture(cover, _on_tex, scale)

    def _load_hero_blur(self, book: Book, cover: Path):
        """Generate and display the blurred hero background asynchronously."""
        self._hero_bg.set_paintable(None)
        book_id = book.id

        def _work():
            blur_path = _generate_blurred_cover(cover)
            if not blur_path:
                return
            try:
                texture = Gdk.Texture.new_from_filename(str(blur_path))
            except Exception:
                return

            def _deliver():
                if self._current_book and self._current_book.id == book_id:
                    self._hero_bg.set_paintable(texture)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_deliver)

        _executor.submit(_work)

    def _refresh_last_read(self):
        """Populate the 'Last read' meta line from history.db, if any."""
        book = self._current_book
        if not book:
            self._last_read_label.set_visible(False)
            return
        from hermitage import history

        ts = history.last_opened_for(book.id)
        if ts is None:
            self._last_read_label.set_visible(False)
        else:
            self._last_read_label.set_text(f"Last read:  {history.humanize(ts)}")
            self._last_read_label.set_visible(True)

    def _on_dismiss_clicked(self, btn):
        """Close the Codex sidebar."""
        if self.on_dismiss:
            self.on_dismiss()

    def _on_author_clicked(self, btn):
        """Search for the current book's author."""
        book = self._current_book
        if book and book.authors and self.on_search:
            author = book.authors[0]
            self.on_search(f'authors:"{author}"')

    def _on_series_clicked(self, btn):
        """Search for the current book's series."""
        book = self._current_book
        if book and book.series and self.on_search:
            self.on_search(f'series:"{book.series}"')

    def _on_tag_clicked(self, btn, tag: str):
        """Search for a specific tag."""
        if self.on_search:
            self.on_search(f'tags:"{tag}"')

    def _on_custom_clicked(self, btn, label: str, value: str):
        """Filter the library by a custom-column value.

        Exact match (the `=` prefix), so clicking "Read" does not also pull in
        "To Read" the way a substring search would — this mirrors what Calibre
        itself generates when you click a custom-column value in its UI.
        """
        if self.on_search:
            self.on_search(f'#{label}:"={value}"')

    def _on_identifier_clicked(self, btn, url: str):
        """Open an external identifier URL in the system browser."""
        launcher = Gtk.UriLauncher(uri=url)
        launcher.launch(self.get_root(), None, None)

    def _on_read_clicked(self, btn):
        """Launch the book in the system's default reader."""
        book = self._current_book
        if not book:
            return

        chosen = _find_format_file(book)
        if not chosen:
            return

        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(chosen)))
        launcher.launch(self.get_root(), None, None)

        # Record the open immediately — even if the launcher races we want the
        # event in history.db so the indicator and "Last read" line update.
        from hermitage import history

        history.record_open(book.id)
        if self.on_book_opened:
            self.on_book_opened(book.id)
        # Refresh the meta line so the user sees "Last read: just now"
        self._refresh_last_read()
