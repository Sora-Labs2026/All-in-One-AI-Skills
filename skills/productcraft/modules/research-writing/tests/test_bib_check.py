"""Tests for scripts/bib_check.py (standard library only).

Run: python3 -B -m unittest discover -s <productcraft>/modules/research-writing/tests -v
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "bib_check.py")
_spec = importlib.util.spec_from_file_location("bib_check", SCRIPT)
bib_check = importlib.util.module_from_spec(_spec)
sys.modules["bib_check"] = bib_check  # dataclasses look the module up while the class is built
_spec.loader.exec_module(bib_check)

CLEAN = """\
@article{smith2020,
  author  = {Smith, Jane and Doe, John},
  title   = {A study of {DNA} repair},
  journal = {Journal of Examples},
  year    = {2020},
  volume  = {12},
  pages   = {101--110},
  doi     = {10.1234/example.2020.001}
}

@book{lee2018,
  author    = {Lee, Ann},
  title     = {Field Methods},
  publisher = {Example Press},
  year      = 2018,
  isbn      = {978-0-306-40615-7}
}
"""


class BibCheckCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bibcheck-")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, content, binary=False):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if binary:
            with open(path, "wb") as fh:
                fh.write(content)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(textwrap.dedent(content))
        return path

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = bib_check.main(list(argv))
            except SystemExit as exc:  # argparse usage errors
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def findings(self, content, *extra):
        path = self.write("refs.bib", content)
        code, out, _ = self.run_main(path, "--json", "--max-year", "2030", *extra)
        data = json.loads(out)
        return code, data["findings"], data["summary"]

    def codes(self, content, *extra):
        return [f["code"] for f in self.findings(content, *extra)[1]]


class CleanAndExitCodes(BibCheckCase):
    def test_clean_file_has_no_findings_and_exits_zero(self):
        code, findings, summary = self.findings(CLEAN)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])
        self.assertEqual(summary["entries"], 2)
        self.assertEqual(summary["dialect"], "bibtex")

    def test_errors_exit_one(self):
        code, _, _ = self.findings("@article{a, title={T}}\n")
        self.assertEqual(code, 1)

    def test_warnings_exit_zero_unless_strict(self):
        content = "@misc{a, title={T}, note={}}\n"
        self.assertEqual(self.findings(content)[0], 0)
        self.assertEqual(self.findings(content, "--strict")[0], 1)

    def test_usage_errors_exit_two(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main(os.path.join(self.tmp, "missing.bib"))[0], 2)
        path = self.write("x.bib", CLEAN)
        self.assertEqual(self.run_main(path, "--ignore", "NOT_A_RULE")[0], 2)
        self.assertEqual(self.run_main(path, "--dialect", "zzz")[0], 2)

    def test_ignore_and_min_level(self):
        content = "@article{a, title={T}, year={2020}, author={X, Y}}\n"
        self.assertIn("MISSING_FIELD", self.codes(content))
        code, findings, _ = self.findings(content, "--ignore", "MISSING_FIELD")
        self.assertEqual((code, findings), (0, []))
        _, findings, _ = self.findings("@misc{a, title={The mRNA story}}\n", "--min-level", "warn")
        self.assertEqual(findings, [])

    def test_text_output_has_location_and_summary(self):
        path = self.write("refs.bib", "@article{a, title={T}}\n")
        code, out, _ = self.run_main(path)
        self.assertEqual(code, 1)
        self.assertIn("refs.bib:1: ERROR MISSING_FIELD a: @article lacks author", out)
        self.assertIn("1 file(s), 1 entries (dialect: bibtex)", out)

    def test_output_is_deterministic(self):
        path = self.write("refs.bib", "@article{b, title={T}}\n@article{a, title={U}}\n@article{a, title={V}}\n")
        first = self.run_main(path, "--json")[1]
        self.assertEqual(first, self.run_main(path, "--json")[1])

    def test_list_rules(self):
        code, out, _ = self.run_main("--list-rules")
        self.assertEqual(code, 0)
        self.assertIn("MALFORMED_DOI", out)
        self.assertIn("UNBALANCED_BRACES", out)


class Structure(BibCheckCase):
    def test_unclosed_entry_at_end_of_file(self):
        codes = self.codes("@article{a,\n  title = {T},\n  year = {2020}\n")
        self.assertIn("UNBALANCED_BRACES", codes)

    def test_unclosed_entry_resyncs_at_next_entry(self):
        content = ("@article{a,\n  author={X, Y},\n  title = {T\n}\n"
                   "@misc{b, title={Fine}}\n")
        _, findings, summary = self.findings(content)
        unbalanced = [f for f in findings if f["code"] == "UNBALANCED_BRACES"]
        self.assertEqual(len(unbalanced), 1)
        self.assertIn("next entry at line 5", unbalanced[0]["message"])
        self.assertEqual(summary["entries"], 2)

    def test_extra_closing_brace_is_reported(self):
        content = "@article{a,\n  title = {T}},\n  year = {2020}\n}\n"
        self.assertIn("UNBALANCED_BRACES", self.codes(content))

    def test_braces_in_comment_lines_are_ignored(self):
        content = "% a stray } in a comment line, contact me@example.org }\n" + CLEAN
        self.assertEqual(self.codes(content), [])

    def test_unterminated_quote(self):
        self.assertIn("UNTERMINATED_QUOTE", self.codes('@misc{a, title = "Open quote}\n'))

    def test_missing_comma_between_fields(self):
        content = "@misc{a,\n  title = {T}\n  note = {N}\n}\n"
        _, findings, _ = self.findings(content)
        missing = [f for f in findings if f["code"] == "MISSING_COMMA"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["line"], 3)

    def test_missing_and_invalid_keys(self):
        self.assertIn("MISSING_KEY", self.codes("@misc{title = {T}}\n"))
        self.assertIn("INVALID_KEY", self.codes("@misc{smith 2020, title = {T}}\n"))

    def test_percent_inside_entry_gets_a_hint(self):
        _, findings, _ = self.findings("@misc{a,\n  % title = {old},\n  title = {T}\n}\n")
        syntax = [f for f in findings if f["code"] == "SYNTAX"]
        self.assertEqual(len(syntax), 1)
        self.assertIn("does not treat %", syntax[0]["message"])

    def test_parenthesized_entry_and_comments_and_preamble(self):
        content = ('@preamble{ "\\newcommand{\\noop}[1]{}" }\n'
                   "@comment{ anything {here} }\n"
                   "@misc(a, title = {Round brackets})\n")
        code, findings, summary = self.findings(content)
        self.assertEqual((code, findings, summary["entries"]), (0, [], 1))

    def test_duplicate_and_empty_fields(self):
        codes = self.codes("@misc{a, title = {T}, title = {U}, note = {}}\n")
        self.assertIn("DUPLICATE_FIELD", codes)
        self.assertIn("EMPTY_FIELD", codes)


class Duplicates(BibCheckCase):
    def test_duplicate_key_points_to_first_definition(self):
        _, findings, _ = self.findings("@misc{a, title={T}}\n@misc{a, title={U}}\n")
        dup = [f for f in findings if f["code"] == "DUPLICATE_KEY"]
        self.assertEqual(len(dup), 1)
        self.assertEqual(dup[0]["line"], 2)
        self.assertIn("refs.bib:1", dup[0]["message"])

    def test_keys_differing_in_case(self):
        self.assertIn("DUPLICATE_KEY_CASE", self.codes("@misc{Smith, title={T}}\n@misc{smith, title={U}}\n"))

    def test_duplicate_doi_ignores_case_and_url_prefix(self):
        content = ("@misc{a, title={One title here}, doi={10.1234/ABC}}\n"
                   "@misc{b, title={Another title}, doi={https://doi.org/10.1234/abc}}\n")
        self.assertIn("DUPLICATE_DOI", self.codes(content))

    def test_possible_duplicate_by_title_and_year(self):
        content = ("@misc{a, title={Deep {Learning} for Proteins}, year={2021}}\n"
                   "@misc{b, title={Deep learning for proteins.}, year={2021}}\n"
                   "@misc{c, title={Deep learning for proteins}, year={2022}}\n")
        _, findings, _ = self.findings(content)
        dups = [f for f in findings if f["code"] == "POSSIBLE_DUPLICATE"]
        self.assertEqual([f["key"] for f in dups], ["b"])

    def test_duplicates_across_files(self):
        one = self.write("one.bib", "@misc{a, title={T}}\n")
        two = self.write("two.bib", "@misc{a, title={U}}\n")
        code, out, _ = self.run_main(one, two)
        self.assertEqual(code, 1)
        self.assertIn("two.bib:1: ERROR DUPLICATE_KEY a:", out)


class RequiredFields(BibCheckCase):
    def test_bibtex_required_fields_with_alternatives(self):
        _, findings, _ = self.findings("@inbook{a, editor={E, F}, title={T}, publisher={P}, year={2000}}\n")
        msgs = [f["message"] for f in findings if f["code"] == "MISSING_FIELD"]
        self.assertEqual(msgs, ["@inbook lacks chapter or pages"])

    def test_soft_required_fields_are_warnings(self):
        _, findings, _ = self.findings("@unpublished{a, author={A, B}, title={T}}\n")
        self.assertEqual([(f["code"], f["level"]) for f in findings], [("MISSING_FIELD", "WARN")])

    def test_biblatex_detected_and_aliases_accepted(self):
        content = ("@online{web, author={Org}, title={Page}, date={2024-03-01}, url={https://example.org}}\n"
                   "@article{art, author={A, B}, title={T}, journal={J}, date={2019}}\n")
        code, findings, summary = self.findings(content)
        self.assertEqual(summary["dialect"], "biblatex")
        self.assertEqual((code, findings), (0, []))

    def test_forced_bibtex_dialect_flags_biblatex_types(self):
        content = "@online{web, author={Org}, title={Page}, year={2024}, url={https://example.org}}\n"
        self.assertIn("UNKNOWN_TYPE", self.codes(content, "--dialect", "bibtex"))

    def test_biblatex_report_requires_type_as_warning(self):
        _, findings, _ = self.findings("@report{r, author={A, B}, title={T}, institution={I}, date={2020}}\n")
        self.assertEqual([(f["code"], f["level"]) for f in findings], [("MISSING_FIELD", "WARN")])

    def test_crossref_parent_supplies_fields(self):
        content = ("@inproceedings{paper, author={A, B}, title={T}, crossref={conf}}\n"
                   "@proceedings{conf, title={Proceedings of Things}, year={2020}}\n")
        self.assertEqual(self.codes(content), [])

    def test_missing_crossref_parent(self):
        content = "@inproceedings{paper, author={A, B}, title={T}, crossref={nowhere}}\n"
        codes = self.codes(content)
        self.assertIn("MISSING_CROSSREF", codes)
        self.assertIn("MISSING_FIELD", codes)

    def test_string_macros_and_month_names(self):
        content = ('@string{jx = "Journal X"}\n'
                   "@article{a, author={A, B}, title={T}, journal=jx, year=2001, month=mar}\n"
                   "@misc{b, title={T2}, note=undefinedmacro}\n")
        _, findings, _ = self.findings(content)
        self.assertEqual([f["code"] for f in findings], ["UNDEFINED_STRING"])
        self.assertIn("undefinedmacro", findings[0]["message"])

    def test_string_concatenation(self):
        content = ('@string{pre = "Proc. of "}\n'
                   '@inproceedings{a, author={A, B}, title={T}, booktitle=pre # "Things", year={2020}}\n')
        self.assertEqual(self.codes(content), [])


class Identifiers(BibCheckCase):
    def test_malformed_dois(self):
        for doi in ("not-a-doi", "10.12/short-prefix", "10.1234/a 10.1234/b", "11.1234/abc"):
            with self.subTest(doi=doi):
                self.assertIn("MALFORMED_DOI", self.codes("@misc{a, title={T}, doi={%s}}\n" % doi))

    def test_doi_variants(self):
        self.assertEqual(self.codes("@misc{a, title={T}, doi={doi:10.1234/abc}}\n"), ["DOI_AS_URL"])
        self.assertEqual(self.codes("@misc{a, title={T}, doi={10.1234/a\\_b}}\n"), ["DOI_BACKSLASH"])
        self.assertEqual(self.codes("@misc{a, title={T}, doi={10.1234/abc.}}\n"), ["DOI_TRAILING_PUNCT"])
        self.assertEqual(self.codes("@misc{a, title={T}, doi={10.1002/(SICI)1097-4571(199806)49:8<693::AID-ASI4>3.0.CO;2-0}}\n"), [])
        self.assertEqual(self.codes("@misc{a, title={T}, url={https://doi.org/10.1234/abc}}\n"), ["DOI_IN_URL"])

    def test_years(self):
        cases = {"20200": "MALFORMED_YEAR", "2020a": "YEAR_SUFFIX", "in press": "YEAR_NOT_NUMERIC",
                 "2019--2020": "YEAR_NOT_NUMERIC", "2031": "YEAR_IN_FUTURE"}
        for year, code in cases.items():
            with self.subTest(year=year):
                self.assertEqual(self.codes("@misc{a, title={T}, year={%s}}\n" % year), [code])
        self.assertEqual(self.codes("@misc{a, title={T}, year={2030}}\n"), [])

    def test_biblatex_dates(self):
        ok = ("2020", "2020-02", "2020-02-29", "2019/2020", "2020-01-05/2020-01-09", "2020/")
        for date in ok:
            with self.subTest(date=date):
                self.assertEqual(self.codes("@misc{a, author={A, B}, title={T}, date={%s}}\n" % date), [])
        for date in ("2020-13", "20-01-2020", "spring 2020"):
            with self.subTest(date=date):
                self.assertIn("MALFORMED_DATE", self.codes("@misc{a, author={A, B}, title={T}, date={%s}}\n" % date))
        self.assertIn("YEAR_DATE_MISMATCH", self.codes("@misc{a, author={A, B}, title={T}, year={2019}, date={2020-01}}\n"))

    def test_arxiv_isbn_pmid(self):
        good = ("@misc{a, title={T}, archiveprefix={arXiv}, eprint={2103.14030v2}, isbn={0-306-40615-2},"
                " pmid={34265844}}\n@misc{b, title={U}, eprinttype={arxiv}, eprint={hep-th/9901001}}\n")
        self.assertEqual(self.codes(good, "--dialect", "bibtex"), [])
        bad = ("@misc{a, title={T}, archiveprefix={arXiv}, eprint={21.03.14030}, isbn={978-0-306-40615-8},"
               " pmid={PMC123}}\n")
        self.assertEqual(sorted(self.codes(bad)), ["MALFORMED_ARXIV", "MALFORMED_ISBN", "MALFORMED_PMID"])

    def test_list_ids(self):
        content = ("@misc{a, title={T}, doi={https://doi.org/10.1234/abc}}\n"
                   "@misc{b, title={U}, archiveprefix={arXiv}, eprint={2101.00001}, pmid={123}}\n"
                   "@misc{c, title={V}}\n")
        path = self.write("ids.bib", content)
        code, out, _ = self.run_main(path, "--list-ids")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["key\tdoi\tarxiv\tpmid", "a\t10.1234/abc\t\t", "b\t\t2101.00001\t123"])


class NamesAndStyle(BibCheckCase):
    def test_author_separators(self):
        self.assertIn("AUTHOR_SEPARATOR", self.codes("@misc{a, title={T}, author={Smith, J., Doe, J.}}\n"))
        self.assertIn("AUTHOR_SEPARATOR", self.codes("@misc{a, title={T}, author={Smith, J.; Doe, J.}}\n"))
        self.assertEqual(self.codes("@misc{a, title={T}, author={King, Jr., Martin and {Acme, Inc.}}}\n"), [])

    def test_et_al(self):
        self.assertIn("ET_AL", self.codes("@misc{a, title={T}, author={Smith, J. and et al.}}\n"))
        self.assertEqual(self.codes("@misc{a, title={T}, author={Smith, J. and others}}\n"), [])

    def test_unprotected_capitals_and_page_ranges(self):
        _, findings, _ = self.findings("@misc{a, title={Editing mRNA with {CRISPR}}, pages={5-9}}\n")
        self.assertEqual(sorted((f["code"], f["level"]) for f in findings),
                         [("PAGES_SINGLE_HYPHEN", "INFO"), ("UNPROTECTED_CAPS", "INFO")])
        caps = [f for f in findings if f["code"] == "UNPROTECTED_CAPS"][0]
        self.assertIn("mRNA", caps["message"])
        self.assertNotIn("CRISPR", caps["message"])


class Citations(BibCheckCase):
    def test_latex_citations(self):
        bib = self.write("refs.bib", CLEAN + "@misc{spare, title={Never cited}}\n@misc{Mixed, title={M}}\n")
        tex = self.write("paper.tex", r"""
            % \cite{commented_out}
            As shown \citep[see][p.~4]{smith2020, ghost} and \Textcite{lee2018}.
            Escaped 50\% is not a comment \cite{mixed}.
            \cites[a]{lee2018}[b]{alsoghost}
            """)
        code, out, _ = self.run_main(bib, "--cited-in", tex, "--json")
        data = json.loads(out)
        got = sorted((f["code"], f["key"]) for f in data["findings"])
        self.assertEqual(got, [("CITE_KEY_CASE", "mixed"), ("MISSING_ENTRY", "alsoghost"),
                               ("MISSING_ENTRY", "ghost"), ("UNCITED_ENTRY", "spare")])
        self.assertEqual(code, 1)

    def test_nocite_star_suppresses_uncited(self):
        bib = self.write("refs.bib", CLEAN)
        tex = self.write("paper.tex", "\\nocite{*}\n")
        code, out, _ = self.run_main(bib, "--cited-in", tex, "--json")
        self.assertEqual((code, json.loads(out)["findings"]), (0, []))

    def test_aux_files_bibtex_and_biblatex(self):
        bib = self.write("refs.bib", CLEAN)
        aux = self.write("paper.aux", "\\citation{smith2020,lee2018}\n\\abx@aux@cite{0}{ghost}\n")
        code, out, _ = self.run_main(bib, "--cited-in", aux, "--json")
        got = [(f["code"], f["key"]) for f in json.loads(out)["findings"]]
        self.assertEqual(got, [("MISSING_ENTRY", "ghost")])

    def test_markdown_citations(self):
        bib = self.write("refs.bib", CLEAN)
        md = self.write("notes.md", """\
            As @smith2020 showed [see @lee2018, p. 4; -@smith2020]. Mail me@example.org.
            See @fig:plot and @sec:intro.
            ```python
            @decorator_in_code
            ```
            Inline `@code_span` and @ghost.
            """)
        code, out, _ = self.run_main(bib, "--cited-in", md, "--json")
        got = [(f["code"], f["key"], f["line"]) for f in json.loads(out)["findings"]]
        self.assertEqual(got, [("MISSING_ENTRY", "ghost", 6)])


class Inputs(BibCheckCase):
    def test_directory_is_searched_recursively_in_sorted_order(self):
        self.write("lib/b.bib", "@misc{b, title={B}}\n")
        self.write("lib/sub/a.bib", "@misc{a, title={A}}\n")
        self.write("lib/notes.txt", "@misc{ignored, title={X}}\n")
        code, out, _ = self.run_main(os.path.join(self.tmp, "lib"), "--json")
        self.assertEqual((code, json.loads(out)["summary"]["entries"], json.loads(out)["summary"]["files"]), (0, 2, 2))

    def test_latin1_file_is_read_with_a_warning(self):
        path = self.write("old.bib", "@misc{a, title={Caf\xe9}}\n".encode("latin-1"), binary=True)
        code, out, _ = self.run_main(path, "--json")
        self.assertEqual([f["code"] for f in json.loads(out)["findings"]], ["ENCODING"])
        self.assertEqual(code, 0)

    def test_utf8_bom_is_accepted(self):
        path = self.write("bom.bib", "\ufeff@misc{a, title={T}}\n".encode("utf-8"), binary=True)
        code, out, _ = self.run_main(path, "--json")
        self.assertEqual((code, json.loads(out)["findings"]), (0, []))


if __name__ == "__main__":
    unittest.main()
