# Chemistry, bioactivity and drug databases

Read this when a task resolves compound identities, pulls properties or synonyms, collects bioactivity or binding data for a target, looks up drug records, or builds a purchasable screening library: PubChem, ChEMBL, BindingDB, DrugBank, ZINC and UniChem. Shared rules are in `bio-data-access.md`. Structure parsing, standardization and fingerprints are in `rdkit-and-datamol.md`; filters in `medchem-filters.md`; models in `molecular-ml.md`. Regulatory drug data (labels, adverse events) is in `clinical-and-translational-databases.md`.

## Which resource answers the question

| Question | Use | License note |
|---|---|---|
| What is this compound; properties, synonyms, any deposited substance; screening assay results | PubChem | Mostly unrestricted; some depositor terms |
| Curated potency data (IC50, Ki, Kd, EC50) from papers and assays; targets; drug mechanisms and indications | ChEMBL | Share-alike |
| Measured protein-ligand binding affinities, including patent data | BindingDB | Attribution |
| Drug monographs, targets, transporters, interactions, products | DrugBank | Non-commercial without a paid license |
| Purchasable and make-on-demand compounds prepared for docking | ZINC | Free for research |
| The same compound's IDs across many databases | UniChem | Open |

## Compound identity comes first

- Standardize structures before comparing them: strip salts and solvents, neutralize, pick a canonical tautomer (RDKit `MolStandardize` or the ChEMBL structure pipeline; see `rdkit-and-datamol.md`). Keep the parent and the original form side by side (ChEMBL `molecule_hierarchy`, PubChem parent compound).
- Join on the full standard InChIKey. The first 14 characters encode connectivity only, so they group stereoisomers and some tautomers, which is useful for loose matching and wrong for identity. SMILES strings from different toolkits are not comparable as text.
- Names (trade names, salt names, abbreviations) are ambiguous. Resolve a name to an ID, then confirm the structure.
- Record whether stereochemistry is undefined, racemic or specified.

## PubChem

