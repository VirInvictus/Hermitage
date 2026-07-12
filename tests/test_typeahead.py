"""Tests for the pure helpers behind the grid type-ahead find and the
fractional-scale thumbnail tiers (Phase 13)."""

from __future__ import annotations

import unittest

from hermitage.app import first_index_with_prefix
from hermitage.thumbnailer import _thumb_dims


class TestFirstIndexWithPrefix(unittest.TestCase):
    TITLES = ["Abaddon", "Berserk", "berlin diary", "Zealot"]

    def test_empty_prefix_returns_none(self):
        self.assertIsNone(first_index_with_prefix(self.TITLES, ""))

    def test_no_match_returns_none(self):
        self.assertIsNone(first_index_with_prefix(self.TITLES, "qq"))

    def test_matches_first_by_order(self):
        # Two titles start with "ber"; the earlier index wins.
        self.assertEqual(first_index_with_prefix(self.TITLES, "ber"), 1)

    def test_case_insensitive(self):
        self.assertEqual(first_index_with_prefix(self.TITLES, "ABA"), 0)
        self.assertEqual(first_index_with_prefix(self.TITLES, "z"), 3)

    def test_empty_list(self):
        self.assertIsNone(first_index_with_prefix([], "a"))


class TestThumbDims(unittest.TestCase):
    def test_scale_one_matches_base(self):
        self.assertEqual(_thumb_dims(1), (360, 540))

    def test_scale_two_and_three(self):
        self.assertEqual(_thumb_dims(2), (720, 1080))
        self.assertEqual(_thumb_dims(3), (1080, 1620))

    def test_scale_below_one_clamps(self):
        self.assertEqual(_thumb_dims(0), (360, 540))
        self.assertEqual(_thumb_dims(-5), (360, 540))


if __name__ == "__main__":
    unittest.main()
