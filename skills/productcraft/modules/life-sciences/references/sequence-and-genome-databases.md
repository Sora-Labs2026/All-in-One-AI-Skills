# Sequence, gene and genome databases

Read this when a task needs gene records, transcript or protein sequences, genome assemblies and annotation files, raw sequencing reads, published expression series, Ensembl variant-effect predictions or transcription factor binding profiles from NCBI, ENA, Ensembl, GEO, SRA or JASPAR. Shared rules (identifiers, rate limits, snapshots, licenses) are in `bio-data-access.md`; Entrez code with Biopython is in `biopython.md`; quick notebook lookups are in `gget.md`.

## Which resource answers the question

| Question | Use | Notes |
|---|---|---|
| Gene summary, aliases, RefSeq transcripts, gene IDs across many organisms | NCBI Gene (E-utilities or Datasets) | Integer Gene IDs (`7157` is human TP53) |
| Genome assembly with annotation for a species | NCBI Datasets or Ensembl FTP | `GCF_` RefSeq or `GCA_` GenBank assemblies |
| Gene models, canonical transcripts, regions, orthologs, cross-references | Ensembl REST, BioMart or FTP | Vertebrates; other kingdoms in Ensembl Genomes divisions |
| Consequence of a variant on transcripts | Ensembl VEP (REST for a few, local for many or for patient data) | Consequence terms are Sequence Ontology terms |
| Raw reads (FASTQ) for a published study | ENA file reports, or SRA with sra-tools | The same run is mirrored across INSDC |
| Processed expression from published experiments | GEO | Processing differs by submitter |
| Transcription factor binding profiles | JASPAR | Versioned matrix IDs |

## NCBI: Gene, RefSeq and Datasets

### E-utilities

- Base `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` with `esearch`, `esummary`, `efetch`, `elink`, `epost` and `einfo`. Limits: 3 requests per second without a key, 10 with `api_key`; always send `tool` and `email`. Biopython code is in `biopython.md`.
- Use field tags, not free text, in `db=gene`: `TP53[sym] AND "Homo sapiens"[orgn] AND alive[prop]`. `alive[prop]` drops discontinued and replaced records, which otherwise show up as duplicates.
- For more than a few hundred IDs, `epost` them or search with `usehistory=y`, then page `efetch` or `esummary` with `WebEnv`, `query_key`, `retstart` and `retmax` (a few hundred per call). Send long ID lists by POST, not in the URL.
- PubMed searches return at most 10,000 IDs per query; split by date range. Literature search itself is in `../../research-writing/references/biomedical-and-preprint-apis.md`.

### Bulk gene files (the best mapping tables)

`https://ftp.ncbi.nlm.nih.gov/gene/DATA/` holds `gene_info.gz` (per-organism files under `GENE_INFO/`), `gene2refseq.gz`, `gene2ensembl.gz`, `gene2accession.gz`, `gene2go.gz` and `gene_history.gz`. They are regenerated daily, so record the download date. Use `gene_history.gz` to translate discontinued Gene IDs before reporting them as missing.

### NCBI Datasets

The v2 REST API (`https://api.ncbi.nlm.nih.gov/datasets/v2/`) and the `datasets` and `dataformat` command-line tools return gene, genome and virus data packages. Same key and similar limits as E-utilities (about 5 requests per second without a key, 10 with one).

```bash
datasets summary gene symbol BRCA1 --taxon human --as-json-lines \
  | dataformat tsv gene --fields gene-id,symbol,description        # list fields: dataformat tsv gene --help
datasets download gene symbol TP53 --taxon human --include gene,rna,protein --filename tp53.zip
datasets download genome accession GCF_000001405.40 --include gff3,rna,protein,genome --dehydrated --filename grch38.zip
datasets rehydrate --directory grch38/      # after unzip; fetches the large files with resumable transfers
```

- Use `--dehydrated` plus `rehydrate` for genomes and large sets; it resumes and verifies.
- Check the CLI version (`datasets --version`); field names and flags have changed between releases.

### RefSeq accessions

| Prefix | Meaning |
|---|---|
| `NM_`, `NR_` | Curated mRNA, curated non-coding RNA |
| `XM_`, `XR_` | Predicted (model) mRNA and RNA; can be replaced or withdrawn |
| `NP_`, `XP_` | Curated and predicted proteins |
| `NC_`, `NG_`, `NT_`, `NW_` | Chromosomes, genomic regions (often used for HGVS `g.`), contigs, scaffolds |
| `WP_` | Non-redundant prokaryotic proteins shared across genomes |

