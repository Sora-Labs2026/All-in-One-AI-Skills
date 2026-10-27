# Clinical decision-support documents: evidence, recommendations, cohorts, pathways and treatment plans

Read this when the user asks for an evidence summary, guideline-style recommendations with evidence grades, a biomarker-stratified cohort analysis, a decision algorithm or care pathway, or an individual treatment-plan draft. Reports and notes are in `clinical-documentation.md`. Survival statistics are in `../../ml-engineering/references/survival-analysis.md`; trial registries and drug labels are reached through `clinical-and-translational-databases.md`.

**Guardrail.** These documents inform qualified clinicians; they do not replace them. Every output is a draft that a clinician reviews and owns. It is not medical advice for any person. Each recommendation carries an evidence level in a named grading system and a citation the agent has verified exists. No number, dose or trial result is invented, and no patient data is fabricated.

## Know when a document becomes regulated software

A document a clinician reads is different from software that generates patient-specific recommendations. If the user is building the latter, say early that it may be a medical device:

- **US:** decision-support software is outside device regulation only when it meets all four criteria in section 520(o)(1)(E) of the FD&C Act as explained in FDA's 2022 clinical decision support guidance: it does not process images, signals or patterns; it displays or analyzes medical information; it supports a health care professional's recommendation; and the professional can independently review the basis. Software that gives time-critical alerts or a single directive output usually fails these criteria.
- **EU:** under MDR Rule 11, software that provides information used for diagnostic or therapeutic decisions is class IIa or higher.
- Pointers for the quality system and software lifecycle are in `medical-device-quality.md`.

## Evidence: name the system, never mix systems

| System | Used by | Levels |
|---|---|---|
| GRADE | WHO, many guideline groups, Cochrane | Certainty of evidence: high, moderate, low, very low. Recommendation: strong or conditional, for or against |
| 1A to 2C (strength number plus quality letter) | Several societies and point-of-care references | 1 strong or 2 weak; A high, B moderate, C low or very low quality |
| ACC and AHA | Cardiology guidelines | Class of recommendation I, IIa, IIb, III (no benefit or harm); level of evidence A, B-R, B-NR, C-LD, C-EO |
| NCCN | Oncology | Categories 1, 2A, 2B, 3, plus preference (preferred, other recommended, useful in certain circumstances) |
| USPSTF | US preventive services | Grades A, B, C, D, I |
| Oxford CEBM (2011) | Evidence-based medicine teaching | Levels 1 to 5 by question type |

- When citing a guideline, copy its own grade in its own system and name the system and the guideline version. Do not translate grades between systems.
- When the user asks the agent to grade evidence itself, use GRADE and show the work for each outcome: start high for randomized trials and low for observational studies; rate down for risk of bias, inconsistency, indirectness, imprecision and publication bias; rate up only for a large effect, a dose-response gradient, or when all plausible confounding would reduce the effect. Mark the result as the agent's proposal for the guideline panel.
- Recency: guidelines and labels change. Record the version and date of each source and add "check for updates since [date]".

An evidence table that keeps each claim checkable:

| Recommendation (draft wording) | Grade and system | Source (verified) | Where in the source | Notes for the panel |
|---|---|---|---|---|
| `[[wording]]` | `[[e.g. strong, moderate certainty (GRADE)]]` | `[[organization, title, version, year, DOI or URL]]` | `[[section, table or page]]` | `[[population differences, updates pending]]` |

## Citations and numbers

