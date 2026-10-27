# ML Engineering

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Build models and LLM features whose reported quality survives contact with production. This module covers classical ML with scikit-learn and gradient boosting, explainability, dimensionality reduction, survival analysis, forecasting and time-series ML, graph neural networks, deep learning with PyTorch, Lightning and Hugging Face Transformers, fine-tuning, reinforcement learning, statistical inference and Bayesian modeling, ML pipelines and MLOps, recommendation systems, cautious LLM-driven hypothesis generation, and LLM application engineering (RAG, prompts inside products, and their evaluation). Every topic ends in evidence: held-out scores with spread, compared against baselines.

**How the work is done** (done-when checks, planning, test-first, debugging, verification) lives in `../engineering-workflow/GUIDE.md`. Exploratory analysis, data wrangling and plotting live in `../data-engineering/GUIDE.md`. Writing Agent Skills and their prompts lives in `../builder-tools/GUIDE.md`; this module covers prompts inside applications.

## When to activate

- Training, tuning, evaluating, explaining, comparing or deploying a model; any claim that a model, prompt or retrieval change "is better".
- Statistical questions: test selection, A/B tests, p-values, effect sizes, power, regression interpretation, Bayesian models.
- Time-to-event, forecasting, time-series classification, graph learning, embeddings and 2-D maps of data, recommendations, RL environments and agents.
- Building or changing a RAG pipeline, an LLM-powered product feature, its prompts, tool schemas or evaluation suite; fine-tuning a language model.
- **Not for** pure data cleaning, SQL, dashboards or charts (`../data-engineering/GUIDE.md`), scientific simulation and numerical methods (`../scientific-computing/GUIDE.md`), domain models for biology, chemistry or medicine (`../life-sciences/GUIDE.md`), or the security review of an LLM feature (`../code-security-review/GUIDE.md`).

## Ground rules

1. **Evaluation honesty first.** Split the data the way the model will meet new data; fit every preprocessing step inside the training fold; tune on validation, score the test set once; report spread over folds, seeds or bootstrap resamples; always show the trivial baseline and the current production model. A number without these is not a result.
2. **Name the decision before the metric.** Choose metrics, thresholds and segments from what the prediction drives and what errors cost.
3. **Check versions, not memory.** These libraries change APIs often (scikit-learn, Transformers, TRL, PEFT, Lightning, PyG, PyMC, Gymnasium, forecasting models). Read the installed version (`python -c "import pkg; print(pkg.__version__)"`) and its documentation before writing code; state the version you assumed when you cannot check.
4. **Data is sensitive by default.** Minimize personal data, de-identify health data, never fabricate records, keep secrets out of code, prompts and notebooks (`../agent-safety/GUIDE.md`). Ask before sending data to a hosted model or API, and confirm its data terms with the owner.
5. **Licenses count.** Check licenses of libraries (for example GPL-3.0 scikit-survival), pretrained weights (some are non-commercial or gated) and training data before they enter a product. Record them.
6. **Compute and money need approval.** Estimate GPU hours, API tokens and evaluation costs before large runs, downloads of multi-gigabyte weights, or paid jobs, and ask first.
7. **Hands off production.** Do not deploy models, shift traffic, change retraining schedules, or run learned policies on physical hardware without explicit permission. Prepare commands and plans and hand them over.
8. **Report only what ran.** Scores, tests and checks that did not run are `NOT VERIFIED` with the reason. Never invent metrics, datasets, citations or results.

## Workflow

1. **Frame:** the prediction or estimate, its unit, when it is made, what it drives, the cost of each error type, and the success threshold.
2. **Audit the data:** row counts, label definition and delay, missingness, duplicates, entity and time structure. Run `scripts/split_check.py` on the splits.
3. **Baseline:** the trivial model and a simple strong model (linear, default gradient boosting, seasonal naive, BM25, popularity, the current prompt).
4. **Iterate on validation:** one change at a time, every run tracked with config, data version and seed.
5. **Confirm once:** freeze choices, score the test set, compare with `scripts/compare_scores.py`, inspect segments and errors.
6. **Ship safely:** versioned artifact, validation gates, monitoring plan, rollback path (`references/mlops.md`).

