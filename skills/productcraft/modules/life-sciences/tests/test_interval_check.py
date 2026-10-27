"""Tests for modules/life-sciences/scripts/interval_check.py."""

import gzip
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "interval_check.py"
spec = importlib.util.spec_from_file_location("interval_check", SCRIPT)
interval_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interval_check)


def run(argv):
    """Run main() and return (exit code, stdout)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = interval_check.main(argv)
    return code, out.getvalue()


class TempTree(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._dir.name)
        self.addCleanup(self._dir.cleanup)

    def write(self, name, text, compress=False):
        path = self.root / name
        if compress:
            with gzip.open(path, "wt") as handle:
                handle.write(text)
        else:
            path.write_text(text)
        return str(path)


class ConvertTests(unittest.TestCase):
    def test_one_based_region_to_bed(self):
        code, out = run(["convert", "chr1:1000-2000", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["zero_based_half_open"], {"start": 999, "end": 2000})
        self.assertEqual(data["one_based_closed"], {"start": 1000, "end": 2000})
        self.assertEqual(data["length"], 1001)

    def test_zero_based_region_to_one_based(self):
        code, out = run(["convert", "chr1:999-2000", "--from", "zero-based", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["region_string"], "chr1:1000-2000")

    def test_single_base_round_trip(self):
        code, out = run(["convert", "chrX:5-5", "--json"])
        data = json.loads(out)
        self.assertEqual(data["length"], 1)
        self.assertEqual(data["bed_line"], "chrX\t4\t5")

    def test_commas_accepted(self):
        code, out = run(["convert", "chr7:1,000,000-1,000,100", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["length"], 101)

    def test_text_output_names_both_conventions(self):
        code, out = run(["convert", "chr1:10-20"])
        self.assertEqual(code, 0)
        self.assertIn("1-based, closed", out)
        self.assertIn("0-based, half-open", out)

    def test_malformed_region_is_usage_error(self):
        self.assertEqual(run(["convert", "chr1-100-200"])[0], 2)

    def test_inverted_region_is_usage_error(self):
        self.assertEqual(run(["convert", "chr1:200-100"])[0], 2)

    def test_zero_start_rejected_for_one_based(self):
        self.assertEqual(run(["convert", "chr1:0-100"])[0], 2)


class CheckTests(TempTree):
    GOOD = "chr1\t100\t200\tp1\t0\t+\nchr1\t300\t400\tp2\t0\t-\nchr2\t10\t20\tp3\t0\t+\n"

    def test_clean_file_passes(self):
        path = self.write("good.bed", self.GOOD)
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["errors"], 0)
        self.assertEqual(data["files"][0]["counts"]["records"], 3)
        self.assertEqual(data["files"][0]["naming_style"], "chr-prefixed")

    def test_header_and_comment_lines_skipped(self):
        path = self.write("track.bed", 'track name="x"\n# a comment\n' + self.GOOD)
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["files"][0]["counts"]["records"], 3)

    def test_inverted_interval_is_an_error(self):
        path = self.write("bad.bed", "chr1\t200\t100\n")
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 1)
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("INVERTED", codes)

    def test_zero_length_warns_but_does_not_fail(self):
        path = self.write("zero.bed", "chr1\t50\t50\n")
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 0)
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("ZERO_LENGTH", codes)

    def test_strict_turns_warnings_into_failure(self):
        path = self.write("zero.bed", "chr1\t50\t50\n")
        self.assertEqual(run(["check", path, "--strict", "--json"])[0], 1)

    def test_mixed_naming_is_an_error(self):
        path = self.write("mixed.bed", "chr1\t10\t20\n2\t10\t20\n")
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 1)
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("MIXED_NAMING", codes)

    def test_unsorted_and_interleaved_are_warnings(self):
        path = self.write("unsorted.bed", "chr1\t300\t400\nchr1\t100\t200\nchr2\t1\t2\nchr1\t500\t600\n")
        code, out = run(["check", path, "--json"])
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("UNSORTED", codes)
        self.assertIn("INTERLEAVED", codes)

    def test_duplicate_interval_warns(self):
        path = self.write("dup.bed", "chr1\t10\t20\nchr1\t10\t20\n")
        code, out = run(["check", path, "--json"])
        counts = json.loads(out)["files"][0]["counts"]
        self.assertEqual(counts["duplicates"], 1)

    def test_empty_file_is_an_error(self):
        path = self.write("empty.bed", "# nothing here\n")
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 1)
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("EMPTY", codes)

    def test_gzip_input_is_read(self):
        path = self.write("good.bed.gz", self.GOOD, compress=True)
        code, out = run(["check", path, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["files"][0]["counts"]["records"], 3)

    def test_gff_is_converted_to_half_open(self):
        gff = "chr1\tsrc\tgene\t1\t100\t.\t+\t.\tID=g1\n"
        path = self.write("genes.gtf", gff)
        sizes = self.write("sizes.txt", "chr1\t100\n")
        code, out = run(["check", path, "--genome", sizes, "--json"])
        self.assertEqual(code, 0, msg=out)   # 1-based 1..100 is 0..100 half-open, inside a 100 bp contig
        self.assertEqual(json.loads(out)["files"][0]["format"], "gff")

    def test_coordinate_past_contig_end_is_an_error(self):
        path = self.write("over.bed", "chr1\t10\t5000\n")
        sizes = self.write("sizes.txt", "chr1\t1000\n")
        code, out = run(["check", path, "--genome", sizes, "--json"])
        self.assertEqual(code, 1)
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("PAST_END", codes)

    def test_unknown_contig_is_an_error(self):
        path = self.write("other.bed", "chrZ\t10\t20\n")
        sizes = self.write("sizes.txt", "chr1\t1000\n")
        code, out = run(["check", path, "--genome", sizes, "--json"])
        self.assertEqual(code, 1)
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("UNKNOWN_CONTIG", codes)

    def test_naming_mismatch_against_sizes_file(self):
        path = self.write("plain.bed", "1\t10\t20\n")
        sizes = self.write("sizes.txt", "chr1\t1000\n")
        code, out = run(["check", path, "--genome", sizes, "--json"])
        codes = [f["code"] for f in json.loads(out)["files"][0]["findings"]]
        self.assertIn("NAMING_MISMATCH", codes)

    def test_fai_style_sizes_file_is_accepted(self):
        path = self.write("good.bed", self.GOOD)
        fai = self.write("ref.fa.fai", "chr1\t1000\t10\t60\t61\nchr2\t500\t20\t60\t61\n")
        self.assertEqual(run(["check", path, "--genome", fai, "--json"])[0], 0)

    def test_several_files_in_one_run(self):
        a = self.write("a.bed", self.GOOD)
        b = self.write("b.bed", "chr1\t200\t100\n")
        code, out = run(["check", a, b, "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(len(json.loads(out)["files"]), 2)

    def test_missing_file_is_usage_error(self):
        self.assertEqual(run(["check", str(self.root / "nope.bed")])[0], 2)

    def test_missing_sizes_file_is_usage_error(self):
        path = self.write("good.bed", self.GOOD)
        self.assertEqual(run(["check", path, "--genome", str(self.root / "nope.sizes")])[0], 2)

    def test_output_is_deterministic(self):
        path = self.write("good.bed", self.GOOD)
        first = run(["check", path, "--json"])[1]
        second = run(["check", path, "--json"])[1]
        self.assertEqual(first, second)


class NamingStyleTests(unittest.TestCase):
    def test_styles(self):
        self.assertEqual(interval_check.naming_style(["chr1", "chr2"]), "chr-prefixed")
        self.assertEqual(interval_check.naming_style(["1", "2"]), "plain")
        self.assertEqual(interval_check.naming_style(["chr1", "2"]), "mixed")
        self.assertEqual(interval_check.naming_style([]), "unknown")


if __name__ == "__main__":
    unittest.main()
