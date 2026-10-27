# Microbiome and community ecology with scikit-bio

Read this when you analyze feature tables (ASVs, OTUs, species or gene counts per sample): alpha and beta diversity, UniFrac, ordination, PERMANOVA and related tests, compositional transforms, or differential abundance. Building trees is in `phylogenetics.md`; amplicon denoising and taxonomy assignment are upstream steps (QIIME 2, DADA2, Deblur) whose outputs this file assumes.

## Setup

```bash
python -m pip install scikit-bio biom-format
python -c "import skbio; print(skbio.__version__)"
```

The 0.6 series reworked several APIs (for example the argument naming feature IDs in phylogenetic metrics, composition helpers, table support and alignment functions). Check the installed version and its documentation before copying examples.

## The data is compositional

Sequencing returns a sample of fixed size from each library, so counts carry only relative information. Consequences:
- A taxon can look "increased" only because others decreased.
- Correlations between relative abundances are biased (spurious negative correlation); use methods designed for compositions for networks (SparCC-type or graphical-model approaches).
- Library size differs for technical reasons and affects richness and rare-taxon detection.

Every step below handles this one way or another; state how.

## Inputs and hygiene

- Feature table (samples by features), taxonomy, a rooted tree for phylogenetic metrics, and metadata keyed by sample ID.
- **Negative controls:** extraction blanks and PCR negatives reveal contaminants, which dominate low-biomass samples. Identify contaminants with a dedicated method (for example frequency- or prevalence-based tests against controls) and report what was removed.
- **Positive controls:** a mock community shows whether expected taxa appear at roughly expected proportions.
- Remove features from host, chloroplast or mitochondria when they are not of interest, and say so.

## Depth: rarefy or not

- For **diversity** comparisons, unequal depth biases richness and unweighted metrics. Rarefying (subsampling each sample to the same depth, `skbio.stats.subsample_counts`) is an accepted way to control it; repeat with several seeds or report one recorded seed, and report how many samples fell below the depth and were dropped.
- For **differential abundance**, do not rarefy; use a method that models library size or compositions.
- Look at a rarefaction curve before choosing the depth; a depth below the plateau undercounts richness.

## Alpha diversity

```python
from skbio.diversity import alpha_diversity

shannon = alpha_diversity("shannon", counts, ids=sample_ids)
faith = alpha_diversity("faith_pd", counts, ids=sample_ids, tree=rooted_tree, taxa=feature_ids)
# older releases name this argument otu_ids
```

- Inputs are integer counts (rarefied or not, as decided above), not relative abundances.
- Richness estimators of unseen species are sensitive to singletons, which denoising methods often remove; interpret them carefully on denoised data.
- Compare groups with a test suited to the design (paired or mixed models for repeated sampling), see `../../ml-engineering/references/statistical-inference.md`.

## Beta diversity and ordination

```python
from skbio.diversity import beta_diversity
from skbio.stats.ordination import pcoa

bc = beta_diversity("braycurtis", counts, ids=sample_ids)
uu = beta_diversity("unweighted_unifrac", counts, ids=sample_ids, tree=rooted_tree, taxa=feature_ids)
ordination = pcoa(bc)
ordination.proportion_explained[:3]
```

| Metric | Sensitive to | Notes |
|---|---|---|
| Bray-Curtis | Abundant taxa | Common default for abundance data |
| Jaccard | Presence or absence | Depth-sensitive; rarefy first |
| Unweighted UniFrac | Rare lineages, presence | Needs a rooted tree covering all features |
| Weighted UniFrac | Abundant lineages | Less sensitive to rare taxa |
| Aitchison (Euclidean on CLR) | Log-ratios | Compositionally coherent; needs zero handling |

- UniFrac needs a rooted tree whose tips include every feature ID in the table, with identical names. Count mismatches before computing; missing tips fail or silently drop features depending on the version.
- PCoA on non-Euclidean distances can yield negative eigenvalues; report proportion explained from the positive axes and note the correction used if any.
- For large sample sets, the dedicated UniFrac implementation (the `unifrac` package) is much faster than a pure Python route.

## Testing group differences

```python
from skbio.stats.distance import permanova, permdisp

perm = permanova(bc, grouping=metadata, column="group", permutations=9999)
disp = permdisp(bc, grouping=metadata, column="group", permutations=9999)
```

- PERMANOVA tests whether group centroids differ, but it also reacts to differences in spread, especially with unbalanced groups. Always run PERMDISP alongside; if dispersions differ, say the result may reflect spread rather than location.
- Use restricted permutations (within subject or block) for repeated measures and blocked designs; free permutation of correlated samples inflates significance. scikit-bio's `permanova` permutes freely; for strata use a tool that supports them (for example `adonis2` with `strata` in R's vegan) or aggregate to one sample per subject.
- Report the pseudo-F, R-squared, permutations and p-value; with many metadata variables, adjust for multiple tests.
- Mantel tests relate two distance matrices (for example community and geographic distance); they test correlation, not causation, and are sensitive to spatial autocorrelation.

## Compositional transforms

```python
from skbio.stats.composition import clr, multi_replace     # older releases: multiplicative_replacement

clr_values = clr(multi_replace(counts))                     # replace zeros, then centered log-ratio
```

- Zeros must be replaced before log-ratios; the replacement choice changes results for rare taxa. Filter very rare features first.
- CLR values are relative to the sample's geometric mean; they are not absolute abundances.

## Differential abundance

- Methods disagree, sometimes widely, on the same data. Use at least two methods built for compositional count data (for example ANCOM-style log-ratio tests, ALDEx2, ANCOM-BC, or linear models on CLR with appropriate care) and report taxa found by both.
- scikit-bio includes an ANCOM implementation and, in recent releases, a Dirichlet-multinomial based test; many standard methods are R packages, which is fine to call from a pipeline.
- Filter on prevalence first (for example present in at least 10% of samples), adjust p-values, and report effect sizes with direction.
- Absolute changes need absolute data (spike-ins, qPCR of total load, flow counts); relative methods cannot provide them.

## Checks (done when)

- [ ] Negative and positive controls reviewed; contaminants and removed features reported.
- [ ] Depth handling stated: rarefaction depth, seeds and dropped samples, or the model that accounts for depth.
- [ ] Tree tips match feature IDs exactly before phylogenetic metrics.
- [ ] PERMANOVA reported with PERMDISP, permutation scheme and effect size.
- [ ] Differential abundance confirmed by at least two compositional methods, with effect sizes and adjusted p-values.
