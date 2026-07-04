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
from hermitage.database import Book, load_library, load_virtual_libraries, library_root

_SCHEMA = """
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT,
    sort TEXT,
    path TEXT,
    has_cover INTEGER DEFAULT 0,
    series_index REAL DEFAULT 1.0,
    pubdate TEXT,
    timestamp TEXT
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
CREATE TABLE identifiers (
    id INTEGER PRIMARY KEY, book INTEGER, type TEXT, val TEXT
);
CREATE TABLE preferences (id INTEGER PRIMARY KEY, key TEXT, val TEXT);
"""


def _reset_module_state():
    database._library_root_cache = None
    database._cleanup_snapshot()
    database._snapshot_notified = False


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
        self.assertEqual(b1.comment, "<p>Funny.</p>")
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

    def test_library_root(self):
        load_library()
        self.assertEqual(library_root(), self.root)


class TestVirtualLibraries(_FixtureBase):
    def test_load(self):
        self.assertEqual(load_virtual_libraries(), {"Fantasy": 'tags:"Fic.Fantasy"'})


class TestLockedFallback(_FixtureBase):
    def test_snapshot_when_locked(self):
        # An EXCLUSIVE transaction makes even mode=ro reads fail with
        # "database is locked" — load_library must fall back to a snapshot.
        locker = sqlite3.connect(self.db_path)
        locker.execute("BEGIN EXCLUSIVE")
        try:
            books = load_library()
            self.assertEqual(len(books), 2)
            self.assertIsNotNone(database._snapshot_path)
            snapshot = database._snapshot_path
            self.assertTrue(Path(snapshot).is_file())
        finally:
            locker.rollback()
            locker.close()
        database._cleanup_snapshot()
        self.assertFalse(Path(snapshot).exists())


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
        self.assertIsNone(b.cover_path)


if __name__ == "__main__":
    unittest.main()
