#!/usr/bin/env python3
"""Check the shape of common life-science identifiers, offline.

Classifies each identifier (auto mode) or validates every identifier against one
expected type (--type). Covers UniProt accessions and entry names, Ensembl and
RefSeq accessions, NCBI Gene and HGNC IDs, gene symbols, rsIDs, ClinVar
accessions, SPDI, VCF-style and GTEx variant IDs, HGVS expressions (shape only),
ChEMBL, PubChem, DrugBank, HMDB, KEGG, EC numbers, InChIKeys, PDB and AlphaFold
IDs, InterPro, Pfam, PANTHER, Reactome, WikiPathways, STRING, GEO, INSDC and
SRA accessions, assemblies, trial registry numbers, GWAS Catalog, COSMIC,
ClinPGx/PharmGKB, Metabolomics Workbench, DepMap, Cellosaurus, JASPAR and ZINC
IDs, DOIs, PubMed and PMC IDs, and ontology CURIEs, IRIs and short forms.

It also flags common damage: zero-stripped ontology IDs (GO:6915), unversioned
transcripts, HGVS expressions whose prefix does not fit the reference sequence,
spreadsheet-mangled gene symbols (1-Mar), renamed symbols (SEPT2), wrong case,
duplicates and lists that mix versioned and unversioned IDs.

Shape only: an identifier that passes may still not exist, may be obsolete, or
may point at the wrong record. Confirm existence with the database itself, and
validate HGVS against the reference with a dedicated validator.

Read-only, standard library only, no network, deterministic output.

Exit codes: 0 every identifier recognized (or valid for --type) with no errors
(and no warnings with --strict); 1 at least one identifier invalid or
unrecognized (or any warning with --strict); 2 usage or input error.
"""

import argparse
import json
import re
import sys

VERSION = "1.0"

STATUSES = ("ok", "warn", "invalid", "unrecognized")

# ---------------------------------------------------------------- helpers


def _m(type_, label, normalized, details=None, warnings=None, errors=None):
    return {
        "type": type_,
        "label": label,
        "normalized": normalized,
        "details": dict(sorted((details or {}).items())),
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _full(pattern, flags=0):
    return re.compile(r"\A(?:" + pattern + r")\Z", flags)


UNIPROT_ACC = r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}"
UNIPROT_RE = _full(r"(?P<acc>" + UNIPROT_ACC + r")(?:-(?P<iso>\d+))?")
UNIPROT_NAME_RE = _full(r"(?P<code>[A-Z0-9]{1,11})_(?P<species>(?=[A-Z0-9]*[A-Z])[A-Z0-9]{2,5})")

ENSEMBL_RE = _full(r"ENS(?P<species>[A-Z]{3,5})?(?P<feature>[GTPER])(?P<num>\d{11})(?:\.(?P<ver>\d+))?")
ENSEMBL_FEATURES = {"G": "gene", "T": "transcript", "P": "protein", "E": "exon", "R": "regulatory feature"}

REFSEQ_RE = _full(r"(?P<prefix>AC|AP|NC|NG|NM|NP|NR|NT|NW|XM|XP|XR|WP|YP)_(?P<num>\d{6,9})(?:\.(?P<ver>\d+))?")
REFSEQ_NZ_RE = _full(r"NZ_(?P<num>[A-Z]{2,6}\d{6,10})(?:\.(?P<ver>\d+))?")
REFSEQ_KINDS = {
    "AC": "genomic (alternate assembly)", "AP": "protein (alternate assembly)",
    "NC": "genomic, complete molecule (chromosome)", "NG": "genomic region", "NT": "genomic contig",
    "NW": "genomic scaffold", "NM": "mRNA, curated", "NR": "non-coding RNA, curated",
    "NP": "protein, curated", "XM": "mRNA, predicted model", "XR": "non-coding RNA, predicted model",
    "XP": "protein, predicted model", "WP": "protein, non-redundant prokaryotic", "YP": "protein (no curated mRNA)",
}

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE_LIKE_RE = _full(r"\d{1,2}-(?:" + MONTHS + r")|(?:" + MONTHS + r")-\d{1,2}", re.I)

INTEGER_RE = _full(r"[1-9]\d*")

# Ontology and vocabulary prefixes: canonical prefix -> (local-ID pattern, description, padded width or None)
ONTOLOGIES = {
    "GO": (r"\d{7}", "Gene Ontology", 7),
    "HP": (r"\d{7}", "Human Phenotype Ontology", 7),
    "MONDO": (r"\d{7}", "Mondo disease ontology", 7),
    "EFO": (r"\d{7}", "Experimental Factor Ontology", 7),
    "UBERON": (r"\d{7}", "Uberon anatomy ontology", 7),
    "CL": (r"\d{7}", "Cell Ontology", 7),
    "SO": (r"\d{7}", "Sequence Ontology", 7),
    "MP": (r"\d{7}", "Mammalian Phenotype Ontology", 7),
    "ECO": (r"\d{7}", "Evidence and Conclusion Ontology", 7),
    "OBI": (r"\d{7}", "Ontology for Biomedical Investigations", 7),
    "UO": (r"\d{7}", "Units of Measurement Ontology", 7),
    "PATO": (r"\d{7}", "Phenotype And Trait Ontology", 7),
    "CHEBI": (r"\d+", "ChEBI chemical entity", None),
    "DOID": (r"\d+", "Human Disease Ontology", None),
    "NCBITaxon": (r"\d+", "NCBI Taxonomy", None),
    "NCIT": (r"C\d+", "NCI Thesaurus", None),
    "Orphanet": (r"\d+", "Orphanet (ORDO)", None),
    "ORPHA": (r"\d+", "Orphanet", None),
    "OMIM": (r"\d{6}", "OMIM entry", None),
    "MESH": (r"[CDGQ]\d{6}(?:\d{3})?", "MeSH unique ID", None),
}
OBO_STYLE = {"GO", "HP", "MONDO", "EFO", "UBERON", "CL", "SO", "MP", "ECO", "OBI", "UO", "PATO",
             "CHEBI", "DOID", "NCBITaxon", "NCIT", "Orphanet"}
PREFIX_LOOKUP = {k.lower(): k for k in ONTOLOGIES}

KEGG_DB_PREFIXES = {"cpd", "dr", "ko", "md", "rn", "gl", "ec", "ds", "path", "map", "br", "up", "ncbi",
                    "drug", "compound", "glycan", "reaction", "module", "disease", "orthology"}
