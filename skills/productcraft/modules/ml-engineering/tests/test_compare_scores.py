"""Offline tests for compare_scores.py; temporary files only, no network."""
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

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_scores.py"
spec = importlib.util.spec_from_file_location("compare_scores", SCRIPT)
cs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cs
spec.loader.exec_module(cs)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cs.main(argv)
    return code, out.getvalue(), err.getvalue()


class SpecialFunctions(unittest.TestCase):
    def test_t_quantiles_match_tables(self):
        self.assertAlmostEqual(cs.t_quantile(0.975, 10), 2.228139, places=5)
        self.assertAlmostEqual(cs.t_quantile(0.975, 1), 12.706205, places=4)
        self.assertAlmostEqual(cs.t_quantile(0.995, 30), 2.749996, places=5)
        self.assertAlmostEqual(cs.t_quantile(0.025, 10), -2.228139, places=5)

    def test_two_sided_p(self):
        self.assertAlmostEqual(cs.t_sf_two_sided(2.0, 10), 0.073388, places=5)
        self.assertAlmostEqual(cs.t_sf_two_sided(0.0, 5), 1.0, places=12)

    def test_betainc_identities(self):
        for x in (0.1, 0.5, 0.9):
            self.assertAlmostEqual(cs.betainc(1, 1, x), x, places=12)
            self.assertAlmostEqual(cs.betainc(3, 1, x), x ** 3, places=12)
            self.assertAlmostEqual(cs.betainc(2.5, 4, x) + cs.betainc(4, 2.5, 1 - x), 1.0, places=12)

    def test_exact_binomial(self):
        self.assertAlmostEqual(cs.binom_two_sided_half(1, 10), 22 / 1024, places=12)
        self.assertEqual(cs.binom_two_sided_half(5, 10), 1.0)
        self.assertEqual(cs.binom_two_sided_half(0, 0), 1.0)
        tiny = cs.binom_two_sided_half(0, 1000)
        self.assertAlmostEqual(tiny / (2.0 * 2.0 ** -1000), 1.0, places=9)
        self.assertAlmostEqual(cs.binom_two_sided_half(480, 1000), cs.binom_two_sided_half(520, 1000), places=12)


