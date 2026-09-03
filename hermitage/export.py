"""Export the loaded library to JSON or CSV.

Reformats the in-memory `list[Book]` Hermitage already has. Comments are
JIT-loaded since Phase 15 (None on books whose Codex never opened), so the
caller passes the bulk map (database.get_all_comments()) and unread books
export empty rather than recording every synopsis as absent. Format is
picked from the destination path's extension (`.json` → JSON, `.csv` →
CSV); unknown extensions fall back to JSON.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from hermitage.database import Book


def detect_format(path: Path) -> str:
    """Return 'csv' for *.csv, 'json' for everything else."""
    return "csv" if path.suffix.lower() == ".csv" else "json"


def _book_to_dict(b: Book) -> dict:
    """Flatten a Book into a JSON-serialisable dict."""
    return {
        "id": b.id,
        "title": b.title,
        "sort": b.sort,
        "authors": b.authors,
        "series": b.series,
        "series_index": b.series_index,
        "tags": b.tags,
        "rating": b.rating,
        "comment": b.comment,
        "formats": b.formats,
        "pubdate": b.pubdate,
        "added": b.timestamp,
        "has_cover": b.has_cover,
        "path": b.path,
        "identifiers": b.identifiers,
        "pages": b.pages,
        "custom": b.custom,
        "author_sorts": b.author_sorts,
        "author_links": b.author_links,
    }


def export_books(
    books: list[Book],
    path: Path,
    fmt: str | None = None,
    comments: dict[int, str] | None = None,
) -> int:
    """Write *books* to *path* as JSON or CSV. Returns the number written.

    `comments` is the bulk {book_id: html} map (database.get_all_comments());
    when given, books whose comment was never JIT-loaded export their real
    synopsis instead of None.
    """
    if fmt is None:
        fmt = detect_format(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # JIT comments: None means "never opened in the Codex" (a startup
    # artifact, not a fact about the library), so a supplied map fills those
    # in before anything is written.
    if comments:
        for b in books:
            if b.comment is None:
                b.comment = comments.get(b.id) or ""

    if fmt == "json":
        data = [_book_to_dict(b) for b in books]
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    elif fmt == "csv":
        # Lists / dicts get joined / JSON-encoded so the CSV stays single-line.
        fieldnames = [
            "id",
            "title",
            "sort",
            "authors",
            "series",
            "series_index",
            "tags",
            "rating",
            "formats",
            "pubdate",
            "added",
            "has_cover",
            "path",
            "identifiers",
            "pages",
            "custom",
            "author_sorts",
            "author_links",
        ]
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for b in books:
                writer.writerow(
                    {
                        "id": b.id,
                        "title": b.title,
                        "sort": b.sort,
                        "authors": "; ".join(b.authors),
                        "series": b.series or "",
                        "series_index": b.series_index,
                        "tags": "; ".join(b.tags),
                        "rating": b.rating if b.rating is not None else "",
                        "formats": "; ".join(b.formats),
                        "pubdate": b.pubdate or "",
                        "added": b.timestamp or "",
                        "has_cover": b.has_cover,
                        "path": b.path,
                        "identifiers": json.dumps(b.identifiers, ensure_ascii=False)
                        if b.identifiers
                        else "",
                        "pages": b.pages if b.pages is not None else "",
                        "custom": json.dumps(b.custom, ensure_ascii=False)
                        if b.custom
                        else "",
                        "author_sorts": "; ".join(b.author_sorts),
                        "author_links": "; ".join(b.author_links),
                    }
                )
    else:
        raise ValueError(f"Unknown export format: {fmt!r}")

    return len(books)
