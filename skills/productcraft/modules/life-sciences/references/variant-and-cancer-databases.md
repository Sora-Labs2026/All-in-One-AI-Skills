# Variant, population-genetics and cancer databases

Read this when a task looks up the clinical significance of variants (ClinVar), population allele frequencies and gene constraint (gnomAD), trait associations (GWAS Catalog), tissue expression and eQTLs (GTEx), somatic cancer mutations (COSMIC), cancer cohort genomics (cBioPortal) or cell-line gene dependencies (DepMap). Shared rules are in `bio-data-access.md`; VCF handling and normalization in `reads-and-variants.md`.

**Guardrail.** These sources support research and software. Classifying a patient's variant is done by qualified people following professional guidelines (ACMG/AMP for germline variants) with validated pipelines. Do not present a database lookup as a diagnosis, and do not send patient variants to public web APIs: annotate them against local copies.

## Normalize before you query

- State the assembly (GRCh37 or GRCh38) and normalize: left-align, split multi-allelic records, check REF against the reference (`bcftools norm`, see `reads-and-variants.md`).
- Use the representation each source expects: VCF-style chromosome-position-REF-ALT (gnomAD writes `1-55051215-G-GA`), versioned HGVS (`NM_000546.6:c.215C>G`), rsID, or SPDI for exchange between NCBI services.
- An rsID names a locus, not an allele: one rsID can cover several alternate alleles, and dbSNP merges rsIDs over time. Join on chromosome, position, REF and ALT.
- Check HGVS against the reference with VariantValidator, Mutalyzer or the `hgvs` Python package. `../scripts/bio_id_check.py` only checks the shape (accession type matches `c.`, `g.` or `p.`, version present, plausible change syntax).

## ClinVar

- **What it holds:** submitted assertions about variants. `VCV` accessions aggregate a variant, `RCV` a variant-condition pair, `SCV` one submission; all are versioned. Variation IDs and Allele IDs are integers.
- **Classification types:** since 2024 ClinVar separates germline classification, somatic clinical impact and oncogenicity. Code that reads only an older single clinical-significance field misses or mislabels records; read the field for the type you need.
- **Review status matters more than the label.** Stars: four for practice guideline, three for expert panel, two for multiple submitters with criteria and no conflicts, one for a single submitter with criteria (or conflicting classifications), none without assertion criteria. Filter on review status, and inspect the `SCV` submissions behind any conflict.
- **Access:** E-utilities with `db=clinvar` for small lookups. For analysis use the FTP site `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/`: weekly VCFs per assembly (`vcf_GRCh38/`, with dated copies), `tab_delimited/variant_summary.txt.gz`, `submission_summary.txt.gz`, and monthly XML releases.
- **Pitfall:** `variant_summary.txt.gz` has one row per variant per assembly. Filter the `Assembly` column to one build or every count doubles. The VCF contains only variants with precise coordinates, so it is smaller than the full set.
- **Change over time:** classifications are revised. Pin the dated file and, when re-annotating, report which variants changed class since the previous run.
- **Terms:** NCBI places no restrictions on use; credit submitters when discussing specific assertions.

```python
import pandas as pd

vs = pd.read_csv("variant_summary.txt.gz", sep="\t", low_memory=False, dtype=str)
vs = vs[vs["Assembly"] == "GRCh38"]            # one build only
print(sorted(vs.columns)[:10])                  # column names change; read the header before filtering
```

## gnomAD

- **What it holds:** allele frequencies from aggregated exomes and genomes, per genetic ancestry group, plus coverage, gene constraint, structural variants and loss-of-function curation. v4.1 (GRCh38, 2024) combines about 730,000 exomes and 76,000 genomes; v2.1.1 is GRCh37; v3.1 genomes are GRCh38.
- **API:** the browser's GraphQL endpoint `https://gnomad.broadinstitute.org/api`, with dataset IDs such as `gnomad_r4`, `gnomad_r3` and `gnomad_r2_1` (read the current enum from the schema). It is meant for interactive-scale use; heavy loops get rate limited or blocked.
- **Bulk:** the downloads page and public cloud buckets (Google Cloud, AWS and Azure open-data programs) have sites VCFs, Hail Tables, constraint and coverage tables. Fetch a region without downloading whole files: `bcftools view -r chr17:<start>-<end> <https URL of the sites VCF>` reads the remote tabix index.
- **Interpretation:**
  - For "too common to cause disease" arguments use the filtering allele frequency (the `faf95` group maximum), not the raw global AF, and compare it with a disease-specific threshold.
  - Check the variant's `filters` and the coverage at the site. Absence from gnomAD in a poorly covered region says nothing.
  - Ancestry group labels and the "popmax" concept were renamed in v4 (genetic ancestry groups, `grpmax`); update old code.
  - Gene constraint: use LOEUF as a continuous score. Suggested cutoffs differ between v2 and v4; take them from the gnomAD help page for the version you use.
