"""Series browser — sibling to GenreBrowser, grouped by Calibre series.

Calibre stores `series` (the name) and `series_index` (the position) on every
book. We aggregate the loaded library here — no extra DB query needed — and
render each series as a card with its name, book count, index range, and the
list of titles in reading order. Clicking the card filters the grid via
`series:"Name"`, which `app._on_search_changed` already auto-sorts by
`series_index` (Phase 6).
"""

from __future__ import annotations

from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Pango

from hermitage.database import Book


@dataclass(slots=True)
class SeriesEntry:
    name: str
    books: list[Book]  # in series_index order

    @property
    def count(self) -> int:
        return len(self.books)

    @property
    def index_range(self) -> str:
        """Human-readable index span — '#1' or '#1 → #7' or '#1 → #7 (gaps)'."""
        if not self.books:
            return ""
        indices = sorted({b.series_index for b in self.books})

        def _fmt(i: float) -> str:
            return str(int(i)) if i == int(i) else f"{i:g}"

        first, last = indices[0], indices[-1]
        if first == last:
            return f"#{_fmt(first)}"

        # Detect a complete contiguous integer run from first to last
        contiguous = (
            len(indices) == int(last) - int(first) + 1
            and all(i == int(i) for i in indices)
        )
        suffix = "" if contiguous else " (incomplete)"
        return f"#{_fmt(first)} → #{_fmt(last)}{suffix}"


def _build_series_index(books: list[Book]) -> list[SeriesEntry]:
    """Group books by series, drop the series-less, sort each by index."""
    by_name: dict[str, list[Book]] = {}
    for b in books:
        if not b.series:
            continue
        by_name.setdefault(b.series, []).append(b)

    out: list[SeriesEntry] = []
    for name, bs in by_name.items():
        bs.sort(key=lambda b: b.series_index)
        out.append(SeriesEntry(name=name, books=bs))
    out.sort(key=lambda e: e.name.lower())
    return out


# ---------------------------------------------------------------------------
# SeriesBrowser widget
# ---------------------------------------------------------------------------


class SeriesBrowser(Gtk.Box):
    """Category page that lists every series in the library."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_search = None  # callback(query_str)
        self._build_ui()

    def _build_ui(self):
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp(maximum_size=900, tightening_threshold=700)
        self._content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18,
        )
        self._content.set_margin_start(24)
        self._content.set_margin_end(24)
        self._content.set_margin_top(24)
        self._content.set_margin_bottom(24)
        clamp.set_child(self._content)
        scrolled.set_child(clamp)
        self.append(scrolled)

    def populate(self, books: list[Book]):
        """Build the series page from the loaded library."""
        # Clear prior content
        while True:
            child = self._content.get_first_child()
            if child is None:
                break
            self._content.remove(child)

        entries = _build_series_index(books)

        header = Gtk.Label(label="Series", xalign=0)
        header.add_css_class("title-1")
        self._content.append(header)

        total_books_in_series = sum(e.count for e in entries)
        subtitle = Gtk.Label(
            label=(
                f"{len(entries)} series · "
                f"{total_books_in_series} of {len(books)} books"
            ),
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_margin_bottom(4)
        self._content.append(subtitle)

        if not entries:
            empty = Adw.StatusPage(
                title="No series in this library",
                description=(
                    "Calibre series metadata is empty — "
                    "set a series on a book in Calibre to see it here."
                ),
                icon_name="view-paged-symbolic",
            )
            self._content.append(empty)
            return

        for entry in entries:
            self._content.append(self._build_card(entry))

    def _build_card(self, entry: SeriesEntry) -> Gtk.Widget:
        """Build a single series card. Whole card is the click target."""
        card = Gtk.Button()
        card.add_css_class("card")
        card.add_css_class("series-card")
        card.set_can_focus(True)
        card.connect("clicked", self._on_card_clicked, entry.name)
        card.set_tooltip_text(f'Filter library to “{entry.name}”')

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        inner.set_margin_top(14)
        inner.set_margin_bottom(14)

        # Header row: name + index range (right-aligned)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        name_label = Gtk.Label(label=entry.name, xalign=0)
        name_label.add_css_class("series-name")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_hexpand(True)
        head.append(name_label)

        range_label = Gtk.Label(label=entry.index_range)
        range_label.add_css_class("series-range")
        head.append(range_label)

        inner.append(head)

        # Subtitle — book count + first/last titles for orientation
        first_title = entry.books[0].title
        last_title = entry.books[-1].title
        if entry.count == 1:
            sub_text = first_title
        elif entry.count == 2:
            sub_text = f"{first_title}  ·  {last_title}"
        else:
            sub_text = f"{first_title}  →  {last_title}  ({entry.count} books)"

        sub_label = Gtk.Label(label=sub_text, xalign=0)
        sub_label.add_css_class("series-titles")
        sub_label.set_ellipsize(Pango.EllipsizeMode.END)
        sub_label.set_wrap(False)
        inner.append(sub_label)

        card.set_child(inner)
        return card

    def _on_card_clicked(self, btn, series_name: str):
        if self.on_search:
            self.on_search(f'series:"{series_name}"')
