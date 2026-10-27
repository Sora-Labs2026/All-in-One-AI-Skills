# Clinical documentation drafts: reports, notes, case reports and trial documents

Read this when the user asks for a draft of a clinical document: a case report for a journal, an imaging, pathology or laboratory report, a clinical note (SOAP note, history and physical, consult note, discharge summary), or a clinical trial document (clinical study report section, serious adverse event narrative, protocol deviation record). Evidence summaries, recommendations, cohort analyses, decision pathways and treatment plans are in `clinical-decision-documents.md`. File formats (Word, PDF) are in `../../documents/GUIDE.md`.

**Guardrail.** Every document here is a draft for a qualified clinician (or, for trial documents, the responsible investigator and medical monitor) to review, correct and sign. It is not medical advice and not a diagnosis. The agent never signs, never states that a clinician reviewed something, and never fills a clinical fact that is not in the source records.

## Rules that apply to every clinical draft

1. **Label it.** First line or header: `DRAFT prepared with AI assistance for review by a qualified clinician. Not for clinical use until reviewed and signed.` Keep the label until a human removes it.
2. **Facts come from sources.** Each finding, value, date, medication and dose traces to a record the user supplied. Keep a source map (statement, source document, location) next to the draft for the reviewer.
3. **Gaps stay visible.** Missing or ambiguous information becomes a placeholder such as `[[CLINICIAN: confirm laterality]]` or `[[MISSING: discharge medications]]`. Never infer typical values, normal findings, or doses.
4. **Interpretation belongs to the clinician.** The agent may organize and phrase what the record says. It does not assign a diagnosis, a BI-RADS or other category, a tumor grade or stage, a causality judgment or a severity grade unless that judgment is already written in the source, and then it quotes it.
5. **Citations are verified.** Any guideline, paper or label cited is looked up and confirmed to exist with matching title, year and identifier (PMID or DOI). Never cite from memory.
6. **Minimum necessary data.** Use only the identifiers the document type needs. For publication and teaching, de-identify (`clinical-deidentification.md`). For documents inside a care setting, the organization must allow this tool to handle its records.
7. **Units and terms.** Units and reference intervals come from the reporting laboratory, not from general knowledge. Avoid error-prone abbreviations: the Joint Commission "Do Not Use" list bans U, IU, QD, QOD, a trailing zero (5.0 mg), a missing leading zero (.5 mg), and MS, MSO4 and MgSO4.

A source map the reviewer can check line by line (illustrative rows):

| # | Statement in the draft | Source document | Location | Status |
|---|---|---|---|---|
| 1 | Creatinine rose from 88 to 210 umol/L between day 1 and day 3 | Lab results export | Rows dated day 1 and day 3 | Copied |
| 2 | Started IV piperacillin-tazobactam on day 2 | Medication administration record | Day 2, 14:05 entry | Copied |
| 3 | Discharge follow-up with nephrology | (none found) | | `[[MISSING]]` |

## Case reports for journals

Follow the CARE reporting guideline and the journal's author instructions (word limits, reference style, consent form).

- Sections in order: title containing "case report"; keywords; abstract; introduction (why the case adds knowledge); patient information (de-identified demographics, relevant history); clinical findings; a timeline table; diagnostic assessment (tests, differential, reasoning, challenges); therapeutic interventions (what, dose, route, duration, changes); follow-up and outcomes (including adverse events and adherence); discussion (strengths, limitations, relevant literature, lessons); patient perspective when available; informed consent statement.
- Consent for publication is the clinician's responsibility; leave `[[CONSENT: confirm written consent for publication is on file]]`.
- De-identify more than Safe Harbor requires for rare cases: a rare disease plus an age, a location and a date can identify a person. Use relative time ("on day 3"), age ranges where exact age is not essential, and crop or mask images.
- The literature comparison cites verified sources only; "no similar cases have been reported" needs a documented search (databases, terms, date).

## Diagnostic reports

- **Imaging:** clinical indication; technique (modality, region, contrast, protocol); comparison studies with dates; findings organized by organ or region; impression that answers the clinical question. Structured systems (BI-RADS, Lung-RADS, LI-RADS, PI-RADS from the American College of Radiology) have exact category definitions and versions; use the current version's wording, and leave the category itself to the radiologist.
- **Surgical pathology:** specimen and site, clinical history, gross description, microscopic description, diagnosis, comments. Cancer resections use the College of American Pathologists protocols (synoptic elements such as histologic type, grade, margins, lymph nodes and pathologic stage); name the protocol version and leave each element for the pathologist to complete.
- **Laboratory:** specimen and collection time, test and method, result with unit, the laboratory's reference interval and flag, and the laboratory's critical-value notification record. Never flag a value as abnormal using an interval the laboratory did not report.

