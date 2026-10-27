# Life Sciences

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Analyze biological and chemical data with the standard open-source libraries so the result can be reproduced, defended and handed to a scientist for review. The module covers sequences, alignments, variants, genomic intervals and coverage tracks; single-cell and bulk transcriptomics, RNA velocity and gene regulatory networks; phylogenetics and microbial diversity; protein language models and docking; cheminformatics, medicinal-chemistry filters and molecular machine learning; mass spectrometry; metabolic models, glycosylation and flow cytometry files; and data provenance. Each topic has one focused reference. Read only the ones the task touches.

**How the work is done** (done-when checks, planning, test-first, debugging, verification) lives in `../engineering-workflow/GUIDE.md`. Model evaluation, splits, leakage and statistics live in `../ml-engineering/GUIDE.md`. Numerical methods, simulation, molecular dynamics and cluster jobs live in `../scientific-computing/GUIDE.md`. Data wrangling, storage formats and plotting live in `../data-engineering/GUIDE.md`. This module does not repeat them.

## When to activate

- The input is a biological or chemical file or identifier: FASTA, FASTQ, GenBank, SAM, BAM, CRAM, VCF, BCF, BED, bigWig, GTF, h5ad, loom, mzML, MGF, SDF, SMILES, SBML, Newick, BIOM, FCS, PDB or mmCIF.
- The user asks for a bioinformatics, genomics, transcriptomics, single-cell, phylogenetic, microbiome, proteomics, metabolomics, cheminformatics or drug-discovery analysis, or for code that performs one.
- An application ingests, stores or serves such data and needs the library behavior right (coordinates, formats, licenses).
- The input is a DICOM file or series, a whole-slide image, a physiological signal (ECG, PPG, EDA, EEG or EMG file, EDF or WFDB), a spike-sorting recording (SpikeGLX, Open Ephys, NWB), an EHR extract or a wearable export; or the user asks for a query of a public biological, chemical or clinical database, a clinical document draft, a medical-device quality document, a lab-robot protocol or an ELN integration.
- **Not for** general statistics or ML without a biological or chemical data type (`../ml-engineering/GUIDE.md`), simulation and molecular dynamics (`../scientific-computing/GUIDE.md`), or charts alone (`../data-engineering/GUIDE.md`).

## Ground rules

1. **Research output, not clinical advice.** Results from this module are exploratory research output. Never present a variant interpretation, expression signature, docking score or model prediction as a diagnosis, treatment recommendation or safety claim about a person or a drug. Say what a qualified scientist or clinician must confirm, and keep that caveat in reports and user interfaces.
2. **Pin the reference.** Record the genome build (for example GRCh38), the annotation source and release (for example Ensembl 112 or GENCODE 46), the chromosome naming style (`chr1` or `1`) and the coordinate convention of every file. Never mix builds; convert with a liftover tool and report what failed to lift.
3. **Know the coordinate convention.** BED, BAM internals, pysam and most Python APIs are 0-based half-open. VCF, GFF, GTF, SAM text and region strings such as `chr1:1000-2000` are 1-based and closed. Convert once, at the boundary, and test the conversion on a known feature. Run `scripts/interval_check.py` on interval files before joining them.
4. **Check versions, not memory.** These libraries change APIs between releases (Scanpy, AnnData, scvi-tools, RDKit, pyOpenMS, ETE, scikit-bio, ESM, CELLxGENE Census). Read the installed version (`python -c "import pkg; print(pkg.__version__)"`) before writing code, and state the version you assumed when you cannot check.
5. **Record everything a rerun needs.** Tool and library versions, reference files with checksums, parameters, random seeds, database or atlas release, and the exact command. Seed every stochastic step (UMAP, Leiden, scVI, network inference, splits, sampling) and say which results still vary between runs, such as GPU nondeterminism.
6. **Raw data is read-only.** Never modify input files in place. Write outputs under new names, keep raw counts next to normalized values, and keep an untouched copy of the original download.
7. **Size first.** Estimate memory before loading: cells times genes, reads, spectra, molecules. Prefer indexed random access, backed or streamed reads, sparse matrices and chunked processing over loading whole files. Ask before downloads over a few gigabytes, GPU jobs or long cluster runs.
8. **Licenses and terms count.** Check the license of tools (several are GPL, which matters when they ship inside a product), model weights (some are non-commercial or gated), datasets and spectral or chemical libraries (some need a paid license for commercial use), and web prediction servers (several are free for academic use only). Record them in the report.
9. **Data leaves the machine only with permission.** Human sequence, variant, expression and cytometry data can identify people. Do not send it to remote services (web BLAST, hosted models, prediction servers, LLM APIs) without the owner's permission and a check of the service's terms. Never fabricate samples or records. De-identification and HIPAA or GDPR duties are covered in the clinical section below.
10. **Dual use.** Help with research and engineering, but do not help design or enhance pathogens, toxins or other agents of harm, and do not plan to evade biosafety screening. Generated sequences and molecules are hypotheses that need expert and institutional review before any synthesis.
11. **Report only what ran.** Every number in a report comes from a command that ran in this session or a cited, verified source. Checks that did not run are `NOT VERIFIED` with the reason. Never invent accessions, citations, benchmark scores or results.

