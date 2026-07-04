"""In-app preferences window — reads and writes config.yaml."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

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


class PreferencesWindow(Adw.PreferencesWindow):
    """Application preferences backed by config.yaml."""

    def __init__(self, parent: Gtk.Window, on_settings_changed=None):
        super().__init__(
            transient_for=parent,
            title="Preferences",
        )
        self._on_settings_changed = on_settings_changed
        self._build_ui()

    def _build_ui(self):
        # ---- Library group ----
        lib_group = Adw.PreferencesGroup(
            title="Library",
            description="Calibre library location",
        )

        self._path_row = Adw.ActionRow(
            title="Library Path",
            subtitle=get("library_path", "Not set"),
        )
        change_btn = Gtk.Button(
            label="Change",
            valign=Gtk.Align.CENTER,
        )
        change_btn.connect("clicked", self._on_change_path)
        self._path_row.add_suffix(change_btn)
        lib_group.add(self._path_row)

        # ---- Display group ----
        display_group = Adw.PreferencesGroup(
            title="Display",
            description="Grid sorting and display preferences",
        )

        # Sort field dropdown
        self._sort_row = Adw.ComboRow(title="Sort By")
        sort_model = Gtk.StringList()
        for _, label in SORT_FIELDS:
            sort_model.append(label)
        self._sort_row.set_model(sort_model)

        current_field = get("sort_field", "title")
        for i, (key, _) in enumerate(SORT_FIELDS):
            if key == current_field:
                self._sort_row.set_selected(i)
                break
        self._sort_row.connect("notify::selected", self._on_sort_field_changed)
        display_group.add(self._sort_row)

        # Sort direction
        self._ascending_row = Adw.SwitchRow(
            title="Ascending Order",
            subtitle="Sort from A to Z, oldest to newest, lowest to highest",
        )
        self._ascending_row.set_active(get("sort_ascending", True))
        self._ascending_row.connect(
            "notify::active", self._on_sort_dir_changed,
        )
        display_group.add(self._ascending_row)

        # ---- Page ----
        page = Adw.PreferencesPage()
        page.add(lib_group)
        page.add(display_group)
        self.add(page)

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
            toast = Adw.Toast(title="No metadata.db found in that folder")
            self.add_toast(toast)
            return

        set_value("library_path", str(path))
        self._path_row.set_subtitle(str(path))

        toast = Adw.Toast(title="Library path updated — restart to apply")
        self.add_toast(toast)

    def _on_sort_field_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(SORT_FIELDS):
            key = SORT_FIELDS[idx][0]
            set_value("sort_field", key)
            if self._on_settings_changed:
                self._on_settings_changed()

    def _on_sort_dir_changed(self, row, _pspec):
        set_value("sort_ascending", row.get_active())
        if self._on_settings_changed:
            self._on_settings_changed()
