"""Register bundled fonts with Pango at startup.

Hermitage ships its typography (Fraunces, Inter, IBM Plex Sans Condensed) in
``hermitage/fonts/`` so the look is identical on every machine. We hand the
files to the default PangoCairo font map via ``add_font_file`` (Pango 1.56+),
which scopes the registration to this process — no system fontconfig changes,
no user font directory pollution.
"""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Pango, PangoCairo

FONTS_DIR = Path(__file__).parent / "fonts"

# Order doesn't matter for Pango, but keep families together for readability.
_FONT_FILES = (
    "Fraunces-Variable.ttf",
    "Fraunces-Italic-Variable.ttf",
    "InterVariable.ttf",
    "InterVariable-Italic.ttf",
    "IBMPlexSansCondensed-Regular.ttf",
    "IBMPlexSansCondensed-Medium.ttf",
    "IBMPlexSansCondensed-SemiBold.ttf",
)

_registered = False


def register_bundled_fonts() -> bool:
    """Register every bundled .ttf with the default Pango font map.

    Idempotent. Returns True if registration succeeded (or was already done),
    False if the runtime is too old or any font failed to load — callers can
    fall back to system defaults via the CSS fallback chain.
    """
    global _registered
    if _registered:
        return True

    fontmap = PangoCairo.FontMap.get_default()
    if not hasattr(fontmap, "add_font_file"):
        print(
            "hermitage: Pango is too old for runtime font registration "
            f"({Pango.version_string()}); using system fallback fonts.",
            file=sys.stderr,
        )
        return False

    ok = True
    for name in _FONT_FILES:
        path = FONTS_DIR / name
        if not path.is_file():
            print(f"hermitage: bundled font missing: {path}", file=sys.stderr)
            ok = False
            continue
        try:
            fontmap.add_font_file(str(path))
        except Exception as exc:
            print(
                f"hermitage: failed to register {name}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            ok = False

    _registered = ok
    return ok