## Workflow

1. **Frame:** the biological question, the unit of replication (donor, animal, culture, plate), the comparison, and what result would change a decision.
2. **Inspect inputs:** file formats, build, naming style, coordinate convention, raw versus normalized values, sample sheet. Run `scripts/interval_check.py` and `scripts/counts_check.py` where they apply.
3. **Dry run on a subset:** one chromosome, a thousand cells, a hundred molecules. Confirm shapes, units and a known positive control before the full run.
4. **Full run:** record versions, parameters and seeds as you go (`references/data-provenance.md`).
5. **Verify:** compare against a positive and a negative control, a published or known result, or a simpler method. Look at the diagnostic plots the reference names.
6. **Report:** results with uncertainty, the caveats from rule 1, and what remains `NOT VERIFIED`.

## Pick the references

### Sequences and genomics

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| FASTA, FASTQ, GenBank parsing, translation, pairwise alignment, NCBI Entrez, BLAST, PDB parsing with Biopython | `references/biopython.md` | Record counts in and out match; Entrez calls identified and rate-limited; BLAST database and version recorded |
| SAM, BAM, CRAM, VCF, BCF with pysam, samtools or bcftools; variant stores for large cohorts (TileDB-VCF) | `references/reads-and-variants.md` | Indexes present; flags and MAPQ filters stated; a region spot-checked against `samtools view` or `bcftools view` |
| BED and other interval files, overlaps, liftover, region tokens and embeddings | `references/genomic-intervals.md` | `interval_check.py` clean against the genome's sizes file; one overlap verified by hand |
| BAM to bigWig, normalization, signal heatmaps, ChIP, ATAC or CUT&RUN quality control with deepTools | `references/deeptools-coverage.md` | Same normalization across samples; fingerprint and correlation plots reviewed; genome size matches build |
| Quick gene, sequence, structure or enrichment lookups with gget | `references/gget.md` | Database release recorded; results saved to files; nothing sensitive sent to remote services |

### Single-cell

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| AnnData objects, h5ad and zarr files, layers, views, concatenation, backed mode | `references/anndata.md` | Raw counts preserved in a layer; obs and var indexes unique; file reopens with the same shape |
| Single-cell RNA-seq with Scanpy: QC, doublets, normalization, clustering, markers, annotation | `references/scanpy.md` | QC thresholds justified per sample; doublets handled; markers checked against known biology; condition effects tested on pseudobulk |
| Integration, reference mapping, multimodal or probabilistic models with scvi-tools | `references/scvi-tools.md` | Model trained on raw counts; training curves converged; integration scored for both batch mixing and biology |
| RNA velocity with scVelo | `references/rna-velocity.md` | Spliced and unspliced layers verified; velocity direction checked against known differentiation |
| CELLxGENE Census queries and atlas-scale data | `references/cellxgene-census.md` | Census version pinned; `is_primary_data` filter applied; query size estimated before loading |

### Expression and networks

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Bulk RNA-seq differential expression with PyDESeq2, pseudobulk from single cells | `references/bulk-rnaseq-deseq2.md` | `counts_check.py` clean; design full rank; reference level explicit; PCA, dispersion and p-value histogram reviewed |
| Gene regulatory network inference (GRNBoost2, GENIE3, regulons) | `references/gene-regulatory-networks.md` | TF list and seeds recorded; edges stable across seeds; spot-checked against known regulation |

