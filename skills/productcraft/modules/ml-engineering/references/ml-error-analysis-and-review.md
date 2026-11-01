# Error analysis, experiment logs and reviewing ML changes

Read this when a baseline model exists and the question is what to try next; when metrics and thresholds must be chosen from what errors cost; when you analyze a model's mistakes; when you keep a record of experiments; or when you review a pull request that touches features, training, evaluation, serving or monitoring code. Split and leakage rules are in `evaluation-and-leakage.md`; promotion gates and monitoring in `mlops.md`.

## Price the mistakes

- Look at the confusion matrix in counts, not only rates, and put a cost on each cell with the owner: a false fraud alert costs a support call and an annoyed customer; a missed fraud costs the chargeback.
- Every metric choice makes some error cheaper and another more likely. Say which, and who absorbs it.
  - Precision when acting on a false positive is expensive; recall when missing a positive is.
  - F1 only when the two costs are genuinely similar.
  - Ranking metrics when order matters more than a cut-off (`../scripts/rank_metrics.py`).
  - Calibration when the probability itself drives a decision or is shown to people.
  - Latency, memory and cost per prediction are metrics too; they bound which models are feasible.
- Choose the threshold on validation data by expected cost, then score the test set once with it:

```python
import numpy as np

def cost_threshold(y_true, p, cost_fp, cost_fn):
    grid = np.unique(np.concatenate([[0.0, 1.0], p]))
    costs = [cost_fp * np.sum((p >= t) & (y_true == 0)) + cost_fn * np.sum((p < t) & (y_true == 1)) for t in grid]
    best = int(np.argmin(costs))
    return float(grid[best]), float(costs[best])
```

With well-calibrated probabilities the cost-minimizing rule is "act when p > cost_fp / (cost_fp + cost_fn)"; a large gap between that value and the threshold found above is a sign the probabilities are not calibrated.

## Look at the errors

After each baseline or significant change:

1. **Sample** false positives, false negatives, low-confidence predictions, abstentions and system failures (timeouts, missing features) separately: dozens of each, drawn at random from validation data, not the first rows.
2. **Tag each error** with its most likely cause. A fixed tag list keeps counts comparable across iterations:

| Tag | Meaning | Usual next move |
|---|---|---|
| label | Label wrong or ambiguous | Fix labels, adjudication rules, or measure label noise |
| signal | Information needed is not in the features | New feature family, with a leakage check |
| stale | Feature missing or out of date at prediction time | Pipeline or freshness fix |
| data bug | Wrong join, unit, parsing, duplicate | Fix the data code, add a test |
| threshold | Right ranking, wrong cut-off for this segment | Cost-based threshold, per-segment review |
| product | The case is ambiguous to people too | Change the product flow or add human review |
| serving | Online features differ from training | Shared feature code or an equivalence test |
| new | Input unlike training data | Coverage, abstention, monitoring |

3. **Count the tags.** The largest bucket decides the next experiment. Model capacity is the answer only when "signal" dominates and simpler fixes are exhausted.
4. **Slice the metrics** by segments that matter (new versus returning users, language, region, device, source, time period); averages hide the segment that got worse.
5. **Keep the evidence:** each important error class becomes a regression case, an evaluation slice, a monitoring panel or a runbook entry.

Errors and samples often contain personal data: review them where the data lives and put only counts and redacted examples in reports.

## Keep an experiment log

Record every experiment, including failures and reverted ideas, next to the code or in the tracker (`mlops.md`):

```text
ID / date:       exp-031, 2026-10-14
Hypothesis:      false negatives on first-week accounts lack usage history; tenure-bucketed defaults will help
Change:          one change only: imputation by tenure bucket (commit 7c1e0a2)
Run:             data snapshot 2026-10-01, config churn-v3.yaml, seeds 1-5
Result:          PR-AUC 0.412 -> 0.431 (mean of 5 seeds, spread 0.006); compared with compare_scores.py cv
Slices:          first-week accounts recall 0.31 -> 0.40; other slices within +/-0.005
Error tags:      'signal' share among false negatives 46% -> 33%
Decision:        keep
Learned:         new-account errors were mostly missing history, not model capacity
Next:            label audit on 'label'-tagged false positives (now the largest bucket)
```

One change per experiment keeps results attributable. The log shows reviewers that the selected model is not the lucky survivor of many invisible tries.

## Reviewing an ML change

Start with the scope (`git diff --stat`), find which stages the change touches (data extraction, labels, features, training, evaluation, artifact, serving, monitoring), run the project's tests and evaluation commands, then check:

| Area | Look for |
|---|---|
| Framing | The decision, error costs and success metric are stated; the change targets the largest error bucket |
| Data and leakage | Split matches deployment (time or group where needed); every feature is available at prediction time; preprocessing fitted inside the training fold |
| Reproducibility | Code, data snapshot, config, environment and seed recorded; no notebook state needed to retrain |
| Evaluation | Baseline and current production model compared on the same data, with spread; test set not used for tuning; slices reported |
| Promotion | Gates written before the result; thresholds in config; gates fail closed |
| Serving | Training and serving transforms shared or tested for equivalence; input validation; timeout and fallback; model version in every prediction log |
| Monitoring and rollback | Drift, quality and system signals with owners; the previous artifact stays deployable |
| Security and privacy | No personal data or secrets in artifacts, logs, notebooks or prompts; no unpickling of untrusted files |

Quick read-only searches that often find problems:

```bash
git grep -nE "fit_transform|fit\(" -- '*.py' | head -40              # fitted before the split?
git grep -nE "train_test_split|random_split|shuffle=True" -- '*.py'  # random split on time or user data?
git grep -nE "pickle\.load|joblib\.load|weights_only=False" -- '*.py'
git grep -nE "threshold\s*=\s*0\.[0-9]+" -- '*.py'                     # magic thresholds without a cost basis
```

Retrieval and language-model changes add the checks in `rag-systems.md` and `llm-evaluation.md`: recall against a keyword baseline, a reranker that actually changes the order, abstention when context is insufficient, citations that point to retrieved sources.

**Blockers** (any one means `BLOCK` until fixed or explicitly accepted by the owner): a split that leaks the future or shares entities across splits; a feature unavailable at prediction time; tuning on the test set; no comparison with baseline and production; duplicated training and serving logic without an equivalence test; no model version in prediction logs; rollback that requires retraining; loading untrusted pickles; personal data in artifacts or logs.

Report findings highest severity first:

```text
[HIGH] Feature uses post-outcome field
File:  features/build.py:57
Issue: refund_issued is set days after the prediction moment; validation AUC is inflated
Fix:   drop it, or compute it as of the prediction timestamp with a point-in-time join
Decision: BLOCK   Tests run: pytest tests/features (pass), make eval (not run: needs warehouse access)
```

## Checks (done when)

- [ ] Error costs agreed; metrics and threshold chosen from them on validation data.
- [ ] Errors sampled at random by type, tagged, counted and sliced; the next experiment targets the largest bucket.
- [ ] Every experiment, including reverted ones, is in the log with one change, its data, seeds and spread.
- [ ] Reviews cover every area in the table, cite file and line, and list what was not run.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Accuracy reported on imbalanced data | Costed confusion matrix; precision, recall or PR-AUC |
| Threshold 0.5 by default | Cost-based threshold on validation |
| Looking only at the first few errors | Random samples per error type |
| Bigger model as the default next step | Tag counts decide |
| Many changes in one experiment | One change per experiment |
| Review limited to code style | ML-specific areas and blockers |
