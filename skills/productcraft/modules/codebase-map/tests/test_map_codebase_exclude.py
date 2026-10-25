"""Offline tests for map_codebase.py --exclude; no network.

Reuses the fixture helpers of test_map_codebase.py: every test maps a fresh copy
of a fixture tree in a temporary directory.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from test_map_codebase import by_path, full_map, materialize, module


class ExcludeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.py = materialize("pyproj", self._tmp.name)
        self.js = materialize("jsproj", self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = module.main(list(argv))
            except SystemExit as exc:  # argparse errors
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_directory_pattern_removes_the_subtree(self):
        m = full_map(self.py, exclude=["src/django_site/"])
        files = by_path(m)
        self.assertFalse(any(p.startswith("src/django_site/") for p in files))
        self.assertIn("src/app/core.py", files)
        self.assertEqual(m["stats"]["exclude"], ["src/django_site/"])
        self.assertEqual(m["stats"]["excluded_paths"], 1)  # the directory itself, not each file
        self.assertFalse(any(r["framework"] == "django" for r in m["routes"]))

    def test_unanchored_glob_matches_at_any_depth(self):
        m = full_map(self.js, exclude=["*.test.js", "styles.css"])
        files = by_path(m)
        self.assertNotIn("src/server.test.js", files)
        self.assertNotIn("src/styles.css", files)
        self.assertIn("src/server.js", files)
        self.assertEqual(m["stats"]["excluded_paths"], 2)

    def test_exclude_beats_a_gitignore_negation(self):
        # the fixture's .gitignore ignores *.log but re-includes keep.log
        self.assertIn("keep.log", by_path(full_map(self.py)))
        self.assertNotIn("keep.log", by_path(full_map(self.py, exclude=["keep.log"])))

    def test_exclude_applies_without_gitignore(self):
        m = full_map(self.py, use_gitignore=False, exclude=["generated/"])
        files = by_path(m)
        self.assertNotIn("generated/skip.py", files)
        self.assertIn("debug.log", files)  # gitignore really is off
        self.assertEqual(m["stats"]["excluded_paths"], 1)

    def test_imports_of_excluded_files_are_reported_unresolved(self):
        m = full_map(self.js, exclude=["src/lib/util.ts"])
        index = by_path(m)["src/index.ts"]
        self.assertIn("./lib/util", index["unresolved"])
        self.assertNotIn("src/lib/util.ts", index["imports"])

    def test_no_exclude_keeps_previous_output(self):
        m = full_map(self.py)
        self.assertEqual(m["stats"]["exclude"], [])
        self.assertEqual(m["stats"]["excluded_paths"], 0)

    def test_cli_repeatable_flag_and_markdown_note(self):
        code, out, _ = self.run_cli(str(self.py), "--exclude", "src/django_site/", "--exclude", "*.toml")
        self.assertEqual(code, 0)
        self.assertIn("2 excluded by --exclude", out)
        code, out, _ = self.run_cli(str(self.py))
        self.assertEqual(code, 0)
        self.assertNotIn("--exclude", out)

    def test_cli_json_records_patterns(self):
        code, out, _ = self.run_cli(str(self.py), "--json", "--exclude", "tests/")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["stats"]["exclude"], ["tests/"])
        self.assertFalse(any(f["path"].startswith("tests/") for f in data["files"]))

    def test_cli_rejects_empty_and_negated_patterns(self):
        for bad in ("", "!keep.log", "# comment"):
            code, _, err = self.run_cli(str(self.py), "--exclude", bad)
            self.assertEqual(code, 2, bad)
            self.assertIn("invalid --exclude pattern", err)

    def test_focus_inside_an_excluded_directory_is_an_error(self):
        code, _, err = self.run_cli(str(self.py), "--exclude", "src/django_site/", "--focus", "src/django_site/urls.py")
        self.assertEqual(code, 2)
        self.assertIn("excluded", err)


if __name__ == "__main__":
    unittest.main()
