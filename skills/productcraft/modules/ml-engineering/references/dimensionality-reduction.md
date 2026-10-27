# Dimensionality reduction: PCA, UMAP and t-SNE

Read this when you need to visualize high-dimensional data, compress features before another model, cluster embeddings, or explain what a 2-D map of the data does and does not show. Plot styling belongs to `../../data-engineering/GUIDE.md`.

## Pick the method

| Goal | Method | Why |
|---|---|---|
| Compress features for a downstream model; denoise; decorrelate | PCA (`sklearn.decomposition.PCA`), `TruncatedSVD` for sparse data | Linear, fast, has `transform` and `inverse_transform`, variance explained is interpretable |
| 2-D or 3-D map that shows local neighborhoods | UMAP (`umap-learn`) | Good local structure, faster than t-SNE, can `transform` new points |
| 2-D map for a one-off figure of a fixed dataset | t-SNE (`sklearn.manifold.TSNE`, or openTSNE for speed and new points) | Excellent local separation; no reusable mapping in scikit-learn |
| Reduce before density clustering | UMAP to 5 to 20 dimensions, then HDBSCAN | Clusters in moderate dimensions, not in the 2-D picture |
| Parts-based, non-negative data (counts, spectra) | NMF | Additive, interpretable components |

Run PCA first anyway: it is the baseline, it reveals scaling problems, and reducing to 50 components before UMAP or t-SNE speeds them up with little loss.

## What a 2-D embedding can and cannot tell you

- **Can:** which points are near each other in the original space, whether labeled groups separate, where outliers sit, whether batches or sites dominate structure (a quality-control signal).
- **Cannot:** distances between clusters, cluster sizes, or density in the original space. UMAP and t-SNE distort all three. Do not measure gaps between blobs or say one cluster is "twice as spread".
- **Cannot:** prove that clusters exist. Both methods can produce clumps from noise with some settings. Confirm structure with a clustering stability check or a downstream task.

## UMAP setup and parameters

```bash
python -m pip install umap-learn        # check: python -c "import umap; print(umap.__version__)"
```

```python
import umap
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

reducer = make_pipeline(StandardScaler(), umap.UMAP(n_neighbors=15, min_dist=0.1, n_components=2,
                                                     metric="euclidean", random_state=42))
emb_train = reducer.fit_transform(X_train)
emb_new = reducer.transform(X_new)      # projects new points into the learned map
```

| Parameter | Effect | Typical values |
|---|---|---|
| `n_neighbors` | Size of the neighborhood considered: small values emphasize fine local structure, large values more global layout | 5 to 50; 15 default; raise for smoother maps, lower to separate small groups |
| `min_dist` | How tightly points pack in the output; affects the picture, not the neighborhood graph | 0.0 to 0.1 for clustering input; 0.1 to 0.5 for readable plots |
| `n_components` | Output dimensions | 2 or 3 to look at; 5 to 20 as clustering or model input |
| `metric` | Distance in the input space | `euclidean` on scaled numeric data, `cosine` for embeddings and TF-IDF, `hamming` or `jaccard` for binary |
| `random_state` | Reproducible output | Setting it disables multi-threading, so it is slower; leave it unset for speed when exact reproducibility does not matter |

Other options worth knowing:
- `densmap=True` keeps more of the local density information, at a run-time cost.
- Supervised UMAP: `fit(X, y)` pulls same-label points together; mark unlabeled points with `-1` for semi-supervised use. Fit it on training labels only, or the map leaks labels into anything built on it.
- `ParametricUMAP` learns a neural network encoder (needs TensorFlow/Keras); useful for very fast `transform` on new data.
- `inverse_transform` exists but is slow and approximate; use it for illustration only.
- GPU: RAPIDS cuML provides a compatible UMAP for large datasets on NVIDIA hardware.

## Clustering on embeddings

```python
import hdbscan  # or sklearn.cluster.HDBSCAN (scikit-learn 1.3+)

cluster_space = umap.UMAP(n_neighbors=30, min_dist=0.0, n_components=10, random_state=42).fit_transform(X_scaled)
labels = hdbscan.HDBSCAN(min_cluster_size=50, min_samples=10).fit_predict(cluster_space)
# label -1 is noise: report its share instead of forcing those points into clusters
```

- Cluster in the 5 to 20 dimensional UMAP space; make a separate 2-D UMAP only for display.
- Check stability: rerun with different seeds and subsamples, compare labelings with the adjusted Rand index, and report clusters that persist.
- Name clusters only after a domain expert has looked at members and summary statistics. A cluster is a hypothesis.

## Leakage and evaluation

- Any reduction fitted on all rows, then used as model features, leaks test information. Fit PCA or UMAP inside the training fold (put it in the `Pipeline`) and `transform` validation and test rows.
- Judge a reduction used for modeling by the downstream metric with cross-validation, not by how the picture looks.
- For visual quality, compare neighborhood preservation (for example `sklearn.manifold.trustworthiness`) across settings rather than eyeballing.

## PCA notes

- Scale features first unless they share units; PCA on raw data is dominated by the largest-variance columns.
- Choose components by explained variance (`PCA(n_components=0.95)`) or by downstream performance, not by a fixed number.
- `PCA(svd_solver="randomized")` or `IncrementalPCA` for large data; `TruncatedSVD` for sparse matrices (it does not center).
- Loadings (`components_`) show which original features drive each component; signs are arbitrary.

## t-SNE notes

- `perplexity` (roughly the neighborhood size) between 5 and 50; results change with it, so show two values when the picture is used to argue a point.
- Initialize with PCA (`init="pca"`, the scikit-learn default since 1.2) for more stable global layout.
- scikit-learn's TSNE has no `transform` for new points. openTSNE supports adding points to an existing embedding.

## Scale and performance

- UMAP handles hundreds of thousands to a few million rows on a workstation; the nearest-neighbor search (pynndescent) dominates. Reduce with PCA to 50 dimensions first.
- The first call compiles with Numba and is slow; later calls are faster.
- Memory grows with `n_neighbors` times rows. Lower `n_neighbors` or subsample when memory is tight, then `transform` the rest.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Interpreting distances or sizes between UMAP or t-SNE clusters | Describe neighborhoods only; quantify in the original space |
| Unscaled mixed-unit features | Scale, or choose a metric that suits the data |
| Clustering on the 2-D plot coordinates | Cluster in 5 to 20 dimensions; plot separately |
| Supervised UMAP fitted with test labels | Fit on training labels only |
| One run shown as "the structure" | Show seed and parameter sensitivity |
| Batch effects mistaken for biology or behavior | Color the map by batch, site and date before interpreting |

## Done when

- [ ] PCA baseline run; scaling and metric chosen deliberately.
- [ ] Any reduction used as features is fitted inside the training fold.
- [ ] Plots state the method and parameters, and the text avoids inter-cluster distance claims.
- [ ] Clusters were checked for stability across seeds and subsamples and colored by known confounders.
