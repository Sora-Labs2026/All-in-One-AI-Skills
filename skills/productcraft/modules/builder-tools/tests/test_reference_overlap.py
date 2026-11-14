import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reference_overlap as ro  # noqa: E402

PASSAGE = "our tide tables update every six minutes so skippers can plan the harbour exit safely"


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = ro.main(argv)
    return code, out.getvalue()


class ReferenceOverlapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.site, self.ref = root / "site", root / "ref"
        self.site.mkdir()
        self.ref.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, base, name, content, binary=False):
        p = base / name
        p.parent.mkdir(parents=True, exist_ok=True)
        (p.write_bytes if binary else p.write_text)(content)
        return p

    def test_no_leads_exits_zero(self):
        self.write(self.site, "index.html", "<h1>Plan your week</h1><p>Simple calendars for small teams.</p>")
        self.write(self.ref, "page.html", "<h1>Ferry times</h1><p>Departures from the north pier.</p>")
        code, out = run(["--site", str(self.site), "--reference", str(self.ref)])
        self.assertEqual(code, 0)
        self.assertIn("0 lead(s)", out)

    def test_exact_binary_match(self):
        self.write(self.site, "img/hero.png", b"\x89PNG fake bytes", binary=True)
        self.write(self.ref, "assets/other-name.png", b"\x89PNG fake bytes", binary=True)
        code, out = run(["--site", str(self.site), "--reference", str(self.ref), "--json"])
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(len(report["exact_files"]), 1)
        self.assertTrue(report["exact_files"][0]["site"].endswith("hero.png"))

    def test_same_name_different_content(self):
        self.write(self.site, "logo.svg", "<svg><path d='M0 0h1'/></svg>")
        self.write(self.ref, "logo.svg", "<svg><path d='M0 0h2'/></svg>")
        report = ro.analyze(self.site, [self.ref], 8, [])
        self.assertEqual(len(report["same_name_different_content"]), 1)
        self.assertEqual(report["exact_files"], [])

    def test_shared_text_is_merged_into_one_passage(self):
        self.write(self.site, "index.html", f"<main><p>Welcome. {PASSAGE.capitalize()}.</p></main>")
        self.write(self.ref, "ref.md", f"Intro text. {PASSAGE}! More text follows here.")
        report = ro.analyze(self.site, [self.ref], 8, [])
        self.assertEqual(len(report["shared_text"]), 1)
        passages = report["shared_text"][0]["passages"]
        self.assertEqual(len(passages), 1)
        self.assertIn("tide tables update every six minutes", passages[0])

    def test_script_and_style_text_ignored_in_markup(self):
        self.write(self.site, "index.html", f"<script>var s = '{PASSAGE}';</script><p>Different words entirely here.</p>")
        self.write(self.ref, "ref.txt", PASSAGE)
        report = ro.analyze(self.site, [self.ref], 8, [])
        self.assertEqual(report["shared_text"], [])

    def test_alt_text_is_compared(self):
        self.write(self.site, "index.html", f'<img src="a.jpg" alt="{PASSAGE}">')
        self.write(self.ref, "ref.txt", PASSAGE)
        report = ro.analyze(self.site, [self.ref], 8, [])
        self.assertEqual(len(report["shared_text"]), 1)

    def test_distinctive_numbers(self):
        self.write(self.site, "pricing.html", "<p>Only $1,299 a year, used by 37.5% of crews since 2021.</p>")
        self.write(self.ref, "notes.txt", "Price $1,299. Share 37.5%. Founded 2021. 12 ships.")
        report = ro.analyze(self.site, [self.ref], 8, [])
        nums = report["shared_numbers"][0]["numbers"]
        self.assertIn("$1,299", nums)
        self.assertIn("37.5%", nums)
        self.assertNotIn("2021", nums)

    def test_excluded_folder_skipped(self):
        self.write(self.site, "dist/copy.bin", b"same", binary=True)
        self.write(self.ref, "copy.bin", b"same", binary=True)
        report = ro.analyze(self.site, [self.ref], 8, ["dist"])
        self.assertEqual(report["exact_files"], [])

    def test_missing_path_is_usage_error(self):
        code, _ = run(["--site", str(self.site / "nope"), "--reference", str(self.ref)])
        self.assertEqual(code, 2)

    def test_small_ngram_rejected(self):
        code, _ = run(["--site", str(self.site), "--reference", str(self.ref), "--ngram", "2"])
        self.assertEqual(code, 2)

    def test_help_exits_zero(self):
        code, out = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Read-only", out)

    def test_reference_may_be_single_file(self):
        ref_file = self.write(self.ref, "one.txt", PASSAGE)
        self.write(self.site, "a.md", PASSAGE)
        report = ro.analyze(self.site, [ref_file], 8, [])
        self.assertEqual(report["files_scanned"]["references"], 1)
        self.assertEqual(len(report["shared_text"]), 1)


if __name__ == "__main__":
    unittest.main()
