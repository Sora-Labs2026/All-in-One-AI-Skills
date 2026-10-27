# Public databases: access, identifiers, snapshots and terms

Read this first whenever a task queries, downloads or combines public biological, chemical or clinical databases. It covers what every source has in common: choosing between an API and a bulk download, identifiers and cross-database mapping, polite and robust clients, reproducible snapshots, licenses and citation. The per-database facts live in the topic references listed below.

Database content supports research and software. A ClinVar classification, an FDA adverse-event count or a CPIC recommendation is not medical advice for a person; say so in reports and user interfaces (rule 1 of `../GUIDE.md`).

## Pick the topic reference

| The question is about | Read |
|---|---|
| Genes, transcripts, genome assemblies, raw reads, expression series, transcription factor motifs | `sequence-and-genome-databases.md` |
| Clinical significance of variants, allele frequencies, GWAS hits, eQTLs, somatic cancer mutations, cancer cohorts, cell-line dependencies | `variant-and-cancer-databases.md` |
| Protein function, domains, experimental or predicted structures, interaction networks | `protein-and-structure-databases.md` |
| Pathways and enrichment, metabolites, metabolomics studies, enzyme kinetics | `pathway-and-metabolism-databases.md` |
| Compound identity, bioactivity, binding affinities, drug records, purchasable screening libraries | `chemistry-and-drug-databases.md` |
| Adverse events and labels, clinical trials, pharmacogenomics, target-disease evidence, phenotype-driven gene lists | `clinical-and-translational-databases.md` |
| Finding, mapping or validating ontology terms; parsing OWL or OBO files | `biomedical-ontologies.md` |

One-off lookups in a notebook can use `gget.md`; NCBI access code with Biopython is in `biopython.md`.

## Choose the access route by scale

| Need | Route | Why |
|---|---|---|
| A few records, exploration, a UI that shows live data | REST or GraphQL API | Current data, no setup |
| Hundreds to tens of thousands of records | Batch endpoints: POSTed ID lists, ID-mapping jobs, NCBI history server, paginated search | Fewer calls, fewer 429s |
| Whole tables, genome-wide work, anything rerun later | Bulk download of a numbered release (FTP or HTTPS, cloud bucket, SQL dump, Parquet) | Reproducible, no rate limits, usually faster |
| Joins across many resources | A release-pinned integrated dump (Open Targets Parquet, Monarch knowledge graph) or your own local tables | One consistent snapshot |

Rule of thumb: if the loop would make more than a few thousand calls, or the analysis will be rerun or published, download the release instead of crawling the API. Most APIs serve only the current release, so they cannot reproduce last year's numbers.

### Clients

- Prefer the provider's own client or plain `requests`/`httpx` with a small wrapper you control. Official clients worth using: Biopython `Bio.Entrez` for NCBI, `chembl_webresource_client`, `rcsb-api` for the RCSB PDB.
- Multi-service wrappers (`bioservices` covers about 40 services, `gget` a dozen) are convenient for exploration. They lag behind upstream API changes, and `bioservices` is GPL-3.0, which matters only if you distribute software that includes it.
- APIs move. UniProt changed to `rest.uniprot.org` in 2022, ClinicalTrials.gov retired its classic API in 2024 and the GWAS Catalog moved to a v2 API. Check the installed client version and the provider's current documentation before reusing old code.

## Identifiers

