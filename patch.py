from pathlib import Path
import re

content = Path("pyproject.toml").read_text()
content = content.replace('"cquarry",', '"cquarry @ git+https://github.com/VirInvictus/cquarry.git",')
Path("pyproject.toml").write_text(content)

content = Path("patchnotes.md").read_text()
new_notes = """# Hermitage Patch Notes

## v1.2.0 (2026-08-23)

---

### Core Upgrades

**Centralized Calibre DB Access:** Hermitage's database backend has been entirely replaced by the `cquarry` shared library (`cquarry.db.CalibreDB`). This eliminates duplicated SQLite snapshot logic, correctly leverages upstream database locking safety, and seamlessly synchronizes query semantics with `CalibreQuarry` and `Bindery`.

"""
content = re.sub(r"^# Hermitage Patch Notes\n", new_notes, content)
Path("patchnotes.md").write_text(content)