For human clinical-style reporting, use MANE Select: one transcript per protein-coding gene with an identical RefSeq and Ensembl pair. The MANE summary table is on the NCBI FTP site under `refseq/MANE/`; record its release number.

## Ensembl

### REST API

- `https://rest.ensembl.org` for the current release on GRCh38; `https://grch37.rest.ensembl.org` for GRCh37. Send `Content-Type: application/json`. Limit: 15 requests per second (55,000 per hour) per client; responses carry `X-RateLimit-*` headers and 429 includes `Retry-After`.
- The server answers only for the current release (for example 115 in September 2025). Read it from `/info/data` and record it. To reproduce an older release, use that release's FTP files, its BioMart archive site, or `pyensembl` with an explicit release.
- Useful endpoints: `/lookup/symbol/homo_sapiens/BRCA2`, `/lookup/id/{id}?expand=1`, POST `/lookup/id` with `{"ids": [...]}`, `/sequence/id/{id}?type=cdna|cds|protein|genomic`, `/overlap/region/human/7:140424943-140624564?feature=gene`, `/xrefs/id/{id}`, `/map/human/GRCh37/{region}/GRCh38`, `/vep/human/hgvs/{notation}`, `/vep/human/id/{rsid}` and POST `/vep/human/region`. Batch endpoints cap the number of items per request; the documentation page for each one states the maximum.
- `lookup` marks `is_canonical`; for human protein-coding genes the Ensembl canonical transcript is the MANE Select transcript where one exists.

```python
import requests

def ensembl_lookup(ids, base="https://rest.ensembl.org"):
    """Batch lookup; returns {id: record or None}. Unknown IDs come back as null."""
    r = requests.post(f"{base}/lookup/id", json={"ids": ids},
                      headers={"Content-Type": "application/json", "Accept": "application/json"},
                      timeout=60)
    r.raise_for_status()
    return r.json()

release = requests.get("https://rest.ensembl.org/info/data", headers={"Accept": "application/json"},
                       timeout=30).json()["releases"]
```

### VEP

- The REST VEP is for tens to a few hundred variants and for public variants only. For whole VCFs, and for any patient or unpublished data, run VEP locally (the official Docker image with an offline cache of the same release and assembly) so the data stays on the machine and the run is pinned.
- Normalize variants first (`reads-and-variants.md`). Record VEP version, cache release, assembly, plugins and flags (`--pick`, `--mane`, `--everything`). A "most severe consequence" depends on the transcript set; state which transcript you report.

### BioMart and FTP

- BioMart (web, `pybiomart`, R `biomaRt`) builds attribute tables: Ensembl gene ID, symbol, NCBI Gene ID, UniProt accession, biotype. Archive hosts named by date (for example `https://may2024.archive.ensembl.org`) serve past releases for several years.
- FTP `https://ftp.ensembl.org/pub/release-N/` has GTF and GFF3 annotation, FASTA (`cdna`, `ncrna`, `pep`, `dna`), and `CHECKSUMS` files. For human alignment use the `primary_assembly` FASTA: `toplevel` adds haplotypes and patches, which creates multi-mapping reads.
- GENCODE and Ensembl annotations match for a given release pair (for example GENCODE 46 equals Ensembl 112) but use `chr1` versus `1` naming.

## ENA, SRA and INSDC reads

- ENA (EMBL-EBI), NCBI SRA and DDBJ exchange data as INSDC partners, so a run submitted to SRA (`SRR`) is also served by ENA. ENA's file report gives direct FASTQ URLs with MD5 checksums, which is often simpler than the SRA toolkit.

| Level | ENA / NCBI / DDBJ accessions |
|---|---|
| Project | `PRJEB`, `PRJNA`, `PRJDB` |
| Study | `ERP`, `SRP`, `DRP` |
| Sample | `SAMEA`, `SAMN`, `SAMD` (BioSample) and `ERS`, `SRS`, `DRS` |
| Experiment | `ERX`, `SRX`, `DRX` |
| Run | `ERR`, `SRR`, `DRR` |
| Assembly | `GCA_` (GenBank), `GCF_` (RefSeq) |

```python
import csv, io, requests

def ena_runs(accession):
    """Runs for a project, study or sample with FASTQ URLs, MD5s and sizes."""
    r = requests.get("https://www.ebi.ac.uk/ena/portal/api/filereport", timeout=120, params={
        "accession": accession, "result": "read_run", "format": "tsv",
        "fields": "run_accession,sample_accession,library_layout,fastq_ftp,fastq_md5,fastq_bytes"})
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text), delimiter="\t"))
```

