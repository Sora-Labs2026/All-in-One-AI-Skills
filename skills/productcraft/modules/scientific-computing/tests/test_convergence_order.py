"""Offline tests for convergence_order.py using manufactured power-law data."""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convergence_order.py"
spec = importlib.util.spec_from_file_location("convergence_order", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def power_law(hs, exact, constant, order):
    return [exact + constant * h ** order for h in hs]


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv)
        except SystemExit as exc:  # argparse usage errors and --help
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def csv(numbers):
    return ",".join(repr(x) for x in numbers)


class ObservedOrderTests(unittest.TestCase):
    def test_uniform_ratio_recovers_second_order_and_extrapolates(self):
        hs = [0.4, 0.2, 0.1]
        values = power_law(hs, 1.0, 0.5, 2.0)
        code, out, _ = run(["--h", csv(hs), "--values", csv(values), "--expected-order", "2", "--json"])
        self.assertEqual(code, 0)
        report = json.loads(out)
        triplet = report["triplets"][0]
        self.assertEqual(triplet["type"], "monotone")
        self.assertAlmostEqual(triplet["observed_order"], 2.0, places=6)
        self.assertAlmostEqual(triplet["extrapolated"], 1.0, places=9)
        self.assertEqual(report["verdict"], "PASS")

    def test_non_uniform_ratio_solved_by_iteration(self):
        hs = [0.3, 0.2, 0.1]  # ratios 1.5 and 2.0
        values = power_law(hs, 2.0, 3.0, 1.5)
        pairs = module.sort_fine_to_coarse(hs, values)
        triplet = module.triplet_analysis(pairs[0], pairs[1], pairs[2], 1.25)
        self.assertAlmostEqual(triplet["observed_order"], 1.5, places=6)
        self.assertAlmostEqual(triplet["extrapolated"], 2.0, places=8)

    def test_input_order_does_not_matter(self):
        hs = [0.1, 0.4, 0.2]
        values = power_law(hs, 1.0, 0.5, 2.0)
        code, out, _ = run(["--h", csv(hs), "--values", csv(values), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual([lvl["h"] for lvl in json.loads(out)["levels_fine_to_coarse"]], [0.1, 0.2, 0.4])

    def test_gci_matches_hand_calculation(self):
        hs = [0.04, 0.02, 0.01]
        values = [1.0128, 1.0032, 1.0008]
        pairs = module.sort_fine_to_coarse(hs, values)
        triplet = module.triplet_analysis(pairs[0], pairs[1], pairs[2], 1.25)
        expected_gci = 1.25 * abs((1.0008 - 1.0032) / 1.0008) / (2.0 ** 2 - 1.0)
        self.assertAlmostEqual(triplet["gci_fine"], expected_gci, places=12)
        self.assertGreater(triplet["asymptotic_ratio"], 0.95)
        self.assertLess(triplet["asymptotic_ratio"], 1.05)

    def test_four_levels_give_two_triplets(self):
        hs = [0.8, 0.4, 0.2, 0.1]
        code, out, _ = run(["--h", csv(hs), "--values", csv(power_law(hs, 0.0 + 5.0, 1.0, 1.0)), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["triplets"]), 2)

    def test_cells_and_dimension_give_spacing(self):
        hs = module.spacings_from_cells([1000, 8000, 64000], 3)
        self.assertAlmostEqual(hs[0] / hs[1], 2.0, places=9)
        self.assertAlmostEqual(hs[1] / hs[2], 2.0, places=9)
        code, _, _ = run(["--cells", "1000,8000,64000", "--dim", "3", "--values", "1.04,1.01,1.0025"])
        self.assertEqual(code, 0)


class ProblemDetectionTests(unittest.TestCase):
    def test_oscillatory_convergence_flagged(self):
        # fine 1.0, medium 1.02, coarse 0.96: changes alternate in sign and shrink
        code, out, _ = run(["--h", "0.025,0.05,0.1", "--values", "1.0,1.02,0.96", "--json"])
        self.assertEqual(code, 1)
        report = json.loads(out)
        self.assertEqual(report["triplets"][0]["type"], "oscillatory")
        self.assertEqual(report["verdict"], "CHECK")

    def test_divergence_flagged_without_error_band(self):
        # fine 1.5, medium 1.1, coarse 1.0: changes grow as the grid is refined
        code, out, _ = run(["--h", "0.025,0.05,0.1", "--values", "1.5,1.1,1.0", "--json"])
        self.assertEqual(code, 1)
        triplet = json.loads(out)["triplets"][0]
        self.assertEqual(triplet["type"], "divergent")
        self.assertNotIn("gci_fine", triplet)

    def test_expected_order_mismatch_fails(self):
        hs = [0.4, 0.2, 0.1]
        values = power_law(hs, 1.0, 0.5, 1.0)
        code, out, _ = run(["--h", csv(hs), "--values", csv(values), "--expected-order", "2"])
        self.assertEqual(code, 1)
        self.assertIn("differs from expected", out)

    def test_small_refinement_ratio_noted(self):
        hs = [0.12, 0.11, 0.10]
        values = power_law(hs, 1.0, 1.0, 2.0)
        pairs = module.sort_fine_to_coarse(hs, values)
        triplet = module.triplet_analysis(pairs[0], pairs[1], pairs[2], 1.25)
        self.assertTrue(any("below 1.3" in note for note in triplet["notes"]))

    def test_zero_value_reports_absolute_band(self):
        hs = [0.1, 0.2, 0.4]
        values = [0.0, 0.03, 0.15]  # changes 0.03 and 0.12: monotone, order 2
        pairs = module.sort_fine_to_coarse(hs, values)
        triplet = module.triplet_analysis(pairs[0], pairs[1], pairs[2], 1.25)
        self.assertNotIn("gci_fine", triplet)
        self.assertIn("abs_band_fine", triplet)


class ExactValueTests(unittest.TestCase):
    def test_fourth_order_against_exact(self):
        hs = [0.2, 0.1, 0.05, 0.025]
        values = power_law(hs, 3.0, -2.0, 4.0)
        code, out, _ = run(["--h", csv(hs), "--values", csv(values), "--exact", "3", "--expected-order", "4",
                            "--json"])
        self.assertEqual(code, 0)
        exact = json.loads(out)["exact_analysis"]
        self.assertAlmostEqual(exact["fitted_order"], 4.0, places=4)
        self.assertTrue(exact["errors_decrease"])

    def test_two_levels_with_exact_only(self):
        code, out, _ = run(["--h", "0.1,0.05", "--values", "1.01,1.0025", "--exact", "1", "--json"])
        self.assertEqual(code, 0)
        self.assertAlmostEqual(json.loads(out)["exact_analysis"]["pairwise_orders"][0], 2.0, places=6)

    def test_error_norm_mode_skips_gci(self):
        hs = [0.1, 0.05, 0.025, 0.0125]
        norms = [3.0 * h ** 2 for h in hs]
        code, out, _ = run(["--h", csv(hs), "--values", csv(norms), "--errors", "--expected-order", "2", "--json"])
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertNotIn("triplets", report)
        self.assertAlmostEqual(report["exact_analysis"]["fitted_order"], 2.0, places=6)

    def test_error_norm_mode_rejects_negative_and_exact(self):
        self.assertEqual(run(["--h", "0.1,0.05,0.025", "--values", "1e-2,-1e-3,1e-4", "--errors"])[0], 2)
        self.assertEqual(run(["--h", "0.1,0.05,0.025", "--values", "1e-2,1e-3,1e-4", "--errors",
                              "--exact", "0"])[0], 2)

    def test_errors_that_grow_fail(self):
        code, _, _ = run(["--h", "0.1,0.05", "--values", "1.01,1.02", "--exact", "1"])
        self.assertEqual(code, 1)


class TwoLevelAndUsageTests(unittest.TestCase):
    def test_two_levels_with_assumed_order_use_larger_safety_factor(self):
        code, out, _ = run(["--h", "0.1,0.05", "--values", "1.01,1.0025", "--assumed-order", "2", "--json"])
        self.assertEqual(code, 0)
        two = json.loads(out)["two_level"]
        self.assertEqual(two["safety_factor"], 3.0)
        self.assertAlmostEqual(two["extrapolated"], 1.0, places=9)

    def test_two_levels_without_order_is_usage_error(self):
        code, _, err = run(["--h", "0.1,0.05", "--values", "1.01,1.0025"])
        self.assertEqual(code, 2)
        self.assertIn("two levels need", err)

    def test_usage_errors(self):
        cases = [
            ["--h", "0.1,0.05,0.025", "--values", "1,2"],            # length mismatch
            ["--h", "0.1,0.1,0.05", "--values", "1,2,3"],            # duplicate spacing
            ["--h", "-0.1,0.05,0.025", "--values", "1,2,3"],         # negative spacing
            ["--h", "0.1,x,0.025", "--values", "1,2,3"],             # not a number
            ["--cells", "100,800,6400", "--values", "1,2,3"],        # cells without dim
            ["--h", "0.4,0.2,0.1", "--values", "1,2,3", "--safety-factor", "0.5"],
            ["--values", "1,2,3"],                                   # no spacing
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                code, _, _ = run(argv)
                self.assertEqual(code, 2)

    def test_help_exits_zero(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Richardson", out)

    def test_output_is_deterministic(self):
        argv = ["--h", "0.04,0.02,0.01", "--values", "1.0128,1.0032,1.0008", "--json"]
        self.assertEqual(run(argv)[1], run(argv)[1])


if __name__ == "__main__":
    unittest.main()
