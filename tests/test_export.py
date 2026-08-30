"""Tests for JSON / CSV library export."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from hermitage.database import Book
from hermitage.export import detect_format, export_books


def _books():
    return [
        Book(
            id=1,
            title="Good Omens",
            sort="Good Omens",
            authors=["Terry Pratchett", "Neil Gaiman"],
            path="Terry Pratchett/Good Omens (1)",
            has_cover=True,
            tags=["Fic.Fantasy", "Humour"],
            rating=8,
            formats=["EPUB", "PDF"],
            comment="<p>Funny.</p>",
            identifiers={"isbn": "9780060853983"},
        ),
        Book(
            id=2,
            title="The Dispossessed",
            sort="Dispossessed, The",
            authors=["Ursula K. Le Guin"],
            path="Ursula K. Le Guin/The Dispossessed (2)",
            has_cover=False,
            series="Hainish Cycle",
            series_index=2.0,
        ),
    ]


class TestDetectFormat(unittest.TestCase):
    def test_extensions(self):
        self.assertEqual(detect_format(Path("x.csv")), "csv")
        self.assertEqual(detect_format(Path("x.CSV")), "csv")
        self.assertEqual(detect_format(Path("x.json")), "json")
        self.assertEqual(detect_format(Path("x.weird")), "json")


class TestExport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="hermitage-test-")
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_json_round_trip(self):
        out = self.dir / "lib.json"
        count = export_books(_books(), out)
        self.assertEqual(count, 2)
        data = json.loads(out.read_text())
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["authors"], ["Terry Pratchett", "Neil Gaiman"])
        self.assertEqual(data[0]["identifiers"], {"isbn": "9780060853983"})
        self.assertEqual(data[1]["series"], "Hainish Cycle")

    def test_csv_rows(self):
        out = self.dir / "lib.csv"
        export_books(_books(), out)
        with out.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["authors"], "Terry Pratchett; Neil Gaiman")
        self.assertEqual(rows[0]["tags"], "Fic.Fantasy; Humour")
        self.assertEqual(json.loads(rows[0]["identifiers"]), {"isbn": "9780060853983"})
        self.assertEqual(rows[1]["rating"], "")
        self.assertEqual(rows[1]["identifiers"], "")

    def test_explicit_format_overrides_extension(self):
        out = self.dir / "lib.json"
        export_books(_books(), out, fmt="csv")
        with out.open(newline="") as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), 2)

    def test_pages_custom_and_author_columns_export(self):
        # Regression (Phase 15): pages, custom, author_sorts and author_links
        # existed on Book but were silently dropped by both export formats.
        books = _books()
        books[0].pages = 288
        books[0].custom = {"reading_status": "Read"}
        books[0].author_sorts = ["Pratchett, Terry", "Gaiman, Neil"]
        books[0].author_links = ["", "https://neilgaiman.com"]

        jout = self.dir / "lib.json"
        export_books(books, jout)
        data = json.loads(jout.read_text())
        self.assertEqual(data[0]["pages"], 288)
        self.assertEqual(data[0]["custom"], {"reading_status": "Read"})
        self.assertEqual(data[0]["author_sorts"], ["Pratchett, Terry", "Gaiman, Neil"])
        self.assertEqual(data[1]["pages"], None)
        self.assertEqual(data[1]["custom"], {})

        cout = self.dir / "lib.csv"
        export_books(books, cout)
        with cout.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["pages"], "288")
        self.assertEqual(json.loads(rows[0]["custom"]), {"reading_status": "Read"})
        self.assertEqual(rows[0]["author_sorts"], "Pratchett, Terry; Gaiman, Neil")
        self.assertEqual(rows[1]["pages"], "")
        self.assertEqual(rows[1]["custom"], "")
        self.assertEqual(rows[1]["author_sorts"], "")

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            export_books(_books(), self.dir / "x.json", fmt="xml")


if __name__ == "__main__":
    unittest.main()
