"""In-app preferences window — reads and writes config.yaml.

Plain GTK 4 (no libadwaita): a Gtk.Window hosting boxed-list rows, a
Gtk.DropDown for the sort field and a Gtk.Switch for the direction. Escape
closes it. Toasts come from the owned widgets.ToastOverlay.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk

from hermitage import widgets
from hermitage.config import get, set_value

# Sort field options matching the keys used in app.py sorting
SORT_FIELDS = [
    ("title", "Title"),
    ("author", "Author"),
    ("date_added", "Date Added"),
    ("pubdate", "Publication Date"),
    ("rating", "Rating"),
    ("series", "Series"),
]


class PreferencesWindow(Gtk.Window):
    """Application preferences backed by config.yaml."""

    def __init__(self, parent: Gtk.Window, on_settings_changed=None):
        super().__init__(
            transient_for=parent,
            modal=True,
            title="Preferences",
            default_width=480,
            default_height=420,
        )
        self._on_settings_changed = on_settings_changed
        self._build_ui()

        # Escape closes, matching the app's dialog conventions.
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

    def _on_key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _build_ui(self):
        self.set_titlebar(Gtk.HeaderBar())

        self._toast = widgets.ToastOverlay()
        self.set_child(self._toast)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = widgets.Clamp(maximum_size=560)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(24)
        page.set_margin_bottom(24)
        clamp.set_child(page)
        scrolled.set_child(clamp)
        self._toast.set_child(scrolled)

        # ---- Library group ----
        page.append(self._group_title("Library"))
        lib_list = widgets.boxed_list()

        change_btn = Gtk.Button(label="Change", valign=Gtk.Align.CENTER)
        change_btn.connect("clicked", self._on_change_path)
        self._path_row = widgets.value_row(
            "Library Path",
            get("library_path", "Not set"),
            suffix=change_btn,
        )
        lib_list.append(self._path_row)
        page.append(lib_list)

        # ---- Display group ----
        page.append(self._group_title("Display"))
        display_list = widgets.boxed_list()

        # Sort field dropdown
        self._sort_dd = Gtk.DropDown.new_from_strings(
            [label for _, label in SORT_FIELDS]
        )
        current_field = get("sort_field", "title")
        for i, (key, _) in enumerate(SORT_FIELDS):
            if key == current_field:
                self._sort_dd.set_selected(i)
                break
        self._sort_dd.set_valign(Gtk.Align.CENTER)
        self._sort_dd.connect("notify::selected", self._on_sort_field_changed)
        display_list.append(widgets.value_row("Sort By", suffix=self._sort_dd))

        # Sort direction
        self._asc_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._asc_switch.set_active(get("sort_ascending", True))
        self._asc_switch.connect("notify::active", self._on_sort_dir_changed)
        display_list.append(
            widgets.value_row(
                "Ascending Order",
                "Sort from A to Z, oldest to newest, lowest to highest",
                suffix=self._asc_switch,
            )
        )
        page.append(display_list)

    @staticmethod
    def _group_title(text: str) -> Gtk.Widget:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("title-2")
        return label

    def _on_change_path(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Calibre Library Folder")
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return

        if folder is None:
            return

        path = Path(folder.get_path())
        db = path / "metadata.db"

        if not db.is_file():
            self._toast.add_toast("No metadata.db found in that folder")
            return

        set_value("library_path", str(path))
        self._path_row._subtitle_label.set_text(str(path))
        self._toast.add_toast("Library path updated — restart to apply")

    def _on_sort_field_changed(self, dropdown, _pspec):
        idx = dropdown.get_selected()
        if 0 <= idx < len(SORT_FIELDS):
            key = SORT_FIELDS[idx][0]
            set_value("sort_field", key)
            if self._on_settings_changed:
                self._on_settings_changed()

    def _on_sort_dir_changed(self, switch, _pspec):
        set_value("sort_ascending", switch.get_active())
        if self._on_settings_changed:
            self._on_settings_changed()
