# Evaluation and leakage

Read this before you report any model score, choose between models, tune hyperparameters, or claim that a change helped. Every other reference in this module assumes these rules.

## The four honesty rules

1. **The test set is touched once.** Model selection, feature selection, threshold choice, early stopping and prompt tweaks all happen on training and validation data. If a test score influenced any decision, it is now a validation score; say so and get a fresh test set.
2. **The split matches deployment.** Ask how the model will meet new data: new rows from known users, new users, the future, new sites, new documents. The split must reproduce that, or the score answers a different question.
3. **Every number has a spread.** Report the mean and the variation across folds, seeds or bootstrap resamples. A difference smaller than that variation is not a finding.
4. **Every number has a baseline.** A score means nothing without the trivial model (majority class, mean, last value, popularity, BM25) and the current production model on the same split.

## Choose the split from the deployment question

| The model will predict for | Split | scikit-learn |
|---|---|---|
| New independent rows from the same population | Random, stratified for classification | `train_test_split(..., stratify=y)`, `StratifiedKFold` |
| New entities (patients, users, devices, documents, molecules with new scaffolds) | Group split: every row of one entity in one fold | `GroupKFold`, `StratifiedGroupKFold`, `GroupShuffleSplit` |
| The future | Time split: train on the past, test on the later period, with a gap as long as the label delay | `TimeSeriesSplit(n_splits, gap=..., test_size=...)` or explicit date cut-offs |
| New sites, hospitals, regions or stores | Leave-one-site-out or grouped by site | `LeaveOneGroupOut` |
| Both new entities and the future | Time cut-off, then drop test entities seen in training | Custom: filter by date, then by group membership |

Check the result: `python3 <productcraft>/modules/ml-engineering/scripts/split_check.py --split train=train.csv --split test=test.csv --id <id> --group <entity> --time <timestamp> --target <label>` reports id, group and time overlap, duplicated rows, label copies and class balance. It cannot see leakage inside feature computation; the catalog below covers that.

Sizes: hold out enough test rows that the metric's interval is narrower than the smallest difference you care about. For a proportion near p measured on n independent rows, the 95% half-width is about `1.96 * sqrt(p(1-p)/n)`: 1,000 rows at 80% accuracy gives about +/-2.5 points. If data is scarce, use repeated cross-validation for selection and nested cross-validation for the final estimate instead of a single small test set.

## Leakage catalog

Leakage makes offline scores better than production will ever be. Look for each of these by name.

| Leak | How it happens | Fix |
|---|---|---|
| Preprocessing fitted on all data | Scaler, imputer, encoder, PCA, UMAP, feature selection or SMOTE fitted before the split | Put every fitted step inside a `Pipeline`, so cross-validation refits it per fold |
| Target encoding without cross-fitting | Category means computed with the row's own label | `TargetEncoder` (scikit-learn 1.3+) cross-fits in `fit_transform`; never call `fit` then `transform` on the same training rows |
| Duplicates and near duplicates across splits | Same record exported twice, augmented copies, re-posted text, the same image at two sizes | Deduplicate before splitting; group near duplicates (hash, MinHash, embedding similarity) and split by group |
| Entity overlap | Rows from one patient or user in both train and test | Group split |
| Future information | Features aggregated over windows that end after the prediction time; "last status" columns refreshed after the label event; global statistics over the whole period | Compute every feature "as of" the prediction timestamp (point-in-time joins); keep a gap between train end and test start |
| Label proxies | A column written because of the outcome: refund issued, diagnosis code, ticket closed reason, account deleted flag | Ask for each top feature "would this be known at prediction time?"; inspect top importances and any single feature with near-perfect accuracy |
| Selection on the test set | Picking the best of many runs, seeds, prompts or thresholds by test score | Select on validation; report the selected configuration once on test |
| Early stopping on test | Passing the test set as `eval_set` to a booster or as the validation loader | A separate validation split, or cross-validation |
| Resampling before splitting | Oversampling (SMOTE, random duplication) applied to the full dataset | Resample only inside the training fold (`imblearn.pipeline.Pipeline`) |
| Unsupervised steps on test labels | Clustering or embedding learned with test rows, then used as features | Fit on train only, `transform` the test rows |
| Benchmark contamination | Public test items that appeared in a pretrained model's training data | Prefer private or post-cut-off test sets; check overlap where possible |

A model that scores far above published or production numbers is a leakage suspect first and a breakthrough second.

## Cross-validation done right

```python
from sklearn.model_selection import StratifiedGroupKFold, cross_validate

cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
res = cross_validate(pipe, X, y, groups=groups, cv=cv,
                     scoring=["roc_auc", "average_precision", "neg_log_loss"],
                     return_train_score=True, n_jobs=-1)
for k in ("test_roc_auc", "test_average_precision"):
    print(k, res[k].mean().round(4), "+/-", res[k].std(ddof=1).round(4))
```

- `pipe` holds every preprocessing step. Passing a pre-transformed `X` defeats the point.
- Compare `train_*` with `test_*`: a large gap means overfitting, a small gap with poor scores means underfitting or weak features.
- **Nested cross-validation** when you tune and also need an unbiased estimate from the same data: an inner `GridSearchCV` or `RandomizedSearchCV` inside an outer `cross_validate`. The outer score estimates the whole procedure, not one fitted model.
- **Repeated k-fold** (`RepeatedStratifiedKFold`) when comparing two pipelines on small data: more resamples, steadier means.
- Use the same folds for every model you compare (fixed `random_state`, same `groups`), so differences are paired.

