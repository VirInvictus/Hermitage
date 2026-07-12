"""Owned GTK4 widgets — the plain-GTK successors to the handful of libadwaita
widgets Hermitage relied on.

Dropping libadwaita (roadmap Phase 14) means re-implementing the few adwaita
widgets that earned their keep: a width-clamping container (`Clamp`), a
two-line header title (`WindowTitle`), an auto-hiding notification overlay
(`ToastOverlay`), a centred empty-state composite (`StatusPage`), and the
boxed-list row helper both Preferences and Insights share (`value_row`). None
needs a new dependency; the structural styling lives in `style.css`.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, GLib, Gtk, Pango


# ---------------------------------------------------------------------------
# Clamp — width-capped, centred container (replaces Adw.Clamp)
# ---------------------------------------------------------------------------


class Clamp(Gtk.Widget):
    """Constrain a single child to `maximum_size` px wide and centre it.

    GTK CSS has no `max-width`, which is exactly why libadwaita shipped a
    measure-overriding widget for this. We do the same: cap the natural width
    in `do_measure`, answer height-for-width at the clamped width, and centre
    the child in `do_size_allocate`. The tightening-threshold easing Adw.Clamp
    offered is deliberately dropped (as in the Colophon pilot).
    """

    __gtype_name__ = "HermitageClamp"

    def __init__(self, maximum_size: int = 600, child: Gtk.Widget | None = None):
        super().__init__()
        self._child: Gtk.Widget | None = None
        self._maximum_size = maximum_size
        if child is not None:
            self.set_child(child)

    def set_child(self, child: Gtk.Widget | None):
        if child is self._child:
            return
        if self._child is not None:
            self._child.unparent()
        self._child = child
        if child is not None:
            child.set_parent(self)
        self.queue_resize()

    def get_child(self) -> Gtk.Widget | None:
        return self._child

    def set_maximum_size(self, size: int):
        if size != self._maximum_size:
            self._maximum_size = size
            self.queue_resize()

    def get_maximum_size(self) -> int:
        return self._maximum_size

    def do_measure(self, orientation, for_size):
        child = self._child
        if child is None or not child.get_visible():
            return (0, 0, -1, -1)

        if orientation == Gtk.Orientation.HORIZONTAL:
            min_w, nat_w, _, _ = child.measure(orientation, for_size)
            # Cap the natural width at the clamp, but never below the child's
            # own minimum (a child that insists on more than the cap wins).
            nat_w = max(min_w, min(nat_w, self._maximum_size))
            return (min_w, nat_w, -1, -1)

        # Vertical: lay the child out at the clamped width so wrapping text
        # reports the correct height-for-width.
        width = for_size
        if width >= 0:
            width = min(width, self._maximum_size)
        return child.measure(orientation, width)

    def do_size_allocate(self, width, height, baseline):
        child = self._child
        if child is None:
            return
        child_width = min(width, self._maximum_size)
        x = max(0, (width - child_width) // 2)
        alloc = Gdk.Rectangle()
        alloc.x = x
        alloc.y = 0
        alloc.width = child_width
        alloc.height = height
        child.size_allocate(alloc, baseline)

    def do_dispose(self):
        if self._child is not None:
            self._child.unparent()
            self._child = None
        Gtk.Widget.do_dispose(self)


# ---------------------------------------------------------------------------
# WindowTitle — two-line header title (replaces Adw.WindowTitle)
# ---------------------------------------------------------------------------


class WindowTitle(Gtk.Box):
    """Title over a dim subtitle, for use as a Gtk.HeaderBar title widget."""

    __gtype_name__ = "HermitageWindowTitle"

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_valign(Gtk.Align.CENTER)
        self.add_css_class("window-title")

        self._title = Gtk.Label(label=title)
        self._title.add_css_class("wt-title")
        self._title.set_ellipsize(Pango.EllipsizeMode.END)
        self._title.set_single_line_mode(True)
        self.append(self._title)

        self._subtitle = Gtk.Label(label=subtitle)
        self._subtitle.add_css_class("wt-subtitle")
        self._subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        self._subtitle.set_single_line_mode(True)
        self._subtitle.set_visible(bool(subtitle))
        self.append(self._subtitle)

    def set_title(self, text: str):
        self._title.set_text(text or "")

    def get_title(self) -> str:
        return self._title.get_text()

    def set_subtitle(self, text: str):
        self._subtitle.set_text(text or "")
        self._subtitle.set_visible(bool(text))


# ---------------------------------------------------------------------------
# ToastOverlay — transient bottom notification (replaces Adw.ToastOverlay)
# ---------------------------------------------------------------------------


class ToastOverlay(Gtk.Overlay):
    """Wrap content and pop an auto-hiding toast over the bottom edge.

    Newest-wins: a fresh toast cancels the pending hide of the previous one so
    two back-to-back messages don't leave the first stuck on screen.
    """

    __gtype_name__ = "HermitageToastOverlay"

    def __init__(self):
        super().__init__()
        self._hide_id = 0

        self._revealer = Gtk.Revealer()
        self._revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self._revealer.set_transition_duration(200)
        self._revealer.set_halign(Gtk.Align.CENTER)
        self._revealer.set_valign(Gtk.Align.END)
        self._revealer.set_margin_bottom(24)
        self._revealer.set_reveal_child(False)

        self._label = Gtk.Label()
        self._label.set_wrap(True)
        self._label.set_max_width_chars(60)
        self._label.add_css_class("toast")
        self._revealer.set_child(self._label)

        self.add_overlay(self._revealer)
        # The toast must not influence the main child's measurement.
        self.set_measure_overlay(self._revealer, False)

    def add_toast(self, text: str):
        if self._hide_id:
            GLib.source_remove(self._hide_id)
            self._hide_id = 0
        self._label.set_text(text)
        self._revealer.set_reveal_child(True)
        self._hide_id = GLib.timeout_add_seconds(4, self._hide)

    def _hide(self) -> bool:
        self._revealer.set_reveal_child(False)
        self._hide_id = 0
        return GLib.SOURCE_REMOVE


# ---------------------------------------------------------------------------
# StatusPage — centred empty / loading state (replaces Adw.StatusPage)
# ---------------------------------------------------------------------------


class StatusPage(Gtk.Box):
    """Centred icon + title + description, with an optional child below.

    API mirrors Adw.StatusPage (`set_title` / `set_description` /
    `set_icon_name` / `set_child`) so existing callers that mutate the copy in
    place (the no-results page) keep working unchanged.
    """

    __gtype_name__ = "HermitageStatusPage"

    def __init__(
        self,
        title: str = "",
        description: str = "",
        icon_name: str | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.add_css_class("status-page")
        self._extra: Gtk.Widget | None = None

        self._icon = Gtk.Image()
        self._icon.set_pixel_size(96)
        self._icon.add_css_class("status-icon")
        self.append(self._icon)

        self._title = Gtk.Label()
        self._title.add_css_class("status-title")
        self._title.set_wrap(True)
        self._title.set_justify(Gtk.Justification.CENTER)
        self.append(self._title)

        self._desc = Gtk.Label()
        self._desc.add_css_class("status-description")
        self._desc.add_css_class("dim-label")
        self._desc.set_wrap(True)
        self._desc.set_justify(Gtk.Justification.CENTER)
        self._desc.set_max_width_chars(50)
        self.append(self._desc)

        self.set_title(title)
        self.set_description(description)
        self.set_icon_name(icon_name)

    def set_title(self, text: str):
        self._title.set_text(text or "")
        self._title.set_visible(bool(text))

    def set_description(self, text: str):
        self._desc.set_text(text or "")
        self._desc.set_visible(bool(text))

    def set_icon_name(self, name: str | None):
        if name:
            self._icon.set_from_icon_name(name)
            self._icon.set_visible(True)
        else:
            self._icon.set_visible(False)

    def set_child(self, widget: Gtk.Widget | None):
        if self._extra is not None:
            self.remove(self._extra)
        self._extra = widget
        if widget is not None:
            self.append(widget)


# ---------------------------------------------------------------------------
# Boxed-list rows — shared by Preferences and the Insights audit list
# ---------------------------------------------------------------------------


def value_row(
    title: str,
    subtitle: str | None = None,
    *,
    prefix: Gtk.Widget | None = None,
    suffix: Gtk.Widget | None = None,
) -> Gtk.Box:
    """A single boxed-list row: optional prefix icon, title over an optional
    subtitle, optional trailing control. Returns a Gtk.Box (Gtk.ListBox wraps
    it in a row on append). The title/subtitle labels are stashed on the box
    (`_title_label` / `_subtitle_label`) for callers that update them later.
    """
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.add_css_class("owned-row")

    if prefix is not None:
        prefix.set_valign(Gtk.Align.CENTER)
        row.append(prefix)

    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text.set_hexpand(True)
    text.set_valign(Gtk.Align.CENTER)

    title_label = Gtk.Label(label=title, xalign=0)
    title_label.add_css_class("owned-row-title")
    title_label.set_ellipsize(Pango.EllipsizeMode.END)
    text.append(title_label)

    subtitle_label = None
    if subtitle is not None:
        subtitle_label = Gtk.Label(label=subtitle, xalign=0)
        subtitle_label.add_css_class("owned-row-subtitle")
        subtitle_label.add_css_class("dim-label")
        subtitle_label.set_wrap(True)
        subtitle_label.set_xalign(0)
        text.append(subtitle_label)

    row.append(text)

    if suffix is not None:
        suffix.set_valign(Gtk.Align.CENTER)
        row.append(suffix)

    row._title_label = title_label
    row._subtitle_label = subtitle_label
    return row


def boxed_list() -> Gtk.ListBox:
    """A non-selectable Gtk.ListBox styled as an adwaita-style boxed list."""
    lb = Gtk.ListBox()
    lb.set_selection_mode(Gtk.SelectionMode.NONE)
    lb.add_css_class("boxed-list")
    return lb
