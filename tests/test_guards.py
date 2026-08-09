"""Regression guards for the Hyprland-native migration (Phases 13/14).

These are cheap, headless invariants that fail loudly if a future patch
reintroduces libadwaita, adds a GNOME-only GSettings dependency, or breaks the
app-id / StartupWMClass lockstep a Hyprland windowrule relies on.
"""

from __future__ import annotations

import ast
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


_TOPLEVELS = {"Window", "AboutDialog", "ApplicationWindow"}


def _is_toplevel(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr in _TOPLEVELS


def _has_application_kwarg(call: ast.Call) -> bool:
    return any(kw.arg == "application" for kw in call.keywords)


class TestSecondaryWindowAppId(unittest.TestCase):
    """Every toplevel must be registered with the Gtk.Application.

    A `Gtk.Window` that is never added to the application does not inherit the
    app id: GTK falls back to `g_get_prgname()`, so the Wayland surface reports
    `python` under `python -m hermitage` and `hermitage` under the console
    script, but never the app id in either case. That is precisely the class a
    Hyprland `windowrulev2` keys on, so a user rule targeting Hermitage silently
    misses any window that skips this.

    Found 2026-07-28 during the Phase 13 visual pass: Preferences, Library
    Insights, Keyboard Shortcuts and About all reported `python`, verified live
    with `hyprctl clients`. Confirmed 2026-08-09 with a four-window probe that
    both candidate fixes work (`application=` at construction, and a later
    `app.add_window()`) while a plain construction reports the prgname. The
    construction kwarg is the one used here. `TestAppIdLockstep` above cannot
    see this class of bug, which is why it gets its own guard.
    """

    def _offenders(self) -> list[str]:
        bad: list[str] = []
        for path in _py_sources():
            tree = ast.parse(path.read_text(), filename=str(path))

            # Toplevel subclasses: the app must reach super().__init__.
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef):
                    continue
                if not any(_is_toplevel(base) for base in cls.bases):
                    continue
                for call in ast.walk(cls):
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "__init__"
                        and isinstance(call.func.value, ast.Call)
                        and isinstance(call.func.value.func, ast.Name)
                        and call.func.value.func.id == "super"
                        and not _has_application_kwarg(call)
                    ):
                        bad.append(f"{path.name}:{call.lineno} class {cls.name}")

            # Direct constructions, e.g. the Shortcuts and About dialogs.
            for call in ast.walk(tree):
                if (
                    isinstance(call, ast.Call)
                    and _is_toplevel(call.func)
                    and not _has_application_kwarg(call)
                ):
                    bad.append(f"{path.name}:{call.lineno} {ast.unparse(call.func)}()")
        return bad

    def test_every_toplevel_is_registered_with_the_application(self):
        offenders = self._offenders()
        self.assertEqual(
            offenders,
            [],
            "these toplevels will report the wrong Wayland app_id; pass "
            "application= (or call app.add_window) so a Hyprland window rule "
            "matches them: " + ", ".join(offenders),
        )

    def test_the_guard_can_actually_fail(self):
        """A guard that cannot fail is not a guard.

        Catagotchi shipped a smoke suite whose gates could not fail and it hid a
        parse error in `main`; this asserts the detector fires on the exact
        pattern the 2026-07-28 pass found in the wild.
        """
        tree = ast.parse(
            "import gi\n"
            "from gi.repository import Gtk\n"
            "dlg = Gtk.Window(transient_for=win, modal=True, title='Nope')\n"
        )
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _is_toplevel(n.func)
        ]
        self.assertEqual(len(calls), 1)
        self.assertFalse(_has_application_kwarg(calls[0]))


if __name__ == "__main__":
    unittest.main()
