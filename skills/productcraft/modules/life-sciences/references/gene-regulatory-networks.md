# Gene regulatory networks from expression data

Read this when you infer transcription factor to target links from bulk or single-cell expression (GRNBoost2 and GENIE3 through arboreto, or the SCENIC workflow), or estimate transcription factor activity from known regulons. Network analysis without regulation (centrality, communities) belongs to `../../data-engineering/references/networkx-graphs.md`.

## Set expectations first

Expression-based network inference finds genes whose expression is predictable from a transcription factor's expression. That is co-expression, not regulation:
- edges can reflect cell-type composition, cell cycle or shared upstream signals;
- the importance score has no direction (activation or repression) and no p-value;
- benchmarks against ChIP and perturbation ground truth have repeatedly found many methods only modestly better than random on real data.

Use inferred networks to prioritize hypotheses, and say so. Claims about specific regulation need motif, binding or perturbation evidence.

## Two routes

| Route | When |
|---|---|
| **Known regulons, activity scoring:** curated TF-target sets (for example DoRothEA or CollecTRI) scored per sample or cell with a tool such as decoupler | You want TF activity per condition or cell type; more robust and easier to defend |
| **De novo inference:** GRNBoost2 or GENIE3, optionally pruned by motif enrichment (SCENIC) | You want new candidate targets, or the organism and context lack curated regulons |

Many projects should start with the first and use the second only for discovery.

## Setup and environment

```bash
python -m pip install arboreto            # GRNBoost2 and GENIE3 on Dask
```

arboreto is lightly maintained and depends on Dask's distributed scheduler; recent Dask releases have broken it. Pin `dask` and `distributed` to versions known to work with the installed arboreto (or use the published containers of the SCENIC tools), record them, and test on a small matrix first.

## GRNBoost2

```python
import pandas as pd
from arboreto.algo import grnboost2
from distributed import Client, LocalCluster

def main():
    expr = pd.read_parquet("expr_cells_x_genes.parquet")       # rows = cells or samples, columns = genes
    tfs = [g for g in open("tfs_human.txt").read().split() if g in expr.columns]
    with LocalCluster(n_workers=8, threads_per_worker=1) as cluster, Client(cluster) as client:
        links = grnboost2(expression_data=expr, tf_names=tfs, seed=7, client_or_address=client)
    links.to_parquet("links_seed7.parquet")                    # columns: TF, target, importance

if __name__ == "__main__":                                      # required: Dask starts worker processes
    main()
```

- **Orientation:** observations as rows, genes as columns, gene names as column labels matching the TF list exactly (symbols or IDs, same case).
- **TF list:** a curated list for the species; record its source and version. Without `tf_names`, every gene is a candidate regulator and the run is slower and harder to interpret.
- **Input values:** use one consistent normalization; filter genes expressed in very few cells or samples first. Record the choice.
- **Seeds:** GRNBoost2 is stochastic. Run three or more seeds and keep edges that recur, or aggregate ranks across seeds.
- GENIE3 (random forests) is slower; use it as a comparison, not by default.

## Reading the output

- Importance values are relative within a target model; they are not probabilities and do not compare cleanly across targets. A fixed threshold such as "importance above 0.5" has no meaning across datasets.
- Select edges by rank: the top k regulators per target, the top n edges overall, or edges stable across seeds. State the rule.
- Add a sign separately (correlation between TF and target within the relevant cells), and treat it as a hint, not a mechanism.
- Run within a cell type or condition when the question is about regulation inside it; across mixed populations, the strongest edges often just separate cell types.

## SCENIC: pruning by motifs

The SCENIC workflow (pySCENIC):
1. Co-expression modules from GRNBoost2 (the step above).
2. Pruning: keep targets whose regulatory regions are enriched for the TF's motif, using ranking databases for the organism and genome build (cisTarget databases); the result is a set of regulons.
3. Activity: score each regulon in each cell (AUCell), giving a cells-by-regulons matrix for clustering and comparison.

- The motif databases must match the species and build of the annotation; mismatches silently prune almost everything.
- Regulons with very few targets are fragile. Report regulon sizes and require a minimum.
- Run the pipeline several times (different seeds) and keep regulons that recur.

## Validate

- **Known biology:** do master regulators of the cell types appear among the top regulators of their markers?
- **External evidence:** overlap of predicted targets with ChIP-seq peaks near the target's promoter, or with genes that change when the TF is perturbed (knockdown, CRISPR screens). Compare with a random-edges baseline of the same size; report precision at the top k.
- **Stability:** fraction of top edges shared across seeds and across bootstrap or donor subsamples.

## Scale

- Time grows with genes times observations. Restrict to variable genes plus the TF list, and subsample cells per type for very large datasets (record the sampling).
- Dask workers each hold a copy of the matrix; memory is roughly the matrix size times the number of workers. Use fewer workers with more memory when it does not fit.

## Checks (done when)

- [ ] TF list source, normalization, gene filter, library versions (including Dask) and seeds recorded.
- [ ] Edges selected by a stated rank or stability rule, not an absolute importance cut.
- [ ] Results recur across at least three seeds.
- [ ] Top regulators checked against known biology and at least one external source, with a random baseline.
- [ ] The report states that inferred edges are co-expression hypotheses, not demonstrated regulation.
