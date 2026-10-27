# Single-cell RNA-seq with Scanpy

Read this when you take single-cell or single-nucleus RNA-seq counts from raw matrices to quality-controlled, clustered and annotated cells, find marker genes, or compare conditions. The data structure is in `anndata.md`; deep generative integration in `scvi-tools.md`; velocity in `rna-velocity.md`; condition-level differential expression in `bulk-rnaseq-deseq2.md`.

## Setup

```bash
python -m pip install "scanpy[leiden]"        # pulls igraph and leidenalg
python -c "import scanpy as sc; sc.logging.print_header()"   # prints versions of scanpy and its stack
```

Paste the version header into the report. Defaults have changed across 1.9, 1.10 and 1.11 (Leiden backend, PCA arguments such as `mask_var`, built-in doublet detection and aggregation); check the installed version before copying code.

## Overview of a defensible run

1. Load each sample separately, with its metadata.
2. QC per sample: thresholds from the data, not from a tutorial.
3. Remove or flag doublets per sample. Consider ambient RNA correction for droplet data.
4. Combine samples, keep counts in a layer, normalize and log-transform.
5. Select variable genes (batch-aware), run PCA.
6. Check for batch effects; integrate only if needed.
7. Neighbors, clustering at several resolutions, UMAP for display only.
8. Markers, then annotation with evidence.
9. Condition comparisons on pseudobulk per donor, and composition with methods built for proportions.

## Quality control

```python
import numpy as np
import scanpy as sc

symbols = adata.var["gene_symbol"]                                # symbols column; IDs are the index
adata.var["mt"] = symbols.str.startswith("MT-")                    # mouse: "mt-"
adata.var["ribo"] = symbols.str.startswith(("RPS", "RPL"))
adata.var["hb"] = symbols.str.fullmatch(r"HB(A1|A2|B|D|E1|G1|G2|M|Q1|Z)")
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ribo", "hb"], percent_top=None,
                           log1p=True, inplace=True)

def robust_z(x):
    """Distance from the median in units of the median absolute deviation."""
    med = np.median(x)
    mad = np.median(np.abs(x - med)) or 1e-9
    return (x - med) / mad

obs = adata.obs
low_quality = (np.abs(robust_z(obs["log1p_total_counts"])) > K_DEPTH) | \
              (np.abs(robust_z(obs["log1p_n_genes_by_counts"])) > K_DEPTH)
high_mito = obs["pct_counts_mt"] > MITO_CAP            # cap chosen for this tissue and protocol
adata.obs["qc_fail"] = low_quality | high_mito
```

`K_DEPTH` (often between 3 and 5) and `MITO_CAP` are decisions, not constants: choose them per sample from the distributions, write them down, and show the plots that justify them.

- Compute thresholds per sample; depth and quality differ between channels. Write the chosen thresholds and the cells removed per sample into the report.
- Mitochondrial fraction depends on tissue and protocol: metabolically active cells (heart, kidney, liver) are naturally high, and single-nucleus data should be low. A fixed cut such as 5% from a blood tutorial can delete real cell types.
- Use the gene prefixes of the organism and annotation in use; mouse symbols are lower-case (`mt-`).
- Look at the plots (`sc.pl.violin`, `sc.pl.scatter` of total counts against genes colored by mitochondrial fraction) before and after filtering. Thresholds that cut through a dense population need a reason.
- Filter genes lightly (`sc.pp.filter_genes(adata, min_cells=3)`) and only after combining samples, so gene sets stay aligned.

## Doublets and ambient RNA

```python
sc.pp.scrublet(adata, batch_key="sample")       # adds obs["predicted_doublet"], obs["doublet_score"]
```

- Run doublet detection per sample (`batch_key`) on counts, before normalization. The expected rate rises with the number of cells loaded per channel; compare the predicted rate with the chemistry's guidance.
- Clusters made of predicted doublets, or that express markers of two lineages, deserve a second look before they become a "novel population".
- Droplet data carries ambient RNA from lysed cells. When marker genes of abundant types show up everywhere, correct with a dedicated tool (for example CellBender on the raw matrix) and record it.

## Normalize, select genes, reduce

```python
adata.layers["counts"] = adata.X.copy()
sc.pp.normalize_total(adata)                    # scales each cell to the median total count
sc.pp.log1p(adata)
adata.layers["log1p"] = adata.X.copy()

sc.pp.highly_variable_genes(adata, n_top_genes=2000, flavor="seurat_v3",
                            layer="counts", batch_key="sample")   # seurat_v3 expects counts
sc.pp.pca(adata, n_comps=50, mask_var="highly_variable")          # older releases: use_highly_variable=True
```

