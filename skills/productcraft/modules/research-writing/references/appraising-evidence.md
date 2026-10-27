# Appraising papers and sources

Read this when the user asks whether a paper, report, article, dataset or web page can be trusted, how strong the evidence for a claim is, or wants a structured evaluation or score of a piece of scholarly work. Reasoning errors in arguments (one's own included) are in `critical-thinking-and-bias.md`; writing a formal review for a journal is in `peer-review.md`.

## Five-minute triage

Answer these before reading closely. Any "no" or "unknown" changes how much weight the source can carry.

1. **What kind of source is it?** Primary research, systematic review, narrative review, preprint, conference abstract, editorial, press release, news report, blog, vendor material, AI-generated summary.
2. **Where did it appear?** A journal indexed by the major databases and listed in the Directory of Open Access Journals if it is open access, versus a venue with signs of predatory publishing (promises of very fast acceptance, fees hidden until acceptance, unrelated scope, fake impact metrics). When in doubt, check the publisher's membership of COPE and the journal's indexing.
3. **Is it still standing?** Search for retraction, correction or expression of concern (publisher page, Crossref update notices, the Retraction Watch database, PubMed publication type). Look for post-publication discussion on PubPeer for papers that matter.
4. **Who paid and who benefits?** Funding statement, competing interests, author affiliations, sponsor control of data.
5. **Does the abstract match the results?** "Spin" (a conclusion stronger than the data, a secondary outcome promoted, a non-significant primary outcome reframed as a trend) is common. Read the results table before trusting the abstract.
6. **When?** Older evidence may be superseded; check for newer studies or reviews.

## Does the design fit the claim?

| Design | Can support | Main threats |
|---|---|---|
| Randomized controlled trial | Causal effect of an intervention in the trial population | Poor allocation concealment, unblinded outcome assessment, attrition, outcome switching, small size |
| Cohort (prospective or retrospective) | Associations, incidence, prognosis; causal claims only with strong design and adjustment | Confounding, loss to follow-up, exposure misclassification |
| Case-control | Associations for rare outcomes | Recall bias, control selection, confounding |
| Cross-sectional | Prevalence, associations at one time | No temporal order; reverse causation |
| Quasi-experimental (difference-in-differences, regression discontinuity, interrupted time series, instrumental variables) | Causal effects when their assumptions hold | Assumption violations (parallel trends, valid instrument, no manipulation at the cutoff) |
| Case series, case report | Hypotheses, rare harms | No comparison group |
| Laboratory, animal, in silico | Mechanisms, plausibility | Translation to humans or the real world; small samples; flexible analysis |
| Benchmark results (machine learning) | Performance on that benchmark under that protocol | Leakage, tuning on the test set, unreported variance across seeds, weak baselines |
| Systematic review and meta-analysis | Summary of a body of evidence | Only as good as the included studies and the search; heterogeneity; publication bias |

A well-conducted observational study can be more trustworthy than a badly run trial. Rank by design, then adjust for execution.

## Four kinds of validity

- **Internal:** is the effect real in this study? Randomization and concealment, blinding, confounding control, attrition, measurement.
- **External:** does it apply to the user's population and setting? Who was excluded, where and when it ran, adherence, dose.
- **Construct:** do the measures capture the concept? Validated instruments, surrogate versus patient-relevant or business-relevant outcomes, proxies.
- **Statistical conclusion:** are the inferences sound? Power, test choice, multiple comparisons, effect sizes with intervals. Test selection and reporting rules are in `../../ml-engineering/references/statistical-inference.md`.

## Statistical and reporting red flags

- Large effects from small samples, or many p-values just under 0.05.
- Many outcomes, subgroups or models with no correction and no pre-specification.
- Primary outcome in the paper differs from the registered one (compare with the trial registry or preregistration).
- Relative effects without absolute numbers ("halves the risk" from 2 in 10,000 to 1 in 10,000).
- Per-protocol results only, or missing data handled by dropping cases without justification.
- Baseline imbalance ignored; causal language ("leads to", "improves") from observational data.
- Prediction models without external validation, calibration or a comparison with a simple baseline.
- Figures without defined error bars; axes that start at a value chosen to exaggerate.
- Data and code "available on request" for a claim that matters.

Name a concern as a concern ("the dose-response figure shows identical noise in panels B and D; worth asking the authors"), not as an accusation of misconduct.

## Appraisal tools

Use a named tool when the appraisal will be reported: RoB 2 (randomized trials), ROBINS-I and ROBINS-E (non-randomized studies of interventions and exposures), QUADAS-2 (diagnostic accuracy), PROBAST (prediction models), AMSTAR 2 (systematic reviews), and the JBI or CASP checklists for other designs. Rate the body of evidence with GRADE (`literature-search-and-review.md`).

## Structured evaluation of a manuscript, thesis or proposal

When the user wants a scored evaluation, rate each dimension that applies on a 1-5 scale with written evidence; the scores are judgments, not measurements, and only comparable between raters who calibrated on the same examples.

| Dimension | 5 looks like | 2 looks like |
|---|---|---|
| Problem and question | Specific, important, answerable question with a stated gap | Vague aim, gap asserted without evidence |
| Use of prior work | Critical synthesis of the most relevant work, recent and foundational | Summary list, key work missing or misrepresented |
| Design and methods | Design fits the question; reproducible detail; threats addressed | Design cannot support the claims; key details missing |
| Data | Appropriate, adequate, documented sources and samples | Convenience data, size unjustified, provenance unclear |
| Analysis | Correct methods, assumptions checked, uncertainty shown, alternatives considered | Wrong tests, no uncertainty, selective analyses |
| Results and claims | Claims match the evidence; limitations stated | Overreach, causal claims without causal design |
| Writing and presentation | Clear structure, figures that stand alone, consistent terms | Hard to follow, figures unlabeled, inconsistent numbers |
| References | Accurate, verifiable, balanced | Errors, missing identifiers, citations that do not support claims |

For each dimension give the score, two or three specific strengths and weaknesses with locations, and the change that would raise the score. End with the three changes that matter most. Average scores only if the user asks, and show the per-dimension scores next to any average.

## Non-academic sources

- **Read laterally.** Before reading a page closely, find out who is behind it from other sites: what do independent sources say about the publisher or author?
- **Trace claims to the origin.** Follow quotes, statistics and images back to the first appearance: the dataset, the official report, the original study, the full interview. Coverage that cites "a study" without a link is a lead, not evidence.
- **Statistics:** confirm the definition, the denominator, the unit, the time period and the geography; check whether a number is a forecast or a measurement, and whether it is nominal or inflation-adjusted.
- **Independence:** ten articles repeating one press release are one source.
- **Dates:** prefer the publication and last-updated dates on the page; archive copies show what a page said on a given day.
- **Encyclopedias and AI answers** are maps to sources, not sources. An AI search summary that cites a link must be checked against that link: the page may not say what the summary claims.

## Communicate strength honestly

| Evidence | Wording |
|---|---|
| Several well-conducted studies or a high-certainty review agree | "shows", "consistently found" |
| Some good studies, some inconsistency or indirectness | "suggests", "is associated with" |
| Few or weak studies | "limited evidence", "early studies indicate" |
| None or conflicting | "unknown", "no good evidence either way" |

Say what would change the assessment ("a randomized trial in adults over 65 would settle the dose question").

## Checks (done when)

- [ ] Source type, venue, retraction status, funding and date checked for each source relied on.
- [ ] Design matched against the claim; the main validity threats named for the user's context.
- [ ] Red flags reported with locations and phrased as concerns.
- [ ] A named appraisal tool used where the appraisal will be published.
- [ ] Scores, if given, carry written evidence per dimension.
- [ ] The conclusion's wording matches the strength of the evidence.