- Look up every cited trial, guideline and paper (PubMed, DOI resolution, the guideline publisher's site) and confirm title, authors or organization, year and identifier. Check for retractions (Crossref includes Retraction Watch data). Never write a citation from memory, and never write "studies show" without the studies.
- Copy effect estimates (hazard ratios, response rates, confidence intervals) from the source with the table or figure they came from; do not recompute them from rounded numbers.
- Doses, schedules and contraindications come from the current drug label (DailyMed in the US, the summary of product characteristics in the EU) or the cited guideline, quoted with the source, and marked for verification by a pharmacist or the treating clinician.
- Templates and examples use placeholders (`[[HR (95% CI) from source]]`), never realistic-looking invented values.

## Cohort analyses

The user supplies the data; the agent analyzes and drafts.

- Pre-specify: population, biomarker definitions and cut-offs, endpoints (overall survival, progression-free survival, objective response rate, duration of response), comparisons and the primary analysis, before looking at results.
- Response criteria by name and version (RECIST 1.1, iRECIST for immunotherapy, disease-specific criteria); survival by Kaplan-Meier with numbers at risk, log-rank tests and Cox models with the proportional-hazards check; response rates with exact (Clopper-Pearson) confidence intervals.
- Subgroups: show forest plots with interaction tests, adjust or flag for multiplicity, and call subgroup findings hypothesis-generating. Small subgroups give wide intervals; show them.
- Report missing data, censoring, follow-up time (reverse Kaplan-Meier for median follow-up), exclusions with counts, and the analysis software and versions.
- A retrospective cohort shows association, not that a biomarker causes response. Write it that way.

## Decision algorithms and pathways

- Draw the flow as a diagram (Mermaid or Graphviz in Markdown, or a vector figure), and keep a table version for accessibility.
- Every decision node has a testable criterion with units and thresholds from a cited source; every path ends in an action, a referral or "outside this pathway: clinician judgment". Include branches for unknown or missing values and for contraindications.
- Encode the algorithm as data or code when it will be used repeatedly, and test it with a table of cases written with the clinician (input values, expected path). Each node keeps its citation.

```python
# Thresholds and citations are placeholders until the clinician supplies them from the cited source.
PATHWAY = {
    "start": {"ask": "marker_positive", "yes": "check_function", "no": "refer", "unknown": "order_test",
              "source": "[[guideline, section]]"},
    "check_function": {"ask": "egfr_below_threshold", "yes": "refer", "no": "option_a", "unknown": "order_test",
                       "source": "[[label, section]]"},
}
ENDPOINTS = {"refer", "order_test", "option_a"}

def walk(case, node="start"):
    path = [node]
    while node not in ENDPOINTS:
        answer = case.get(PATHWAY[node]["ask"])           # True, False or None (unknown)
        node = PATHWAY[node]["yes" if answer is True else "no" if answer is False else "unknown"]
        path.append(node)
    return path

# Cases agreed with the clinician: every branch, including unknown values, has a test.
assert walk({"marker_positive": True, "egfr_below_threshold": False})[-1] == "option_a"
assert walk({"marker_positive": None})[-1] == "order_test"
```

## Individual treatment-plan drafts

These are the highest-risk documents: they concern one person.

- Inputs are the patient's documented problems, history, medications, allergies, relevant results and the clinician's stated goals. Anything else is a placeholder.
- Structure, short enough to use: problem list; goals written as specific, measurable and time-bound targets agreed with the clinician and the patient; options for each problem drawn from the cited guideline, each with its evidence grade; the clinician's chosen intervention left as `[[CLINICIAN: select]]` unless the user (the clinician) already chose; monitoring parameters and frequency; thresholds for escalation that the clinician sets; patient education points; follow-up schedule; who to contact.
- Safety checklist for the reviewer, not a verdict: allergies, kidney and liver function for dosing, pregnancy and lactation, drug-drug interactions, age-specific cautions. The agent lists what to check and where the data is; it does not clear the patient.
- Patient-facing material: plain language at about a 6th to 8th grade reading level, short sentences, the warning signs that need urgent care, and a teach-back prompt. Translations are reviewed by a qualified translator.

## Layout

- Page one is a summary a busy reader can act on: purpose, population or patient, the key recommendations with their grades, critical safety points, and the draft label. Details, methods, evidence tables and references follow.
- Every page carries the draft label, the version and date, and the review block (`Reviewed by: [[NAME, credentials]]  Date: [[DATE]]`).
- Produce Word or PDF through `../../documents/GUIDE.md` and render the result to check it.

## Checks (done when)

- Every recommendation has a citation that was looked up and an evidence level copied from, or proposed in, one named system.
- Every number traces to the user's data or a cited source location; doses are quoted from a label or guideline and flagged for verification.
- Cohort analyses list pre-specified endpoints, methods, censoring, missing data and multiplicity handling.
- Algorithms have tested paths, including missing-value branches; treatment plans leave clinical choices to the clinician.
- The draft label and blank review block are present; device-regulation questions were raised if software is being built.
