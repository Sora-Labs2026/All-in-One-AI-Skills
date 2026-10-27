"""Offline tests for csv_profile.py using synthetic files written to a temporary folder."""
import codecs
import gzip
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "csv_profile.py"
spec = importlib.util.spec_from_file_location("csv_profile", SCRIPT)
cp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cp
spec.loader.exec_module(cp)


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = cp.main([str(a) for a in args])
        except SystemExit as exc:  # argparse --help, --version and usage errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TempFiles(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text, encoding="utf-8"):
        path = self.dir / name
        path.write_bytes(text.encode(encoding) if isinstance(text, str) else text)
        return path

    def profile(self, path, *extra):
        code, out, err = run_cli(path, "--json", *extra)
        self.assertIn(code, (0, 1), err)
        return json.loads(out)

    def column(self, report, name):
        return next(c for c in report["columns"] if c["name"] == name)

    def codes(self, report, column=None):
        return {f["code"] for f in report["findings"] if column is None or f["column"] == column}


class SniffingTests(TempFiles):
    def test_delimiters(self):
        for delim, name in ((",", "comma"), (";", "semicolon"), ("\t", "tab"), ("|", "pipe")):
            body = delim.join(["id", "city", "score"]) + "\n"
            body += "".join(delim.join([str(i), f"c{i}", str(i * 3)]) + "\n" for i in range(20))
            rep = self.profile(self.write(f"d_{name}.txt", body))
            self.assertEqual(rep["file"]["delimiter_name"], name)
            self.assertEqual(len(rep["columns"]), 3)
            self.assertEqual(rep["rows"]["data_rows"], 20)

    def test_quoted_delimiters_and_newlines_do_not_split(self):
        body = 'id,comment\n1,"a, b, c"\n2,"line one\nline two"\n3,plain\n'
        rep = self.profile(self.write("q.csv", body))
        self.assertEqual(rep["file"]["delimiter"], ",")
        self.assertEqual(rep["rows"]["data_rows"], 3)
        self.assertIn("EMBEDDED_NEWLINES", self.codes(rep, "comment"))

    def test_encodings(self):
        text = "name,city\nJos\u00e9,Z\u00fcrich\nAnna,K\u00f6ln\n"
        cases = [
            ("utf8.csv", text.encode("utf-8"), "utf-8"),
            ("bom.csv", codecs.BOM_UTF8 + text.encode("utf-8"), "utf-8-sig"),
            ("u16.csv", text.encode("utf-16"), "utf-16"),
            ("win.csv", text.encode("cp1252"), "cp1252"),
        ]
        for name, raw, expected in cases:
            rep = self.profile(self.write(name, raw))
            self.assertEqual(rep["file"]["encoding"], expected, name)
            self.assertEqual(rep["file"]["decode_errors"], 0, name)
            self.assertEqual([c["name"] for c in rep["columns"]], ["name", "city"], name)
        self.assertIn("ENCODING_GUESS", self.codes(self.profile(self.dir / "win.csv")))

    def test_wrong_encoding_is_counted(self):
        path = self.write("latin.csv", "name\nJos\u00e9\n", encoding="cp1252")
        rep = self.profile(path, "--encoding", "utf-8")
        self.assertEqual(rep["file"]["decode_errors"], 1)
        self.assertIn("DECODE_ERRORS", self.codes(rep))
        self.assertIn("ENCODING_DAMAGE", self.codes(rep, "name"))

    def test_gzip_and_overrides(self):
        path = self.dir / "t.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write("a:b\n1:2\n3:4\n")
        rep = self.profile(path, "--delimiter", ":")
        self.assertEqual(rep["rows"]["data_rows"], 2)
        self.assertEqual(rep["file"]["delimiter_basis"], "given with --delimiter")

    def test_no_header(self):
        rep = self.profile(self.write("n.csv", "1,2\n3,4\n5,6\n"), "--no-header")
        self.assertEqual([c["name"] for c in rep["columns"]], ["column_1", "column_2"])
        self.assertEqual(rep["rows"]["data_rows"], 3)


