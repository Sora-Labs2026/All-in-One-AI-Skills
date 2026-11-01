"""Offline tests for bench_compare.py; temporary files only, no network."""
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

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bench_compare.py"
spec = importlib.util.spec_from_file_location("bench_compare", SCRIPT)
bc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bc
spec.loader.exec_module(bc)

FAST = [11.2, 11.0, 11.5, 11.1, 11.3, 11.05, 11.4, 11.25, 11.15, 11.35, 11.22, 11.18]
SLOW = [12.1, 11.9, 12.4, 12.0, 12.2, 12.3, 11.8, 12.5, 12.15, 12.05, 12.12, 12.28]


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bc.main(argv)
    return code, out.getvalue(), err.getvalue()


def csv_list(values):
    return ",".join(str(v) for v in values)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return str(path)


class SpecialFunctions(unittest.TestCase):
    def test_t_quantiles_match_tables(self):
        self.assertAlmostEqual(bc.t_quantile(0.975, 10), 2.228139, places=5)
        self.assertAlmostEqual(bc.t_quantile(0.975, 1), 12.706205, places=4)
        self.assertAlmostEqual(bc.t_quantile(0.025, 30), -2.042272, places=5)

    def test_two_sided_p(self):
        self.assertAlmostEqual(bc.t_two_sided_p(2.0, 10), 0.073388, places=5)
        self.assertAlmostEqual(bc.t_two_sided_p(0.0, 7), 1.0, places=12)
        self.assertEqual(bc.t_two_sided_p(math.inf, 7), 0.0)

    def test_incomplete_beta_identities(self):
        for x in (0.1, 0.5, 0.9):
            self.assertAlmostEqual(bc.reg_inc_beta(1, 1, x), x, places=12)
            self.assertAlmostEqual(bc.reg_inc_beta(2, 1, x), x ** 2, places=12)
            self.assertAlmostEqual(bc.reg_inc_beta(2.5, 4, x) + bc.reg_inc_beta(4, 2.5, 1 - x), 1.0, places=12)

    def test_normal_two_sided(self):
        self.assertAlmostEqual(bc.normal_two_sided_p(1.959964), 0.05, places=5)


class Descriptive(unittest.TestCase):
    def test_quantiles_and_outliers(self):
        stats = bc.describe([1, 2, 3, 4, 100])
        self.assertEqual(stats["median"], 3)
        self.assertEqual(stats["q1"], 2)
        self.assertEqual(stats["q3"], 4)
        self.assertEqual(stats["outliers"], 1)
        self.assertAlmostEqual(stats["geometric_mean"], math.exp(sum(map(math.log, [1, 2, 3, 4, 100])) / 5))

    def test_average_ranks_with_ties(self):
        self.assertEqual(bc.ranks([10, 20, 20, 30]), [1.0, 2.5, 2.5, 4.0])

    def test_drift_correlation(self):
        self.assertAlmostEqual(bc.spearman_with_order(list(range(1, 11))), 1.0)
        self.assertAlmostEqual(bc.spearman_with_order(list(range(10, 0, -1))), -1.0)
        self.assertIsNone(bc.spearman_with_order([3, 3, 3, 3]))


class MannWhitney(unittest.TestCase):
    def test_exact_distribution_sums_to_binomial(self):
        for m, n in ((1, 1), (3, 3), (4, 7), (10, 10)):
            counts = bc.mann_whitney_counts(m, n)
            self.assertEqual(len(counts), m * n + 1)
            self.assertEqual(sum(counts), math.comb(m + n, m))
            self.assertTrue(all(c >= 0 for c in counts))
            self.assertEqual(counts, counts[::-1])     # symmetric

    def test_exact_complete_separation(self):
        result = bc.mann_whitney([1, 2, 3], [4, 5, 6])
        self.assertEqual(result["method"], "exact")
        self.assertEqual(result["u"], 9.0)
        self.assertAlmostEqual(result["p"], 2 / 20)
        result = bc.mann_whitney(list(range(1, 11)), list(range(11, 21)))
        self.assertAlmostEqual(result["p"], 2 / math.comb(20, 10), places=15)

    def test_identical_samples_not_significant(self):
        result = bc.mann_whitney([1, 2, 3, 4], [1, 2, 3, 4])
        self.assertEqual(result["method"], "normal approximation")   # ties force the approximation
        self.assertGreater(result["p"], 0.9)

    def test_all_values_equal(self):
        self.assertEqual(bc.mann_whitney([5, 5], [5, 5])["p"], 1.0)


