# HIPAA and PHI engineering controls

Read this when building, changing or reviewing software that creates, receives, stores or transmits protected health information (PHI) for a covered entity or a business associate; when choosing vendors (hosting, logging, analytics, support, AI models) for such data; or when a request says "make it HIPAA compliant". De-identification is in `clinical-deidentification.md`; general application security in `../../launchguard/references/security-baseline.md`; consumer apps outside HIPAA in `consumer-health-data.md`; privacy policies and consent in `../../legal-ready/GUIDE.md`.

**Guardrail.** Engineering guidance, not legal advice. The organization's privacy and security officers and counsel decide what applies and whether controls suffice. There is no official HIPAA certification: never describe a product as "HIPAA certified" or "HIPAA compliant" as a fact; say which safeguards are implemented and evidenced. Never use real PHI in examples, tests or the conversation.

## Does HIPAA apply?

- **Covered entities:** health plans, health care clearinghouses, and providers that conduct standard electronic transactions (claims, eligibility). **Business associates:** anyone who creates, receives, maintains or transmits PHI on a covered entity's behalf, and their subcontractors. HHS guidance (2016) treats a cloud provider that stores encrypted PHI as a business associate even without the decryption key.
- **PHI** is individually identifiable health information held by a covered entity or business associate, in any form; ePHI is the electronic part, and the Security Rule governs it. Data a consumer app collects for its own users, not on a covered entity's behalf, is usually not PHI, but the FTC Act, the FTC Health Breach Notification Rule (amended in 2024 to cover health apps) and state laws such as Washington's My Health My Data Act apply instead.
- **Overlays:** 42 CFR Part 2 for substance use disorder treatment records (its 2024 rule aligned it more closely with HIPAA, with compliance required from 16 February 2026); state medical privacy laws; GDPR for patients in the EU.
- **Record the answer:** who is the covered entity, who is a business associate, which business associate agreements (BAAs) exist, and which systems hold PHI. Ask the owner; do not decide it silently.

## Security Rule safeguards as engineering work

The Security Rule (45 CFR Part 164, Subpart C) marks some specifications "required" and others "addressable"; addressable means implement it or document why an equivalent alternative is reasonable, not "optional". In January 2025 HHS proposed an update that would, among other things, make encryption and multi-factor authentication mandatory and require asset inventories, network maps and regular vulnerability testing. Check whether a final rule has been published and its compliance date before relying on the current text.

| Safeguard (citation) | Engineering control | Evidence to keep |
|---|---|---|
| Risk analysis and risk management (164.308(a)(1)) | Data-flow inventory of every place PHI lives or passes; threat model (`../../code-security-review/references/threat-modeling.md`); tracked remediation | Dated risk analysis updated with each significant change |
| Information system activity review (164.308(a)(1)) | Audit logs reviewed on a schedule, with alerts | Review records |
| Workforce access (164.308(a)(3), (a)(4)) | Role-based access with the minimum necessary; joiner, mover and leaver automation; periodic access reviews | Role matrix, review sign-offs |
| Unique user identification (164.312(a)(2)(i), required) | No shared logins; service accounts distinct from people | Account inventory |
| Emergency access (164.312(a)(2)(ii), required) | Break-glass access with extra logging, alerts and after-the-fact review | Break-glass procedure, review records |
| Automatic logoff (164.312(a)(2)(iii)) | Session timeouts suited to the setting (shared clinical workstations need shorter ones) | Configuration |
| Encryption at rest (164.312(a)(2)(iv)) | Databases, object storage, backups, laptops and mobile devices encrypted with managed keys; key access separated from data access | Key policy, configuration evidence |
| Audit controls (164.312(b), required) | Record reads as well as writes (see below) | Log schema, retention settings |
| Integrity (164.312(c)) | Signed or append-only clinical records, versioning instead of overwrite, checksums on transfers | Design notes, tests |
| Person or entity authentication (164.312(d), required) | Multi-factor authentication for workforce access; strong patient authentication proportional to risk | Identity provider configuration |
| Transmission security (164.312(e)) | TLS 1.2 or later on every hop, including internal services and HL7 feeds (MLLP inside a VPN or over TLS) | Scans, configuration |
| Contingency plan (164.308(a)(7)) | Backups, tested restores, disaster recovery, emergency-mode operation | Restore test results |
| Business associate contracts (164.308(b)) | A BAA with every vendor that touches PHI | Vendor register |
| Documentation retention (164.316(b)(2)) | Policies, procedures and required records kept six years | Document register |

## Minimum necessary in code

- **Fields:** APIs return only the fields a role needs for its purpose; build separate projections for clinical, billing, scheduling and analytics use instead of one "full patient" endpoint (`../../launchguard/references/security-baseline.md`, control 17).
- **Rows:** scope access by care relationship, facility or tenant, enforced in one place the application cannot bypass (database row-level security or a single data-access layer), with tests that prove cross-scope reads fail.
- **Purpose:** analytics and model development use de-identified data or a limited data set under a data use agreement (`clinical-deidentification.md`).
- Disclosures for treatment are exempt from the minimum-necessary standard, but they are still authenticated and logged.

