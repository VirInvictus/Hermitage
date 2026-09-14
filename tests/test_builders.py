"""Tests for the pure aggregation helpers behind the GTK browse surfaces.

Importing genres/series/insights/codex pulls in Gtk, which is safe headless —
no widget is ever instantiated here; only the module-level builders and
dataclasses are exercised.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hermitage.codex import (
    _IDENTIFIER_LINKS,
    CodexView,
    _clean_html,
    _enum_color_hex,
    _find_format_file,
    _ordered_formats,
)
from hermitage.database import Book, CustomColumn
from hermitage.genres import _build_tag_tree, _rolled_counts
from hermitage.insights import summarize
from hermitage.series import SeriesEntry, _build_series_index


def _book(**kw):
    defaults = dict(
        id=1,
        title="T",
        sort="T",
        authors=["A"],
        path="A/T (1)",
        has_cover=False,
    )
    defaults.update(kw)
    return Book(**defaults)


# --------------------------------------------------------------------------- #
# genres
# --------------------------------------------------------------------------- #
class TestTagTree(unittest.TestCase):
    def test_nested_counts(self):
        books = [
            _book(id=1, tags=["Fic.Fantasy.Grimdark"]),
            _book(id=2, tags=["Fic.Fantasy"]),
            _book(id=3, tags=["Fic"]),
            _book(id=4, tags=["Non"]),
            _book(id=5, tags=[]),
        ]
        tree = _build_tag_tree(books)
        fic = tree["children"]["Fic"]
        self.assertEqual(fic["_count"], 1)  # book 3 directly on Fic
        self.assertEqual(_rolled_counts(books)["Fic"], 3)
        self.assertEqual(fic["children"]["Fantasy"]["_count"], 1)
        self.assertEqual(
            fic["children"]["Fantasy"]["children"]["Grimdark"]["_count"], 1
        )
        self.assertEqual(_rolled_counts(books)["Non"], 1)

    def test_blank_tags_ignored(self):
        tree = _build_tag_tree([_book(tags=["  ", ""])])
        self.assertEqual(tree["children"], {})


# --------------------------------------------------------------------------- #
# series
# --------------------------------------------------------------------------- #
class TestSeriesIndex(unittest.TestCase):
    def test_groups_and_sorts(self):
        books = [
            _book(id=1, series="Hainish Cycle", series_index=2.0),
            _book(id=2, series="Hainish Cycle", series_index=1.0),
            _book(id=3, series="Ankh-Morpork", series_index=1.0),
            _book(id=4, series=None),
        ]
        entries = _build_series_index(books)
        self.assertEqual([e.name for e in entries], ["Ankh-Morpork", "Hainish Cycle"])
        hainish = entries[1]
        self.assertEqual([b.id for b in hainish.books], [2, 1])
        self.assertEqual(hainish.count, 2)

    def test_index_range_contiguous(self):
        entry = SeriesEntry(
            name="S",
            books=[_book(id=i, series="S", series_index=float(i)) for i in (1, 2, 3)],
        )
        self.assertEqual(entry.index_range, "#1 → #3")

    def test_index_range_with_gaps(self):
        entry = SeriesEntry(
            name="S",
            books=[_book(id=i, series="S", series_index=float(i)) for i in (1, 4)],
        )
        self.assertEqual(entry.index_range, "#1 → #4 (incomplete)")

    def test_index_range_single(self):
        entry = SeriesEntry(name="S", books=[_book(id=1, series="S", series_index=1.5)])
        self.assertEqual(entry.index_range, "#1.5")


# --------------------------------------------------------------------------- #
# insights
# --------------------------------------------------------------------------- #
class TestSummarize(unittest.TestCase):
    def test_counts_and_audit(self):
        books = [
            _book(
                id=1,
                authors=["A1"],
                tags=["Fic"],
                formats=["EPUB"],
                rating=8,
                series="S",
                identifiers={"isbn": "x"},
            ),
            _book(id=2, authors=["A2"], tags=[], formats=[], rating=6),
            _book(id=3, authors=["A1"], tags=["Fic"], formats=["PDF"]),
        ]
        s = summarize(books)
        self.assertEqual(s.total_books, 3)
        self.assertEqual(s.total_authors, 2)
        self.assertEqual(s.total_series, 1)
        self.assertEqual(s.total_tags, 1)
        self.assertEqual(s.total_identifiers, 1)
        self.assertEqual(s.top_tags[0], ("Fic", 2))
        self.assertEqual(s.top_authors[0], ("A1", 2))
        self.assertEqual([b.id for b in s.no_formats], [2])
        self.assertEqual([b.id for b in s.no_tags], [2])
        self.assertEqual([b.id for b in s.no_identifiers], [2, 3])
        self.assertEqual(s.rated_count, 2)
        self.assertEqual(s.avg_rating_x10, 7)

    def test_average_keeps_half_star_precision(self):
        # Regression (Phase 15): `//` averaged [8, 7] to 7 (a 3.5-star display);
        # true average is 7.5 → 3.75 stars.
        books = [_book(id=1, rating=8), _book(id=2, rating=7)]
        self.assertEqual(summarize(books).avg_rating_x10, 7.5)


# --------------------------------------------------------------------------- #
# codex helpers
# --------------------------------------------------------------------------- #
class TestCleanHtml(unittest.TestCase):
    def test_strips_tags_and_entities(self):
        raw = "<p>It&rsquo;s <b>good</b> &amp; short.</p>"
        self.assertEqual(_clean_html(raw), "It’s good & short.")

    def test_collapses_whitespace(self):
        raw = "a   \t b"
        self.assertEqual(_clean_html(raw), "a b")

    def test_paragraph_breaks_survive(self):
        # Regression (Phase 15): block boundaries were stripped to spaces,
        # flattening multi-paragraph comments into one wall of text.
        raw = "<p>First para.</p><p>Second para.</p>tail<br/>more"
        self.assertEqual(_clean_html(raw), "First para.\n\nSecond para.\ntail\nmore")


class TestIdentifierLinks(unittest.TestCase):
    def test_formats_produce_urls(self):
        for key, (label, fmt) in _IDENTIFIER_LINKS.items():
            with self.subTest(key=key):
                url = fmt.format("VALUE")
                self.assertIn("VALUE", url)
                self.assertTrue(label)


class TestEnumColorFor(unittest.TestCase):
    """enum_colors resolves positionally, Calibre's real shape, or None.

    Regression (found on the 1.8.4 smoke run): the old code assumed a
    value->color dict and raised AttributeError on every real enum column
    (colors is a list aligned with enum_values), crashing the Codex on
    any book carrying a value in that column.
    """

    def _col(self, display):
        return CustomColumn(
            id=3,
            label="status",
            name="Status",
            datatype="enumeration",
            is_multiple=False,
            display=display,
        )

    def test_positional_resolution(self):
        col = self._col(
            {
                "enum_values": ["To Read", "Reading", "Read"],
                "enum_colors": ["red", "gold", "#00ff00"],
            }
        )
        self.assertEqual(CodexView._enum_color_for(col, "To Read"), "#ff0000")
        self.assertEqual(CodexView._enum_color_for(col, "Reading"), "#ffd700")
        self.assertEqual(CodexView._enum_color_for(col, "Read"), "#00ff00")

    def test_value_not_in_values(self):
        col = self._col({"enum_values": ["a"], "enum_colors": ["red"]})
        self.assertIsNone(CodexView._enum_color_for(col, "b"))

    def test_empty_missing_or_odd_colors(self):
        self.assertIsNone(
            CodexView._enum_color_for(self._col({"enum_values": ["a"]}), "a")
        )
        self.assertIsNone(
            CodexView._enum_color_for(
                self._col({"enum_values": ["a"], "enum_colors": []}), "a"
            )
        )
        self.assertIsNone(CodexView._enum_color_for(self._col({}), "a"))
        # A dict shape is not Calibre's; treated as no colors, not a crash.
        self.assertIsNone(
            CodexView._enum_color_for(
                self._col({"enum_values": ["a"], "enum_colors": {"a": "#ff0000"}}),
                "a",
            )
        )

    def test_unknown_name_and_non_string(self):
        col = self._col({"enum_values": ["a", "b"], "enum_colors": ["chartreuse2", 5]})
        self.assertIsNone(CodexView._enum_color_for(col, "a"))
        self.assertIsNone(CodexView._enum_color_for(col, "b"))

    def test_hex_passthrough(self):
        col = self._col({"enum_values": ["a"], "enum_colors": ["#aB12cD"]})
        self.assertEqual(CodexView._enum_color_for(col, "a"), "#aB12cD")

    def test_enum_color_hex_names(self):
        self.assertEqual(_enum_color_hex("GREY"), "#808080")
        self.assertEqual(_enum_color_hex(" grey "), "#808080")
        self.assertIsNone(_enum_color_hex("not-a-color"))
        self.assertIsNone(_enum_color_hex(None))


class _FormatMapDB:
    """Stands in for the CalibreDB singleton with a fixed format map."""

    def __init__(self, fmt_map):
        self._fmt_map = fmt_map

    def get_formats(self, book_id):
        return self._fmt_map


class TestFindFormatFile(unittest.TestCase):
    """The format resolver against a temp library tree, db and root stubbed.

    Regression (final audit 2026-09-13): the scan loop used to rebind the
    `fmt` parameter, so the retry gate tested the leaked last scanned
    format and every book whose catalogued formats resolved to no file on
    disk recursed until RecursionError on each Read-button click.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        root_patcher = mock.patch(
            "hermitage.codex.library_root", return_value=self.root
        )
        root_patcher.start()
        self.addCleanup(root_patcher.stop)
        db_patcher = mock.patch(
            "hermitage.codex.get_cquarry_db", return_value=_FormatMapDB({})
        )
        db_patcher.start()
        self.addCleanup(db_patcher.stop)

    def _book(self, formats):
        return Book(
            id=1,
            title="t",
            sort="t",
            authors=[],
            path="A/T (1)",
            has_cover=0,
            formats=formats,
        )

    def _fmt_map(self, fmt_map):
        patcher = mock.patch(
            "hermitage.codex.get_cquarry_db", return_value=_FormatMapDB(fmt_map)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _make_dir(self):
        d = self.root / "A" / "T (1)"
        d.mkdir(parents=True)
        return d

    def test_fileless_book_returns_none(self):
        # Catalogued format, nothing on disk, empty format map: None, and
        # no recursion (the bug burned ~1000 stack levels per Read click).
        self.assertIsNone(_find_format_file(self._book(["EPUB"])))

    def test_requested_format_falls_through_then_none(self):
        # An explicitly requested format that resolves to nothing falls
        # through to the priority order once, then returns None.
        self.assertIsNone(_find_format_file(self._book(["EPUB"]), "PDF"))

    def test_glob_fallback_finds_file(self):
        d = self._make_dir()
        (d / "novel.epub").write_bytes(b"x")
        self.assertEqual(_find_format_file(self._book(["EPUB"])), d / "novel.epub")

    def test_catalog_path_wins(self):
        d = self._make_dir()
        real = d / "Novel.epub"
        real.write_bytes(b"x")
        self._fmt_map({"EPUB": {"path": str(real)}})
        self.assertEqual(_find_format_file(self._book(["EPUB"])), real)


# format ordering (codex's multi-format selector)
class TestOrderedFormats(unittest.TestCase):
    def _book(self, formats):
        return Book(
            id=1,
            title="t",
            sort="t",
            authors=[],
            path="x",
            has_cover=0,
            formats=formats,
        )

    def test_priority_order_with_unranked_tail(self):
        ordered = _ordered_formats(self._book(["CBZ", "PDF", "EPUB"]))
        self.assertEqual(ordered[0], "EPUB")
        self.assertIn("PDF", ordered[1:2])
        self.assertEqual(ordered[-1], "CBZ")  # unranked formats go last

    def test_single_format_stays_alone(self):
        self.assertEqual(_ordered_formats(self._book(["EPUB"])), ["EPUB"])


if __name__ == "__main__":
    unittest.main()
