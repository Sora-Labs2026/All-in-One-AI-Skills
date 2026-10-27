# Research ideation and hypothesis generation

Read this when the user wants to brainstorm research directions, find a new angle on a problem, explain a puzzling observation, or turn a question into testable hypotheses and a study design. Machine-generated hypotheses mined from a labeled dataset are in `../../ml-engineering/references/llm-hypothesis-generation.md`; power and test selection are in `../../ml-engineering/references/statistical-inference.md`.

## Two modes, kept apart

Generating and judging use different thinking. Mixing them kills ideas early and lets weak ones through late.

1. **Diverge:** produce many options without evaluating them. Quantity and variety first.
2. **Cluster:** group related ideas, merge duplicates, name the themes.
3. **Converge:** evaluate the most promising few against explicit criteria, and pick next steps.

Tell the user which mode you are in. The user owns the direction; your job is to widen the options and then sharpen them.

## Start with context

Ask a few questions before generating, and stop once you could explain the problem to a colleague:

- What is known and what is the puzzle? Which observation does not fit the current picture?
- What has been tried, and why did it fail or stall?
- What constraints are real (equipment, data, ethics, time, money, skills) and which are habits?
- What would count as a good outcome: a paper, a decision, a prototype, a grant aim?

## Techniques for the divergent phase

| Technique | Prompt | Good for |
|---|---|---|
| Assumption reversal | List the field's core assumptions; what if one is false? | Stuck fields, contrarian angles |
| Anomaly hunting | Which results were dismissed as noise or outliers? | Hidden mechanisms |
| Scale shift | Look at the problem one level down and one level up (molecule, cell, organism, population; request, user, market) | Missing explanatory levels |
| Constraint change | Remove a constraint (unlimited data) or add one (no lab, one week) | Unblocking, cheap first tests |
| Cross-domain analogy | Which other field solved a problem with the same structure? | Transferring methods |
| Method recombination (SCAMPER) | Substitute, combine, adapt, modify, put to another use, eliminate, reverse a step of an existing method | Improving protocols and pipelines |
| Morphological matrix | List the problem's dimensions and options per dimension; scan combinations | Systematic coverage of a design space |
| Inversion | How would we make the outcome worse? Then reverse each answer | Finding levers |
| "What would have to be true?" | For a bold outcome, list the conditions; which is testable now? | Turning ambition into steps |

Generate in rounds of 10 to 20 options, then ask the user which directions to push. Mark ideas you have not checked against the literature as unchecked; never claim one is new.

## Novelty and grounding

Before calling an idea novel or a gap real, search (`literature-search-and-review.md`) and say what you searched and when. "I found no work combining A and B in OpenAlex and PubMed searches on 2026-10-27 (strings below)" is a finding; "this is unexplored" is not. Ideas presented as building on prior work must cite papers resolved by identifier in this session.

## From an observation to competing hypotheses

1. **Describe the phenomenon precisely:** what, where, when, how large, compared with what, measured how.
2. **List three to five explanations at different levels,** always including the mundane ones: measurement artifact, chance, confounding, selection. Mundane explanations are usually right and cheap to rule out.
3. **For each hypothesis write the mechanism, the assumptions it needs, and its predictions,** including predictions about things not yet measured.
4. **Find discriminating predictions:** observations where the hypotheses disagree. A test that every hypothesis predicts the same way teaches nothing.
5. **Rank** by testability, plausibility given current evidence, cost of the test, and value of the answer.

A small worked example. Observation: plants in greenhouse B grow 20 % less than in greenhouse A over six weeks (n = 12 trays each).

| Hypothesis | Mechanism | Discriminating prediction |
|---|---|---|
| H0 chance | Tray-to-tray variation | Difference shrinks or vanishes in a repeat with more trays |
| H1 light | B's glazing transmits less light | Light meter shows lower PAR in B; growth tracks position within B |
| H2 temperature | B runs cooler at night | Logger shows lower night temperature; growth gap largest in cold weeks |
| H3 seed lot | B received a different seed batch | Swapping lots between houses moves the gap with the lot |
| H4 measurement | B measured at a different time of day | Re-measuring both houses blind at the same hour removes the gap |

Testing H4 and H3 first is cheapest and rules out the explanations that would make the others moot.

## What makes a hypothesis good

- **Testable and falsifiable:** it names an observation that would contradict it.
- **Specific:** direction, and where possible size, of the effect, and the conditions under which it should hold.
- **Mechanistic where possible:** explains how, not only what.
- **Parsimonious:** no more moving parts than the evidence needs.
- **Consistent with established findings,** or explicit about which finding it challenges and why.
- **Worth knowing:** the answer changes a decision, a theory or the next experiment.

## Design the test

- **Comparison and controls:** what is the counterfactual? Include positive and negative controls where the method allows.
- **Randomization and blinding** wherever assignment and assessment can be randomized or hidden.
- **Replication:** distinguish biological or independent replicates from technical repeats; the unit of analysis is the unit that was randomized.
- **Sample size:** from a power analysis with an effect size justified by prior data or the smallest effect worth detecting, not from habit.
- **Pilot first** when the method, recruitment or measurement is new.
- **Write the analysis plan before the data:** primary outcome, test, covariates, exclusions, stopping rule. Preregister it (OSF, AsPredicted, a trial registry for trials) when the result will be published or will drive a decision.

Common designs and when they fit:

| Design | Fits when |
|---|---|
| Randomized experiment (A/B test, trial) | You control assignment |
| Factorial | Several factors and their interactions matter |
| Crossover or within-subject | Effects are reversible and carryover is manageable |
| Difference-in-differences | A change hit one group and not a comparable one, with parallel pre-trends |
| Regression discontinuity | Assignment follows a cutoff on a measured score |
| Interrupted time series | A change happened at a known time and there is a long series before it |
| Cohort or case-control | Exposure cannot be assigned; outcomes are common (cohort) or rare (case-control) |
| Ablation (computational) | Which component of a model or pipeline drives performance |

## Output for a hypothesis set

```markdown
## Phenomenon
<precise description, data source, size of effect>

## Hypotheses
| ID | Statement | Mechanism | Key assumptions | Prediction that would refute it |

## Discriminating tests (in recommended order)
| Test | Distinguishes | Cost and time | Expected result under each hypothesis |

## Evidence used
<papers resolved by identifier, user data; unchecked items marked>

## Open questions for the user
```

## Checks (done when)

- [ ] Divergent and convergent phases were kept apart, and the user chose the directions pursued.
- [ ] Novelty claims rest on a recorded search; cited prior work was resolved by identifier.
- [ ] Each hypothesis has a mechanism, assumptions and a refuting observation; mundane explanations are included.
- [ ] At least one test discriminates between the leading hypotheses; controls, replication, sample size and analysis plan are stated.
