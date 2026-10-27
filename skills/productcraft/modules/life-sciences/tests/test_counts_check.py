"""Tests for modules/life-sciences/scripts/counts_check.py."""

import gzip
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "counts_check.py"
spec = importlib.util.spec_from_file_location("counts_check", SCRIPT)
counts_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counts_check)

N_GENES = 60          # genes far outnumber samples, as in a real matrix
SAMPLE_NAMES = ["S1", "S2", "S3", "S4", "S5", "S6"]


def make_counts(n_genes=N_GENES, samples=SAMPLE_NAMES):
    """A plain integer count matrix with genes in rows."""
    lines = ["gene\t" + "\t".join(samples)]
    for g in range(1, n_genes + 1):
        lines.append(f"G{g}\t" + "\t".join(str(10 * g + j) for j in range(len(samples))))
    return "\n".join(lines) + "\n"


COUNTS_GENES_IN_ROWS = make_counts()
SAMPLES_BALANCED = (
    "sample\tbatch\tcondition\n"
    "S1\tb1\tcontrol\nS2\tb2\tcontrol\nS3\tb1\tcontrol\n"
    "S4\tb2\ttreated\nS5\tb1\ttreated\nS6\tb2\ttreated\n"
)
SAMPLES_CONFOUNDED = (
    "sample\tbatch\tcondition\n"
    "S1\tb1\tcontrol\nS2\tb1\tcontrol\nS3\tb1\tcontrol\n"
    "S4\tb2\ttreated\nS5\tb2\ttreated\nS6\tb2\ttreated\n"
)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = counts_check.main(argv)
    return code, out.getvalue()


def codes_from(output):
    return [f["code"] for f in json.loads(output)["findings"]]


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


