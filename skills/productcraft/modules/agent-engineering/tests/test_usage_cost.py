"""Offline tests for usage_cost.py using synthetic usage logs and price files; no network."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "usage_cost.py"
spec = importlib.util.spec_from_file_location("usage_cost", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

PRICES = {
    "as_of": "2026-10-01", "source": "synthetic test table", "currency": "USD",
    "models": {
        "model-a": {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.3},
        "family-*": {"input": 1, "output": 5},
        "family-large*": {"input": 10, "output": 50},
    },
}


def separate(session, ts, model, inp, out, write=0, read=0, **extra):
    rec = {"timestamp": ts, "session_id": session, "model": model,
           "usage": {"input_tokens": inp, "output_tokens": out,
                     "cache_creation_input_tokens": write, "cache_read_input_tokens": read}}
    rec.update(extra)
    return rec


class Workspace:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def log(self, records, name="usage.jsonl", extra_lines=()):
        path = self.dir / name
        lines = [json.dumps(r) for r in records] + list(extra_lines)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def prices(self, table=PRICES, name="prices.json"):
        path = self.dir / name
        path.write_text(json.dumps(table), encoding="utf-8")
        return str(path)

    def close(self):
        self.tmp.cleanup()


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def run_json(argv):
    code, out, err = run(argv + ["--json"])
    return code, (json.loads(out) if out.strip() else None), err


class TokenConventions(unittest.TestCase):
    def test_separate_counters(self):
        t = module.extract_tokens(separate("s", "2026-10-30", "m", 100, 20, write=50, read=400), False)
        self.assertEqual(t, {"ordinary": 100, "cache_write": 50, "cache_read": 400, "output": 20})

    def test_chat_style_subset_counters(self):
        rec = {"usage": {"prompt_tokens": 3000, "completion_tokens": 200, "prompt_tokens_details": {"cached_tokens": 1024}}}
        t = module.extract_tokens(rec, False)
        self.assertEqual(t, {"ordinary": 1976, "cache_write": 0, "cache_read": 1024, "output": 200})

    def test_responses_style_subset_counters(self):
        rec = {"usage": {"input_tokens": 500, "output_tokens": 9, "input_tokens_details": {"cached_tokens": 128}}}
        t = module.extract_tokens(rec, False)
        self.assertEqual((t["ordinary"], t["cache_read"]), (372, 128))

    def test_input_includes_cache_flag(self):
        rec = {"input_tokens": 1000, "output_tokens": 1, "cache_write_tokens": 100, "cache_read_tokens": 600}
        self.assertEqual(module.extract_tokens(rec, True)["ordinary"], 300)
        self.assertEqual(module.extract_tokens(rec, False)["ordinary"], 1000)

    def test_invalid_counts_raise(self):
        for rec in ({"input_tokens": -1, "output_tokens": 0}, {"input_tokens": "12", "output_tokens": 0},
                    {"input_tokens": 1.5, "output_tokens": 0}, {"event": "no usage"},
                    {"usage": {"prompt_tokens": 10, "prompt_tokens_details": {"cached_tokens": 20}}}):
            with self.assertRaises(ValueError, msg=rec):
                module.extract_tokens(rec, False)

    def test_prompt_text_fields_are_ignored(self):
        rec = {"input": "a prompt that must never be read as a number", "input_tokens": 7, "output_tokens": 3}
        self.assertEqual(module.extract_tokens(rec, False)["ordinary"], 7)


class Costs(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_costs_cache_rate_and_savings(self):
        log = self.ws.log([
            separate("s1", "2026-10-30T10:00:00Z", "model-a", 1000, 500, write=10000),
            separate("s1", "2026-10-30T10:01:00Z", "model-a", 1200, 400, read=10000),
        ])
        code, rep, _ = run_json([log, "--prices", self.ws.prices()])
        self.assertEqual(code, 0)
        self.assertAlmostEqual(rep["cost"]["total"], 0.0606)
        self.assertAlmostEqual(rep["cost"]["without_caching"], 0.0801)
        self.assertAlmostEqual(rep["cost"]["caching_savings"], 0.0195)
        self.assertAlmostEqual(rep["cache"]["token_hit_rate"], round(10000 / 22200, 4))
        self.assertEqual(rep["cache"]["records_with_cache_reads"], 1)
        self.assertEqual(rep["prices"]["as_of"], "2026-10-01")

    def test_write_without_reads_costs_more_than_no_caching(self):
        log = self.ws.log([separate("s", "2026-10-30", "model-a", 0, 0, write=1000000)])
        code, rep, _ = run_json([log, "--prices", self.ws.prices()])
        self.assertAlmostEqual(rep["cost"]["caching_savings"], -0.75)

    def test_longest_wildcard_wins_and_exact_beats_wildcard(self):
        table = {"family-large-2": {"input": 2, "output": 2}, "family-*": {"input": 1, "output": 5},
                 "family-large*": {"input": 10, "output": 50}}
        self.assertEqual(module.match_price("family-large-2", {k: v for k, v in table.items()})["input"], 2)
        self.assertEqual(module.match_price("family-large-3", table)["input"], 10)
        self.assertEqual(module.match_price("family-small", table)["input"], 1)
        self.assertIsNone(module.match_price("other", table))

    def test_unpriced_models_are_reported_not_guessed(self):
        log = self.ws.log([separate("s1", "2026-10-30", "model-a", 1000, 0),
                           separate("s2", "2026-10-30", "mystery-model", 5000, 100)])
        code, rep, _ = run_json([log, "--prices", self.ws.prices(), "--budget", "100"])
        self.assertEqual(code, 1)
        self.assertEqual(rep["unpriced_models"], [{"model": "mystery-model", "tokens": 5100}])
        self.assertEqual(rep["budget"]["status"], "unknown")
        mystery = [r for r in rep["by_model"] if r["key"] == "mystery-model"][0]
        self.assertIsNone(mystery["cost"])

    def test_missing_cache_rate_makes_record_unpriced(self):
        log = self.ws.log([separate("s", "2026-10-30", "family-small", 100, 10, read=50)])
        code, rep, _ = run_json([log, "--prices", self.ws.prices()])
        self.assertEqual(rep["unpriced_models"][0]["model"], "family-small")

    def test_budget_within_and_exceeded(self):
        log = self.ws.log([separate("s", "2026-10-30", "model-a", 1000000, 0)])  # 3.00 USD
        self.assertEqual(run([log, "--prices", self.ws.prices(), "--budget", "3"])[0], 0)
        code, out, _ = run([log, "--prices", self.ws.prices(), "--budget", "2.5"])
        self.assertEqual(code, 1)
        self.assertIn("budget: EXCEEDED", out)


class Cumulative(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_latest_snapshot_per_session(self):
        rows = [
            {"timestamp": "2026-10-30T10:00:00Z", "session_id": "a", "model": "m", "input_tokens": 100, "output_tokens": 1, "estimated_cost_usd": 0.5},
            {"timestamp": "2026-10-30T12:00:00Z", "session_id": "a", "model": "m", "input_tokens": 300, "output_tokens": 3, "estimated_cost_usd": 1.5},
            {"timestamp": "2026-10-30T11:00:00Z", "session_id": "a", "model": "m", "input_tokens": 200, "output_tokens": 2, "estimated_cost_usd": 1.0},
            {"timestamp": "2026-10-30T09:00:00Z", "session_id": "b", "model": "m", "input_tokens": 50, "output_tokens": 5, "estimated_cost_usd": 0.25},
        ]
        log = self.ws.log(rows)
        code, rep, _ = run_json([log, "--cumulative", "--budget", "1.5"])
        self.assertEqual(code, 1)
        self.assertEqual(rep["records_used"], 2)
        self.assertEqual(rep["snapshots_superseded"], 2)
        self.assertEqual(rep["tokens"]["ordinary"], 350)
        self.assertEqual(rep["recorded_cost"]["total"], 1.75)
        self.assertEqual(rep["budget"]["basis"], "recorded cost fields")
        code, rep, _ = run_json([log, "--budget", "10"])
        self.assertEqual(rep["recorded_cost"]["total"], 3.25)  # summing snapshots overcounts

    def test_records_without_session_are_kept(self):
        log = self.ws.log([{"model": "m", "input_tokens": 10, "output_tokens": 1},
                           {"model": "m", "input_tokens": 20, "output_tokens": 2}])
        code, rep, _ = run_json([log, "--cumulative"])
        self.assertEqual((code, rep["records_used"]), (0, 2))


class Inputs(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_malformed_and_skipped_lines_are_counted(self):
        log = self.ws.log([separate("s", "2026-10-30", "m", 1, 1)],
                          extra_lines=["not json", "[1, 2]", json.dumps({"event": "heartbeat"})])
        code, rep, _ = run_json([log])
        self.assertEqual((code, rep["malformed_lines"], rep["skipped_records"]), (0, 2, 1))

    def test_days_from_iso_and_epoch(self):
        self.assertEqual(module.day_of("2026-10-30T23:59:59Z"), "2026-10-30")
        self.assertEqual(module.day_of(1700000000), "2023-11-14")
        self.assertEqual(module.day_of(1700000000000), "2023-11-14")
        self.assertEqual(module.day_of(None), "(unknown)")

    def test_bad_inputs_exit_2(self):
        log = self.ws.log([separate("s", "2026-10-30", "m", 1, 1)])
        self.assertEqual(run([str(self.ws.dir / "missing.jsonl")])[0], 2)
        empty = self.ws.log([], name="empty.jsonl")
        self.assertEqual(run([empty])[0], 2)
        for bad in ({"models": {}}, {"models": {"m": {"input": 1}}}, {"models": {"m": {"input": -1, "output": 1}}}):
            self.assertEqual(run([log, "--prices", self.ws.prices(bad, name="bad.json")])[0], 2, bad)
        (self.ws.dir / "notjson.json").write_text("{", encoding="utf-8")
        self.assertEqual(run([log, "--prices", str(self.ws.dir / "notjson.json")])[0], 2)
        self.assertEqual(run([log, "--budget", "abc"])[0], 2)
        self.assertEqual(run([log, "--budget", "-1"])[0], 2)

    def test_text_report_and_determinism(self):
        log = self.ws.log([separate("s2", "2026-10-31", "model-a", 10, 1), separate("s1", "2026-10-30", "model-a", 20, 2)])
        args = [log, "--prices", self.ws.prices()]
        first, second = run(args)[1], run(args)[1]
        self.assertEqual(first, second)
        self.assertIn("prices: as of 2026-10-01", first)
        self.assertLess(first.index("2026-10-30"), first.index("2026-10-31"))

    def test_undated_price_file_is_flagged(self):
        table = dict(PRICES)
        del table["as_of"]
        log = self.ws.log([separate("s", "2026-10-30", "model-a", 10, 1)])
        out = run([log, "--prices", self.ws.prices(table, name="undated.json")])[1]
        self.assertIn("as of UNDATED", out)


if __name__ == "__main__":
    unittest.main()
