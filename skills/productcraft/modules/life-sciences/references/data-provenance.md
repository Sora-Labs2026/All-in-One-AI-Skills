# Data provenance for biological analyses

Read this when an analysis must be rerun, reviewed, shared or audited: versioning datasets, recording which code and parameters produced which outputs, validating sample metadata against ontologies, or setting up a lineage system such as LaminDB. ML experiment tracking and model registries are in `../../ml-engineering/references/mlops.md`; storage formats in `../../data-engineering/references/storage-formats-and-zarr.md`.

## The minimum record

For every output that leaves your hands (a table, a figure, an h5ad file, a model), someone must be able to answer:

| Question | Record |
|---|---|
| Which inputs? | Path or URI, accession with version, download date, SHA-256 checksum |
| Which reference? | Genome build, annotation release, database or atlas release |
| Which code? | Repository and commit (and whether the tree had uncommitted changes) |
| Which environment? | Lockfile or environment file, container image digest, key library versions |
| Which settings? | Parameters, thresholds, random seeds, command line |
| When and by whom? | Timestamp, operator, machine or cluster job ID |
| Which outputs? | Paths and checksums |

Small projects can keep this as a manifest file next to the outputs. Larger ones need a system; the record is the same either way.

## Practices

1. **Immutable raw data.** Keep downloaded and instrument files in a read-only area. Everything else is derived and can be regenerated.
2. **Checksums at the boundaries.** Hash files when they arrive and when they are produced. A changed checksum on an input explains a changed result.
3. **Identify by content or stable key, not by file name.** `final_v2_fixed.h5ad` says nothing. Use structured keys (`project/assay/sample/stage`) plus versions.
4. **Metadata with controlled vocabularies.** Use ontology terms for cell types (Cell Ontology), tissues (UBERON), diseases (MONDO), organisms (NCBI Taxonomy) and assays (EFO), with term IDs, not only labels. Validate sample sheets before analysis: required columns, allowed values, units, no duplicates.
5. **One sample sheet as the source of truth.** Every pipeline step reads it; no step keeps its own copy with edits.
6. **Separate identifying data.** Keep names, medical record numbers and dates of birth out of analysis metadata; link through a coded ID held elsewhere under access control. The clinical section of `../GUIDE.md` covers de-identification duties.
7. **Rerun to prove it.** Provenance is verified when a fresh run from the record reproduces the outputs (identical checksums, or agreement within stated tolerance for steps that are not bit-reproducible).

## A manifest with the standard library

```python
import hashlib, json, pathlib, platform, subprocess, sys
from datetime import datetime, timezone

def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()

def git_state():
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return {"commit": commit, "dirty": dirty}

def write_manifest(inputs, outputs, params, out="manifest.json"):
    record = {
        "created": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "code": git_state(), "params": params,
        "inputs": {str(p): sha256(p) for p in map(pathlib.Path, inputs)},
        "outputs": {str(p): sha256(p) for p in map(pathlib.Path, outputs)},
    }
    pathlib.Path(out).write_text(json.dumps(record, indent=2, sort_keys=True))
```

Add library versions (`importlib.metadata.version(name)` for each key package) and the reference releases to `params`.

## Choosing a system

| Need | Option |
|---|---|
| Single analyst, small data | Git for code, manifest files, an environment lockfile |
| Data versions tied to git commits | DVC or a similar data-versioning tool with remote storage |
| Pipelines with many steps and samples | A workflow manager (Nextflow, Snakemake) with pinned containers; its run reports and traces are part of the record |
| Queryable registry of datasets, lineage across notebooks and pipelines, ontology-validated metadata | LaminDB, or a comparable data catalog |

## LaminDB in brief

LaminDB is an open-source (Apache-2.0) Python framework that keeps a registry of artifacts (files and in-memory objects such as DataFrames and AnnData), the transforms (notebooks, scripts, pipeline steps) and runs that produced them, and features and labels that annotate them. Its companion ontology registries back metadata validation.

```python
import lamindb as ln

ln.track()                                            # registers this script or notebook as a run
raw = ln.Artifact.get(key="projectA/scrna/raw/donor1.h5ad")
adata = raw.load()
# ... analysis ...
ln.Artifact.from_anndata(adata, key="projectA/scrna/qc/donor1.h5ad",
                         description="QC-filtered, doublets removed").save()
ln.finish()                                           # closes the run; outputs now link to inputs and code
```

- **Curate before saving:** validate a DataFrame or AnnData against a schema with the curator classes, standardize synonyms to ontology terms, and only then save. Validation errors are data problems to fix, not warnings to silence.
- **Instances:** a local SQLite database with local storage suits one person; a shared PostgreSQL database with object storage suits teams. Some setups register the instance with the vendor's hosted service; check what metadata leaves your infrastructure, and keep sensitive projects on self-managed databases and storage.
- **API churn:** the API changed substantially between major versions (registry names, curation classes, tracking calls). Check `lamindb.__version__` and that version's documentation; do not copy examples across versions.
- Credentials for databases and buckets come from the environment or the platform's credential store, never from notebooks (`../../agent-safety/GUIDE.md`).

## Sharing and deposition

- Deposit raw data and processed matrices in the repository the community expects: GEO, SRA or ENA for sequencing; PRIDE for proteomics; MetaboLights or the Metabolomics Workbench for metabolomics; general repositories such as Zenodo for code and derived files, with a DOI.
- Human sequence and genotype data generally needs controlled-access repositories (for example dbGaP or EGA) and consent that allows sharing; ask the data owner before preparing any submission.
- Include the provenance record and the sample sheet with ontology IDs; they are what makes the deposit reusable.

## Checks (done when)

- [ ] Every delivered output can be traced to inputs with checksums, references, code commit, environment, parameters and seeds.
- [ ] Raw inputs are untouched; derived files are regenerable from the record.
- [ ] Sample metadata validated against required fields and ontology terms, with identifying data kept apart.
- [ ] A rerun from the record reproduced at least one key output.
