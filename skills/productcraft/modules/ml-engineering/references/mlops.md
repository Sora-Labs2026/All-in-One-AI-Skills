# ML pipelines and MLOps

Read this when a model must be trained repeatably, tracked, versioned, promoted, deployed, monitored or retrained: experiment tracking, data and model versioning, training pipelines and orchestration, feature stores, validation gates, shadow and canary releases, drift monitoring. General CI/CD, observability and release practice live in `../../engineering-practices/references/ci-and-release.md` and `../../engineering-practices/references/observability.md`; infrastructure in `../../cloud-infrastructure/GUIDE.md`.

## Start small

Match the machinery to the stage. Most teams need levels 1 and 2 long before anything else.

| Level | What exists | Add when |
|---|---|---|
| 1. Reproducible run | Training script with a config file, pinned dependencies, fixed seeds, data snapshot reference, metrics written to a file | Always |
| 2. Tracked experiments and a registry | Experiment tracker (MLflow, Weights & Biases or similar), model registry with versions and aliases | More than one person or more than a handful of runs |
| 3. Pipeline | Orchestrated steps (validate data, build features, train, evaluate, register) with caching and retries | Scheduled retraining or multi-step data preparation |
| 4. Automated promotion and monitoring | Validation gates, shadow or canary deployment, drift and performance monitoring, retraining triggers | The model drives a product decision continuously |

## Reproducibility contract

Every model artifact must answer: which code (git commit), which data (snapshot id or hash), which config (all hyperparameters), which environment (lockfile, container image digest, library versions), which random seeds, and which evaluation results. If any of these is missing, the model cannot be rebuilt or audited.

- Configs in files (YAML or TOML, or Hydra-style composition), not in notebooks or command history.
- Data versioning: DVC, lakeFS, Delta or Iceberg table versions, or immutable dated snapshots in object storage. Large data never goes into git.
- Containers pin the CUDA, driver-compatible framework and Python versions for training and serving.

## Experiment tracking

```python
import mlflow

mlflow.set_experiment("churn-model")
with mlflow.start_run(run_name="hgb-v3") as run:
    mlflow.log_params(cfg)                                   # every hyperparameter
    mlflow.set_tags({"git_commit": commit, "data_snapshot": snapshot_id})
    model = train(cfg, train_df)
    metrics = evaluate(model, valid_df)                      # validation only during development
    mlflow.log_metrics(metrics)
    mlflow.sklearn.log_model(model, name="model",          # older MLflow: artifact_path=
                             input_example=valid_df.head(3), registered_model_name="churn")
```

- Log every run, including failures and abandoned ideas; selection bias across invisible runs is real.
- Log the evaluation dataset identity next to the metrics, so numbers from different test sets are never compared.
- Register models with a signature (input schema) and an input example; the serving side validates against it.
- MLflow model stages (Staging, Production) were deprecated in favor of **aliases** (for example `@champion`, `@challenger`) and tags in 2.9+; MLflow 3 continues that direction. Check the installed version.
- The tracking server holds artifacts that may contain data samples; apply access control and do not log personal data.

## Pipelines and orchestration

- Each step is a function of explicit inputs to explicit outputs, idempotent and re-runnable: rerunning with the same inputs gives the same outputs and does not duplicate side effects.
- Typical steps: ingest snapshot, validate data, build features, split, train, evaluate against gates, register, (optionally) deploy to shadow.
- Orchestrators: Airflow, Prefect, Dagster, Kubeflow Pipelines, Argo Workflows, or a managed equivalent in the cloud you already use. Pick the one the organization already runs; the differences matter less than having one.
- Cache expensive steps by content hash of their inputs.
- Fail loudly: a data validation failure stops the pipeline and alerts; it does not train on bad data.

## Data validation

Check at ingestion and before training (pandera, Great Expectations, or hand-written assertions):
- Schema: columns, types, allowed categories, nullability.
- Ranges and distributions: value bounds, missing-value rates, category frequencies, row counts compared with the previous snapshot.
- Label sanity: class balance, label delay (are recent rows labeled yet?), duplicates.
- Leakage: run `python3 <productcraft>/modules/ml-engineering/scripts/split_check.py` on the produced splits (see `evaluation-and-leakage.md`).

## Feature stores and training-serving skew

