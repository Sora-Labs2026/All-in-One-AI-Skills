"""Offline tests for reorder_point.py using synthetic CSV files in a temporary folder."""
import importlib.util
import io
import json
import math
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from statistics import NormalDist

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reorder_point.py"
spec = importlib.util.spec_from_file_location("reorder_point", SCRIPT)
rp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rp
spec.loader.exec_module(rp)

Z95 = NormalDist().inv_cdf(0.95)


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = rp.main([str(a) for a in args])
        except SystemExit as exc:  # argparse --help, --version and usage errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def demand_csv(series, start_week=1):
    """series: {sku: [qty or None for a missing row, ...]} -> CSV text with ISO week labels."""
    lines = ["sku,period,quantity"]
    for sku, values in series.items():
        for offset, qty in enumerate(values):
            if qty is not None:
                lines.append(f"{sku},2026-W{start_week + offset:02d},{qty}")
    return "\n".join(lines) + "\n"


class TempFiles(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text, encoding="utf-8"):
        path = self.dir / name
        path.write_text(text, encoding=encoding)
        return path

    def report(self, *args, expect=(0,)):
        code, out, err = run_cli(*args, "--json")
        self.assertIn(code, expect, err)
        return json.loads(out)

    @staticmethod
    def item(report, sku):
        return next(it for it in report["items"] if it["sku"] == sku)


class SafetyStockTests(TempFiles):
    def test_continuous_review_matches_formula(self):
        values = [10, 12, 8, 11, 9, 10, 10, 12, 8, 11, 9, 10]
        path = self.write("d.csv", demand_csv({"A": values}))
        it = self.item(self.report(path, "--lead-time", 2), "A")
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        ss = Z95 * sd * math.sqrt(2)
        self.assertAlmostEqual(it["safety_stock"], round(ss, 3), places=3)
        self.assertAlmostEqual(it["reorder_point"], round(mean * 2 + ss, 3), places=3)
        self.assertEqual(it["policy"], "continuous")
        self.assertIsNone(it["order_up_to"])

    def test_lead_time_variability_increases_safety_stock(self):
        values = [10, 12, 8, 11, 9, 10] * 2
        path = self.write("d.csv", demand_csv({"A": values}))
        base = self.item(self.report(path, "--lead-time", 2), "A")
        varied = self.item(self.report(path, "--lead-time", 2, "--lead-time-sd", 0.5), "A")
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        expected = Z95 * math.sqrt(2 * sd ** 2 + mean ** 2 * 0.25)
        self.assertAlmostEqual(varied["safety_stock"], round(expected, 3), places=3)
        self.assertGreater(varied["safety_stock"], base["safety_stock"])

    def test_periodic_review_uses_protection_interval(self):
        values = [20] * 6 + [24] * 6
        demand = self.write("d.csv", demand_csv({"A": values}))
        position = self.write("p.csv", "sku,on_hand,on_order,backorders,committed\nA,30,10,5,5\n")
        it = self.item(self.report(demand, "--lead-time", 2, "--review-period", 1, "--position", position), "A")
        mean = 22.0
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / 11)
        ss = Z95 * sd * math.sqrt(3)
        self.assertEqual(it["policy"], "periodic")
        self.assertIsNone(it["reorder_point"])
        self.assertAlmostEqual(it["order_up_to"], round(mean * 3 + ss, 3), places=3)
        self.assertEqual(it["inventory_position"], 30.0)
        self.assertAlmostEqual(it["suggested_order"], round(mean * 3 + ss - 30, 3), places=3)

    def test_inventory_position_drives_reorder_flag(self):
        demand = self.write("d.csv", demand_csv({"A": [10] * 12, "B": [10] * 12}))
        position = self.write("p.csv", "sku,on_hand,on_order,backorders,committed\nA,15,0,0,0\nB,15,10,0,0\n")
        report = self.report(demand, "--lead-time", 2, "--position", position)
        # constant demand: sd 0, ROP = 20
        self.assertEqual(self.item(report, "A")["reorder_point"], 20.0)
        self.assertTrue(self.item(report, "A")["reorder_now"])
        self.assertFalse(self.item(report, "B")["reorder_now"])

    def test_service_level_half_gives_zero_safety_stock(self):
        path = self.write("d.csv", demand_csv({"A": [5, 15] * 6}))
        it = self.item(self.report(path, "--lead-time", 1, "--service-level", 0.5), "A")
        self.assertEqual(it["safety_stock"], 0.0)
        self.assertEqual(it["reorder_point"], 10.0)

    def test_params_override_defaults_per_item(self):
        demand = self.write("d.csv", demand_csv({"A": [10] * 12, "B": [10] * 12}))
        params = self.write("params.csv", "sku,lead_time,review_period,service_level\nB,4,,0.99\n")
        report = self.report(demand, "--lead-time", 2, "--params", params)
        self.assertEqual(self.item(report, "A")["lead_time"], 2.0)
        self.assertEqual(self.item(report, "B")["lead_time"], 4.0)
        self.assertEqual(self.item(report, "B")["service_level"], 0.99)
        self.assertEqual(self.item(report, "B")["reorder_point"], 40.0)

    def test_missing_lead_time_leaves_safety_stock_empty(self):
        path = self.write("d.csv", demand_csv({"A": [10] * 12}))
        it = self.item(self.report(path), "A")
        self.assertIsNone(it["safety_stock"])
        self.assertTrue(any("no lead time" in w for w in it["warnings"]))