### Evolution and diversity

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Multiple alignment, tree inference, rooting, support values, tree handling with the ETE toolkit | `references/phylogenetics.md` | Alignment inspected; model selection and support method reported; root justified |
| Microbiome and community ecology with scikit-bio: diversity, UniFrac, ordination, PERMANOVA | `references/microbiome-scikit-bio.md` | Depth normalization stated; tree tips match feature IDs; PERMANOVA paired with a dispersion test |

### Data management

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Provenance, versioned datasets, validated metadata, LaminDB-style lineage | `references/data-provenance.md` | Every output links to its inputs, code version, parameters and environment; checksums recorded |

### Proteins and structure

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Protein language models (ESM family): embeddings, variant scoring, sequence generation | `references/protein-language-models.md` | Weights license checked; special tokens excluded from pooling; a simple baseline compared |
| Protein-ligand docking with DiffDock and classical tools | `references/docking.md` | Redocking a known ligand reproduces its pose; poses pass physical validity checks; confidence not reported as affinity |

### Cheminformatics

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Parsing, standardizing, fingerprints, similarity, substructures, conformers with RDKit or datamol | `references/rdkit-and-datamol.md` | Parse failures counted; standardization pipeline stated; duplicates removed by InChIKey |
| Drug-likeness rules, structural alerts, PAINS, compound triage | `references/medchem-filters.md` | Pass and fail counts per filter reported; known drugs or actives run as a sanity check |
| Molecular featurization and property models (molfeat, DeepChem, TorchDrug, Therapeutics Data Commons) | `references/molecular-ml.md` | Scaffold or cluster split; fingerprint plus gradient boosting baseline; spread over seeds; dataset license recorded |

### Mass spectrometry

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Spectral library matching with matchms; LC-MS processing, features and identifications with pyOpenMS | `references/mass-spectrometry.md` | Tolerances and minimum matched peaks stated; identifications at a controlled FDR or with a stated confidence level |

### Other

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Genome-scale metabolic models with COBRApy: FBA, FVA, knockouts, media | `references/metabolic-modeling.md` | Model validated; medium stated; solver and status recorded; results checked against known growth |
| N- and O-glycosylation sites, glycan notation, glycoengineering choices | `references/glycoengineering.md` | Sequons found with overlap-aware search; predictions labeled as predictions; server terms checked |
| FCS flow cytometry files: reading, channels, compensation, transforms | `references/flow-cytometry-files.md` | Compensation source stated; transform and cofactor recorded; identifying keywords removed before sharing |

Several references often apply together. A single-cell study touches `anndata`, `scanpy`, `scvi-tools` and `bulk-rnaseq-deseq2` (pseudobulk). A screening campaign touches `rdkit-and-datamol`, `medchem-filters`, `molecular-ml` and `docking`.

## Public databases and ontologies

