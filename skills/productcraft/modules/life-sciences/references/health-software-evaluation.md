# Evaluating health software and health AI before release

Read this when deciding whether a release of clinical software (EHR features, decision support, patient-facing apps, integrations) may ship, or when evaluating an AI feature that works with health data: clinical note summarization, patient-message drafting, triage or symptom chat, coding assistance, risk prediction. General LLM evaluation (evaluation sets, judges, variance, regression in CI) is in `../../ml-engineering/references/llm-evaluation.md`; leakage and splits in `../../ml-engineering/references/evaluation-and-leakage.md`; models built on EHR data in `ehr-modeling.md`; decision-support test design in `clinical-decision-support-software.md`. This file adds what health changes.

**Guardrail.** Evaluation evidence informs a release decision made by the organization's clinical safety lead or governance group; it is not a claim that a product is safe or effective, and nothing here is medical advice. Use synthetic data, or de-identified data under its data use terms, and keep patient-level content out of the conversation.

## Release gates by hazard

Group tests by the harm they guard against, not by code module, and let the clinical safety owner write the acceptance rule for each group before the run.

| Gate | What it covers | Typical rule |
|---|---|---|
| Clinical logic | Decision support rules, scores, dose and interaction checks, unit conversions | Every golden case passes; any failure blocks |
| PHI exposure | Canary-record leak tests, authorization and cross-tenant tests, headers and storage (`hipaa-engineering-controls.md`) | Any failure blocks |
| Clinical data integrity | Signed records immutable (addendum only), audit events written, no cascading deletes of clinical data, concurrent-edit handling, time zones | Any failure blocks |
| Clinical workflow | End-to-end flows: encounter, ordering, results review, documentation, alerts displayed | Each failure is triaged by clinical impact; a failure such as allergies missing from the patient header blocks even if every other test passes |
| Interoperability | FHIR resources valid against profiles; HL7 v2 messages parsed, acknowledged and mapped; malformed input rejected safely (`ehr-integration-fhir-hl7.md`) | Failures on safety-relevant fields block |

- Avoid percentage pass thresholds for safety gates. A 98% pass rate can hide the one test that matters; classify each failure against the hazard log instead.
- Run the gates on every merge to the release branch, with the commit, environment, data version and results stored as release evidence.
- Health IT used in the NHS follows the clinical risk management standards DCB0129 (manufacturers) and DCB0160 (deploying organizations): a hazard log, a clinical safety case and a named clinical safety officer. They are a good model elsewhere too.

## What to evaluate in health AI

| Dimension | Question | How to measure |
|---|---|---|
| Task performance | Does it do the job? | For classifiers: discrimination (AUROC), and sensitivity, specificity and predictive values at the operating threshold clinicians chose. For generation: factual accuracy against the source record |
| Calibration | Do predicted risks match observed rates? | Calibration plot, slope and intercept, on held-out data |
| Subgroups | Does it work for everyone it will be used on? | The same metrics by age band, sex, race and ethnicity where recorded and lawful to use, language, site and device, with confidence intervals; say when a subgroup is too small to judge |
| Clinical utility | Is acting on it better than the alternatives? | Decision curve analysis (net benefit against treat-all and treat-none) or a comparison with the current process |
| Robustness | Does it survive real data? | Missing fields, unit and coding changes, typos and abbreviations, different note styles, a held-out site or time period |
| Generative safety | What can go wrong in the text? | Error taxonomy below |
| Privacy | Can it expose data? | Memorized record fragments, cross-session leakage, instructions hidden in documents it reads |
| Workflow effect | Does it help in practice? | Time and error rates measured in a pilot, not assumed; watch for automation bias (clinicians accepting wrong output) |

### Error taxonomy for generated clinical text

Agree the categories and their severity with clinicians before scoring. A common starting set:

