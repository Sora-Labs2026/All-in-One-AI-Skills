# Public imaging data: NCI Imaging Data Commons and other archives

Read this when a task needs public radiology or pathology images (CT, MR, PET, X-ray, slide microscopy, segmentations, annotations) for research, benchmarking or model training: finding a cohort, checking licenses, downloading reproducibly and citing the data. Reading the files is in `dicom-imaging.md` and `whole-slide-pathology.md`.

**Guardrail.** Public does not mean unrestricted. Each collection has its own license and some have use agreements. The images are de-identified by the archive, but if you find identifying information, stop using that item and report it to the archive; do not redistribute it.

## Where to look

| Archive | Access | Notes |
|---|---|---|
| NCI Imaging Data Commons (IDC) | Open, no login; `idc-index` Python package, web portal, public cloud buckets, BigQuery | Cancer imaging in DICOM, including slide microscopy, segmentations and annotations; versioned releases; per-series license |
| The Cancer Imaging Archive (TCIA) | Mostly open; some collections need a signed data use agreement | Source of many IDC collections; read each collection page for restrictions |
| OpenNeuro | Open | Neuroimaging in BIDS format (NIfTI), mostly CC0 |
| PhysioNet imaging sets (for example MIMIC-CXR) | Credentialed access: training plus a data use agreement | Terms forbid sharing and re-identification; see `ehr-modeling.md` for how the agent handles credentialed data |
| Hospital or consortium datasets | Application and agreement | Terms usually forbid commercial use and redistribution |

Prefer IDC for cancer imaging: a single index, consistent DICOM, explicit licenses and generated citations.

## IDC with idc-index

```bash
python -m pip install --upgrade idc-index        # a new data release ships as a new package version
python -c "import idc_index; print(idc_index.__version__)"
```

```python
from idc_index import IDCClient                   # older releases: from idc_index import index; index.IDCClient()

client = IDCClient()
print(client.get_idc_version())                   # record this, for example "v23"; results change between releases

cohort = client.sql_query("""
    SELECT collection_id, PatientID, StudyInstanceUID, SeriesInstanceUID,
           Modality, BodyPartExamined, series_size_MB, license_short_name, source_DOI
    FROM index
    WHERE Modality = 'CT' AND BodyPartExamined = 'CHEST'
      AND license_short_name LIKE 'CC BY %' AND license_short_name NOT LIKE '%NC%'
""")
print(len(cohort), cohort.PatientID.nunique(), round(cohort.series_size_MB.sum() / 1024, 1), "GB")
cohort.to_csv("cohort_manifest.csv", index=False)  # the manifest is the reproducible definition of the cohort
```

- `sql_query` runs DuckDB SQL over a local metadata index; it costs nothing and needs no account. List the tables and columns with `client.indices_overview` rather than guessing column names, and explore distinct values (`SELECT DISTINCT BodyPartExamined ...`) before filtering, because labels are inconsistent across collections.
- Extra indexes load on demand with `client.fetch_index(...)`: collection-level metadata (cancer types are there, not in the main index), slide microscopy, segmentations, annotations, clinical tables.
- Download from the manifest: `client.download_from_selection(seriesInstanceUID=list(cohort.SeriesInstanceUID), downloadDir="data/")`, or the `idc download` command with a manifest file. Files are named by archive UUIDs, not DICOM UIDs; read the UIDs from the headers.
- `client.citations_from_selection(seriesInstanceUID=...)` returns formatted citations for the `source_DOI` values; include them in any report or paper, along with the IDC release.
- `client.get_viewer_URL(seriesInstanceUID=...)` opens a browser viewer, useful to check a few series before downloading many.
Segmentations and slide microscopy live in their own indexes; join them back to the main index:

```python
client.fetch_index("seg_index")
segs = client.sql_query("""
    SELECT s.SeriesInstanceUID AS seg_series, s.segmented_SeriesInstanceUID AS image_series,
           i.collection_id, i.license_short_name
    FROM seg_index s JOIN index i ON s.segmented_SeriesInstanceUID = i.SeriesInstanceUID
    WHERE i.collection_id = 'nlst'
""")
client.fetch_index("sm_index")                    # slide microscopy: one row per slide series, with pixel spacing
```

Column names in these indexes have changed between releases; confirm them in `client.indices_overview` before relying on a query.

- Full DICOM metadata, including private elements, is in BigQuery public datasets. Queries are billed by bytes scanned: use a dry run to see the size, select only needed columns, and use the local index first.

## Licenses and terms

- Read `license_short_name` per series, not per collection guess. Most IDC data is CC BY (commercial use allowed with attribution); a minority is CC BY-NC (no commercial use); a few collections have custom terms.
- A model or derived dataset built from NC data inherits the restriction in practice. Keep the license column through every join and filter, and split commercial and non-commercial cohorts early if the product could become commercial.
- Attribution is a license condition, not a courtesy: cite each collection's DOI and the archive.
- TCIA and hospital datasets can require a signed agreement before download; the agent does not sign or click through agreements on the user's behalf.

## Building a sound cohort

- **Unit of analysis is the patient.** One patient can have many studies and series. Split train, validation and test by patient (`../../ml-engineering/references/evaluation-and-leakage.md`), and check that no patient appears in two collections under different IDs when collections overlap.
- **Labels have provenance.** Expert annotations, consensus reads and AI-generated segmentations sit side by side. Record which `analysis_result_id` or annotation series each label came from and do not mix AI-generated labels into a test set as if they were ground truth.
- **Acquisition differs.** Scanner vendor, protocol, slice thickness and contrast phase vary by collection. Report these per split and check performance per vendor or site.
- **Size first.** Sum `series_size_MB` before downloading; some collections are terabytes. Ask before downloads over a few gigabytes.

## Checks (done when)

- IDC release, `idc-index` version and the query text are recorded with the manifest (series UIDs, license, DOI per row).
- Downloaded instance counts match the index for every series; failures are retried and listed.
- Every series used has a license compatible with the intended use, and citations were generated and included.
- Splits are by patient; label provenance is recorded per series.
