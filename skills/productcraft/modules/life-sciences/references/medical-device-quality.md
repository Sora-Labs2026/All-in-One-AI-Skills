# Medical-device quality systems: ISO 13485, with IEC 62304 and ISO 14971 pointers

Read this when a team building a medical device or software as a medical device (SaMD) needs quality management system (QMS) documents, a gap analysis against ISO 13485, preparation for a certification or regulatory audit, a software lifecycle under IEC 62304, a risk management file under ISO 14971, or a first answer to "is our software a medical device?". Clinical documents are in `clinical-documentation.md` and `clinical-decision-documents.md`.

**Guardrail.** General guidance for building documents and software, not regulatory or legal advice. The manufacturer's management owns, approves and signs the QMS; a regulatory affairs professional or notified body decides questions of classification and conformity. Never describe a product or company as "compliant", "certified" or "cleared" unless a certificate or clearance exists, and never invent the company's facts (`../../legal-ready/GUIDE.md` has the same rule for legal claims).

## Where the rules stand (check dates; these move)

- **ISO 13485:2016** is the QMS standard for medical devices. In the EU it is harmonized as EN ISO 13485:2016 with amendment A11:2021.
- **US:** FDA's Quality Management System Regulation (QMSR) amends 21 CFR Part 820 to incorporate ISO 13485:2016 by reference. The final rule was published in February 2024 and took effect on 2 February 2026, replacing the Quality System Regulation. Records that FDA previously did not inspect, such as management review and internal audit reports, are no longer shielded; confirm the details in the final rule.
- **EU:** the Medical Device Regulation (EU) 2017/745 and the In Vitro Diagnostic Regulation (EU) 2017/746 require a QMS (MDR Article 10(9)); notified bodies audit it. Transition deadlines were extended (Regulation (EU) 2023/607); check the current dates for the device class.
- ISO standards are copyrighted. Cite clause numbers and paraphrase; the organization buys the standard. Do not reproduce clause text.

## ISO 13485 at a glance

| Clause | What the organization must have in place (paraphrased) |
|---|---|
| 4 QMS | Process approach with outsourced processes controlled (4.1.5); validation of software used in the QMS (4.1.6); a quality manual with scope and justified exclusions (4.2.2); a medical device file per device type or family (4.2.3); document control (4.2.4); record control, including retention and protection of health information (4.2.5) |
| 5 Management | Commitment, quality policy and measurable objectives, responsibilities and authorities, a management representative, internal communication, planned management reviews with defined inputs and outputs (5.6) |
| 6 Resources | Competence, training and its effectiveness (6.2); infrastructure and maintenance (6.3); work environment and contamination control (6.4) |
| 7 Product realization | Planning with risk management (7.1); customer and regulatory requirements (7.2); design and development: planning, inputs, outputs, review, verification, validation (including clinical or performance evaluation), transfer, changes and the design and development file (7.3); purchasing and supplier control (7.4); production and service: cleanliness, installation, servicing, process validation including production software (7.5.6), sterilization (7.5.7), identification (7.5.8), traceability (7.5.9), preservation (7.5.11); control of monitoring and measuring equipment (7.6) |
| 8 Measurement and improvement | Feedback and post-market inputs (8.2.1); complaint handling (8.2.2); reporting to regulatory authorities (8.2.3); internal audit (8.2.4); monitoring of processes and product (8.2.5, 8.2.6); nonconforming product (8.3); data analysis (8.4); corrective and preventive action (8.5.2, 8.5.3) |

- Requirements in clauses 6, 7 and 8 that genuinely do not apply may be excluded, with the justification recorded in the quality manual; design and development is the usual candidate where regulations allow it. Software companies rarely can exclude design controls.
- Build the list of required documented procedures and records by reading the clauses the organization's scope includes, not from a count found online. Keep it as a table: clause, required item, document ID, owner, status, evidence location.

## Gap analysis that an auditor would accept

1. **Scope first:** devices, classes, markets, sites, outsourced processes and suppliers. Ask the user; leave placeholders such as `[[COMPANY: legal manufacturer name and address]]`.
2. **For each applicable requirement,** record: existing document or record (by ID and revision), owner, status (in place with evidence, partial, missing, not applicable with justification), the gap in one sentence, and the action.
3. **Evidence over intent.** A written procedure without records of it being followed is a partial at best. Ask for sample records (training records, a closed CAPA, a management review, a supplier evaluation).
4. **Prioritize by risk** to patients and to certification: CAPA, complaint handling, design controls and risk management, supplier control and document control usually come first.
5. **Output:** the gap table, a document index, and a dated action plan with owners. Make no claim of readiness; the internal and certification audits decide.

