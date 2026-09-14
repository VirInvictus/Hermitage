"""Tests for the portal colour-scheme mapping.

The startup query and the live SettingChanged handler must map portal
values identically: the handler used to apply `scheme == 1`, so a live
flip to "no preference" went light while the same value at startup
stayed dark.
"""

import unittest
from unittest import mock

from hermitage import theme


class TestSchemePreference(unittest.TestCase):
    def test_values_map_to_dark_default(self):
        # 1=dark, 2=light, 0=no preference -> dark default.
        for scheme, expected in [(0, True), (1, True), (2, False)]:
            with self.subTest(scheme=scheme):
                self.assertEqual(theme._scheme_is_dark(scheme), expected)

    def test_setting_changed_handler_matches_the_startup_query(self):
        for scheme, expected in [(0, True), (1, True), (2, False)]:
            with self.subTest(scheme=scheme):
                with mock.patch.object(theme, "_apply") as apply_mock:
                    params = theme.GLib.Variant(
                        "(ssv)",
                        (
                            "org.freedesktop.appearance",
                            "color-scheme",
                            theme.GLib.Variant("u", scheme),
                        ),
                    )
                    theme._on_signal(None, None, "SettingChanged", params)
                    apply_mock.assert_called_once_with(expected)

    def test_other_namespaces_are_ignored(self):
        with mock.patch.object(theme, "_apply") as apply_mock:
            params = theme.GLib.Variant(
                "(ssv)",
                ("org.other.namespace", "color-scheme", theme.GLib.Variant("u", 2)),
            )
            theme._on_signal(None, None, "SettingChanged", params)
            apply_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
