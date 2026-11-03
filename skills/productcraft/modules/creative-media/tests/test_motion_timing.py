"""Tests for scripts/motion_timing.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "motion_timing.py"
SPEC = importlib.util.spec_from_file_location("motion_timing", SCRIPT)
mt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mt)


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = mt.main(list(args))
    return code, out.getvalue()


def run_json(*args):
    code, out = run(*args, "--json")
    return code, json.loads(out)


class FramesTests(unittest.TestCase):
    def test_round_half_up(self):
        code, data = run_json("frames", "--fps", "30", "--ms", "450", "50", "800")
        self.assertEqual(code, 0)
        self.assertEqual([r["frames"] for r in data["conversions"]], [14, 2, 24])

    def test_fractional_fps(self):
        _, data = run_json("frames", "--fps", "29.97", "--ms", "1000")
        self.assertEqual(data["conversions"][0]["frames"], 30)


class BeatsTests(unittest.TestCase):
    def test_whole_beat_grid(self):
        code, data = run_json("beats", "--fps", "30", "--bpm", "120", "--bars", "1")
        self.assertEqual(code, 0)
        self.assertEqual(data["frames_per_beat"], 15)
        self.assertEqual([g["frame"] for g in data["grid"]], [0, 15, 30, 45, 60])

    def test_absolute_grid_does_not_drift(self):
        code, data = run_json("beats", "--fps", "30", "--bpm", "128", "--bars", "8")
        # 14.0625 frames per beat: beat 32 lands at exactly 450, a rounded 14-frame step would give 448
        self.assertEqual(data["grid"][32]["frame"], 450)
        self.assertEqual(code, 1)
        self.assertTrue(any("drifts" in w for w in data["warnings"]))

    def test_offset_and_downbeats(self):
        _, data = run_json("beats", "--fps", "25", "--bpm", "100", "--bars", "1", "--offset-ms", "200")
        self.assertEqual(data["grid"][0]["frame"], 5)
        self.assertTrue(data["grid"][0]["downbeat"])
        self.assertFalse(data["grid"][1]["downbeat"])


class LoopTests(unittest.TestCase):
    def test_render_range_excludes_frame_n(self):
        code, data = run_json("loop", "--fps", "30", "--seconds", "4", "--cycles", "2")
        self.assertEqual(code, 0)
        self.assertEqual(data["render_range"], [0, 119])

    def test_fractional_cycles_and_bad_period_warn(self):
        code, data = run_json("loop", "--fps", "30", "--frames", "120", "--cycles", "1.5", "--period-frames", "45", "40")
        self.assertEqual(code, 1)
        self.assertEqual(len(data["warnings"]), 2)
        self.assertIn("40", data["warnings"][1])

    def test_seconds_not_whole_frames_warn(self):
        code, data = run_json("loop", "--fps", "24", "--seconds", "1.01")
        self.assertEqual(code, 1)
        self.assertEqual(data["frames"], 24)


class GifTests(unittest.TestCase):
    def test_delays_sum_exactly(self):
        code, data = run_json("gif", "--fps", "30", "--frames", "30")
        self.assertEqual(code, 0)
        self.assertEqual(sum(data["delays_cs"]), 100)
        self.assertEqual(set(data["delays_cs"]), {3, 4})

    def test_even_rate(self):
        _, data = run_json("gif", "--fps", "25", "--frames", "50")
        self.assertEqual(data["delays_cs"], [4] * 50)

    def test_clamped_delays_warn(self):
        code, data = run_json("gif", "--fps", "60", "--frames", "60")
        self.assertEqual(code, 1)
        self.assertTrue(any("under 2" in w for w in data["warnings"]))

    def test_compress(self):
        self.assertEqual(mt.compress([3, 3, 4, 3]), "3x2 4 3")


class BlurTests(unittest.TestCase):
    def test_default_four_subframes_over_half_a_frame(self):
        code, data = run_json("blur", "--fps", "25")
        self.assertEqual(code, 0)
        self.assertEqual(data["offsets_frames"], [0.0625, 0.1875, 0.3125, 0.4375])
        self.assertAlmostEqual(data["times_s"][3], 0.4375 / 25)

    def test_frame_offset_and_full_shutter(self):
        _, data = run_json("blur", "--fps", "30", "--frame", "10", "--subframes", "2", "--shutter", "360")
        self.assertEqual(data["offsets_frames"], [0.25, 0.75])
        self.assertAlmostEqual(data["times_s"][0], 10.25 / 30)

    def test_single_subframe_warns_and_bad_shutter_fails(self):
        self.assertEqual(run("blur", "--fps", "30", "--subframes", "1")[0], 1)
        self.assertEqual(run("blur", "--fps", "30", "--shutter", "400")[0], 2)


class HoldAndUsageTests(unittest.TestCase):
    def test_hold(self):
        code, data = run_json("hold", "--words", "9", "--fps", "30")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(data["seconds"], 3.2)
        self.assertEqual(data["frames"], 96)

    def test_usage_errors(self):
        self.assertEqual(run("nope")[0], 2)
        self.assertEqual(run("gif", "--fps", "30", "--frames", "0")[0], 2)
        self.assertEqual(run("frames", "--fps", "0", "--ms", "1")[0], 2)
        self.assertEqual(run("beats", "--fps", "30", "--bpm", "120", "--bars", "0")[0], 2)

    def test_help_exits_zero(self):
        self.assertEqual(run("--help")[0], 0)


if __name__ == "__main__":
    unittest.main()