| Clause | Requirement (paraphrased) | Evidence (ID, revision) | Owner | Status | Gap | Action, due date |
|---|---|---|---|---|---|---|
| 8.5.2 | Corrective action procedure and records of actions taken and their effectiveness | SOP-012 rev B; CAPA log | `[[ROLE]]` | Partial | No effectiveness checks recorded for closed CAPAs | Add effectiveness step and review the last 10 CAPAs, `[[DATE]]` |
| 7.4.1 | Supplier evaluation and selection criteria, proportionate to risk | none found | `[[ROLE]]` | Missing | Cloud hosting and contract developer not evaluated | Draft supplier procedure and approved supplier list, `[[DATE]]` |

## Writing procedures and the manual

- A procedure says who does what, when, and which record proves it: purpose, scope, responsibilities by role, definitions, steps, records produced, related documents, revision history, approval block.
- Write what the organization actually does or will do, at its scale. A ten-person software company copying a large manufacturer's procedures fails audits on day one because nobody follows them.
- The quality manual describes scope and exclusions, references every procedure, and shows how processes interact (a process map).
- The medical device file holds, per device family: description and intended use, labeling and instructions for use, specifications, manufacturing and servicing procedures, measuring and monitoring procedures, installation requirements, the risk management file, verification and validation, and the design and development file.
- Electronic QMS records and signatures in the US fall under 21 CFR Part 11; validate the QMS software for its intended use (4.1.6).

## Software lifecycle: IEC 62304

IEC 62304:2006 with amendment 1:2015 (a second edition has been in development; check whether it is published) defines lifecycle processes for medical device software.

- **Safety class** from the worst harm a software failure could contribute to after external risk controls: A (no injury or damage to health possible), B (non-serious injury possible), C (death or serious injury possible). The class sets which activities and documents are required; justify it in the risk file.
- **Processes:** development planning; software requirements; architecture (class B and C); detailed design (class C, and parts of B); unit implementation and verification; integration and integration testing; system testing; release. Plus maintenance, risk management for software (including failures of third-party components), configuration management and problem resolution.
- **SOUP** (software of unknown provenance: open-source libraries, operating systems, runtimes): list each with name, version, the requirements it must meet, and its known anomalies relevant to safety; monitor them after release. A lockfile plus an SBOM supports this (`../../engineering-practices/references/dependencies.md`).
- Agile development fits IEC 62304 when the plan maps sprints to the required activities and records (AAMI TIR45 describes how).
- **Traceability:** requirement to architecture or design item to test to risk control, kept as a matrix or generated from the issue tracker and test reports.

| Requirement | Design item | Verification (test ID, result) | Hazard and risk control | Released in |
|---|---|---|---|---|
| SRS-014 Alert when a value is out of range | `alerts/rules.py` | TC-114 pass, TC-115 pass | HAZ-007 missed alert; RC-007 unit tests plus monitoring | 1.4.0 |

Generate this from the tracker and CI results rather than maintaining it by hand, and fail the release check when a requirement has no passing test or a risk control has no verification.

## Risk management: ISO 14971

ISO 14971:2019, with guidance in ISO/TR 24971:2020:

- A risk management plan with acceptability criteria derived from the manufacturer's policy.
- Hazard analysis: hazards, foreseeable sequences of events, hazardous situations and harms, including misuse and use errors (usability engineering under IEC 62366-1).
- Estimate risk (probability of harm and severity), evaluate it against the criteria, and control it in priority order: inherent safety by design, then protective measures, then information for safety. Warnings alone do not replace a design fix that is possible.
- Verify each control was implemented and is effective; evaluate residual risk, benefit-risk and overall residual risk; hold a risk management review before release.
- Collect production and post-production information (complaints, field data, cybersecurity events, literature) and feed it back into the file.

## Is it a medical device? Pointers for software

- International framing: the IMDRF definition and risk categorization of SaMD.
- **US:** device software functions; the 2022 clinical decision support guidance (see `clinical-decision-documents.md` for the four criteria); predetermined change control plans for AI-enabled device software functions (final guidance, December 2024); premarket cybersecurity guidance and section 524B of the FD&C Act for cyber devices (SBOM, vulnerability management).
- **EU:** MDR Rule 11 and MDCG 2019-11 on qualification and classification of software; the AI Act (Regulation (EU) 2024/1689) treats AI that is, or is a safety component of, a device needing notified-body assessment as high-risk, with obligations scheduled from August 2027 (check for changes).
- Related standards: IEC 82304-1 (health software products), IEC 81001-5-1 (security in the health software lifecycle), IEC 62366-1 (usability), IEC 60601 (electrical equipment, for hardware).

Answer classification questions with the criteria and the open questions, and recommend a regulatory professional; do not give a final classification.

## Checks (done when)

- Scope, markets and device classes are confirmed by the user; company facts are placeholders until supplied.
- The gap table covers every applicable clause with evidence references, status and owner; exclusions are justified.
- Each drafted procedure names roles, steps, records and an approval block left for the organization.
- For software: the IEC 62304 class is justified in the risk file, SOUP is listed with versions, and the traceability matrix links requirements, tests and risk controls.
- No document or message calls the company compliant, certified or cleared without a certificate or clearance in hand; standard text is cited by clause, not copied.
