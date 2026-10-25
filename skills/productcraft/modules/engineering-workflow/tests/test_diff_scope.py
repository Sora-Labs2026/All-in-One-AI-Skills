"""Offline tests for diff_scope.py using synthetic diffs only; no network."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "diff_scope.py"
spec = importlib.util.spec_from_file_location("diff_scope", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def git_file(path, hunks, header_extra=""):
    """Build one `diff --git` section. hunks: list of (old_start, new_start, lines)."""
    out = [f"diff --git a/{path} b/{path}"]
    if header_extra:
        out.append(header_extra)
    out += [f"--- a/{path}", f"+++ b/{path}"]
    for old_start, new_start, lines in hunks:
        old_n = sum(1 for x in lines if x[:1] in (" ", "-"))
        new_n = sum(1 for x in lines if x[:1] in (" ", "+"))
        out.append(f"@@ -{old_start},{old_n} +{new_start},{new_n} @@")
        out += lines
    return "\n".join(out) + "\n"


def codes(report, severity=None):
    return [f["code"] for f in report["findings"] if severity is None or f["severity"] == severity]


def run_cli(argv, stdin_text=None):
    out = io.StringIO()
    old_stdin = sys.stdin
    try:
        if stdin_text is not None:
            sys.stdin = io.StringIO(stdin_text)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = module.main(argv)
            except SystemExit as exc:  # argparse --help / errors
                code = exc.code
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue()


class ParseTests(unittest.TestCase):
    def test_counts_statuses_and_line_numbers(self):
        diff = (
            git_file("src/app.py", [(10, 10, [" keep", "-old", "+new", "+extra", " keep"])])
            + "diff --git a/src/new.py b/src/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/src/new.py\n"
            "@@ -0,0 +1,2 @@\n+a = 1\n+b = 2\n"
            + "diff --git a/src/gone.py b/src/gone.py\ndeleted file mode 100644\n--- a/src/gone.py\n+++ /dev/null\n"
            "@@ -1,1 +0,0 @@\n-x = 1\n"
            + "diff --git a/src/old_name.py b/src/new_name.py\nsimilarity index 100%\n"
            "rename from src/old_name.py\nrename to src/new_name.py\n"
            + "diff --git a/img/logo.png b/img/logo.png\nBinary files a/img/logo.png and b/img/logo.png differ\n"
        )
        files = {f.path: f for f in module.parse_diff(diff)}
        self.assertEqual((files["src/app.py"].added, files["src/app.py"].removed), (2, 1))
        self.assertEqual([n for n, _ in files["src/app.py"].added_lines], [11, 12])
        self.assertEqual(files["src/new.py"].status, "A")
        self.assertEqual(files["src/gone.py"].status, "D")
        self.assertEqual(files["src/new_name.py"].status, "R")
        self.assertEqual(files["src/new_name.py"].old_path, "src/old_name.py")
        self.assertTrue(files["img/logo.png"].binary)

    def test_removed_line_that_looks_like_a_header_stays_in_hunk(self):
        diff = git_file("notes.sql", [(1, 1, ["--- a comment that was removed", "+-- replacement", " select 1;"])])
        (f,) = module.parse_diff(diff)
        self.assertEqual((f.added, f.removed), (1, 1))

    def test_plain_unified_diff_without_git_headers(self):
        diff = "--- lib/a.py\t2026-01-01\n+++ lib/a.py\t2026-01-02\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        (f,) = module.parse_diff(diff)
        self.assertEqual((f.path, f.status, f.added, f.removed), ("lib/a.py", "M", 1, 1))

    def test_kind_classification(self):
        cases = {
            "tests/test_api.py": "test", "src/api_test.go": "test", "web/button.spec.tsx": "test",
            "src/UserServiceTest.java": "test", "src/latest.py": "code", "docs/guide.md": "docs",
            "package-lock.json": "lockfile", "requirements-dev.txt": "manifest", "dist/app.min.js": "generated",
            "config/settings.yaml": "other",
        }
        for path, kind in cases.items():
            self.assertEqual(module.kind_of(path), kind, path)


class FindingTests(unittest.TestCase):
    def test_debug_leftovers_by_language_without_false_positives(self):
        diff = (
            git_file("web/app.ts", [(1, 1, ["+console.log(user)", "+  debugger;", " const a = 1;"])])
            + git_file("svc/job.py", [(1, 1, ["+breakpoint()", "+model.fit(x, y)", "+print('done')", " pass"])])
            + git_file("core/lib.rs", [(1, 1, ["+let v = dbg!(x);", " fn main() {}"])])
        )
        report = module.analyze(module.parse_diff(diff))
        hits = [(f["path"], f["line"]) for f in report["findings"] if f["code"] == "DEBUG_LEFTOVER"]
        self.assertEqual(sorted(hits), [("core/lib.rs", 1), ("svc/job.py", 1), ("web/app.ts", 1), ("web/app.ts", 2)])

    def test_findings_never_echo_line_text(self):
        token = "tok_" + "z" * 20
        diff = git_file("web/app.js", [(1, 1, [f"+console.log('{token}')", " x();"])])
        report = module.analyze(module.parse_diff(diff))
        self.assertIn("DEBUG_LEFTOVER", codes(report))
        self.assertNotIn(token, json.dumps(report))
        self.assertNotIn(token, module.format_text(report))

    def test_focused_and_skipped_tests_only_in_test_files(self):
        diff = (
            git_file("web/cart.test.ts", [(1, 1, ["+it.only('adds item', () => {})", "+it.skip('removes', () => {})", " x"])])
            + git_file("tests/test_cart.py", [(1, 1, ["+@pytest.mark.skip(reason='later')", "+@pytest.mark.skipif(WIN, reason='posix')",
                                                     "+    fit(model, rows)", " x"])])
            + git_file("web/stream.ts", [(1, 1, ["+reader.skip(4)", "+test.only = flag", " x"])])
        )
        report = module.analyze(module.parse_diff(diff))
        got = sorted((f["code"], f["path"]) for f in report["findings"] if f["code"] in ("FOCUSED_TEST", "SKIPPED_TEST"))
        self.assertEqual(got, [("FOCUSED_TEST", "web/cart.test.ts"), ("SKIPPED_TEST", "tests/test_cart.py"),
                               ("SKIPPED_TEST", "web/cart.test.ts")])

    def test_assertions_removed_and_test_file_deleted(self):
        diff = git_file("tests/test_tax.py", [(1, 1, ["-    assert tax(0) == 0", "-    assert tax(10) == 1", "+    tax(10)", " def t(): pass"])])
        diff += "diff --git a/tests/test_old.py b/tests/test_old.py\ndeleted file mode 100644\n--- a/tests/test_old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-def test_x(): pass\n"
        report = module.analyze(module.parse_diff(diff))
        self.assertIn("ASSERTIONS_REMOVED", codes(report))
        self.assertIn("TEST_FILE_DELETED", codes(report))

    def test_whitespace_only_hunk_detected_and_real_change_ignored(self):
        diff = (
            git_file("src/fmt.py", [(1, 1, ["-x = [1,2]", "+x = [1,2]  ", "-y=1", "+y=1\r", "+", " z = 3"])])
            + git_file("src/real.py", [(1, 1, ["-y = 1", "+y = 2", " z = 3"])])
        )
        report = module.analyze(module.parse_diff(diff))
        ws = [f["path"] for f in report["findings"] if f["code"] == "WHITESPACE_ONLY"]
        self.assertEqual(ws, ["src/fmt.py"])

    def test_conflict_markers(self):
        diff = git_file("src/a.py", [(1, 1, ["+<<<<<<< HEAD", "+a = 1", "+=======", "+a = 2", "+>>>>>>> feature", " b"])])
        diff += git_file("docs/title.rst", [(1, 1, ["+Title", "+=======", " x"])])
        report = module.analyze(module.parse_diff(diff))
        hits = [(f["path"], f["line"]) for f in report["findings"] if f["code"] == "CONFLICT_MARKER"]
        self.assertEqual(hits, [("src/a.py", 1), ("src/a.py", 3), ("src/a.py", 5)])

    def test_scope_globs_and_directory_prefixes(self):
        diff = (
            git_file("src/billing/invoice.py", [(1, 1, ["-a", "+b"])])
            + git_file("tests/billing/test_invoice.py", [(1, 1, ["-a", "+b"])])
            + git_file("src/auth/login.py", [(1, 1, ["-a", "+b"])])
        )
        report = module.analyze(module.parse_diff(diff), scopes=["src/billing", "tests/*/test_*.py"])
        self.assertEqual([f["path"] for f in report["findings"] if f["code"] == "OUT_OF_SCOPE"], ["src/auth/login.py"])

    def test_lockfile_churn_versus_dependency_change(self):
        lock_only = git_file("package-lock.json", [(1, 1, ['-  "v": 1', '+  "v": 2'])])
        report = module.analyze(module.parse_diff(lock_only))
        self.assertIn("LOCKFILE_WITHOUT_MANIFEST", codes(report, "WARN"))
        both = lock_only + git_file("package.json", [(1, 1, ['+  "left-pad": "1.3.0",', " {"])])
        report = module.analyze(module.parse_diff(both))
        self.assertNotIn("LOCKFILE_WITHOUT_MANIFEST", codes(report))
        self.assertEqual(codes(report).count("DEPENDENCY_CHANGE"), 2)

    def test_code_without_test_change_is_info_only(self):
        code_only = git_file("src/a.py", [(1, 1, ["-a = 1", "+a = 2"])])
        report = module.analyze(module.parse_diff(code_only))
        self.assertEqual(codes(report), ["CODE_WITHOUT_TEST_CHANGE"])
        self.assertEqual(report["summary"]["warn"], 0)
        with_test = code_only + git_file("tests/test_a.py", [(1, 1, ["+    assert a == 2", " def test(): pass"])])
        self.assertNotIn("CODE_WITHOUT_TEST_CHANGE", codes(module.analyze(module.parse_diff(with_test))))

    def test_large_diff_threshold_mode_change_generated_and_todo(self):
        many = ["+line %d" % i for i in range(30)]
        diff = git_file("src/big.py", [(1, 1, many + [" end"])], header_extra="old mode 100644\nnew mode 100755")
        diff += git_file("build/out.js", [(1, 1, ["+x()", " y()"])])
        diff += git_file("src/todo.py", [(1, 1, ["+# TODO handle retries", "+# FIXME units", " pass"])])
        report = module.analyze(module.parse_diff(diff), max_lines=20)
        found = codes(report)
        for expected in ("LARGE_DIFF", "MODE_CHANGE", "GENERATED_FILE", "NEW_TODO"):
            self.assertIn(expected, found)
        self.assertEqual(found.count("NEW_TODO"), 1)
        self.assertNotIn("LARGE_DIFF", codes(module.analyze(module.parse_diff(diff), max_lines=0)))

    def test_clean_change_has_no_findings_and_output_is_deterministic(self):
        diff = git_file("src/a.py", [(1, 1, ["-a = 1", "+a = 2"])]) + git_file("tests/test_a.py", [(1, 1, ["-    assert a == 1", "+    assert a == 2"])])
        first = module.analyze(module.parse_diff(diff))
        second = module.analyze(module.parse_diff(diff))
        self.assertEqual(first["findings"], [])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertIn("Findings: none", module.format_text(first))


class CliTests(unittest.TestCase):
    def test_help_exits_zero(self):
        code, out = run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Read-only", out)

    def test_stdin_json_and_strict_exit_codes(self):
        diff = git_file("web/app.js", [(1, 1, ["+console.log(1)", " x()"])])
        code, out = run_cli(["--diff", "-", "--json"], stdin_text=diff)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["summary"]["files"], 1)
        code, _ = run_cli(["--diff", "-", "--strict"], stdin_text=diff)
        self.assertEqual(code, 1)
        clean = git_file("docs/a.md", [(1, 1, ["-old", "+new"])])
        code, _ = run_cli(["--diff", "-", "--strict"], stdin_text=clean)
        self.assertEqual(code, 0)

    def test_missing_file_is_input_error(self):
        code, _ = run_cli(["--diff", os.path.join(tempfile.gettempdir(), "does-not-exist-diff-scope.patch")])
        self.assertEqual(code, 2)

    def test_git_mode_reads_working_tree_and_lists_untracked(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)

            def git(*args):
                subprocess.run(["git", "-C", d, "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                               check=True, capture_output=True, env=env)

            git("init", "-q")
            Path(d, "app.py").write_text("a = 1\n")
            git("add", "app.py")
            git("commit", "-q", "-m", "init")
            Path(d, "app.py").write_text("a = 2\n")
            Path(d, "notes.txt").write_text("scratch\n")
            code, out = run_cli(["--repo", d, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual([f["path"] for f in data["files"]], ["app.py"])
            untracked = [f["message"] for f in data["findings"] if f["code"] == "UNTRACKED_FILES"]
            self.assertEqual(len(untracked), 1)
            self.assertIn("notes.txt", untracked[0])
            git("add", "app.py")
            git("commit", "-q", "-m", "change")
            code, out = run_cli(["--repo", d, "--git", "HEAD~1..HEAD", "--json"])
            self.assertEqual(code, 0)
            self.assertNotIn("UNTRACKED_FILES", [f["code"] for f in json.loads(out)["findings"]])


if __name__ == "__main__":
    unittest.main()