NON_KEGG_PREFIXES = KEGG_DB_PREFIXES | set(PREFIX_LOOKUP) | {
    "rs", "pmid", "pmc", "doi", "http", "https", "urn", "cid", "sid", "aid", "chr", "hgnc", "mgi",
    "rgd", "zfin", "gene", "geneid", "taxon", "uniprot", "uniprotkb", "ensembl", "chembl", "pubchem"}

DNA_KINDS = {"c": "coding DNA", "g": "genomic DNA", "m": "mitochondrial DNA", "n": "non-coding DNA",
             "o": "circular genomic DNA", "r": "RNA", "p": "protein"}

AA3 = "Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val|Sec|Pyl|Ter|Xaa"


def _norm_ws(value):
    return value.strip()


# ---------------------------------------------------------------- per-type checkers
# Each checker takes (value, explicit) and returns a match dict or None.
# explicit=True means the user asked for this type, so ambiguous forms (bare integers) are accepted.


def check_uniprot(v, explicit=False):
    s = v
    m = re.match(r"\A(?:UniProtKB|uniprot|UniProt):(.+)\Z", s, re.I)
    if m:
        s = m.group(1)
    m = UNIPROT_RE.match(s)
    if not m:
        return None
    d = {"accession": m.group("acc"), "length": len(m.group("acc"))}
    label = "UniProtKB accession"
    if m.group("iso"):
        d["isoform"] = int(m.group("iso"))
        label += " (isoform)"
    return _m("uniprot", label, s, d)


def check_uniprot_name(v, explicit=False):
    m = UNIPROT_NAME_RE.match(v)
    if not m or m.group("code") in ("CVCL", "ACH"):
        return None
    return _m("uniprot-name", "UniProtKB entry name (mnemonic)", v, {"species_code": m.group("species")},
              warnings=["entry names can change between releases; store the accession instead"])


def check_ensembl(v, explicit=False):
    s = v
    m = re.match(r"\Aensembl:(.+)\Z", s, re.I)
    if m:
        s = m.group(1)
    m = ENSEMBL_RE.match(s)
    if not m:
        return None
    feature = ENSEMBL_FEATURES[m.group("feature")]
    d = {"feature": feature, "species_code": m.group("species") or "(human)",
         "accession": s.split(".")[0]}
    if m.group("ver"):
        d["version"] = int(m.group("ver"))
    return _m("ensembl", f"Ensembl {feature} ID", s, d)


def check_refseq(v, explicit=False):
    m = REFSEQ_RE.match(v)
    warnings = []
    if m:
        prefix = m.group("prefix")
        kind = REFSEQ_KINDS[prefix]
        d = {"molecule": kind, "accession": v.split(".")[0]}
    else:
        m = REFSEQ_NZ_RE.match(v)
        if not m:
            return None
        d = {"molecule": "genomic, WGS contig (RefSeq)", "accession": v.split(".")[0]}
    if m.group("ver"):
        d["version"] = int(m.group("ver"))
    else:
        warnings.append("unversioned: sequence and coordinates can change between versions; record the version")
    return _m("refseq", f"RefSeq {d['molecule']}", v, d, warnings)


def check_ncbigene(v, explicit=False):
    m = re.match(r"\A(?:NCBIGene|GeneID|ncbigene|EntrezGene):(\d+)\Z", v)
    if m:
        num = m.group(1)
    elif explicit and INTEGER_RE.match(v):
        num = v
    else:
        return None
    if num.startswith("0"):
        return _m("ncbigene", "NCBI Gene ID", v, {}, errors=["NCBI Gene IDs have no leading zeros"])
    return _m("ncbigene", "NCBI Gene ID", f"NCBIGene:{num}", {"gene_id": int(num)})


def check_hgnc(v, explicit=False):
    m = re.match(r"\AHGNC:(\d+)\Z", v, re.I)
    if not m:
        if explicit and INTEGER_RE.match(v):
            return _m("hgnc", "HGNC ID", f"HGNC:{v}", {"hgnc_id": int(v)},
                      warnings=["bare number; write HGNC IDs with the prefix (HGNC:" + v + ")"])
        return None
    return _m("hgnc", "HGNC ID", f"HGNC:{m.group(1)}", {"hgnc_id": int(m.group(1))})


RENAMED_SYMBOLS = [
    (re.compile(r"\ASEPT(\d{1,2})\Z", re.I), "SEPTIN{}"),
    (re.compile(r"\AMARCH(\d{1,2})\Z", re.I), "MARCHF{}"),
    (re.compile(r"\ADEC1\Z", re.I), "DELEC1"),
]


def check_symbol(v, explicit=False):
    if not explicit:
        return None
    if DATE_LIKE_RE.match(v):
        return _m("symbol", "gene symbol", v, {}, errors=[
            "looks like a spreadsheet date conversion of a gene symbol (for example MARCHF1 or SEPTIN2, "
            "formerly MARCH1 and SEPT2); recover the original symbol from the source"])
    if re.search(r"\s", v):
        return _m("symbol", "gene symbol", v, {}, errors=["contains whitespace"])
    if not re.match(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,39}\Z", v) or not re.search(r"[A-Za-z]", v):
        return _m("symbol", "gene symbol", v, {}, errors=["not shaped like a gene symbol"])
    warnings = []
    for rx, new in RENAMED_SYMBOLS:
        mm = rx.match(v)
        if mm:
            warnings.append("previous symbol; HGNC renamed it " + new.format(*mm.groups()) +
                            "; map through HGNC previous symbols")
    for other in (check_ensembl, check_uniprot, check_refseq, check_chembl):
        hit = other(v)
        if hit:
            warnings.append(f"shaped like an identifier ({hit['label']}), not a symbol")
    return _m("symbol", "gene symbol", v, {}, warnings)


def check_rsid(v, explicit=False):
    m = re.match(r"\Ars([1-9]\d*)\Z", v)
    if not m:
        return None
    return _m("rsid", "dbSNP reference SNP ID", v, {"number": int(m.group(1))})


def check_clinvar(v, explicit=False):
    m = re.match(r"\A(VCV|RCV|SCV)(\d{9})(?:\.(\d+))?\Z", v)
    if not m:
        return None
    kinds = {"VCV": "variation record", "RCV": "variant-condition record", "SCV": "submission"}
    d = {"record": kinds[m.group(1)], "accession": f"{m.group(1)}{m.group(2)}"}
    if m.group(3):
        d["version"] = int(m.group(3))
    return _m("clinvar", f"ClinVar {kinds[m.group(1)]} accession", v, d)


