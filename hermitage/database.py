"""Read-only interface to a Calibre metadata.db."""

from __future__ import annotations

import os
import sqlite3
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

    @property
    def cover_path(self) -> Path | None:
        """Absolute path to the cover image, or None."""
        if not self.has_cover:
            return None
        return _library_root() / self.path / "cover.jpg"


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
    GROUP_CONCAT(DISTINCT a.name)       AS authors,
    s.name                              AS series,
    r.rating                            AS rating,
    c.text                              AS comment,
    GROUP_CONCAT(DISTINCT t.name)       AS tags,
    GROUP_CONCAT(DISTINCT d.format)     AS formats
FROM books b
    LEFT JOIN books_authors_link    bal ON b.id = bal.book
    LEFT JOIN authors               a   ON bal.author = a.id
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
# Library root resolution
# ---------------------------------------------------------------------------

_library_root_cache: Path | None = None


def _library_root() -> Path:
    global _library_root_cache
    if _library_root_cache is None:
        _library_root_cache = _resolve_library_path().parent
    return _library_root_cache


def _resolve_library_path() -> Path:
    """Locate the metadata.db via env var or default path."""
    env = os.environ.get("HERMITAGE_DB")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(f"HERMITAGE_DB points to missing file: {p}")

    default = Path.home() / "docs" / "Calibre Library" / "metadata.db"
    if default.is_file():
        return default
    raise FileNotFoundError(
        "No metadata.db found. Set HERMITAGE_DB or place a Calibre library "
        f"at {default.parent}"
    )


def _connect() -> sqlite3.Connection:
    db_path = _resolve_library_path()
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_library() -> list[Book]:
    """Load every book from the Calibre database (read-only)."""
    global _library_root_cache
    _library_root_cache = _resolve_library_path().parent
    conn = _connect()
    try:
        rows = conn.execute(_BOOKS_QUERY).fetchall()
    finally:
        conn.close()

    books: list[Book] = []
    for r in rows:
        books.append(Book(
            id=r["id"],
            title=r["title"],
            sort=r["sort"],
            authors=r["authors"].split(",") if r["authors"] else [],
            path=r["path"],
            has_cover=bool(r["has_cover"]),
            series=r["series"],
            series_index=r["series_index"],
            rating=r["rating"],
            tags=r["tags"].split(",") if r["tags"] else [],
            comment=r["comment"],
            formats=r["formats"].split(",") if r["formats"] else [],
            pubdate=r["pubdate"],
        ))
    return books


# ---------------------------------------------------------------------------
# FTS5 Search Index (in-memory)
# ---------------------------------------------------------------------------

_fts_conn: sqlite3.Connection | None = None
_fts_book_index: dict[int, int] = {}  # book.id -> position in books list


def build_search_index(books: list[Book]):
    """Build an in-memory FTS5 index from loaded books."""
    global _fts_conn, _fts_book_index
    _fts_conn = sqlite3.connect(":memory:")
    _fts_conn.execute(
        "CREATE VIRTUAL TABLE books_fts USING fts5("
        "  title, authors, tags, series,"
        "  content='', contentless_delete=1,"
        "  tokenize='unicode61 remove_diacritics 2'"
        ")"
    )
    _fts_book_index.clear()
    rows = []
    for i, b in enumerate(books):
        _fts_book_index[b.id] = i
        rows.append((
            b.id,
            b.title,
            " ".join(b.authors),
            " ".join(t.replace(".", " ") for t in b.tags),
            b.series or "",
        ))
    _fts_conn.executemany(
        "INSERT INTO books_fts(rowid, title, authors, tags, series) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    _fts_conn.commit()


def search(query: str, books: list[Book], limit: int = 50) -> list[Book]:
    """Search the FTS5 index. Returns matching books ranked by relevance."""
    if not _fts_conn or not query.strip():
        return []
    # Append * for prefix matching so partial words work
    terms = query.strip().split()
    fts_query = " ".join(
        f'"{t.replace(chr(34), "")}"*' for t in terms if t.replace('"', "")
    )
    if not fts_query:
        return []
    try:
        rows = _fts_conn.execute(
            "SELECT rowid FROM books_fts WHERE books_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (fts_query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    results = []
    for (rowid,) in rows:
        idx = _fts_book_index.get(rowid)
        if idx is not None:
            results.append(books[idx])
    return results