1. **Store stable accessions, not names.** Gene symbols are renamed (HGNC changed `SEPT1` to `SEPTIN1` and `MARCH1` to `MARCHF1`, partly because spreadsheets turned them into dates) and collide across species. Join on HGNC, NCBI Gene or Ensembl IDs, UniProt accessions or InChIKeys and keep symbols as labels. Read gene lists as text, never through a spreadsheet's type guessing.
2. **Keep versions.** `ENST00000269305.9`, `NM_000546.6` and a ClinVar `VCV...` accession with its `.N` suffix name a specific sequence or record state. HGVS `c.` positions are only meaningful against a versioned transcript. Strip versions for joins, keep them for provenance.
3. **Carry the namespace and organism.** In mixed tables write CURIEs with a registered prefix (`UniProtKB:P04637`, `NCBIGene:7157`, `HGNC:11998`, `CHEBI:15422`) and resolve prefixes against one registry (Bioregistry or identifiers.org), used consistently.
4. **Coordinates need an assembly and a convention.** Record GRCh37 or GRCh38, `chr1` or `1`, `chrM` or `MT`, and 0-based or 1-based for every coordinate. Liftover rules are in `genomic-intervals.md`.
5. **Check shape before calling an API.** `../scripts/bio_id_check.py` classifies or validates identifiers offline (UniProt, Ensembl, RefSeq, rsID, ClinVar, HGVS shape, ChEMBL, InChIKey, PDB, ontology CURIEs and more) and flags zero-stripped ontology IDs, unversioned transcripts and spreadsheet-mangled gene symbols.

```bash
python3 <productcraft>/modules/life-sciences/scripts/bio_id_check.py P04637 NM_000546 GO:6915 1-Mar
python3 <productcraft>/modules/life-sciences/scripts/bio_id_check.py --type ensembl --file ids.txt --json
```

### Cross-database mapping

| Mapping | Best sources |
|---|---|
| Gene symbol, NCBI Gene, Ensembl, UniProt | NCBI `gene_info`, `gene2ensembl` and `gene2refseq` files; HGNC complete set; Ensembl BioMart or `xrefs` endpoints; UniProt ID mapping |
| One transcript per human gene | MANE Select (matched RefSeq `NM_` and Ensembl `ENST` pairs with identical sequence) |
| Compounds | Standard InChIKey as the join key; UniChem; PubChem cross-references |
| KEGG to other IDs | KEGG `conv` (KEGG license terms apply) |
| Diseases and phenotypes | Mondo equivalence mappings, published SSSOM files (see `biomedical-ontologies.md`) |
| Variants | Normalize first (`reads-and-variants.md`), then rsID, HGVS and SPDI conversions through NCBI Variation Services or Ensembl VEP |

Mapping rules:
- Mappings are many-to-many. Decide how to treat one-to-many cases (keep all, pick a canonical member such as the MANE transcript or the reviewed Swiss-Prot entry, or drop) and write the rule down.
- Report counts: input, mapped one-to-one, one-to-many, unmapped, duplicates removed. Never drop unmapped rows silently.
- Map stable ID to stable ID. A round trip through gene symbols loses and invents matches.
- Record the mapping source and its release. Mappings change between releases.

## Polite, robust clients

- **Identify yourself.** NCBI wants `tool` and `email` parameters; send a `User-Agent` with a contact address elsewhere; STRING asks for `caller_identity`.
- **Keys and accounts** (NCBI API key, openFDA key, BioPortal key, COSMIC, DrugBank and BRENDA logins) come from environment variables the user sets. Never print them, put them in code, notebooks or logs, or ask for them in chat (`../../agent-safety/references/secrets.md`).
- **Throttle below the published limit** with one limiter shared by all workers. Parallel workers multiply the rate.
- **Honor 429 and 503.** Wait for `Retry-After` when given, otherwise back off exponentially with jitter, and cap attempts. Retry only idempotent requests (`../../engineering-practices/references/resilience.md`).
- **Always set timeouts**, follow the server's pagination (cursor or `next` link) until it stops, and compare the row count with the total the API reports.
- **Run large jobs off-peak** when the provider asks (NCBI: weekends, or 9 pm to 5 am US Eastern on weekdays).
- **Do not scrape HTML** when an API or a download exists, and respect `robots.txt` and the terms of use.

