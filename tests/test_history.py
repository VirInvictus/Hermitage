"""Tests for the local reading-history database.

DB_PATH is redirected to a temp directory and the module's init/cache state
reset per test — the real ~/.local/share/hermitage/history.db is untouched.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hermitage import history


class _HistoryBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="hermitage-test-")
        self._saved = (history.DB_PATH, history._inited, history._opened_cache)
        history.DB_PATH = Path(self._tmp.name) / "history.db"
        history._inited = False
        history._opened_cache = None

    def tearDown(self):
        history.DB_PATH, history._inited, history._opened_cache = self._saved
        self._tmp.cleanup()

    @staticmethod
    def _insert(book_id: int, ts: str):
        """Insert an open event with an explicit timestamp."""
        conn = history._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO opens(book_id, opened_at) VALUES (?, ?)",
                (book_id, ts),
            )
            conn.commit()
        finally:
            conn.close()


class TestRecordAndRead(_HistoryBase):
    def test_record_open_marks_book(self):
        self.assertFalse(history.is_opened(7))
        history.record_open(7)
        self.assertTrue(history.is_opened(7))
        self.assertIn(7, history.opened_book_ids())

    def test_cache_updates_after_record(self):
        history.opened_book_ids()  # prime the cache
        history.record_open(3)
        self.assertTrue(history.is_opened(3))

    def test_last_opened_for(self):
        self.assertIsNone(history.last_opened_for(1))
        ts = history.record_open(1)
        got = history.last_opened_for(1)
        self.assertEqual(got, datetime.fromisoformat(ts))

    def test_recently_read_orders_by_last_open(self):
        self._insert(1, "2026-07-01T10:00:00+00:00")
        self._insert(2, "2026-07-02T10:00:00+00:00")
        self._insert(3, "2026-07-03T10:00:00+00:00")
        self._insert(1, "2026-07-04T10:00:00+00:00")  # re-open bumps book 1
        self.assertEqual(history.recently_read(), [1, 3, 2])
        self.assertEqual(history.recently_read(limit=2), [1, 3])


class TestHumanize(unittest.TestCase):
    def test_buckets(self):
        now = datetime.now(timezone.utc)
        cases = [
            (timedelta(seconds=10), "just now"),
            (timedelta(minutes=5), "5 minutes ago"),
            (timedelta(hours=1), "1 hour ago"),
            (timedelta(days=3), "3 days ago"),
            (timedelta(days=14), "2 weeks ago"),
            (timedelta(days=90), "3 months ago"),
            (timedelta(days=800), "2 years ago"),
        ]
        for delta, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(history.humanize(now - delta), expected)

    def test_naive_timestamp_assumed_utc(self):
        naive = datetime.now(timezone.utc).replace(tzinfo=None)
        self.assertEqual(history.humanize(naive), "just now")


if __name__ == "__main__":
    unittest.main()