## Where PHI leaks in software

| Leak path | Fix |
|---|---|
| Application logs, traces and APM spans (request bodies, SQL parameters, headers) | Structured logging with an allowlist of fields; redaction in the logger; body capture off in APM; opaque internal IDs instead of names or record numbers |
| Error trackers and crash reports (local variables, breadcrumbs, screenshots) | Scrubbing rules, a BAA or a self-hosted tracker |
| URLs and query strings (proxy logs, browser history, `Referer`) | Opaque IDs in paths; searches by POST; `Referrer-Policy: no-referrer` or `same-origin` |
| Analytics tags, tracking pixels and session replay | None on authenticated patient pages unless the vendor signed a BAA and is configured for it. HHS's December 2022 bulletin on tracking technologies (updated March 2024) was partly vacated by a federal court in June 2024 for certain unauthenticated pages; get counsel's view for public pages |
| Browser and device storage (local storage, IndexedDB, service-worker caches, OS backups, app-switcher screenshots, clipboard) | Keep PHI in memory; `Cache-Control: no-store` on PHI responses; mobile screenshot and backup protections |
| Notifications, SMS and email bodies | Generic text ("You have a new message"), details behind sign-in, unless the patient chose otherwise under the organization's policy |
| Exports, spreadsheets, support tickets, chat tools | Export controls with logging; support tools under BAA; redaction before tickets |
| Non-production environments | Synthetic or properly de-identified data only, never a copy of production |
| Search indexes, caches, queues, warehouses and backups | Same encryption, access control, logging and BAAs as the primary store |
| AI and LLM services (prompts, retrieved context, outputs, provider logs) | Only under a BAA that covers the specific service, with retention and training settings as the contract requires; minimize and redact; keep the data in the agreed region |

## Audit logging

- **Event fields:** actor (user ID, role, acting on behalf of), patient or record (opaque ID), action (view, search, create, update, delete, export, print, break-glass), resource type and ID, timestamp in UTC, source (IP address, device, application), outcome, and a request ID that ties it to application logs.
- **Log reads,** including search results that display patients, and flag bulk access and exports.
- **Tamper evidence:** append-only storage with deletion blocked (object lock or WORM retention), hash-chained or signed batches, and credentials separate from the application's.
- **Logs contain PHI identifiers,** so they get the same protection as the data.
- **Use them:** alerts for unusual access (high volume, records of staff or prominent people, access without a care relationship, after-hours spikes) and a scheduled review with named reviewers.

## Vendors and BAAs

Keep a register of every service that touches PHI, including sub-processors: hosting, databases, backups, email and SMS, logging, error tracking, analytics, support desks and AI providers. For each: BAA signed (date), the specific services the BAA covers (cloud BAAs usually list eligible services; others are not covered even in the same account), and required configuration. No BAA means no PHI: redact, de-identify, or do not integrate.

## Breach readiness

- Under the Breach Notification Rule, a breach of unsecured PHI requires notice to individuals without unreasonable delay and within 60 days of discovery; notice to HHS (at the same time for 500 or more people, otherwise in an annual log); and media notice when more than 500 residents of a state or jurisdiction are affected. Business associates notify the covered entity, often faster under the BAA.
- PHI encrypted as HHS guidance describes, with keys not compromised, counts as secured, which is why key management matters as much as encryption.
- Engineering makes the assessment possible: the data map says where PHI is, audit logs say who accessed what, and the system can list affected individuals. The privacy officer runs the risk assessment and decides on notification.

## Patient rights the software must support

Access to records (currently within 30 days, with one 30-day extension) including electronic copies and API access, amendment requests, accounting of disclosures, and restriction requests. Build these as features with audit trails, not as manual exports.

## Tests and evidence

- **Canary records:** create synthetic patients with unique marker values, exercise every feature, then search logs, traces, error events, analytics payloads and caches for the markers. Any hit is a leak.
- Cross-tenant and cross-role denial tests on every PHI endpoint; an audit event emitted for each read path; `Cache-Control` headers on PHI responses; no third-party scripts on PHI pages; session timeout behavior.
- Keep an evidence pack: data-flow diagram, risk analysis, vendor and BAA register, access reviews, test results and restore tests, each dated.

## Done when

- [ ] Covered entity, business associate and BAA status are recorded for each party and system.
- [ ] Every Security Rule row above has a control and evidence, or a documented reason it is addressed another way.
- [ ] PHI access is minimum-necessary by field, row and purpose, enforced in one place and tested.
- [ ] Canary-record tests show no PHI in logs, traces, error reports, analytics, URLs or caches.
- [ ] Audit logs capture reads, are tamper-evident and are reviewed.
- [ ] No vendor without a BAA receives PHI, and no claim of certification or compliance is made in product copy.
