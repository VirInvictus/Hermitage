"""Library Insights — at-a-glance stats and audit for the loaded library.

A standalone `Gtk.Window` opened from the hamburger menu. Operates entirely
on the in-memory `list[Book]` Hermitage already has — no extra DB query, no
background work. Aggregations are computed once at construction and rendered
into a scrollable column.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango

from hermitage import widgets
from hermitage.database import Book


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LibrarySummary:
    total_books: int
    total_authors: int
    total_series: int
    total_tags: int
    total_identifiers: int
    top_tags: list[tuple[str, int]]
    top_authors: list[tuple[str, int]]
    format_counts: list[tuple[str, int]]
    no_cover: list[Book]
    no_formats: list[Book]
    no_tags: list[Book]
    no_identifiers: list[Book]
    rated_count: int
    avg_rating_x10: int  # rating * 2 to render as 10-scale int (no floats)


def summarize(books: list[Book]) -> LibrarySummary:
    """Compute every stat the Insights window renders."""
    tag_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()
    fmt_counter: Counter[str] = Counter()
    series: set[str] = set()
    identifier_count = 0
    no_cover: list[Book] = []
    no_formats: list[Book] = []
    no_tags: list[Book] = []
    no_identifiers: list[Book] = []
    rated_total = 0
    rated_count = 0

    for b in books:
        for t in b.tags:
            t = t.strip()
            if t:
                tag_counter[t] += 1
        for a in b.authors:
            a = a.strip()
            if a:
                author_counter[a] += 1
        for f in b.formats:
            f = f.strip()
            if f:
                fmt_counter[f] += 1
        if b.series:
            series.add(b.series)
        identifier_count += len(b.identifiers)

        if not b.has_cover or (b.cover_path and not b.cover_path.is_file()):
            no_cover.append(b)
        if not b.formats:
            no_formats.append(b)
        if not b.tags:
            no_tags.append(b)
        if not b.identifiers:
            no_identifiers.append(b)

        if b.rating:
            rated_total += b.rating
            rated_count += 1

    avg = (rated_total // rated_count) if rated_count else 0

    return LibrarySummary(
        total_books=len(books),
        total_authors=len(author_counter),
        total_series=len(series),
        total_tags=len(tag_counter),
        total_identifiers=identifier_count,
        top_tags=tag_counter.most_common(15),
        top_authors=author_counter.most_common(15),
        format_counts=fmt_counter.most_common(),
        no_cover=no_cover,
        no_formats=no_formats,
        no_tags=no_tags,
        no_identifiers=no_identifiers,
        rated_count=rated_count,
        avg_rating_x10=avg,
    )


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------


class InsightsWindow(Gtk.Window):
    """Library Insights — at-a-glance + top-N + audit."""

    def __init__(self, parent: Gtk.Window, books: list[Book]):
        super().__init__(
            transient_for=parent,
            modal=True,
            title="Library Insights",
            default_width=720,
            default_height=720,
        )

        self._summary = summarize(books)
        self._build_ui()

    def _build_ui(self):
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = widgets.Clamp(maximum_size=720)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        column.set_margin_start(24)
        column.set_margin_end(24)
        column.set_margin_top(24)
        column.set_margin_bottom(24)

        column.append(self._build_glance())
        column.append(self._build_top_section("Top Tags", self._summary.top_tags))
        column.append(
            self._build_top_section("Top Authors", self._summary.top_authors),
        )
        column.append(
            self._build_top_section(
                "Formats",
                self._summary.format_counts,
                max_rows=20,
            ),
        )
        column.append(self._build_audit())

        clamp.set_child(column)
        scrolled.set_child(clamp)
        self.set_titlebar(Gtk.HeaderBar())
        self.set_child(scrolled)

    # ------------------------------------------------------------------

    def _build_glance(self) -> Gtk.Widget:
        """Big-number summary tiles."""
        s = self._summary
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        section.append(self._section_title("At a glance"))

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_min_children_per_line(2)
        flow.set_max_children_per_line(5)
        flow.set_row_spacing(8)
        flow.set_column_spacing(8)

        tiles = [
            ("Books", f"{s.total_books:,}"),
            ("Authors", f"{s.total_authors:,}"),
            ("Series", f"{s.total_series:,}"),
            ("Tags", f"{s.total_tags:,}"),
            ("Identifiers", f"{s.total_identifiers:,}"),
        ]
        for label, value in tiles:
            flow.append(self._make_tile(label, value))
        section.append(flow)

        if s.rated_count:
            avg = s.avg_rating_x10 / 2  # display 0–5
            note = Gtk.Label(
                label=(
                    f"Rated:  {s.rated_count:,} of {s.total_books:,} books  "
                    f"·  average {avg:.1f} / 5"
                ),
                xalign=0,
            )
            note.add_css_class("dim-label")
            section.append(note)
        return section

    def _make_tile(self, label: str, value: str) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.add_css_class("card")
        card.add_css_class("insights-tile")
        card.set_margin_top(2)

        value_lbl = Gtk.Label(label=value, xalign=0.5)
        value_lbl.add_css_class("insights-tile-value")

        name_lbl = Gtk.Label(label=label, xalign=0.5)
        name_lbl.add_css_class("insights-tile-label")

        value_lbl.set_margin_top(14)
        name_lbl.set_margin_bottom(14)
        card.append(value_lbl)
        card.append(name_lbl)
        return card

    # ------------------------------------------------------------------

    def _build_top_section(
        self,
        title: str,
        items: list[tuple[str, int]],
        max_rows: int = 15,
    ) -> Gtk.Widget:
        """Bar-style ranked list with proportional fill."""
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        section.append(self._section_title(title))

        if not items:
            empty = Gtk.Label(label="—", xalign=0)
            empty.add_css_class("dim-label")
            section.append(empty)
            return section

        max_count = items[0][1] or 1  # items is sorted desc
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        for name, count in items[:max_rows]:
            rows.append(self._make_bar_row(name, count, max_count))

        section.append(rows)
        return section

    def _make_bar_row(self, name: str, count: int, max_count: int) -> Gtk.Widget:
        """One row with name, count, and a Gtk.LevelBar showing proportion."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        name_label = Gtk.Label(label=name, xalign=0)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_size_request(220, -1)
        name_label.add_css_class("insights-row-name")
        row.append(name_label)

        bar = Gtk.LevelBar()
        bar.set_min_value(0)
        bar.set_max_value(max_count)
        bar.set_value(count)
        bar.set_hexpand(True)
        bar.add_css_class("insights-bar")
        row.append(bar)

        count_label = Gtk.Label(label=f"{count:,}")
        count_label.add_css_class("insights-row-count")
        count_label.set_xalign(1)
        count_label.set_size_request(60, -1)
        row.append(count_label)

        return row

    # ------------------------------------------------------------------

    def _build_audit(self) -> Gtk.Widget:
        """Library hygiene: missing covers / formats / tags / identifiers."""
        s = self._summary
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        section.append(self._section_title("Audit"))

        list_box = Gtk.ListBox()
        list_box.add_css_class("boxed-list")
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        rows = [
            ("Missing cover files", s.no_cover, "image-x-generic-symbolic"),
            ("No format files", s.no_formats, "document-properties-symbolic"),
            ("No tags", s.no_tags, "tag-symbolic"),
            ("No external IDs", s.no_identifiers, "emblem-shared-symbolic"),
        ]
        total = s.total_books or 1
        for title, sample, icon in rows:
            list_box.append(self._make_audit_row(title, sample, icon, total))
        section.append(list_box)
        return section

    def _make_audit_row(
        self,
        title: str,
        sample: list[Book],
        icon_name: str,
        total: int,
    ) -> Gtk.Widget:
        n = len(sample)
        pct = (n * 100) // total if total else 0
        if n == 0:
            subtitle = "0 books — clean"
        else:
            preview = ", ".join(b.title for b in sample[:3])
            if n > 3:
                preview += f", +{n - 3:,} more"
            subtitle = f"{n:,} books ({pct}%) — {preview}"

        img = Gtk.Image.new_from_icon_name(icon_name)
        return widgets.value_row(title, subtitle, prefix=img)

    # ------------------------------------------------------------------

    @staticmethod
    def _section_title(text: str) -> Gtk.Widget:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("title-2")
        return label