```python
import os, random, time, requests

class PoliteClient:
    """Rate-limited GET with timeouts, Retry-After and capped backoff."""
    def __init__(self, base, per_second, contact=os.environ.get("CONTACT_EMAIL", "unknown")):
        self.base, self.gap, self.last = base.rstrip("/"), 1.0 / per_second, 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"analysis-pipeline/1.0 (mailto:{contact})"

    def get(self, path, params=None, tries=5):
        for attempt in range(tries):
            time.sleep(max(0.0, self.gap - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            r = self.session.get(f"{self.base}/{path.lstrip('/')}", params=params, timeout=(5, 120))
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
                return r
            ra = r.headers.get("Retry-After", "")
            time.sleep((float(ra) if ra.isdigit() else min(60, 2 ** attempt)) + random.uniform(0, 1))
        raise RuntimeError(f"gave up after {tries} attempts: {path}")
```

- **Cache on disk**, keyed by method, URL, sorted parameters and body, inside a directory named for the release (`cache/uniprot-<release>/`). `requests-cache` with a SQLite backend works; give it no expiry for pinned analyses and a short one for live views.
- **Downloads** resume (`curl -C -`, `wget -c`), go to a new directory, and are verified against the checksum file the provider publishes (MD5 on NCBI and ENA, the algorithm named in Ensembl's `CHECKSUMS`). Estimate the size first and ask before pulling more than a few gigabytes.

## Reproducible snapshots

Record for every source: database, release or version as the source reports it, access date (UTC), the exact query or URL with parameters, file names with checksums, genome assembly, and client library version. A small manifest next to the data is enough.

```yaml
# data/MANIFEST.yaml
- source: UniProtKB
  release: "<YYYY_MM>"          # copied from the X-UniProt-Release response header
  accessed: "<UTC timestamp>"
  query: "gene_exact:TP53 AND organism_id:9606 AND reviewed:true"
  file: uniprot_tp53.tsv
  sha256: "<computed after download>"
  license: CC BY 4.0
- source: ClinVar
  release: "clinvar_<YYYYMMDD>.vcf.gz"   # the dated weekly file actually downloaded
  accessed: "<UTC date>"
  assembly: GRCh38
  license: NCBI, no use restrictions
```

| Source | Where the version is reported |
|---|---|
| UniProt | `X-UniProt-Release` response header; release notes on the FTP site |
| Ensembl | REST `/info/data`; FTP `release-N` folders |
| ChEMBL | `/chembl/api/data/status`; release folders `chembl_NN` |
| Reactome | `/ContentService/data/database/version` |
| STRING | `/api/json/version`; versioned hosts such as `version-12-0.string-db.org` |
| ClinVar, PubChem, GEO | Dated bulk files; for API pulls, the access date is the version |
| ClinicalTrials.gov | `/api/v2/version` (data timestamp) |
| openFDA | `meta.last_updated` in every response |
| GTEx, gnomAD | Dataset parameter (`gtex_v10`, `gnomad_r4`) and the release named on the downloads page |
| Open Targets, DepMap, COSMIC, KEGG | Release names (`25.06`, `24Q4`, `v102`, `info/kegg`) |
| Ontologies | `owl:versionIRI` or the dated release file |

- When the source has numbered releases, analyze a downloaded release. When it does not (PubChem, ClinicalTrials.gov, openFDA, GEO metadata), store the raw responses with timestamps and treat the stored copy as the snapshot.
- Tests use saved fixtures and never touch the network in CI; keep one opt-in live smoke test.
- Rerunning on a newer release is a new analysis. Diff the outputs and report what changed and why. Provenance of the whole analysis is covered in `data-provenance.md`.

## Licenses and terms

The license is decided by the use: internal academic research, a commercial product or service, or redistribution of the data. Ask which applies before building on a restricted source.

| Terms | Sources (check each provider's page; terms change) |
|---|---|
| No restrictions or CC0 | NCBI databases (GenBank, RefSeq, Gene, GEO, SRA, dbSNP, ClinVar; submitters may hold rights in some records), ENA and DDBJ, Ensembl, InterPro, PDB, gnomAD, Open Targets Platform, openFDA |
| Attribution (CC BY 4.0) | UniProt, AlphaFold DB, STRING, Reactome, DepMap public releases, BRENDA (since its 2023 release) |
| Share-alike | ChEMBL (CC BY-SA 3.0), ClinPGx and PharmGKB (CC BY-SA 4.0): data you redistribute that derives from them must carry the same license |
| Non-commercial or paid license | **KEGG**: website and API free for academic use only; commercial use and FTP bulk access need a paid license. **COSMIC**: free for academic and non-profit use after registration; commercial use needs a paid license. **DrugBank**: full data for non-commercial research after an approved account; commercial use needs a paid license (its open vocabulary and structure files are CC0). **HMDB**: free for non-commercial use; commercial use or redistribution needs the authors' written permission. **OMIM**, **SNOMED CT**, **MedDRA** and **UMLS** need license agreements |
| Per-dataset terms | cBioPortal studies, GWAS Catalog summary statistics, Metabolomics Workbench studies, the Monarch knowledge graph (each ingested source keeps its license) |
| Controlled access | dbGaP, EGA, GTEx protected data, TCGA controlled data, UK Biobank: approved application and data use agreement required |

- When the use is commercial and a source is restricted, stop and say so plainly; propose open alternatives (Reactome or WikiPathways instead of KEGG, ChEMBL and openFDA labels instead of DrugBank) rather than quietly using the restricted one.
- Tools that fetch data at runtime inherit the data's terms. An enrichment package calling the KEGG API inside a commercial service is commercial use of KEGG.
- Keep the license and the attribution with every derived file (a licenses file next to the data, or the manifest), and do not commit restricted files to public repositories or bake them into public container images. Product-level license duties are in `../../legal-ready/GUIDE.md`.

## Controlled access and privacy

- Never try to bypass a registration wall, a data use agreement or controlled access, and never ask for someone's credentials. Work only inside the environment the agreement names, and do not copy controlled data elsewhere.
- Patient-derived data stays local. Sending a patient's variants to the public VEP server, phenotypes to a similarity API or a genotype file to a web tool discloses health data to a third party. Use the local version of the tool (VEP with an offline cache, PharmCAT, Exomiser) unless the data owner has approved the transfer and the service's terms allow it. De-identification and HIPAA or GDPR duties are in the clinical section of `../GUIDE.md`.
- Aggregate data can still identify people: rare variants in small cohorts, or repeated queries against summary statistics. Do not join public data with other sources to re-identify anyone.

## Cite data, not just papers

- Cite the resource with the publication its "cite us" page names, plus the release or version, the access date and the accessions actually used (GEO series, ENA studies, ChEMBL document IDs). Use dataset DOIs where the provider mints them (DepMap releases, many knowledge-graph releases).
- Never write a citation from memory. Copy it from the resource's citation page and confirm the DOI or PubMed ID resolves (`../../research-writing/references/citations-and-reference-managers.md`).
- When a database aggregates other work (GWAS Catalog studies, ClinVar submitters, cBioPortal studies), cite the original studies whose results you discuss.
- A data availability statement lists each source, release, accessions and license.

## Preprints and literature

Preprint metadata (bioRxiv, medRxiv) and literature search are covered in `../../research-writing/references/biomedical-and-preprint-apis.md`. When preprint content becomes data (text mining, figure reuse, redistribution), check each preprint's own license field; some are all rights reserved.

## Checks (done when)

- [ ] Every source has its release or version, access date, query and file checksums recorded in a manifest.
- [ ] Identifier mapping reports mapped, one-to-many, unmapped and duplicate counts; nothing was dropped silently.
- [ ] Clients identified themselves, stayed under the published limits and never logged a key or password.
- [ ] Each source's license was checked against the intended use, and every restriction was reported to the user in plain words.
- [ ] Three to five records were spot-checked against the provider's web page for the same release.
- [ ] Citations were copied from the providers' citation pages and their DOIs resolve.
- [ ] No patient-derived data went to a remote service without the owner's approval.