def check_spdi(v, explicit=False):
    m = re.match(r"\A(N[CGTW]_\d+\.\d+):(\d+):([ACGTN]*):([ACGTN]*)\Z", v)
    if not m:
        return None
    return _m("spdi", "SPDI variant (0-based interbase position)", v,
              {"sequence": m.group(1), "position": int(m.group(2)), "deleted": m.group(3), "inserted": m.group(4)})


CHROM = r"[1-9]|1\d|2[0-2]|X|Y|M|MT"


def check_vcf_variant(v, explicit=False):
    m = re.match(r"\A(chr)?(" + CHROM + r")-([1-9]\d*)-([ACGTN]+)-([ACGTN]+)\Z", v)
    if not m:
        return None
    warnings = []
    if m.group(1):
        warnings.append("gnomAD-style IDs omit 'chr'")
    if m.group(4) == m.group(5):
        return _m("vcf-variant", "chrom-pos-ref-alt variant ID", v, {}, errors=["REF and ALT are identical"])
    return _m("vcf-variant", "chrom-pos-ref-alt variant ID (gnomAD style)", v,
              {"chrom": m.group(2), "pos": int(m.group(3)), "ref": m.group(4), "alt": m.group(5)}, warnings)


def check_gtex_variant(v, explicit=False):
    m = re.match(r"\Achr(" + CHROM + r")_([1-9]\d*)_([ACGTN]+)_([ACGTN]+)_b(3[78])\Z", v)
    if not m:
        return None
    return _m("gtex-variant", "GTEx variant ID", v,
              {"chrom": m.group(1), "pos": int(m.group(2)), "ref": m.group(3), "alt": m.group(4),
               "build": "GRCh" + m.group(5)})


# ---- HGVS (shape only)


def _hgvs_ref_kind(ref):
    base, _, ver = ref.partition(".")
    versioned = bool(ver)
    if re.match(r"\A(?:NM|XM)_\d+\Z", base):
        return "coding transcript", versioned, True
    if re.match(r"\A(?:NR|XR)_\d+\Z", base):
        return "non-coding transcript", versioned, True
    if base == "NC_012920":
        return "mitochondrial genome", versioned, True
    if re.match(r"\A(?:NC|NG|NT|NW)_\d+\Z", base):
        return "genomic", versioned, True
    if re.match(r"\A(?:NP|XP)_\d+\Z", base):
        return "protein", versioned, True
    if re.match(r"\AENS[A-Z]*T\d{11}\Z", base):
        return "transcript", versioned, True
    if re.match(r"\AENS[A-Z]*P\d{11}\Z", base):
        return "protein", versioned, True
    if re.match(r"\AENS[A-Z]*G\d{11}\Z", base):
        return "gene", versioned, True
    if re.match(r"\ALRG_\d+t\d+\Z", ref):
        return "transcript", True, False
    if re.match(r"\ALRG_\d+p\d+\Z", ref):
        return "protein", True, False
    if re.match(r"\ALRG_\d+\Z", ref):
        return "genomic", True, False
    return "unknown", versioned, False


ALLOWED_KINDS = {
    "coding transcript": "cr",
    "non-coding transcript": "nr",
    "transcript": "cnr",
    "genomic": "go",
    "mitochondrial genome": "m",
    "protein": "p",
    "gene": "g",
}


def _dna_patterns(kind):
    if kind in "cnr":
        pos = r"(?:[-*]?\d+(?:[+-]\d+)?|\?)"
    else:
        pos = r"(?:\d+|\?)"
    nt = "[acgun]" if kind == "r" else "[ACGTN]"
    rng = pos + r"(?:_" + pos + r")?"
    return [
        _full(pos + nt + ">" + nt),
        _full(rng + "="),
        _full(rng + r"del(?:" + nt + r"+|\d+)?"),
        _full(rng + r"dup(?:" + nt + r"+|\d+)?"),
        _full(pos + "_" + pos + r"ins(?:" + nt + r"+|\d+|\(\d+\))"),
        _full(rng + r"delins" + nt + "+"),
        _full(pos + "_" + pos + r"inv(?:\d+)?"),
        _full(rng + nt + r"*\[\d+(?:_\d+)?\]"),
        _full(r"=|\?"),
    ]


def _check_dna_body(kind, body):
    errors, warnings = [], []
    if kind != "r" and re.search(r"(?:>|ins|delins|del|dup)[acgtn]|[acgtn]>", body):
        return ["DNA changes use upper-case nucleotides (RNA, r., uses lower case)"], warnings
    if kind == "r" and re.search(r"[ACGTU]>|>[ACGTU]", body):
        return ["RNA changes (r.) use lower-case nucleotides"], warnings
    if kind in "gmo" and re.search(r"\d[+-]\d|\*\d|(?:^|_)-\d", body):
        return [f"{kind}. positions are plain sequence numbers; intronic offsets and UTR positions belong to c."], warnings
    allele = re.match(r"\A\[(.+)\](?:;\[(.+)\])?\Z", body)
    parts = []
    if allele:
        for group in allele.groups():
            if group:
                parts.extend(p for p in re.split(r";|\(;\)", group) if p)
    else:
        parts = [body]
    patterns = _dna_patterns(kind)
    for part in parts:
        if "(" in part and not re.search(r"ins\(\d+\)", part):
            warnings.append("uncertain positions in parentheses are not shape-checked")
            continue
        if re.search(r"(?<!del)ins", part) and "_" not in part:
            errors.append("an insertion needs the two flanking positions (for example 76_77insG)")
            continue
        if not any(p.match(part) for p in patterns):
            errors.append(f"change '{part}' does not match a recognised HGVS {kind}. shape")
    return errors, warnings


def _protein_patterns():
    aa = "(?:" + AA3 + ")"
    term = r"(?:Ter|\*)"
    pos = aa + r"\d+"
    rng = pos + r"(?:_" + pos + r")?"
    return [
        _full(pos + r"(?:" + aa + r"|\*)"),
        _full(pos + "="),
        _full(rng + "del"),
        _full(rng + "dup"),
        _full(pos + "_" + pos + r"ins(?:" + aa + r"|\*)+"),
        _full(rng + r"delins(?:" + aa + r"|\*)+"),
        _full(pos + "(?:" + aa + ")?fs(?:" + term + r"(?:\d+|\?))?"),
        _full(pos + "(?:" + aa + ")?ext(?:" + term + r"|-)?(?:\d+|\?)"),
        _full(rng + r"\[\d+\]"),
    ]


