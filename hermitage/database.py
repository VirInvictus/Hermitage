"""Read-only interface to a Calibre metadata.db."""

from __future__ import annotations

import atexit
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Book:
    id: int
    title: str
    sort: str
    authors: list[str]
    path: str
    has_cover: bool
    series: str | None = None
    series_index: float = 1.0
    rating: int | None = None
    tags: list[str] = field(default_factory=list)
    comment: str | None = None
    formats: list[str] = field(default_factory=list)
    pubdate: str | None = None
    timestamp: str | None = None  # date added to Calibre
    identifiers: dict[str, str] = field(default_factory=dict)
    # User-defined Calibre custom columns, keyed by column label (e.g.
    # "reading_status"). Multi-valued text columns hold a list[str]; every
    # other datatype holds a single scalar (str/int/float). Only columns that
    # actually have a value for this book appear.
    custom: dict[str, str | list[str]] = field(default_factory=dict)

    @property
    def cover_path(self) -> Path | None:
        """Absolute path to the cover image, or None."""
        if not self.has_cover:
            return None
        return library_root() / self.path / "cover.jpg"


@dataclass(slots=True)
class CustomColumn:
    """Schema for one Calibre user-defined custom column."""

    id: int
    label: str  # search key, e.g. "reading_status" (used as #label: in queries)
    name: str  # display title, e.g. "Status"
    datatype: str  # text, enumeration, datetime, int, float, bool, comments, ...
    is_multiple: bool


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

_BOOKS_QUERY = """
SELECT
    b.id,
    b.title,
    COALESCE(b.sort, b.title)   AS sort,
    b.path,
    b.has_cover,
    b.series_index,
    b.pubdate,
    b.timestamp,
    (SELECT GROUP_CONCAT(name)
     FROM (SELECT a.name AS name
           FROM books_authors_link bal
           JOIN authors a ON a.id = bal.author
           WHERE bal.book = b.id
           ORDER BY bal.id))           AS authors,
    s.name                              AS series,
    r.rating                            AS rating,
    c.text                              AS comment,
    GROUP_CONCAT(DISTINCT t.name)       AS tags,
    GROUP_CONCAT(DISTINCT d.format)     AS formats
FROM books b
    LEFT JOIN books_series_link     bsl ON b.id = bsl.book
    LEFT JOIN series                s   ON bsl.series = s.id
    LEFT JOIN books_ratings_link    brl ON b.id = brl.book
    LEFT JOIN ratings               r   ON brl.rating = r.id
    LEFT JOIN comments              c   ON b.id = c.book
    LEFT JOIN books_tags_link       btl ON b.id = btl.book
    LEFT JOIN tags                  t   ON btl.tag = t.id
    LEFT JOIN data                  d   ON b.id = d.book
GROUP BY b.id
ORDER BY b.sort COLLATE NOCASE
"""

# ---------------------------------------------------------------------------
# Custom columns (ported from ../CalibreQuarry/src/cquarry/db.py)
# ---------------------------------------------------------------------------
#
# Calibre stores user-defined columns in a `custom_columns` schema table. The
# values live in one of two shapes, and cquarry taught us to detect which by
# whether a link table exists rather than by is_multiple: text/enumeration/
# series columns are normalized into a `custom_column_N` value table plus a
# `books_custom_column_N_link` join table (even single-valued enumerations),
# while int/float/bool/datetime/comments are stored directly in
# `custom_column_N` with its own `book` column.


def _fetch_custom_columns(conn: sqlite3.Connection) -> list[CustomColumn]:
    """Read every custom column's schema. Empty list if the table is absent."""
    try:
        rows = conn.execute(
            "SELECT id, label, name, datatype, is_multiple FROM custom_columns",
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        CustomColumn(
            id=r["id"],
            label=r["label"],
            name=r["name"],
            datatype=r["datatype"],
            is_multiple=bool(r["is_multiple"]),
        )
        for r in rows
    ]


