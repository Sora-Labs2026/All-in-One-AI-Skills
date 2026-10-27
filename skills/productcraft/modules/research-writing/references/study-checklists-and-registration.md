# Study checklists (CONSORT, STROBE, PRISMA and others), registration and data availability

Read this when a study is being designed or written up and the venue, funder or field expects a reporting checklist (CONSORT, STROBE, PRISMA and the others), when a trial or review must be registered, or when the paper needs data and code availability statements.

A reporting guideline lists what a reader needs to judge and reproduce a study. It does not make a study good, and it is far easier to follow when chosen at the design stage, because it tells you what to record.

## Pick the guideline

The EQUATOR Network library is the index of current guidelines and their extensions; check it and the venue's instructions for the version required. Versions below were current in 2025-2026.

| Study type | Guideline | Notes |
|---|---|---|
| Randomized trial | CONSORT 2025 (replaced CONSORT 2010) | Extensions for cluster, non-inferiority, pilot and feasibility trials, harms, outcomes, and AI interventions (CONSORT-AI) |
| Trial protocol | SPIRIT 2025 | SPIRIT-AI for AI interventions |
| Observational study (cohort, case-control, cross-sectional) | STROBE | RECORD for routinely collected data, STROBE-MR for Mendelian randomization, STREGA for genetic association |
| Systematic review or meta-analysis | PRISMA 2020 | PRISMA-S for the search, PRISMA-P for protocols, PRISMA-ScR for scoping reviews, PRISMA-NMA and PRISMA-DTA for network and diagnostic reviews |
| Diagnostic accuracy | STARD 2015 | QUADAS-2 is the matching appraisal tool |
| Prediction model development or validation | TRIPOD+AI (2024, replaced TRIPOD 2015) | PROBAST for appraisal |
| Case report | CARE | |
| Qualitative research | SRQR or COREQ | COREQ for interviews and focus groups |
| Quality improvement | SQUIRE 2.0 | |
| Economic evaluation | CHEERS 2022 | |
| Animal research | ARRIVE 2.0 | |
| Description of an intervention | TIDieR | Used alongside the design's guideline |
| Online or web survey | CHERRIES; CROSS for surveys generally | |
| Early clinical evaluation of AI decision support | DECIDE-AI | |
| Medical imaging AI | CLAIM (2024 update) | |
| Machine-learning-based science generally | REFORMS | Many ML venues also require their own paper checklist |
| Omics data deposition | MIAME, MINSEQE and related minimum-information standards | Repository requirements: see `../../life-sciences/GUIDE.md` |

If no guideline fits exactly, use the closest one and say which items do not apply.

## Use the checklist properly

1. Download the official checklist for the right version and extension; keep it with the manuscript.
2. For each item, record where it is reported (section, page or line). Journals often require the completed checklist on submission.
3. For an item not reported, either add it or write "not applicable" with the reason. Never mark an item as reported when it is not.
4. When the information does not exist (randomization method undocumented, no sample-size calculation), say so in the paper as a limitation. Ask the authors; do not reconstruct details that nobody recorded.
5. Flow diagrams (CONSORT participant flow, PRISMA study flow) must add up at every step and match the text. Draw them from the same counts table the analysis uses.

An agent can map a draft to a checklist quickly. Present the result as a table of item, status (reported, partly, missing, not applicable) and location, followed by the questions the authors must answer for the missing items:

```markdown
| Item (use the numbering of the checklist version in force) | Status | Location | Note or question for authors |
|---|---|---|---|
| Sample size determination | Partly | Methods, l. 140 | Effect size and power assumed? Source of the effect size? |
| Allocation concealment mechanism | Missing | - | How were allocations concealed until assignment? |
| Participant flow per group | Reported | Fig. 1 | Counts in Fig. 1 and Results differ by 2 in the control arm |
```

Items most often missing or vague in submitted manuscripts, worth checking first:

- Sample size justification (the assumed effect, its source, power and alpha).
- Randomization sequence generation, allocation concealment and who was blinded.
- The pre-specified primary outcome, and any change from the registered one.
- How missing data were handled, and how many observations each analysis used.
- Harms and adverse events, reported for all groups.
- Eligibility criteria and the setting, dates and locations of recruitment.
- Where the protocol and statistical analysis plan can be read.
- The funder's role in design, analysis and the decision to publish.
- For prediction models and machine learning: how data were split, how hyperparameters were tuned without touching the test set, calibration, and external validation.

## Registration

- **Clinical trials:** prospective registration before the first participant is enrolled is required by ICMJE journals and by law in many places. Use ClinicalTrials.gov or a WHO primary registry (EU CTIS for EU trials of medicinal products). Report the registration number in the abstract.
- **Systematic reviews:** register health-related reviews in PROSPERO before screening; use OSF for others.
- **Other confirmatory studies:** preregister hypotheses, primary outcome and analysis plan on OSF or AsPredicted, or submit a Registered Report where the venue offers it.
- Report deviations from the registered plan openly in the paper: what changed, when and why.

## Data and code availability

- Deposit data in a repository that issues persistent identifiers: a domain repository when one exists (for example GEO, PDB, ENA), otherwise a general one (Zenodo, Dryad, Figshare, OSF). Cite the dataset with its DOI and version.
- License data clearly (CC0 or CC BY are common for data; MIT, BSD or Apache-2.0 for code) and include a README describing files, variables, units and how to run the code.
- Sensitive data (people, endangered species locations, security-relevant material) goes to controlled access with the conditions described; de-identify before sharing and record the method. Patient data rules (HIPAA, GDPR) apply; see `../../life-sciences/GUIDE.md` for clinical data handling.
- Archive the exact code version used for the paper (a tagged release with a DOI), and list software and package versions or an environment file.
- Write the availability statement to say what is available, where, under which license, and what is restricted and why. "Available on reasonable request" is weak and often fails in practice; use it only when sharing is genuinely restricted, and name who decides.

## Checks (done when)

- [ ] The guideline and version match the study design and the venue's requirement; extensions considered.
- [ ] The checklist is filled with locations; every missing item is added, justified as not applicable, or listed as a question for the authors.
- [ ] Flow diagram counts add up and match the text.
- [ ] Registration numbers are reported and deviations from the plan explained.
- [ ] Data and code have persistent identifiers, licenses and a README, or a specific reason they are restricted.
