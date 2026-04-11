"""First-run setup wizard — shown when no config file exists."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk


class SetupWizard(Adw.Window):
    """First-run wizard that asks the user to pick their Calibre library."""

    def __init__(self, app: Adw.Application):
        super().__init__(
            application=app,
            title="Welcome to Hermitage",
            default_width=500,
            default_height=400,
            resizable=False,
        )
        self._app = app
        self._build_ui()

    def _build_ui(self):
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=16,
        )
        content.set_valign(Gtk.Align.CENTER)
        content.set_halign(Gtk.Align.CENTER)
        content.set_margin_start(32)
        content.set_margin_end(32)
        content.set_margin_top(24)
        content.set_margin_bottom(24)

        # Icon
        icon = Gtk.Image.new_from_icon_name("library-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")
        content.append(icon)

        # Title
        title = Gtk.Label(label="Welcome to Hermitage")
        title.add_css_class("title-1")
        content.append(title)

        # Description
        desc = Gtk.Label(
            label="Select your Calibre library folder to get started.\n"
            "This is the folder containing metadata.db.",
        )
        desc.set_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        desc.add_css_class("dim-label")
        content.append(desc)

        # Selected path display
        self._path_label = Gtk.Label(label="No folder selected")
        self._path_label.add_css_class("monospace")
        self._path_label.add_css_class("dim-label")
        self._path_label.set_ellipsize(2)  # Pango.EllipsizeMode.MIDDLE
        self._path_label.set_max_width_chars(50)
        content.append(self._path_label)

        # Buttons
        btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
        )
        btn_box.set_halign(Gtk.Align.CENTER)

        choose_btn = Gtk.Button(label="Choose Folder")
        choose_btn.add_css_class("suggested-action")
        choose_btn.add_css_class("pill")
        choose_btn.connect("clicked", self._on_choose)
        btn_box.append(choose_btn)

        self._continue_btn = Gtk.Button(label="Continue")
        self._continue_btn.add_css_class("pill")
        self._continue_btn.set_sensitive(False)
        self._continue_btn.connect("clicked", self._on_continue)
        btn_box.append(self._continue_btn)

        content.append(btn_box)

        # Error label
        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_visible(False)
        content.append(self._error_label)

        toolbar.set_content(content)
        self.set_content(toolbar)

        self._selected_path: Path | None = None

    def _on_choose(self, btn):
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
            self._error_label.set_text(
                "No metadata.db found in this folder. "
                "Please select a Calibre library directory.",
            )
            self._error_label.set_visible(True)
            self._continue_btn.set_sensitive(False)
            self._selected_path = None
            self._path_label.set_text("No folder selected")
            return

        self._error_label.set_visible(False)
        self._selected_path = path
        self._path_label.set_text(str(path))
        self._path_label.remove_css_class("dim-label")
        self._continue_btn.set_sensitive(True)

    def _on_continue(self, btn):
        if not self._selected_path:
            return

        from hermitage.config import load_config, save_config

        cfg = load_config()
        cfg["library_path"] = str(self._selected_path)
        save_config()

        # Close wizard and launch the main window
        self.close()
        self._app.do_activate()