class TypeTests(TempFiles):
    def test_inferred_types(self):
        body = "i,f,b,d,ts,s,dc\n"
        rows = [("1", "1.5", "true", "2024-01-31", "2024-01-31T10:00:00Z", "red", "ab"),
                ("-2", "2", "False", "2024-02-29", "2024-02-01T00:00:00Z", "blue", "cd"),
                ("30", "3e2", "yes", "2023-12-01", "2024-03-01T23:59:59Z", "green", "ef")]
        body += "".join(",".join(r) + "\n" for r in rows)
        rep = self.profile(self.write("t.csv", body))
        types = {c["name"]: c["type"] for c in rep["columns"]}
        self.assertEqual(types, {"i": "integer", "f": "float", "b": "boolean", "d": "date",
                                 "ts": "datetime", "s": "string", "dc": "string"})
        num = self.column(rep, "i")["numeric"]
        self.assertEqual((num["min"], num["max"], num["negatives"]), (-2.0, 30.0, 1))
        self.assertEqual(self.column(rep, "d")["dates"]["min"], "2023-12-01")

    def test_invalid_calendar_date_is_text(self):
        rep = self.profile(self.write("bad.csv", "d\n2024-02-30\n2024-13-01\n"))
        self.assertEqual(self.column(rep, "d")["type"], "string")

    def test_mixed_types_and_null_tokens(self):
        body = "amount\n" + "".join(f"{i}.5\n" for i in range(30)) + "abc\nN/A\nnull\n\n"
        rep = self.profile(self.write("m.csv", body))
        col = self.column(rep, "amount")
        self.assertEqual(col["type"], "float")
        self.assertEqual(col["nonconforming"], 1)
        self.assertEqual(col["nulls"], 2)
        self.assertEqual(col["null_tokens"], ["n/a", "null"])
        self.assertEqual(rep["rows"]["blank_lines"], 1)
        self.assertIn("MIXED_TYPES", self.codes(rep, "amount"))
        self.assertIn("NULL_TOKENS", self.codes(rep, "amount"))

    def test_custom_null_token(self):
        rep = self.profile(self.write("c.csv", "v\n1\n2\nunknown\n"), "--null-token", "UNKNOWN")
        col = self.column(rep, "v")
        self.assertEqual((col["type"], col["nulls"]), ("integer", 1))

    def test_decimal_comma_with_semicolon(self):
        rep = self.profile(self.write("eu.csv", "id;price\n1;1,5\n2;2,25\n3;3\n"))
        self.assertEqual(self.column(rep, "price")["type"], "float (decimal comma)")
        self.assertIn("DECIMAL_COMMA", self.codes(rep, "price"))

    def test_quantiles_are_exact_for_small_columns(self):
        rep = self.profile(self.write("q.csv", "x\n" + "".join(f"{i}\n" for i in range(1, 102))))
        num = self.column(rep, "x")["numeric"]
        self.assertEqual((num["p50"], num["p25"], num["p75"]), (51.0, 26.0, 76.0))
        self.assertFalse(num["quantiles_approximate"])
        self.assertEqual(num["outliers_1_5_iqr"], 0)


