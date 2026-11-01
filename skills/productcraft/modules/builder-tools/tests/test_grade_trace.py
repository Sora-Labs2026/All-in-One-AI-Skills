"""Tests for scripts/grade_trace.py. Standard library only; traces and specs are built at run time."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import grade_trace as gt  # noqa: E402

# The test-first spec shown in references/instruction-compliance-testing.md.
TDD_SPEC = {
    "id": "test-first",
    "steps": [
        {"id": "write_test", "tool": "Write|Edit|MultiEdit", "field": "file_path",
         "match": "(^|/)tests?/|(^|/)test_[^/]*\\.py$", "before": "write_impl"},
        {"id": "run_red", "tool": "Bash", "field": "command", "match": "\\bpytest\\b",
         "output": "(?i)\\b(failed|error)", "after": "write_test", "before": "write_impl"},
        {"id": "write_impl", "tool": "Write|Edit|MultiEdit", "field": "file_path",
         "match": "^(?!.*(^|/)tests?/)(?!.*test_).*\\.py$"},
        {"id": "run_green", "tool": "Bash", "field": "command", "match": "\\bpytest\\b",
         "output": "(?i)\\bpassed\\b", "output_not": "(?i)\\bfailed\\b", "after": "write_impl"},
    ],
    "forbidden": [{"id": "skip_hooks", "tool": "Bash", "field": "command", "match": "--no-verify"}],
}


def call(tool, inp, output="", is_error=False):
    return {"tool": tool, "input": inp, "output": output, "is_error": is_error}


GOOD = [
    call("Read", {"file_path": "src/slug.py"}),
    call("Write", {"file_path": "tests/test_slug.py", "content": "def test_x(): ..."}),
    call("Bash", {"command": "pytest -q"}, "1 failed in 0.02s"),
    call("Write", {"file_path": "src/slug.py", "content": "def slugify(s): ..."}),
    call("Bash", {"command": "pytest -q"}, "1 passed in 0.01s"),
]


def stream_json(calls, parent=None):
    """Render calls as headless stream-JSON events: assistant tool_use, then user tool_result."""
    lines = [json.dumps({"type": "system", "subtype": "init"})]
    for n, c in enumerate(calls):
        uid = f"toolu_{n:03d}"
        lines.append(json.dumps({"type": "assistant", "parent_tool_use_id": parent, "message": {"content": [
            {"type": "text", "text": "working"},
            {"type": "tool_use", "id": uid, "name": c["tool"], "input": c["input"]}]}}))
        lines.append(json.dumps({"type": "user", "parent_tool_use_id": parent, "message": {"content": [
            {"type": "tool_result", "tool_use_id": uid, "is_error": c["is_error"],
             "content": [{"type": "text", "text": c["output"]}]}]}}))
    lines.append(json.dumps({"type": "result", "subtype": "success"}))
    return "\n".join(lines) + "\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def spec(self, data=None):
        return self.write("spec.json", json.dumps(data if data is not None else TDD_SPEC))

    def jsonl(self, name, calls):
        return self.write(name, "".join(json.dumps(c) + "\n" for c in calls))

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = gt.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def graded(self, calls, spec=None):
        loaded = gt.load_spec(self.spec(spec))
        return gt.grade(loaded, calls)

    def status(self, result):
        return {s["id"]: s["passed"] for s in result["steps"]}


class GradingTests(Base):
    def test_compliant_jsonl_trace(self):
        code, out, _ = self.cli(self.spec(), self.jsonl("good.jsonl", GOOD))
        self.assertEqual(code, 0, out)
        self.assertIn("compliance 4/4", out)
        self.assertIn("#2 Write tests/test_slug.py", out)

    def test_stream_json_trace_is_parsed(self):
        code, out, _ = self.cli("--json", self.spec(), self.write("run.jsonl", stream_json(GOOD)))
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual(data["traces"][0]["events"], 5)
        self.assertTrue(data["traces"][0]["compliant"])

    def test_implementation_first_fails_ordering(self):
        calls = [GOOD[3], GOOD[1], GOOD[2], GOOD[4]]
        result = self.graded(calls)
        st = self.status(result)
        self.assertFalse(st["write_test"])
        self.assertIn("must come before 'write_impl'", result["steps"][0]["reason"])
        self.assertFalse(result["compliant"])

    def test_failed_prerequisite_does_not_carry_dependants(self):
        calls = [GOOD[3], GOOD[2], GOOD[4]]  # no test written at all
        result = self.graded(calls)
        reasons = {s["id"]: s["reason"] for s in result["steps"]}
        self.assertEqual(reasons["write_test"], "no matching tool call")
        self.assertIn("prerequisite 'write_test'", reasons["run_red"])

    def test_after_picks_a_later_match(self):
        calls = [call("Bash", {"command": "pytest"}, "1 passed"), *GOOD]
        st = self.status(self.graded(calls))
        self.assertTrue(all(st.values()), st)

    def test_output_not_rejects_mixed_results(self):
        calls = GOOD[:4] + [call("Bash", {"command": "pytest"}, "1 failed, 2 passed")]
        st = self.status(self.graded(calls))
        self.assertFalse(st["run_green"])

    def test_forbidden_call_makes_run_non_compliant(self):
        calls = GOOD + [call("Bash", {"command": "git commit --no-verify -m wip"})]
        code, out, _ = self.cli(self.spec(), self.jsonl("bad.jsonl", calls))
        self.assertEqual(code, 1)
        self.assertIn("FORBIDDEN  skip_hooks  #6", out)

    def test_optional_step_does_not_lower_compliance(self):
        spec = {"steps": [{"id": "lint", "tool": "Bash", "field": "command", "match": "ruff", "required": False},
                          {"id": "tests", "tool": "Bash", "field": "command", "match": "pytest"}]}
        result = self.graded([call("Bash", {"command": "pytest"})], spec)
        self.assertTrue(result["compliant"])
        self.assertEqual(result["required_total"], 1)

    def test_error_flag_condition(self):
        spec = {"steps": [{"id": "ran", "tool": "Bash", "field": "command", "match": "pytest", "error": False}]}
        self.assertFalse(self.graded([call("Bash", {"command": "pytest"}, "not found", True)], spec)["compliant"])
        self.assertTrue(self.graded([call("Bash", {"command": "pytest"}, "ok")], spec)["compliant"])

    def test_dotted_field_and_whole_input_match(self):
        spec = {"steps": [{"id": "deleg", "tool": "Task|Agent", "field": "options.agent", "match": "^reviewer$"},
                          {"id": "any", "tool": "Grep", "match": "callers"}]}
        calls = [call("Agent", {"options": {"agent": "reviewer"}}), call("Grep", {"pattern": "callers of slugify"})]
        self.assertTrue(self.graded(calls, spec)["compliant"])

    def test_main_only_ignores_subagent_calls(self):
        nested = stream_json([GOOD[1]], parent="toolu_parent")
        main = stream_json([GOOD[3]])
        path = self.write("mixed.jsonl", nested + main)
        spec = {"steps": [{"id": "write_test", "tool": "Write", "field": "file_path", "match": "tests/"}]}
        sp = self.spec(spec)
        self.assertEqual(self.cli(sp, path)[0], 0)
        self.assertEqual(self.cli("--main-only", sp, path)[0], 1)

    def test_summary_over_several_traces(self):
        bad = self.jsonl("bad.jsonl", [GOOD[3]])
        code, out, _ = self.cli(self.spec(), self.jsonl("good.jsonl", GOOD), bad)
        self.assertEqual(code, 1)
        self.assertIn("compliant traces: 1/2", out)

    def test_unparsable_lines_are_counted_not_fatal(self):
        path = self.write("noisy.jsonl", "not json\n" + "".join(json.dumps(c) + "\n" for c in GOOD))
        code, out, _ = self.cli(self.spec(), path)
        self.assertEqual(code, 0)
        self.assertIn("1 unparsable lines skipped", out)

    def test_excerpt_redacts_token_like_text_and_truncates(self):
        fake = "tok" + "A1b2C3d4" * 6
        text = gt.excerpt(f"curl -H 'Authorization: Bearer {fake}' https://example.test/" + "x" * 80)
        self.assertNotIn(fake, text)
        self.assertIn("[REDACTED]", text)
        self.assertLessEqual(len(text), gt.EXCERPT)


class SpecErrorTests(Base):
    def assertSpecError(self, data, fragment):
        code, _, err = self.cli(self.spec(data), self.jsonl("t.jsonl", GOOD))
        self.assertEqual(code, 2)
        self.assertIn(fragment, err)

    def test_cycle_is_rejected(self):
        self.assertSpecError({"steps": [{"id": "a", "after": "b"}, {"id": "b", "after": "a"}]}, "cycle")

    def test_unknown_reference_is_rejected(self):
        self.assertSpecError({"steps": [{"id": "a", "before": "zzz"}]}, "unknown step 'zzz'")

    def test_bad_regex_is_rejected(self):
        self.assertSpecError({"steps": [{"id": "a", "match": "("}]}, "not a valid regular expression")

    def test_duplicate_ids_and_unknown_keys(self):
        self.assertSpecError({"steps": [{"id": "a"}, {"id": "a"}]}, "unique")
        self.assertSpecError({"steps": [{"id": "a", "pattern": "x"}]}, "unknown keys")

    def test_forbidden_entries_take_no_ordering(self):
        self.assertSpecError({"steps": [{"id": "a"}], "forbidden": [{"id": "f", "after": "a"}]}, "no ordering")

    def test_missing_files_exit_2(self):
        self.assertEqual(self.cli(str(self.dir / "none.json"), "x.jsonl")[0], 2)
        self.assertEqual(self.cli(self.spec(), str(self.dir / "missing.jsonl"))[0], 2)

    def test_help_mentions_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            gt.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("Exit 0", out.getvalue())


if __name__ == "__main__":
    unittest.main()