Read `references/bio-data-access.md` first for any database work (access route, identifiers and mapping, polite clients, snapshots, licenses, citation); each topic reference groups databases by the question they answer.

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Any query, download or join of public databases; identifier mapping; release pinning; data licenses and citation | `references/bio-data-access.md` | Release, access date, query and checksums in a manifest; mapping counts reported; each source's license checked against the intended use |
| NCBI Gene, RefSeq and Datasets; Ensembl REST, VEP, BioMart and FTP; ENA and SRA reads; GEO series; JASPAR motifs | `references/sequence-and-genome-databases.md` | Ensembl, RefSeq or MANE release and assembly recorded; discontinued IDs handled; read files pass MD5; patient variants annotated with local VEP |
| ClinVar, gnomAD, GWAS Catalog, GTEx, COSMIC, cBioPortal, DepMap | `references/variant-and-cancer-databases.md` | Variants normalized on the stated build; ClinVar classification type, review status and dated file; gnomAD version and filtering allele frequency; COSMIC license checked; profiled-sample denominators |
| UniProt, InterPro and Pfam, PDB, AlphaFold DB, STRING | `references/protein-and-structure-databases.md` | Release recorded; accessions, not entry names; structure quality, assembly and chain IDs reviewed; predicted models labelled with pLDDT and PAE; STRING version, cutoff and background stated |
| Reactome, KEGG, HMDB, Metabolomics Workbench, BRENDA; pathway enrichment | `references/pathway-and-metabolism-databases.md` | Pathway release, ID type, background and unmapped count reported; KEGG and HMDB terms checked against the use; kinetic values carry organism, conditions and source |
| PubChem, ChEMBL, BindingDB, DrugBank, ZINC, UniChem | `references/chemistry-and-drug-databases.md` | Structures standardized and joined on InChIKey; activity filters documented; releases recorded; DrugBank license matches the use |
| openFDA, ClinicalTrials.gov, ClinPGx (PharmGKB, CPIC, PharmCAT), Open Targets Platform, Monarch and HPO annotations | `references/clinical-and-translational-databases.md` | Data timestamps recorded; FAERS caveats and case deduplication; trial totals checked; nothing presented as advice for a patient; dosing or diagnostic features flagged as possibly regulated |
| Ontology term lookup (OLS, BioPortal, OAK), mapping (SSSOM), annotation validation (SHACL, LinkML), OWL or OBO parsing, ROBOT checks | `references/biomedical-ontologies.md` | Ontology versions named; IDs current, non-obsolete and in the expected branch; mappings stored with predicates and justifications; ROBOT reason and report clean for authored ontologies |

## Clinical data, imaging and the lab

