"""Tests for scripts/lint_skill.py. Standard library only; skill folders are built in a temp dir
at run time so this package never ships a second SKILL.md."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import lint_skill as ls  # noqa: E402

GOOD_DESC = ("Builds and checks invoice PDFs from order data. Use when the user asks for an invoice, "
             "a billing PDF or a receipt for an order, or wants an existing invoice corrected.")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "invoice-maker"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def skill(self, frontmatter, body="# Invoice maker\n\nSee [layout](references/layout.md).\n"):
        self.write("SKILL.md", f"---\n{frontmatter}\n---\n{body}")

    def codes(self, findings, level=None):
        return sorted(f.code for f in findings if level is None or f.level == level)

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = ls.main(list(args))
        return code, out.getvalue()


class FrontmatterTests(Base):
    def test_valid_skill_is_clean(self):
        self.skill(f"name: invoice-maker\ndescription: {GOOD_DESC}\nlicense: MIT\nmetadata:\n  version: \"1.0\"")
        self.write("references/layout.md", "# Layout\n")
        self.assertEqual(ls.lint(str(self.root)), [])

    def test_missing_frontmatter(self):
        self.write("SKILL.md", "# No frontmatter\n")
        self.assertIn("SK002", self.codes(ls.lint(str(self.root)), "error"))

    def test_unterminated_frontmatter(self):
        self.write("SKILL.md", "---\nname: invoice-maker\n# body\n")
        self.assertIn("SK002", self.codes(ls.lint(str(self.root))))

    def test_bad_name_and_folder_mismatch(self):
        self.skill(f"name: Invoice_Maker\ndescription: {GOOD_DESC}")
        self.write("references/layout.md", "x")
        codes = self.codes(ls.lint(str(self.root)))
        self.assertIn("SK011", codes)
        self.assertIn("SK012", codes)

    def test_name_rules(self):
        for bad in ("-lead", "trail-", "dou--ble", "a" * 65):
            self.assertIsNone(ls.NAME_RE.match(bad) if len(bad) <= 64 else None, bad)
        for good in ("pdf", "pdf-tools", "a1-b2"):
            self.assertTrue(ls.NAME_RE.match(good), good)

    def test_description_limits_and_trigger_wording(self):
        self.skill("name: invoice-maker\ndescription: " + "x" * 1100)
        self.write("references/layout.md", "x")
        codes = self.codes(ls.lint(str(self.root)))
        self.assertIn("SK021", codes)
        self.assertIn("SK023", codes)

    def test_folded_block_description(self):
        self.skill("name: invoice-maker\ndescription: >\n  Builds invoice PDFs from order data.\n  Use when the user asks for an invoice or receipt for an order.")
        self.write("references/layout.md", "x")
        findings = ls.lint(str(self.root))
        self.assertNotIn("SK020", self.codes(findings))
        self.assertNotIn("SK023", self.codes(findings))

    def test_angle_brackets_first_person_and_unknown_key(self):
        self.skill("name: invoice-maker\ndescription: I can make <b>invoices</b>. Use when asked for invoices.\nmodel: fast")
        self.write("references/layout.md", "x")
        codes = self.codes(ls.lint(str(self.root)))
        for code in ("SK022", "SK024", "SK025", "SK032"):
            self.assertIn(code, codes)

    def test_unparseable_frontmatter_reports_line(self):
        self.skill(f"name: invoice-maker\ndescription: {GOOD_DESC}\n  stray: indent\n???")
        findings = [f for f in ls.lint(str(self.root)) if f.code == "SK003"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 5)

    def test_metadata_must_be_mapping(self):
        self.skill(f"name: invoice-maker\ndescription: {GOOD_DESC}\nmetadata: v1")
        self.write("references/layout.md", "x")
        self.assertIn("SK031", self.codes(ls.lint(str(self.root))))


class BodyAndFilesTests(Base):
    def setUp(self):
        super().setUp()
        self.fm = f"name: invoice-maker\ndescription: {GOOD_DESC}"

    def test_broken_link_and_path(self):
        self.skill(self.fm, "Read [rules](references/missing.md) and run `scripts/build.py`.\n")
        findings = ls.lint(str(self.root))
        sk050 = [f for f in findings if f.code == "SK050"]
        self.assertEqual(sorted(f.level for f in sk050), ["error", "warning"])
        self.assertEqual(sk050[0].line, 1 + 4)  # line number counts the frontmatter

    def test_paths_in_code_fences_are_ignored(self):
        self.skill(self.fm, "Example:\n```\nsee `references/not-real.md`\n```\n")
        self.assertNotIn("SK050", self.codes(ls.lint(str(self.root))))

    def test_paths_relative_to_enclosing_module_resolve(self):
        self.skill(self.fm, "Read `modules/tax/GUIDE.md`.\n")
        self.write("modules/tax/GUIDE.md", "Use [rates](references/rates.md) and `assets/form.json`.\n")
        self.write("modules/tax/references/rates.md", "# Rates\n")
        self.write("modules/tax/assets/form.json", "{}")
        self.assertNotIn("SK050", self.codes(ls.lint(str(self.root))))

    def test_long_body_and_empty_body(self):
        self.skill(self.fm, "line\n" * 30)
        self.assertIn("SK040", self.codes(ls.lint(str(self.root), max_body_lines=20)))
        self.skill(self.fm, "\n")
        self.assertIn("SK041", self.codes(ls.lint(str(self.root)), "error"))

    def test_orphan_reference_and_long_reference_without_contents(self):
        self.skill(self.fm, "Read [layout](references/layout.md).\n")
        self.write("references/layout.md", "# Layout\n" + "text\n" * 50)
        self.write("references/forgotten.md", "# Forgotten\n")
        findings = ls.lint(str(self.root), max_ref_lines=20)
        self.assertIn(("SK060", "references/forgotten.md"), [(f.code, f.path) for f in findings])
        self.assertIn(("SK061", "references/layout.md"), [(f.code, f.path) for f in findings])

    def test_file_named_in_table_under_referenced_folder_is_not_orphan(self):
        self.skill(self.fm, "Rules live in `references/rules/`.\n\n| File |\n|---|\n| `tax.md` |\n")
        self.write("references/rules/tax.md", "# Tax\n")
        self.assertNotIn("SK060", self.codes(ls.lint(str(self.root))))

    def test_junk_secrets_nested_skill_and_absolute_paths(self):
        self.skill(self.fm, "Run /home/alex/tools/build.sh first.\n")
        self.write(".env", "TOKEN=abc")
        self.write("scripts/__pycache__/x.pyc", "")
        self.write("examples/other/SKILL.md", "---\nname: other\n---\n")
        codes = self.codes(ls.lint(str(self.root)))
        self.assertGreaterEqual(codes.count("SK070"), 2)
        self.assertIn("SK071", codes)
        self.assertIn("SK051", codes)

    def test_link_outside_skill_is_info(self):
        (self.root.parent / "outside.md").write_text("x", encoding="utf-8")
        self.skill(self.fm, "See [repo notes](../outside.md).\n")
        found = [f for f in ls.lint(str(self.root)) if f.code == "SK052"]
        self.assertEqual([f.level for f in found], ["info"])

    def test_env_example_is_allowed(self):
        self.skill(self.fm, "Copy `assets/.env.example`.\n")
        self.write("assets/.env.example", "TOKEN=")
        self.assertNotIn("SK070", self.codes(ls.lint(str(self.root))))


class CliTests(Base):
    def test_exit_codes_and_json(self):
        self.skill(f"name: invoice-maker\ndescription: {GOOD_DESC}", "Body without links.\n")
        code, out = self.cli(str(self.root))
        self.assertEqual(code, 0)
        self.write("stray/.env", "X=1")
        self.assertEqual(self.cli(str(self.root))[0], 0)
        self.assertEqual(self.cli("--strict", str(self.root))[0], 1)
        code, out = self.cli("--json", str(self.root))
        data = json.loads(out)
        self.assertEqual(data["counts"]["warning"], 1)
        self.assertEqual(out, self.cli("--json", str(self.root))[1])

    def test_error_exit_and_missing_dir(self):
        self.write("SKILL.md", "no frontmatter")
        self.assertEqual(self.cli(str(self.root))[0], 1)
        self.assertEqual(self.cli(str(self.root / "nope"))[0], 2)

    def test_does_not_modify_files(self):
        self.skill(f"name: invoice-maker\ndescription: {GOOD_DESC}")
        before = sorted((p.relative_to(self.root), p.read_bytes()) for p in self.root.rglob("*") if p.is_file())
        self.cli(str(self.root))
        after = sorted((p.relative_to(self.root), p.read_bytes()) for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