## Pick metrics before training

| Task | Primary metric | Also report | Avoid as the only metric |
|---|---|---|---|
| Balanced classification | Log loss or Brier score (probabilities), accuracy (decisions) | Confusion matrix, per-class recall | |
| Imbalanced classification | Average precision (PR AUC); recall at a fixed precision or cost-weighted loss | ROC AUC, calibration curve, base rate | Accuracy; ROC AUC alone hides poor precision on rare positives |
| Decisions with known costs | Expected cost at the chosen threshold | Threshold, confusion matrix at that threshold | Any threshold-free metric |
| Regression | MAE (median-like errors) or RMSE (punishes large errors); pinball loss for quantiles | Error by segment, residual plot, MAE of the naive baseline | R² alone; MAPE when actuals can be near zero |
| Ranking and retrieval | nDCG@k, recall@k, MRR | Coverage, per-query distribution | Precision@k when relevant items are few |
| Forecasting | MASE or scaled errors against seasonal naive | Interval coverage, pinball loss | MAPE alone |
| Clustering | External labels if any (ARI, NMI); otherwise stability across resamples and domain review | Silhouette as a weak hint | Silhouette alone as proof of structure |

- **Calibration** matters whenever a probability is used as a probability (risk scores, expected value, thresholds set by policy). Check with `CalibrationDisplay` and the Brier score; fix with `CalibratedClassifierCV` (isotonic needs about 1,000+ calibration rows, sigmoid works with fewer). In scikit-learn 1.6+ wrap an already fitted model in `FrozenEstimator` instead of the deprecated `cv="prefit"`.
- **Thresholds** are a decision, tuned on validation data: `TunedThresholdClassifierCV` (1.5+) optimizes a scorer such as cost or recall at a precision floor. The default 0.5 is rarely right for imbalanced data.
- **Segments.** Report the metric for every slice that matters (class, region, device, demographic group where lawful and relevant, new versus returning). An overall gain can hide a regression in a small slice.

## Baselines that must appear

- Classification: `DummyClassifier(strategy="prior")` for log loss, `"most_frequent"` for accuracy; a regularized logistic regression on the same features.
- Regression: `DummyRegressor(strategy="median")`; a linear model.
- Tabular in general: a gradient-boosted tree model with default settings. Deep models must beat it to justify their cost.
- Time series: naive (last value) and seasonal naive.
- Retrieval and recommendations: BM25 or popularity, respectively.
- LLM features: the current prompt or system in production, and a simple non-LLM rule if one exists.

## Report variance and compare models honestly

- Fold-to-fold standard deviation is the minimum. For a single test set, a bootstrap interval of the metric over rows (or over groups when rows are clustered) is better.
- Neural networks and RL: train with at least 3 seeds (5 or more for close calls) and report mean and spread. One seed is an anecdote.
- Comparing two models:
  - **Cross-validation scores:** the plain paired t-test on fold scores is overconfident because training sets overlap. Use the corrected resampled t-test: `compare_scores.py cv --a ... --b ... --folds 5`.
  - **One shared test set, per-example losses or scores:** paired bootstrap, clustered when rows share a user, document or site: `compare_scores.py bootstrap --csv per_example.csv --a-col a --b-col b [--cluster-col user]`.
  - **One shared test set, right or wrong per example:** exact McNemar: `compare_scores.py mcnemar`.
  - **Many comparisons** (many metrics, slices or candidate models): adjust with Holm or Benjamini-Hochberg (`compare_scores.py adjust`), and say how many comparisons you made.
- Statistical significance is not practical significance. State the effect in the metric's own units and whether it clears the threshold that would change a decision.

## Imbalanced data

- First change the metric and the threshold, not the data. Use class weights (`class_weight="balanced"`, `scale_pos_weight` in boosters) before resampling.
- Resampling (SMOTE and relatives) rarely beats weighting plus threshold tuning on modern learners, and it distorts predicted probabilities. If you resample, do it inside the training fold only and recalibrate.
- Report the base rate next to every precision figure; precision depends on prevalence, so a test set with an artificial class balance overstates it.

## Hyperparameter search without fooling yourself

- Randomized or Bayesian search (Optuna, scikit-learn's `RandomizedSearchCV`, `HalvingRandomSearchCV`) beats a large grid for more than two or three parameters.
- The best cross-validation score among many configurations is optimistically biased; the more configurations, the larger the bias. Nested CV or a held-out test set gives the honest number.
- Fix the budget (trials or hours) in advance and log every trial, not just the winner.

## Done when

- [ ] The split mirrors deployment and `split_check.py` (or an equivalent check) shows no unexplained overlap.
- [ ] All fitted preprocessing lives inside the pipeline that cross-validation refits.
- [ ] The test set was scored once, after every choice was frozen.
- [ ] Metrics were chosen from the decision, reported with spread, next to the trivial baseline and the current production model.
- [ ] Comparisons use paired, corrected tests or intervals; multiple comparisons are adjusted and counted.
- [ ] Results for important segments are listed, including any that got worse.
- [ ] The report names what was not checked (for example, no temporal holdout available).
