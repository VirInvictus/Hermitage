"""Tests for the read-only Calibre database layer.

A minimal metadata.db is assembled in a temp directory with the handful of
tables Hermitage's joined query touches, then pointed at via HERMITAGE_DB.
Module-level caches (library root, snapshot state) are reset around every
test so cases stay independent.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from hermitage import database
from hermitage.database import (
    Book,
    get_comment_for,
    library_root,
    load_library,
    load_virtual_libraries,
)

_SCHEMA = """
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT,
    sort TEXT,
    author_sort TEXT,
    path TEXT,
    has_cover INTEGER DEFAULT 0,
    series_index REAL DEFAULT 1.0,
    pubdate TEXT,
    timestamp TEXT,
    last_modified TEXT
);
CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE books_authors_link (
    id INTEGER PRIMARY KEY, book INTEGER, author INTEGER
);
CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE books_series_link (
    id INTEGER PRIMARY KEY, book INTEGER, series INTEGER
);
CREATE TABLE ratings (id INTEGER PRIMARY KEY, rating INTEGER);
CREATE TABLE books_ratings_link (
    id INTEGER PRIMARY KEY, book INTEGER, rating INTEGER
);
CREATE TABLE comments (id INTEGER PRIMARY KEY, book INTEGER, text TEXT);
CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE books_tags_link (
    id INTEGER PRIMARY KEY, book INTEGER, tag INTEGER
);
CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER, format TEXT);
CREATE TABLE publishers (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE books_publishers_link (id INTEGER PRIMARY KEY, book INTEGER, publisher INTEGER);
CREATE TABLE languages (id INTEGER PRIMARY KEY, lang_code TEXT);
CREATE TABLE books_languages_link (id INTEGER PRIMARY KEY, book INTEGER, lang_code INTEGER);
CREATE TABLE identifiers (
    id INTEGER PRIMARY KEY, book INTEGER, type TEXT, val TEXT
);
CREATE TABLE preferences (id INTEGER PRIMARY KEY, key TEXT, val TEXT);
CREATE TABLE custom_columns (
    id INTEGER PRIMARY KEY, label TEXT, name TEXT, datatype TEXT, is_multiple INTEGER
);
-- col 1 (status): normalized enumeration — value table + link table
CREATE TABLE custom_column_1 (id INTEGER PRIMARY KEY, value TEXT, link TEXT);
CREATE TABLE books_custom_column_1_link (
    id INTEGER PRIMARY KEY, book INTEGER, value INTEGER
);
-- col 2 (translators): normalized multi-valued text
CREATE TABLE custom_column_2 (id INTEGER PRIMARY KEY, value TEXT, link TEXT);
CREATE TABLE books_custom_column_2_link (
    id INTEGER PRIMARY KEY, book INTEGER, value INTEGER
);
-- col 3 (date_read): stored directly — a `book` column, no link table
CREATE TABLE custom_column_3 (id INTEGER PRIMARY KEY, book INTEGER, value TEXT);
CREATE TABLE annotations (
    id INTEGER PRIMARY KEY, book INTEGER, format TEXT,
    user_type TEXT, user TEXT, timestamp TEXT,
    annot_id TEXT, annot_type TEXT, annot_data TEXT
);
CREATE TABLE last_read_positions (
    id INTEGER PRIMARY KEY,
    book INTEGER NOT NULL,
    format TEXT NOT NULL COLLATE NOCASE,
    user TEXT NOT NULL,
    device TEXT NOT NULL,
    cfi TEXT NOT NULL,
    epoch REAL NOT NULL,
    pos_frac REAL NOT NULL DEFAULT 0,
    UNIQUE(user, device, book, format)
);
CREATE TABLE books_pages_link (
    book INTEGER NOT NULL, pages INTEGER, algorithm TEXT, format TEXT,
    format_size INTEGER, timestamp TEXT, needs_scan BOOLEAN DEFAULT 0 NOT NULL
);
"""


def _reset_module_state():
    database._library_root_cache = None
    database._custom_columns_cache = None
    database._cquarry_db_instance = None


class _FixtureBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="hermitage-test-")
        self.root = Path(self._tmp.name)
        self.db_path = self.root / "metadata.db"

        conn = sqlite3.connect(self.db_path)
        conn.executescript(_SCHEMA)
        self._populate(conn)
        conn.commit()
        conn.close()

        self._old_env = os.environ.get("HERMITAGE_DB")
        os.environ["HERMITAGE_DB"] = str(self.db_path)
        _reset_module_state()

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("HERMITAGE_DB", None)
        else:
            os.environ["HERMITAGE_DB"] = self._old_env
        _reset_module_state()
        self._tmp.cleanup()

    def _populate(self, conn: sqlite3.Connection):
        conn.executemany(
            "INSERT INTO books(id, title, sort, path, has_cover, series_index,"
            " pubdate, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    1,
                    "Good Omens",
                    "Good Omens",
                    "Terry Pratchett/Good Omens (1)",
                    1,
                    1.0,
                    "1990-05-01 00:00:00+00:00",
                    "2026-01-01 00:00:00+00:00",
                ),
                (
                    2,
                    "The Dispossessed",
                    "Dispossessed, The",
                    "Ursula K. Le Guin/The Dispossessed (2)",
                    0,
                    2.0,
                    None,
                    None,
                ),
            ],
        )
        # Book 1 has two authors. Insert the AUTHOR rows out of order but the
        # LINK rows in reading order — load_library must follow bal.id, not
        # alphabetical GROUP_CONCAT order. One name carries Calibre's
        # pipe-escaped comma.
        conn.executemany(
            "INSERT INTO authors(id, name) VALUES (?,?)",
            [
                (1, "Terry Pratchett"),
                (2, "Gaiman| Neil"),
                (3, "Ursula K. Le Guin"),
            ],
        )
        # Native page count for book 1 (cquarry's books_pages_link reader).
        conn.execute(
            "INSERT INTO books_pages_link (book, pages, algorithm) VALUES (1, 288, 'demo')"
        )
        conn.executemany(
            "INSERT INTO books_authors_link(id, book, author) VALUES (?,?,?)",
            [(1, 1, 1), (2, 1, 2), (3, 2, 3)],
        )
        conn.execute("INSERT INTO series(id, name) VALUES (1, 'Hainish Cycle')")
        conn.execute("INSERT INTO books_series_link(book, series) VALUES (2, 1)")
        conn.execute("INSERT INTO ratings(id, rating) VALUES (1, 8)")
        conn.execute("INSERT INTO books_ratings_link(book, rating) VALUES (1, 1)")
        conn.execute("INSERT INTO comments(book, text) VALUES (1, '<p>Funny.</p>')")
        conn.executemany(
            "INSERT INTO tags(id, name) VALUES (?,?)",
            [(1, "Fic.Fantasy"), (2, "Humour")],
        )
        conn.executemany(
            "INSERT INTO books_tags_link(book, tag) VALUES (?,?)",
            [(1, 1), (1, 2)],
        )
        conn.executemany(
            "INSERT INTO data(book, format) VALUES (?,?)",
            [(1, "EPUB"), (1, "PDF"), (2, "EPUB")],
        )
        conn.execute(
            "INSERT INTO identifiers(book, type, val) VALUES (1, 'isbn', '9780060853983')"
        )
        conn.execute(
            "INSERT INTO preferences(key, val) VALUES ('virtual_libraries', ?)",
            (json.dumps({"Fantasy": 'tags:"Fic.Fantasy"'}),),
        )
        conn.execute(
            "INSERT INTO preferences(key, val) VALUES ('saved_searches', ?)",
            (json.dumps({"Funny": "tags:Humour"}),),
        )
        conn.execute(
            "INSERT INTO preferences(key, val) VALUES ('virt_libs_hidden', ?)",
            (json.dumps(["Fantasy"]),),
        )
        conn.execute(
            "INSERT INTO preferences(key, val) VALUES ('virt_libs_order', ?)",
            (json.dumps({"Fantasy": 0}),),
        )
        conn.execute(
            "INSERT INTO annotations VALUES"
            " (1, 1, 'EPUB', 'local', 'reader', '2026-01-02T00:00:00',"
            "  'a1', 'highlight', '{\"text\": \"wise\"}')"
        )
        conn.execute(
            "INSERT INTO last_read_positions (book, format, user, device, cfi, epoch, pos_frac) VALUES"
            " (1, 'EPUB', 'reader', 'kobo', 'epubcfi(/6/4)', 100, 0.42),"
            " (1, 'EPUB', 'reader', 'phone', 'epubcfi(/6/9)', 200, 0.90)"
        )
        # Custom columns — three shapes: a single-valued normalized enumeration,
        # a multi-valued normalized text column, and a directly-stored datetime.
        # Only book 1 carries values; book 2 must come back with custom == {}.
        conn.executemany(
            "INSERT INTO custom_columns(id, label, name, datatype, is_multiple)"
            " VALUES (?,?,?,?,?)",
            [
                (1, "status", "Status", "enumeration", 0),
                (2, "translators", "Translators", "text", 1),
                (3, "date_read", "Date Read", "datetime", 0),
            ],
        )
        conn.execute(
            "INSERT INTO custom_column_1(id, value, link) VALUES (1, 'Read', '')"
        )
        conn.execute(
            "INSERT INTO books_custom_column_1_link(book, value) VALUES (1, 1)"
        )
        conn.executemany(
            "INSERT INTO custom_column_2(id, value, link) VALUES (?,?,?)",
            [(1, "Alpha", ""), (2, "Beta", "")],
        )
        conn.executemany(
            "INSERT INTO books_custom_column_2_link(book, value) VALUES (?,?)",
            [(1, 1), (1, 2)],
        )
        conn.execute(
            "INSERT INTO custom_column_3(book, value) VALUES (1, '2026-02-14')"
        )


class TestLoadLibrary(_FixtureBase):
    def test_loads_every_book_sorted(self):
        books = load_library()
        self.assertEqual([b.id for b in books], [2, 1])  # sort COLLATE NOCASE

    def test_author_order_and_pipe_commas(self):
        by_id = {b.id: b for b in load_library()}
        # Order follows the link table (bal.id), not the author names; the
        # pipe in "Gaiman| Neil" is restored to a comma.
        self.assertEqual(by_id[1].authors, ["Terry Pratchett", "Gaiman, Neil"])
        self.assertEqual(by_id[2].authors, ["Ursula K. Le Guin"])

    def test_joined_fields(self):
        by_id = {b.id: b for b in load_library()}
        b1, b2 = by_id[1], by_id[2]
        self.assertEqual(sorted(b1.tags), ["Fic.Fantasy", "Humour"])
        self.assertEqual(sorted(b1.formats), ["EPUB", "PDF"])
        self.assertEqual(b1.rating, 8)
        # Comments are JIT-loaded (Phase 15): startup carries None; the
        # per-book fetch fills it in.
        self.assertIsNone(b1.comment)
        self.assertEqual(b1.identifiers, {"isbn": "9780060853983"})
        self.assertEqual(b2.series, "Hainish Cycle")
        self.assertEqual(b2.series_index, 2.0)
        self.assertEqual(b2.tags, [])
        self.assertEqual(b2.identifiers, {})

    def test_cover_path(self):
        by_id = {b.id: b for b in load_library()}
        self.assertEqual(
            by_id[1].cover_path,
            self.root / "Terry Pratchett/Good Omens (1)" / "cover.jpg",
        )
        self.assertIsNone(by_id[2].cover_path)  # has_cover = 0

    def test_pages_from_native_table(self):
        # Page counts ride on the Book from cquarry's books_pages_link reader.
        by_id = {b.id: b for b in load_library()}
        self.assertEqual(by_id[1].pages, 288)
        self.assertIsNone(by_id[2].pages)  # no native row for this book

    def test_library_root(self):
        load_library()
        self.assertEqual(library_root(), self.root)


class TestJitComments(_FixtureBase):
    """Phase 15: comments fetch on demand, one book at a time."""

    def test_get_comment_for_returns_the_row(self):
        self.assertEqual(get_comment_for(1), "<p>Funny.</p>")

    def test_get_comment_for_none_when_no_row(self):
        self.assertIsNone(get_comment_for(2))  # book with no comment row
        self.assertIsNone(get_comment_for(999))  # unknown book


class TestVirtualLibraries(_FixtureBase):
    def test_load(self):
        self.assertEqual(load_virtual_libraries(), {"Fantasy": 'tags:"Fic.Fantasy"'})


class TestPathResolution(unittest.TestCase):
    def test_env_var_missing_file_raises(self):
        old = os.environ.get("HERMITAGE_DB")
        os.environ["HERMITAGE_DB"] = "/nonexistent/metadata.db"
        try:
            with self.assertRaises(FileNotFoundError):
                database._resolve_library_path()
        finally:
            if old is None:
                os.environ.pop("HERMITAGE_DB", None)
            else:
                os.environ["HERMITAGE_DB"] = old


class TestBookDataclass(unittest.TestCase):
    def test_defaults(self):
        b = Book(id=1, title="T", sort="T", authors=[], path="p", has_cover=False)
        self.assertEqual(b.tags, [])
        self.assertEqual(b.formats, [])
        self.assertEqual(b.identifiers, {})
        self.assertEqual(b.custom, {})
        self.assertIsNone(b.cover_path)


class TestCustomColumns(_FixtureBase):
    def test_schema_loaded(self):
        cols = {c.label: c for c in database.load_custom_columns()}
        self.assertEqual(set(cols), {"status", "translators", "date_read"})
        self.assertEqual(cols["status"].name, "Status")
        self.assertFalse(cols["status"].is_multiple)
        self.assertTrue(cols["translators"].is_multiple)
        self.assertEqual(cols["date_read"].datatype, "datetime")

    def test_values_populated_per_book(self):
        by_id = {b.id: b for b in load_library()}
        b1 = by_id[1]
        # Single-valued normalized column → scalar; multi → list; direct storage.
        self.assertEqual(b1.custom["status"], "Read")
        self.assertEqual(b1.custom["translators"], ["Alpha", "Beta"])
        self.assertEqual(b1.custom["date_read"], "2026-02-14")
        # A book with no custom values comes back with an empty dict.
        self.assertEqual(by_id[2].custom, {})

    def test_schema_cache_warmed_by_load_library(self):
        load_library()
        # After a library load the schema is cached, so load_custom_columns()
        # returns it without reopening the DB.
        self.assertIsNotNone(database._custom_columns_cache)
        labels = {c.label for c in database.load_custom_columns()}
        self.assertEqual(labels, {"status", "translators", "date_read"})


class TestSavedSearchesAndUiState(_FixtureBase):
    """cquarry-backed saved searches and Calibre sidebar layout state."""

    def test_load_saved_searches(self):
        self.assertEqual(database.load_saved_searches(), {"Funny": "tags:Humour"})

    def test_load_vl_ui_state(self):
        state = database.load_vl_ui_state()
        self.assertEqual(state["hidden"], ["Fantasy"])
        self.assertEqual(state["order"], {"Fantasy": 0})

    def test_defaults_when_preferences_absent(self):
        # A library without the UI-state keys yields empty defaults.
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM preferences WHERE key LIKE 'virt_libs%'")
        conn.execute("DELETE FROM preferences WHERE key = 'saved_searches'")
        conn.commit()
        conn.close()
        database._cquarry_db_instance = None
        self.assertEqual(database.load_saved_searches(), {})
        self.assertEqual(database.load_vl_ui_state(), {"hidden": [], "order": {}})


class TestAnnotationsAndProgress(_FixtureBase):
    """Annotation extraction and reading-progress helpers."""

    def test_get_annotations_decodes_payload(self):
        notes = database.get_annotations(1)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["annot_data"], {"text": "wise"})
        self.assertEqual(database.get_annotations(2), [])

    def test_get_reading_progress(self):
        # phone carries the later epoch; the wrapper must pick it
        self.assertAlmostEqual(database.get_reading_progress(1), 0.90)
        self.assertIsNone(database.get_reading_progress(2))


if __name__ == "__main__":
    unittest.main()
