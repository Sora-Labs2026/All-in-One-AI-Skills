# Clinical, regulatory and translational databases

Read this when a task pulls FDA adverse-event reports, labels, recalls or device data (openFDA), searches registered clinical trials (ClinicalTrials.gov), looks up pharmacogenomic gene-drug evidence and guidelines (ClinPGx with PharmGKB, CPIC and PharmCAT), ranks target-disease evidence (Open Targets Platform), or links phenotypes, diseases and genes across species (Monarch Initiative and HPO annotations). Shared rules are in `bio-data-access.md`; variant databases are in `variant-and-cancer-databases.md`.

**Guardrail.** This is general information for building software and analyzing data, not medical advice. Adverse-event counts, labels, trial listings and pharmacogenomic guidelines do not support a decision about an individual patient without a qualified clinician. Software that recommends diagnoses, treatments or doses for patients can be regulated as a medical device; flag that to the user before building it. Never fabricate patient records, keep patient data local, and follow the clinical section of `../GUIDE.md` for de-identification and HIPAA or GDPR duties.

## Which resource answers the question

| Question | Use |
|---|---|
| Adverse-event reports, product labels, recalls, NDC codes, approvals, device reports and clearances | openFDA |
| Registered trials: status, phase, interventions, eligibility, sites, posted results | ClinicalTrials.gov API v2 (other registries for non-US trials) |
| How genotype affects drug response; CPIC guidelines; allele function; pharmacogenomic labels | ClinPGx (PharmGKB, CPIC, PharmCAT) |
| Evidence that a target is associated with a disease; tractability; known drugs | Open Targets Platform |
| Genes and diseases that match a set of phenotypes; disease-phenotype annotations; model organisms | Monarch Initiative and HPO annotations |

## openFDA

- **Endpoints** under `https://api.fda.gov/`:
  - drugs: `drug/event` (FAERS adverse events), `drug/label`, `drug/ndc`, `drug/enforcement` (recalls), `drug/drugsfda`;
  - devices: `device/event` (MAUDE), `device/510k`, `device/pma`, `device/classification`, `device/recall`, `device/udi`;
  - food and veterinary: `food/enforcement`, `food/event`, `animalandveterinary/event`.

  Append `.json`.
- **Query:** `search=patient.drug.openfda.generic_name:"metformin"+AND+receivedate:[20240101+TO+20241231]`, `count=patient.reaction.reactionmeddrapt.exact` for counts of exact values, `limit` up to 1,000 and `skip` up to 25,000. For deeper result sets use the `search_after` paging the documentation describes, or the bulk files.
- **Limits:** without a key 240 requests per minute and 1,000 per day per IP; with a free key 240 per minute and 120,000 per day. Pass `api_key` from an environment variable.
- **Bulk:** `https://api.fda.gov/download.json` lists zipped JSON partitions per endpoint. Each API response's `meta.last_updated` dates the data.
- **Reading FAERS correctly:**
  - Reports are voluntary and spontaneous. There is no denominator, so counts are not incidence or risk.
  - Reporting rises after news, litigation and label changes.
  - Cases are duplicated across reporters and versions; keep the latest version per `safetyreportid`.
  - Drug names are unstandardized; the harmonized `openfda.*` fields exist only when matching succeeded, so count the unmatched rows.
  - Disproportionality measures (PRR, ROR) detect signals for review; they do not establish causation.
- **Terms:** openFDA data are public domain (CC0). Reaction terms are MedDRA preferred terms; using the MedDRA hierarchy itself requires a MedDRA subscription. Responses carry a disclaimer; keep it in user-facing outputs.

## ClinicalTrials.gov

