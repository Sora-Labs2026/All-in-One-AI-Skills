"""Tests for scripts/check_evals.py and scripts/eval_summary.py (stdlib only)."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_evals  # noqa: E402
import eval_summary  # noqa: E402

PROMPT = """---
description: A test case
tags: [smoke]
runs: 3
max_turns: 10
allowed_tools: [Skill, Read]
plugins: ["../.."]
---

Do the thing.
"""
SKILL = "---\ntype: tool_used\ntool: Skill\ninput_match: '\"skill\"\\s*:\\s*\"productcraft\"'\n---\n"
RUBRIC = "---\ntype: llm\nweight: 2\n---\nPASS if it works.\n"


class CheckEvalsTests(unittest.TestCase):
    def make(self, prompt=PROMPT, graders=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        case = pathlib.Path(tmp.name) / "evals" / "case-a"
        (case / "graders").mkdir(parents=True)
        (case / "prompt.md").write_text(prompt)
        for name, text in (graders if graders is not None else {"skill": SKILL, "rubric": RUBRIC}).items():
            (case / "graders" / f"{name}.md").write_text(text)
        return case

    def run_main(self, case):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_evals.main(["--dir", str(case.parent)])
        return code, out.getvalue()

    def test_valid_case_passes(self):
        code, out = self.run_main(self.make())
        self.assertEqual(code, 0, out)
        self.assertIn("1 cases, 2 graders: OK", out)

    def test_frontmatter_parses_lists_and_quotes(self):
        meta, body = check_evals.parse_frontmatter(PROMPT)
        self.assertEqual(meta["allowed_tools"], ["Skill", "Read"])
        self.assertEqual(meta["plugins"], ["../.."])
        self.assertEqual(body.strip(), "Do the thing.")

    def test_unknown_prompt_key(self):
        problems, _ = check_evals.check_case(self.make(PROMPT.replace("runs: 3", "scaffold_script: x.sh")))
        self.assertTrue(any("unknown key scaffold_script" in p for p in problems))

    def test_skill_grader_needs_skill_tool(self):
        problems, _ = check_evals.check_case(self.make(PROMPT.replace("[Skill, Read]", "[Read]")))
        self.assertTrue(any("add Skill to allowed_tools" in p for p in problems))

    def test_only_indicators_is_a_problem(self):
        problems, _ = check_evals.check_case(self.make(graders={"skill": SKILL}))
        self.assertTrue(any("with-only indicator" in p for p in problems))

    def test_negative_skill_grader_counts_as_scored(self):
        neg = "---\ntype: tool_used\ntool: Skill\nmin: 0\nmax: 0\narm: both\n---\n"
        problems, _ = check_evals.check_case(self.make(graders={"no-skill": neg}))
        self.assertEqual(problems, [])

    def test_bad_regex_and_flags(self):
        bad = "---\ntype: regex\npattern: '(unclosed'\nflags: g\n---\n"
        problems, _ = check_evals.check_case(self.make(graders={"bad": bad, "rubric": RUBRIC}))
        self.assertTrue(any("does not compile" in p for p in problems))
        self.assertTrue(any("flags may only use" in p for p in problems))

    def test_unknown_type_and_missing_field(self):
        graders = {"x": "---\ntype: contains\n---\n", "y": "---\ntype: regex\n---\n", "rubric": RUBRIC}
        problems, _ = check_evals.check_case(self.make(graders=graders))
        self.assertTrue(any("unknown type 'contains'" in p for p in problems))
        self.assertTrue(any("regex grader needs pattern" in p for p in problems))

    def test_write_tool_must_be_granted_on_command_line(self):
        problems, _ = check_evals.check_case(self.make(PROMPT.replace("[Skill, Read]", "[Skill, Read, Bash]")))
        self.assertTrue(any("Bash is not a read-only tool" in p for p in problems))

    def test_empty_llm_and_out_of_range_runs(self):
        graders = {"rubric": "---\ntype: llm\n---\n"}
        problems, _ = check_evals.check_case(self.make(PROMPT.replace("runs: 3", "runs: 99"), graders))
        self.assertTrue(any("needs PASS/FAIL criteria" in p for p in problems))
        self.assertTrue(any("runs must be an integer" in p for p in problems))

    def test_missing_directory_is_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_evals.main(["--dir", "/nonexistent/evals"]), 2)


def result(cases, cost=0.5):
    return {"costUsd": cost, "cases": cases}


def run(score, **passed):
    return {"score": score, "graders": [{"name": k, "passed": v} for k, v in passed.items()]}


POS_GRADERS = [{"name": "skill-fired", "type": "tool_used", "config": {"tool": "Skill"}},
               {"name": "read-module", "type": "tool_used", "config": {"tool": "Read", "arm": "with-only"}},
               {"name": "rubric", "type": "llm", "config": {}}]
NEG_GRADERS = [{"name": "no-skill", "type": "tool_used", "config": {"tool": "Skill", "min": 0, "max": 0, "arm": "both"}}]


class EvalSummaryTests(unittest.TestCase):
    def test_trigger_and_read_rates(self):
        case = {"name": "a", "graders": POS_GRADERS,
                "arms": {"with": [run(1, **{"skill-fired": True, "read-module": True, "rubric": True}),
                                  run(0.5, **{"skill-fired": False, "read-module": False, "rubric": True})]},
                "aggregates": {"score": 0.75}}
        text, totals = eval_summary.summarize(result([case]))
        self.assertAlmostEqual(totals["trigger_rate"], 0.5)
        self.assertAlmostEqual(totals["module_read_rate"], 0.5)
        self.assertIn("| a | should load | 50 % | 50 % | 0.75 |", text)

    def test_negative_case_counts_false_triggers(self):
        case = {"name": "n", "graders": NEG_GRADERS,
                "arms": {"with": [run(1, **{"no-skill": True}), run(0, **{"no-skill": False})]}}
        _, totals = eval_summary.summarize(result([case]))
        self.assertAlmostEqual(totals["false_trigger_rate"], 0.5)
        self.assertIsNone(totals["trigger_rate"])

    def test_delta_from_aggregates(self):
        case = {"name": "d", "graders": POS_GRADERS, "arms": {"with": [run(1, **{"skill-fired": True})],
                                                               "without": [run(0.6)]},
                "aggregates": {"score": 1, "scoreWithout": 0.6, "delta": 0.4}}
        text, totals = eval_summary.summarize(result([case]))
        self.assertAlmostEqual(totals["mean_delta"], 0.4)
        self.assertIn("| 1.00 | 0.60 | 0.40 |", text)

    def test_min_trigger_gate(self):
        case = {"name": "a", "graders": POS_GRADERS, "arms": {"with": [run(0, **{"skill-fired": False})]}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(result([case]), fh)
        self.addCleanup(pathlib.Path(fh.name).unlink)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(eval_summary.main([fh.name, "--min-trigger", "0.8"]), 1)
            self.assertEqual(eval_summary.main([fh.name]), 0)

    def test_unreadable_input(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(eval_summary.main(["/nonexistent.json"]), 2)


if __name__ == "__main__":
    unittest.main()