class MatrixTests(TempTree):
    def test_clean_matrix_alone_passes(self):
        path = self.write("counts.tsv", COUNTS_GENES_IN_ROWS)
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 0, msg=out)
        data = json.loads(out)
        self.assertEqual(data["n_genes"], N_GENES)
        self.assertEqual(data["n_samples"], len(SAMPLE_NAMES))
        self.assertEqual(data["orientation"], "genes-in-rows")

    def test_samples_in_rows_detected(self):
        genes = [f"G{i}" for i in range(1, 41)]
        lines = ["sample\t" + "\t".join(genes)]
        for s in ("S1", "S2", "S3"):
            lines.append(s + "\t" + "\t".join(str(i + 1) for i in range(len(genes))))
        path = self.write("wide.tsv", "\n".join(lines) + "\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(json.loads(out)["orientation"], "samples-in-rows")

    def test_orientation_can_be_forced(self):
        path = self.write("counts.tsv", COUNTS_GENES_IN_ROWS)
        code, out = run(["--counts", path, "--orientation", "samples-in-rows", "--json"])
        data = json.loads(out)
        self.assertEqual(data["n_samples"], N_GENES)          # rows are now read as samples
        self.assertEqual(data["n_genes"], len(SAMPLE_NAMES))

    def test_similar_dimensions_warn_about_the_guess(self):
        path = self.write("square.tsv", make_counts(n_genes=6))
        code, out = run(["--counts", path, "--json"])
        self.assertIn("AMBIGUOUS_ORIENTATION", codes_from(out))

    def test_explicit_orientation_silences_the_guess_warning(self):
        path = self.write("square.tsv", make_counts(n_genes=6))
        code, out = run(["--counts", path, "--orientation", "genes-in-rows", "--json"])
        self.assertNotIn("AMBIGUOUS_ORIENTATION", codes_from(out))

    def test_csv_input_is_read(self):
        path = self.write("counts.csv", COUNTS_GENES_IN_ROWS.replace("\t", ","))
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["n_samples"], 6)

    def test_gzip_input_is_read(self):
        path = self.write("counts.tsv.gz", COUNTS_GENES_IN_ROWS, compress=True)
        self.assertEqual(run(["--counts", path, "--json"])[0], 0)

    def test_non_integer_values_are_an_error(self):
        path = self.write("tpm.tsv", "gene\tS1\tS2\nG1\t1.5\t2.5\nG2\t3.25\t4.5\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("NON_INTEGER", codes_from(out))

    def test_negative_values_are_an_error(self):
        path = self.write("neg.tsv", "gene\tS1\tS2\nG1\t-3\t2\nG2\t4\t5\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE", codes_from(out))

    def test_missing_values_are_an_error(self):
        path = self.write("na.tsv", "gene\tS1\tS2\nG1\tNA\t2\nG2\t4\t5\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("MISSING", codes_from(out))

    def test_all_zero_sample_is_an_error(self):
        path = self.write("zero.tsv", "gene\tS1\tS2\nG1\t0\t2\nG2\t0\t5\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("EMPTY_SAMPLE", codes_from(out))

    def test_all_zero_gene_warns(self):
        path = self.write("zerogene.tsv", "gene\tS1\tS2\nG1\t0\t0\nG2\t4\t5\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 0)
        self.assertIn("ZERO_GENES", codes_from(out))
        self.assertEqual(run(["--counts", path, "--strict", "--json"])[0], 1)

    def test_duplicate_gene_ids_are_an_error(self):
        path = self.write("dup.tsv", "gene\tS1\tS2\nG1\t1\t2\nG1\t3\t4\nG2\t5\t6\n")
        code, out = run(["--counts", path, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("DUP_GENES", codes_from(out))

    def test_large_depth_spread_warns(self):
        path = self.write("spread.tsv", "gene\tS1\tS2\nG1\t1\t5000\nG2\t1\t6000\n")
        code, out = run(["--counts", path, "--json"])
        self.assertIn("DEPTH_SPREAD", codes_from(out))


class DesignTests(TempTree):
    def setUp(self):
        super().setUp()
        self.counts = self.write("counts.tsv", COUNTS_GENES_IN_ROWS)

    def test_balanced_design_is_full_rank(self):
        samples = self.write("samples.tsv", SAMPLES_BALANCED)
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "batch,condition", "--json"])
        self.assertEqual(code, 0, msg=out)
        self.assertIn("DESIGN", codes_from(out))

    def test_confounded_factors_are_an_error(self):
        samples = self.write("samples.tsv", SAMPLES_CONFOUNDED)
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "batch,condition", "--json"])
        self.assertEqual(code, 1)
        found = codes_from(out)
        self.assertIn("CONFOUNDED", found)
        self.assertIn("RANK_DEFICIENT", found)

    def test_single_sample_group_is_an_error(self):
        samples = self.write("samples.tsv",
                             "sample\tcondition\nS1\ta\nS2\ta\nS3\ta\nS4\ta\nS5\ta\nS6\tb\n")
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "condition", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("NO_REPLICATES", codes_from(out))

    def test_two_sample_group_warns(self):
        samples = self.write("samples.tsv",
                             "sample\tcondition\nS1\ta\nS2\ta\nS3\ta\nS4\ta\nS5\tb\nS6\tb\n")
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "condition", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("FEW_REPLICATES", codes_from(out))

    def test_constant_factor_is_an_error(self):
        samples = self.write("samples.tsv",
                             "sample\tcondition\nS1\ta\nS2\ta\nS3\ta\nS4\ta\nS5\ta\nS6\ta\n")
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "condition", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("CONSTANT_FACTOR", codes_from(out))

    def test_empty_factor_value_is_an_error(self):
        samples = self.write("samples.tsv",
                             "sample\tcondition\nS1\ta\nS2\ta\nS3\ta\nS4\tb\nS5\tb\nS6\t\n")
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "condition", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("MISSING_LEVEL", codes_from(out))

    def test_unknown_factor_column_is_an_error(self):
        samples = self.write("samples.tsv", SAMPLES_BALANCED)
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--design", "treatment", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("NO_FACTOR", codes_from(out))

    def test_sample_mismatch_between_inputs(self):
        samples = self.write("samples.tsv",
                             "sample\tcondition\nS1\ta\nS2\ta\nS3\ta\nS4\tb\nS5\tb\nS9\tb\n")
        code, out = run(["--counts", self.counts, "--samples", samples, "--json"])
        self.assertEqual(code, 1)
        found = codes_from(out)
        self.assertIn("UNMATCHED_COUNTS", found)
        self.assertIn("UNMATCHED_META", found)

    def test_named_sample_column(self):
        samples = self.write("samples.tsv",
                             "run\tsample_id\tcondition\n"
                             "r1\tS1\ta\nr2\tS2\ta\nr3\tS3\ta\nr4\tS4\tb\nr5\tS5\tb\nr6\tS6\tb\n")
        code, out = run(["--counts", self.counts, "--samples", samples,
                         "--sample-col", "sample_id", "--design", "condition", "--json"])
        self.assertEqual(code, 0, msg=out)

    def test_design_without_samples_is_usage_error(self):
        self.assertEqual(run(["--counts", self.counts, "--design", "condition"])[0], 2)

    def test_missing_file_is_usage_error(self):
        self.assertEqual(run(["--counts", str(self.root / "nope.tsv")])[0], 2)

    def test_output_is_deterministic(self):
        samples = self.write("samples.tsv", SAMPLES_BALANCED)
        argv = ["--counts", self.counts, "--samples", samples, "--design", "batch,condition", "--json"]
        self.assertEqual(run(argv)[1], run(argv)[1])


class DesignRankTests(unittest.TestCase):
    def test_rank_of_independent_columns(self):
        rows = [[1.0, 0.0], [1.0, 1.0]]
        self.assertEqual(counts_check.design_rank(rows), 2)

    def test_rank_of_duplicated_column(self):
        rows = [[1.0, 1.0, 1.0], [1.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
        self.assertEqual(counts_check.design_rank(rows), 2)

    def test_rank_of_empty_matrix(self):
        self.assertEqual(counts_check.design_rank([]), 0)


if __name__ == "__main__":
    unittest.main()
