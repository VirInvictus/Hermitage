"""Regression guards for the Hyprland-native migration (Phases 13/14).

These are cheap, headless invariants that fail loudly if a future patch
reintroduces libadwaita, adds a GNOME-only GSettings dependency, or breaks the
app-id / StartupWMClass lockstep a Hyprland windowrule relies on.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_PKG = _REPO / "hermitage"


def _py_sources() -> list[Path]:
    return sorted(_PKG.glob("*.py"))


class TestNoLibadwaita(unittest.TestCase):
    """The whole point of Phase 14: no libadwaita anywhere in the package."""

    def test_no_adw_require_version(self):
        for path in _py_sources():
            text = path.read_text()
            self.assertNotIn(
                'require_version("Adw"',
                text,
                f"{path.name} still requires the Adw typelib",
            )
            self.assertNotIn("require_version('Adw'", text)

    def test_no_adw_import(self):
        # Match an actual `Adw` name imported from gi.repository, not the word
        # appearing in a comment or docstring.
        import_re = re.compile(r"from\s+gi\.repository\s+import\s+([^\n]+)")
        for path in _py_sources():
            for line in import_re.findall(path.read_text()):
                names = {n.strip() for n in line.split(",")}
                self.assertNotIn(
                    "Adw", names, f"{path.name} imports Adw from gi.repository"
                )


class TestNoGSettings(unittest.TestCase):
    """Dark/light flows through the portal (hermitage/theme.py), never a
    GNOME-only GSettings schema."""

    def test_no_gsettings_construction(self):
        for path in _py_sources():
            text = path.read_text()
            self.assertNotIn("Gio.Settings(", text, f"{path.name} reads GSettings")
            self.assertNotIn("Gio.Settings.new", text, f"{path.name} reads GSettings")


class TestAppIdLockstep(unittest.TestCase):
    """APP_ID must match StartupWMClass so a Hyprland windowrulev2 keeps
    targeting the window after any rename."""

    def test_app_id_matches_startup_wm_class(self):
        from hermitage.app import APP_ID

        desktop = (_REPO / "data" / f"{APP_ID}.desktop").read_text()
        match = re.search(r"^StartupWMClass=(.+)$", desktop, re.MULTILINE)
        self.assertIsNotNone(match, "no StartupWMClass in the .desktop file")
        self.assertEqual(match.group(1).strip(), APP_ID)


if __name__ == "__main__":
    unittest.main()
