# Bulk RNA-seq differential expression with PyDESeq2

Read this when you test which genes change between conditions in bulk RNA-seq counts, or in pseudobulk counts aggregated from single cells. PyDESeq2 is a Python implementation of the DESeq2 method (negative binomial model, shrunken dispersions, Wald tests). General statistics are in `../../ml-engineering/references/statistical-inference.md`.

## Before any code: the design

1. **Unit of replication.** Biological replicates (animals, donors, independent cultures) are samples. Technical replicates (the same library sequenced twice) are summed, not counted as samples. Cells are never replicates.
2. **Replicates per group.** Three is a practical minimum; with two, variance estimates are poor and power is low. Say so when it applies.
3. **Confounding.** If every treated sample was processed in batch 2 and every control in batch 1, the batch effect and the treatment effect cannot be separated by any model. Check the cross-tabulation of every factor pair before fitting.
4. **The question as a contrast.** "Treated versus control within each genotype" and "does the treatment effect differ by genotype" are different models (main effects versus an interaction). Write the contrast down before fitting.

Run the helper before analysis; it checks integer counts, orientation, sample matching, library sizes, replicate counts and whether the design is full rank:

```bash
python3 <productcraft>/modules/life-sciences/scripts/counts_check.py \
  --counts counts.tsv --samples samples.tsv --sample-col sample --design batch,condition
```

## Inputs

- **Raw integer counts**, samples as rows and genes as columns. Not TPM, FPKM, CPM or log values; the model needs counts to estimate variance.
- Counts from featureCounts, HTSeq or STAR gene counts are ready. Estimated counts from salmon or kallisto are fractional: aggregate transcripts to genes and round (as DESeq2's own import does), or use a tximport-style importer, and say which.
- Metadata indexed by the same sample IDs, with factors as strings or categoricals and continuous covariates as numbers (centered or scaled if their range is large).
- Gene IDs as stable identifiers (Ensembl without version suffix), symbols kept separately.

## Setup

```bash
python -m pip install pydeseq2
python -c "import pydeseq2; print(pydeseq2.__version__)"
```

The API changed in the 0.4 series (formula designs instead of a list of design factors; an inference object for parallelism; coefficient names in formula style). Check the installed version and print coefficient names rather than guessing them.

## The run

```python
import pandas as pd
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats
from pydeseq2.default_inference import DefaultInference

counts = pd.read_csv("counts.tsv", sep="\t", index_col=0).T        # genes x samples on disk -> samples x genes
meta = pd.read_csv("samples.tsv", sep="\t", index_col="sample").loc[counts.index]
meta["condition"] = pd.Categorical(meta["condition"], categories=["control", "treated"])  # reference first

min_group = meta["condition"].value_counts().min()
keep = (counts >= 10).sum(axis=0) >= min_group                      # expressed in at least one group's worth of samples
counts = counts.loc[:, keep]

inference = DefaultInference(n_cpus=8)
dds = DeseqDataSet(counts=counts, metadata=meta, design="~batch + condition",
                   refit_cooks=True, inference=inference)
dds.deseq2()
print(dds.varm["LFC"].columns.tolist())                              # exact coefficient names

ds = DeseqStats(dds, contrast=["condition", "treated", "control"], alpha=0.05, inference=inference)
ds.summary()
res = ds.results_df                                                  # baseMean, log2FoldChange, lfcSE, stat, pvalue, padj
```

- The contrast `[factor, numerator, denominator]` fixes the direction: positive log fold change means higher in the numerator level.
- Pre-filtering is for speed and power, not correctness; independent filtering inside the test does the rest.
- `padj` is `NaN` for genes removed by independent filtering or flagged as count outliers. They were not tested; they are not "not significant", and they belong in neither list.

## Effect sizes

- Raw log fold changes of low-count genes are noisy. Shrink them for ranking and plots:

```python
ds.lfc_shrink(coeff="condition[T.treated]")     # use a name printed from dds.varm["LFC"]
```

  Shrinkage changes `log2FoldChange` in the results table; the p-values stay those of the Wald test. Report which values a table shows.
- To claim changes larger than a threshold, test against the threshold (the `lfc_null` and `alt_hypothesis` options of `DeseqStats` in recent releases) instead of filtering significant genes on fold change afterwards; post-hoc filtering does not control the error rate for the thresholded claim.

## Designs beyond two groups

- **Several groups:** fit once, then one `DeseqStats` per contrast. Report the number of contrasts; each controls its own FDR.
- **Paired samples** (before and after in the same donor): include the donor in the design (`~donor + condition`).
- **Interaction:** `~genotype + treatment + genotype:treatment` tests whether the treatment effect differs by genotype; the coefficient names tell you which contrast each represents. Interactions need more replicates.
- **Likelihood-ratio tests** (time courses, many-level factors tested at once): PyDESeq2 has focused on Wald tests; if the installed version lacks a likelihood-ratio test, use R DESeq2 for that analysis rather than approximating it with many pairwise contrasts.

## Diagnostics (look at all of them)

```python
dds.vst()                                        # variance-stabilized values for exploration, in a layer
```

1. **Size factors:** values far from the others flag a failed or very different library.
2. **PCA of variance-stabilized counts** colored by condition, batch and any other factor. Replicates should group; an outlier replicate needs an explanation (sample swap, degradation) before removal, and removals are reported.
3. **Dispersion plot:** gene-wise estimates scattered around a decreasing trend. A flat or odd trend points to unmodeled structure.
4. **P-value histogram:** flat with a spike near zero when there is signal. A hump in the middle, or a rise toward one, suggests a missing covariate, wrong model or non-count input.
5. **MA plot** of shrunken fold changes against mean expression.
6. **Known genes:** a gene you expect to change (the knocked-out gene, a treatment target) should do so.

## Pseudobulk from single cells

- Sum raw counts per biological sample and cell type (`scanpy.md`), drop pseudobulk samples built from very few cells, then run the same procedure per cell type with donors as replicates.
- Include the number of cells per pseudobulk sample as a covariate or check that it does not differ systematically between conditions.
- Run cell types separately and report the FDR control per cell type; the tested gene sets differ.

## Downstream

- Enrichment uses the genes that were **tested** as the background, not the whole genome.
- Ranked-list methods (GSEA-style) use the Wald statistic or shrunken fold change, stated explicitly.
- Heatmaps use variance-stabilized values, centered per gene.

## Pitfalls

| Pitfall | Fix |
|---|---|
| TPM or normalized values as input | Raw counts only; `counts_check.py` flags non-integers |
| Genes as rows passed directly | Transpose to samples x genes; check `counts.shape` |
| Metadata order differs from counts | Reindex metadata by the counts index |
| Batch fully confounded with condition | Report it; no model fixes it |
| `NaN` padj treated as not significant | Report filtered and outlier genes separately |
| Fold-change filter after testing | Test against the threshold |
| Cells used as replicates | Pseudobulk per donor |

## Report

Genes in, genes tested, filtered and outliers; design formula and contrast; replicates per group; FDR level and threshold test (if any); shrinkage method; number of genes up and down; the diagnostic plots; library versions.

## Checks (done when)

- [ ] `counts_check.py` ran clean, or every warning is explained.
- [ ] Design is full rank, the contrast direction is explicit, and coefficient names were printed, not guessed.
- [ ] Size factors, PCA, dispersion, p-value histogram and a known positive-control gene were reviewed.
- [ ] Untested genes (`NaN` padj) are reported separately from non-significant ones.
- [ ] Enrichment uses the tested genes as background.
