"""Genre browser — attractive category page built from Calibre tags."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Pango

from hermitage.database import Book


# ---------------------------------------------------------------------------
# Tag tree builder
# ---------------------------------------------------------------------------


def _build_tag_tree(books: list[Book]) -> dict:
    """Build a nested dict from dot-separated tags with book counts.

    Returns a tree where each node is:
        {"_count": int, "children": {name: node, ...}}
    """
    root: dict = {"_count": 0, "children": {}}

    for book in books:
        for tag in book.tags:
            tag = tag.strip()
            if not tag:
                continue
            parts = tag.split(".")
            node = root
            for part in parts:
                if part not in node["children"]:
                    node["children"][part] = {"_count": 0, "children": {}}
                node = node["children"][part]
            node["_count"] += 1

    return root


def _total_count(node: dict) -> int:
    """Recursively count all books under a node."""
    total = node["_count"]
    for child in node["children"].values():
        total += _total_count(child)
    return total


# ---------------------------------------------------------------------------
# GenreBrowser widget
# ---------------------------------------------------------------------------


class GenreBrowser(Gtk.Box):
    """Attractive genre/category browse page."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_search = None  # callback(query_str)
        self._build_ui()

    def _build_ui(self):
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._clamp = Adw.Clamp(maximum_size=800, tightening_threshold=600)
        self._content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
        )
        self._content.set_margin_start(24)
        self._content.set_margin_end(24)
        self._content.set_margin_top(24)
        self._content.set_margin_bottom(24)
        self._clamp.set_child(self._content)
        scrolled.set_child(self._clamp)
        self.append(scrolled)

    def populate(self, books: list[Book]):
        """Build the genre page from the book list."""
        # Clear existing content
        while True:
            child = self._content.get_first_child()
            if child is None:
                break
            self._content.remove(child)

        tree = _build_tag_tree(books)

        # Page header
        header = Gtk.Label(label="Genres", xalign=0)
        header.add_css_class("title-1")
        self._content.append(header)

        total_books = len(books)
        subtitle = Gtk.Label(
            label=f"{total_books} books across {self._count_leaves(tree)} genres",
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_margin_bottom(8)
        self._content.append(subtitle)

        # Build sections for each top-level category
        for name in sorted(tree["children"].keys()):
            child_node = tree["children"][name]
            section = self._build_section(name, name, child_node)
            self._content.append(section)

    def _build_section(
        self,
        display_name: str,
        full_path: str,
        node: dict,
    ) -> Gtk.Widget:
        """Build a section card for a top-level category."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("card")
        card.add_css_class("genre-card")
        card.set_margin_bottom(4)

        # Section header with total count
        total = _total_count(node)
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        header_box.set_margin_start(16)
        header_box.set_margin_end(16)
        header_box.set_margin_top(16)
        header_box.set_margin_bottom(8)

        section_label = Gtk.Label(label=display_name, xalign=0)
        section_label.add_css_class("title-3")
        section_label.set_hexpand(True)
        header_box.append(section_label)

        count_label = Gtk.Label(label=f"{total} books")
        count_label.add_css_class("dim-label")
        count_label.add_css_class("genre-count")
        header_box.append(count_label)

        card.append(header_box)

        # Direct books in this category (if any)
        if node["_count"] > 0:
            direct_btn = Gtk.Button()
            direct_btn.add_css_class("codex-link-btn")
            direct_btn.set_halign(Gtk.Align.START)
            direct_btn.set_margin_start(16)
            direct_btn.set_margin_bottom(4)
            direct_label = Gtk.Label(
                label=f"General ({node['_count']})",
            )
            direct_label.add_css_class("genre-direct")
            direct_btn.set_child(direct_label)
            direct_btn.connect(
                "clicked",
                self._on_genre_clicked,
                full_path,
            )
            card.append(direct_btn)

        # Recursively render children
        if node["children"]:
            self._build_children(card, node, full_path, depth=0)

        # Bottom padding
        spacer = Gtk.Box()
        spacer.set_size_request(-1, 12)
        card.append(spacer)

        return card

    def _build_children(
        self,
        container: Gtk.Box,
        node: dict,
        parent_path: str,
        depth: int,
    ):
        """Recursively render child nodes. Leaf nodes as pills, branches as
        labeled subsections with their own pill flows."""
        # Separate children into leaves (no further children) and branches
        leaves: list[tuple[str, str, dict]] = []
        branches: list[tuple[str, str, dict]] = []

        for child_name in sorted(node["children"].keys()):
            child_node = node["children"][child_name]
            child_path = f"{parent_path}.{child_name}"
            if child_node["children"]:
                branches.append((child_name, child_path, child_node))
            else:
                leaves.append((child_name, child_path, child_node))

        indent = 16 + (depth * 12)

        # Render leaf nodes as a flow of pills
        if leaves:
            flow = Gtk.FlowBox()
            flow.set_selection_mode(Gtk.SelectionMode.NONE)
            flow.set_homogeneous(False)
            flow.set_max_children_per_line(20)
            flow.set_min_children_per_line(1)
            flow.set_row_spacing(6)
            flow.set_column_spacing(6)
            flow.set_margin_start(indent)
            flow.set_margin_end(16)
            flow.set_margin_bottom(8)
            flow.add_css_class("genre-flow")

            for child_name, child_path, child_node in leaves:
                pill_btn = self._make_pill(child_name, child_path, child_node)
                flow.append(pill_btn)

            container.append(flow)

        # Render branch nodes as labeled subsections
        for child_name, child_path, child_node in branches:
            child_total = _total_count(child_node)

            # Subsection header
            sub_header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=6,
            )
            sub_header.set_margin_start(indent)
            sub_header.set_margin_end(16)
            sub_header.set_margin_top(4)
            sub_header.set_margin_bottom(4)

            # Make the subsection name clickable
            name_btn = Gtk.Button()
            name_btn.add_css_class("genre-subsection-btn")
            name_label = Gtk.Label(label=child_name, xalign=0)
            name_label.add_css_class("genre-subsection")
            name_btn.set_child(name_label)
            name_btn.set_hexpand(True)
            name_btn.set_halign(Gtk.Align.FILL)
            name_btn.connect("clicked", self._on_genre_clicked, child_path)
            sub_header.append(name_btn)

            sub_count = Gtk.Label(label=str(child_total))
            sub_count.add_css_class("dim-label")
            sub_count.add_css_class("genre-count")
            sub_header.append(sub_count)

            container.append(sub_header)

            # Direct books at this branch level
            if child_node["_count"] > 0:
                direct_btn = Gtk.Button()
                direct_btn.add_css_class("codex-link-btn")
                direct_btn.set_halign(Gtk.Align.START)
                direct_btn.set_margin_start(indent + 12)
                direct_btn.set_margin_bottom(2)
                direct_label = Gtk.Label(
                    label=f"General ({child_node['_count']})",
                )
                direct_label.add_css_class("genre-direct")
                direct_btn.set_child(direct_label)
                direct_btn.connect(
                    "clicked",
                    self._on_genre_clicked,
                    child_path,
                )
                container.append(direct_btn)

            # Recurse into this branch's children
            self._build_children(
                container,
                child_node,
                child_path,
                depth + 1,
            )

    def _make_pill(
        self,
        name: str,
        full_path: str,
        node: dict,
    ) -> Gtk.Button:
        """Create a single genre pill button."""
        total = _total_count(node)
        pill_btn = Gtk.Button()
        pill_btn.add_css_class("genre-pill")

        pill_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
        )
        name_label = Gtk.Label(label=name)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        pill_box.append(name_label)

        cnt_label = Gtk.Label(label=str(total))
        cnt_label.add_css_class("genre-pill-count")
        pill_box.append(cnt_label)

        pill_btn.set_child(pill_box)
        pill_btn.connect("clicked", self._on_genre_clicked, full_path)
        return pill_btn

    def _on_genre_clicked(self, btn, tag_path: str):
        """Search for books with this tag path."""
        if self.on_search:
            self.on_search(f'tags:"{tag_path}"')

    @staticmethod
    def _count_leaves(tree: dict) -> int:
        """Count total number of leaf tag paths."""
        count = 0
        for node in tree["children"].values():
            leaves = GenreBrowser._count_leaves(node)
            if leaves == 0:
                count += 1
            else:
                count += leaves
            if node["_count"] > 0 and node["children"]:
                count += 1  # node is both a leaf and a parent
        return count