Training-serving skew (features computed differently offline and online) is the most common production ML bug.
- Compute features with one implementation used by both training and serving, or a feature store (Feast or a platform equivalent) that serves the same definitions offline and online.
- Point-in-time correct joins for training data: each training row gets feature values as they were at its prediction time, never later.
- Log the features actually used at serving time and compare their distributions with training features.

## Validation gates before promotion

A candidate replaces the current model only if, on the same frozen evaluation set and slices:
- It beats the current model on the primary metric by more than the run-to-run spread (`compare_scores.py` for paired comparisons).
- No important slice regresses beyond an agreed tolerance.
- Calibration, latency (p95, p99), memory and cost per prediction are within budget.
- Input schema and output contract match the serving interface.
- Fairness checks agreed with the owner pass, where relevant.

Write the gates as code in the pipeline, with thresholds in config, and store the gate report with the model version.

## Deployment patterns

| Pattern | Use | Note |
|---|---|---|
| Batch scoring | Predictions needed on a schedule (daily churn scores) | Simplest; write outputs with model version and timestamp |
| Online service | Low-latency predictions per request | Validate inputs; timeouts and fallbacks for the model call |
| Shadow | New model scores live traffic, results logged, not used | Compare predictions and latency with no user impact |
| Canary | Small share of traffic gets the new model | Watch guardrail metrics; automatic rollback criteria |
| A/B test | Measure business impact | Design per `statistical-inference.md` (sample size, no peeking) |

- Keep the previous model version deployable for instant rollback. Rollback must not depend on retraining.
- Pickle-based model files execute code on load: load only artifacts from your own registry. Prefer safer formats (ONNX, safetensors, framework-native formats) for serving where available.
- Production deploys, traffic shifts and retraining schedules change live systems: prepare them, and run them only with the user's explicit permission.

## Monitoring

| Signal | Detects | How |
|---|---|---|
| Service health | Errors, latency, throughput | Standard service metrics and alerts |
| Input data quality | Missing values, schema changes, broken upstream features | Validation on live inputs, rate of fallbacks |
| Input drift | Population change | Distribution distance per feature (PSI, Jensen-Shannon, KS) against the training reference; alert on sustained change, not single spikes |
| Prediction drift | Model behavior change | Distribution of scores and predicted classes over time |
| Performance | Actual quality | Metrics on labeled outcomes as labels arrive; proxy metrics while waiting |
| Business guardrails | Harm | Complaints, overrides by humans, downstream KPIs |

- Drift is a prompt to look, not proof of degradation; performance on fresh labels is the ground truth.
- Delayed labels: track the delay and evaluate on matured windows.
- Feedback loops: a model that changes what data is collected (recommendations, fraud blocks) biases future training data. Keep a small randomized holdout or exploration share where the owner accepts it.
- Open-source drift tooling (Evidently, NannyML, whylogs) helps; dashboards need owners and runbooks.

## Retraining

- Retrain on a schedule matched to how fast the data changes, or on a trigger (sustained drift plus a performance drop), always through the same pipeline and gates.
- Never auto-promote without the gates; consider human approval for high-impact models.
- Keep training data windows and their reasons in the run metadata.

## Documentation

A model card for each production model: intended use and users, out-of-scope uses, training data and its period, evaluation results by slice, known limitations, fairness considerations, owner, and monitoring links. Store it with the registry entry.

## Security and privacy

- Credentials for data stores, trackers and registries come from a secret manager or environment, never code or notebooks (see `../../agent-safety/GUIDE.md`).
- Minimize personal data in features and logs; set retention on training snapshots; honor deletion requests in training data and derived features where the law requires it.
- Restrict who can register and promote models; promotion is a production change.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Notebook-only training | Scripted pipeline with config and tracked runs |
| Model cannot be rebuilt | Commit, data snapshot, config, environment and seeds recorded |
| Feature code duplicated for serving | One feature implementation or a feature store |
| Promotion on a single metric | Gates with slices, latency, cost and spread |
| Drift alert floods | Sustained-change thresholds, owners and runbooks |
| Rollback by retraining | Keep the previous version deployable |

## Done when

- [ ] Each model version links code commit, data snapshot, config, environment and evaluation report.
- [ ] Data validation and leakage checks run in the pipeline and stop it on failure.
- [ ] Promotion gates are code with thresholds in config; the report is stored with the version.
- [ ] Rollback to the previous version is tested.
- [ ] Monitoring covers service health, input quality, drift and performance, with owners.
- [ ] Production changes were prepared and handed over, or run only with explicit permission.
