"""Tests for scripts/cut_rhythm.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cut_rhythm.py"
SPEC = importlib.util.spec_from_file_location("cut_rhythm", SCRIPT)
cut_rhythm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cut_rhythm)

SHOWINFO = """[Parsed_showinfo_1 @ 0x55] n:   0 pts:  12288 pts_time:1       duration: 512
[Parsed_showinfo_1 @ 0x55] n:   1 pts:  40960 pts_time:3
[Parsed_showinfo_1 @ 0x55] n:   2 pts:  61440 pts_time:4
[Parsed_showinfo_1 @ 0x55] n:   3 pts:  81920 pts_time:7
"""

SCENE_CSV = """Timecode List:,00:00:01.000,00:00:03.000
Scene Number,Start Frame,Start Timecode,Start Time (seconds),End Frame,End Timecode,End Time (seconds)
1,1,00:00:00.000,0.000,25,00:00:01.000,1.000
2,26,00:00:01.000,1.000,75,00:00:03.000,3.000
3,76,00:00:03.000,3.000,100,00:00:04.000,4.000
"""


class CutRhythmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def file(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def run_json(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cut_rhythm.main([str(a) for a in argv] + ["--json"])
        return code, (json.loads(out.getvalue()) if out.getvalue() else None)

    def test_showinfo_log_with_duration(self):
        code, rep = self.run_json(self.file("log.txt", SHOWINFO), "--duration", "10")
        self.assertEqual(code, 0)
        self.assertEqual(rep["shot_lengths_s"], [1.0, 2.0, 1.0, 3.0, 3.0])
        s = rep["stats"]
        self.assertEqual(s["shots"], 5)
        self.assertEqual(s["median_s"], 2.0)
        self.assertEqual(s["mad_s"], 1.0)
        self.assertEqual(s["cuts_per_minute"], 24.0)

    def test_missing_duration_drops_last_shot_with_warning(self):
        code, rep = self.run_json(self.file("log.txt", SHOWINFO))
        self.assertEqual(code, 1)
        self.assertEqual(rep["shot_lengths_s"], [1.0, 2.0, 1.0, 3.0])
        self.assertTrue(any("--duration" in w for w in rep["warnings"]))

    def test_scene_list_csv_prefers_seconds_columns(self):
        code, rep = self.run_json(self.file("scenes.csv", SCENE_CSV))
        self.assertEqual(rep["shot_lengths_s"], [1.0, 2.0, 1.0])
        self.assertEqual(code, 0)

    def test_plain_list_with_timecodes_and_frames(self):
        code, rep = self.run_json(self.file("cuts.txt", "00:00:01.5, 3\n00:00:04:12\n"),
                                  "--fps", "24", "--duration", "6")
        self.assertEqual(rep["shot_lengths_s"], [1.5, 1.5, 1.5, 1.5])
        self.assertEqual(rep["stats"]["median_frames"], 36.0)
        self.assertEqual(code, 0)

    def test_frame_timecode_needs_fps_and_drop_frame_rejected(self):
        self.assertEqual(self.run_json(self.file("a.txt", "00:00:04:12"))[0], 2)
        self.assertEqual(self.run_json(self.file("b.txt", "00:00:04;12"), "--fps", "29.97")[0], 2)

    def test_suspect_short_shots_flagged_and_excluded_from_plan(self):
        code, rep = self.run_json(self.file("c.txt", "1 1.02 2 3"), "--duration", "4", "--fps", "25",
                                  "--plan", "8")
        self.assertEqual(code, 1)
        self.assertEqual([s["index"] for s in rep["suspect_shots"]], [2])
        self.assertTrue(all(sh["frames"] > 1 for sh in rep["plan"]["shots"]))

    def test_plan_fills_target_exactly_and_is_seeded(self):
        log = self.file("log.txt", SHOWINFO)
        _, a = self.run_json(log, "--duration", "10", "--fps", "30", "--plan", "12.5", "--seed", "4")
        _, b = self.run_json(log, "--duration", "10", "--fps", "30", "--plan", "12.5", "--seed", "4")
        _, c = self.run_json(log, "--duration", "10", "--fps", "30", "--plan", "12.5", "--seed", "5")
        self.assertEqual(a["plan"], b["plan"])
        self.assertNotEqual(a["plan"]["shots"], c["plan"]["shots"])
        self.assertEqual(sum(s["frames"] for s in a["plan"]["shots"]), 375)
        starts = [s["start_frame"] for s in a["plan"]["shots"]]
        self.assertEqual(starts, sorted(starts))

    def test_beat_snapped_plan(self):
        _, rep = self.run_json(self.file("log.txt", SHOWINFO), "--duration", "10", "--fps", "30",
                               "--bpm", "120", "--plan", "8")
        shots = rep["plan"]["shots"]
        self.assertEqual(sum(s["frames"] for s in shots), 240)
        for s in shots[:-1]:
            self.assertEqual(s["frames"] % 15, 0)          # 120 BPM at 30 fps = 15 frames per beat
        self.assertEqual(rep["stats"]["median_beats"], 4.0)

    def test_usage_errors(self):
        log = self.file("log.txt", SHOWINFO)
        self.assertEqual(self.run_json(log, "--plan", "5")[0], 2)            # plan needs fps
        self.assertEqual(self.run_json(log, "--fps", "0")[0], 2)
        self.assertEqual(self.run_json(self.dir / "missing.txt")[0], 2)
        self.assertEqual(self.run_json(self.file("bad.txt", "soon later"))[0], 2)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            cut_rhythm.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_text_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cut_rhythm.main([str(self.file("log.txt", SHOWINFO)), "--duration", "10", "--fps", "25",
                                    "--plan", "4"])
        self.assertEqual(code, 0)
        self.assertIn("5 shots over 10.00 s", out.getvalue())
        self.assertIn("Plan:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
