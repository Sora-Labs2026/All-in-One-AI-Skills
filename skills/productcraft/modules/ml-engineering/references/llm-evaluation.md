# Evaluating LLM features: RAG, prompts and judges

Read this before changing a prompt, model, retrieval setting or tool in an LLM-powered feature, and whenever someone claims such a change "works better". It covers evaluation sets, retrieval and answer metrics, LLM-as-judge, harness hygiene, variance and regression testing. Evaluating Agent Skills themselves is in `../../builder-tools/references/skill-evaluation.md`.

## The evaluation set is the product spec

- **Source cases from reality:** production logs (de-identified), support tickets, user research, and domain experts. Add synthetic cases only to fill gaps, and keep them labeled as synthetic.
- **Cover the space:** common requests, hard ones, ambiguous ones, out-of-scope requests that should be declined, adversarial inputs (prompt injection, policy probes), and inputs where the right answer is "I don't know" or "not in the sources".
- **Each case has a checkable expectation:** a reference answer, required facts, required citations, a JSON schema, a unit test, or a rubric with concrete criteria.
- **Size:** 50 cases find gross problems; a few hundred are needed to detect differences of a few percentage points. For a pass rate near 80% on n independent cases, the 95% half-width is about `1.96 * sqrt(0.16 / n)`: 100 cases give about +/-8 points.
- **Split it:** a development set you iterate on, and a held-out test set you score only to confirm a change. Tuning prompts on the test set overfits it exactly as tuning hyperparameters does. Draw the split at random (stratified by case type), not by picking the cases that currently fail.
- **Version it** with the code, and record which version produced each score.

## What to measure

### Retrieval (for RAG)

| Metric | Meaning | Needs |
|---|---|---|
| Recall@k (context recall) | Share of the relevant chunks or documents that appear in the top k | Labeled relevant ids per question |
| Hit rate@k | Questions with at least one relevant item in the top k | Same |
| MRR, nDCG@k | Whether relevant items rank near the top | Same; graded relevance for nDCG |
| Precision@k (context precision) | Share of retrieved items that are relevant | Same |

Compute them deterministically from logged ids:
```bash
python3 <productcraft>/modules/ml-engineering/scripts/rank_metrics.py retrieval_run.jsonl --k 5,10,20 --ci --min recall@10=0.85
```
Label relevance at the document or passage level that survives re-chunking (document id plus section), or re-label after chunking changes. Always include a BM25-only baseline.

### Answers

| Property | Check |
|---|---|
| Correctness | Exact or normalized match for short answers; required facts present; reference comparison by a calibrated judge for long answers |
| Groundedness (faithfulness) | Every claim is supported by the provided sources; citations point to chunks that actually support the sentence |
| Completeness | Required points covered (checklist per case) |
| Abstention | Declines or says "not found" when sources lack the answer; does not decline answerable questions |
| Format | Schema validity, length limits, required sections, language |
| Safety and policy | No disallowed content, no leakage of system prompt or other users' data, injection attempts fail |
| Cost and latency | Tokens, cost per answer, time to first token and total time, per variant |

Prefer **atomic checks** (one property per check, pass or fail) over one blended 1-to-10 score: they are more reproducible, easier to calibrate and tell you what to fix. Grade **outcomes**, not phrasing: accept any wording that is correct and grounded.

## Graders, from cheapest to most expensive

1. **Code checks:** schema validation, regex for required fields, exact match after normalization (case, whitespace, number formats, units), unit tests for generated code, citation ids within the provided set.
2. **LLM-as-judge** with a rubric, for properties code cannot check (faithfulness, completeness, tone).
3. **Human review** for calibration, high-stakes domains and final sign-off.

### Building a trustworthy LLM judge

