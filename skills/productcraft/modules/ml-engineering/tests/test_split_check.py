"""Offline tests for split_check.py; temporary files only, no network."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "split_check.py"
spec = importlib.util.spec_from_file_location("split_check", SCRIPT)
sc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sc
spec.loader.exec_module(sc)


class SplitCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, header, rows):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(",".join(header) + "\n")
            for row in rows:
                handle.write(",".join(str(v) for v in row) + "\n")
        return path

    def run_json(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sc.main(list(argv) + ["--json"])
        data = json.loads(out.getvalue()) if out.getvalue().strip().startswith("{") else None
        return code, data, err.getvalue()

    def codes(self, data):
        return {f["code"] for f in data["findings"]}

    def test_clean_split_exits_zero(self):
        header = ["id", "user", "ts", "x", "y"]
        train = self.write("train.csv", header, [(i, f"u{i}", f"2024-01-{i + 1:02d}", i, i % 2) for i in range(10)])
        test = self.write("test.csv", header, [(100 + i, f"v{i}", f"2024-02-{i + 1:02d}", 50 + i, i % 2)
                                               for i in range(5)])
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"test={test}",
                                      "--id", "id", "--group", "user", "--time", "ts", "--target", "y")
        self.assertEqual(code, 0)
        self.assertEqual(data["warnings"], 0)

    def test_detects_id_group_time_and_duplicate_leaks(self):
        header = ["id", "user", "ts", "x", "y"]
        train = self.write("train.csv", header, [(1, "u1", "2024-01-01", 10, 0), (2, "u2", "2024-01-05", 20, 1)])
        test = self.write("test.csv", header, [(2, "u2", "2024-01-03T10:00:00Z", 99, 1),
                                               (3, "u3", "2024-02-01", 10, 1)])
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"test={test}",
                                      "--id", "id", "--group", "user", "--time", "ts", "--target", "y")
        self.assertEqual(code, 1)
        self.assertTrue({"ID_OVERLAP", "GROUP_OVERLAP", "TIME_OVERLAP", "DUPLICATE_ROWS",
                         "LABEL_CONFLICT"} <= self.codes(data))

    def test_target_copy_and_unseen_class(self):
        header = ["x", "leak", "y"]
        train = self.write("train.csv", header, [(i, i % 2, i % 2) for i in range(30)])
        test = self.write("test.csv", header, [(100 + i, 2, 2) for i in range(5)])
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"test={test}", "--target", "y")
        self.assertEqual(code, 1)
        codes = self.codes(data)
        self.assertIn("TARGET_COPY", codes)
        self.assertIn("UNSEEN_CLASS", codes)
        copy = [f for f in data["findings"] if f["code"] == "TARGET_COPY"]
        self.assertEqual(copy[0]["column"], "leak")

    def test_schema_mismatch_and_three_splits(self):
        train = self.write("a.csv", ["x", "y"], [(1, 0), (2, 1)])
        valid = self.write("b.csv", ["x", "y"], [(3, 0)])
        test = self.write("c.csv", ["x", "z"], [(4, 1)])
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"valid={valid}",
                                      "--split", f"test={test}")
        self.assertEqual(code, 1)
        self.assertIn("SCHEMA_MISMATCH", self.codes(data))

    def test_duplicate_id_within_split_and_unparsed_time(self):
        header = ["id", "ts", "x"]
        train = self.write("train.csv", header, [(1, "2024-01-01", 1), (1, "2024-01-02", 2)])
        test = self.write("test.csv", header, [(5, "not a date", 3)])
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"test={test}",
                                      "--id", "id", "--time", "ts")
        self.assertEqual(code, 1)
        self.assertTrue({"DUPLICATE_ID", "TIME_UNPARSED"} <= self.codes(data))

    def test_ignore_removes_column_from_duplicate_check(self):
        header = ["x", "noise"]
        train = self.write("train.csv", header, [(1, "a")])
        test = self.write("test.csv", header, [(1, "b")])
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"test={test}")
        self.assertEqual(code, 0)
        code, data, _ = self.run_json("--split", f"train={train}", "--split", f"test={test}", "--ignore", "noise")
        self.assertEqual(code, 1)
        self.assertIn("DUPLICATE_ROWS", self.codes(data))

    def test_no_examples_hides_identifiers(self):
        header = ["id", "x"]
        train = self.write("train.csv", header, [("secret-id-1", 1)])
        test = self.write("test.csv", header, [("secret-id-1", 2)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sc.main(["--split", f"train={train}", "--split", f"test={test}", "--id", "id", "--no-examples"])
        self.assertNotIn("secret-id-1", out.getvalue())

    def test_bad_inputs_exit_two(self):
        train = self.write("train.csv", ["x"], [(1,)])
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sc.main(["--split", f"train={train}"]), 2)
            self.assertEqual(sc.main(["--split", f"train={train}", "--split",
                                      f"test={os.path.join(self.dir, 'missing.csv')}"]), 2)
            self.assertEqual(sc.main(["--split", f"train={train}", "--split", f"test={train}",
                                      "--target", "nope"]), 2)
            self.assertEqual(sc.main(["--split", "no-equals-sign"]), 2)

    def test_parse_time_forms(self):
        self.assertEqual(sc.parse_time("12.5"), 12.5)
        self.assertEqual(sc.parse_time("2024-01-01T00:00:00Z"), sc.parse_time("2024-01-01"))
        self.assertIsNotNone(sc.parse_time("2024-01-01 08:30:00"))
        self.assertIsNone(sc.parse_time("yesterday"))


if __name__ == "__main__":
    unittest.main()
