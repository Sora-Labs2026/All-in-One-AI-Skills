"""Offline tests for rank_metrics.py; temporary files only, no network."""
import contextlib
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rank_metrics.py"
spec = importlib.util.spec_from_file_location("rank_metrics", SCRIPT)
rm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rm
spec.loader.exec_module(rm)


class PerQuery(unittest.TestCase):
    def test_binary_metrics_by_hand(self):
        m = rm.per_query({"d3": 1.0, "d9": 1.0}, ["d3", "d4", "d9"], 3, "exp")
        self.assertEqual(m["hit"], 1.0)
        self.assertAlmostEqual(m["precision"], 2 / 3)
        self.assertEqual(m["recall"], 1.0)
        self.assertEqual(m["mrr"], 1.0)
        self.assertAlmostEqual(m["ndcg"], 1.5 / (1 + 1 / math.log2(3)))
        self.assertAlmostEqual(m["map"], (1 + 2 / 3) / 2)

    def test_graded_ndcg_exp_and_linear(self):
        rel = {"d1": 3.0, "d2": 1.0}
        exp = rm.per_query(rel, ["d2", "d1"], 2, "exp")["ndcg"]
        self.assertAlmostEqual(exp, (1 + 7 / math.log2(3)) / (7 + 1 / math.log2(3)))
        lin = rm.per_query(rel, ["d2", "d1"], 2, "linear")["ndcg"]
        self.assertAlmostEqual(lin, (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3)))

    def test_miss_and_short_lists(self):
        m = rm.per_query({"a": 1.0}, ["x"], 5, "exp")
        self.assertEqual((m["hit"], m["mrr"], m["ndcg"], m["map"], m["recall"]), (0.0, 0.0, 0.0, 0.0, 0.0))
        self.assertEqual(m["precision"], 0.0)
        m = rm.per_query({"a": 1.0}, ["a"], 5, "exp")
        self.assertAlmostEqual(m["precision"], 1 / 5)
        self.assertEqual(m["ndcg"], 1.0)

    def test_map_normalized_by_min_k_relevant(self):
        rel = {f"r{i}": 1.0 for i in range(10)}
        m = rm.per_query(rel, ["r0", "r1"], 2, "exp")
        self.assertEqual(m["map"], 1.0)
        self.assertAlmostEqual(m["recall"], 0.2)


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "run.jsonl")
        lines = [
            {"query": "q1", "relevant": ["d3", "d9"], "retrieved": ["d3", "d4", "d9"]},
            {"query": "q2", "relevant": {"d1": 3, "d2": 1}, "retrieved": ["d2", "d1", "d2"]},
            {"query": "q3", "relevant": [], "retrieved": ["d5"]},
        ]
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(x) for x in lines) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rm.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_summary_counts_skips_and_duplicates(self):
        code, out, err = self.run_cli(self.path, "--k", "3", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["queries_scored"], 2)
        self.assertEqual(data["queries_without_relevant"], 1)
        self.assertEqual(data["duplicate_retrieved_dropped"], 1)
        self.assertAlmostEqual(data["metrics"]["precision@3"]["mean"], 2 / 3)
        self.assertIn("no relevant item", err)

    def test_threshold_gate(self):
        code, out, _ = self.run_cli(self.path, "--k", "3", "--min", "recall@3=0.9")
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli(self.path, "--k", "3", "--min", "ndcg@3=0.9")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)

    def test_ci_is_deterministic_and_brackets_mean(self):
        _, out1, _ = self.run_cli(self.path, "--k", "3", "--ci", "--resamples", "300", "--json")
        _, out2, _ = self.run_cli(self.path, "--k", "3", "--ci", "--resamples", "300", "--json")
        self.assertEqual(out1, out2)
        entry = json.loads(out1)["metrics"]["ndcg@3"]
        self.assertLessEqual(entry["ci"][0], entry["mean"])
        self.assertGreaterEqual(entry["ci"][1], entry["mean"])

    def test_per_query_csv(self):
        code, out, _ = self.run_cli(self.path, "--k", "3", "--per-query")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertTrue(lines[0].startswith("query,relevant,retrieved,hit@3"))
        self.assertEqual(len(lines), 3)

    def test_coverage(self):
        code, out, _ = self.run_cli(self.path, "--k", "1", "--catalog-size", "10", "--json")
        self.assertEqual(json.loads(out)["metrics"]["coverage@1"]["mean"], 0.2)

    def test_bad_input(self):
        bad = os.path.join(self.tmp.name, "bad.jsonl")
        with open(bad, "w", encoding="utf-8") as handle:
            handle.write("{not json}\n")
        self.assertEqual(self.run_cli(bad)[0], 2)
        self.assertEqual(self.run_cli(self.path, "--k", "0")[0], 2)
        self.assertEqual(self.run_cli(self.path, "--k", "3", "--min", "ndcg@5=0.1")[0], 2)
        self.assertEqual(self.run_cli(self.path, "--min", "bogus@3=1")[0], 2)
        dup = os.path.join(self.tmp.name, "dup.jsonl")
        with open(dup, "w", encoding="utf-8") as handle:
            handle.write('{"query": "a", "relevant": ["x"], "retrieved": []}\n' * 2)
        self.assertEqual(self.run_cli(dup)[0], 2)

    def test_help(self):
        code, out, _ = self.run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("nDCG", out)


if __name__ == "__main__":
    unittest.main()