class SuspiciousValueTests(TempFiles):
    def test_formatting_zeros_and_sentinels(self):
        body = 'zip,amount,score\n00123,"1,234.50",5\n00456,$12,-999\n10001,7,-999\n20002,8,3\n'
        rep = self.profile(self.write("s.csv", body))
        self.assertIn("LEADING_ZEROS", self.codes(rep, "zip"))
        self.assertIn("FORMATTED_NUMBERS", self.codes(rep, "amount"))
        self.assertIn("SENTINEL_VALUES", self.codes(rep, "score"))

    def test_sentinel_dates_and_ambiguous_order(self):
        body = "d1,d2,d3\n1900-01-01,03/04/2024,13/04/2024\n2024-05-01,05/06/2024,04/13/2024\n"
        rep = self.profile(self.write("dates.csv", body))
        self.assertIn("SENTINEL_DATES", self.codes(rep, "d1"))
        self.assertIn("AMBIGUOUS_DATES", self.codes(rep, "d2"))
        self.assertIn("MIXED_DATE_ORDER", self.codes(rep, "d3"))

    def test_day_first_is_reported(self):
        rep = self.profile(self.write("dmy.csv", "d\n13/04/2024\n03/04/2024\n"))
        self.assertIn("DAY_FIRST_DATES", self.codes(rep, "d"))

    def test_formula_prefix_whitespace_and_case(self):
        body = "note,status\n=HYPERLINK(1),Open\n+cmd,open\nplain ,Closed\n@x,closed\n-x,open\nok,Open\n"
        body += "".join(f"row{i},Open\n" for i in range(6))
        rep = self.profile(self.write("f.csv", body))
        found = {f["code"]: f["message"] for f in rep["findings"] if f["column"] == "note"}
        self.assertIn("FORMULA_PREFIX", found)
        self.assertIn(": 4;", found["FORMULA_PREFIX"])
        self.assertIn("WHITESPACE", found)
        self.assertIn("CASE_VARIANTS", self.codes(rep, "status"))

    def test_negative_numbers_are_not_formulas(self):
        rep = self.profile(self.write("neg.csv", "x\n-1\n-2.5\n+3\n"))
        self.assertNotIn("FORMULA_PREFIX", self.codes(rep))

    def test_mixed_timezones_and_big_integers(self):
        body = "ts,id\n2024-01-01T10:00:00Z,9007199254740993\n2024-01-01 11:00:00,1\n"
        rep = self.profile(self.write("tz.csv", body))
        self.assertIn("MIXED_TIMEZONES", self.codes(rep, "ts"))
        self.assertIn("BIG_INTEGERS", self.codes(rep, "id"))

    def test_control_characters(self):
        rep = self.profile(self.write("ctl.csv", "v\nab\x07c\nok\n"))
        self.assertIn("CONTROL_CHARS", self.codes(rep, "v"))

    def test_constant_and_all_null_columns(self):
        rep = self.profile(self.write("k.csv", "a,b,c\n1,x,\n2,x,NA\n3,x,\n"))
        self.assertIn("CONSTANT", self.codes(rep, "b"))
        self.assertIn("ALL_NULL", self.codes(rep, "c"))


class RowAndKeyTests(TempFiles):
    def test_ragged_rows_report_line_numbers(self):
        rep = self.profile(self.write("r.csv", "a,b,c\n1,2,3\n4,5\n6,7,8,9\n"))
        rows = rep["rows"]
        self.assertEqual((rows["short_rows"], rows["long_rows"]), (1, 1))
        self.assertEqual(rows["ragged_lines"], [3, 4])
        self.assertEqual(self.column(rep, "c")["nulls"], 1)
        self.assertIn("RAGGED_ROWS", self.codes(rep))

    def test_duplicate_rows_and_headers(self):
        rep = self.profile(self.write("dup.csv", "a,a,\n1,2,3\n1,2,3\n4,5,6\n"))
        self.assertEqual(rep["rows"]["duplicate_rows"], 1)
        self.assertIn("DUPLICATE_ROWS", self.codes(rep))
        self.assertIn("DUPLICATE_HEADER", self.codes(rep))
        self.assertIn("BLANK_HEADER", self.codes(rep))

    def test_single_and_composite_keys(self):
        rep = self.profile(self.write("k1.csv", "id,v\n1,a\n2,a\n3,b\n"))
        self.assertEqual(rep["keys"]["single"], ["id"])
        rep = self.profile(self.write("k2.csv", "a,b,c\n1,x,p\n1,y,p\n2,x,p\n2,y,q\n"))
        self.assertEqual(rep["keys"]["single"], [])
        self.assertEqual(rep["keys"]["composite"], [["a", "b"]])
        rep = self.profile(self.write("k3.csv", "a,b\n1,x\n1,x\n"))
        self.assertIn("NO_KEY", self.codes(rep))

    def test_key_beyond_distinct_cap_is_rechecked(self):
        body = "id,grp\n" + "".join(f"{i},{i % 3}\n" for i in range(50))
        rep = self.profile(self.write("cap.csv", body), "--distinct-cap", "10")
        self.assertTrue(self.column(rep, "id")["distinct_capped"])
        self.assertEqual(rep["keys"]["single"], ["id"])
        self.assertEqual(rep["keys"]["composite"], [])
        body = "id\n" + "".join(f"{i}\n" for i in range(30)) + "29\n"
        rep = self.profile(self.write("cap2.csv", body), "--distinct-cap", "10")
        self.assertEqual(rep["keys"]["single"], [])

    def test_max_rows(self):
        body = "x\n" + "".join(f"{i}\n" for i in range(100))
        rep = self.profile(self.write("m.csv", body), "--max-rows", "10")
        self.assertEqual(rep["rows"]["data_rows"], 10)
        self.assertTrue(rep["rows"]["truncated_at_max_rows"])
        self.assertIn("--max-rows", rep["keys"]["note"])