- **Terms:** CC0; cite the gnomAD paper for the version used.

```python
import requests

QUERY = """
query ($id: String!, $ds: DatasetId!) {
  variant(variantId: $id, dataset: $ds) {
    variant_id
    exome  { ac an filters }
    genome { ac an filters }
  }
}"""

def gnomad_counts(variant_id, dataset="gnomad_r4"):   # variant_id: "chrom-pos-ref-alt" from a normalized VCF
    r = requests.post("https://gnomad.broadinstitute.org/api", timeout=60,
                      json={"query": QUERY, "variables": {"id": variant_id, "ds": dataset}})
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):                    # unknown variants come back as errors, not 404s
        return None, body["errors"]
    return body["data"]["variant"], None      # AF = ac / an per sequencing type
```

## GWAS Catalog

- **What it holds:** curated associations from published genome-wide association studies. Studies are `GCST` accessions; traits are EFO terms (`EFO_0001360` in the API, `EFO:0001360` as a CURIE); variants are rsIDs; publications are PubMed IDs.
- **Inclusion threshold:** the catalog records associations down to p < 1e-5. Filter to genome-wide significance (p < 5e-8) yourself when that is what you mean.
- **Access:** REST API v2 at `https://www.ebi.ac.uk/gwas/rest/api/v2/` (HAL JSON with paging links; the older unversioned API was scheduled for retirement in 2026). Full-catalog TSV downloads carry a release date. Summary statistics live on the EBI FTP site under `pub/databases/gwas/summary_statistics/`, with harmonised GRCh38 files where available.
- **Interpretation:**
  - The reported or mapped gene is usually the nearest or overlapping gene, not the causal gene.
  - Lead SNPs from different studies can tag the same signal through linkage disequilibrium; clump or fine-map before counting loci.
  - Most cohorts are of European ancestry; say so when generalizing.
  - Effect sizes mix odds ratios and betas, and the effect allele is sometimes missing. When harmonizing, palindromic SNPs (A/T, C/G) need allele-frequency checks to resolve strand.
- **Terms:** free to use with citation of the catalog and the original studies. Summary statistics carry per-study licenses, exposed in study metadata.

## GTEx

- **What it holds:** bulk RNA-seq across about 50 tissues from roughly a thousand post-mortem donors, with eQTLs and sQTLs. Datasets: `gtex_v8` (GENCODE v26) and `gtex_v10` (GENCODE v39), both GRCh38.
- **API:** v2 at `https://gtexportal.org/api/v2/`, JSON, paginated (`page`, `itemsPerPage`). Most endpoints take a versioned GENCODE ID, so resolve symbols first with `/reference/gene?geneId=APOE`. Common calls: `/expression/medianGeneExpression`, `/association/singleTissueEqtl`. Always pass `datasetId`.
- **Variant IDs** look like `chr1_12345_A_G_b38`. Convert from VCF style deliberately.
- **Interpretation:** an eQTL links a variant to expression in a tissue; it does not make that gene causal for a GWAS trait. Use colocalization (for example `coloc`) and remember that discovery power follows tissue sample size.
- **Access tiers:** expression and QTL summaries are open; genotypes, individual phenotypes and raw reads are controlled access through dbGaP (study `phs000424`).

## COSMIC