- **API v2:** `https://clinicaltrials.gov/api/v2/studies` returns JSON or CSV.
  - Search with `query.cond`, `query.intr`, `query.term` and `query.locn`; filter with `filter.overallStatus` (for example `RECRUITING`) and `filter.advanced` (expressions such as `AREA[Phase]PHASE3`).
  - Trim with `fields`; page with `pageSize` (up to 1,000) and the returned `nextPageToken` passed back as `pageToken`; add `countTotal=true` to check completeness.
  - One study: `/studies/{nctId}`. `/version` returns the data timestamp; record it.
  - The classic API was retired in 2024, so old code fails.
- **Rate:** keep to about 50 requests per minute per IP; download with large pages instead of many small calls.
- **Data model:** `protocolSection` (identification, status, design, arms and interventions, eligibility, contacts and locations modules), `resultsSection` and `hasResults`. Enumerations are upper case (`PHASE2`, `INTERVENTIONAL`).

```python
import requests

def trials(cond, status="RECRUITING", fields="NCTId,BriefTitle,Phase,OverallStatus"):
    url, params, out = "https://clinicaltrials.gov/api/v2/studies", {
        "query.cond": cond, "filter.overallStatus": status, "fields": fields,
        "pageSize": 1000, "countTotal": "true"}, []
    while True:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("studies", []))
        token = body.get("nextPageToken")
        if not token:
            return body.get("totalCount"), out    # compare totalCount with len(out)
        params["pageToken"] = token
```

- **Caveats:**
  - Records are entered by sponsors and can be stale; the status becomes unknown when a record is not verified for two years.
  - Eligibility criteria are free text, and results posting is incomplete.
  - Search other registries (EU CTIS, ISRCTN, the WHO ICTRP portal) for non-US trials.
- **Personal data:** records name investigators and contacts. Do not harvest them for outreach or marketing.
- **Terms:** free to use under the National Library of Medicine's terms; cite NCT IDs and the data timestamp, and do not imply NLM endorsement.

## ClinPGx: PharmGKB, CPIC and PharmCAT

- **What it is:** since 2025, PharmGKB, CPIC and PharmCAT content is consolidated under ClinPGx. Existing PharmGKB accessions (`PA...` for genes, chemicals and other entities) remain.
- **What it holds:**
  - Clinical annotations with levels of evidence (1A, 1B, 2A, 2B, 3, 4), variant annotations and pathways.
  - Drug label annotations from regulators (FDA, EMA, PMDA, Health Canada).
  - CPIC guidelines, with gene-drug pairs graded A to D.
  - Allele definition, function and phenotype tables. Star-allele nomenclature for many genes is maintained by PharmVar; record which allele definition version a result used.
- **Access:** a REST API (formerly at `api.pharmgkb.org`) limited to about 2 requests per second (contact the team before heavy use), and bulk TSV downloads of annotations and relationships, which are better for analysis. Record the download date or version.
- **PharmCAT** turns a VCF into star-allele calls, phenotypes and CPIC-based recommendation text. Run it locally (Java or Docker) so patient genotypes stay on the machine; record its version and the guideline versions.
- **License:** CC BY-SA 4.0. Attribution is required, and redistributed derivative data must keep the same license.
- **Caution:** CPIC guidelines assume a confirmed genotype and a clinician applying them. A tool that outputs dosing advice for a patient is regulated territory (see the guardrail above).

## Open Targets Platform

- **What it holds:** target-disease association scores that aggregate evidence types (genetic associations including locus-to-gene, somatic mutations, known drugs from ChEMBL, pathways, expression, literature mining, animal models), plus target tractability and safety, and drug information.
- **Identifiers:** targets are Ensembl gene IDs (`ENSG00000141510`); diseases and phenotypes use EFO, MONDO, HP or Orphanet IDs written with an underscore (`EFO_0000305`); drugs are ChEMBL IDs.
- **API:** GraphQL at `https://api.platform.opentargets.org/api/v4/graphql`. Request only the fields you need, page with `page: {index, size}`, resolve names with `search(queryString: ...)`, and read the data version from the `meta` query.