class SeriesTests(TempFiles):
    def test_missing_periods_inside_history_are_zero_and_leading_ones_skipped(self):
        # A sells every week from W01; B starts in W03 and skips W05.
        text = demand_csv({"A": [4] * 8, "B": [None, None, 6, 6, None, 6, 6, 6]})
        report = self.report(self.write("d.csv", text), "--lead-time", 1)
        b = self.item(report, "B")
        self.assertEqual(b["periods"], 6)
        self.assertEqual(b["filled_zero_periods"], 1)
        self.assertAlmostEqual(b["mean"], 5.0)

    def test_trailing_periods_after_last_sale_count_as_zero(self):
        text = demand_csv({"A": [4] * 8, "B": [9, 9, 9, 9]})
        b = self.item(self.report(self.write("d.csv", text), "--lead-time", 1), "B")
        self.assertEqual(b["periods"], 8)
        self.assertEqual(b["filled_zero_periods"], 4)

    def test_duplicate_rows_in_a_period_are_summed(self):
        text = "sku,period,quantity\nA,2026-01,3\nA,2026-01,4\nA,2026-02,7\n"
        a = self.item(self.report(self.write("d.csv", text), "--lead-time", 1), "A")
        self.assertEqual(a["total"], 14.0)
        self.assertEqual(a["periods"], 2)
        self.assertEqual(a["sd"], 0.0)

    def test_header_with_bom_spaces_and_capitals(self):
        text = "﻿ SKU , Period ,Quantity\nA,2026-01,3\nA,2026-02,5\n"
        a = self.item(self.report(self.write("d.csv", text), "--lead-time", 1), "A")
        self.assertEqual(a["total"], 8.0)

    def test_semicolon_delimiter(self):
        text = "sku;period;quantity\nA;2026-01;3\nA;2026-02;5\n"
        a = self.item(self.report(self.write("d.csv", text), "--lead-time", 1, "--delimiter", ";"), "A")
        self.assertEqual(a["total"], 8.0)


class ClassificationTests(TempFiles):
    def test_demand_patterns(self):
        series = {
            "SMOOTH": [10, 11, 9, 10, 12, 8, 10, 11, 9, 10, 10, 10],
            "ERRATIC": [2, 40, 3, 35, 1, 50, 2, 45, 3, 30, 2, 40],
            "INTERMIT": [0, 0, 5, 0, 0, 5, 0, 0, 6, 0, 0, 5],
            "LUMPY": [0, 0, 1, 0, 0, 40, 0, 0, 2, 0, 0, 60],
        }
        # explicit zero rows count as observed periods, so the leading zeros are kept
        text = demand_csv(series)
        report = self.report(self.write("d.csv", text), "--lead-time", 1, expect=(0,))
        self.assertEqual(self.item(report, "SMOOTH")["pattern"], "smooth")
        self.assertEqual(self.item(report, "ERRATIC")["pattern"], "erratic")
        self.assertEqual(self.item(report, "INTERMIT")["pattern"], "intermittent")
        self.assertEqual(self.item(report, "LUMPY")["pattern"], "lumpy")
        self.assertTrue(any("normal approximation" in w for w in self.item(report, "LUMPY")["warnings"]))

    def test_abc_by_value_when_every_item_has_a_cost(self):
        demand = self.write("d.csv", demand_csv({"A": [100] * 12, "B": [10] * 12, "C": [1] * 12}))
        params = self.write("p.csv", "sku,unit_cost\nA,1\nB,50\nC,1\n")
        report = self.report(demand, "--lead-time", 1, "--params", params)
        self.assertEqual(report["settings"]["abc_basis"], "value")
        self.assertEqual(self.item(report, "B")["abc"], "A")   # value 6000 ranks first
        self.assertEqual(self.item(report, "A")["abc"], "B")   # share before it is 6000/7212 = 0.83
        self.assertEqual(self.item(report, "C")["abc"], "C")

    def test_abc_falls_back_to_quantity_with_partial_costs(self):
        demand = self.write("d.csv", demand_csv({"A": [100] * 12, "B": [10] * 12}))
        params = self.write("p.csv", "sku,unit_cost\nB,50\n")
        report = self.report(demand, "--lead-time", 1, "--params", params)
        self.assertEqual(report["settings"]["abc_basis"], "quantity")
        self.assertEqual(self.item(report, "A")["abc"], "A")
        self.assertTrue(any("unit_cost is missing" in w for w in report["warnings"]))

    def test_xyz_cutoffs(self):
        demand = self.write("d.csv", demand_csv({"X1": [10] * 12, "Y1": [5, 15] * 6, "Z1": [0, 30] * 6}))
        report = self.report(demand, "--lead-time", 1)
        self.assertEqual(self.item(report, "X1")["xyz"], "X")
        self.assertEqual(self.item(report, "Y1")["xyz"], "Y")
        self.assertEqual(self.item(report, "Z1")["xyz"], "Z")


