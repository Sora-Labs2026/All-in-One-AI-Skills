# Classical ML with scikit-learn and gradient boosting

Read this for tabular classification and regression, preprocessing, pipelines, tuning, clustering and outlier detection. Evaluation rules are in `evaluation-and-leakage.md`; read it too.

## Pick the tool

| Situation | Start with | Why |
|---|---|---|
| Tabular data, any size that fits in memory | `HistGradientBoostingClassifier/Regressor`, or LightGBM, XGBoost, CatBoost | Strong default accuracy, handles missing values, little preprocessing |
| Need coefficients, monotone effects or a simple audit trail | Regularized linear or logistic regression; GAM-style models (`SplineTransformer` + linear model) | Interpretable by construction |
| Many categorical columns with high cardinality | CatBoost, or `TargetEncoder` + boosting | Ordered target statistics without leakage |
| Text with a few thousand labeled rows | `TfidfVectorizer` + `LogisticRegression` as the baseline; then sentence embeddings + linear model | Cheap, strong baselines before any fine-tuning |
| Small data (hundreds of rows) | Linear models, small random forests, strong regularization, repeated CV | Variance dominates; complex models overfit the folds |
| Data larger than memory | Out-of-core `SGDClassifier`/`partial_fit`, or a distributed engine (see `../../data-engineering/GUIDE.md`) | scikit-learn is single-machine |
| Images, audio, long text, sequences | Deep learning (`deep-learning-pytorch.md`, `transformers.md`) | Hand-made features rarely compete |

Deep learning on ordinary tabular data rarely beats well-tuned gradient boosting; make it earn its place against that baseline.

## Setup and versions

```bash
python -m pip install "scikit-learn>=1.5" pandas numpy   # check: python -c "import sklearn; print(sklearn.__version__)"
python -m pip install lightgbm xgboost catboost          # only the booster you use
```

Version-sensitive features (check the installed version before using them):
- 1.2: `set_output(transform="pandas")` keeps column names through pipelines.
- 1.3: `TargetEncoder`, `HDBSCAN`, `cross_validate(..., return_indices=True)`.
- 1.4: `HistGradientBoosting*(categorical_features="from_dtype")` reads pandas `category` columns; `root_mean_squared_error` replaces `mean_squared_error(squared=False)`.
- 1.5: `TunedThresholdClassifierCV`, `FixedThresholdClassifier`.
- 1.6: `FrozenEstimator` for calibrating or stacking an already fitted model.
- Metadata routing (passing `sample_weight` or `groups` through meta-estimators) is opt-in via `sklearn.set_config(enable_metadata_routing=True)`; check that every step supports it.

## The pipeline idiom

Every fitted transformation goes inside the pipeline. This is what makes cross-validation honest and what you deploy.

```python
import numpy as np
from sklearn.compose import ColumnTransformer, make_column_selector as cols
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

numeric = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler())
categorical = make_pipeline(SimpleImputer(strategy="most_frequent"),
                            OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20,
                                          sparse_output=False))      # pandas output needs dense arrays
prep = ColumnTransformer([("num", numeric, cols(dtype_include=np.number)),
                          ("cat", categorical, cols(dtype_include=["object", "category"]))],
                         verbose_feature_names_out=False).set_output(transform="pandas")

linear = Pipeline([("prep", prep), ("clf", LogisticRegression(max_iter=2000, C=1.0))])
boosted = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=0)  # needs category dtype
```

Idioms that matter:
- `handle_unknown="infrequent_if_exist"` (or `"ignore"`) so new categories at prediction time do not crash the service.
- `add_indicator=True` keeps "was missing" as a signal; missingness is often informative.
- Trees do not need scaling; linear models, SVMs, k-NN, neural networks and PCA do.
- Use `ColumnTransformer` column lists or selectors, never positional indexes on a DataFrame whose column order may change.
- Custom steps: subclass `BaseEstimator, TransformerMixin`, learn state only in `fit`, store it in attributes ending with `_`, and test with `sklearn.utils.estimator_checks.check_estimator` when the transformer will be reused.
- `FunctionTransformer` for stateless transforms (log1p, ratios). Anything with learned state needs a real transformer.

## Tuning

```python
from scipy.stats import loguniform, randint
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

search = RandomizedSearchCV(
    boosted,
    {"learning_rate": loguniform(0.02, 0.3), "max_leaf_nodes": randint(15, 127),
     "min_samples_leaf": randint(10, 200), "l2_regularization": loguniform(1e-3, 10)},
    n_iter=40, scoring="average_precision", cv=StratifiedKFold(5, shuffle=True, random_state=0),
    n_jobs=-1, random_state=0, refit=True)
search.fit(X_train, y_train)
```