ONE_LETTER_RE = _full(
    r"[ACDEFGHIKLMNPQRSTVWYUOX]\d+(?:_[ACDEFGHIKLMNPQRSTVWYUOX]\d+)?"
    r"(?:[ACDEFGHIKLMNPQRSTVWYUOX*=]|del|dup|ins[A-Z*]+|delins[A-Z*]+|[A-Z]?fs\*?\d*|ext.*)")


def _check_protein_body(body):
    details, errors, warnings = {}, [], []
    inner = body
    if body.startswith("(") and body.endswith(")"):
        inner = body[1:-1]
        details["predicted"] = True
    if inner in ("=", "?", "0", "0?"):
        return details, errors, warnings
    if any(p.match(inner) for p in _protein_patterns()):
        return details, errors, warnings
    if ONE_LETTER_RE.match(inner):
        warnings.append("one-letter amino-acid codes; three-letter codes (p.Arg72Pro) are preferred")
        return details, errors, warnings
    errors.append(f"change '{body}' does not match a recognised HGVS p. shape")
    return details, errors, warnings


HGVS_RE = _full(r"(?P<ref>[A-Za-z][A-Za-z0-9_]*(?:\.\d+)?)(?:\((?P<gene>[A-Za-z0-9_.-]+)\))?:"
                r"(?P<kind>[cgmnopr])\.(?P<body>.+)")


def check_hgvs(v, explicit=False):
    if re.match(r"\A(?:chr)?(?:\d{1,2}|X|Y|M|MT):[cgmnopr]\.", v, re.I):
        return _m("hgvs", "HGVS expression", v, {}, errors=[
            "HGVS needs a versioned reference sequence accession (for example NC_000017.11), not a chromosome name"])
    m = HGVS_RE.match(v)
    if not m:
        return None
    ref, kind, body = m.group("ref"), m.group("kind"), m.group("body")
    ref_kind, versioned, needs_version = _hgvs_ref_kind(ref)
    d = {"reference": ref, "reference_kind": ref_kind, "prefix": kind + ".", "type": DNA_KINDS[kind]}
    tail = re.match(r"\A(.*\S)\s+\((p\..+)\)\Z", body)        # ClinVar style: c.215C>G (p.Pro72Arg)
    if tail and kind != "p":
        body, d["protein_change"] = tail.group(1), tail.group(2)
    if m.group("gene"):
        d["gene"] = m.group("gene")
    errors, warnings = [], []
    if ref_kind == "unknown":
        warnings.append("reference sequence not recognised as RefSeq, Ensembl or LRG")
    else:
        allowed = ALLOWED_KINDS[ref_kind]
        if kind not in allowed:
            errors.append(f"'{kind}.' does not fit a {ref_kind} reference (expected "
                          + " or ".join(k + "." for k in allowed) + ")")
        if ref_kind == "gene":
            warnings.append("HGVS on an Ensembl gene ID is unusual; use a transcript or genomic accession")
    if needs_version and not versioned:
        warnings.append("reference sequence is unversioned; positions are only meaningful against a version")
    if not errors:
        if kind == "p":
            pdet, perr, pwarn = _check_protein_body(body)
            d.update(pdet)
            errors += perr
            warnings += pwarn
        else:
            derr, dwarn = _check_dna_body(kind, body)
            errors += derr
            warnings += dwarn
    d["checked"] = "shape only; validate against the reference sequence before use"
    return _m("hgvs", f"HGVS {kind}. ({DNA_KINDS[kind]}) expression", v, d, warnings, errors)


# ---- chemistry and drugs


def check_chembl(v, explicit=False):
    if not re.match(r"\ACHEMBL\d+\Z", v):
        return None
    return _m("chembl", "ChEMBL ID (molecule, target, assay or document)", v, {})


def check_inchikey(v, explicit=False):
    m = re.match(r"\A([A-Z]{14})-([A-Z]{8})([SN])([A-Z])-([A-Z])\Z", v)
    if not m:
        return None
    d = {"connectivity_block": m.group(1), "standard": m.group(3) == "S", "protonation": m.group(5)}
    warnings = []
    if m.group(3) == "N":
        warnings.append("non-standard InChIKey; standard keys (flag S) are the ones databases index")
    if m.group(4) != "A":
        warnings.append(f"version character '{m.group(4)}' is not 'A' (InChI version 1)")
    return _m("inchikey", "InChIKey", v, d, warnings)


def check_inchi(v, explicit=False):
    m = re.match(r"\AInChI=1(S?)/\S+\Z", v)
    if not m:
        return None
    return _m("inchi", "InChI string", v, {"standard": m.group(1) == "S"})


def check_pubchem(v, explicit=False):
    for kind, rx in (("CID", r"(?:CID:?\s?|pubchem\.compound:)(\d+)"),
                     ("SID", r"(?:SID:?\s?|pubchem\.substance:)(\d+)"),
                     ("AID", r"(?:AID:?\s?|pubchem\.bioassay:)(\d+)")):
        m = re.match(r"\A" + rx + r"\Z", v, re.I)
        if m:
            return _m("pubchem", f"PubChem {kind}", f"{kind}{m.group(1)}", {"record": kind, "number": int(m.group(1))})
    if explicit and INTEGER_RE.match(v):
        return _m("pubchem", "PubChem CID", f"CID{v}", {"record": "CID", "number": int(v)},
                  warnings=["bare number read as a CID; label CIDs, SIDs and AIDs explicitly"])
    return None


def check_drugbank(v, explicit=False):
    if not re.match(r"\ADB\d{5}\Z", v):
        return None
    return _m("drugbank", "DrugBank drug ID", v, {})


def check_hmdb(v, explicit=False):
    m = re.match(r"\AHMDB(\d+)\Z", v)
    if not m:
        return None
    digits = m.group(1)
    if len(digits) == 7:
        return _m("hmdb", "HMDB metabolite ID", v, {})
    if len(digits) == 5:
        new = "HMDB" + digits.zfill(7)
        return _m("hmdb", "HMDB metabolite ID (legacy 5-digit form)", new, {"legacy": True},
                  warnings=[f"legacy 5-digit form; current IDs have 7 digits: {new}"])
    return _m("hmdb", "HMDB metabolite ID", v, {}, errors=["HMDB IDs have 7 digits (HMDB0000122)"])