def _fetch_custom_values(
    conn: sqlite3.Connection,
    col: CustomColumn,
) -> dict[int, str | list[str]]:
    """Load {book_id: value} for one custom column (multi-valued → list)."""
    cid = col.id
    link_table = f"books_custom_column_{cid}_link"
    has_link = bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (link_table,),
        ).fetchone()
    )

    try:
        if has_link:
            rows = conn.execute(
                f"SELECT l.book AS book, c.value AS value "
                f"FROM {link_table} l "
                f"JOIN custom_column_{cid} c ON c.id = l.value"
            ).fetchall()
            grouped: dict[int, list[str]] = {}
            for r in rows:
                grouped.setdefault(r["book"], []).append(r["value"])
            if col.is_multiple:
                return {k: [str(v) for v in vals] for k, vals in grouped.items()}
            # Single-valued normalized column (text, enumeration): one value.
            return {k: vals[0] for k, vals in grouped.items()}
        # Stored directly (int, float, bool, datetime, comments). Composite
        # columns are computed and have no value table — the SELECT errors and
        # we treat them as having no stored values.
        return {
            r["book"]: r["value"]
            for r in conn.execute(
                f"SELECT book, value FROM custom_column_{cid}"
            ).fetchall()
        }
    except sqlite3.OperationalError as exc:
        print(
            f"hermitage: could not read custom column '{col.label}': {exc}",
            file=sys.stderr,
        )
        return {}


# Schema cache — warmed by load_library(), reused by load_custom_columns() so
# the Codex doesn't reopen the DB just to learn the display names.
_custom_columns_cache: list[CustomColumn] | None = None


def load_custom_columns() -> list[CustomColumn]:
    """Return the custom-column schema (cached after the first library load)."""
    global _custom_columns_cache
    if _custom_columns_cache is not None:
        return _custom_columns_cache
    conn = _connect()
    try:
        _custom_columns_cache = _fetch_custom_columns(conn)
    finally:
        conn.close()
    return _custom_columns_cache


# ---------------------------------------------------------------------------
# Library root resolution
# ---------------------------------------------------------------------------

_library_root_cache: Path | None = None


def library_root() -> Path:
    """Return the Calibre library root directory."""
    global _library_root_cache
    if _library_root_cache is None:
        _library_root_cache = _resolve_library_path().parent
    return _library_root_cache


def _resolve_library_path() -> Path:
    """Locate metadata.db. Precedence: env var > config file > error."""
    # 1. Environment variable override
    env = os.environ.get("HERMITAGE_DB")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(f"HERMITAGE_DB points to missing file: {p}")

    # 2. Config file
    from hermitage.config import get as cfg_get

    lib_path = cfg_get("library_path", "")
    if lib_path:
        p = Path(lib_path).expanduser().resolve()
        db = p / "metadata.db"
        if db.is_file():
            return db
        # Config points somewhere but the file is missing
        raise FileNotFoundError(
            f"Configured library path has no metadata.db: {p}",
        )

    # 3. No config — app should show first-run wizard
    raise FileNotFoundError(
        "No library configured. Run Hermitage to set up your Calibre library.",
    )


# ---------------------------------------------------------------------------
# Connection (with locked-DB snapshot fallback)
# ---------------------------------------------------------------------------

# When Calibre holds a write lock on metadata.db, sqlite refuses even read-only
# opens. We mirror cquarry's approach: copy the .db plus its -wal/-shm siblings
# to a temp file and read from the snapshot. The snapshot path is cached so a
# second _connect() reuses it instead of copying twice, and atexit unlinks it.

_snapshot_path: str | None = None
_snapshot_notified: bool = False


