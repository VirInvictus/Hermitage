"""CLI tool to verify Calibre library path resolution and cover integrity."""

from __future__ import annotations

import sys
import time

from hermitage.database import load_library, library_root


def verify_library():
    """Bench-test path resolution for every book in the library."""
    t0 = time.perf_counter()
    books = load_library()
    load_ms = (time.perf_counter() - t0) * 1000
    root = library_root()

    total = len(books)
    missing_dir = []
    missing_cover = []
    cover_ok = 0
    no_cover_flag = 0
    no_formats = []

    t1 = time.perf_counter()
    for b in books:
        book_dir = root / b.path
        if not book_dir.is_dir():
            missing_dir.append(b)
            continue

        if b.has_cover:
            # Canonical cover resolution (cquarry get_cover_path with the
            # Book wrapper's unverified semantics): the catalogued cover.jpg
            # path, checked on disk here. A cover.png-only book still counts
            # as missing, exactly as the hardcoded check did — flagged in the
            # 1.7.0 patchnotes as a known gap, not silently changed.
            cover = b.cover_path
            if cover is not None and cover.is_file():
                cover_ok += 1
            else:
                missing_cover.append(b)
        else:
            no_cover_flag += 1

        if not b.formats:
            no_formats.append(b)

    scan_ms = (time.perf_counter() - t1) * 1000

    # Report
    print(f"Library root:  {root}")
    print(f"Total books:   {total}")
    print(f"DB load:       {load_ms:.0f} ms")
    print(f"Path scan:     {scan_ms:.0f} ms")
    print()

    print(f"Covers OK:           {cover_ok}")
    print(f"No cover (flagged):  {no_cover_flag}")

    if missing_dir:
        print(f"\nMISSING DIRECTORIES ({len(missing_dir)}):")
        for b in missing_dir:
            print(f"  [{b.id}] {b.title} -> {b.path}")

    if missing_cover:
        print(f"\nMISSING COVER FILES ({len(missing_cover)}):")
        print("  (has_cover=True but cover.jpg not found on disk)")
        for b in missing_cover:
            print(f"  [{b.id}] {b.title} -> {root / b.path}")

    if no_formats:
        print(f"\nNO FORMAT FILES ({len(no_formats)}):")
        for b in no_formats:
            print(f"  [{b.id}] {b.title}")

    if not missing_dir and not missing_cover:
        print("\nAll paths verified OK.")

    return len(missing_dir) + len(missing_cover)


def main():
    print("Hermitage — Library Verification\n")
    errors = verify_library()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