KEGG_SIMPLE = [
    ("C", "cpd", "KEGG compound"), ("D", "dr", "KEGG drug"), ("K", "ko", "KEGG orthology (KO)"),
    ("M", "md", "KEGG module"), ("R", "rn", "KEGG reaction"), ("G", "gl", "KEGG glycan"),
]


def check_kegg(v, explicit=False):
    for letter, db, label in KEGG_SIMPLE:
        if re.match(r"\A(?:" + db + r":)?" + letter + r"\d{5}\Z", v):
            return _m("kegg", label, v, {})
    m = re.match(r"\A(?:path:)?(map|ko|ec|rn|[a-z]{3,4})(\d{5})\Z", v)
    if m:
        return _m("kegg", "KEGG pathway", v, {"organism_or_map": m.group(1)})
    m = re.match(r"\A([a-z]{3,4}):([A-Za-z0-9_.-]+)\Z", v)
    if m and m.group(1) not in NON_KEGG_PREFIXES:
        return _m("kegg", "KEGG gene", v, {"organism": m.group(1)})
    return None


def check_ec(v, explicit=False):
    m = re.match(r"\A(?:EC[ :]?|ec:)?(\d+)\.(\d+|-)\.(\d+|-)\.(n?\d+|-)\Z", v)
    if not m:
        return None
    parts = list(m.groups())
    if not 1 <= int(parts[0]) <= 7:
        return _m("ec", "EC number", v, {}, errors=["EC classes run from 1 to 7"])
    seen_dash = False
    for p in parts[1:]:
        if p == "-":
            seen_dash = True
        elif seen_dash:
            return _m("ec", "EC number", v, {}, errors=["a '-' level cannot be followed by a number"])
    warnings = []
    if seen_dash:
        warnings.append("partial EC number (incomplete classification)")
    if parts[3].startswith("n"):
        warnings.append("preliminary EC number (n-prefixed serial)")
    return _m("ec", "EC number", "EC " + ".".join(parts), {}, warnings)


# ---- structures, domains, pathways, networks


def check_pdb(v, explicit=False):
    m = re.match(r"\A([1-9][A-Za-z0-9]{3})(?:[_.:]([A-Za-z0-9]{1,4}))?\Z", v)
    if m and re.search(r"[A-Za-z]", m.group(1)[1:]):
        d = {}
        if m.group(2):
            d["chain"] = m.group(2)
        return _m("pdb", "PDB entry ID (case-insensitive)", m.group(1).upper() + ("_" + m.group(2) if m.group(2) else ""), d)
    m = re.match(r"\Apdb_([0-9][0-9a-z]{7})\Z", v, re.I)
    if m:
        return _m("pdb", "PDB entry ID (extended form)", "pdb_" + m.group(1).lower(), {})
    return None


def check_alphafold(v, explicit=False):
    m = re.match(r"\AAF-(" + UNIPROT_ACC + r")-F(\d+)(?:-model_v(\d+))?\Z", v)
    if not m:
        return None
    d = {"uniprot": m.group(1), "fragment": int(m.group(2))}
    if m.group(3):
        d["model_version"] = int(m.group(3))
    return _m("alphafold", "AlphaFold DB entry", v, d)


def check_domain(v, explicit=False):
    for rx, type_, label in ((r"IPR\d{6}", "interpro", "InterPro entry"), (r"PF\d{5}", "pfam", "Pfam family"),
                             (r"CL\d{4}", "pfam", "Pfam clan"), (r"PTHR\d{5}(?::SF\d+)?", "panther", "PANTHER family")):
        if re.match(r"\A" + rx + r"\Z", v):
            return _m(type_, label, v, {})
    return None


def check_reactome(v, explicit=False):
    m = re.match(r"\AR-([A-Z]{3})-(\d+)(?:\.(\d+))?\Z", v)
    if not m:
        return None
    d = {"species_code": m.group(1)}
    if m.group(3):
        d["version"] = int(m.group(3))
    return _m("reactome", "Reactome stable ID", v, d)


def check_wikipathways(v, explicit=False):
    if not re.match(r"\AWP\d+(?:_r\d+)?\Z", v):
        return None
    return _m("wikipathways", "WikiPathways ID", v, {})


def check_string(v, explicit=False):
    m = re.match(r"\A(\d+)\.(ENS[A-Z]*P\d{11})\Z", v)
    if not m:
        return None
    return _m("string", "STRING protein ID", v, {"taxon": int(m.group(1)), "protein": m.group(2)})


# ---- archives, studies and registries

ARCHIVE_PATTERNS = [
    (r"(GSE|GSM|GPL|GDS)\d+", "geo", "GEO accession"),
    (r"PRJ(?:EB|NA|DB)\d+", "insdc", "INSDC BioProject"),
    (r"[EDS]RP\d{6,}", "insdc", "INSDC study"),
    (r"SAM(?:N|EA|D)\d+", "insdc", "BioSample"),
    (r"[EDS]RS\d{6,}", "insdc", "INSDC sample"),
    (r"[EDS]RX\d{6,}", "insdc", "INSDC experiment"),
    (r"[EDS]RR\d{6,}", "insdc", "INSDC run"),
    (r"[EDS]RA\d{6,}", "insdc", "INSDC submission"),
    (r"NCT\d{8}", "nct", "ClinicalTrials.gov ID"),
    (r"\d{4}-\d{6}-\d{2}(?:-\d{2})?", "eu-ct", "EU clinical trial number (EudraCT or CTIS)"),
    (r"GCST\d{6,}", "gwas", "GWAS Catalog study"),
    (r"COS[VM]\d+", "cosmic", "COSMIC mutation ID"),
    (r"PA\d+", "pharmgkb", "ClinPGx/PharmGKB accession"),
    (r"(?:ST|PR|AN)\d{6}", "mwb", "Metabolomics Workbench ID"),
    (r"ACH-\d{6}", "depmap", "DepMap model ID"),
    (r"CVCL_[A-Z0-9]{4}", "cellosaurus", "Cellosaurus cell line"),
]


def check_archive(v, explicit=False, only=None):
    for rx, type_, label in ARCHIVE_PATTERNS:
        if only and type_ != only:
            continue
        if re.match(r"\A" + rx + r"\Z", v):
            return _m(type_, label, v, {})
    return None


