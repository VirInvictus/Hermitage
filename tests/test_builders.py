"""Tests for the pure aggregation helpers behind the GTK browse surfaces.

Importing genres/series/insights/codex pulls in Gtk, which is safe headless —
no widget is ever instantiated here; only the module-level builders and
dataclasses are exercised.
"""

import unittest

from hermitage.codex import _clean_html, _IDENTIFIER_LINKS
from hermitage.database import Book
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
        self.assertEqual(
            _clean_html(raw), "First para.\n\nSecond para.\ntail\nmore"
        )


class TestIdentifierLinks(unittest.TestCase):
    def test_formats_produce_urls(self):
        for key, (label, fmt) in _IDENTIFIER_LINKS.items():
            with self.subTest(key=key):
                url = fmt.format("VALUE")
                self.assertIn("VALUE", url)
                self.assertTrue(label)


if __name__ == "__main__":
    unittest.main()
