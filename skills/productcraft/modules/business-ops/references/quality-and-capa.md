# Quality: nonconformance, root cause, CAPA, SPC and supplier quality

Read this when the task is handling a nonconforming part or lot, choosing a disposition, running a root-cause investigation, writing or closing a corrective and preventive action (CAPA), reading a control chart, setting incoming inspection or managing a supplier's quality. Medical-device quality systems (ISO 13485, FDA's Quality Management System Regulation in force since 2 February 2026, EU MDR) are covered in `../../life-sciences/references/medical-device-quality.md`; use that file for device gap assessments and this one for the day-to-day mechanics. Statistical tests beyond SPC are in `../../ml-engineering/references/statistical-inference.md`.

## Ground rules

- **Contain first, investigate second.** Quarantine suspect material (physical tag and a system hold that blocks shipping) before anyone starts on root cause.
- **Dispositions follow authority.** Use-as-is and repair need engineering justification and, in many sectors, customer approval; the people named in the company's procedure sign, not the agent.
- **Safety-critical and regulatory characteristics are never used as-is** without a formal risk assessment and any required notification.
- **Evidence over intent.** A CAPA is closed on data showing the problem stopped, not on a completed task list.
- **Do not hide findings.** A nonconformance found during an audit gets the same formal treatment as any other.

## Nonconformance lifecycle

1. **Identify:** who found it, where (incoming, in-process, final, field), the requirement violated (drawing, specification clause, revision), measured values against tolerance, quantity, lot or serial traceability, photographs.
2. **Contain:** the suspect population is everything that shares the cause: the same supplier lot, production run, tool, operator shift or time window, including work-in-progress, finished stock, stock in transit and stock at customers.
3. **Disposition** by the material review board (quality, engineering, production; the customer where the contract requires):

| Disposition | When | Requirement |
|---|---|---|
| Use as is | No effect on form, fit, function, safety or regulatory compliance | Documented engineering justification; customer concession where required (common in aerospace and automotive) |
| Rework | Can be brought fully into conformance by an approved procedure | Written rework instruction; re-inspect to the original requirement |
| Repair | Made usable but will not fully meet the requirement | Engineering disposition and usually customer concession; a permanent deviation |
| Return to supplier | Supplier-caused | Supplier corrective action request, debit or replacement, scorecard update |
| Scrap | None of the above, or uneconomic | Authorised sign-off; witnessed destruction for serialised or safety-critical parts |

4. **Decide whether a CAPA is needed.** Not every nonconformance needs one. Typical triggers: recurrence of the same failure mode, customer complaints, field failures, audit findings, adverse trends. Write the trigger rule into the procedure so the decision is consistent.

## Root-cause analysis

| Method | Use when | Limitation |
|---|---|---|
| 5 Whys | A simple, single causal chain | Assumes one chain; each "why" must be verified with data |
| Cause-and-effect (fishbone) diagram | Generating hypotheses across categories (people, machine, material, method, measurement, environment) | Produces candidates, not proof |
| Is / is-not analysis | Narrowing where, when and on what the problem does and does not occur | Needs good data on the "is not" side |
| Fault tree analysis | Safety-critical or complex failures with interacting causes | Effortful; quantitative only with failure-rate data |
| 8D | Team-based supplier or customer problem solving, often required by automotive customers | The format does not replace verified evidence |

Signs the investigation stopped at a symptom: the root cause is "human error" or "operator did not follow the procedure" (ask why the system allowed it), the action is "retrain" alone, or the root cause restates the problem. Verify a suspected cause by turning it on and off (reproduce the defect, then remove the cause and show it disappears) where that is safe.

## CAPA that holds up in an audit

- **Action statement:** specific, tied to the verified cause, with an owner, a due date and the evidence that will show completion. "Add a torque check at station 12 with a calibrated wrench, recorded on the traveller, from date X" rather than "improve inspection".
- **Prefer stronger controls:** design changes and error-proofing beat added inspection, which beats procedures and training.
- **Verification versus effectiveness:** verification confirms the action was implemented as planned; the effectiveness check confirms the problem did not recur over a defined, meaningful period or number of lots. Define the effectiveness criterion when the CAPA opens, not when closing it.
- **Recurrence after closure** means reopening the investigation, not opening a new CAPA for the same issue.
- Preventive action addresses potential problems found through trends, risk assessment or near misses; keep it distinct from correction of an existing problem.

## Statistical process control

**Control limits are not specification limits.** Control limits describe what the process does (typically the mean plus and minus three standard deviations of the plotted statistic); specification limits describe what the customer needs. A process can be in control and out of specification, or in specification and out of control.

| Data | Chart |
|---|---|
| Measurements in rational subgroups of about 2 to 10 | X-bar and R |
| Larger subgroups | X-bar and S |
| Individual measurements (batch processes, destructive tests) | Individuals and moving range (I-MR) |
| Proportion defective, varying sample size | p chart (np chart when the sample size is fixed) |
| Defects per unit, fixed area of opportunity | c chart (u chart when the area varies) |

- Use one documented set of run rules and apply it consistently. The Western Electric rules flag one point beyond 3 sigma, two of three beyond 2 sigma on the same side, four of five beyond 1 sigma on the same side, and eight in a row on one side; the Nelson rules add trends and alternation patterns. More rules mean more false alarms.
- Do not adjust a stable process because a point "looks high"; reacting to common-cause variation (tampering) increases variation.
- **Capability indices** (Cp, Cpk for within-subgroup variation; Pp, Ppk for overall) are meaningful only for a stable process with a suitable distribution and a capable measurement system. Check the measurement system first (gauge repeatability and reproducibility). Customer minimums such as Cpk 1.33 come from the customer's requirements, not from this file.

## Incoming inspection and sampling

- Attribute sampling plans in ISO 2859-1 (equivalent to ANSI/ASQ Z1.4) are indexed by lot size, inspection level and acceptable quality limit (AQL), with switching rules between normal, tightened and reduced inspection. The AQL is the quality level the plan accepts most of the time; it is not a guarantee that accepted lots contain fewer defects. Look at the plan's operating characteristic curve to see what it actually protects against.
- Zero-acceptance (c = 0) plans are common for critical characteristics; some customers mandate them.
- Rely on supplier certificates of conformance only under a written agreement and with periodic verification of the supplier's own testing; falsified certificates are a containment event for everything from that supplier.

## Supplier quality

- Score suppliers on a few metrics (defects per million received, on-time delivery, corrective-action response time and effectiveness, lot acceptance) and share the scorecard on a fixed cadence.
- Escalate in documented steps: corrective action request, increased inspection, controlled shipping (supplier-side sorting or data with each shipment), qualifying an alternative source, and finally removal from the approved supplier list with a transition plan. Develop rather than switch when the supplier has unique capability and engages; switch when it does not.

## Communication

Internal reports lead with impact (production, customers, safety, cost) and containment status, then details. Customer notifications of shipped nonconforming product lead with what was contained, which lots or serials are affected, what the customer should do and when the next update comes; timing follows safety risk and the contract. Regulatory responses are factual, acknowledge the observation, and show investigation, action and evidence.

## Checks (done when)

- [ ] Containment covers the whole suspect population and is recorded before root-cause work.
- [ ] Each disposition has the justification and the signatures the procedure requires.
- [ ] The root cause was verified with data, not inferred; the action addresses it with the strongest practical control.
- [ ] The CAPA has an effectiveness criterion set in advance and evidence of meeting it before closure.
- [ ] Control charts use the right type, documented run rules, and limits computed from process data rather than specifications.