def check_assembly(v, explicit=False):
    m = re.match(r"\AGC([AF])_(\d{9})(?:\.(\d+))?\Z", v)
    if not m:
        return None
    d = {"source": "RefSeq" if m.group(1) == "F" else "GenBank", "accession": f"GC{m.group(1)}_{m.group(2)}"}
    warnings = []
    if m.group(3):
        d["version"] = int(m.group(3))
    else:
        warnings.append("unversioned assembly accession; record the version")
    return _m("assembly", "genome assembly accession", v, d, warnings)


def check_jaspar(v, explicit=False):
    m = re.match(r"\A(MA|PB|PF|PH|PL|CN|POL|UN)(\d{4})(?:\.(\d+))?\Z", v)
    if not m:
        return None
    d = {"collection_prefix": m.group(1), "base_id": m.group(1) + m.group(2)}
    warnings = []
    if m.group(3):
        d["version"] = int(m.group(3))
    else:
        warnings.append("unversioned JASPAR base ID; store the versioned matrix ID (for example MA0139.2)")
    return _m("jaspar", "JASPAR matrix ID", v, d, warnings)


def check_zinc(v, explicit=False):
    m = re.match(r"\AZINC(\d+)\Z", v)
    if not m:
        return None
    if len(m.group(1)) == 12:
        return _m("zinc", "ZINC ID (ZINC15/ZINC20 form)", v, {})
    if len(m.group(1)) < 12:
        return _m("zinc", "ZINC ID (unpadded)", "ZINC" + m.group(1).zfill(12), {},
                  warnings=["unpadded ZINC ID; ZINC15/ZINC20 IDs pad to 12 digits"])
    return None


def check_doi(v, explicit=False):
    m = re.match(r"\A(?:doi:\s?|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)\Z", v, re.I)
    if not m:
        return None
    return _m("doi", "DOI", m.group(1), {})


def check_pmid(v, explicit=False):
    m = re.match(r"\A(?:PMID:?\s?|pubmed:)(\d+)\Z", v, re.I)
    if m:
        return _m("pmid", "PubMed ID", f"PMID:{m.group(1)}", {})
    if explicit and INTEGER_RE.match(v):
        return _m("pmid", "PubMed ID", f"PMID:{v}", {})
    return None


def check_pmcid(v, explicit=False):
    if not re.match(r"\APMC\d+\Z", v):
        return None
    return _m("pmcid", "PubMed Central ID", v, {})


def check_taxon(v, explicit=False):
    prefixes = r"NCBITaxon|taxon|taxid" if explicit else r"taxon|taxid"   # auto mode: NCBITaxon is an ontology CURIE
    m = re.match(r"\A(?:" + prefixes + r"):(\d+)\Z", v, re.I)
    if m:
        return _m("taxon", "NCBI Taxonomy ID", f"NCBITaxon:{m.group(1)}", {"taxon": int(m.group(1))})
    if explicit and INTEGER_RE.match(v):
        return _m("taxon", "NCBI Taxonomy ID", f"NCBITaxon:{v}", {"taxon": int(v)})
    return None


# ---- ontology CURIEs, IRIs and short forms


def _ontology_local(prefix, local, original, form, extra_warnings=()):
    pattern, desc, width = ONTOLOGIES[prefix]
    curie = f"{prefix}:{local}"
    warnings = list(extra_warnings)
    if re.match(r"\A" + pattern + r"\Z", local):
        return _m("ontology", f"{desc} term ({form})", curie, {"prefix": prefix, "local_id": local}, warnings)
    if width and local.isdigit() and len(local) < width:
        fixed = f"{prefix}:{local.zfill(width)}"
        return _m("ontology", f"{desc} term", original, {"prefix": prefix}, warnings,
                  errors=[f"{prefix} IDs have {width} zero-padded digits: {fixed}"])
    return _m("ontology", f"{desc} term", original, {"prefix": prefix}, warnings,
              errors=[f"local ID '{local}' does not fit the {prefix} pattern"])


def check_ontology(v, explicit=False):
    m = re.match(r"\Ahttps?://purl\.obolibrary\.org/obo/([A-Za-z]+)_(\w+)\Z", v)
    if not m:
        m = re.match(r"\Ahttps?://www\.ebi\.ac\.uk/efo/(EFO)_(\d+)\Z", v)
    if not m:
        m = re.match(r"\Ahttps?://www\.orpha\.net/ORDO/(Orphanet)_(\d+)\Z", v)
    if m:
        prefix = PREFIX_LOOKUP.get(m.group(1).lower())
        if prefix:
            return _ontology_local(prefix, m.group(2), v, "IRI")
        return None
    m = re.match(r"\A([A-Za-z]+):(\S+)\Z", v)
    if m and m.group(1).lower() in PREFIX_LOOKUP:
        prefix = PREFIX_LOOKUP[m.group(1).lower()]
        extra = []
        if m.group(1) != prefix:
            extra.append(f"prefix case: write {prefix}:")
        return _ontology_local(prefix, m.group(2), v, "CURIE", extra)
    m = re.match(r"\A([A-Za-z]+)_(\w+)\Z", v)
    if m and m.group(1) in OBO_STYLE:
        prefix = m.group(1)
        return _ontology_local(prefix, m.group(2), v, "short form",
                               ["OBO short form (underscore); store the CURIE"])
    return None


# ---------------------------------------------------------------- registry