**Clinical guardrail.** Everything in this section is general information for building software and analyzing data. It is not medical advice and never a diagnosis, prognosis or treatment decision for a person. Clinical documents (reports, notes, case reports, trial documents, evidence summaries, recommendations, pathways, treatment plans) are drafts for a qualified clinician to review, correct and sign: label them as drafts, trace every clinical fact to a source record the user supplied, leave clinical judgments and missing facts as visible placeholders, give each recommendation an evidence level in one named grading system, and cite only sources you have looked up and confirmed exist. Never fabricate patient data, including in examples and tests; use generated synthetic data and label it synthetic. Before clinical data is shared, published, used for training or shown to any hosted service, de-identify it under the frame the data owner names: HIPAA Safe Harbor (all 18 identifier kinds removed, no actual knowledge of re-identification) or Expert Determination (a documented expert finding of very small risk); a limited data set is still protected health information. Under GDPR and UK GDPR, health data is special-category data and pseudonymised data is still personal data. Run code where the data lives and print only schemas, counts and aggregates into the conversation. Software that diagnoses, treats, predicts or recommends for patients may be a medical device (software as a medical device): raise it early and read `references/medical-device-quality.md` for the regulatory pointers (FDA's clinical decision support criteria, EU MDR Rule 11, IEC 62304, ISO 14971, the EU AI Act). Lab hardware follows the same caution: simulate or dry-run first, show the deck and plan, and run anything physical, or submit any paid cloud-lab order, only after the user's explicit go-ahead.

### Imaging and microscopy

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| DICOM files with pydicom: headers, pixel values (HU, windows, color), series to volumes, NIfTI, derived SEG and SR objects, PACS and DICOMweb | `references/dicom-imaging.md` | Modality transform applied once; spacing, direction and left-right checked in a viewer; derived objects reference the right series; nothing written to a clinical archive |
| De-identifying DICOM, EHR tables, notes or signals; HIPAA Safe Harbor or Expert Determination; GDPR pseudonymisation; pseudonyms, date shifting, crosswalks | `references/clinical-deidentification.md` | Frame and sign-off named; `dicom_phi_check.py` has no HIGH findings and every WARN is fixed or allowed with a reason; pixels and file names reviewed |
| Public imaging data: NCI Imaging Data Commons with idc-index, TCIA, cohort selection, licenses and citations | `references/public-imaging-data.md` | Release, query and manifest saved; per-series license fits the use; citations generated; patient-level splits |
| Whole-slide images: OpenSlide and other readers, tissue masks, tiling at fixed MPP, stain normalization, tile QC (histolab, TIAToolbox, PathML) | `references/whole-slide-pathology.md` | MPP recorded per slide; masks and tile grids inspected on thumbnails; patient-level splits with site held out; label and macro images stripped before sharing |
| OMERO image servers: connection, planes and tiles, ROIs, annotations, tables, scripts | `references/microscopy-image-servers.md` | Least-privileged account; z, c, t order right; writes namespaced and read back; nothing deleted without approval of the exact list |

### Signals and health records

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| ECG, PPG, HRV, EDA, respiration, EMG or EOG with NeuroKit2; event-related physiology | `references/physiological-signals.md` | Sampling rate verified from timestamps; peaks inspected; corrected beats reported; HRV duration rules respected; detector validated or `NOT VERIFIED` |
| Neuropixels and other probe recordings: SpikeInterface preprocessing, drift, Kilosort 4, quality metrics, curation, NWB export | `references/spike-sorting.md` | Drift corrected once and reviewed; versions and parameters saved; curation thresholds fixed in advance with counts; pipeline checked on ground-truth data |
| Models on EHR data (MIMIC, eICU, OMOP, PyHealth): cohorts, index time, code systems, leakage, evaluation | `references/ehr-modeling.md` | Data use terms respected; index time and leakage review written; patient-level split checked; calibration and subgroup results with intervals |

### Clinical documents and quality systems

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Drafts of case reports, imaging, pathology and lab reports, clinical notes, discharge summaries, CSR sections, SAE narratives | `references/clinical-documentation.md` | Draft label and blank review block; source map complete; no invented findings, grades or doses; citations looked up |
| Evidence summaries, graded recommendations, cohort analyses, decision pathways, individual treatment-plan drafts | `references/clinical-decision-documents.md` | Each recommendation has a verified citation and a grade in one named system; numbers trace to data or source; pathway branches tested; clinical choices left to the clinician |
| ISO 13485 QMS, FDA QMSR, EU MDR, IEC 62304, ISO 14971, software as a medical device questions | `references/medical-device-quality.md` | Scope confirmed; gap table with evidence and owners; placeholders for company facts; no compliance or certification claims |

### Lab automation and lab data

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Opentrons protocols, PyLabRobot, other liquid handlers and instruments, cloud-lab protocol APIs | `references/lab-automation.md` | Simulation log read; deck map handed over; explicit go-ahead before any physical run or paid order; water run checked before samples |
| Benchling, DNAnexus, LabArchives, protocols.io and hosted workflow platforms; ELN and registry writes; compute jobs | `references/lab-data-platforms.md` | Dry-run plan approved; writes read back and idempotent; no signed record edited or deleted; job cost estimated and approved |
| Wearable, phone and consumer health data: exports, vendor OAuth APIs, normalization, FHIR mapping, privacy duties | `references/consumer-health-data.md` | Import report with types, sources, duplicates and units; DST and travel days spot-checked; minimal scopes; no diagnostic language |

## Cross-cutting essentials

Use these when no reference is needed; open the reference when a bullet raises a question.

### Coordinates, builds and identifiers
- Convert a 1-based closed region to BED with `start - 1, end`; convert BED back with `start + 1, end`. `scripts/interval_check.py convert` prints both forms.
- Chromosome names must match exactly between files (`chr1` against `1`, `chrM` against `MT`). Rename with an explicit mapping table, never with a regex guess.
- Gene symbols change and collide; join on stable identifiers (Ensembl gene IDs without the version suffix, UniProt accessions, InChIKeys) and keep the symbol as a label.
- Check identifier lists with `scripts/bio_id_check.py` before batch queries: it flags zero-stripped ontology IDs (`GO:6915`), unversioned transcripts, HGVS prefixes that do not fit the reference, spreadsheet-damaged symbols (`1-Mar`) and lists mixing versioned and unversioned IDs.

### Statistics that bite in biology
- The replicate is the independent unit (donor, animal, culture), not the cell, read or well. Tests across cells from a few donors are pseudoreplication; aggregate first.
- Thousands of genes, peaks or features mean multiple testing. Report adjusted p-values (Benjamini-Hochberg unless the method defines its own) and effect sizes.
- Batch confounded with condition cannot be corrected afterwards. Check the design before analysis and say so plainly when it is confounded. Details in `../ml-engineering/references/statistical-inference.md`.

### Size and memory
- A dense float32 matrix needs 4 bytes per value: one million cells by 30,000 genes is 120 GB dense; keep it sparse.
- Index before random access (`.bai`, `.csi`, `.tbi`, `.fai`) and stream sequentially otherwise. Use backed AnnData, Census `axis_query`, chunked readers and Dask (`../data-engineering/references/dask-and-out-of-core.md`) for data larger than memory.

## Helper scripts

All are Python 3 standard library only, read only their inputs, never use the network and print deterministic output. Exit codes: 0 no errors, 1 errors found (or warnings with `--strict`), 2 bad input or usage. Each has `--help` and `--json`.

```bash
# Interval files: bounds, sort order, naming style, zero-length and duplicate intervals; against a sizes file: unknown contigs and coordinates past the end
python3 <productcraft>/modules/life-sciences/scripts/interval_check.py check peaks.bed genes.gtf --genome hg38.chrom.sizes
python3 <productcraft>/modules/life-sciences/scripts/interval_check.py convert chr1:1000-2000 --from one-based

# Bulk count matrix and sample sheet before differential expression
python3 <productcraft>/modules/life-sciences/scripts/counts_check.py --counts counts.tsv --samples samples.tsv --design batch,condition

# Identifiers: classify, or validate against one type, before batch queries and joins
python3 <productcraft>/modules/life-sciences/scripts/bio_id_check.py P04637 NM_000546 GO:6915 1-Mar
python3 <productcraft>/modules/life-sciences/scripts/bio_id_check.py --type ensembl --file genes.tsv --column 2 --skip-header --json

# DICOM headers after de-identification: identifiers, dates, free text, private tags, UIDs, burned-in and face flags; values hidden
python3 <productcraft>/modules/life-sciences/scripts/dicom_phi_check.py --uid-root 2.25 --strict deid_out/
```

`<productcraft>` is the folder where the ProductCraft skill is installed. A clean result does not prove the build is right or the design is sound: `interval_check.py` only knows the sizes file it is given, and `counts_check.py` cannot see hidden batch structure. `bio_id_check.py` checks shape only: an identifier that passes may not exist or may be obsolete, and an HGVS expression that passes still needs validation against its reference sequence. A clean `dicom_phi_check.py` run is header evidence only: it does not inspect pixels, slide label images, embedded documents or file names, and its exit code 2 also covers "no DICOM files found". Tests: `python3 -B -m unittest discover -s <productcraft>/modules/life-sciences/tests -v`.

## What to report

Add these to the workflow module's report and `../../assets/review-template.md`:
- The question, the unit of replication and the comparison.
- Inputs with build, annotation release, naming style, convention and checksums; database and atlas releases with access dates.
- Tool and library versions, parameters, seeds and the commands that ran.
- Results with uncertainty (adjusted p-values, confidence intervals, support values, spread over seeds) and the controls that were checked.
- Licenses of tools, weights, datasets and services used, and any data sent off the machine with the owner's permission.
- For clinical work: the de-identification frame and checks run, the draft label and review status of documents, and the evidence system used for each recommendation. For lab hardware: the simulation result and the user's go-ahead.
- The research-output caveat from rule 1, and everything left `NOT VERIFIED` with the reason.

## Working with other ProductCraft modules

- `../engineering-workflow/GUIDE.md`: tracks, done-when checks, debugging and verification for analysis code and pipelines.
- `../ml-engineering/GUIDE.md`: splits, leakage, baselines, statistical tests and model comparison; `../ml-engineering/references/graph-neural-networks.md` and `../ml-engineering/references/transformers.md` for model internals.
- `../scientific-computing/GUIDE.md`: molecular dynamics, numerical methods, HPC and job scripts.
- `../data-engineering/GUIDE.md`: data wrangling, Parquet and Zarr storage, plotting and publication figures.
- `../research-writing/GUIDE.md`: methods sections, verified citations and study design.
- `../agent-safety/GUIDE.md`: API keys for NCBI and other services by name only, never in code or chat.
- `../legal-ready/GUIDE.md`: personal and health data duties and dataset or model licenses inside a product.
- `../cloud-infrastructure/GUIDE.md`: GPU and batch infrastructure; plan and estimate cost before running anything.
- `../documents/GUIDE.md`: Word and PDF output of clinical drafts and reports.
- `../integrations/GUIDE.md`: OAuth, webhooks and rate limits for lab platforms and health-data APIs.
