#!/usr/bin/env python3
"""Minimal regression suite for scripts/audit.py (stdlib unittest, no network).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the deterministic rule set (R1/R2/R3/R5/R6), language detection,
monolingual rendering, and the framework metrics (FR1/FR2/FR3).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import audit  # noqa: E402


def col(cid, title, parent=None, direct=0, total=None):
    return {
        "collection_id": cid,
        "title": title,
        "parent_id": parent,
        "bookmarks_count": direct,
        "total_bookmarks_count": direct if total is None else total,
    }


def find(findings, rule):
    return [f for f in findings if f["rule"] == rule]


class AuditRuleTests(unittest.TestCase):
    def test_r1_same_parent_duplicate_is_p0(self):
        cols = [col(1, "Tools", parent=10, direct=5),
                col(2, "tools", parent=10, direct=5),
                col(10, "Design", direct=1)]
        _, findings, _ = audit.audit(cols, [])
        r1 = find(findings, "R1")
        self.assertEqual(len(r1), 1)
        self.assertEqual(r1[0]["priority"], "P0")

    def test_r1_cross_parent_duplicate_is_p1(self):
        cols = [col(1, "Study", parent=10, direct=5),
                col(2, "Study", parent=20, direct=5),
                col(10, "Design", direct=1),
                col(20, "Code", direct=1)]
        _, findings, _ = audit.audit(cols, [])
        self.assertEqual(find(findings, "R1")[0]["priority"], "P1")

    def test_r2_fragmented_flagged(self):
        cols = [col(1, "Tiny", direct=3)]
        _, findings, _ = audit.audit(cols, [])
        self.assertEqual(len(find(findings, "R2")), 1)

    def test_r3_empty_flagged(self):
        cols = [col(1, "Empty")]
        _, findings, _ = audit.audit(cols, [])
        self.assertEqual(len(find(findings, "R3")), 1)

    def test_r6_singular_plural_pair(self):
        cols = [col(1, "Tool", parent=10, direct=4),
                col(2, "Tools", parent=20, direct=4),
                col(10, "Code", direct=1),
                col(20, "Design", direct=1)]
        _, findings, _ = audit.audit(cols, [])
        self.assertEqual(len(find(findings, "R6")), 1)

    def test_unsorted_backlog_p0_threshold(self):
        items = [{"title": "t%d" % i} for i in range(21)]
        cols = [col(1, "Solo", direct=1)]
        _, findings, _ = audit.audit(cols, items)
        self.assertEqual(find(findings, "R5")[0]["priority"], "P0")
        _, findings, _ = audit.audit(cols, items[:20])
        self.assertEqual(find(findings, "R5")[0]["priority"], "P1")

    def test_missing_title_does_not_crash(self):
        cols = [{"collection_id": 1, "parent_id": None,
                 "bookmarks_count": 0, "total_bookmarks_count": 0}]  # no "title" key
        _, findings, _ = audit.audit(cols, [])
        self.assertEqual(len(find(findings, "R3")), 1)
        zh = audit.render(cols, [], None, findings, "zh")
        self.assertIn("R3", zh)


class LanguageTests(unittest.TestCase):
    def test_detect_chinese(self):
        self.assertEqual(audit.detect_language("帮我盘点一下收藏夹"), "zh")

    def test_detect_english(self):
        self.assertEqual(audit.detect_language("audit my collections please"), "en")

    def test_fallback_without_sample(self):
        self.assertEqual(audit.detect_language(""), "en")

    def test_render_is_monolingual(self):
        cols = [col(1, "A", direct=50), col(2, "B", parent=1, direct=3)]
        _, findings, _ = audit.audit(cols, [{"title": "x"}])
        zh = audit.render(cols, [{"title": "x"}], None, findings, "zh")
        en = audit.render(cols, [{"title": "x"}], None, findings, "en")
        self.assertNotIn("Overview", zh)
        self.assertNotIn("总览", en)
        self.assertIn("总览", zh)
        self.assertIn("Overview", en)


class FrameworkTests(unittest.TestCase):
    def test_fr1_flat_heavy(self):
        cols = [col(1, "Flat", direct=45)]
        rows, lib_total, warnings = audit.framework(cols)
        self.assertTrue(any(w[0] == "FR1" for w in warnings))

    def test_fr2_dominance(self):
        cols = [col(1, "Big", direct=10, total=60), col(2, "Small", direct=5, total=5)]
        rows, lib_total, warnings = audit.framework(cols)
        self.assertTrue(any(w[0] == "FR2" for w in warnings))

    def test_fr3_tiny_top(self):
        cols = [col(1, "Tiny", direct=4)]
        rows, lib_total, warnings = audit.framework(cols)
        self.assertTrue(any(w[0] == "FR3" for w in warnings))

    def test_healthy_library_has_no_warnings(self):
        cols = [col(1, "One", direct=20, total=30),
                col(11, "kid", parent=1, direct=10),
                col(2, "Two", direct=20, total=30),
                col(21, "kid", parent=2, direct=10),
                col(3, "Three", direct=15, total=20),
                col(31, "kid", parent=3, direct=5)]
        rows, lib_total, warnings = audit.framework(cols)
        self.assertEqual(warnings, [])


class RobustnessTests(unittest.TestCase):
    def test_pipe_in_title_is_escaped(self):
        cols = [col(1, "A|B", direct=3)]
        _, findings, _ = audit.audit(cols, [])
        md = audit.render(cols, [], None, findings, "en")
        self.assertNotIn("A|B", md)
        self.assertIn("A\\|B", md)

    def test_depth_cache_matches_uncached(self):
        cols = [col(1, "Root", direct=1),
                col(2, "Mid", parent=1, direct=1),
                col(3, "Leaf", parent=2, direct=1),
                col(4, "Leaf2", parent=2, direct=1)]
        by_id = audit.build_by_id(cols)
        cache = {}
        for c in cols:
            for _ in range(2):  # second pass hits the cache
                self.assertEqual(audit.depth_of(c, by_id),
                                 audit.depth_of(c, by_id, cache))

    def test_framework_uses_same_depth_as_render(self):
        cols = [col(1, "Top", direct=5, total=25),
                col(11, "Mid", parent=1, direct=5, total=20),
                col(111, "Leaf", parent=11, direct=20)]
        _, findings, by_id = audit.audit(cols, [])
        gov = [c for c in cols if c.get("collection_id") not in (-1, -99)]
        max_render = max(audit.depth_of(c, by_id) for c in gov)
        rows, _, _ = audit.framework(cols)
        self.assertEqual(rows[0]["max_depth"], max_render)


if __name__ == "__main__":
    unittest.main()