TYPES = [
    ("uniprot", "UniProtKB accession, optional isoform (P04637, P04637-2)", check_uniprot),
    ("uniprot-name", "UniProtKB entry name (P53_HUMAN); unstable", check_uniprot_name),
    ("ensembl", "Ensembl gene, transcript, protein, exon or regulatory ID", check_ensembl),
    ("refseq", "RefSeq accession (NM_, NP_, NC_, XM_ ...)", check_refseq),
    ("ncbigene", "NCBI Gene ID (NCBIGene:7157; bare integer with --type)", check_ncbigene),
    ("hgnc", "HGNC ID (HGNC:11998)", check_hgnc),
    ("symbol", "gene symbol (only with --type): date damage, renamed symbols", check_symbol),
    ("rsid", "dbSNP rsID (rs699)", check_rsid),
    ("clinvar", "ClinVar VCV, RCV or SCV accession", check_clinvar),
    ("spdi", "SPDI variant (NC_000017.11:7676153:G:C)", check_spdi),
    ("vcf-variant", "chrom-pos-ref-alt variant (gnomAD style)", check_vcf_variant),
    ("gtex-variant", "GTEx variant ID (chr1_12345_A_G_b38)", check_gtex_variant),
    ("hgvs", "HGVS expression, shape only (NM_000546.6:c.215C>G)", check_hgvs),
    ("chembl", "ChEMBL ID (CHEMBL25)", check_chembl),
    ("inchikey", "InChIKey", check_inchikey),
    ("inchi", "InChI string", check_inchi),
    ("pubchem", "PubChem CID, SID or AID (CID2244; bare integer with --type)", check_pubchem),
    ("drugbank", "DrugBank ID (DB00945)", check_drugbank),
    ("hmdb", "HMDB ID (HMDB0000122)", check_hmdb),
    ("kegg", "KEGG pathway, gene, compound, drug, KO, module, reaction or glycan", check_kegg),
    ("ec", "EC number (EC 1.1.1.1)", check_ec),
    ("pdb", "PDB entry ID (4HHB, pdb_00004hhb), optional chain", check_pdb),
    ("alphafold", "AlphaFold DB entry (AF-P04637-F1)", check_alphafold),
    ("interpro", "InterPro entry (IPR000001)", check_domain),
    ("pfam", "Pfam family or clan (PF00870, CL0023)", check_domain),
    ("panther", "PANTHER family (PTHR11447)", check_domain),
    ("reactome", "Reactome stable ID (R-HSA-69620)", check_reactome),
    ("wikipathways", "WikiPathways ID (WP254)", check_wikipathways),
    ("string", "STRING protein ID (9606.ENSP00000269305)", check_string),
    ("geo", "GEO accession (GSE, GSM, GPL, GDS)", check_archive),
    ("insdc", "INSDC/SRA/ENA project, study, sample, experiment, run", check_archive),
    ("assembly", "genome assembly accession (GCF_000001405.40)", check_assembly),
    ("nct", "ClinicalTrials.gov ID (NCT + 8 digits)", check_archive),
    ("eu-ct", "EudraCT or CTIS trial number", check_archive),
    ("gwas", "GWAS Catalog study (GCST...)", check_archive),
    ("cosmic", "COSMIC mutation ID (COSV, COSM)", check_archive),
    ("pharmgkb", "ClinPGx/PharmGKB accession (PA...)", check_archive),
    ("mwb", "Metabolomics Workbench study, project or analysis", check_archive),
    ("depmap", "DepMap model ID (ACH-000001)", check_archive),
    ("cellosaurus", "Cellosaurus cell line (CVCL_0023)", check_archive),
    ("jaspar", "JASPAR matrix ID (MA0139.2)", check_jaspar),
    ("zinc", "ZINC15/ZINC20 ID", check_zinc),
    ("doi", "DOI", check_doi),
    ("pmid", "PubMed ID (PMID:...; bare integer with --type)", check_pmid),
    ("pmcid", "PubMed Central ID", check_pmcid),
    ("taxon", "NCBI Taxonomy ID (NCBITaxon:9606; bare integer with --type)", check_taxon),
    ("ontology", "ontology CURIE, OBO IRI or short form (GO:0006915)", check_ontology),
]
TYPE_NAMES = [t[0] for t in TYPES]
SHARED_ARCHIVE = {"geo", "insdc", "nct", "eu-ct", "gwas", "cosmic", "pharmgkb", "mwb", "depmap", "cellosaurus"}


def _run_checker(type_name, fn, value, explicit):
    if type_name in SHARED_ARCHIVE:
        return fn(value, explicit, only=type_name)
    res = fn(value, explicit)
    if res and type_name in ("interpro", "pfam", "panther") and res["type"] != type_name:
        return None
    return res


def detect(value):
    """All matches for a value in auto mode, deduplicated and in registry order."""
    seen, out = set(), []
    for name, _desc, fn in TYPES:
        res = _run_checker(name, fn, value, explicit=False)
        if res:
            key = (res["type"], res["label"], res["normalized"])
            if key not in seen:
                seen.add(key)
                out.append(res)
    return out


def _hints(value):
    hints = []
    if INTEGER_RE.match(value):
        hints.append("bare integer is ambiguous (NCBI Gene, PubMed, PubChem CID, taxon); add a prefix such as "
                     "NCBIGene:, PMID:, CID: or NCBITaxon:, or pass --type")
    if DATE_LIKE_RE.match(value):
        hints.append("looks like a spreadsheet date; a gene symbol (MARCHF1, SEPTIN2, formerly MARCH1, SEPT2) "
                     "may have been converted")
    if re.search(r"\s", value):
        squeezed = re.sub(r"\s+", "", value)
        found = detect(squeezed)
        if found:
            hints.append(f"contains whitespace; without it this is a {found[0]['label']}: {squeezed}")
        else:
            hints.append("contains whitespace")
    if re.match(r"\AENS[A-Z]*[GTPER]\d+(?:\.\d+)?\Z", value):
        hints.append("Ensembl stable IDs have exactly 11 digits after the feature letter")
    if value.upper().startswith("ZINC") and not value.startswith("ZINC0"):
        hints.append("ZINC22 and other ZINC formats are not shape-checked; treat them as opaque IDs")
    candidates = []
    if value.upper().startswith("RS") and value[2:].isdigit():
        candidates.append("rs" + value[2:])
    candidates += [value.upper(), value.lower()]
    for cand in candidates:
        if cand != value:
            found = detect(cand)
            if found:
                hints.append(f"case: did you mean {cand} ({found[0]['label']})?")
                break
    if not hints:
        hints.append("no known identifier shape; for gene symbols pass --type symbol")
    return hints