## Pick the references

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Any model evaluation, split, metric, comparison or leakage question | `references/evaluation-and-leakage.md` | Deployment-matching split checked; baselines and spread reported; test scored once |
| Tabular models, scikit-learn pipelines, tuning, gradient boosting, clustering, outliers | `references/classical-ml.md` | One pipeline holds all fitted steps; dummy, linear and boosting baselines on the same folds |
| Why a model predicts something; feature importance; SHAP; fairness probes | `references/explainability.md` | Output space and background stated; importance on held-out data; leakage suspects checked |
| PCA, UMAP, t-SNE; embedding maps; clustering embeddings | `references/dimensionality-reduction.md` | Reduction fitted inside the training fold when used as features; no inter-cluster distance claims |
| Time-to-event outcomes with censoring; churn timing, failure, clinical follow-up | `references/survival-analysis.md` | Censoring handled; assumptions checked; Uno's C or time-dependent AUC plus calibration on held-out subjects |
| Forecasting future values; foundation forecasting models; prediction intervals | `references/forecasting.md` | Rolling-origin backtest against seasonal naive; errors by horizon; interval coverage |
| Classifying, clustering or segmenting whole series; stream anomalies | `references/time-series-ml.md` | Split by recording or subject; ROCKET or 1-NN DTW baseline |
| Graph data: node, link or graph prediction | `references/graph-neural-networks.md` | Non-GNN baselines; link targets absent from input graph; 5+ seeds |
| Neural network training in PyTorch or Lightning, multi-GPU, debugging training | `references/deep-learning-pytorch.md` | Overfit-one-batch check; best checkpoint by validation; several seeds |
| Hugging Face models: loading, inference, tokenizers, encoder fine-tuning | `references/transformers.md` | License and revision pinned; chat template used; beats simple baselines |
| LoRA, QLoRA, full fine-tuning, SFT, DPO of language models | `references/fine-tuning.md` | Prompting and retrieval ruled out with numbers; beats best-prompted base on frozen test set; no regressions |
| RL environments and agents, Stable-Baselines3, vectorized environments | `references/reinforcement-learning.md` | `check_env` passes; 5+ seeds on separate eval environments; beats heuristic baseline |
| Test selection, assumptions, multiple comparisons, effect sizes, power, A/B tests | `references/statistical-inference.md` | Plan fixed before results; effect sizes with CIs; comparisons counted and adjusted |
| Regression with interpretation: OLS, GLMs, logistic, counts, mixed models, statsmodels | `references/statsmodels-regression.md` | Family fits the outcome; covariance matches dependence; diagnostics reviewed |
| Bayesian and hierarchical models, PyMC, ArviZ | `references/bayesian-modeling.md` | Prior predictive check; R-hat at most 1.01, no unexplained divergences; posterior predictive check |
| Experiment tracking, registries, pipelines, feature stores, deployment patterns, drift | `references/mlops.md` | Each version links code, data, config, environment and evaluation; gates as code; rollback tested |
| Recommendations, related items, ranking for users, conversational recommenders | `references/recommender-systems.md` | Time-based split; popularity baseline; coverage and segment metrics; constraints enforced outside the model |
| LLM-generated hypotheses from labeled data | `references/llm-hypothesis-generation.md` | Label-blind validated measurements; multiplicity adjusted over all hypotheses; confirmed on held-out data |
| RAG pipelines: ingestion, chunking, embeddings, hybrid search, reranking, access control | `references/rag-systems.md` | Recall@k and answer quality against a BM25 baseline; access filters server-side and tested |
| Evaluating LLM features, RAG answers, judges, regression suites | `references/llm-evaluation.md` | Versioned dev and held-out sets; calibrated judges; paired, repeated comparisons |
| Prompts, tool schemas and structured outputs inside an application | `references/prompt-design.md` | Untrusted input delimited; outputs validated in code; prompt versioned with evaluation results |

Several often apply together: a churn model touches `classical-ml`, `evaluation-and-leakage`, `explainability` and `mlops`; a support assistant touches `rag-systems`, `prompt-design` and `llm-evaluation`.

## Topic essentials

Use these when the reference is not needed; open it when a bullet raises a question.

### Evaluation
- Random splits only for independent rows; group splits for entities; time splits for the future. Duplicates and entity overlap across splits are leakage.
- Probabilities that drive decisions need calibration checks; thresholds are tuned on validation for the actual cost.
- Fold scores are not independent: compare with the corrected resampled t-test, paired bootstrap or McNemar, not a plain t-test.