## Clinical notes

- **SOAP and progress notes:** subjective (history in the patient's words where useful), objective (vitals, examination, results), assessment (the clinician's), plan (the clinician's). The agent can structure dictated or written content into these sections; it does not author the assessment or plan.
- **History and physical, consult notes:** chief complaint, history of present illness, past history, medications with doses, allergies with reactions, family and social history, review of systems, examination, data, and the consultant's question and answer.
- **Discharge summaries:** admission and discharge diagnoses as documented, hospital course by problem, procedures, discharge medications with a reconciliation against admission medications (new, changed, stopped, and why), pending results, follow-up appointments, patient instructions at a plain reading level.
- Copy-forward hazards: never carry examination findings or plans from an earlier note into a new one as if they were current.

Medication reconciliation is clearer as a table than as prose:

| Medication | On admission | At discharge | Change | Reason (from the record) |
|---|---|---|---|---|
| Metformin 500 mg oral twice daily | Yes | No | Stopped | `[[CLINICIAN: confirm reason]]` |
| Apixaban 5 mg oral twice daily | No | Yes | New | As documented in the discharge plan |

## Clinical trial documents

- **Clinical study report:** follow the ICH E3 structure (synopsis, ethics, investigators and administration, introduction, objectives, investigational plan, study patients and disposition, efficacy evaluation, safety evaluation, discussion and conclusions, tables and figures, appendices). Numbers come from the statistical outputs (tables, listings and figures) with their identifiers; the statistical analysis plan governs which analyses are primary. GCP follows ICH E6, whose third revision was finalized in 2025.
- **Serious adverse event narratives:** subject identifier (not the name), age and sex, study arm (if unblinded is permitted), event term as coded (MedDRA requires a subscription), onset and resolution dates relative to first dose, seriousness criteria met (death, life-threatening, hospitalization or its prolongation, persistent or significant disability, congenital anomaly, other medically important event), severity grade as assessed (CTCAE in oncology, using the version the protocol names), relevant history and concomitant medications, actions taken with the study drug, outcome, and the investigator's causality and the sponsor's expectedness assessments as recorded.
A narrative skeleton that keeps judgments with the people who own them:

```text
DRAFT prepared with AI assistance for review by the investigator and medical monitor.
Subject [[SUBJECT ID]], a [[AGE]]-year-old [[SEX]] in [[ARM or "blinded"]], received the first dose on
study day 1. On study day [[N]] the subject [[EVENT DESCRIPTION AS RECORDED]] (MedDRA PT: [[CODED TERM]]).
Seriousness criteria recorded: [[CRITERIA]]. Severity as assessed by the investigator: [[GRADE, CTCAE version]].
Relevant history: [[FROM eCRF]]. Concomitant medications: [[FROM eCRF]].
Action taken with study drug: [[AS RECORDED]]. Outcome: [[AS RECORDED]] on study day [[N]].
Investigator causality assessment: [[AS RECORDED]]. Sponsor expectedness assessment: [[AS RECORDED]].
Open questions for the reviewer: [[LIST]]
```

- **Reporting clocks** are the sponsor's regulatory obligation; quote them, do not decide them. Under US IND rules (21 CFR 312.32), unexpected fatal or life-threatening suspected adverse reactions are reported within 7 calendar days and other serious and unexpected suspected adverse reactions within 15; other regions have their own rules. Flag clock dates for the safety team; never compute them silently.
- **Protocol deviations:** what happened, when, which subject, the protocol section affected, impact on safety and data integrity, the classification under the sponsor's own definitions, root cause and corrective and preventive action.
- Publication reporting guidelines: CONSORT (updated in 2025) for randomized trials, STROBE for observational studies, STARD for diagnostic accuracy, TRIPOD+AI for prediction models, SPIRIT for protocols. Use the checklist version the journal requires.

## Producing the file

- Write the draft in Markdown first, then produce Word or PDF through `../../documents/GUIDE.md`, and render the output to check headings, tables and the draft label.
- Keep a separate source map and an open-questions list for the reviewer; do not bury questions inside the prose.
- Include a review block: `Reviewed and approved by: [[NAME, credentials]]  Date: [[DATE]]`, left blank.

## Checks (done when)

- The draft label is present; the review block is blank; no statement claims a review happened.
- Every clinical fact maps to a source in the source map; placeholders mark everything missing or needing judgment.
- No diagnosis, category, grade, stage, causality or dose was invented; judgments present in the sources are quoted as written.
- Citations were looked up and match; reporting checklist items are mapped to sections.
- De-identification was applied where the document leaves the care setting; the rendered file was opened and checked.