- One property per judge call, with a concrete rubric and examples of pass and fail; ask for a short justification, then a verdict in a structured output.
- Give the judge what it needs and nothing that biases it: the question, the sources (for groundedness), the reference (for correctness), and the candidate answer. Do not reveal which system produced which answer.
- Known biases: position (randomize order in pairwise comparisons or score both orders), verbosity (instruct not to reward length; check correlation of scores with length), self-preference (avoid using the model under test as its own judge where possible).
- **Calibrate against humans:** have people label 50 to 100 cases independently; report agreement (percent agreement and Cohen's kappa). Iterate the judge prompt until agreement on clear cases is high, and keep the human-labeled set to re-check the judge whenever its prompt or model changes.
- Test the judge on known negatives: an empty answer, "I don't know" to an answerable question, a fluent answer to a different question, an answer that contradicts the sources. All must fail.
- Treat the candidate text as data in the judge prompt; candidates can contain text that tries to instruct the judge.
- Pin the judge model version and settings; a judge change makes old and new scores incomparable.

Open-source evaluation frameworks (Ragas, DeepEval, promptfoo, Inspect and others) provide metric implementations and runners. Their LLM-based metrics are judges too: calibrate them on your data before trusting them.

## Harness hygiene

- Call the **same entry point** the product uses (same prompt assembly, retrieval, tools, model and settings). A re-implemented call measures something else.
- Separate **infrastructure failures** (timeouts, rate limits, parse failures of the harness, truncation at the output limit) from model failures. Record them in their own column and retry with backoff; never score them as wrong answers or silently drop them.
- Distinguish "the model said no answer" from "the system produced no answer".
- Save full traces per case (inputs, retrieved ids, prompts, outputs, judge inputs and outputs) so a surprising score can be explained without re-running.
- Check the harness with an oracle (reference answers should score near 100%) and a null system (empty or constant answers should score near 0%) before the first real run.
- Record the model identifier actually returned by the API, token usage and latency per call.
- Isolate state between cases for agentic features (fresh workspace, no leftover files or memory).

## Variance and comparisons

- LLM outputs vary between runs even with fixed settings, and some current models do not accept sampling parameters at all. Run each case more than once (3 to 5 repetitions for close comparisons) and report the mean with an interval.
- Compare variants **paired**: same cases, same repetitions. Use per-case scores with `compare_scores.py bootstrap` (paired bootstrap) or `compare_scores.py mcnemar` for pass/fail on the same cases. Cluster by source document or user when several cases share one.
- A change is an improvement only when the interval of the difference excludes zero and the size matters. Report what got worse as well as what got better, by case type.
- Many variants or metrics compared at once: adjust (`compare_scores.py adjust`) or confirm the winner on the held-out test set.

## Regression testing in CI

- Keep a fast smoke suite (20 to 50 cases, deterministic code checks first) that runs on every prompt, retrieval or model change.
- Run the full suite before release and on a schedule, since hosted models can change behavior even under the same name; pin model versions where the provider allows it.
- Thresholds in config: fail the build when a metric falls below the floor or drops more than the noise band relative to the last accepted run.
- Track cost of the evaluation itself; LLM-judged suites spend real money on every run. Get approval for large paid runs.

## Online evaluation and monitoring

- Log user feedback (ratings, corrections, follow-up questions, copy or accept actions) with the trace id; sample traces for weekly human review.
- Monitor rates of abstention, refusals, schema failures, citation failures, latency and cost per request.
- A/B test significant changes with a pre-registered primary metric (`statistical-inference.md`).
- Feed reviewed failures back into the development set; keep the test set stable for comparability.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Iterating prompts against the test set | Development set for iteration, test set to confirm |
| One run per case, small differences celebrated | Repetitions, paired intervals, practical thresholds |
| Uncalibrated judge scores reported as quality | Human agreement measured and reported |
| Timeouts and truncations scored as wrong | Separate infrastructure failures; retry with backoff |
| Evaluation calls a copy of the prompt, not the product path | Call the real entry point |
| Retrieval never measured separately | Retrieval metrics on labeled relevant ids, plus BM25 baseline |
| Only averages reported | Results by case type, including regressions |

## Done when

- [ ] A versioned evaluation set with development and held-out test splits covers normal, hard, out-of-scope, adversarial and no-answer cases.
- [ ] Code checks run first; LLM judges are calibrated against human labels with agreement reported.
- [ ] The harness separates infrastructure failures, saves traces and passed oracle and null checks.
- [ ] Comparisons are paired, repeated and reported with intervals, cost and latency.
- [ ] A smoke suite gates changes in CI, with the model version pinned or the drift risk noted.