- **What it holds:** expert-curated somatic mutations in cancer, the Cancer Gene Census, mutational signatures, resistance mutations and cell-line data. Genomic mutation IDs are `COSV` (legacy `COSM` IDs remain in older files).
- **Access:** registration required. Downloads use an authenticated scripted request that returns a short-lived signed URL. Keep the account email and password in environment variables and never in code, logs or chat.
- **Releases** are numbered (`v102` in 2025). Use the numbered path, not `latest`, and record it with the assembly (GRCh37 and GRCh38 files differ).
- **License, plainly:** free for academic and non-profit research after registration; any commercial use requires a paid license. Files may not be redistributed, so keep them out of public repositories, shared buckets and container images.
- **Open alternatives** for somatic data: GDC open-access masked mutation files, public cBioPortal studies and somatic records in ClinVar. They are not equivalent to COSMIC curation; say what was used.

## cBioPortal

- **What it holds:** harmonized cancer genomics studies with mutations, copy number, expression, structural variants and clinical data. Study IDs look like `brca_tcga_pan_can_atlas_2018`; molecular profiles are `{studyId}_mutations`; sample lists are `{studyId}_all`. Genes are addressed by NCBI Gene ID.
- **API:** `https://www.cbioportal.org/api` with OpenAPI documentation (`/api/swagger-ui/`); no authentication for the public portal. Private instances use data access tokens kept in environment variables. Bulk: per-study archives from the cBioPortal datahub.

```python
import requests

BASE = "https://www.cbioportal.org/api"
study = "brca_tcga_pan_can_atlas_2018"
muts = requests.post(f"{BASE}/molecular-profiles/{study}_mutations/mutations/fetch",
                     params={"projection": "SUMMARY"}, timeout=120,
                     json={"sampleListId": f"{study}_all", "entrezGeneIds": [7157]}).json()
```

- **Pitfalls:**
  - Read each study's `referenceGenome`; many legacy studies are GRCh37.
  - Targeted panels do not cover every gene, so compute frequencies over samples profiled for that gene (gene panel data), not over all samples.
  - Discrete copy-number calls (-2 to 2) are relative calls, not absolute copy numbers.
  - The same TCGA patients appear in several studies (legacy, PanCancer Atlas); deduplicate by patient ID before pooling.
- **Terms:** data keep the terms of their source studies; cite them. The portal software is AGPL-3.0, which matters only when you host a modified portal.

## DepMap

- **What it holds:** genome-wide CRISPR knockout screens in cancer cell lines (Chronos gene effect and dependency probability), older RNAi data, omics (expression, mutations, copy number) and drug sensitivity. Cell lines are `ACH-` model IDs; cross-reference Cellosaurus `CVCL_` IDs for identity. Gene columns read `SYMBOL (EntrezID)`.
- **Releases:** public releases are named by quarter (for example `24Q4`) and published with a dataset DOI; the portal's download page lists files per release. Pin the release and record the DOI. File and column names change between releases (the model metadata file was renamed in the 2022-2023 restructuring), so read headers instead of hard-coding them.
- **Interpretation:**
  - A gene effect of 0 means no effect and about -1 is the median of common essential genes.
  - Separate selective dependencies from common essentials, and control for lineage, which confounds many biomarker associations.
  - Cell lines drift and are sometimes misidentified; check identity annotations.
- **Terms:** DepMap public data are CC BY 4.0; some integrated datasets carry their own terms.

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| A variant "not found" in gnomAD or ClinVar | Different build, unnormalized alleles or chromosome naming; normalize and query with the source's representation |
| Doubled ClinVar counts | Both assemblies kept from `variant_summary`; filter one |
| "Pathogenic" taken from a zero-star record | Filter on review status; inspect conflicts |
| GTEx call returns nothing for a symbol | Endpoint needs a versioned GENCODE ID for the dataset's GENCODE release |
| Mutation frequency too low in panel studies | Denominator included unprofiled samples |
| DepMap code breaks on a new release | Renamed files or columns; read headers and pin the release |

## Checks (done when)

- [ ] Variants were normalized on the stated assembly before every lookup, and the representation per source is documented.
- [ ] ClinVar results name the classification type, review status filter and dated release file.
- [ ] gnomAD results name the version and dataset, use filtering allele frequency where a frequency argument is made, and note coverage.
- [ ] GWAS results state the p-value threshold applied and do not equate mapped genes with causal genes.
- [ ] COSMIC use was checked against its license, and COSMIC files are absent from anything shared.
- [ ] cBioPortal frequencies use profiled-sample denominators and deduplicated patients.
- [ ] DepMap release name and DOI are recorded.
- [ ] No patient-derived variant was sent to a remote service without approval.
