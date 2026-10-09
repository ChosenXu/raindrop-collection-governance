#!/usr/bin/env python3
"""Offline tests for the confidence-band decision logic in jev_precheck.py.

The band decisions used to live inline in the network-coupled work() closure,
so they had zero test coverage in CI (no typesafe-sdk there) — and shipped the
unknown-band bug fixed in 1.2.3. They are now pure functions; these tests lock
the precedence and the threshold boundaries.

Run from the skill root:
    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import jev_precheck  # noqa: E402

HIGH = 0.85
MEDIUM = 0.50


class FlatBandTests(unittest.TestCase):
    def test_empty_mapping_is_unknown_even_at_high_confidence(self):
        # regression: 1.2.3 fixed "no-mapped-collection flags every bookmark"
        self.assertEqual(
            jev_precheck.assign_band_flat(5, [], 1.0, HIGH, MEDIUM), "unknown")

    def test_current_in_mapped_is_consistent_even_at_high_confidence(self):
        self.assertEqual(
            jev_precheck.assign_band_flat(5, [5, 7], 0.99, HIGH, MEDIUM),
            "consistent")

    def test_high_band_at_boundary(self):
        self.assertEqual(
            jev_precheck.assign_band_flat(2, [5], 0.85, HIGH, MEDIUM), "high")

    def test_medium_band_between_thresholds(self):
        self.assertEqual(
            jev_precheck.assign_band_flat(2, [5], 0.6, HIGH, MEDIUM), "medium")

    def test_medium_band_at_boundary_is_inclusive(self):
        self.assertEqual(
            jev_precheck.assign_band_flat(2, [5], 0.50, HIGH, MEDIUM), "medium")

    def test_low_band_below_medium(self):
        self.assertEqual(
            jev_precheck.assign_band_flat(2, [5], 0.49, HIGH, MEDIUM), "low")


class TreeBandTests(unittest.TestCase):
    def test_predicted_equals_current_is_consistent(self):
        self.assertEqual(
            jev_precheck.assign_band_tree(5, 5, 1.0, HIGH, MEDIUM), "consistent")

    def test_high_band_at_boundary(self):
        self.assertEqual(
            jev_precheck.assign_band_tree(2, 5, 0.85, HIGH, MEDIUM), "high")

    def test_medium_band_between_thresholds(self):
        self.assertEqual(
            jev_precheck.assign_band_tree(2, 5, 0.7, HIGH, MEDIUM), "medium")

    def test_low_band_below_medium(self):
        self.assertEqual(
            jev_precheck.assign_band_tree(2, 5, 0.1, HIGH, MEDIUM), "low")


if __name__ == "__main__":
    unittest.main()