class Comparisons(unittest.TestCase):
    def test_welch_ratio_direction(self):
        w = bc.welch_log(SLOW, FAST, 0.95)
        self.assertLess(w["ratio"], 1.0)
        self.assertLess(w["ci_high"], 1.0)
        self.assertLess(w["p"], 1e-6)
        self.assertLess(w["ci_low"], w["ratio"])

    def test_welch_zero_variance(self):
        w = bc.welch_log([5, 5, 5], [5, 5, 5], 0.95)
        self.assertEqual((w["ratio"], w["ci_low"], w["ci_high"], w["p"]), (1.0, 1.0, 1.0, 1.0))

    def test_bootstrap_deterministic_and_skippable(self):
        one = bc.bootstrap_median_ratio(SLOW, FAST, 0.95, 500, 7)
        two = bc.bootstrap_median_ratio(SLOW, FAST, 0.95, 500, 7)
        self.assertEqual(one, two)
        self.assertLess(one["ci_high"], 1.0)
        self.assertIsNone(bc.bootstrap_median_ratio(SLOW, FAST, 0.95, 0, 7))

    def test_verdict_rules(self):
        self.assertEqual(bc.verdict(0.90, 0.95, 0, False), "improvement")
        self.assertEqual(bc.verdict(1.02, 1.10, 0, False), "regression")
        self.assertEqual(bc.verdict(0.97, 1.02, 0, False), "no significant difference")
        self.assertEqual(bc.verdict(0.99, 1.01, 2, False), "equivalent")
        self.assertEqual(bc.verdict(0.96, 0.99, 2, False), "inconclusive")
        self.assertEqual(bc.verdict(0.90, 0.95, 2, False), "improvement")
        self.assertEqual(bc.verdict(1.05, 1.10, 2, True), "improvement")
        self.assertEqual(bc.verdict(0.90, 0.95, 0, True), "regression")


class Inputs(TempDirCase):
    def test_plain_text_with_comments(self):
        path = self.write("a.txt", "# seconds\n1.5\n\n1.6, 1.7  # warm\n1.8 1.9\n")
        self.assertEqual(bc.load_sample(path, None, None, ","), [1.5, 1.6, 1.7, 1.8, 1.9])

    def test_hyperfine_selection_by_index_and_command(self):
        data = {"results": [{"command": "old", "times": [1.0, 1.1]}, {"command": "new", "times": [0.9, 0.8]}]}
        path = self.write("h.json", json.dumps(data))
        self.assertEqual(bc.load_sample(path, "1", None, ","), [0.9, 0.8])
        self.assertEqual(bc.load_sample(path, "old", None, ","), [1.0, 1.1])
        with self.assertRaises(bc.InputError):
            bc.load_sample(path, None, None, ",")
        with self.assertRaises(bc.InputError):
            bc.load_sample(path, "missing", None, ",")

    def test_pytest_benchmark_needs_raw_data(self):
        good = {"benchmarks": [{"name": "test_parse", "stats": {"data": [0.01, 0.02]}}]}
        bad = {"benchmarks": [{"name": "test_parse", "stats": {"mean": 0.015}}]}
        self.assertEqual(bc.load_sample(self.write("g.json", json.dumps(good)), None, None, ","), [0.01, 0.02])
        with self.assertRaises(bc.InputError):
            bc.load_sample(self.write("b.json", json.dumps(bad)), None, None, ",")

    def test_csv_column(self):
        path = self.write("r.csv", "run,seconds\n1,2.5\n2,2.4\n3,\n")
        self.assertEqual(bc.load_sample(path, None, "seconds", ","), [2.5, 2.4])
        with self.assertRaises(bc.InputError):
            bc.load_sample(path, None, None, ",")
        with self.assertRaises(bc.InputError):
            bc.load_sample(path, None, "ms", ",")

    def test_bad_inputs(self):
        with self.assertRaises(bc.InputError):
            bc.load_sample(str(self.dir / "missing.txt"), None, None, ",")
        with self.assertRaises(bc.InputError):
            bc.load_sample(self.write("x.txt", "1.0\nabc\n"), None, None, ",")
        with self.assertRaises(bc.InputError):
            bc.load_sample(self.write("n.txt", "1.0\nnan\n"), None, None, ",")
        with self.assertRaises(bc.InputError):
            bc.load_sample(self.write("j.json", "{broken"), None, None, ",")