- Address parameters inside pipelines with `step__param` (`"clf__C"`).
- Prefer randomized search or Optuna over grids; tune learning rate and tree size first, then regularization.
- Boosters: use early stopping on a validation split carved from training data (`early_stopping=True` with `validation_fraction` in HistGradientBoosting; `eval_set` of a validation split in LightGBM and XGBoost), never on the test set.
- Successive halving (`HalvingRandomSearchCV`, experimental import `sklearn.experimental.enable_halving_search_cv`) saves time on large searches.
- The best CV score of the search is optimistic; see nested CV in `evaluation-and-leakage.md`.

## Gradient-boosting libraries

| Library | Strength | Watch out for |
|---|---|---|
| scikit-learn HistGradientBoosting | No extra dependency, native missing values and categoricals | Fewer knobs, no GPU |
| LightGBM | Fast on large data, good categorical handling | Leaf-wise growth overfits small data: cap `num_leaves`, raise `min_child_samples` |
| XGBoost | Mature, GPU (`device="cuda"`), monotone and interaction constraints | Set `enable_categorical=True` with pandas categories; pin the version since defaults changed in 2.x |
| CatBoost | Categorical features without manual encoding, ordered boosting | Slower training; pass `cat_features` explicitly |

All three expose native SHAP-style contributions (`pred_contribs`, `pred_contrib`, `get_feature_importance(type="ShapValues")`); see `explainability.md`.

## Clustering and outlier detection

- Scale features first, and choose the distance deliberately; clustering results are mostly a consequence of feature choice and scaling.
- K-Means assumes compact, similar-size spherical clusters; use `n_init="auto"` and several seeds. `MiniBatchKMeans` for large data.
- `HDBSCAN` (1.3+) finds clusters of varying density and labels noise as `-1`; tune `min_cluster_size` from the smallest group that would matter.
- Gaussian mixtures give soft assignments; choose components by BIC.
- No ground truth: judge clusters by stability (re-cluster bootstrap samples and compare with adjusted Rand index), by whether they are actionable, and by domain review. A silhouette score alone proves nothing.
- Outliers: `IsolationForest` for tabular data, `LocalOutlierFactor(novelty=True)` when you must score new points, robust covariance for roughly Gaussian data. Set `contamination` from domain knowledge or leave it at `"auto"` and threshold scores yourself. Validate on labeled incidents if any exist.

## Text features in scikit-learn

- `TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)` plus `LogisticRegression` or `LinearSVC` is the baseline every text model must beat.
- `HashingVectorizer` for streaming or huge vocabularies (no inverse mapping to words).
- Fit vectorizers inside the pipeline: vocabulary and IDF learned on test text are leakage.

## Persistence and deployment

- `joblib.dump(pipe, "model.joblib")` stores the whole pipeline. Pickle-based files execute code when loaded: load only files you produced or trust, never user uploads. `skops.io` offers a safer format with an explicit trusted-types list.
- Pickles are tied to library versions. Record `sklearn.__version__`, Python version and the training data hash next to the file; load with the same versions or retrain. For cross-language or long-lived serving, export to ONNX (`skl2onnx`) and compare predictions on a sample.
- Freeze the column schema: validate incoming columns and dtypes before `predict`, so a renamed column fails loudly instead of being imputed silently.

## Performance and scale

- `n_jobs=-1` parallelizes CV and forests; avoid nested parallelism (search `n_jobs` and estimator `n_jobs` both at -1 oversubscribes cores).
- `HistGradientBoosting` bins features and scales to millions of rows; classic `GradientBoostingClassifier` does not.
- One-hot encoding of high-cardinality columns explodes memory; use `min_frequency`, `max_categories`, target encoding or native categorical support.
- Sparse matrices stay sparse only if every step supports them; a `StandardScaler(with_mean=True)` densifies.

## Top pitfalls

| Pitfall | Fix |
|---|---|
| `fit_transform` on the full data before splitting | Pipeline inside cross-validation |
| `ConvergenceWarning` from linear models ignored | Scale features, raise `max_iter`, or adjust `C`; do not suppress the warning |
| `LabelEncoder` used on features | It is for targets; use `OrdinalEncoder` or `OneHotEncoder` for features |
| Impurity-based `feature_importances_` treated as truth | Biased toward high-cardinality features; use permutation importance on held-out data |
| Probabilities from SVC (`probability=True`) or boosted trees used raw | Calibrate on held-out data and check the calibration curve |
| `random_state` fixed once and results reported as stable | Vary seeds and report the spread |
| Accuracy reported on imbalanced data | Average precision, recall at a precision floor, cost |

## Done when

- [ ] One pipeline object holds every fitted step and is what gets cross-validated, saved and served.
- [ ] Baselines (dummy, linear, default boosting) are reported on the same folds.
- [ ] Tuning used only training data; the final test score was computed once.
- [ ] Library versions and the training data reference are stored with the model file.
- [ ] Predictions from the saved file match the in-memory model on a sample.
