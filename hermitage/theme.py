"""The single theme-resolution path.

Libadwaita used to give Hermitage follow-system dark/light for free via a
portal-backed `Adw.StyleManager`. Having dropped libadwaita (Phase 14), we own
that path here: read the freedesktop appearance portal directly over D-Bus,
map it to a Kanagawa Dragon (dark) / Kanagawa Lotus (light) palette that we
inject as GTK named colours, and re-apply live when the portal reports a
change. No new dependency — Gio ships with PyGObject; degrades to the dark
default when no portal answers.

This module is *the* place theme is resolved. Nothing else should read a
colour scheme (guarded by tests: no `Gio.Settings`, no `Adw`).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

# ---------------------------------------------------------------------------
# Palettes — Kanagawa Dragon (dark) and a Kanagawa Lotus-derived light.
# Keys are the logical roles; _palette_css expands them into the full set of
# GTK/Adwaita named colours so both our stylesheet and the stock widget
# internals (buttons, entries, menus) pick up the palette.
# ---------------------------------------------------------------------------

DARK = {
    "window_bg": "#181616",
    "window_fg": "#c5c9c5",
    "view_bg": "#1d1c19",
    "view_fg": "#c5c9c5",
    "card_bg": "#201f1e",
    "card_fg": "#c5c9c5",
    "card_shade": "#141312",
    "headerbar_bg": "#1d1c19",
    "headerbar_fg": "#c5c9c5",
    "popover_bg": "#23211f",
    "popover_fg": "#c5c9c5",
    "dialog_bg": "#1d1c19",
    "dialog_fg": "#c5c9c5",
    "sidebar_bg": "#1a1918",
    "sidebar_fg": "#c5c9c5",
    "accent": "#8ba4b0",  # dragonBlue2
    "accent_fg": "#181616",
    "success": "#8a9a7b",  # dragonGreen
    "warning": "#c4b28a",  # dragonYellow
    "error": "#c4746e",  # dragonRed
    "borders": "#393836",  # dragonBlack5
}

LIGHT = {
    "window_bg": "#f2ecbc",
    "window_fg": "#545464",  # lotusInk1
    "view_bg": "#e7dba0",
    "view_fg": "#545464",
    "card_bg": "#e5ddb0",
    "card_fg": "#545464",
    "card_shade": "#dcd5ac",
    "headerbar_bg": "#e5ddb0",
    "headerbar_fg": "#545464",
    "popover_bg": "#e7dba0",
    "popover_fg": "#545464",
    "dialog_bg": "#f2ecbc",
    "dialog_fg": "#545464",
    "sidebar_bg": "#e5ddb0",
    "sidebar_fg": "#545464",
    "accent": "#4d699b",  # lotusBlue4
    "accent_fg": "#f2ecbc",
    "success": "#6f894e",  # lotusGreen
    "warning": "#77713f",  # lotusYellow
    "error": "#c84053",  # lotusRed
    "borders": "#cabf83",
}


def _palette_css(p: dict[str, str]) -> str:
    """Expand a role palette into the full GTK named-colour block."""
    return f"""
