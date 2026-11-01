# Building clinical decision support software

Read this when building or changing software that checks orders (drug interactions, allergies, doses), computes clinical scores, raises alerts or suggests actions inside a clinical workflow: an EHR module, a standalone clinical app or a CDS Hooks service. Written evidence summaries and recommendation documents are in `clinical-decision-documents.md`; connecting to the EHR is in `ehr-integration-fhir-hl7.md`; release testing and AI evaluation are in `health-software-evaluation.md`; PHI controls are in `hipaa-engineering-controls.md`.

**Guardrail.** This is software engineering guidance, not medical advice. The clinical content (interaction pairs, dose limits, score tables, thresholds, alert wording) comes from a licensed knowledge source or a published specification chosen by the client's clinical governance, and a named clinician approves it. The agent never invents a rule, dose, threshold or interaction pair and never fills a gap from memory; it leaves `[[CLINICAL CONTENT: ...]]` placeholders and labels test values as synthetic.

## Settle the regulatory question first

Software that analyzes patient-specific data to recommend or alert can be a medical device. Raise it before design, not after:

- **US:** the FD&C Act section 520(o)(1)(E) criteria, explained in FDA's 2022 clinical decision support guidance, keep some CDS outside device rules only when all four criteria hold, including that the clinician can independently review the basis of the recommendation. Time-critical alarms, outputs that act as a single directive, and anything that processes images or signals usually fall inside. Certified health IT in the US must also meet the decision support interventions criterion of the ONC HTI-1 rule (in force for certified products from 1 January 2025), which requires source attributes, including for predictive interventions, to be available to users.
- **EU:** MDR Rule 11 places most software that informs diagnostic or therapeutic decisions in class IIa or higher.
- Pointers for the quality system, IEC 62304 and ISO 14971: `medical-device-quality.md`.

## Architecture

Keep three things separate:

1. **Knowledge** (data): versioned rule sets, each rule carrying its source, the source's version or date, the approving clinician, the approval date and the effective date. Store it as reviewable files or tables with change control like code; a knowledge update is a release.
2. **Engine** (code): pure, deterministic functions. Typed clinical facts in (codes, values, units, timestamps), findings out (rule ID and version, severity, message key, the input values used, the source reference). No database, network or clock calls inside the engine; the caller passes "now". That is what makes it testable and reproducible.
3. **Presentation and workflow**: where and how findings appear, who must respond, what gets recorded.

Log every evaluation as a decision record: engine version, knowledge version, a hash or snapshot of the inputs, the findings, and what the clinician did (accepted, changed the order, overrode with a reason). Without it nobody can answer "why did it fire, or why didn't it?" after an incident.

## Inputs: codes, units, time and missing data

- **Codes, not strings.** Drugs as RxNorm ingredients (map brand names and NDCs to ingredients first) or the national equivalent; labs as LOINC; problems as SNOMED CT or ICD-10; allergies as coded substances or classes. Free-text matching misses brand names and misspellings and hits look-alikes.
- **Units.** Convert explicitly with UCUM-aware code and reject unknown units. Milligram-versus-microgram and per-dose-versus-per-day confusions are classic causes of harm.
- **Time.** Each value carries when it was measured. The governance team defines how old a weight, a creatinine or a potassium may be before it no longer counts; the engine applies that rule and says which value it used.
- **Missing required input is a result, not a pass.** A weight-based dose check without a current weight returns "cannot evaluate: weight missing" and the workflow treats it as governance decided (block, or require acknowledgment). A score with a missing parameter is "not computed", never computed as if the parameter were normal.
- **Engine failure is visible.** An exception, a timeout or an unavailable knowledge base shows "check unavailable" to the clinician and is logged and alerted. Silently returning "no alerts" is the most dangerous failure mode in CDS.

## Check patterns

