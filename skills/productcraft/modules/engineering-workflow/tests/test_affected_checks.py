"""Offline tests for affected_checks.py with synthetic ledgers; git tests use a temporary repository."""
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "affected_checks.py"
spec = importlib.util.spec_from_file_location("affected_checks", SCRIPT)
ac = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ac
spec.loader.exec_module(ac)

LEDGER = {
    "always": ["ruff check ."],
    "modules": {
        "ingest": {"paths": ["pipelines/ingest/"], "check": "pytest tests/ingest -q", "downstream": ["clean"]},
        "clean": {"paths": ["pipelines/clean/*.py"], "check": "python scripts/reconcile.py clean",
                  "downstream": ["report"], "unverified_downstream": ["export"]},
        "report": {"paths": ["pipelines/report/"], "check": None},
        "export": {"paths": ["pipelines/export/"], "check": "pytest tests/export -q"},
    },
}


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = ac.main(list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class LedgerFile:
    def __init__(self, data):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "regression.json"
        self.path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")

    def close(self):
        self._tmp.cleanup()


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.ledger = LedgerFile(LEDGER)
        self.modules, self.always = ac.load_ledger(self.ledger.path)

    def tearDown(self):
        self.ledger.close()

    def checks(self, result):
        return [c["module"] for c in result["checks"]]

    def kinds(self, result):
        return {(f["check"], f["subject"]) for f in result["findings"]}

    def test_downstream_is_transitive_and_ordered(self):
        result = ac.plan(self.modules, self.always, ["pipelines/ingest/read.py"], {})
        self.assertEqual([a["module"] for a in result["affected"]], ["ingest", "clean", "report"])
        self.assertEqual(self.checks(result), ["ingest", "clean"])
        self.assertIn(("no-check", "report"), self.kinds(result))
        self.assertIn(("unverified-edge", "clean -> export"), self.kinds(result))

    def test_leaf_change_runs_only_its_check(self):
        result = ac.plan(self.modules, self.always, ["pipelines/export/write.py"], {})
        self.assertEqual(self.checks(result), ["export"])
        self.assertEqual(result["findings"], [])

    def test_unmapped_files_and_path_normalization(self):
        result = ac.plan(self.modules, self.always, ["./README.md", "pipelines\\ingest\\a.py"], {})
        self.assertIn(("unmapped", "README.md"), self.kinds(result))
        self.assertIn("ingest", result["direct"])

    def test_glob_star_crosses_directories(self):
        result = ac.plan(self.modules, self.always, ["pipelines/clean/sub/x.py", "pipelines/clean/notes.md"], {})
        self.assertEqual(result["direct"], {"clean": ["pipelines/clean/sub/x.py"]})
        self.assertIn(("unmapped", "pipelines/clean/notes.md"), self.kinds(result))

    def test_exemption_stops_propagation_and_is_reported(self):
        result = ac.plan(self.modules, self.always, ["pipelines/ingest/read.py"], {"ingest": "logging only"})
        self.assertEqual([a["module"] for a in result["affected"]], ["ingest"])
        self.assertIn(("exempt", "ingest"), self.kinds(result))

    def test_cycle_is_reported_and_all_members_run(self):
        modules = {
            "a": {"paths": ["a/"], "check": "check a", "downstream": ["b"], "unverified": []},
            "b": {"paths": ["b/"], "check": "check b", "downstream": ["a"], "unverified": []},
        }
        result = ac.plan(modules, [], ["a/x"], {})
        self.assertEqual(sorted(self.checks(result)), ["a", "b"])
        self.assertIn(("cycle", "a, b"), self.kinds(result))

    def test_no_changes(self):
        result = ac.plan(self.modules, self.always, [], {})
        self.assertEqual(result["checks"], [])
        self.assertIn("No ledger module", ac.render_text(result))


class LedgerValidationTests(unittest.TestCase):
    def assert_invalid(self, data, fragment):
        ledger = LedgerFile(data)
        try:
            with self.assertRaises(ac.LedgerError) as ctx:
                ac.load_ledger(ledger.path)
            self.assertIn(fragment, str(ctx.exception))
        finally:
            ledger.close()

    def test_unknown_downstream(self):
        self.assert_invalid({"modules": {"a": {"paths": ["a/"], "downstream": ["zzz"]}}}, "unknown module")

    def test_missing_paths_and_bad_check(self):
        self.assert_invalid({"modules": {"a": {"check": "x"}}}, "paths")
        self.assert_invalid({"modules": {"a": {"paths": ["a/"], "check": 5}}}, "check")

    def test_bad_json_and_empty(self):
        self.assert_invalid("{oops", "invalid JSON")
        self.assert_invalid({"modules": {}}, "non-empty")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.ledger = LedgerFile(LEDGER)

    def tearDown(self):
        self.ledger.close()

    def test_strict_exit_and_json(self):
        code, out, _ = run_cli("--ledger", str(self.ledger.path), "--changed", "pipelines/ingest/a.py", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["always"], ["ruff check ."])
        code, _, _ = run_cli("--ledger", str(self.ledger.path), "--changed", "pipelines/ingest/a.py", "--strict")
        self.assertEqual(code, 1)
        code, _, _ = run_cli("--ledger", str(self.ledger.path), "--changed", "pipelines/export/a.py", "--strict")
        self.assertEqual(code, 0)

    def test_bad_exempt_and_missing_ledger_exit_2(self):
        code, _, err = run_cli("--ledger", str(self.ledger.path), "--changed", "x", "--exempt", "nobody=reason")
        self.assertEqual(code, 2)
        self.assertIn("--exempt", err)
        code, _, _ = run_cli("--ledger", str(self.ledger.path) + ".missing", "--changed", "x")
        self.assertEqual(code, 2)

    def test_changed_from_file(self):
        listing = self.ledger.path.parent / "changed.txt"
        listing.write_text("pipelines/report/r.py\n\n", encoding="utf-8")
        code, out, _ = run_cli("--ledger", str(self.ledger.path), "--changed-from", str(listing))
        self.assertEqual(code, 0)
        self.assertIn("changed  report", out)

    def test_help(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("never runs them", out)

    def test_output_does_not_depend_on_input_order(self):
        ledger = ("--ledger", str(self.ledger.path))
        first = run_cli(*ledger, "--changed", "pipelines/clean/b.py", "pipelines/ingest/a.py")[1]
        second = run_cli(*ledger, "--changed", "pipelines/ingest/a.py", "pipelines/clean/b.py")[1]
        self.assertEqual(first, second)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class GitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        env_args = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]

        def git(*args):
            subprocess.run(["git", *env_args, *args], cwd=self.root, check=True, capture_output=True)

        git("init", "-q", "-b", "main")
        (self.root / "pipelines" / "ingest").mkdir(parents=True)
        (self.root / "pipelines" / "ingest" / "a.py").write_text("x = 1\n")
        git("add", ".")
        git("commit", "-q", "-m", "base")
        git("switch", "-q", "-c", "feature")
        (self.root / "pipelines" / "ingest" / "a.py").write_text("x = 2\n")
        git("commit", "-q", "-am", "change")
        (self.root / "pipelines" / "export").mkdir(parents=True)
        (self.root / "pipelines" / "export" / "new.py").write_text("y = 1\n")   # untracked
        self.ledger = LedgerFile(LEDGER)

    def tearDown(self):
        self.ledger.close()
        self._tmp.cleanup()

    def test_git_collects_committed_and_untracked_changes(self):
        code, out, err = run_cli("--ledger", str(self.ledger.path), "--git", "main", "--root", str(self.root), "--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(sorted(data["direct"]), ["export", "ingest"])

    def test_unknown_base_exit_2(self):
        code, _, err = run_cli("--ledger", str(self.ledger.path), "--git", "no-such-ref", "--root", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("failed", err)


if __name__ == "__main__":
    unittest.main()