```python
import requests

Q = """
query ($ensg: String!) {
  target(ensemblId: $ensg) {
    approvedSymbol
    associatedDiseases(page: {index: 0, size: 25}) {
      count
      rows { score disease { id name } }
    }
  }
}"""
r = requests.post("https://api.platform.opentargets.org/api/v4/graphql", timeout=60,
                  json={"query": Q, "variables": {"ensg": "ENSG00000141510"}})
r.raise_for_status()
data = r.json()
assert not data.get("errors"), data.get("errors")
```

- **Bulk:** every release (named `YY.MM`, for example `25.06`, roughly quarterly) publishes Parquet and JSON datasets on the EBI FTP site and in a public BigQuery dataset. Systematic analyses over many targets or diseases belong there, not in API loops. The separate Open Targets Genetics portal was folded into the Platform in 2024-2025; update code that still calls it.
- **Interpretation:**
  - Scores rank evidence within one release and change between releases.
  - Literature and well-studied genes score higher.
  - Indirect associations propagate up the disease ontology.
  - A known drug for a target is not evidence of efficacy in a new indication.
- **License:** CC0 for Platform data; cite the evidence sources when discussing their contributions.

## Monarch Initiative and HPO annotations

- **What it holds:** a knowledge graph that integrates genes, diseases (Mondo), phenotypes (HPO for human, MP for mouse, ZP for zebrafish, aligned through uPheno), orthologs, model organisms and variants from many sources, modeled with Biolink categories and predicates.
- **Access:**
  - The v3 REST API (under `https://api-v3.monarchinitiative.org/v3/api/`) covers entity lookup, search, associations filtered by category (for example disease-to-phenotype) and semantic-similarity comparisons; read its OpenAPI page for current paths.
  - The `monarch-py` client wraps the same API.
  - Release-dated knowledge-graph downloads (KGX TSV, DuckDB or SQLite, Neo4j) are on the Monarch data site.
- **Identifiers:** CURIEs such as `MONDO:0007739`, `HP:0001250`, `HGNC:11998`, `MGI:` and `ZFIN:` IDs.
- **HPO annotations** (`phenotype.hpoa`, `genes_to_phenotype.txt`) come from the HPO project's dated releases. They link diseases from OMIM, Orphanet and DECIPHER to HPO terms with frequency, onset and evidence codes. Pin the release.
- **Phenotype-driven gene ranking:**
  - Use semantic similarity over the ontology (ancestors count; specific terms weigh more), not exact term overlap.
  - For patient prioritization with sequence data, run a local tool such as Exomiser with the VCF and HPO terms, so neither leaves the machine.
  - Rankings are candidates for expert review, not diagnoses.
- **Terms:** the graph mixes sources with different licenses, some non-commercial. Check per-source license metadata before redistribution or commercial use. HPO has its own license with attribution and modification conditions, and OMIM content is licensed separately.

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| Adverse-event "rates" reported from FAERS | No denominator; report counts and disproportionality as signals only |
| Drug counts too low in openFDA | Unmatched names lack `openfda.*` fields; search raw fields too and report the unmatched share |
| Trial list incomplete | Missing pages or wrong status filter; compare with `countTotal` and check the status enum |
| Pharmacogenomic call differs between tools | Different allele definition or guideline versions; record both |
| Open Targets scores differ from last quarter | New release; pin it and compare release to release |
| Disease ID not found in Open Targets | CURIE colon form used; the API expects `EFO_0000305` |

## Checks (done when)

- [ ] Each source's data timestamp, release or version is recorded (`meta.last_updated`, `/version`, release names).
- [ ] FAERS results carry the reporting caveats, deduplicated case counts and the unmatched-name share.
- [ ] Trial searches report the query, filters, total count and retrieval date.
- [ ] ClinPGx and Monarch outputs carry their share-alike or per-source license notes.
- [ ] Nothing is presented as advice for a specific patient; dosing or diagnostic features were flagged as potentially regulated.
- [ ] Patient genotypes and phenotypes were processed with local tools only, unless the data owner approved otherwise.
