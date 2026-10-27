"""Tests for bio_id_check.py. Standard library only; no network."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
SCRIPT = os.path.join(SCRIPTS, "bio_id_check.py")
sys.path.insert(0, SCRIPTS)

import bio_id_check as bic  # noqa: E402


def run(argv, stdin_text=None):
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = bic.main(argv)
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


def first(value, expected=None):
    r = bic.classify(value, expected)
    return r["status"], (r["matches"][0]["type"] if r["matches"] else None), r


class TestGenesAndSequences(unittest.TestCase):
    def test_uniprot(self):
        self.assertEqual(first("P04637")[:2], ("ok", "uniprot"))
        self.assertEqual(first("A0A023GPI8")[:2], ("ok", "uniprot"))
        status, type_, r = first("P04637-2")
        self.assertEqual((status, type_), ("ok", "uniprot"))
        self.assertEqual(r["matches"][0]["details"]["isoform"], 2)
        self.assertEqual(first("P0463")[0], "unrecognized")

    def test_uniprot_entry_name_warns(self):
        status, type_, r = first("P53_HUMAN")
        self.assertEqual((status, type_), ("warn", "uniprot-name"))
        self.assertIn("accession", " ".join(r["messages"]))

    def test_ensembl(self):
        status, type_, r = first("ENSG00000139618")
        self.assertEqual((status, type_), ("ok", "ensembl"))
        self.assertEqual(r["matches"][0]["details"]["feature"], "gene")
        r = bic.classify("ENST00000380152.8")
        self.assertEqual(r["matches"][0]["details"]["feature"], "transcript")
        self.assertEqual(r["matches"][0]["details"]["version"], 8)
        r = bic.classify("ENSMUSG00000017167")
        self.assertEqual(r["matches"][0]["details"]["species_code"], "MUS")

    def test_ensembl_wrong_digit_count_hint(self):
        status, _type, r = first("ENSG0000013961")
        self.assertEqual(status, "unrecognized")
        self.assertIn("11 digits", r["messages"][0])

    def test_refseq(self):
        status, _type, r = first("NM_000546.6")
        self.assertEqual(status, "ok")
        self.assertIn("mRNA, curated", r["matches"][0]["label"])
        status, _type, r = first("NM_000546")
        self.assertEqual(status, "warn")
        self.assertIn("unversioned", r["messages"][0])
        self.assertIn("predicted", bic.classify("XP_011524437.1")["matches"][0]["label"])
        self.assertIn("chromosome", bic.classify("NC_000017.11")["matches"][0]["label"])

    def test_bare_integer_is_ambiguous_unless_typed(self):
        status, _type, r = first("7157")
        self.assertEqual(status, "unrecognized")
        self.assertIn("ambiguous", r["messages"][0])
        status, type_, r = first("7157", "ncbigene")
        self.assertEqual((status, type_), ("ok", "ncbigene"))
        self.assertEqual(r["matches"][0]["normalized"], "NCBIGene:7157")
        self.assertEqual(first("9606", "taxon")[:2], ("ok", "taxon"))
        self.assertEqual(first("NCBIGene:7157")[:2], ("ok", "ncbigene"))

    def test_gene_symbols(self):
        self.assertEqual(first("TP53", "symbol")[0], "ok")
        self.assertEqual(first("Trp53", "symbol")[0], "ok")
        status, _type, r = first("SEPT2", "symbol")
        self.assertEqual(status, "warn")
        self.assertIn("SEPTIN2", r["messages"][0])
        self.assertIn("MARCHF1", first("MARCH1", "symbol")[2]["messages"][0])
        self.assertEqual(first("1-Mar", "symbol")[0], "invalid")
        self.assertEqual(first("Sep-2", "symbol")[0], "invalid")
        self.assertEqual(first("BRCA 1", "symbol")[0], "invalid")

    def test_date_mangled_symbol_hint_in_auto_mode(self):
        status, _type, r = first("1-Mar")
        self.assertEqual(status, "unrecognized")
        self.assertIn("spreadsheet date", r["messages"][0])


class TestVariants(unittest.TestCase):
    def test_rsid_and_case_hint(self):
        self.assertEqual(first("rs699")[:2], ("ok", "rsid"))
        status, _type, r = first("RS699")
        self.assertEqual(status, "unrecognized")
        self.assertIn("rs699", r["messages"][0])

    def test_whitespace_hint(self):
        status, _type, r = first("rs 699")
        self.assertEqual(status, "unrecognized")
        self.assertIn("rs699", " ".join(r["messages"]))

    def test_clinvar_spdi_vcf_gtex(self):
        self.assertEqual(first("VCV000012345.3")[:2], ("ok", "clinvar"))
        self.assertEqual(first("RCV000012345")[:2], ("ok", "clinvar"))
        self.assertEqual(first("NC_000017.11:7676153:G:C")[:2], ("ok", "spdi"))
        self.assertEqual(first("1-55051215-G-GA")[:2], ("ok", "vcf-variant"))
        self.assertEqual(first("chr1-55051215-G-GA")[0], "warn")
        self.assertEqual(first("1-100-A-A")[0], "invalid")
        status, type_, r = first("chr1_12345_A_G_b38")
        self.assertEqual((status, type_), ("ok", "gtex-variant"))
        self.assertEqual(r["matches"][0]["details"]["build"], "GRCh38")

    def test_hgvs_valid_shapes(self):
        for expr in ("NM_000546.6:c.215C>G", "NC_000017.11:g.7676154G>C", "NM_004006.2:c.4375_4379del",
                     "NM_000546.6:c.-14G>C", "NM_000546.6:c.88+1G>T", "NM_000546.6:c.76_77insG",
                     "NM_000546.6:c.215_216delinsAT", "NM_000546.6:c.[76A>C;83G>C]", "NM_000546.6:r.76a>c",
                     "NC_012920.1:m.3243A>G", "NP_000537.3:p.Arg72Pro", "NP_000537.3:p.Arg97ProfsTer23",
                     "NP_000537.3:p.Trp26Ter", "NP_000537.3:p.Trp26*", "NP_000537.3:p.(Arg72Pro)",
                     "NP_000537.3:p.?", "NP_000537.3:p.Met1ext-5", "NP_000537.3:p.Lys23_Val25del",
                     "ENST00000269305.9:c.215C>G", "LRG_321t1:c.215C>G",
                     "NM_000546.6(TP53):c.215C>G (p.Pro72Arg)"):
            with self.subTest(expr=expr):
                status, type_, r = first(expr)
                self.assertEqual((status, type_), ("ok", "hgvs"), r["messages"])

    def test_hgvs_clinvar_style_details(self):
        r = bic.classify("NM_000546.6(TP53):c.215C>G (p.Pro72Arg)")
        d = r["matches"][0]["details"]
        self.assertEqual(d["gene"], "TP53")
        self.assertEqual(d["protein_change"], "p.Pro72Arg")

    def test_hgvs_errors(self):
        cases = {
            "NM_000546.6:p.Arg72Pro": "does not fit",
            "NP_000537.3:c.215C>G": "does not fit",
            "NC_012920.1:g.3243A>G": "does not fit",
            "chr17:g.7676154G>C": "reference sequence accession",
            "NM_000546.6:c.215c>g": "upper-case",
            "NM_000546.6:c.76insG": "two flanking positions",
            "NC_000017.11:g.123+5A>G": "plain sequence numbers",
            "NM_000546.6:c.215C>>G": "does not match",
        }
        for expr, fragment in cases.items():
            with self.subTest(expr=expr):
                status, _type, r = first(expr)
                self.assertEqual(status, "invalid")
                self.assertIn(fragment, " ".join(r["messages"]))

    def test_hgvs_warnings(self):
        status, _type, r = first("NM_000546:c.215C>G")
        self.assertEqual(status, "warn")
        self.assertIn("unversioned", " ".join(r["messages"]))
        status, _type, r = first("NP_000537.3:p.R72P")
        self.assertEqual(status, "warn")
        self.assertIn("three-letter", " ".join(r["messages"]))


class TestChemistryStructuresPathways(unittest.TestCase):
    def test_chembl_and_case_hint(self):
        self.assertEqual(first("CHEMBL25")[:2], ("ok", "chembl"))
        status, _type, r = first("chembl25")
        self.assertEqual(status, "unrecognized")
        self.assertIn("CHEMBL25", r["messages"][0])

    def test_inchikey(self):
        status, type_, r = first("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
        self.assertEqual((status, type_), ("ok", "inchikey"))
        self.assertTrue(r["matches"][0]["details"]["standard"])
        self.assertEqual(first("BSYNRYMUTXBXSQ-UHFFFAOYNA-N")[0], "warn")
        self.assertEqual(first("BSYNRYMUTXBXSQ-UHFFFAOYSA")[0], "unrecognized")

    def test_other_chemistry(self):
        self.assertEqual(first("InChI=1S/C9H8O4/c1-6")[:2], ("ok", "inchi"))
        self.assertEqual(first("CID2244")[:2], ("ok", "pubchem"))
        self.assertEqual(first("2244", "pubchem")[0], "warn")
        self.assertEqual(first("DB00945")[:2], ("ok", "drugbank"))
        self.assertEqual(first("HMDB0000122")[:2], ("ok", "hmdb"))
        status, _type, r = first("HMDB00122")
        self.assertEqual(status, "warn")
        self.assertEqual(r["matches"][0]["normalized"], "HMDB0000122")
        self.assertEqual(first("ZINC000000000053")[:2], ("ok", "zinc"))
        self.assertEqual(first("ZINC53")[0], "warn")

    def test_kegg_and_ec(self):
        for value in ("hsa04110", "hsa:7157", "C00031", "K04451", "cpd:C00031", "map00010"):
            with self.subTest(value=value):
                self.assertEqual(first(value)[:2], ("ok", "kegg"))
        self.assertEqual(first("EC 1.1.1.1")[:2], ("ok", "ec"))
        self.assertEqual(first("2.7.11.-")[0], "warn")
        self.assertEqual(first("1.-.1.1")[0], "invalid")
        self.assertEqual(first("8.1.1.1")[0], "invalid")

    def test_structures_domains_networks(self):
        status, type_, r = first("4hhb")
        self.assertEqual((status, type_), ("ok", "pdb"))
        self.assertEqual(r["matches"][0]["normalized"], "4HHB")
        self.assertEqual(first("pdb_00004hhb")[:2], ("ok", "pdb"))
        self.assertEqual(bic.classify("4HHB_A")["matches"][0]["details"]["chain"], "A")
        self.assertEqual(first("1234")[0], "unrecognized")          # all digits: not a PDB ID
        self.assertEqual(first("AF-P04637-F1")[:2], ("ok", "alphafold"))
        self.assertEqual(first("IPR000001")[:2], ("ok", "interpro"))
        self.assertEqual(first("PF00870")[:2], ("ok", "pfam"))
        self.assertEqual(first("PTHR11447")[:2], ("ok", "panther"))
        self.assertEqual(first("R-HSA-69620")[:2], ("ok", "reactome"))
        self.assertEqual(first("WP254")[:2], ("ok", "wikipathways"))
        self.assertEqual(first("9606.ENSP00000269305")[:2], ("ok", "string"))
        self.assertEqual(first("MA0139.2")[:2], ("ok", "jaspar"))
        self.assertEqual(first("MA0139")[0], "warn")


class TestArchivesAndOntologies(unittest.TestCase):
    def test_archives_and_registries(self):
        expected = {
            "GSE12345": "geo", "PRJNA123456": "insdc", "SRR1234567": "insdc", "SAMN01234567": "insdc",
            "GCF_000001405.40": "assembly", "NCT01234567": "nct", "2004-000123-45": "eu-ct",
            "GCST000123": "gwas", "COSV12345678": "cosmic", "PA128": "pharmgkb", "ST000001": "mwb",
            "ACH-000001": "depmap", "CVCL_0023": "cellosaurus", "10.1000/xyz123": "doi",
            "PMID:12345": "pmid", "PMC123456": "pmcid", "taxon:9606": "taxon",
        }
        for value, type_ in expected.items():
            with self.subTest(value=value):
                self.assertEqual(first(value)[:2], ("ok", type_))
        self.assertEqual(first("GCA_000001405")[0], "warn")
        self.assertEqual(first("NCT123")[0], "unrecognized")

    def test_ontology_forms(self):
        self.assertEqual(first("GO:0006915")[:2], ("ok", "ontology"))
        self.assertEqual(first("MONDO:0007739")[0], "ok")
        self.assertEqual(first("CHEBI:15422")[0], "ok")
        self.assertEqual(first("NCBITaxon:9606")[:2], ("ok", "ontology"))
        status, _type, r = first("http://purl.obolibrary.org/obo/GO_0006915")
        self.assertEqual(status, "ok")
        self.assertEqual(r["matches"][0]["normalized"], "GO:0006915")

    def test_zero_stripped_ontology_id(self):
        status, _type, r = first("GO:6915")
        self.assertEqual(status, "invalid")
        self.assertIn("GO:0006915", r["messages"][0])

    def test_short_form_and_prefix_case_warn(self):
        status, _type, r = first("HP_0001250")
        self.assertEqual(status, "warn")
        self.assertEqual(r["matches"][0]["normalized"], "HP:0001250")
        status, _type, r = first("efo:0000305")
        self.assertEqual(status, "warn")
        self.assertEqual(r["matches"][0]["type"], "ontology")
        self.assertIn("EFO:", r["messages"][0])

    def test_type_mismatch(self):
        status, _type, r = first("ENSG00000139618", "uniprot")
        self.assertEqual(status, "invalid")
        self.assertIn("Ensembl gene ID", r["messages"][0])


class TestCli(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(run(["P04637", "GO:0006915"])[0], 0)
        self.assertEqual(run(["P04637", "GO:6915"])[0], 1)
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run(["--type", "nonsense", "P04637"])[0], 2)
        self.assertEqual(run(["--column", "2", "P04637"])[0], 2)
        self.assertEqual(run(["--file", os.path.join(HERE, "does-not-exist.txt")])[0], 2)

    def test_strict_fails_on_warnings(self):
        self.assertEqual(run(["NM_000546"])[0], 0)
        self.assertEqual(run(["--strict", "NM_000546"])[0], 1)

    def test_json_output(self):
        code, out, _err = run(["--json", "P04637", "GO:6915", "7157"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["summary"]["checked"], 3)
        self.assertEqual(data["summary"]["ok"], 1)
        self.assertEqual(data["summary"]["invalid"], 1)
        self.assertEqual(data["summary"]["unrecognized"], 1)
        self.assertEqual([r["line"] for r in data["results"]], [1, 2, 3])

    def test_deterministic(self):
        argv = ["--json", "P04637", "NM_000546", "NM_000546.6", "P04637", "hsa04110"]
        self.assertEqual(run(argv)[1], run(argv)[1])

    def test_file_input_with_comments_and_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ids.tsv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# exported list\nsymbol\tid\n\nTP53\tP04637\nBRCA1\tP38398\n")
            code, out, _err = run(["--file", path, "--column", "2", "--skip-header", "--type", "uniprot"])
            self.assertEqual(code, 0)
            self.assertIn("# checked 2: ok 2", out)
            self.assertTrue(out.startswith("4\tok\tuniprot\tP04637"))
            code, _out, _err = run(["--file", path, "--column", "5"])
            self.assertEqual(code, 2)

    def test_stdin(self):
        code, out, _err = run(["--file", "-"], stdin_text="P04637\nENSG00000139618\n")
        self.assertEqual(code, 0)
        self.assertIn("# checked 2: ok 2", out)

    def test_list_warnings(self):
        code, out, _err = run(["P04637", "P04637", "NM_000546", "NM_000546.6", "NM_000546.5"])
        self.assertEqual(code, 0)
        self.assertIn("appear more than once: P04637 x2", out)
        self.assertIn("carry a version", out)
        self.assertIn("different versions: NM_000546", out)

    def test_quiet_hides_ok(self):
        _code, out, _err = run(["--quiet", "P04637", "NM_000546"])
        self.assertNotIn("\tP04637\t", out)
        self.assertIn("NM_000546", out)

    def test_list_types(self):
        code, out, _err = run(["--list-types"])
        self.assertEqual(code, 0)
        names = [line.split("\t")[0] for line in out.splitlines()]
        self.assertEqual(names, bic.TYPE_NAMES)
        self.assertIn("hgvs", names)

    def test_script_runs_isolated(self):
        proc = subprocess.run([sys.executable, "-I", SCRIPT, "--json", "rs699"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["results"][0]["matches"][0]["type"], "rsid")


if __name__ == "__main__":
    unittest.main()