def classify(value, expected=None):
    """Return a result dict for one identifier."""
    raw = value
    v = _norm_ws(value)
    messages = []
    if v != raw:
        messages.append("surrounding whitespace removed")
    if not v:
        return {"input": raw, "status": "invalid", "matches": [], "messages": ["empty identifier"]}
    if expected:
        fn = dict((t[0], t[2]) for t in TYPES)[expected]
        res = _run_checker(expected, fn, v, explicit=True)
        if not res:
            others = detect(v)
            looks = ("; looks like: " + ", ".join(o["label"] for o in others)) if others else ""
            return {"input": raw, "status": "invalid", "matches": [],
                    "messages": messages + [f"not a valid {expected} identifier{looks}"]}
        matches = [res]
    else:
        matches = detect(v)
        if not matches:
            return {"input": raw, "status": "unrecognized", "matches": [], "messages": messages + _hints(v)}
    good = [m for m in matches if not m["errors"]]
    if good:
        matches = good
        status = "warn" if (messages or any(m["warnings"] for m in good)) else "ok"
        for m in good:
            messages.extend(m["warnings"])
    else:
        status = "invalid"
        for m in matches:
            messages.extend(m["errors"] + m["warnings"])
    clean = [{k: m[k] for k in ("type", "label", "normalized", "details")} for m in matches]
    seen, uniq = set(), []
    for msg in messages:
        if msg not in seen:
            seen.add(msg)
            uniq.append(msg)
    return {"input": raw, "status": status, "matches": clean, "messages": uniq}


def list_checks(results):
    """Warnings that need the whole list: duplicates and version mixing."""
    out = []
    counts = {}
    for r in results:
        key = r["input"].strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    dups = sorted((k for k, c in counts.items() if c > 1), key=lambda k: (-counts[k], k))
    if dups:
        shown = ", ".join(f"{k} x{counts[k]}" for k in dups[:5])
        out.append(f"{len(dups)} value(s) appear more than once: {shown}")
    by_type = {}
    for r in results:
        if r["status"] in ("ok", "warn") and r["matches"]:
            m = r["matches"][0]
            acc = m["details"].get("accession")
            if acc and m["type"] in ("ensembl", "refseq", "clinvar", "assembly"):
                by_type.setdefault(m["type"], []).append((acc, m["details"].get("version")))
    for type_, items in sorted(by_type.items()):
        versioned = sum(1 for _a, ver in items if ver is not None)
        if 0 < versioned < len(items):
            out.append(f"{type_}: {versioned} of {len(items)} IDs carry a version; mixed lists join badly "
                       "(strip versions for joins, keep them for provenance)")
        versions = {}
        for acc, ver in items:
            if ver is not None:
                versions.setdefault(acc, set()).add(ver)
        multi = sorted(a for a, vs in versions.items() if len(vs) > 1)
        if multi:
            out.append(f"{type_}: {len(multi)} accession(s) appear with different versions: " + ", ".join(multi[:5]))
    return out


# ---------------------------------------------------------------- input and output


def read_ids(path, column, delimiter, skip_header):
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, encoding="utf-8-sig") as fh:
            text = fh.read()
    items, header_skipped = [], False
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if skip_header and not header_skipped:
            header_skipped = True
            continue
        if column:
            fields = line.split(delimiter)
            if column > len(fields):
                raise ValueError(f"line {n} has {len(fields)} field(s); column {column} requested")
            value = fields[column - 1]
        else:
            value = line.rstrip("\r\n")
        items.append((n, value))
    return items


def summarize(results):
    s = {k: 0 for k in STATUSES}
    types = {}
    for r in results:
        s[r["status"]] += 1
        for m in r["matches"][:1]:
            types[m["type"]] = types.get(m["type"], 0) + 1
    s["checked"] = len(results)
    s["types"] = dict(sorted(types.items()))
    return s


def render_text(results, summary, list_warnings, quiet):
    lines = []
    for r in results:
        if quiet and r["status"] == "ok":
            continue
        m = r["matches"][0] if r["matches"] else None
        type_ = m["type"] if m else "-"
        if len(r["matches"]) > 1:
            type_ += "+" + str(len(r["matches"]) - 1)
        note = m["label"] if m else ""
        if m and m["normalized"] != r["input"].strip():
            note += f" -> {m['normalized']}"
        if r["messages"]:
            note = (note + "; " if note else "") + "; ".join(r["messages"])
        lines.append(f"{r['line']}\t{r['status']}\t{type_}\t{r['input'].strip()}\t{note}")
    for w in list_warnings:
        lines.append(f"# list: {w}")
    lines.append("# checked {checked}: ok {ok}, warn {warn}, invalid {invalid}, unrecognized {unrecognized}".format(**summary))
    return "\n".join(lines) + "\n"


def build_parser():
    p = argparse.ArgumentParser(
        prog="bio_id_check.py",
        description="Classify or validate life-science identifiers offline (shape only).",
        epilog="Exit codes: 0 all recognized or valid; 1 invalid or unrecognized identifiers "
               "(or warnings with --strict); 2 usage or input error.")
    p.add_argument("ids", nargs="*", help="identifiers to check")
    p.add_argument("--type", choices=TYPE_NAMES, metavar="TYPE",
                   help="validate every identifier against this type (see --list-types)")
    p.add_argument("--file", help="read identifiers from a file, one per line ('-' for standard input); "
                                  "blank lines and lines starting with # are skipped")
    p.add_argument("--column", type=int, help="with --file: take this 1-based column of a delimited file")
    p.add_argument("--delimiter", default="\t", help="column delimiter for --column (default: tab)")
    p.add_argument("--skip-header", action="store_true", help="with --file: skip the first data line")
    p.add_argument("--json", action="store_true", help="print JSON instead of tab-separated lines")
    p.add_argument("--quiet", action="store_true", help="text output: hide identifiers that are ok")
    p.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    p.add_argument("--list-types", action="store_true", help="print the known types and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.list_types:
        for name, desc, _fn in TYPES:
            sys.stdout.write(f"{name}\t{desc}\n")
        return 0
    if args.column is not None and (args.column < 1 or not args.file):
        sys.stderr.write("error: --column needs --file and a value of 1 or more\n")
        return 2
    items = [(i, v) for i, v in enumerate(args.ids, start=1)]
    if args.file:
        try:
            items += read_ids(args.file, args.column, args.delimiter, args.skip_header)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            sys.stderr.write(f"error: cannot read {args.file}: {exc}\n")
            return 2
    if not items:
        sys.stderr.write("error: no identifiers given (pass them as arguments or with --file)\n")
        return 2
    results = []
    for line, value in items:
        r = classify(value, args.type)
        r["line"] = line
        results.append(r)
    lw = list_checks(results)
    summary = summarize(results)
    if args.json:
        payload = {"version": VERSION, "mode": args.type or "auto", "summary": summary,
                   "list_warnings": lw, "results": [dict(sorted(r.items())) for r in results]}
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text(results, summary, lw, args.quiet))
    failed = summary["invalid"] + summary["unrecognized"]
    if failed or (args.strict and (summary["warn"] or lw)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