@define-color window_bg_color {p["window_bg"]};
@define-color window_fg_color {p["window_fg"]};
@define-color view_bg_color {p["view_bg"]};
@define-color view_fg_color {p["view_fg"]};
@define-color card_bg_color {p["card_bg"]};
@define-color card_fg_color {p["card_fg"]};
@define-color card_shade_color {p["card_shade"]};
@define-color headerbar_bg_color {p["headerbar_bg"]};
@define-color headerbar_fg_color {p["headerbar_fg"]};
@define-color headerbar_border_color {p["headerbar_fg"]};
@define-color headerbar_backdrop_color {p["window_bg"]};
@define-color headerbar_shade_color {p["borders"]};
@define-color popover_bg_color {p["popover_bg"]};
@define-color popover_fg_color {p["popover_fg"]};
@define-color dialog_bg_color {p["dialog_bg"]};
@define-color dialog_fg_color {p["dialog_fg"]};
@define-color sidebar_bg_color {p["sidebar_bg"]};
@define-color sidebar_fg_color {p["sidebar_fg"]};
@define-color sidebar_backdrop_color {p["window_bg"]};
@define-color sidebar_border_color {p["borders"]};
@define-color sidebar_shade_color {p["borders"]};
@define-color accent_color {p["accent"]};
@define-color accent_bg_color {p["accent"]};
@define-color accent_fg_color {p["accent_fg"]};
@define-color success_color {p["success"]};
@define-color success_bg_color {p["success"]};
@define-color success_fg_color {p["window_bg"]};
@define-color warning_color {p["warning"]};
@define-color warning_bg_color {p["warning"]};
@define-color warning_fg_color {p["window_bg"]};
@define-color error_color {p["error"]};
@define-color error_bg_color {p["error"]};
@define-color error_fg_color {p["window_bg"]};
@define-color destructive_color {p["error"]};
@define-color destructive_bg_color {p["error"]};
@define-color destructive_fg_color {p["window_bg"]};
@define-color borders {p["borders"]};
"""


# ---------------------------------------------------------------------------
# Portal-backed scheme resolution
# ---------------------------------------------------------------------------

_APPEARANCE = "org.freedesktop.appearance"
_COLOR_SCHEME = "color-scheme"

_palette_provider: Gtk.CssProvider | None = None
_proxy: Gio.DBusProxy | None = None


def init():
    """Install the palette provider, apply the current scheme, and subscribe
    to live changes. Call once, after a display exists (in do_activate)."""
    global _palette_provider
    if _palette_provider is not None:
        return

    _palette_provider = Gtk.CssProvider()
    display = Gdk.Display.get_default()
    # Register above PRIORITY_USER (800): a user ~/.config/gtk-4.0/gtk.css
    # loads at USER and would otherwise outrank an APPLICATION-priority sheet.
    Gtk.StyleContext.add_provider_for_display(
        display, _palette_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1
    )

    _apply(_query_dark())
    _subscribe()


def _apply(dark: bool):
    palette = DARK if dark else LIGHT
    _palette_provider.load_from_string(_palette_css(palette))
    settings = Gtk.Settings.get_default()
    if settings is not None:
        settings.set_property("gtk-application-prefer-dark-theme", dark)


def _get_proxy() -> Gio.DBusProxy:
    global _proxy
    if _proxy is None:
        _proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings",
            None,
        )
    return _proxy


def _unwrap(variant: GLib.Variant) -> GLib.Variant:
    """Descend through nested 'v' (variant) wrappers to the concrete value.

    ReadOne returns `(v)`; the older Read returns a double-wrapped `(v)` whose
    value is itself a variant — this handles either.
    """
    while variant.get_type_string() == "v":
        variant = variant.get_variant()
    return variant


def _query_dark() -> bool:
    """Ask the portal for the preferred colour scheme. 1=dark, 2=light,
    0/none/no-portal → dark default."""
    try:
        proxy = _get_proxy()
        try:
            result = proxy.call_sync(
                "ReadOne",
                GLib.Variant("(ss)", (_APPEARANCE, _COLOR_SCHEME)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error:
            # Older portals only expose the deprecated double-wrapped Read.
            result = proxy.call_sync(
                "Read",
                GLib.Variant("(ss)", (_APPEARANCE, _COLOR_SCHEME)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        scheme = _unwrap(result.get_child_value(0)).get_uint32()
        return scheme == 1
    except (GLib.Error, Exception):
        return True  # no portal backend — Hermitage defaults to dark


def _subscribe():
    try:
        _get_proxy().connect("g-signal", _on_signal)
    except (GLib.Error, Exception):
        pass  # no portal — the one-shot query already applied a default


def _on_signal(proxy, sender_name, signal_name, params):
    if signal_name != "SettingChanged":
        return
    try:
        namespace = params.get_child_value(0).get_string()
        key = params.get_child_value(1).get_string()
        if namespace == _APPEARANCE and key == _COLOR_SCHEME:
            scheme = _unwrap(params.get_child_value(2)).get_uint32()
            _apply(scheme == 1)
    except (GLib.Error, Exception):
        pass
