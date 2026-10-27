# Critical thinking and bias checks

Read this when judging an argument or conclusion, including your own analysis before you report it: a claim in a paper or proposal, a "the data shows" statement, a recommendation the user will act on. Judging sources is in `appraising-evidence.md`; stress-testing a plan or decision is in `stress-tests.md`.

## Pin the claim down

Most disagreements dissolve or sharpen once the claim is stated precisely. Rewrite it in one sentence and classify it:

| Type | Example | What would test it |
|---|---|---|
| Causal | "The new onboarding raised retention" | A comparison that rules out other causes (experiment, credible quasi-experiment) |
| Predictive | "Demand will double next year" | A forecast with an interval, checked later against outcomes |
| Comparative | "Method A is more accurate than B" | Same data, same protocol, variance across runs, a margin that matters |
| Existence or absence | "No alternative meets our needs" | A documented search for alternatives |
| General | "Microservices always speed teams up" | One solid counterexample refutes it |
| Quantitative | "This saves 200 hours a quarter" | The calculation, its inputs and their sources |

Then ask: what observation would show the claim is false? A claim no observation could contradict ("it may help in some cases") says nothing; ask for a measurable version.

## Look for the alternative explanations

Before accepting "X caused Y", rule out each of these, or say you could not:

- **Chance:** small samples, many comparisons, a noisy metric.
- **Selection:** who got into the data, who dropped out, which cases were looked at (survivorship).
- **Measurement:** the instrument, definition or logging changed at the same time.
- **Confounding:** a third factor drives both (seasonality, a concurrent launch, age, severity).
- **Reverse causation:** Y produced X.
- **Regression to the mean:** extreme starting values drift back on their own; interventions started at a low point look effective.
- **Simpson's paradox:** the overall trend reverses inside every subgroup because group sizes differ.
- **Base rates:** a rare condition with a decent test still gives mostly false positives.

A worked base-rate check, since the intuition fails so reliably: prevalence 1 %, sensitivity 90 %, specificity 95 %. Of 10,000 people, 100 have the condition and 90 test positive; of 9,900 without it, 495 test positive. A positive result means the condition with probability 90 / (90 + 495), about 15 %, not 90 %.

## Biases in the person doing the analysis

| Bias | Sign | Countermeasure |
|---|---|---|
| Confirmation | Only supporting evidence searched for or reported | Search explicitly for disconfirming evidence and report it |
| Anchoring | The first number or framing persists despite new data | Re-estimate from scratch before looking at the earlier figure |
| Availability | One vivid recent case drives the conclusion | Look at the base rate or the full distribution |
| Motivated reasoning | The conclusion matches what someone hoped for | Write down beforehand what result would change the decision |
| Sunk cost | "We already invested so much" as a reason to continue | Judge only future costs and benefits |
| Hindsight and outcome bias | A decision judged by its outcome alone | Judge the decision by what was knowable when it was made |
| Overconfidence | Intervals too narrow, no uncertainty stated | State ranges; check past forecasts against outcomes |
| Narrative fallacy | A tidy story explains everything after the fact | Ask what the story predicted before the data arrived |
| Planning fallacy | Estimates from the best case | Use reference classes: how long did similar work take? |
| Bandwagon and authority | "Everyone does it", "a big company does it" | Ask whether their constraints are ours |

## Biases built into research practice

- **Flexible analysis** (many defensible choices tried until one "works"), p-hacking and HARKing (hypotheses written after seeing results). Countermeasures: preregistration or an analysis plan written before the data are seen, blind analysis, reporting every analysis run, and sensitivity or multiverse analyses that show how conclusions depend on choices.
- **Publication bias:** null results are less often published, so published effects run high. Look for registries, preprints and reports of null findings.
- **Outcome switching:** compare the reported primary outcome with the registered one.

## Fallacies worth naming in technical arguments

Naming a fallacy shows the argument does not support the conclusion; it does not show the conclusion is false.

| Fallacy | Shape | Better question |
|---|---|---|
| Post hoc | B followed A, so A caused B | What else changed at the same time? |
| Ecological | A group-level pattern applied to individuals | Is there individual-level data? |
| Prosecutor's fallacy | P(evidence given innocence) confused with P(innocence given evidence) | What is the prior probability? |
| False dichotomy | "Either we rewrite or we stay stuck" | What are the other options, including doing less? |
| Straw man | Attacking a weaker version of the other view | Can you state their view so they would agree with it? |
| Appeal to authority | "The expert said so" | What evidence did the expert rely on? |
| Argument from ignorance | "Not shown to be harmful, so safe" | Was it studied with enough power to see harm? |
| Moving goalposts | New criteria appear after the old ones are met | What were the criteria agreed in advance? |
| Texas sharpshooter | Pattern found after slicing data many ways | Was the pattern predicted, and does it replicate? |

## Self-check before stating a conclusion

Run this on your own findings before reporting them, and include the short version in the report when the stakes are high:

1. State the conclusion in one sentence, with its scope (population, period, conditions).
2. List the evidence for it and the strongest evidence against it.
3. Name the most plausible alternative explanation and why it is less likely, or say it cannot be excluded.
4. Say what result would have changed your mind, and whether you looked for it.
5. Give a confidence level in words (high, moderate, low) with the main reason.
6. List what you did not check (`NOT VERIFIED`).

## Giving critique to a person

- Restate their position in its strongest form and confirm you have it right.
- Criticize the reasoning or the evidence, never the person; point to the exact sentence, figure or step.
- Pair each problem with what would fix it or how to test it.
- Concede what holds up. Do not stack minor objections to make a sound position look weak.
- Leave the decision with the user.

## Checks (done when)

- [ ] The claim is restated precisely and classified, with what would falsify it.
- [ ] Alternative explanations were checked or explicitly left open.
- [ ] Analyst biases relevant to the case were considered, with the countermeasure used.
- [ ] The conclusion's confidence and its unchecked parts are stated.