- **Records:** Substance `SID` (one depositor's record), Compound `CID` (a unique standardized structure), BioAssay `AID`.
- **PUG-REST:** `https://pubchem.ncbi.nlm.nih.gov/rest/pug/<input>/<operation>/<output>`:
  - `/compound/name/aspirin/cids/TXT`
  - `/compound/cid/2244/property/MolecularFormula,MolecularWeight,InChIKey/JSON`
  - `/compound/inchikey/<key>/cids/JSON`
  - `/compound/cid/2244/synonyms/JSON`
  - `/compound/fastsimilarity_2d/cid/2244/cids/JSON?Threshold=90`
  - `/assay/aid/<aid>/summary/JSON`

  Send SMILES and InChI in a POST body (`smiles=...`) to avoid URL-encoding errors with `/`, `#` and `+`. Annotations (pharmacology, safety, patents) come from PUG-View (`/rest/pug_view/data/compound/2244/JSON`).
- **Limits:** at most 5 requests per second, 400 per minute and 300 seconds of running time per minute. The `X-Throttling-Control` response header reports how close you are; exceeding the limits gets the client blocked for a while. Long searches return a `ListKey` to poll.
- **Property names change occasionally** (the SMILES properties were reorganized in 2025). Take names from the current PUG-REST property table and fail loudly on a missing key rather than writing empty columns.
- **Bulk:** `https://ftp.ncbi.nlm.nih.gov/pubchem/` has CID-SMILES, CID-InChIKey, CID-synonym and SDF files. PubChem changes continuously, so the download date is the version.
- **Clients:** `PubChemPy` is a thin wrapper and fine for simple lookups; call PUG-REST directly for anything it does not cover.
- **Assay data:** high-throughput screening actives include many false positives (aggregators, assay interference, PAINS). Treat an active outcome as a lead to confirm, and prefer dose-response AIDs.
- **Terms:** NCBI places no restrictions on PubChem data as a whole, but some depositors attach their own terms; PUG-View shows the source and license of each annotation.

## ChEMBL

- **Identifiers:** one `CHEMBL` namespace for molecules (`CHEMBL25`, aspirin), targets (`CHEMBL203`, EGFR), assays and documents. Check the entity type, not just the ID.
- **Client:** the official `chembl_webresource_client` has Django-style filters, lazy result sets and a local cache.

```python
from chembl_webresource_client.new_client import new_client

acts = (new_client.activity
        .filter(target_chembl_id="CHEMBL203", standard_type="IC50", standard_relation="=",
                pchembl_value__isnull=False, assay_type="B")
        .only(["molecule_chembl_id", "pchembl_value", "assay_chembl_id",
               "document_chembl_id", "data_validity_comment"]))
rows = list(acts)                       # executes the paged requests
```

- **REST:** `https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id=CHEMBL203&standard_type=IC50&limit=1000`, paging through `page_meta.next`; `/status` reports the release.
- **Bulk:** each numbered release (ChEMBL 35 appeared at the end of 2024) ships SQLite, PostgreSQL and MySQL dumps plus SDF files on the EBI FTP site under `chembl/ChEMBLdb/releases/`. For more than a few targets, query a local release with SQL: faster, pinned and free of rate limits.
- **Curating bioactivity:**
  - Use `pchembl_value` (negative log10 molar potency), keep `standard_relation = '='` and rows with an empty `data_validity_comment`, and drop `potential_duplicate` rows.
  - Prefer single-protein targets with assay `confidence_score` 9 (direct single protein) or 8.
  - Aggregate replicates per molecule and target (median) and record the count.
  - Do not pool Ki with IC50, or cell assays with biochemical assays, without saying so.
  - Check the target organism; rodent orthologs share gene names.
- **Drugs:** `max_phase` 4 means approved; drug mechanism and drug indication tables link molecules to targets and diseases.
- **License:** CC BY-SA 3.0. Attribution is required, and a dataset you redistribute that derives from ChEMBL must carry the same license.

## BindingDB

- **What it holds:** measured binding data (Ki, Kd, IC50, EC50) between protein targets and small molecules, from articles, patents and other databases. Compounds have BindingDB monomer IDs (`BDBM...`); targets carry UniProt accessions.
- **Access:** web services query by UniProt accession with an affinity cutoff, and monthly bulk TSV and SDF downloads (the full TSV is several gigabytes; subsets by source exist) carry the release in the file name. Prefer the TSV for analysis.
- **Pitfalls:**
  - BindingDB and ChEMBL share many source papers; deduplicate on compound, target and source document before merging.
  - Affinity columns hold strings such as `>10000`; parse the relation and the value separately.
  - Patent-derived values are less curated than article values.
  - Multi-chain targets need care when mapping to a single UniProt accession.
- **License:** downloadable under an attribution license; confirm the current terms on the download page.

## DrugBank

- **Identifiers:** `DB00945` (aspirin). Records cover drug descriptions, categories (including ATC), targets, enzymes, transporters and carriers with UniProt IDs, drug-drug interactions, pathways and products.
- **Access and license, plainly:**
  - The full database can be downloaded for non-commercial research after an approved account, under a non-commercial license (CC BY-NC 4.0 at the time of writing).
  - Any commercial use, including internal use at a company, needs a paid license, and the API is a commercial product.
  - The DrugBank vocabulary and open structure files are CC0 and are fine for ID mapping.
- **Parsing:** the XML is large; stream it with `lxml.etree.iterparse` (namespace `{http://www.drugbank.ca}`), and record the version (`5.1.x`) in the manifest.
- **Interaction data:** drug-drug interaction text supports research and software development. It is not clinical advice. Clinical decision support needs licensed, maintained content, validation and clinical review (see the clinical guardrails in `../GUIDE.md`).
- **Open alternatives:** ChEMBL drug mechanisms and indications, openFDA drug labels, DailyMed product labels, RxNorm for drug names and codes, and the IUPHAR/BPS Guide to Pharmacology for targets and ligands. Check each one's terms.

## ZINC

- **What it holds:** purchasable and make-on-demand compounds with protonation states and 3D conformers prepared for docking.
  - ZINC22 holds billions of mostly make-on-demand molecules, searched through its CartBlanche interface.
  - ZINC20 (`zinc20.docking.org`) organizes downloads into tranches by heavy-atom count, logP, charge and reactivity.
  - ZINC15 is legacy.
- **Identifiers:** ZINC15 and ZINC20 IDs are `ZINC` plus 12 digits; ZINC22 uses a different format. Treat IDs as opaque strings and keep the SMILES next to them.
- **Downloads:** the tranche browser generates download scripts for SMILES, SDF, mol2 or DOCK formats. Estimate the size first and ask before multi-gigabyte or terabyte pulls. URL-based query endpoints exist but have changed between versions; check the current site before scripting against them.
- **Purchasability changes.** Vendor catalogs in ZINC go stale and make-on-demand synthesis can fail; confirm availability and price with the vendor before ordering.
- **Terms:** free for research use; check the terms before redistributing large subsets; catalog data belongs to the vendors.

## UniChem

- Cross-references compounds across about 40 sources (ChEMBL, PubChem, DrugBank, ChEBI, ZINC, BindingDB, SureChEMBL and others) by standard InChIKey. Its REST API (version 1 since 2022) looks up a compound by InChIKey or by a source's ID and returns every source's ID. Use it to merge sources, then verify a sample of merged structures.

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| The same drug appears twice after a merge | Salt versus parent, or stereo-undefined versus defined; standardize and join on parent InChIKey |
| Potency distribution looks bimodal | Mixed activity types, units or censored values (`>`); filter relation `=` and one type |
| Similarity search returns nothing for a valid SMILES | URL-encoding broke the SMILES; POST it |
| A model looks great on ChEMBL data | Duplicates and near-duplicates across splits; deduplicate by InChIKey and split by scaffold (`molecular-ml.md`) |
| A purchased compound never arrives | Stale ZINC vendor data; confirm with the vendor |

## Checks (done when)

- [ ] Structures were standardized, the pipeline is stated and joins use InChIKeys; counts in and out are reported.
- [ ] Bioactivity filters (types, relation, validity, confidence, organism) and replicate aggregation are documented.
- [ ] PubChem stayed within its limits; ChEMBL and BindingDB releases are recorded.
- [ ] DrugBank use matches its license, and any commercial use was flagged to the user.
- [ ] No interaction or label content is presented as clinical advice.
