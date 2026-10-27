# Automated hypothesis generation on labeled data (use with caution)

Read this when someone wants a language model to propose and test explanations for patterns in a labeled dataset: "what distinguishes fraudulent from genuine reviews?", "which features of a headline predict more clicks?", "what separates churned from retained accounts in support transcripts?". Treat the output as **candidate hypotheses for follow-up**, never as findings. Manual hypothesis formulation and study design for research belong to `../../research-writing/GUIDE.md`.

## When it is worth it, and when not

Useful when:
- Inputs are text or mixed text and tabular fields, where a human-readable pattern ("mentions a specific person by name", "uses first-person plural") is the desired output.
- You want interpretable rules to inspect, debug a model, or seed a properly designed study.

Use something simpler when:
- Features are numeric or categorical columns: subgroup discovery, decision trees or rule learners, and SHAP interactions on a gradient-boosted model (`explainability.md`) are cheaper, deterministic and statistically better understood.
- The goal is prediction accuracy: a fine-tuned classifier or embeddings plus a linear model will usually beat hypothesis-conditioned prompting.
- The question is causal: generated hypotheses describe associations in this dataset.

## The method

1. **Split first.** Train (to generate and refine hypotheses), validation (to select among them), test (touched once, for the final estimate). Group by author, user or source so near-duplicate examples do not cross splits (`evaluation-and-leakage.md`).
2. **Generate.** Show the model small batches of labeled training examples and ask for a few specific, testable hypotheses, each stated as an observable property of an input and its expected direction ("Reviews that mention the hotel's full name are more often deceptive").
3. **Operationalize.** Turn each hypothesis into a measurement on any single example: preferably code (a regex, a count, a parser), otherwise a narrow annotation prompt that returns yes, no or unclear for one example. The measurement must not see the label.
4. **Validate the measurement.** Check the annotator against human labels on a sample (agreement and Cohen's kappa); drop hypotheses whose measurement is unreliable.
5. **Test.** For each hypothesis, compare outcome rates between examples with and without the property on training data, with an effect size and a confidence interval.
6. **Refine.** Collect examples that the current bank explains poorly and ask for new hypotheses from those; replace weak hypotheses. Cap the number of rounds in advance.
7. **Select on validation, confirm on test.** Re-measure the chosen hypotheses on validation data; adjust for every hypothesis tested; report only those that hold, then estimate effects once on the test split.
8. **Review.** A domain expert reads each surviving hypothesis with examples for and against it and judges whether it is plausible, trivial, or an artifact of data collection.

```python
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest

def test_hypothesis(has_property, labels):
    """has_property: list of 0/1/None per example (None = unclear); labels: 0/1 outcome."""
    pairs = [(p, y) for p, y in zip(has_property, labels) if p is not None]
    with_p = [y for p, y in pairs if p == 1]
    without = [y for p, y in pairs if p == 0]
    if min(len(with_p), len(without)) < 20:
        return None                                   # too few examples to say anything
    stat, pval = proportions_ztest([sum(with_p), sum(without)], [len(with_p), len(without)])
    return {"n_with": len(with_p), "rate_with": sum(with_p) / len(with_p),
            "rate_without": sum(without) / len(without), "p": pval}

results = {h.id: test_hypothesis(measure(h, valid_rows), valid_labels) for h in bank}
tested = {k: v for k, v in results.items() if v}
reject, p_adj, _, _ = multipletests([v["p"] for v in tested.values()], method="fdr_bh")
```

`measure` is your code check or annotation prompt; record its version and the model that ran it.

## Safeguards that are not optional

- **Multiplicity.** Generating many hypotheses and testing them on the same data guarantees some false positives. Count every hypothesis ever tested (including discarded rounds), adjust (Benjamini-Hochberg for screening), and confirm on data not used for generation or selection.
- **Leakage through the model's knowledge.** Public datasets and well-known benchmark tasks may be in the model's training data; generated "insights" can be recall of published results rather than discovery. Prefer private or recent data, and say when a dataset is public.
- **Label leakage in measurement.** The annotation prompt must see only the input, never the label or other examples' labels.
- **Annotator bias.** A model annotating "sounds deceptive" or "is emotional" brings its own biases, including stereotypes about groups and dialects. Prefer concrete, observable properties, validate against humans, and check whether a hypothesis is a proxy for a demographic attribute before anyone acts on it.
- **Confounding and data artifacts.** Patterns often reflect how data was collected (source site, time period, annotator) rather than the phenomenon. Check hypotheses within strata of source and time.
- **No invented support.** Hypotheses "from the literature" must cite real papers that the user or a search verified (identifier lookup); the model must not produce references from memory (`../../research-writing/GUIDE.md`).

## Reproducibility, cost and privacy

- Pin the model version, prompts and sampling settings; cache every model response keyed by prompt and input so reruns are identical and cheap; record the dataset version and split seed.
- Estimate cost before running: examples x hypotheses x rounds x tokens. Annotation over large datasets is the expensive part; sample for screening, then measure on full splits only for survivors. Get approval for paid runs.
- Sending records to a hosted model shares them with a third party. De-identify, minimize fields, and confirm the owner's data terms; for health or other sensitive data, use approved environments only and follow HIPAA or GDPR duties.

## Reporting

For each surviving hypothesis: the statement, how it was measured (code or prompt version, annotator agreement), counts with and without the property, outcome rates with confidence intervals on the test split, the adjusted p-value with the total number of hypotheses tested, examples for and against, and the expert's judgment. State plainly that these are exploratory associations that need confirmation in an independent sample or a designed study.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Hypotheses reported as discoveries | Label them exploratory; confirm on new data |
| Selecting and estimating on the same data | Generate on train, select on validation, estimate on test |
| Vague properties ("is suspicious") | Observable, measurable properties; code checks where possible |
| Annotation prompt sees labels | Measurement from the input only |
| Hundreds tested, a handful reported without adjustment | Count everything; adjust; report the count |
| Results on a public benchmark presented as novel | Note possible pretraining exposure; prefer private data |

## Done when

- [ ] Splits are grouped and fixed before generation; the test split was used once.
- [ ] Every hypothesis has a validated, label-blind measurement.
- [ ] Effects come with intervals, multiplicity is adjusted over all hypotheses tested, and the count is reported.
- [ ] A domain expert reviewed the survivors; sensitive-attribute proxies were checked.
- [ ] Model, prompts, cached responses and data versions are recorded; data sharing was approved.