class CommandLine(TempDirCase):
    def test_help_exits_zero(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Exit codes", out)

    def test_improvement_text_report(self):
        code, out, err = run(["--a-values", csv_list(SLOW), "--b-values", csv_list(FAST)])
        self.assertEqual(code, 0, err)
        self.assertIn("Verdict: improvement", out)
        self.assertIn("ratio of geometric means", out)

    def test_regression_gate(self):
        args = ["--a-values", csv_list(FAST), "--b-values", csv_list(SLOW)]
        self.assertEqual(run(args)[0], 0)
        code, out, _ = run(args + ["--fail-on-regression"])
        self.assertEqual(code, 1)
        self.assertIn("regression", out)

    def test_require_improvement(self):
        same = csv_list(FAST)
        code, _, _ = run(["--a-values", same, "--b-values", same, "--require-improvement"])
        self.assertEqual(code, 1)

    def test_higher_is_better_flips(self):
        code, out, _ = run(["--a-values", csv_list(FAST), "--b-values", csv_list(SLOW), "--higher-is-better",
                            "--fail-on-regression"])
        self.assertEqual(code, 0)
        self.assertIn("Verdict: improvement", out)

    def test_equivalence_with_threshold(self):
        base = [10.0 + 0.01 * (i % 5) for i in range(40)]
        cand = [10.0 + 0.01 * ((i + 2) % 5) for i in range(40)]
        code, out, _ = run(["--a-values", csv_list(base), "--b-values", csv_list(cand), "--threshold", "2"])
        self.assertEqual(code, 0)
        self.assertIn("Verdict: equivalent", out)

    def test_json_output_and_determinism(self):
        args = ["--a-values", csv_list(SLOW), "--b-values", csv_list(FAST), "--json", "--bootstrap", "300"]
        first, second = run(args), run(args)
        self.assertEqual(first, second)
        data = json.loads(first[1])
        self.assertEqual(data["verdict"], "improvement")
        for key in ("welch_log", "mann_whitney", "bootstrap_median_ratio", "baseline", "candidate", "hints"):
            self.assertIn(key, data)

    def test_json_with_infinite_t_is_valid(self):
        code, out, _ = run(["--a-values", "5,5,5", "--b-values", "4,4,4", "--json", "--bootstrap", "0"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["welch_log"]["t"], "-inf")
        self.assertEqual(data["verdict"], "improvement")

    def test_drop_first_and_drift_hint(self):
        warm = [20.0, 18.0, 16.0, 14.0, 12.0] + [10.0 + 0.01 * (i % 3) for i in range(12)]
        code, out, _ = run(["--a-values", csv_list(warm), "--b-values", csv_list(warm)])
        self.assertEqual(code, 0)
        self.assertIn("run order", out)
        code, out, _ = run(["--a-values", csv_list(warm), "--b-values", csv_list(warm), "--drop-first", "5"])
        self.assertNotIn("run order", out)
        self.assertIn("dropped the first 5", out)

    def test_hyperfine_two_commands_same_file(self):
        data = {"results": [{"command": "old", "times": SLOW}, {"command": "new", "times": FAST}]}
        path = self.write("bench.json", json.dumps(data))
        code, out, err = run([path, path, "--select-a", "0", "--select-b", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn("Verdict: improvement", out)
        code, _, err = run([path, path])
        self.assertEqual(code, 2)
        self.assertIn("--select-a", err)

    def test_files_and_usage_errors(self):
        a = self.write("a.txt", "\n".join(map(str, SLOW)))
        b = self.write("b.txt", "\n".join(map(str, FAST)))
        self.assertEqual(run([a, b])[0], 0)
        self.assertEqual(run([a])[0], 2)
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run([a, b, "--level", "1.5"])[0], 2)
        self.assertEqual(run([a, b, "--drop-first", "50"])[0], 2)
        self.assertEqual(run(["--a-values", "1,0,2", "--b-values", "1,2,3"])[0], 2)
        self.assertEqual(run(["--a-values", "1", "--b-values", "1,2"])[0], 2)
        self.assertEqual(run([a, b, "--unknown-flag"])[0], 2)

    def test_script_runs_as_subprocess(self):
        import subprocess
        proc = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), "--a-values", csv_list(SLOW),
                               "--b-values", csv_list(FAST), "--fail-on-regression"],
                              capture_output=True, text=True, timeout=60, env={**os.environ, "PYTHONHASHSEED": "0"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("improvement", proc.stdout)


if __name__ == "__main__":
    unittest.main()
