"""Read-only interface to a Calibre metadata.db."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from cquarry.db import CalibreDB


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
# Database instance
# ---------------------------------------------------------------------------

_cquarry_db_instance: CalibreDB | None = None


def get_cquarry_db() -> CalibreDB:
    global _cquarry_db_instance
    if _cquarry_db_instance is None:
        db_path = _resolve_library_path()
        _cquarry_db_instance = CalibreDB(str(db_path))
    return _cquarry_db_instance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_custom_columns_cache: list[CustomColumn] | None = None


def load_custom_columns() -> list[CustomColumn]:
    """Return the custom-column schema (cached after the first library load)."""
    global _custom_columns_cache
    if _custom_columns_cache is not None:
        return _custom_columns_cache

    db = get_cquarry_db()
    _custom_columns_cache = []
    for col in db.get_custom_columns().values():
        _custom_columns_cache.append(
            CustomColumn(
                id=col["id"],
                label=col["label"],
                name=col["name"],
                datatype=col["datatype"],
                is_multiple=col["is_multiple"],
            )
        )
    return _custom_columns_cache


def load_library() -> list[Book]:
    """Load every book from the Calibre database (read-only)."""
    global _library_root_cache
    _library_root_cache = _resolve_library_path().parent
    db = get_cquarry_db()

    custom_cols = load_custom_columns()
    custom_values = {col.label: db.load_custom_column(col.name) for col in custom_cols}

    # Bulk-load identifiers and comments directly via cquarry's connection
    by_book: dict[int, dict[str, str]] = {}
    cur = db.conn.cursor()
    for row in cur.execute("SELECT book, type, val FROM identifiers"):
        by_book.setdefault(row["book"], {})[row["type"]] = row["val"]

    comments_by_book: dict[int, str] = {}
    try:
        for row in cur.execute("SELECT book, text FROM comments"):
            comments_by_book[row["book"]] = row["text"]
    except sqlite3.OperationalError:
        pass

    def _custom_for(book_id: int) -> dict[str, str | list[str]]:
        res: dict[str, str | list[str]] = {}
        for col in custom_cols:
            if book_id in custom_values[col.label]:
                val = custom_values[col.label][book_id]
                if col.is_multiple and isinstance(val, str):
                    res[col.label] = _split(val)
                else:
                    res[col.label] = val
        return res

    def _split(s: str | None) -> list[str]:
        return [p.strip() for p in s.split(",")] if s else []

    books: list[Book] = []
    for b in db.get_all_books():
        # cquarry exposes authors/tags/formats as native lists (names with
        # literal commas survive intact). Calibre historically stored a comma
        # inside author names as '|' (e.g. "Le Guin| Ursula K."); restore the
        # comma for display.
        authors_list = [a.strip().replace("|", ",") for a in (b["authors"] or [])]

        books.append(
            Book(
                id=b["id"],
                title=b["title"],
                sort=b["title_sort"] or b["title"],
                authors=authors_list,
                path=b["path"],
                has_cover=bool(b["has_cover"]),
                series=b["series"],
                series_index=b["series_index"] or 1.0,
                rating=b["rating"],
                tags=list(b["tags"] or []),
                comment=comments_by_book.get(b["id"]),
                formats=list(b["formats"] or []),
                pubdate=b["pubdate"],
                timestamp=b["timestamp"],
                identifiers=by_book.get(b["id"], {}),
                custom=_custom_for(b["id"]),
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
    return get_cquarry_db().get_virtual_libraries()


def load_saved_searches() -> dict[str, str]:
    """Read named saved searches from the Calibre preferences table.

    These power search-bar interpolation via ``search:"Name"`` and can back a
    sidebar section alongside virtual libraries.
    """
    return get_cquarry_db().get_saved_searches()


def load_vl_ui_state() -> dict:
    """Return Calibre's own sidebar layout state for virtual libraries.

    ``{"hidden": [...], "order": {...}}`` — use it to hide and order tabs
    exactly as the user's Calibre GUI does.
    """
    return get_cquarry_db().get_vl_ui_state()


# ---------------------------------------------------------------------------
# Annotations & reading progress
# ---------------------------------------------------------------------------


def get_annotations(book_id: int) -> list[dict]:
    """E-reader highlights/bookmarks/notes recorded by Calibre's drivers."""
    return get_cquarry_db().get_annotations(book_id)


def get_reading_progress(book_id: int) -> float | None:
    """Most recent reading progress fraction (0.0-1.0), or None."""
    rows = get_cquarry_db().get_last_read_positions(book_id)
    if not rows:
        return None
    latest = max(rows, key=lambda r: r.get("epoch_time") or 0)
    frac = latest.get("pos_frac")
    return float(frac) if frac is not None else None
