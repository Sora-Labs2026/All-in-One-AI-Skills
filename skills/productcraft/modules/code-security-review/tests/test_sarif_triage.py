"""Tests for scripts/sarif_triage.py. Run: python3 -m unittest discover -s <module>/tests -v"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import sarif_triage as st  # noqa: E402

try:
    import code_audit  # noqa: E402  (the module's findings validator, next to this script)
except ImportError:  # pragma: no cover - only when the script is tested on its own
    code_audit = None


# Built at runtime so no key-shaped literal sits in the repository.
FAKE_KEY = "sk_live_" + "abcdefghijklmnop" + "1234567890"

def codeql_like(root: Path) -> dict:
    """CodeQL style: rules live in a tool extension and results carry no level."""
    return {"version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "CodeQL", "semanticVersion": "2.19.0"},
                 "extensions": [{"name": "codeql/python-queries", "rules": [
                     {"id": "py/sql-injection", "shortDescription": {"text": "SQL query built from user input"},
                      "defaultConfiguration": {"level": "error"},
                      "properties": {"security-severity": "8.8", "precision": "high",
                                     "tags": ["security", "external/cwe/cwe-089"]}},
                     {"id": "py/clear-text-logging", "defaultConfiguration": {"level": "warning"},
                      "properties": {"security-severity": "7.5", "tags": ["external/cwe/cwe-312"]}}]}]},
        "invocations": [{"executionSuccessful": True}],
        "results": [
            {"ruleId": "py/sql-injection", "rule": {"id": "py/sql-injection", "index": 0, "toolComponent": {"index": 0}},
             "message": {"text": "This query depends on a [user-provided value](1)."},
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "app/db.py"}, "region": {"startLine": 42}}}],
             "partialFingerprints": {"primaryLocationLineHash": "aaa:1"}},
            {"ruleId": "py/clear-text-logging", "rule": {"index": 1, "toolComponent": {"index": 0}},
             "message": {"text": f"Logs {FAKE_KEY} in clear text"},
             "locations": [{"physicalLocation": {
                 "artifactLocation": {"uri": (root / "app" / "log.py").as_uri()},
                 "region": {"startLine": 7, "snippet": {"text": "print(SECRET_VALUE_MARKER)"}}}}],
             "partialFingerprints": {"primaryLocationLineHash": "bbb:1"}},
            {"ruleId": "py/sql-injection", "kind": "pass", "message": {"text": "fine"},
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "app/ok.py"}, "region": {"startLine": 1}}}],
             "partialFingerprints": {"primaryLocationLineHash": "ccc:1"}},
        ]}]}


def semgrep_like() -> dict:
    """Semgrep style: rules in the driver, level on each result, suppressions in source."""
    rule = {"id": "rules.raw-sql", "shortDescription": {"text": "Raw SQL built with an f-string"},
            "defaultConfiguration": {"level": "warning"}, "properties": {"tags": ["CWE-89: SQL Injection"]}}
    loc = lambda uri, line: [{"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": line}}}]
    return {"version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "Semgrep OSS", "rules": [rule]}},
        "results": [
            {"ruleId": "rules.raw-sql", "ruleIndex": 0, "level": "error", "message": {"text": "f-string in execute()"},
             "locations": loc("app/db.py", 42)},
            {"ruleId": "rules.raw-sql", "ruleIndex": 0, "message": {"text": "f-string in execute()"},
             "locations": loc("app/report.py", 10), "suppressions": [{"kind": "inSource"}]},
            {"ruleId": "rules.raw-sql", "ruleIndex": 0, "message": {"text": "f-string in execute()"},
             "locations": loc("../outside.py", 3)},
            {"ruleId": "rules.raw-sql", "ruleIndex": 0, "message": {"text": "f-string in execute()"},
             "locations": loc("app/db.py", 42)},
        ]}]}


def run_cli(*args) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = st.main(list(args))
    return code, buf.getvalue()


class SarifTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        (self.root / "app").mkdir(parents=True)
        self.codeql = Path(self.tmp.name) / "codeql.sarif"
        self.semgrep = Path(self.tmp.name) / "semgrep.sarif"
        self.codeql.write_text(json.dumps(codeql_like(self.root)))
        self.semgrep.write_text(json.dumps(semgrep_like()))

    def tearDown(self):
        self.tmp.cleanup()

    def test_level_resolution(self):
        self.assertEqual(st.resolve_level({}, {"defaultConfiguration": {"level": "error"}}), "error")
        self.assertEqual(st.resolve_level({"level": "note"}, {"defaultConfiguration": {"level": "error"}}), "note")
        self.assertEqual(st.resolve_level({"kind": "pass", "level": "error"}, {}), "none")
        self.assertEqual(st.resolve_level({}, {}), "warning")

    def test_collect_resolves_extension_rules_paths_and_redacts(self):
        results, runs = st.collect(str(self.codeql), self.root)
        self.assertEqual(runs[0]["tool"], "CodeQL")
        sql, log, passed = results
        self.assertEqual((sql["level"], sql["cwe"], sql["security_severity"]), ("error", "CWE-89", "8.8"))
        self.assertEqual(sql["message"], "This query depends on a user-provided value.")
        self.assertEqual((log["file"], log["path_ok"], log["level"]), ("app/log.py", True, "warning"))
        self.assertIn("[REDACTED]", log["message"])
        self.assertEqual(passed["level"], "none")
        self.assertNotIn("SECRET_VALUE_MARKER", json.dumps(results))

    def test_security_label(self):
        self.assertEqual([st.security_label(v) for v in ("9.1", "7.0", "4", "0.5", "0", None, "x")],
                         ["critical", "high", "medium", "low", None, None, None])

    def test_summary(self):
        results, runs = st.collect(str(self.semgrep), self.root)
        more, more_runs = st.collect(str(self.codeql), self.root)
        s = st.summarize(results + more, runs + more_runs, 10)
        self.assertEqual(s["results"], 7)
        self.assertEqual(s["suppressed"], 1)
        self.assertEqual(s["by_level"], {"error": 2, "warning": 3, "note": 0, "none": 1})
        self.assertEqual(s["rules"][0]["rule"], "rules.raw-sql")
        self.assertEqual(s["paths_not_relative"], 1)

    def test_diff_uses_fingerprints(self):
        base = json.loads(self.codeql.read_text())
        base["runs"][0]["results"] = base["runs"][0]["results"][1:2]
        base["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] = 3
        base_path = Path(self.tmp.name) / "base.sarif"
        base_path.write_text(json.dumps(base))
        code, text = run_cli("diff", "--sarif", str(self.codeql), "--baseline", str(base_path),
                             "--root", str(self.root), "--fail-on", "error")
        self.assertEqual(code, 1)
        self.assertIn("1 new, 1 unchanged", text)
        code, _ = run_cli("diff", "--sarif", str(self.codeql), "--baseline", str(self.codeql), "--fail-on", "note")
        self.assertEqual(code, 0)

    def test_multiset_matching_without_fingerprints(self):
        r = {"tool": "t", "rule": "r", "file": "a.py", "message_key": "m", "fingerprint": None}
        fresh, same, absent = st.split_new([dict(r), dict(r)], [dict(r)])
        self.assertEqual((len(fresh), len(same), absent), (1, 1, 0))

    def test_leads_are_valid_possible_findings(self):
        out = Path(self.tmp.name) / "security" / "sast-leads.json"
        code, text = run_cli("leads", "--sarif", str(self.codeql), "--sarif", str(self.semgrep), "--root",
                             str(self.root), "--out", str(out), "--repository", "shop", "--revision", "3f2c1ab")
        self.assertEqual(code, 0)
        self.assertEqual(oct(out.stat().st_mode & 0o777), "0o600")
        doc = json.loads(out.read_text())
        leads = doc["findings"]
        self.assertEqual([l["id"] for l in leads], ["SAST-001", "SAST-002", "SAST-003"])
        self.assertTrue(all(l["confidence"] == "POSSIBLE" and "severity" not in l and l["next_check"] for l in leads))
        semgrep_lead = next(l for l in leads if l["source_tool"] == "Semgrep OSS")
        self.assertEqual(semgrep_lead["occurrences"], 2)
        self.assertEqual(semgrep_lead["also_reported_by"], ["CodeQL:py/sql-injection"])
        self.assertEqual(doc["import_notes"]["skipped_suppressed"], 1)
        self.assertEqual(doc["import_notes"]["skipped_unresolvable_paths"], 1)
        self.assertNotIn("sk_live_", out.read_text())
        if code_audit is not None:
            report = code_audit.validate_findings(doc)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["result"], "NEEDS_REVIEW")

    def test_leads_min_level_and_baseline(self):
        out = Path(self.tmp.name) / "leads.json"
        run_cli("leads", "--sarif", str(self.codeql), "--root", str(self.root), "--out", str(out), "--min-level", "error")
        self.assertEqual([l["rule_id"] for l in json.loads(out.read_text())["findings"]], ["py/sql-injection"])
        run_cli("leads", "--sarif", str(self.codeql), "--baseline", str(self.codeql), "--root", str(self.root),
                "--out", str(out))
        self.assertEqual(json.loads(out.read_text())["findings"], [])

    def test_min_security_severity_keeps_unscored_rules(self):
        out = Path(self.tmp.name) / "leads.json"
        run_cli("leads", "--sarif", str(self.codeql), "--sarif", str(self.semgrep), "--root", str(self.root),
                "--out", str(out), "--min-security-severity", "8.0")
        doc = json.loads(out.read_text())
        self.assertEqual(sorted(l["rule_id"] for l in doc["findings"]), ["py/sql-injection", "rules.raw-sql"])
        self.assertEqual(doc["import_notes"]["skipped_below_security_severity"], 1)

    def test_bad_input(self):
        bad = Path(self.tmp.name) / "bad.sarif"
        bad.write_text('{"version": "2.1.0"}')
        code, _ = run_cli("summary", "--sarif", str(bad))
        self.assertEqual(code, 2)
        code, _ = run_cli("leads", "--sarif", str(self.codeql), "--out", str(bad), "--id-prefix", "x")
        self.assertEqual(code, 2)

    def test_empty_run_warns_instead_of_claiming_clean(self):
        empty = Path(self.tmp.name) / "empty.sarif"
        empty.write_text(json.dumps({"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "X"}}, "results": []}]}))
        code, text = run_cli("summary", "--sarif", str(empty))
        self.assertEqual(code, 0)
        self.assertIn("before reading this as clean", text)


if __name__ == "__main__":
    unittest.main()
