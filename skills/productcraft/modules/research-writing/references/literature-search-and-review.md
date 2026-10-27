# Literature search and review

Read this when the user wants to know what has been published on a question: a background section, a narrative review, a systematic or scoping review, a meta-analysis, a state-of-the-art survey or a quick evidence check. API details for each database are in `scholarly-apis.md` and `biomedical-and-preprint-apis.md`; judging the papers you find is in `appraising-evidence.md`.

## The rule that overrides everything else

Every work you cite or include comes from a search result, a file the user supplied or an identifier you resolved in this session. Never fill a review with papers recalled from memory, however confident the recall feels: titles, years, venues and DOIs recalled by a language model are often wrong in ways that look right. Record where each record came from, and mark anything you could not check `NOT VERIFIED`.

## Pick the review type first

The type decides how much method you owe the reader.

| Type | Use when | Method you must show | Reporting guide |
|---|---|---|---|
| Narrative or critical review | Background for a paper, an expert overview, a teaching text | Sources and dates searched, selection logic, an explicit "not systematic" statement | None formal; be transparent |
| Systematic review | A focused question where completeness and bias control matter (does X work, how often does Y happen) | Protocol, registered where possible; full search strings; dual screening; risk of bias; certainty of evidence | PRISMA 2020, PRISMA-S for the search |
| Scoping review | Mapping what exists, concepts or gaps, before or instead of a systematic review | Protocol; search strings; charting form; no risk-of-bias requirement | PRISMA-ScR |
| Rapid review | A decision needs evidence within weeks | The shortcuts taken (one database, single screening) stated as limitations | Report shortcuts explicitly |
| Umbrella review | Many systematic reviews already exist | Search for reviews; appraise them (AMSTAR 2); handle overlap of primary studies | PRISMA adapted |
| Meta-analysis | Studies are similar enough in population, intervention, comparator and outcome to pool | Everything for a systematic review plus a statistical analysis plan | PRISMA 2020 |

If the user says "systematic" but has a week and no second reviewer, say what a systematic review requires and offer a rapid or scoping review with its limits stated. Do not label a review systematic when its method is not.

## Frame the question

- Interventions: PICO (population, intervention, comparator, outcome); add timing and setting when they matter.
- Exposures and risk factors: PECO (exposure instead of intervention).
- Scoping questions: PCC (population, concept, context).
- Qualitative evidence: SPIDER (sample, phenomenon of interest, design, evaluation, research type).
- Technical surveys (methods, algorithms, systems): task, method family, evaluation setting, metric.

Write the eligibility criteria before searching: study designs, populations, languages, date range, publication types (peer reviewed, preprints, theses, reports). Criteria chosen after seeing results invite bias.

For systematic reviews in health, register the protocol on PROSPERO before screening starts (check its current eligibility rules); for other fields use OSF Registries. PRISMA-P lists what a protocol contains.

## Build the search

1. Split the question into two to four concept blocks (for example "condition", "intervention", "study design").
2. For each block collect synonyms, spelling variants (tumor and tumour), abbreviations, older terms and the database's controlled vocabulary (MeSH in PubMed, Emtree in Embase). Combine terms with OR inside a block and blocks with AND.
3. Use truncation (`therap*`), phrase quotes and proximity operators where the database supports them; syntax differs per database and platform, so translate the strategy rather than pasting it.
4. Avoid NOT unless you can show it removes only irrelevant records; it silently drops relevant ones.
5. Test sensitivity with a seed set: five to ten papers you know are relevant. If the search misses any, find out which term was missing.
6. For systematic reviews, have the strategy peer reviewed (the PRESS checklist is the usual tool) or at least reviewed by the user.
7. Record for every source: database, platform or API, the exact string, filters, the date run and the number of results. This is what PRISMA-S asks for and what makes the search repeatable.

Search more than one source. Typical combinations:

| Field | Core sources (licensed ones marked L) |
|---|---|
| Biomedicine and health | PubMed/MEDLINE, Embase (L), Cochrane CENTRAL, CINAHL (L), trial registries, Europe PMC, medRxiv |
| Multidisciplinary | OpenAlex, Scopus (L), Web of Science (L), Crossref, Semantic Scholar |
| Computer science | arXiv, DBLP, ACM Digital Library, IEEE Xplore, OpenReview, Semantic Scholar |
| Physics and mathematics | arXiv, INSPIRE-HEP, NASA ADS, zbMATH Open, MathSciNet (L) |
| Social and behavioral sciences | ERIC, PsycINFO (L), SSRN, OpenAlex, national statistics and policy repositories |
| Grey literature | Trial registries, theses repositories, government and agency reports, conference proceedings, preprint servers |
| Patents | See `patent-search.md` |

Google Scholar has broad coverage but no API, results that cannot be reproduced exactly, and terms that forbid automated querying. Use it by hand for citation chasing and spot checks, and record that you did.

