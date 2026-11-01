"""Tests for scripts/glass_contrast.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "glass_contrast.py"
SPEC = importlib.util.spec_from_file_location("glass_contrast", SCRIPT)
glass_contrast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(glass_contrast)


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = glass_contrast.main([str(a) for a in argv])
    return code, out.getvalue()


def run_json(*argv):
    code, out = run(*argv, "--json")
    return code, json.loads(out)


class GlassContrastTests(unittest.TestCase):
    def test_wcag_ratio_reference_values(self):
        self.assertAlmostEqual(glass_contrast.ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)
        self.assertAlmostEqual(glass_contrast.ratio((119, 119, 119), (255, 255, 255)), 4.48, places=2)

    def test_white_text_black_tint_solves_near_054(self):
        code, rep = run_json("--text", "#fff", "--tint", "#000", "--solve")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(rep["min_alpha"], 0.535, places=3)
        self.assertEqual(rep["worst_backdrop"], "#FFFFFF")

    def test_check_mode_pass_and_fail(self):
        self.assertEqual(run("--text", "#FFFFFF", "--tint", "#000000", "--alpha", "0.55")[0], 0)
        code, rep = run_json("--text", "#FFFFFF", "--tint", "#000000", "--alpha", "0.5")
        self.assertEqual(code, 1)
        self.assertFalse(rep["meets_target"])
        self.assertAlmostEqual(rep["worst_ratio"], 3.98, places=2)

    def test_dark_text_light_tint_worst_case_is_black_backdrop(self):
        code, rep = run_json("--text", "#111111", "--tint", "#FFFFFF", "--alpha", "0.5")
        self.assertEqual(code, 0)
        self.assertEqual(rep["worst_backdrop"], "#000000")

    def test_text_opacity_lowers_contrast(self):
        _, solid = run_json("--text", "#FFFFFF", "--tint", "#101418", "--alpha", "0.6")
        _, faded = run_json("--text", "#FFFFFF", "--text-alpha", "0.8", "--tint", "#101418", "--alpha", "0.6")
        self.assertLess(faded["worst_ratio"], solid["worst_ratio"])

    def test_listed_backdrops_only(self):
        code, rep = run_json("--text", "#FFFFFF", "--tint", "#000000", "--alpha", "0.3",
                             "--backdrop", "#203040", "--backdrop", "#102030")
        self.assertEqual(rep["scope"], "listed backdrops")
        self.assertEqual(code, 0)
        self.assertEqual(rep["worst_backdrop"], "#203040")

    def test_unreachable_target_reports_full_opacity_ratio(self):
        code, rep = run_json("--text", "#777777", "--tint", "#888888", "--solve")
        self.assertEqual(code, 1)
        self.assertIsNone(rep["min_alpha"])
        self.assertLess(rep["ratio_at_full_opacity"], 4.5)

    def test_large_text_target(self):
        code, rep = run_json("--text", "#fff", "--tint", "#000", "--solve", "--min", "3")
        self.assertEqual(code, 0)
        self.assertLess(rep["min_alpha"], 0.535)

    def test_usage_errors(self):
        self.assertEqual(run("--text", "white", "--tint", "#000", "--alpha", "0.5")[0], 2)
        self.assertEqual(run("--text", "#fff", "--tint", "#000")[0], 2)
        self.assertEqual(run("--text", "#fff", "--tint", "#000", "--alpha", "0.5", "--solve")[0], 2)
        self.assertEqual(run("--text", "#fff", "--tint", "#000", "--alpha", "1.5")[0], 2)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            glass_contrast.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