class WarningAndExitTests(TempFiles):
    def test_bad_rows_are_skipped_and_reported(self):
        text = "sku,period,quantity\nA,2026-01,3\nA,2026-02,lots\n,2026-03,4\nA,2026-03,5\n"
        path = self.write("d.csv", text)
        report = self.report(path, "--lead-time", 1, "--min-periods", 1)
        self.assertTrue(any("2 demand row(s) skipped" in w for w in report["warnings"]))
        code, _, _ = run_cli(path, "--lead-time", 1, "--min-periods", 1, "--strict")
        self.assertEqual(code, 1)

    def test_clean_input_with_strict_exits_zero(self):
        path = self.write("d.csv", demand_csv({"A": [10, 11, 9, 10] * 3}))
        code, out, err = run_cli(path, "--lead-time", 1, "--strict")
        self.assertEqual(code, 0, out + err)

    def test_negative_quantities_and_mixed_period_labels_warn(self):
        text = "sku,period,quantity\nA,2026-01,5\nA,2026-02,-2\nA,2026-3,4\n"
        report = self.report(self.write("d.csv", text), "--lead-time", 1)
        joined = " ".join(report["warnings"])
        self.assertIn("negative quantities", joined)
        self.assertIn("different lengths", joined)

    def test_missing_column_is_usage_error(self):
        path = self.write("d.csv", "sku,qty\nA,1\n")
        code, _, err = run_cli(path, "--lead-time", 1)
        self.assertEqual(code, 2)
        self.assertIn("missing column", err)

    def test_missing_file_is_usage_error(self):
        code, _, err = run_cli(self.dir / "absent.csv", "--lead-time", 1)
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_invalid_arguments_are_usage_errors(self):
        path = self.write("d.csv", demand_csv({"A": [1] * 12}))
        for extra in (["--service-level", "1"], ["--service-level", "0.4"], ["--lead-time", "-1"],
                      ["--abc", "0.9,0.8"], ["--xyz", "abc"], ["--delimiter", ";;"]):
            with self.subTest(extra=extra):
                code, _, _ = run_cli(path, *extra)
                self.assertEqual(code, 2)

    def test_invalid_params_value_is_usage_error(self):
        demand = self.write("d.csv", demand_csv({"A": [1] * 12}))
        params = self.write("p.csv", "sku,lead_time\nA,soon\n")
        code, _, err = run_cli(demand, "--params", params)
        self.assertEqual(code, 2)
        self.assertIn("lead_time", err)

    def test_help_and_version(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("Exit codes", out)
        code, out, _ = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn(rp.VERSION, out)


class OutputTests(TempFiles):
    def test_output_is_deterministic(self):
        path = self.write("d.csv", demand_csv({"B": [3, 4, 5] * 4, "A": [9, 0, 7] * 4}))
        first = run_cli(path, "--lead-time", 2, "--json")
        second = run_cli(path, "--lead-time", 2, "--json")
        self.assertEqual(first, second)
        skus = [it["sku"] for it in json.loads(first[1])["items"]]
        self.assertEqual(skus, ["A", "B"])

    def test_text_report_shows_table_and_action(self):
        demand = self.write("d.csv", demand_csv({"A": [10] * 12}))
        position = self.write("p.csv", "sku,on_hand\nA,5\n")
        code, out, _ = run_cli(demand, "--lead-time", 2, "--position", position)
        self.assertEqual(code, 0)
        self.assertIn("rop/S", out)
        self.assertIn("reorder", out)
        self.assertIn("cycle service level", out)

    def test_script_does_not_write_files(self):
        demand = self.write("d.csv", demand_csv({"A": [10] * 12}))
        before = sorted(p.name for p in self.dir.iterdir())
        run_cli(demand, "--lead-time", 2)
        self.assertEqual(before, sorted(p.name for p in self.dir.iterdir()))


if __name__ == "__main__":
    unittest.main()
