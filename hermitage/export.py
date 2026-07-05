"""Export the loaded library to JSON or CSV.

Pure read-only reformatting of the in-memory `list[Book]` Hermitage already
has — no DB query. Format is picked from the destination path's extension
(`.json` → JSON, `.csv` → CSV); unknown extensions fall back to JSON.
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
    }


def export_books(books: list[Book], path: Path, fmt: str | None = None) -> int:
    """Write *books* to *path* as JSON or CSV. Returns the number written."""
    if fmt is None:
        fmt = detect_format(path)
    path.parent.mkdir(parents=True, exist_ok=True)

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
                    }
                )
    else:
        raise ValueError(f"Unknown export format: {fmt!r}")

    return len(books)
