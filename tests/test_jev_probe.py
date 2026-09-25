#!/usr/bin/env python3
"""Unit tests for the jev_precheck probe and decision logic (no network calls).

Run from the skill root:
    python3 -m unittest discover -s tests -v
"""

import importlib
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

jp = importlib.import_module("jev_precheck")


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("TYPESAFE_API_KEY", None)
        self._saved_opt = os.environ.pop(jp.OPT_OUT_ENV, None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["TYPESAFE_API_KEY"] = self._saved
        if self._saved_opt is not None:
            os.environ[jp.OPT_OUT_ENV] = self._saved_opt

    def test_python_version_check(self):
        ok, ver = jp.python_ok()
        self.assertIsInstance(ok, bool)
        self.assertRegex(ver, r"^\d+\.\d+\.\d+$")

    def test_opt_out_disables_even_with_key(self):
        os.environ["TYPESAFE_API_KEY"] = "dummy"
        os.environ[jp.OPT_OUT_ENV] = "off"
        v = jp.probe()
        self.assertTrue(v["opt_out"])
        self.assertFalse(v["ready"])
        self.assertIn("opt-out", v["auth"])

    def test_missing_key_is_not_ready(self):
        v = jp.probe()
        self.assertFalse(v["api_key"])
        self.assertFalse(v["ready"])
        self.assertEqual(v["auth"], "not_tested")

    def test_local_ready_without_auth_call(self):
        if not jp.SDK_AVAILABLE:
            self.skipTest("typesafe-sdk not installed in this interpreter")
        os.environ["TYPESAFE_API_KEY"] = "dummy"
        v = jp.probe(do_auth_call=False)
        self.assertTrue(v["ready"])
        self.assertEqual(v["auth"], "not_tested")

    def test_opt_out_values(self):
        for value in ("off", "0", "false", "no", "OFF"):
            os.environ[jp.OPT_OUT_ENV] = value
            self.assertTrue(jp.probe()["opt_out"], value)
        os.environ[jp.OPT_OUT_ENV] = "on"
        self.assertFalse(jp.probe()["opt_out"])

    def test_workers_and_threshold_validation(self):
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "jev_precheck.py")
        base = [sys.executable, script,
                "--collections", "/nonexistent.json", "--bookmarks", "/nonexistent.json"]
        r = subprocess.run(base + ["--workers", "0"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--workers", r.stderr)
        r = subprocess.run(base + ["--high", "0.4", "--medium", "0.6"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("thresholds", r.stderr)


if __name__ == "__main__":
    unittest.main()
