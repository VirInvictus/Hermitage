"""Local reading-history database (read-only with respect to Calibre).

Tracks every time the user clicks "Read" on a book. Stored at
``~/.local/share/hermitage/history.db`` so it survives Calibre library moves
and is never written to Calibre's own ``metadata.db``.

Schema is intentionally tiny — one event-log table — so future stats
(books-read-this-week, streaks, etc.) are derivable without a migration.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "hermitage" / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS opens (
    book_id   INTEGER NOT NULL,
    opened_at TEXT    NOT NULL,
    PRIMARY KEY (book_id, opened_at)
);
CREATE INDEX IF NOT EXISTS idx_opens_book ON opens(book_id);
CREATE INDEX IF NOT EXISTS idx_opens_when ON opens(opened_at);
"""

_lock = threading.Lock()
_inited = False

# In-memory cache of book ids with at least one open event. Keeps the
# grid bind hot path free of SQLite — populated lazily and updated on every
# successful record_open().
_opened_cache: set[int] | None = None


def _connect() -> sqlite3.Connection:
    global _inited
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    if not _inited:
        conn.executescript(_SCHEMA)
        conn.commit()
        _inited = True
    return conn


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def record_open(book_id: int) -> str:
    """Append an open event for *book_id*. Returns the timestamp written."""
    global _opened_cache
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO opens(book_id, opened_at) VALUES (?, ?)",
                (book_id, ts),
            )
            conn.commit()
        finally:
            conn.close()
        if _opened_cache is not None:
            _opened_cache.add(book_id)
    return ts


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def opened_book_ids() -> set[int]:
    """Return every book id that has at least one open event (cached)."""
    global _opened_cache
    with _lock:
        if _opened_cache is not None:
            return _opened_cache
        conn = _connect()
        try:
            rows = conn.execute("SELECT DISTINCT book_id FROM opens").fetchall()
        finally:
            conn.close()
        _opened_cache = {r["book_id"] for r in rows}
        return _opened_cache


def is_opened(book_id: int) -> bool:
    """O(1) check that *book_id* has been opened at least once."""
    return book_id in opened_book_ids()


def last_opened_for(book_id: int) -> datetime | None:
    """Return the most recent open timestamp for *book_id*, or None."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT MAX(opened_at) AS ts FROM opens WHERE book_id = ?",
                (book_id,),
            ).fetchone()
        finally:
            conn.close()
    if not row or not row["ts"]:
        return None
    try:
        return datetime.fromisoformat(row["ts"])
    except ValueError:
        return None


def recently_read(limit: int = 50) -> list[int]:
    """Return book ids ordered by most recent open, capped at *limit*."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT book_id, MAX(opened_at) AS last "
                "FROM opens GROUP BY book_id "
                "ORDER BY last DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
    return [r["book_id"] for r in rows]


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def humanize(ts: datetime) -> str:
    """Render *ts* as a short relative phrase ('3 days ago', 'just now')."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    if days < 365:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"