### Models
- Tabular: gradient boosting first, linear models for interpretability; deep learning must beat both.
- Deep learning: pretrained backbones and transfer learning before training from scratch; debug by overfitting one batch.
- Language models: prompt, then retrieval, then fine-tuning; LoRA before full fine-tuning.
- Forecasting: seasonal naive and ETS as baselines; foundation models are backtested like any other model.
- Graphs: graph features plus boosting and label propagation before a GNN.
- RL: a heuristic baseline and 5+ seeds; time limits are truncations, not terminations.

### Statistics
- Welch's t-test by default; effect sizes with confidence intervals always; exact p-values.
- One pre-registered primary outcome; Holm or Benjamini-Hochberg for the rest; never peek-and-stop in A/B tests.
- Robust or cluster-robust standard errors when observations are heteroskedastic or grouped.
- Bayesian results are reported only with clean diagnostics and posterior predictive checks.

### LLM features
- Retrieval: structure-aware chunks with context, hybrid search fused by rank, a reranker, permission filters inside the query.
- Prompts: spec first, data delimited, schema-validated outputs, versioned in the repository, re-evaluated on every model change.
- Evaluation: code checks first, judges calibrated against humans, infrastructure failures separated from model failures, repeated paired runs.

## Helper scripts

All three are Python 3 standard library only, read only their inputs, never use the network, and print deterministic output. Exit codes: 0 success, 1 a check or threshold failed, 2 bad input. Each has `--help` and `--json`.

```bash
# Leakage check across splits: id, group and time overlap, duplicate rows, label copies, class balance
python3 <productcraft>/modules/ml-engineering/scripts/split_check.py \
  --split train=train.csv --split valid=valid.csv --split test=test.csv \
  --id order_id --group customer_id --time created_at --target churned

# Honest comparisons: corrected CV t-test, paired or cluster bootstrap, exact McNemar, Holm/BH adjustment
python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py cv --a 0.81,0.79,0.83,0.80,0.82 --b 0.84,0.80,0.85,0.83,0.83 --folds 5
python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py bootstrap --csv per_example.csv --a-col a --b-col b --cluster-col user_id
python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py adjust --p 0.01,0.04,0.03

# Ranking metrics for retrieval and recommendations: hit, precision, recall, MRR, nDCG, MAP at k; coverage; CIs
python3 <productcraft>/modules/ml-engineering/scripts/rank_metrics.py run.jsonl --k 5,10 --ci --min recall@10=0.8
```

`<productcraft>` is the folder where the ProductCraft skill is installed. A clean `split_check.py` result does not prove the absence of leakage: it cannot see features computed with future data or preprocessing fitted on all rows. Tests: `python3 -B -m unittest discover -s <productcraft>/modules/ml-engineering/tests -v`.

## What to report

Add these to the workflow module's report and `../../assets/review-template.md`:
- The framing: prediction or estimate, unit, decision, error costs, success threshold.
- Split method and the `split_check.py` summary; known leakage risks not checked.
- Baselines and candidates on the same folds or test set, with spread (folds, seeds or bootstrap intervals), and the comparison method used.
- Segment results, including any that got worse; calibration where probabilities are used.
- Versions of key libraries and models, data snapshot, seeds, and licenses of models and data.
- Compute and API cost actually spent; anything left `NOT VERIFIED` and why.
- For deployments: gates, monitoring, rollback path and the commands the user still has to run.

## Working with other ProductCraft modules

- `../engineering-workflow/GUIDE.md`: tracks, done-when checks, debugging and verification for the code around models.
- `../data-engineering/GUIDE.md`: exploratory analysis, data wrangling, SQL, large-data engines and charts.
- `../engineering-practices/GUIDE.md`: API contracts for model services, resilience of model calls, performance, observability, CI/CD and dependencies.
- `../code-security-review/references/vulnerability-classes.md` (LLM and agent risks): prompt injection, output handling, excessive agency, vector store isolation.
- `../launchguard/GUIDE.md`: before launching a feature that exposes models or user data.
- `../legal-ready/GUIDE.md`: personal data, consent, model and data licenses, automated decisions.
- `../cloud-infrastructure/GUIDE.md` and `../scientific-computing/GUIDE.md`: GPU infrastructure, clusters and job scheduling.
- `../research-writing/GUIDE.md`: writing up analyses, verified citations, study design.
- `../life-sciences/GUIDE.md`: domain models and data for biology, chemistry and medicine.
- `../builder-tools/GUIDE.md`: prompts and evaluation for Agent Skills and MCP servers.
