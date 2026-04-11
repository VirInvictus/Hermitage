"""The Codex — premium detail view for a single book."""

from __future__ import annotations

import hashlib
import html
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from hermitage.database import Book, library_root
from hermitage.thumbnailer import get_cached_texture, request_texture

# ---------------------------------------------------------------------------
# Hero banner blur generator
# ---------------------------------------------------------------------------

_BLUR_CACHE_DIR = Path.home() / ".cache" / "hermitage" / "blur"
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hermitage-blur")


def _generate_blurred_cover(cover: Path) -> Path | None:
    """Create a heavily blurred, darkened cover for the hero banner background."""
    from PIL import Image, ImageEnhance, ImageFilter

    try:
        stat = cover.stat()
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
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Synopsis text cleaning
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities from Calibre comments."""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    # Collapse whitespace runs but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Format file resolution
# ---------------------------------------------------------------------------

_FORMAT_PRIORITY = ["EPUB", "PDF", "MOBI", "AZW3", "CBZ", "CBR", "DJVU", "TXT"]


def _find_format_file(book: Book) -> Path | None:
    """Locate the best readable file for a book, preferring EPUB > PDF > etc."""
    root = library_root()
    book_dir = root / book.path

    for fmt in _FORMAT_PRIORITY:
        if fmt in book.formats:
            candidates = list(book_dir.glob(f"*.{fmt.lower()}"))
            if not candidates:
                candidates = list(book_dir.glob(f"*.{fmt}"))
            if candidates:
                return candidates[0]

    # Fallback: try any format present
    for fmt in book.formats:
        candidates = list(book_dir.glob(f"*.{fmt.lower()}"))
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
        self.on_dismiss = None
        self.on_search = None  # callback(query_str) — populate search bar
        self._build_ui()

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
        dismiss_btn.set_valign(Gtk.Align.START)
        dismiss_btn.set_halign(Gtk.Align.END)
        dismiss_btn.set_margin_top(8)
        dismiss_btn.set_margin_end(8)
        dismiss_btn.connect("clicked", self._on_dismiss_clicked)
        self._hero.add_overlay(dismiss_btn)

        # Content overlay: cover + text
        hero_content = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=20,
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
        body = Adw.Clamp(maximum_size=600, tightening_threshold=400)
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

        content.append(body)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_book(self, book: Book):
        """Populate the Codex with a book's details."""
        self._current_book = book

        # Title & Author
        self._title_label.set_text(book.title)
        self._author_label.set_text(
            ", ".join(book.authors) if book.authors else "Unknown Author",
        )

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

        # Rating (Calibre stores 0-10, display as 5-star)
        if book.rating:
            full = book.rating // 2
            stars = "\u2605" * full + "\u2606" * (5 - full)
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
                pill = Gtk.Button(label=tag.strip())
                pill.add_css_class("codex-tag-pill")
                pill.add_css_class("codex-link-btn")
                pill.connect("clicked", self._on_tag_clicked, tag.strip())
                self._tags_flow.append(pill)
        else:
            self._tags_header.set_visible(False)
            self._tags_flow.set_visible(False)

        # Synopsis
        if book.comment:
            text = _clean_html(book.comment)
            self._synopsis.set_text(text)
            self._synopsis_header.set_visible(True)
            self._synopsis.set_visible(True)
        else:
            self._synopsis_header.set_visible(False)
            self._synopsis.set_visible(False)

        # Formats
        if book.formats:
            self._formats_label.set_text(
                "Formats:  " + "  \u00b7  ".join(book.formats),
            )
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

    def _load_hero_cover(self, book: Book, cover: Path):
        """Set the mini cover in the hero from the thumbnail cache."""
        tex = get_cached_texture(cover)
        if tex:
            self._hero_cover.set_paintable(tex)
            return

        self._hero_cover.set_paintable(None)
        book_id = book.id

        def _on_tex(src, texture):
            if self._current_book and self._current_book.id == book_id and texture:
                self._hero_cover.set_paintable(texture)

        request_texture(cover, _on_tex)

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
