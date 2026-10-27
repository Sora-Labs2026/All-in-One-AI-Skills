# Machine learning on electronic health records

Read this when a task builds or evaluates models on EHR data (MIMIC-III, MIMIC-IV, eICU, OMOP CDM extracts, hospital warehouses) for outcomes such as mortality, readmission, length of stay, deterioration, phenotypes or medication recommendation, including with PyHealth-style toolkits, or translates between medical code systems. General evaluation, leakage and model comparison are in `../../ml-engineering/references/evaluation-and-leakage.md`; time-to-event outcomes in `../../ml-engineering/references/survival-analysis.md`.

**Guardrail.** A research model is not a clinical tool. Do not present predictions as advice for a patient, and say that deployment needs prospective validation, clinical governance and possibly device regulation (`medical-device-quality.md`, `clinical-decision-documents.md`). Never fabricate patient records.

## Data access and the agent

- MIMIC and eICU on PhysioNet are credentialed: each user completes human-subjects training and signs a data use agreement. The terms forbid sharing the data and any attempt to re-identify. PhysioNet's guidance treats sending the data to online services, including hosted AI tools, as sharing unless the service is set up under the conditions it describes. Hospital extracts carry similar or stricter terms.
- So the agent writes and runs code where the data lives, and looks only at schemas, row counts, distributions and aggregate metrics. It does not print patient-level rows, notes or identifiers into the conversation.
- For examples, tests and demos use synthetic data (Synthea, or MIMIC demo subsets where their license allows) and say so.

## Shape of EHR data

- Patients have encounters (admissions, ICU stays, visits); encounters have time-stamped events: diagnoses, procedures, medications, labs, vitals, notes. Some tables have no event time.
- **Billing diagnoses have no reliable time within the stay.** In MIMIC, `diagnoses_icd` and `procedures_icd` are assigned at or after discharge. Using them to predict something during the same admission leaks the outcome.
- MIMIC shifts dates per patient into the future; real calendar years are only approximated through `anchor_year_group`. Do not interpret absolute dates or seasons.
- Tables are large (chart events run to hundreds of millions of rows). Load only needed columns and time ranges, convert to Parquet once, and query with DuckDB or Polars (`../../data-engineering/references/polars.md`).

## Code systems and mapping

| Domain | Systems | Notes |
|---|---|---|
| Diagnoses | ICD-9-CM, ICD-10-CM (US switch in October 2015), ICD-10 (WHO), SNOMED CT | Mapping ICD-9 to ICD-10 (CMS GEMs) is many-to-many and approximate; groupers such as CCS or CCSR reduce sparsity |
| Procedures | ICD-9-CM procedure codes (volume 3), ICD-10-PCS, CPT | CPT is licensed by the AMA; do not ship CPT descriptions without a license |
| Medications | NDC, RxNorm, ATC | Normalize NDC to RxNorm ingredients (RxNav), then group by ATC class |
| Labs and observations | LOINC | Same test, different local codes and units across sites: map, then convert units |
| Terminologies | SNOMED CT | Free in SNOMED International member countries through the national release center (in the US through a UMLS license), licensed elsewhere |

- Never guess a code or a mapping. Look codes up in the official release or a vetted API (`biomedical-ontologies.md`), and record the release version.
- Truncating ICD-10 codes to their 3-character category is a reasonable first grouping; say so in the methods.

## Frame the prediction task

Write these down before any modeling:

- **Index time:** the moment the prediction is made (for example 24 hours after ICU admission). Every feature must be available at that moment in a real deployment.
- **Observation window, gap and outcome window:** which data before the index time feed the model, and which period after it defines the label.
- **Cohort:** inclusion and exclusion criteria, first stay only or all stays, minimum age, and a flow table with counts at each step.
- **Label definition:** in-hospital death, death within 30 days (needs a death source beyond the hospital), readmission within 30 days excluding planned readmissions, and so on.

Leakage traps that look like great models:

- Discharge codes, discharge summaries or length of stay used as features.
- Treatments that are themselves responses to the outcome (vasopressors before a shock label, comfort-care orders before a death label).
- Features computed over the whole stay instead of up to the index time.
- The number of recorded events, which grows with stay length and therefore with the outcome.
- Normalization or imputation statistics fitted on all data before splitting.

## Splits and baselines

- Split by patient, never by admission: one patient's stays all go to one split. Check it with `../../ml-engineering/scripts/split_check.py`.
- Add a temporal check (train on earlier admissions, test on later ones; in MIMIC-IV use `anchor_year_group`) and, where possible, an external check on another hospital or dataset (eICU is multi-center).
- Baselines first: logistic regression and gradient boosting on counts of grouped codes, age, sex and summary statistics of labs and vitals in the observation window. Sequence models (GRU, Transformer, RETAIN-style attention) and graph models must beat them on the same splits with confidence intervals to justify their cost.

## PyHealth-style pipelines

Toolkits such as PyHealth package the steps: dataset loaders for MIMIC, eICU and OMOP, task definitions that turn patients into samples, patient-level splitting, model zoos and trainers.

- The PyHealth API changed between major versions: 1.x used task functions and per-dataset code mapping arguments; 2.x (2025) moved to task classes with input and output schemas and a faster dataframe backend. Read `pyhealth.__version__` and follow that version's documentation; do not mix examples from both.
- Inspect what a predefined task actually does (index time, windows, which tables) before using its results. A predefined "mortality" task may use features that are leakage for your question.
- Cache processed samples to disk; reprocessing MIMIC-IV can take a long time and a lot of memory.

## Evaluation

- Report AUROC and AUPRC together with the outcome prevalence; AUPRC is only interpretable against prevalence.
- Calibration matters for risk scores: reliability plot, calibration slope and intercept, Brier score. Recalibrate on validation data, never on test data.
- Clinical utility: sensitivity, positive predictive value and alerts per day at a threshold chosen with clinicians, and decision curves (net benefit across thresholds).
- Bootstrap confidence intervals over patients; compare models on the same test patients (`../../ml-engineering/scripts/compare_scores.py`).
- Subgroups: performance and calibration by age band, sex, race and ethnicity where recorded and appropriate, admission type and site. Missingness itself differs by group (who gets tested), and proxies such as cost encode access to care, not need.
- Medication recommendation models are scored with set metrics (Jaccard, F1) and drug-drug interaction rates; they are not prescribing advice.

## Reporting

Follow TRIPOD+AI (2024) for prediction models: data source and dates, cohort flow, index time, predictors, missing data handling, model, evaluation, subgroup results, limitations and intended use. Include a model card with what the model must not be used for.

## Checks (done when)

- Data use terms respected: no patient-level data in the conversation or in hosted services; synthetic data labeled as such.
- Index time, windows, cohort flow counts and label definition are written down; every feature group passed a leakage review against the index time.
- Splits are by patient (checked), with a temporal or external test where possible.
- Baselines reported next to complex models on the same splits, with patient-level bootstrap intervals.
- Discrimination, calibration, clinical-utility and subgroup results are all reported; code system releases and mappings are recorded.