| Check | Engineering points |
|---|---|
| Drug-drug interaction | Look pairs up symmetrically (normalize the order of the pair); support class-level rules; include drugs on the active list, drugs being ordered together and recently stopped drugs if governance says so |
| Therapeutic duplication | Grouped by class (for example ATC level), not by exact ingredient |
| Drug-allergy | Coded allergens and cross-sensitivity classes from the knowledge source; distinguish intolerance from allergy where the record does; never match on free text alone |
| Drug-condition and drug-lab | Driven by coded problems and current lab values within their validity window |
| Dose range | Per dose and per day; weight- or body-surface-area-based where the rule says so; age bands; renal and hepatic adjustment; route and formulation; cumulative limits; rounding stated |
| Clinical scores | Implement from the primary publication as a table, version-tagged; show the inputs and their timestamps next to the result; scoring variants chosen explicitly (NEWS2, for example, has a second oxygen-saturation scale that a clinician selects for specific patients) |

## Alerts and human factors

Published studies consistently find that most medication alerts are overridden. Each unnecessary interruption teaches clinicians to click through the next one, including the one that matters.

- **Tier by severity and actionability.** Interrupt only for high-severity findings the clinician can act on now; show the rest inline or passively. The commonly cited "five rights" of CDS (right information, person, format, channel and time) are a useful review lens.
- **Make each alert actionable:** what was found, why (the rule and its source), the patient data that triggered it with timestamps, and one-click actions (change the dose, cancel the order, open the reference).
- **Hard stops are rare,** approved by governance, and have an emergency path. Overrides require a reason from a coded list plus optional free text, stored with the decision record.
- **No auto-dismissing notifications for safety alerts;** never rely on color alone; keyboard and screen-reader accessible (`../../responsive-accessibility.md`).
- **Suppression rules** (do not refire the same pair in the same encounter after an override) are clinical decisions, documented and measured.
- **Monitor after release:** firing rate, override rate and time to action per rule; review them with clinical governance on a schedule and retire or retune noisy rules.

## Integration points

- **CDS Hooks 2.0** services receive hook calls (`patient-view`, `order-select`, `order-sign`) and return cards with an indicator (`info`, `warning`, `critical`), suggestions and links. Calls are synchronous inside the clinician's workflow, so design for fast responses from prefetched data and decide with the EHR team what a timeout shows. Details in `ehr-integration-fhir-hl7.md`.
- **Inside an EHR's own rule engine:** the same knowledge and test discipline apply; export the rules and test them outside the EHR where possible.
- **SMART apps** suit calculators and complex displays launched from the chart.

## Testing

- **Golden cases from the specification,** reviewed and signed by a clinician: for each rule, a positive case, a negative case, values just below, at and above each threshold, missing inputs, unit variants and stale values. For interactions, both orders of every pair.
- **Properties:** symmetry of pair checks; monotonicity (raising a dose never turns an exceeded limit into a pass); unit invariance (the same dose in mg and in g gives the same verdict); determinism (same inputs, same output).
- **Knowledge-base tests:** every rule has a source, version, approver and effective date; every code exists in the current terminology release and is not retired.
- **Knowledge updates:** run the full case set, then compare all findings over a fixed synthetic patient population before and after the update; a clinician reviews the differences before release.
- **Mutation testing** of the engine shows whether the tests notice a changed threshold or comparison (`../../engineering-practices/references/advanced-testing.md`).
- **Synthetic patients only** (for example Synthea output), labeled synthetic. No real patient data in fixtures.

## Hazard analysis

Keep a hazard log in the ISO 14971 style: missed alert, false alert leading to under-treatment, wrong patient, wrong unit, stale data used, engine outage, knowledge base out of date. Each hazard has its controls and the test that verifies each control. The release decision references the log (`health-software-evaluation.md`).

## Done when

- [ ] The regulatory question was raised and recorded with the owner's answer.
- [ ] Knowledge, engine and presentation are separate; every rule has a source, version, approver and effective date.
- [ ] Missing inputs and engine failures produce visible "cannot evaluate" or "check unavailable" results, never a silent pass.
- [ ] Inputs are coded, unit-checked and time-stamped; decision records are written for every evaluation.
- [ ] Golden cases, properties and knowledge-base tests pass; the clinician sign-off on the case set is recorded.
- [ ] Alert tiers, override reasons and monitoring metrics were agreed with clinical governance.
