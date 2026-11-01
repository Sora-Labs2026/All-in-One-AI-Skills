# Adding machine learning to a product or an organization

Read this when a team or codebase without machine learning wants to "add ML" or "add AI" to a feature, when you must decide whether a model is the right tool at all, when you plan the first model in an organization, or when you wire a model into an existing application. Language-model features (retrieval, prompts) are in `rag-systems.md` and `prompt-design.md`; evaluation in `evaluation-and-leakage.md`; pipelines and deployment in `mlops.md`.

## First question: is a model the right tool?

| Points toward a model | Points away |
|---|---|
| A decision repeated many times (per order, per message, per user) | A handful of decisions a person can make |
| Patterns too many or too fuzzy for hand-written rules | A rule, threshold, regular expression or sort order already does well |
| Historical examples with outcomes (labels) or a feedback signal | No labels, no way to get them, outcome unknown for months |
| Errors are tolerable, detectable and reversible | One error is catastrophic or irreversible |
| Someone will own it after launch | Nobody will monitor or retrain it |
| The use of the data is permitted for this purpose | Personal data collected for another purpose, no lawful basis or consent for this use |

**Ship the rule first** when one exists. It gives a measured baseline the model must beat, a fallback when the model fails, and often most of the value. Saying "a model is not worth it here" with numbers is a good outcome.

## Write the prediction contract

Agree this with the product owner before any model code. It fits in a pull request description:

```text
Decision changed:   which action uses the prediction, and who or what takes it
Unit and timing:    one prediction per <order | user-day | document>, made at <moment>, with data available then
Output:             <probability | class | ranking | number>, calibrated? model version always attached
Latency and volume: <p95 budget>, <predictions per day>, batch or online
Error costs:        false positive costs <...> to <who>; false negative costs <...> to <who>
Human role:         <none | review above threshold | override and appeal>
Success metric:     <primary>, guardrails <...>, compared with <rule baseline | current process>
Fallback:           <rule> when the model is off, slow or failing
Owner:              <team>, review date <...>
```

Decisions about people (credit, hiring, insurance, access to services, medical triage) carry legal duties: explanation, human review and appeal rights (for example GDPR Article 22 for decisions with legal or similarly significant effects), and the EU AI Act's obligations for high-risk uses, which phase in from 2025 and whose dates were still being revised in 2025-2026. Raise these early and route them to `../../legal-ready/GUIDE.md`; this is not legal advice.

## Check the data is ready

- Where the examples live, who owns them, and whether you may use them for this purpose; access through read-only accounts (`../../data-engineering/references/live-database-access.md`).
- The label: exact definition, who or what produced it, how long after the prediction moment it becomes known, and how noisy it is.
- Feature availability at prediction time: every input must exist, with the value it had, at the moment the prediction is made. Fields filled in later (status after review, refund flags) are leakage.
- Volume per class and per important segment; duplicates; time span; how the population will differ after launch.
- A data contract: columns, types, ranges, allowed nulls, units, owners, and what happens when an upstream change breaks it.
- Profile with `../../data-engineering/scripts/csv_profile.py`; check splits with `../scripts/split_check.py`.

## Integrate behind a seam

The application should not know how the prediction is produced. Put the model behind an interface the application owns, with a flag, a timeout and a fallback:

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import logging

log = logging.getLogger("churn")
_pool = ThreadPoolExecutor(max_workers=4)

def churn_risk(features, model, flags, timeout_s=0.05):
    """Returns (score, source). The rule is the baseline and the fallback."""
    if model is None or not flags.is_on("churn-model", features["account_id"]):
        return rules_score(features), "rules"
    future = _pool.submit(model.predict_one, features)
    try:
        return future.result(timeout=timeout_s), model.version
    except FutureTimeout:
        return rules_score(features), "rules-timeout"   # the worker thread still finishes; size the pool for it
    except Exception:
        log.exception("churn model failed; rules used")
        return rules_score(features), "rules-error"
```

- Log the prediction, the model version (or `rules`), a request id and the minimal input needed to join with the outcome later; no unnecessary personal data.
- **Batch or online:** batch scoring on a schedule is simpler and enough when predictions can be hours old (daily risk lists, emails); online serving is for decisions inside a request.
- **Where the model runs:** in-process (smallest models, simplest), a separate service (shared, independently deployed), a managed endpoint, or a hosted API (check data terms, latency, cost per call and lock-in).
- Roll out in **shadow** first (predict and log, act on nothing), compare with the rule and with offline results, then a small flagged share of traffic with guardrails (`../../cloud-infrastructure/references/canary-analysis.md`).

## Plan the first project in phases

Each phase ends with evidence and a go or stop decision by the owner. Stopping is a valid result.

| Phase | Work | Exit evidence |
|---|---|---|
| 1. Frame | Prediction contract; rule baseline shipped or measured | Baseline numbers on recent data |
| 2. Data | Snapshot, contract, profile, split check | Clean split report; label definition signed off |
| 3. Offline model | Simple strong model (`classical-ml.md`), evaluation against the rule | Beats the rule by more than the spread on held-out data, within latency and cost budget |
| 4. Shadow | Seam, logging, shadow predictions | Online and offline predictions agree; latency and error rate acceptable |
| 5. Limited rollout | Flagged share, guardrails, experiment if impact must be measured (`statistical-inference.md`) | Owner's decision on the agreed metric |
| 6. Operate | Monitoring, retraining plan, runbook, owner on call (`mlops.md`) | Alerts tested; rollback to the rule rehearsed |

## Organization-level adoption

- **Choose the first use case** by value, feasibility (data exists, labels exist) and low risk. Internal efficiency (routing, prioritizing, deduplicating) beats high-stakes decisions about people for a first project.
- **Data foundations before models:** reliable event logging, a place to query history, clear ownership. Most stalled ML projects stall on data, not algorithms.
- **Ownership:** a product owner for the decision, an engineer for the code and pipeline, a data owner for each source, and on-call coverage once it is in production.
- **Build, buy or call an API:** hosted models and vendor features are fast to try; check data use terms, export of your data and labels, cost at full volume, and what happens when the vendor changes the model.
- **Governance proportionate to risk:** an inventory of models in use (owner, purpose, data, version, risk level), model cards, and a review step for models that affect people's opportunities, safety or money.
- **It is software:** tests for transforms and inference schemas, code review, CI, versioned artifacts. Notebooks are for exploration, not for production retraining.
- **Compute and money:** estimate training, serving and API costs before committing, and get approval for paid runs (module ground rule 6).

## Checks (done when)

- [ ] The decision to use a model (or not) is justified against a rule baseline with numbers.
- [ ] The prediction contract and data contract are written and agreed with the owners.
- [ ] Legal and ethical duties for decisions about people were raised and routed.
- [ ] The model sits behind a seam with a flag, timeout, fallback and version logging; shadow results were compared before any traffic was affected.
- [ ] Each phase ended with evidence and an explicit go or stop by the owner.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Model first, problem later | Prediction contract and rule baseline first |
| Labels that are not known at prediction time used as features | Point-in-time feature availability check |
| Model calls scattered through business logic | One seam with fallback and flag |
| No fallback, so an outage of the model breaks the feature | The rule as fallback; timeout |
| First project is a high-stakes decision about people | Start with low-risk internal decisions |
| Nobody owns it after launch | Named owner and on-call before rollout |
