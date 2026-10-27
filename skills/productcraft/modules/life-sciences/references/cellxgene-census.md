# Atlas-scale single-cell data with CELLxGENE Census

Read this when you need expression or metadata for many cells across public single-cell datasets: cells of one type across tissues, a gene across diseases, a reference for annotation, or training data for a model. Your own data goes through `scanpy.md`; the object format is in `anndata.md`.

## What it is

The Census is a versioned, harmonized collection of public human and mouse single-cell datasets, stored as TileDB-SOMA arrays and read through the `cellxgene_census` package. Metadata uses ontology terms (Cell Ontology, UBERON, MONDO, EFO assays). Cells are streamed from cloud object storage, so query size is what decides speed and memory.

## Setup

```bash
python -m pip install cellxgene-census
python -c "import cellxgene_census as cc; print(cc.__version__)"
```

## Pin the release

```python
import cellxgene_census as cc

releases = cc.get_census_version_directory()      # lists releases, including long-term-supported ones
with cc.open_soma(census_version="<LTS release name from the directory>") as census:
    ...
```

- Always pass `census_version`. The default ("stable") moves, and results change when datasets are added or re-curated.
- Prefer long-term-supported releases for anything that will be cited or rerun.
- Record the release name and the package version in the report.

## Explore metadata before expression

```python
with cc.open_soma(census_version=VERSION) as census:
    obs = cc.get_obs(
        census, "homo_sapiens",
        value_filter="tissue_general == 'lung' and is_primary_data == True",
        column_names=["dataset_id", "donor_id", "assay", "cell_type",
                      "cell_type_ontology_term_id", "disease", "suspension_type"],
    )
print(len(obs), "cells")
print(obs.groupby(["assay", "suspension_type"]).size())
```

- **`is_primary_data == True`** keeps one copy of each cell. The same cells appear in several datasets (an atlas and its source studies); without the filter, counts and statistics double-count.
- **Estimate size first.** Cells times genes, and whether it fits in memory, before calling `get_anndata`. A whole tissue can be millions of cells.
- **Filter by ontology IDs** (`cell_type_ontology_term_id`) rather than labels when precision matters; labels are human-readable and can be ambiguous.
- **Donors are nested in datasets.** `donor_id` is only unique within a `dataset_id`; build a combined key before treating donors as replicates.

## Get expression

```python
with cc.open_soma(census_version=VERSION) as census:
    adata = cc.get_anndata(
        census, organism="Homo sapiens",
        obs_value_filter="cell_type_ontology_term_id == 'CL:0000235' and is_primary_data == True",
        var_value_filter="feature_name in ['CD68', 'MARCO', 'APOE']",
        obs_column_names=["dataset_id", "donor_id", "assay", "tissue_general", "disease"],
        X_name="raw",
    )
```

- `X_name="raw"` gives counts as submitted; normalized layers are library-size scaled. Run your own normalization on counts, consistently.
- **Absent is not zero.** Each dataset measured its own gene set. A gene missing from a dataset's panel shows up as zero. Use the presence matrix (`cc.get_presence_matrix`) to restrict comparisons to datasets that measured the gene.
- **Assays differ.** Full-length plate methods and droplet UMI methods have different count distributions; cells and nuclei differ too. Stratify by `assay` and `suspension_type`, or include them as batch variables.
- Restrict genes with `var_value_filter` whenever the question allows; it shrinks downloads by orders of magnitude.

## Larger than memory

```python
import tiledbsoma as soma

with cc.open_soma(census_version=VERSION) as census:
    exp = census["census_data"]["homo_sapiens"]
    with exp.axis_query(
        measurement_name="RNA",
        obs_query=soma.AxisQuery(value_filter="tissue_general == 'brain' and is_primary_data == True"),
        var_query=soma.AxisQuery(value_filter="feature_name in ['GFAP', 'AQP4']"),
    ) as query:
        for tbl in query.X("raw").tables():           # Arrow tables of (cell, gene, value) triples
            accumulate(tbl)                           # running sums, counts, histograms
```

- Accumulate statistics incrementally (sums and counts per group, then divide). Zeros are not stored; count cells from `obs`, not from the triples, when computing means.
- Model training on the Census: the data loaders that once lived under `cellxgene_census.experimental.ml` have moved to a separate TileDB-SOMA machine-learning package in recent releases; check which one the installed version supports.
- Run large queries near the data (the same cloud region as the public bucket) when possible; across the internet they are slow.

## Use as a reference

- Building a reference for label transfer: sample per dataset and donor, not just per cell, so one huge study does not dominate. Keep the dataset and donor columns for batch handling (`scvi-tools.md`).
- Pre-computed embeddings and models are published for some releases; check the release documentation, and record exactly which one you used.

## Licenses and citation

Datasets come from many studies, each with its own citation and generally an attribution license. The datasets table (`census["census_info"]["datasets"]`) holds collection names, DOIs and citations; cite every dataset that contributed cells to a result, and check the license before redistributing data.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Duplicate cells inflate counts | `is_primary_data == True` |
| Results change between runs | Pin `census_version` |
| Gene "not expressed" in a dataset that never measured it | Presence matrix |
| Mixed assays compared directly | Stratify or model assay and suspension type |
| Donors from different studies merged by `donor_id` | Combine with `dataset_id` |
| Out of memory | Estimate with `get_obs`; restrict genes; stream with `axis_query` |

## Checks (done when)

- [ ] Release name and package version recorded.
- [ ] `is_primary_data` filter applied, and query size estimated before loading.
- [ ] Gene presence checked for every dataset contributing to a gene-level comparison.
- [ ] Assay, suspension type, dataset and donor available as variables in the result.
- [ ] Contributing datasets listed with citations.
