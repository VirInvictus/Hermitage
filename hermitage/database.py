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
    timestamp: str | None = None  # date added to Calibre

    @property
    def cover_path(self) -> Path | None:
        """Absolute path to the cover image, or None."""
        if not self.has_cover:
            return None
        return library_root() / self.path / "cover.jpg"


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
            timestamp=r["timestamp"],
        ))
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
        row = conn.execute(
            "SELECT val FROM preferences WHERE key='virtual_libraries'",
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return {}