- Portal API search (`/ena/portal/api/search?result=read_run&query=...`) filters by metadata; `tax_tree(9606)` includes descendants, `tax_eq(9606)` does not. Browser API (`/ena/browser/api/xml/{acc}`, `/fasta/{acc}`, `/embl/{acc}`) returns records. Limit: 50 requests per second.
- Sum `fastq_bytes` before downloading and ask before pulling hundreds of gigabytes. Paired-end runs have `_1` and `_2` files and sometimes a third unpaired file; check `library_layout`. Verify every file's MD5.
- SRA toolkit: `prefetch SRR...` then `fasterq-dump --split-files --threads 8`. Point the cache (`vdb-config`) at a disk with several times the run size free. Public SRA data is also in cloud buckets, which avoids egress charges when the compute runs in the same region.
- Human controlled-access runs (dbGaP) need an authorization file from an approved request. Do not attempt them otherwise.

## GEO

- Accessions: `GSE` series (an experiment), `GSM` samples, `GPL` platforms, `GDS` curated datasets (older array studies only). SuperSeries group SubSeries, so the same `GSM` can appear in several series; deduplicate by `GSM`.
- Access: E-utilities with `db=gds` for search; FTP for files at `https://ftp.ncbi.nlm.nih.gov/geo/series/GSE12nnn/GSE12345/` (the last three digits become `nnn`), with `matrix/`, `soft/`, `miniml/` and `suppl/` folders. Python `GEOparse` and R `GEOquery` parse SOFT and series-matrix files.
- Series matrix files hold the values the submitter processed. Normalization differs between series; for arrays, values above roughly 50 usually mean the data are not log-transformed. Do not merge series without re-processing or explicit batch handling.
- RNA-seq series usually keep counts in supplementary files in submitter-specific formats. For many human and mouse RNA-seq series, GEO also offers counts produced by NCBI's uniform pipeline, which are more comparable across series; otherwise re-process from SRA.
- Sample metadata (`characteristics_ch1`) is free text in `key: value` form. Parse it into columns, normalize terms against an ontology (`biomedical-ontologies.md`) and check condition against submission date or platform for confounding.
- Single-cell series ship matrices or `h5ad` files as supplementary data; loading them is covered in `anndata.md` and `scanpy.md`.

## JASPAR (transcription factor binding profiles)

- Matrix IDs carry a version: `MA0139.2` is the second version of base profile `MA0139`. Store the full versioned ID. The CORE collection is curated and non-redundant; UNVALIDATED profiles are lower confidence.
- Releases are named by year (JASPAR 2024 is current at the time of writing). Pin the release: `pyjaspar` bundles releases for offline use, and the REST API at `https://jaspar.elixir.no/api/v1/` returns matrices in JASPAR, MEME, TRANSFAC or JSON format (`/matrix/MA0139.2/?format=jaspar`) and searches by name, taxon group and collection.
- Scanning: Biopython `Bio.motifs` for small jobs (add pseudocounts, set the background from the sequence GC content, scan both strands); FIMO from the MEME suite for genome scale with q-values. A position weight matrix match is a hypothesis: most matches are not bound in vivo, so intersect with ChIP-seq or ATAC-seq peaks for the cell type.
- Variant impact: score reference and alternate windows that extend motif length minus one base on each side, and report the score change with the threshold used.
- License: openly downloadable with attribution; confirm the current terms on the download page and cite the release paper it names.

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| Gene list shrinks after lookup | Discontinued or renamed IDs and symbols; translate through `gene_history.gz` or HGNC previous symbols, and report what was replaced |
| Same gene twice with different IDs | Mixed versioned and unversioned Ensembl IDs, or alive plus replaced NCBI records; strip versions for the join and filter `alive[prop]` |
| Coordinates off by one or on the wrong build | REST defaults to GRCh38 and 1-based closed regions; use the GRCh37 server for hg19 and convert BED at the boundary |
| Reads multi-map to alternative haplotypes | Aligned to a `toplevel` FASTA; use `primary_assembly` or an analysis set |
| Truncated FASTQ download | Resume and check the published MD5 before any processing |
| GEO samples "do not match" between series | Different processing; re-process raw data or model batch explicitly |

## Checks (done when)

- [ ] Ensembl release, GENCODE or RefSeq annotation release, MANE release, assembly and naming style are recorded.
- [ ] Gene IDs were resolved with organism given and discontinued records handled, with counts reported.
- [ ] VEP or other consequence calls name the tool version, cache release and transcript selection; patient variants were annotated locally.
- [ ] Every downloaded read file passed its MD5 check, and total size was estimated (and approved if large) before download.
- [ ] GEO series were checked for processing, scale and metadata confounding before combining.
- [ ] JASPAR matrix IDs include versions and the release is named; motif hits are reported as predictions.
