"""Tests for the YAML config layer.

The module-level path constants are pointed at a temp directory and the
in-memory cache reset around every test, so the user's real
~/.config/hermitage/config.yaml is never touched.
"""

import tempfile
import unittest
from pathlib import Path

from hermitage import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="hermitage-test-")
        tmp = Path(self._tmp.name)
        self._saved = (config._CONFIG_DIR, config._CONFIG_PATH, config._config)
        config._CONFIG_DIR = tmp
        config._CONFIG_PATH = tmp / "config.yaml"
        config._config = None

    def tearDown(self):
        config._CONFIG_DIR, config._CONFIG_PATH, config._config = self._saved
        self._tmp.cleanup()

    def test_defaults_when_no_file(self):
        self.assertFalse(config.config_exists())
        self.assertEqual(config.get("library_path"), "")
        self.assertEqual(config.get("sort_field"), "title")
        self.assertTrue(config.get("sort_ascending"))

    def test_get_unknown_key_uses_default(self):
        self.assertIsNone(config.get("nope"))
        self.assertEqual(config.get("nope", 42), 42)

    def test_set_value_persists(self):
        config.set_value("sort_field", "author")
        self.assertTrue(config.config_exists())
        # A fresh read from disk sees the write.
        config._config = None
        self.assertEqual(config.get("sort_field"), "author")

    def test_on_disk_values_merge_over_defaults(self):
        config._CONFIG_PATH.write_text("sort_ascending: false\n")
        self.assertFalse(config.get("sort_ascending"))
        self.assertEqual(config.get("sort_field"), "title")

    def test_corrupt_yaml_falls_back_to_defaults(self):
        config._CONFIG_PATH.write_text("{not: [valid")
        self.assertEqual(config.get("sort_field"), "title")

    def test_reload_config_rereads_disk(self):
        config.set_value("sort_field", "rating")
        config._CONFIG_PATH.write_text("sort_field: series\n")
        config.reload_config()
        self.assertEqual(config.get("sort_field"), "series")


if __name__ == "__main__":
    unittest.main()