def _open_ro(path: str) -> sqlite3.Connection:
    """Open *path* read-only via URI."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _make_snapshot(db_path: Path) -> str:
    """Copy metadata.db (+ -wal/-shm) to a tempfile; return its path."""
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="hermitage_")
    os.close(fd)
    shutil.copy2(db_path, tmp)
    for suffix in ("-wal", "-shm"):
        sibling = Path(str(db_path) + suffix)
        if sibling.exists():
            shutil.copy2(sibling, tmp + suffix)
    return tmp


def _cleanup_snapshot():
    """atexit hook — remove the snapshot files if any were created."""
    global _snapshot_path
    if not _snapshot_path:
        return
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(_snapshot_path + suffix)
        except OSError:
            pass
    _snapshot_path = None


atexit.register(_cleanup_snapshot)


def _connect() -> sqlite3.Connection:
    global _snapshot_path, _snapshot_notified

    # If we already fell back to a snapshot earlier in this process, reuse it.
    if _snapshot_path is not None:
        conn = _open_ro(_snapshot_path)
        conn.row_factory = sqlite3.Row
        return conn

    db_path = _resolve_library_path()
    conn = _open_ro(str(db_path))
    try:
        # Probe — sqlite defers the error until first query when the DB is locked.
        conn.execute("SELECT 1 FROM books LIMIT 1")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as exc:
        conn.close()
        if "locked" not in str(exc).lower():
            raise

    # Locked — snapshot it and reopen.
    if not _snapshot_notified:
        print(
            "hermitage: metadata.db is locked (Calibre is running) — "
            "reading from a snapshot copy.",
            file=sys.stderr,
        )
        _snapshot_notified = True
    _snapshot_path = _make_snapshot(db_path)
    conn = _open_ro(_snapshot_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_library() -> list[Book]:
    """Load every book from the Calibre database (read-only)."""
    global _library_root_cache, _custom_columns_cache
    _library_root_cache = _resolve_library_path().parent
    conn = _connect()
    try:
        rows = conn.execute(_BOOKS_QUERY).fetchall()
        # Bulk-load identifiers in a single query — avoids N+1 on the hot path.
        ident_rows = conn.execute("SELECT book, type, val FROM identifiers").fetchall()
        # Same idea for custom columns: one query per column, not per book.
        custom_cols = _fetch_custom_columns(conn)
        custom_values = {
            col.label: _fetch_custom_values(conn, col) for col in custom_cols
        }
    finally:
        conn.close()

    _custom_columns_cache = custom_cols

    by_book: dict[int, dict[str, str]] = {}
    for ir in ident_rows:
        by_book.setdefault(ir["book"], {})[ir["type"]] = ir["val"]

    def _custom_for(book_id: int) -> dict[str, str | list[str]]:
        return {
            col.label: custom_values[col.label][book_id]
            for col in custom_cols
            if book_id in custom_values[col.label]
        }

    books: list[Book] = []
    for r in rows:
        books.append(
            Book(
                id=r["id"],
                title=r["title"],
                sort=r["sort"],
                # Calibre stores commas inside author names as '|'
                # (e.g. "Le Guin| Ursula K."); restore them for display.
                authors=[a.strip().replace("|", ",") for a in r["authors"].split(",")]
                if r["authors"]
                else [],
                path=r["path"],
                has_cover=bool(r["has_cover"]),
                series=r["series"],
                series_index=r["series_index"],
                rating=r["rating"],
                tags=r["tags"].split(",") if r["tags"] else [],
                comment=r["comment"],
                formats=r["formats"].split(",") if r["formats"] else [],
                pubdate=r["pubdate"],
                timestamp=r["timestamp"],
                identifiers=by_book.get(r["id"], {}),
                custom=_custom_for(r["id"]),
            )
        )
    return books


# ---------------------------------------------------------------------------
# Virtual Libraries
# ---------------------------------------------------------------------------


def load_virtual_libraries() -> dict[str, str]:
    """Read virtual library definitions from the Calibre preferences table.

    Returns a dict mapping library name -> Calibre search expression.
    """
    import json

    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT val FROM preferences WHERE key='virtual_libraries'",
            ).fetchone()
        finally:
            conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return {}


from cquarry.db import CalibreDB

_cquarry_db_instance = None


def get_cquarry_db() -> CalibreDB:
    global _cquarry_db_instance
    if _cquarry_db_instance is None:
        db_path = _resolve_library_path()
        _cquarry_db_instance = CalibreDB(str(db_path))
    return _cquarry_db_instance