- Keep all genes in the object; restrict PCA to the variable genes instead of subsetting the object. Marker detection and plots need the full gene set.
- `regress_out` of counts or mitochondrial fraction is slow and can remove biology; do not run it by default. Scaling (`sc.pp.scale(max_value=10)`) is optional; if used, keep it in a separate layer or object.
- Analytic Pearson residuals (`sc.experimental.pp.normalize_pearson_residuals`) are a sound alternative to log-normalization for variable genes and PCA; state which you used.
- Check the variance ratio plot; results are usually stable between 30 and 50 components, but look before choosing.

## Batch effects and integration

- First look: color the PCA and a UMAP by sample, donor and batch. Separation by batch within the same cell type indicates a batch effect; separation by condition may be the biology you want to keep.
- If integration is needed, use a method designed for it: Harmony on the PCA (`sc.external.pp.harmony_integrate`), BBKNN on the graph, or scVI and scANVI (`scvi-tools.md`). ComBat on log values is a weak choice for single cells.
- Integration can erase real differences when batch and condition are confounded. If every condition was run in its own batch, say that the comparison is confounded instead of "correcting" it.
- Score integration on both sides: batch mixing and preservation of known cell types (the scib-metrics package implements the standard metrics).

## Neighbors, clusters, embeddings

```python
sc.pp.neighbors(adata, n_neighbors=15, use_rep="X_pca", random_state=0)
for res in (0.3, 0.6, 1.0):
    sc.tl.leiden(adata, resolution=res, flavor="igraph", n_iterations=2,
                 random_state=0, key_added=f"leiden_{res}")
sc.tl.umap(adata, random_state=0)
```

- Clusters are a partition of a graph, not cell types. Choose the resolution by whether clusters are biologically interpretable and stable (rerun with other seeds or subsamples and compare with the adjusted Rand index).
- UMAP is for display. Distances between clusters, cluster sizes and apparent continuity on a UMAP are not evidence. Do statistics in the PCA or latent space, or on counts.
- Use the same neighbor graph for clustering, PAGA and pseudotime so they agree.

## Markers and annotation

```python
sc.tl.rank_genes_groups(adata, groupby="leiden_0.6", method="wilcoxon", layer="log1p", use_raw=False)
markers = sc.get.rank_genes_groups_df(adata, group=None)
```

- Marker p-values are inflated by construction (the groups were defined on the same data) and treat cells as independent. Use them to rank genes, not as evidence of differential expression.
- Annotate with several known markers per type, a dot plot of their expression across clusters, and, where a good reference exists, a reference-based method (for example CellTypist, label transfer with scANVI, or `sc.tl.ingest`). Record marker lists, reference name and version, and leave ambiguous clusters labeled as such.
- Annotation names should come from a controlled vocabulary (Cell Ontology terms) when data will be shared.

## Comparing conditions

- **Expression:** aggregate counts per donor and cell type, then test with a bulk method that models donors as replicates:

```python
pb = sc.get.aggregate(adata, by=["donor", "cell_type"], func="sum", layer="counts")
```

  Drop pseudobulk samples built from too few cells (for example fewer than 10 to 20), require at least two or three donors per group, then follow `bulk-rnaseq-deseq2.md`. Wilcoxon tests across cells of different conditions treat thousands of cells as replicates and report false positives at scale.
- **Composition:** proportions are compositional (one type rising pushes others down). Use methods built for it, such as scCODA or neighborhood-based tests like Milo, and report per-donor proportions alongside.

## Trajectories

- PAGA (`sc.tl.paga`) summarizes connectivity between clusters; diffusion pseudotime (`sc.tl.dpt`) needs a root cell chosen from biology, which must be stated.
- Pseudotime orders cells; it does not prove a lineage. Direction needs external evidence (known markers, time points, velocity with its caveats in `rna-velocity.md`).

## Scale

- Up to a few hundred thousand cells fits a workstation with sparse matrices. Beyond that: backed reading and subsetting, GPU implementations (the rapids-singlecell package mirrors much of the Scanpy API), or Dask-backed arrays where the installed Scanpy supports them.
- Save checkpoints after QC, after integration and after annotation, with the parameters in `uns`.

## Plots

Figures follow `../../data-engineering/references/plotting.md` and `../../data-engineering/references/publication-figures.md`. For single-cell plots specifically: plot expression from the log-normalized layer, use color scales shared across panels, and avoid rainbow palettes for continuous values.

## Checks (done when)

- [ ] Version header recorded; QC thresholds and cells removed reported per sample, with the plots reviewed.
- [ ] Doublets detected per sample; ambient correction decided and recorded.
- [ ] Raw counts kept in a layer; normalization and variable-gene method stated.
- [ ] Batch effects assessed; integration (if any) scored for mixing and biology.
- [ ] Clusters shown at more than one resolution with a stability check; seeds recorded.
- [ ] Annotations backed by named markers or a named reference; ambiguous clusters labeled as such.
- [ ] Condition effects tested on pseudobulk with donors as replicates; composition with a compositional method.
