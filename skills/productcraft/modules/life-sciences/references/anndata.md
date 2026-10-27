# AnnData: the annotated matrix behind single-cell work

Read this when you create, read, write, subset, combine or debug AnnData objects and `.h5ad` or `.zarr` files, for Scanpy, scvi-tools, scVelo, CELLxGENE Census or your own models. Analysis steps are in `scanpy.md`.

## The object

| Slot | Shape | Holds |
|---|---|---|
| `X` | cells x features | The main matrix (often sparse) |
| `obs`, `var` | DataFrames, one row per cell or feature | Metadata; their indexes are `obs_names` and `var_names` |
| `layers` | dict of matrices shaped like `X` | Alternative values: raw counts, normalized, spliced, unspliced |
| `obsm`, `varm` | dict of arrays with one row per cell or feature | Embeddings (`X_pca`, `X_umap`, `X_scVI`), loadings |
| `obsp`, `varp` | dict of square sparse matrices | Graphs (`connectivities`, `distances`) |
| `uns` | nested dict | Parameters, colors, results that fit nowhere else |
| `raw` | frozen copy of `X` and `var` | Legacy slot for pre-filtering values |

Check the installed version (`anndata.__version__`); lazy reading, Zarr formats and experimental helpers have changed across the 0.10, 0.11 and 0.12 releases.

## Rules that prevent most bugs

1. **Keep raw counts in a layer.** `adata.layers["counts"] = adata.X.copy()` before any normalization. Models such as scVI and pseudobulk DESeq2 need counts; recovering them later is guesswork. Prefer a named layer over `adata.raw`, whose frozen feature set is easy to misuse.
2. **Unique indexes.** `adata.obs_names_make_unique()` and `adata.var_names_make_unique()` after loading. Duplicate gene symbols (common in 10x feature files) silently break joins; use Ensembl IDs as `var_names` and keep symbols in a column.
3. **Views are not copies.** `sub = adata[mask]` is a view. Writing into it triggers a warning and an implicit copy, or modifies what you did not intend. Use `adata[mask].copy()` when the subset will be changed or kept.
4. **Use categoricals for repeated strings.** `adata.strings_to_categoricals()` saves memory and is required for clean writes. Mixed-type object columns (numbers and strings) fail at write time; cast them.
5. **Sparse stays sparse.** Many operations densify silently (`adata.X.toarray()`, `np.asarray(X)`, some scaling). Check `scipy.sparse.issparse(adata.X)` after each step on large data.
6. **Know what `X` holds.** Record in `uns` (or in your report) whether `X` holds counts, normalized or log values. A quick check for counts: `np.allclose(X.data, np.round(X.data))` on a sample of values.

## Reading and writing

```python
import anndata as ad
import scanpy as sc

adata = sc.read_10x_h5("filtered_feature_bc_matrix.h5")   # 10x HDF5
adata = ad.read_h5ad("data.h5ad")
adata.write_h5ad("out.h5ad", compression="gzip")          # smaller, slower; "lzf" is a faster middle ground
adata.write_zarr("out.zarr")                              # chunked; suits object storage and parallel reads
```

- Read a large file without loading `X`: `ad.read_h5ad(path, backed="r")`, filter on `obs`, then `adata[mask].to_memory()`.
- For collections larger than memory, combine files on disk (`anndata.experimental.concat_on_disk` in recent releases) instead of loading all of them.
- Loom and CSV imports lose structure; convert once to h5ad and keep the original.
- After writing, reopen the file and compare shape, layer names and a few values. A write that "worked" can still drop objects that do not serialize (custom classes in `uns`).

## Combining datasets

```python
combined = ad.concat(
    {"donor1": a1, "donor2": a2},      # keys become the label values
    label="sample",                     # new obs column
    join="inner",                       # keep shared features only
    index_unique="-",                   # make cell names unique: AAAC...-donor1
    merge="same",                       # keep var columns that agree across inputs
)
```

- `join="inner"` keeps genes present in every input; `join="outer"` keeps all and fills missing entries (zeros in sparse matrices, missing values in dense ones). Outer-joined zeros look like real zero counts; prefer inner joins, or record which genes were absent per dataset.
- Align feature identifiers first: same annotation release, same ID type, version suffixes stripped consistently.
- Barcodes repeat across samples; always set `index_unique` or prefix barcodes with the sample.
- `obsm`, `layers` and `uns` follow their own merge rules; check that what you need survived.

## Multimodal and spatial

- Several modalities measured on the same cells (RNA plus protein, RNA plus ATAC) belong in a MuData object, one AnnData per modality.
- Spatial data with images and coordinates belongs in SpatialData; plain AnnData holds the count table and coordinates in `obsm["spatial"]`.

## Memory arithmetic

A dense float32 matrix costs 4 bytes per value. 200,000 cells by 33,000 genes is about 26 GB dense. Sparse CSR costs about 8 bytes per nonzero value (value plus column index): with 2,000 detected genes per cell that is about 3 GB. Copies double it. Estimate before loading, and delete intermediate copies (`del`, then `gc.collect()`) in long notebooks.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Counts overwritten by normalization | Copy to `layers["counts"]` first |
| Duplicate gene symbols as `var_names` | Ensembl IDs as index, symbols in a column |
| Changes to a view | `.copy()` the subset |
| Write fails on object columns | Cast to string or categorical |
| Category colors scrambled | Colors in `uns["<key>_colors"]` follow category order; reset them after reordering |
| Outer join zeros mistaken for zero expression | Inner join, or track absent features |

## Checks (done when)

- [ ] Raw counts are in a named layer and documented as such.
- [ ] `obs_names` and `var_names` are unique, with stable feature IDs.
- [ ] The written file reopens with the same shape, layers and key metadata.
- [ ] Concatenated objects record their source in an `obs` column, and the join choice is stated.