When a needed database is licensed and not reachable from here, give the user the translated search string and ask them to run it and export the results (RIS or BibTeX). Say in the report which sources were and were not searched.

## Citation chasing

After the database search, check the reference lists of included studies (backward) and the works that cite them (forward). OpenAlex and Semantic Scholar expose both directions; Crossref exposes outgoing references where publishers deposit them. Record chasing as a separate source in the flow diagram.

## Screen

1. Deduplicate first: exact DOI match, then normalized title plus year plus first author, then a manual look at near-duplicates (preprint and published versions of the same study are the same study; keep the published one and note the preprint).
2. Pilot the criteria on 50 to 100 records with the user; refine wording until two screeners agree.
3. Screen titles and abstracts, then full texts. Record one exclusion reason per full text.
4. For a systematic review, two people screen independently and resolve disagreements; report agreement (percent or Cohen's kappa). An agent can act as one screener only if the user accepts that and the second screener is a person.
5. Machine-assisted screening (active learning tools such as ASReview, or a language model ranking records) may order the queue. It may not exclude records on its own unless its recall was validated on the review's own data and the stopping rule is reported.

Keep the screening record as a table: record ID, source, decision at each stage, reason, screener.

## PRISMA flow numbers

The flow diagram must add up. Check the arithmetic before drawing it:

```text
identified (databases + registers + other methods)
  - duplicates removed - removed by automation tools (state which) = screened
screened - excluded at title/abstract = reports sought
reports sought - not retrieved = assessed for eligibility
assessed - excluded with reasons (listed with counts) = included reports
included reports -> included studies (one study can have several reports)
```

Draw it with the official PRISMA 2020 template or as a Mermaid flowchart (`diagrams-and-mermaid.md`), and keep the counts in the same file as the screening table so they cannot drift apart.

## Extract and appraise

- Design an extraction form before extracting: study ID, design, setting, population, intervention or exposure, comparator, outcomes with definitions and time points, results with units and uncertainty, funding and conflicts, notes. Pilot it on three studies.
- Extract from the paper, citing page, table or figure for each number. Double-extract the main outcome. When data are missing, list what to ask the study authors for; do not estimate silently.
- Assess risk of bias per study and per outcome with the tool that fits the design: RoB 2 for randomized trials, ROBINS-I for non-randomized studies of interventions, ROBINS-E for exposures, QUADAS-2 for diagnostic accuracy, PROBAST for prediction models, AMSTAR 2 for systematic reviews, JBI or CASP checklists for other designs. Support each judgment with a quote or location.
- Rate certainty of the body of evidence with GRADE when the review informs a decision: start at high for randomized trials and low for observational studies, then rate down for risk of bias, inconsistency, indirectness, imprecision and publication bias, and up for large effects, dose-response or confounding that would shrink the effect. Present it in a summary-of-findings table.

## Synthesize

- Organize by question or theme, not one paragraph per study. Each paragraph states what the evidence shows across studies, how strong it is, and where studies disagree and why (population, dose, measurement, risk of bias).
- Without pooling, follow the SWiM guidance (synthesis without meta-analysis): state how studies were grouped, which standardized metric was used and how certainty was judged. Vote counting by "significant or not" is not a synthesis.
- Pool only studies that answer the same question with compatible outcomes. Use a random-effects model by default, report the pooled estimate with its confidence interval, the heterogeneity (tau-squared, I-squared) and a prediction interval. Test small-study effects (funnel plot, Egger test) only with ten or more studies. Use maintained tools (R `metafor` or `meta`; `statsmodels.stats.meta_analysis` in Python for simple cases) and keep the analysis as code. Test selection and effect sizes are in `../../ml-engineering/references/statistical-inference.md`.
- Name the gaps: questions no study answered well, populations missing, outcomes measured inconsistently.
- State the review's own limits: sources not searched, language restrictions, single screening, date of the last search.

## Keep it current

Before finalizing, check every included study for retractions, expressions of concern and corrections (`appraising-evidence.md`), and rerun the searches if more than six to twelve months have passed since the first run, depending on how fast the field moves. Report the date of the last search.

## Checks (done when)

- [ ] Review type stated and matched by the method actually used; deviations from the protocol listed.
- [ ] Every source recorded with string, filters, date and count; unsearched sources named.
- [ ] Every included work traceable to a search record or user file, with a resolved identifier.
- [ ] Screening table and flow diagram exist and their counts agree.
- [ ] Extraction cites locations in the papers; missing data listed rather than guessed.
- [ ] Risk of bias and, where relevant, certainty of evidence assessed with named tools.
- [ ] Synthesis organized by question, with disagreements explained and gaps named.
- [ ] Retraction check done; date of the last search reported; the bibliography passes `scripts/bib_check.py`.