class MultipleTesting(unittest.TestCase):
    def test_holm_and_bh_known_values(self):
        p = [0.01, 0.04, 0.03]
        self.assertEqual([round(v, 10) for v in cs.holm(p)], [0.03, 0.06, 0.06])
        self.assertEqual([round(v, 10) for v in cs.benjamini_hochberg(p)], [0.03, 0.04, 0.04])

    def test_adjusted_never_below_raw_and_capped(self):
        p = [0.5, 0.9, 0.001, 0.2]
        for adj in (cs.holm(p), cs.benjamini_hochberg(p)):
            for raw, a in zip(p, adj):
                self.assertGreaterEqual(a, raw)
                self.assertLessEqual(a, 1.0)

    def test_adjust_cli(self):
        code, out, _ = run(["adjust", "--p", "0.01,0.04,0.03,0.2", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["result"]["holm_rejections"], 1)
        self.assertEqual(data["result"]["m"], 4)

    def test_adjust_rejects_out_of_range(self):
        code, _, err = run(["adjust", "--p", "0.2,1.5"])
        self.assertEqual(code, 2)
        self.assertIn("[0, 1]", err)


class CorrectedTTest(unittest.TestCase):
    A = [0.81, 0.79, 0.83, 0.80, 0.82]
    B = [0.84, 0.80, 0.85, 0.83, 0.83]

    def test_matches_hand_computation(self):
        r = cs.corrected_resampled_t(self.A, self.B, 0.25)
        self.assertAlmostEqual(r["mean_diff_b_minus_a"], 0.02, places=12)
        self.assertAlmostEqual(r["se"], math.sqrt((1 / 5 + 0.25) * 0.0001), places=12)
        self.assertAlmostEqual(r["t"], 0.02 / math.sqrt(0.000045), places=9)
        self.assertEqual(r["df"], 4)
        self.assertGreater(r["se"], r["naive_se_for_contrast"])

    def test_cli_folds_and_gate(self):
        code, out, _ = run(["cv", "--a", ",".join(map(str, self.A)), "--b", ",".join(map(str, self.B)),
                            "--folds", "5", "--json", "--require-improvement"])
        self.assertEqual(code, 0)
        self.assertGreater(json.loads(out)["result"]["ci"][0], 0)
        code, _, _ = run(["cv", "--a", ",".join(map(str, self.A)), "--b", ",".join(map(str, self.B)),
                          "--folds", "5", "--require-improvement", "--lower-is-better"])
        self.assertEqual(code, 1)

    def test_zero_variance_is_reported_not_crashing(self):
        r = cs.corrected_resampled_t([0.5, 0.6], [0.6, 0.7], 0.25)
        self.assertIsNone(r["t"])
        self.assertIn("undefined", r["note"])

    def test_requires_correction_information(self):
        code, _, err = run(["cv", "--a", "0.1,0.2", "--b", "0.2,0.3"])
        self.assertEqual(code, 2)
        self.assertIn("--folds", err)

    def test_unpaired_lengths_rejected(self):
        code, _, err = run(["cv", "--a", "0.1,0.2,0.3", "--b", "0.2,0.3", "--folds", "3"])
        self.assertEqual(code, 2)
        self.assertIn("paired", err)


class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_deterministic_with_seed(self):
        a = [0.0, 1.0] * 50
        b = [1.0, 1.0] * 50
        r1 = cs.paired_bootstrap(a, b, None, 500, 7, 0.95)
        r2 = cs.paired_bootstrap(a, b, None, 500, 7, 0.95)
        self.assertEqual(r1["ci"], r2["ci"])
        self.assertAlmostEqual(r1["mean_diff_b_minus_a"], 0.5)
        self.assertLessEqual(r1["ci"][0], 0.5)
        self.assertGreaterEqual(r1["ci"][1], 0.5)

    def test_cluster_interval_is_wider_for_clustered_effects(self):
        # 10 clusters of 20 rows; the effect is shared within a cluster.
        a, b, clusters = [], [], []
        for c in range(10):
            effect = 1.0 if c % 2 else -0.6
            for _ in range(20):
                a.append(0.0)
                b.append(effect)
                clusters.append(f"c{c}")
        plain = cs.paired_bootstrap(a, b, None, 1000, 1, 0.95)
        clustered = cs.paired_bootstrap(a, b, clusters, 1000, 1, 0.95)
        width = lambda r: r["ci"][1] - r["ci"][0]  # noqa: E731
        self.assertGreater(width(clustered), width(plain))

    def test_single_file_cli_with_gate(self):
        rows = "id,a,b\n" + "".join(f"{i},{0.5},{0.9}\n" for i in range(40))
        path = self.write("pe.csv", rows)
        code, out, _ = run(["bootstrap", "--csv", path, "--a-col", "a", "--b-col", "b",
                            "--resamples", "300", "--require-improvement", "--json"])
        self.assertEqual(code, 0)
        self.assertAlmostEqual(json.loads(out)["result"]["mean_diff_b_minus_a"], 0.4)

    def test_two_file_mode_requires_same_keys(self):
        a = self.write("a.csv", "query,score\nq1,0.1\nq2,0.2\n")
        b = self.write("b.csv", "query,score\nq1,0.3\nq3,0.2\n")
        code, _, err = run(["bootstrap", "--a-csv", a, "--b-csv", b, "--key", "query", "--value", "score"])
        self.assertEqual(code, 2)
        self.assertIn("only one file", err)

    def test_missing_column_is_input_error(self):
        path = self.write("x.csv", "a,b\n1,2\n3,4\n")
        code, _, err = run(["bootstrap", "--csv", path, "--a-col", "a", "--b-col", "nope"])
        self.assertEqual(code, 2)
        self.assertIn("not found", err)


class McNemar(unittest.TestCase):
    def test_counts_and_exact_p(self):
        a = [1] * 50 + [1] * 1 + [0] * 9 + [0] * 40
        b = [1] * 50 + [0] * 1 + [1] * 9 + [0] * 40
        r = cs.mcnemar(a, b)
        self.assertEqual((r["only_a_correct"], r["only_b_correct"], r["discordant"]), (1, 9, 10))
        self.assertAlmostEqual(r["p_two_sided_exact"], 22 / 1024, places=12)

    def test_cli_rejects_non_binary(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("a,b\n1,0\nmaybe,1\n")
            code, _, err = run(["mcnemar", "--csv", path, "--a-col", "a", "--b-col", "b"])
        self.assertEqual(code, 2)
        self.assertIn("0/1", err)


class Cli(unittest.TestCase):
    def test_help_exits_zero(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("B - A", out)

    def test_unknown_command_exits_two(self):
        code, _, _ = run(["frobnicate"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