- **Omission** of a clinically important fact (allergy, active medication, abnormal result, code status).
- **Fabrication:** a statement not supported by the source.
- **Wrong attribution:** a fact assigned to the wrong patient, family member, date or encounter.
- **Negation and certainty errors:** "no chest pain" becoming "chest pain"; "possible" becoming "confirmed".
- **Temporal errors:** past history presented as current, wrong sequence.
- **Dose, unit and number errors.**
- **Unsafe patient-facing content:** advice outside the product's intended use, missed escalation of red-flag symptoms, missing direction to emergency services, mishandled self-harm content.

Rate each error as critical, major or minor by its potential for harm. Report critical errors one by one, with the case, not only as counts.

## Building the evaluation set

- **Sources:** de-identified real cases under their data use terms, or synthetic cases labeled as synthetic. Include rare but dangerous situations on purpose; random samples seldom contain them.
- **Reference standard:** clinicians label against written criteria, with two independent annotators and adjudication of disagreements. Report agreement (Cohen's or Fleiss' kappa) so readers know how hard the task is.
- **Grounded checks for summaries:** each statement in the output should trace to a span in the source; an unsupported statement is a fabrication even if it happens to be true.
- **Red-team set for patient-facing tools:** requests for diagnosis or dosing, emergencies, self-harm, pregnancy and pediatric cases, instructions hidden in uploaded documents, out-of-scope questions. The expected behavior for each is written down in advance.
- **Hygiene:** freeze and version the test set; tune only on a development set; check that public benchmark items are not in the model's training data before trusting a benchmark score.

## Scoring

- Severity-weighted error counts per output, alongside averages; one critical error can outweigh many good outputs.
- LLM judges only after calibration against clinician labels on a sample, with the agreement reported; clinicians review every output a judge marks critical plus a random sample of the rest.
- Confidence intervals by bootstrap over cases; show the worst cases, not only the mean.
- Compare against the current standard of care or current process, not against an imagined perfect baseline.

## Deciding and deploying

- Pre-specify the metrics, subgroups and acceptance criteria with clinical governance before running the frozen test set, and record that you did.
- Before a model influences care, run it in silent mode: it produces outputs that are logged but not shown, and those outputs are compared with what actually happened.
- Device regulation may apply (`medical-device-quality.md`). For AI that is a medical device, the FDA's December 2024 final guidance on predetermined change control plans describes how planned model updates can be authorized in advance; under the EU AI Act, AI in medical devices that need notified-body assessment falls in the high-risk category, with obligations scheduled from August 2027 (check current dates; changes to the timeline were under discussion). The 2021 good machine learning practice principles from the FDA, Health Canada and the MHRA are a sound checklist either way.

## Monitoring after release

- Input drift (case mix, new devices, coding or unit changes), performance drift once outcome labels arrive, calibration drift, and subgroup metrics over time, each with an alert threshold the clinical owner sets.
- A visible way for clinicians to report bad outputs, routed into the incident process, with the ability to roll back the model or switch the feature off quickly.
- Re-run the frozen test set on every model, prompt or retrieval change, and treat a regression in a safety category as a blocked release.

## Reporting

Use the reporting guideline that matches the study: TRIPOD+AI (2024) for prediction models, TRIPOD-LLM (2025) for studies of large language models, DECIDE-AI (2022) for early live clinical evaluation, and CONSORT-AI and SPIRIT-AI (2020) for trials and their protocols. `../../research-writing/references/study-checklists-and-registration.md` explains how to fill a checklist honestly.

## Done when

- [ ] Each release gate has an owner and a written acceptance rule set before the run; results are stored with the commit and data versions.
- [ ] The evaluation set has clinician labels with measured agreement, deliberate rare dangerous cases and a frozen test split.
- [ ] Performance, calibration and subgroup results are reported with intervals; critical errors are listed individually.
- [ ] Generated text was scored with a clinician-agreed error taxonomy; any LLM judge was calibrated against clinicians.
- [ ] A silent-mode run, monitoring metrics and a rollback path exist before the feature influences care.
- [ ] The regulatory question was raised, and the report uses the matching reporting guideline.