class PrivacyAndCliTests(TempFiles):
    def setUp(self):
        super().setUp()
        self.marker = "zq" + "x" * 6 + "-private"
        body = "id,secret,amount\n" + "".join(f"{i},{self.marker}{i % 2},{i}\n" for i in range(5))
        self.path = self.write("p.csv", body)

    def test_no_values_by_default(self):
        for args in ((), ("--json",)):
            code, out, _ = run_cli(self.path, *args)
            self.assertEqual(code, 0)
            self.assertNotIn(self.marker, out)
            self.assertIn("secret", out)  # column names are shown

    def test_show_values_opts_in(self):
        code, out, _ = run_cli(self.path, "--show-values", "--top", "1")
        self.assertEqual(code, 0)
        self.assertIn(self.marker, out)
        rep = json.loads(run_cli(self.path, "--json", "--show-values")[1])
        self.assertEqual(len(self.column(rep, "secret")["values"]["top"]), 2)

    def test_deterministic_output(self):
        body = "v\n" + "".join(f"{(i * 7919) % 1000}.25\n" for i in range(3000))
        path = self.write("det.csv", body)
        a = run_cli(path, "--json", "--sample-size", "100")[1]
        b = run_cli(path, "--json", "--sample-size", "100")[1]
        self.assertEqual(a, b)
        self.assertTrue(json.loads(a)["columns"][0]["numeric"]["quantiles_approximate"])

    def test_exit_codes(self):
        clean = self.write("clean.csv", "id,v\n1,2\n3,4\n")
        self.assertEqual(run_cli(clean, "--strict")[0], 0)
        dirty = self.write("dirty.csv", "id,v\n1,2\n1,2\n")
        self.assertEqual(run_cli(dirty)[0], 0)
        self.assertEqual(run_cli(dirty, "--strict")[0], 1)
        code, _, err = run_cli(self.dir / "missing.csv")
        self.assertEqual(code, 2)
        self.assertIn("not a file", err)
        self.assertEqual(run_cli(self.write("empty.csv", ""))[0], 2)
        self.assertEqual(run_cli(clean, "--delimiter", ";;")[0], 2)
        self.assertEqual(run_cli(clean, "--encoding", "no-such-codec")[0], 2)
        self.assertEqual(run_cli(clean, "--max-rows", "0")[0], 2)

    def test_help_and_text_report(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("--show-values", out)
        code, out, _ = run_cli(self.path)
        self.assertIn("possible keys: id", out)
        self.assertIn("Findings:", out)


if __name__ == "__main__":
    unittest.main()
