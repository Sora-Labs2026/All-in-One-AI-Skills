# Probabilistic single-cell models with scvi-tools

Read this when you integrate single-cell datasets across batches, map query data onto a reference, transfer labels, model CITE-seq or multiome data jointly, detect doublets with a model, or need a count-based latent space for downstream analysis. The surrounding workflow (QC, clustering, annotation) is in `scanpy.md`; training mechanics and GPUs in `../../ml-engineering/references/deep-learning-pytorch.md`.

## When to use it, and when not

- **Use it** when batch effects are real and nonlinear, datasets are large, you need a reference to map new data onto, or several modalities are measured per cell.
- **Do not reach for it** when one well-behaved batch is analyzed alone (PCA is enough), when batch is confounded with condition (no model can separate them), or when the question is a donor-level comparison (pseudobulk, `bulk-rnaseq-deseq2.md`).

## Setup

```bash
python -m pip install scvi-tools
python -c "import scvi; print(scvi.__version__)"
```

The 1.x series changed training arguments (`accelerator` and `devices` replaced older GPU flags) and moved some models to `scvi.external` and to MuData-based setup. Read the documentation for the installed version, and pin it in the environment file.

## Model map

| Data and goal | Model |
|---|---|
| scRNA-seq integration and latent space | `SCVI` |
| Integration plus label transfer from partly labeled data | `SCANVI` (initialized from a trained `SCVI`) |
| Mapping a query onto a trained reference | Reference models with `load_query_data` (architecture surgery) |
| RNA plus surface protein (CITE-seq) | `TOTALVI` |
| RNA plus chromatin accessibility, paired or partly paired | `MULTIVI` |
| scATAC-seq alone | `PEAKVI` (binary accessibility) or Poisson-based variants for counts |
| Doublets | `SOLO`, trained on top of an `SCVI` model |
| Sample-level heterogeneity across many donors | `MRVI` (multi-resolution model; in recent releases) |
| Spatial deconvolution with a single-cell reference | `DestVI`, Stereoscope-style models |

## The basic pattern

```python
import scvi, scanpy as sc

scvi.settings.seed = 0
sc.pp.highly_variable_genes(adata, n_top_genes=3000, flavor="seurat_v3",
                            layer="counts", batch_key="sample", subset=False)
hv = adata[:, adata.var["highly_variable"]].copy()

scvi.model.SCVI.setup_anndata(hv, layer="counts", batch_key="sample",
                              categorical_covariate_keys=["chemistry"],
                              continuous_covariate_keys=["pct_counts_mt"])
model = scvi.model.SCVI(hv, n_latent=30, n_layers=2, gene_likelihood="nb")
model.train(max_epochs=400, early_stopping=True, accelerator="auto")

adata.obsm["X_scVI"] = model.get_latent_representation()
sc.pp.neighbors(adata, use_rep="X_scVI")
```

- **Counts only.** The models describe raw counts; pass the counts layer. Log-normalized or scaled input produces a model that trains and is wrong.
- **What goes in `batch_key`** is removed from the latent space. Put technical units there (sample, lane, chemistry); never the biological condition you want to compare.
- **Covariates are removed too.** Adding a continuous covariate such as mitochondrial fraction subtracts its effect; do it only when that effect is technical.
- **Variable genes:** 2,000 to 5,000 batch-aware variable genes is typical. More genes cost time; fewer can lose rare populations.

## Training and convergence

- Look at the curves: `model.history["elbo_train"]` and `model.history["elbo_validation"]` (or `reconstruction_loss_validation`). Training loss falling while validation rises means overfitting; a curve still falling at the last epoch means too few epochs.
- Early stopping needs a validation split (`train_size` below 1.0, the default holds out a fraction).
- Default epoch counts scale down with dataset size. Small datasets (under a few thousand cells) can overfit; consider fewer epochs or a simpler model.
- GPU runs are not bitwise reproducible even with a seed. Rerun with two or three seeds and check that clusters and conclusions hold.

## Is the integration any good?

Score it on two axes, on held-out labels the model did not see:
- **Batch removal:** batches mix within each cell type (kBET, iLISI, batch ASW).
- **Biology conservation:** known cell types stay separate (NMI and ARI against labels, cLISI, label ASW).

The scib-metrics package computes the standard set; compare against unintegrated PCA and a simple method (Harmony) on the same cells. A method that mixes batches perfectly by blending cell types has failed.

## Label transfer and reference mapping

```python
scanvi = scvi.model.SCANVI.from_scvi_model(model, labels_key="cell_type",
                                           unlabeled_category="Unknown")
scanvi.train(max_epochs=20)
hv.obs["predicted"] = scanvi.predict()
hv.obs["predicted_conf"] = scanvi.predict(soft=True).max(axis=1)
```

- Report prediction confidence and keep low-confidence cells as "unassigned" rather than forcing a label.
- A label that does not exist in the reference cannot be predicted; novel populations appear as low-confidence or wrongly labeled cells. Check clusters with low confidence by markers.
- For query mapping, prepare the query with the reference's genes (`prepare_query_anndata`), load with `load_query_data`, and fine-tune briefly. The reference model, its version and its training data are part of the result; record them.

## Differential expression from a model

```python
de = model.differential_expression(groupby="cell_type", group1="B cell", group2="T cell",
                                   mode="change", delta=0.25, batch_correction=True)
```

- Results give posterior probabilities of a change larger than `delta` in log fold change and an estimated false discovery proportion. They are useful for **cell-type** contrasts and marker discovery.
- They treat cells as the unit. For **conditions across donors**, use pseudobulk with donors as replicates, or a model with sample-level structure, and say which.
- `get_normalized_expression` returns denoised, model-smoothed values. Use them for plots, never as input to count-based tests.

## Saving and reuse

```python
model.save("models/scvi_v1", save_anndata=False, overwrite=True)
model = scvi.model.SCVI.load("models/scvi_v1", adata=hv)       # needs the same genes and setup
```

Store the model directory with the scvi-tools version, the gene list, the `setup_anndata` arguments and the training history. A model cannot be loaded against data with different features.

## Multimodal notes

- CITE-seq protein counts include background from unbound antibodies; totalVI models it, so give it raw protein counts and include isotype controls when available.
- Multiome integration of paired and unpaired cells depends on enough paired cells to anchor the modalities; report how many there were.

## Checks (done when)

- [ ] Models trained on raw counts with technical variables only in `batch_key` and covariates.
- [ ] Training and validation curves reviewed; seeds recorded and conclusions stable across two or more seeds.
- [ ] Integration scored for both batch removal and biology against unintegrated and simple baselines.
- [ ] Transferred labels carry confidence scores, with low-confidence cells left unassigned.
- [ ] Model directory saved with version, gene list, setup arguments and history.
