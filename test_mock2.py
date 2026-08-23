import sqlite3
import tempfile
from pathlib import Path
from cquarry.db import CalibreDB
from tests.test_database import _SCHEMA

with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "metadata.db"
    conn = sqlite3.connect(p)
    conn.executescript(_SCHEMA)
    conn.close()
    try:
        db = CalibreDB(str(p))
        db.get_all_books()
        print("SUCCESS")
    except Exception as e:
        print("FAILED:", e)
