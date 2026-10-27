# RNA velocity with scVelo

Read this when you want to infer the direction of change of single cells from spliced and unspliced RNA, estimate latent time, or rank genes driving a transition. General single-cell steps are in `scanpy.md`; probabilistic velocity models also exist in `scvi-tools.md`.

## Know the limits first

RNA velocity estimates, for each gene, whether unspliced RNA is above or below what a steady state predicts, and turns that into a direction of change. The estimate rests on assumptions that often fail:

- one set of transcription, splicing and degradation rates per gene across the whole population;
- enough unspliced reads (protocols, read length and nuclei versus whole cells change this a lot);
- kinetics that are not dominated by bursts, cell cycle or several lineages using the gene differently.

Velocity can point the wrong way with high confidence when these break. Treat it as a hypothesis generator. Confirm direction with independent evidence: time points, known marker order, lineage tracing or metabolic labeling.

## Inputs

You need two count layers per cell, `spliced` and `unspliced`, from the same barcodes as the processed object:

- `velocyto run` on the BAM, STARsolo with `--soloFeatures Gene Velocyto`, alevin-fry or simpleaf in spliced-unspliced-ambiguous mode, or kb-python's workflow for nascent and mature RNA.
- Use the same genome and annotation as the main analysis.

```python
import scvelo as scv
import scanpy as sc

adata = sc.read_h5ad("processed.h5ad")             # QC, clusters, UMAP already done
ldata = scv.read("sample.loom", cache=False)        # spliced and unspliced layers
# barcode formats differ between tools ("sample:ACGT...x" against "ACGT...-1"): normalize before merging
ldata.obs_names = [bc.split(":")[-1].rstrip("x") + "-1" for bc in ldata.obs_names]
adata = scv.utils.merge(adata, ldata)
print(adata.n_obs, "cells after merge")            # compare with the processed object
```

Check how many cells survived the merge. A large drop means the barcode rewrite is wrong, not that cells were bad.

## Workflow

```python
scv.pp.filter_genes(adata, min_shared_counts=20)
scv.pp.normalize_per_cell(adata)
scv.pp.filter_genes_dispersion(adata, n_top_genes=2000)
scv.pp.log1p(adata)
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)     # smooths over neighbors

scv.tl.recover_dynamics(adata, n_jobs=8)            # dynamical model: slower, fits per-gene kinetics
scv.tl.velocity(adata, mode="dynamical")
scv.tl.velocity_graph(adata)
scv.tl.latent_time(adata)
scv.tl.velocity_confidence(adata)

scv.pl.velocity_embedding_stream(adata, basis="umap", color="cell_type")
```

- The stochastic mode (`mode="stochastic"`) is fast and fine for a first look; the dynamical mode is needed for latent time and per-gene kinetic fits.
- Preprocessing helpers have been renamed or deprecated across releases (combined filter-and-normalize helpers, logging behavior). Check the installed version and its tutorial before copying code, and pin the environment: scVelo has had compatibility problems with newer NumPy and pandas releases.
- `moments` uses its own neighbor graph; keep `n_neighbors` and `n_pcs` consistent with the main analysis or state the difference.

## Checking the result

1. **Phase portraits:** `scv.pl.velocity(adata, ["GeneA", "GeneB"])` for genes whose behavior you know. A gene should show an upregulation arc (unspliced leading spliced) where it is induced. Fits on genes with flat or noisy portraits carry no information.
2. **Fit quality:** look at `adata.var["fit_likelihood"]`; base claims on well-fitted genes.
3. **Known direction:** progenitors should point toward their known descendants. If velocity reverses a known differentiation, the assumptions failed for those genes; report it, do not reinterpret the biology.
4. **Robustness:** rerun with a different gene set (for example more or fewer variable genes) and neighbor count. Conclusions that flip are not conclusions.
5. **Confidence:** `velocity_confidence` measures local coherence, not correctness. Coherent wrong arrows are possible.
6. **Embedding projections exaggerate.** Stream plots on UMAP compress high-dimensional velocity into two dimensions through the neighbor graph; arrows can look smooth where the underlying vectors disagree. Do not quantify anything from the arrows.

## Going further

- Fate probabilities and terminal states: CellRank builds transition matrices from velocity, pseudotime or real experimental time, and lets you combine them. Real time points beat velocity when you have them.
- Metabolic labeling data (new and old RNA) measures kinetics more directly; use tools built for it instead of splicing-based velocity.

## Report

- The tool that produced spliced and unspliced counts, its version, and the fraction of unspliced counts.
- Cells kept after merging, genes used, mode, neighbors and principal components.
- Genes whose phase portraits were inspected, and whether the direction matched independent evidence.
- A plain statement of the assumptions and where they may not hold for this system.

## Checks (done when)

- [ ] Spliced and unspliced layers come from the same genome and annotation as the main analysis; cell loss on merge explained.
- [ ] Phase portraits of known genes inspected; claims rest on well-fitted genes.
- [ ] Direction compared with independent biological evidence, and disagreements reported.
- [ ] Results stable across at least one change of genes or neighbors.
