# Explainability: SHAP, permutation importance and effect plots

Read this when someone asks why a model predicts what it does, which features matter, whether a model relies on something it should not, or when a regulated decision needs per-case reasons.

## Decide what question is being asked

| Question | Method | Notes |
|---|---|---|
| Which features does the model rely on, overall? | Permutation importance on held-out data | Model-agnostic, measured in the metric's units; correlated features share or hide importance |
| How does the prediction change as one feature changes? | Partial dependence (PDP) and individual conditional expectation (ICE) curves; SHAP dependence (scatter) plots | PDP averages; ICE shows heterogeneity |
| Why did the model score this case this way? | SHAP values (local attributions) | Additive: base value + sum of contributions = model output |
| Does the model treat groups differently? | Group metrics first (error rates per group), attributions second | Attributions alone cannot prove or rule out unfairness |
| What would change the decision? | Counterfactual search under realistic constraints | Separate tooling; validate that the suggested changes are actionable |
| Does feature X cause the outcome? | None of the above | Causal questions need a causal design (`statistical-inference.md`); attributions describe the model, not the world |

## SHAP essentials

The Shapley value of a feature is its average marginal contribution to the prediction over orderings of features. SHAP values are **local**, they **sum to the model output minus the base value** (expected output over the background data), and they are in the **units of the explained output**: log-odds, probability, or raw regression units, depending on what you explain.

```bash
python -m pip install shap        # check: python -c "import shap; print(shap.__version__)"
```

Choose the explainer by model type:

| Model | Explainer | Cost |
|---|---|---|
| Tree ensembles (XGBoost, LightGBM, CatBoost, scikit-learn forests and boosting) | `shap.TreeExplainer` | Exact and fast |
| Linear and logistic models | `shap.LinearExplainer` (or the coefficients times centered features) | Exact and fast |
| Deep networks | `shap.DeepExplainer` or `GradientExplainer`; Captum's integrated gradients for PyTorch | Approximate; background choice matters |
| Anything else (pipelines, ensembles, black boxes) | `shap.Explainer(predict_fn, background)` (permutation-based) or `KernelExplainer` | Slow: costs many model calls per explained row |

```python
import shap

explainer = shap.TreeExplainer(model, data=background, feature_perturbation="interventional",
                               model_output="probability")       # probability needs a background
sv = explainer(X_explain)                                         # an Explanation object
shap.plots.beeswarm(sv, max_display=15)                           # global: magnitude and direction
shap.plots.bar(sv)                                                # global: mean |SHAP|
shap.plots.waterfall(sv[0])                                       # one case
shap.plots.scatter(sv[:, "income"], color=sv)                     # dependence and interaction hint

import numpy as np                                                # local accuracy check
assert np.allclose(sv.values.sum(axis=1) + sv.base_values, model.predict_proba(X_explain)[:, 1], atol=1e-4)
```

Without `data=`, `TreeExplainer` uses the path-dependent algorithm and explains the raw margin (log-odds for classifiers); the local accuracy check then compares against the margin, not the probability.

## Background data decides the answer

- The base value and every attribution are relative to the background distribution. Use a representative sample of **training** data (100 to 1,000 rows, or `shap.kmeans(X, k)` summaries for kernel methods), not the test rows you explain.
- Comparing a case against "typical customers" and against "approved customers" gives different, both correct, answers to different questions. State which background you used.
- `feature_perturbation="interventional"` breaks feature dependence (it can create unrealistic combinations); `"tree_path_dependent"` follows the trees' own conditional structure. Neither is the truth when features are strongly correlated; report the choice.

## Pipelines and transformed features

- Explaining a pipeline end to end with a model-agnostic explainer attributes to the original columns but is slow.
- Explaining only the final estimator on transformed features is fast but attributes to one-hot columns and scaled values. Sum the SHAP values of a category's one-hot columns to get the original feature's contribution, and show the original (unscaled) values in plots.
- Get transformed column names with `get_feature_names_out()` or `set_output(transform="pandas")`.

## Multiclass and output shapes

Recent SHAP versions return an `Explanation` whose values have shape `(rows, features)` for single-output models and `(rows, features, classes)` for multiclass; older versions returned a list per class. Check `sv.values.shape` before indexing, and explain one class at a time (`sv[:, :, k]`).

## Permutation importance and partial dependence

```python
from sklearn.inspection import permutation_importance, PartialDependenceDisplay

r = permutation_importance(pipe, X_valid, y_valid, scoring="average_precision",
                           n_repeats=20, random_state=0, n_jobs=-1)
order = r.importances_mean.argsort()[::-1]
for i in order[:10]:
    print(X_valid.columns[i], round(r.importances_mean[i], 4), "+/-", round(r.importances_std[i], 4))

PartialDependenceDisplay.from_estimator(pipe, X_valid, ["age", "tenure"], kind="both")  # PDP + ICE
```

- Compute on held-out data; importance on training data rewards memorization.
- Correlated features split or mask importance: permuting one leaves its twin to carry the signal. Group correlated features (cluster by Spearman correlation) and permute groups, or drop-and-refit for the few that matter.
- Impurity-based `feature_importances_` from trees is biased toward high-cardinality and continuous features; do not report it as "importance" without saying so.

## Debugging with explanations

- A top feature that would not be known at prediction time is leakage, not insight (see `evaluation-and-leakage.md`).
- Compare attributions on misclassified versus correct cases, and across segments, to find where the model relies on spurious cues (an ID-like column, a collection site, an image watermark).
- Sudden changes in mean |SHAP| per feature between model versions or over time are a cheap drift signal.

## Fairness and regulated use

- Measure outcomes by group first: selection rates, false positive and false negative rates, calibration per group. Dropping a protected attribute does not remove proxies (postcode, name, school).
- Attributions help find proxies; they do not certify fairness.
- Where law or policy requires reasons for adverse decisions (credit, insurance, employment, health), per-case explanations must be faithful to the deployed model, stable for similar cases, and reviewed by the owner's legal or compliance team. This module gives engineering practice, not legal advice; see `../../legal-ready/GUIDE.md` for launch obligations.

## Performance

- TreeExplainer is fast; explain a sample (a few thousand rows) for global plots rather than millions.
- Kernel and permutation explainers need many model calls per row. Budget them: explain tens to hundreds of cases, cache results, batch predictions.
- For online per-request explanations, prefer native contributions from the booster (`pred_contribs=True` in XGBoost, `pred_contrib=True` in LightGBM) and return only the top few features.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Reading SHAP as causal effect | Say "the model's output moves with X", not "X causes Y" |
| Background = the explained rows themselves | Background from training data, stated in the report |
| Mixing log-odds and probability units across plots | Pick one output space and label axes with it |
| Explaining a different model than the one deployed | Explain the saved artifact (same pipeline, same version) |
| Beeswarm of 50 features nobody can read | Top 10 to 15, plus grouped "other" |
| Local explanations shown to end users unreviewed | Domain review for wording, stability and legal requirements |

## Done when

- [ ] The method matches the question, and the output space (log-odds, probability, units) is labeled.
- [ ] Background data is described and comes from training data.
- [ ] Local accuracy holds on a sample (attributions sum to output minus base value).
- [ ] Global importance is computed on held-out data, with correlated features grouped or noted.
- [ ] Any surprising top feature has been checked for leakage.
- [ ] The report says explanations describe the model, not causes in the world.
