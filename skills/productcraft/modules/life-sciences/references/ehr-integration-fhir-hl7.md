# EHR integration: FHIR, SMART, CDS Hooks and HL7 version 2

Read this when software exchanges data with electronic health record systems: FHIR REST APIs, SMART on FHIR app launch and backend authorization, bulk export, CDS Hooks services, or HL7 v2 interfaces for admissions, orders and results; and when mapping between them. Wearable and phone health exports are in `consumer-health-data.md`; code systems in `biomedical-ontologies.md`; PHI safeguards in `hipaa-engineering-controls.md`; decision support logic in `clinical-decision-support-software.md`; imaging exchange in `dicom-imaging.md`.

**Guardrail.** Build and test against vendor sandboxes, a local FHIR server and synthetic patients. Connecting to a production EHR, a live interface engine channel or real patient data happens only through the organization's integration team, with the owner's explicit go-ahead. PHI never goes into the conversation, logs, test fixtures or error messages.

## Pick the standard by the job

| Need | Standard | Notes |
|---|---|---|
| An app reads or writes discrete data (patients, problems, medications, results) | FHIR R4 REST plus a national profile set (US Core in the US; UK Core, the International Patient Summary or others elsewhere) | FHIR R4 (4.0.1, 2019) is the deployed baseline; R4B (2022) and R5 (2023) have limited EHR support |
| An app launched from the EHR with the user's and patient's context | SMART App Launch 2.x | OAuth 2.0 with PKCE; scopes limit resources and actions |
| Server-to-server access without a user | SMART Backend Services | Client credentials with a signed JWT assertion |
| Population-scale export | FHIR Bulk Data Access (`$export`) | Asynchronous, NDJSON files |
| Advice inside the clinician's workflow | CDS Hooks 2.0 | Synchronous calls from the EHR to your service |
| Real-time hospital event feeds (admissions, orders, results, scheduling) | HL7 v2 through the site's interface engine | Most in-hospital integration still runs on v2 |
| Clinical documents | C-CDA in the US, or FHIR `DocumentReference` and `Composition` | |

In the US, certified EHRs must expose FHIR R4 APIs with US Core, and US Core versions follow the USCDI data set; the ONC HTI-1 rule moved certified health IT to USCDI v3 from 1 January 2026. Always read what a server actually supports from its CapabilityStatement (`GET [base]/metadata`) and SMART configuration rather than from marketing pages.

## FHIR REST essentials

- **Search, then page by links.** `GET [base]/Observation?patient=Patient/123&category=laboratory&date=ge2025-01-01&_count=100`. Follow `Bundle.link` with `relation = next` as an opaque URL; never build page URLs yourself, and expect servers to ignore parameters they do not support (check `Bundle.link` `self` to see what ran).
- **Token searches** use `system|code`: `code=http://loinc.org|4548-4`. Match codings on system and code, never on display text, and expect several codings per `CodeableConcept`.
- **Identifiers are not ids.** `Patient.id` is local to one server. Match across systems on `identifier` (system plus value), where the system URI belongs to the issuing organization.
- **Must Support** in US Core means "handle it when present", not "always present". Absent data may carry `dataAbsentReason`.
- **Quantities** use UCUM in `system`/`code`; `unit` is display text. **Dates** may be partial (`2024` or `2024-05`); `effective[x]` is when it was true, `issued` when it was released.
- **Writes:** conditional create (`If-None-Exist`) to avoid duplicates on retry; `If-Match` with the resource's ETag for optimistic locking; `transaction` Bundles when all-or-nothing matters, `batch` when not.
- **Errors** come back as `OperationOutcome`; 429 and 503 carry `Retry-After`; back off and cap retries (`../../integrations/GUIDE.md`).
- **Validate** resources against the profiles the server claims, with the official HL7 FHIR Validator: `java -jar validator_cli.jar obs.json -version 4.0.1 -ig hl7.fhir.us.core#6.1.0` (pick the IG version the server certifies). HAPI FHIR (Java), the Firely SDK (.NET) and `fhir.resources` (Python) are the common libraries; a local HAPI FHIR server in a container makes a good integration-test target.

## SMART on FHIR authorization

- Discover endpoints at `[base]/.well-known/smart-configuration`.
- **EHR launch** passes a `launch` token; **standalone launch** asks the user to pick a patient. Both use the authorization code flow with PKCE (S256), and `aud` set to the FHIR base URL.
- **Scopes:** request the minimum. SMART 2.0 scopes look like `patient/Observation.rs` (read and search); 1.0 servers use `patient/Observation.read`. Add `openid fhirUser` only when you need the user's identity, `launch/patient` for patient context, and `offline_access` only when a refresh token is truly needed.
- The patient in context comes from the token response, never from a URL parameter the browser can change.
- **Tokens:** short-lived access tokens; refresh tokens only on a server, encrypted. Browser apps keep tokens in memory, not in local storage.
- **Backend services:** register a public key set (JWKS); obtain tokens with `client_credentials` and a `client_assertion` JWT signed with RS384 or ES384; request `system/` scopes for exactly the resources needed.

## Bulk Data export

- Kick off with `GET [base]/Group/[id]/$export` (or `Patient/$export`) and `Prefer: respond-async`; the server answers 202 with a `Content-Location` status URL.
- Poll the status URL with backoff, honoring `Retry-After`; the final manifest lists NDJSON files per resource type, which may need the access token to download. Use `_type` and `_since` to limit the export; `DELETE` the status URL to cancel.
- The files are PHI: download into controlled storage, encrypt, record access, and delete them on the agreed schedule.

## CDS Hooks

- The EHR discovers services at `GET {base}/cds-services` and calls `POST {base}/cds-services/{id}` with `hook`, `hookInstance`, `context`, `prefetch`, and optionally `fhirServer` and `fhirAuthorization`.
- The response holds `cards`: a short `summary`, an `indicator` (`info`, `warning`, `critical`), the `source`, optional `suggestions` (proposed changes), `links` (often to a SMART app) and, in 2.0, `overrideReasons`; `systemActions` apply changes without a card where the EHR allows it.
- **Security:** the EHR authenticates with a signed JWT; verify issuer, audience, expiry and token ID against an allowlisted key set. Use `fhirAuthorization` only for that call's scope, and never store it.
- **Latency:** the clinician waits for you. Serve from prefetched data, avoid extra FHIR round trips, and agree with the EHR team how a timeout is shown ("decision support unavailable" rather than silence). Use the feedback endpoint to learn which cards were accepted or overridden.

## HL7 version 2 essentials

- A message is a sequence of segments ending in a carriage return (`\r`), not a line feed. Delimiters come from `MSH-1` and `MSH-2`, normally `|` for fields, `^` components, `~` repetitions, `\` escape and `&` subcomponents; read them from each message instead of hard-coding.
- **MSH:** `MSH-3`/`MSH-4` sending application and facility, `MSH-7` message time, `MSH-9` type and trigger (`ORU^R01^ORU_R01`), `MSH-10` control ID, `MSH-11` processing ID (`P` production, `T` training, `D` debugging), `MSH-12` version (2.3 to 2.9 in the field; 2.5.1 is common in US public-health feeds).
- **Common messages:** `ADT^A01` admit, `A03` discharge, `A04` register, `A08` update, `A40` merge patient identifiers; `ORM^O01` or `OML^O21` orders; `ORU^R01` results; `SIU^S12` scheduling; `MDM^T02` documents; `VXU^V04` immunizations.
- **Segments that carry results:** `PID` (`PID-3` identifiers with their assigning authority), `PV1` visit, `OBR` order and report header, `OBX` observations (`OBX-2` value type, `OBX-3` code, `OBX-5` value, `OBX-6` units, `OBX-7` reference range, `OBX-8` abnormal flags, `OBX-11` result status such as `F` final, `P` preliminary, `C` corrected, `OBX-14` observation time), `NTE` notes, and site-specific `Z` segments.
- **Escapes** (`\F\`, `\S\`, `\T\`, `\R\`, `\E\`, `\X0D\`, `\.br\`) are decoded after splitting. A field holding `""` means "explicitly null, delete the stored value", which differs from an empty field ("no change").
- **Timestamps** are `YYYYMMDDHHMM[SS[.S]][+/-ZZZZ]` with variable precision. Without an offset the time is the sender's local time; get the zone from the interface specification and convert once.
- **Transport:** MLLP over TCP frames each message with `0x0B` and `0x1C 0x0D`. The receiver stores the message durably, then acknowledges with `MSA-1` `AA` (accepted), `AE` (error) or `AR` (rejected), or the `CA`/`CE`/`CR` forms in enhanced mode. Senders resend when no acknowledgment arrives, so receivers deduplicate on sending facility plus `MSH-10`. MLLP is plaintext: run it inside a VPN or over TLS.
- **Every site differs.** The interface specification (or a conformance profile) is the contract: segments used, local codes, Z segments, optional fields that are really required. Keep a mapping table from local codes to LOINC and from local units to UCUM, versioned, with an owner.
- **Ordering and corrections:** messages arrive late or out of order; apply corrected results (`C`) over earlier ones by observation time and status precedence, process idempotently, and handle merges (`A40`) by re-linking records; a wrong merge is a patient-safety hazard.

## Mapping v2 to FHIR

- HL7 publishes a v2-to-FHIR mapping guide; use it as the starting point. Typical results mapping: `OBX-3` to `Observation.code`, `OBX-5` with `OBX-2` to the right `value[x]`, `OBX-6` to a UCUM quantity, `OBX-7` to `referenceRange`, `OBX-8` to `interpretation`, `OBX-11` to `status`, `OBX-14` to `effectiveDateTime`; `PID-3` repetitions to `Patient.identifier` with the system taken from the assigning authority.
- Keep the raw message (in PHI-controlled storage) with its control ID and the mapping version, so any FHIR resource can be traced back to its source.

## Patient matching

Wrong-patient errors are among the most serious integration hazards. Never match on name and birth date alone. Match on identifiers with their assigning authority, use the organization's master patient index for probabilistic matching, route uncertain matches to people, and handle link and merge events explicitly.

## Testing

- Vendor developer sandboxes and public SMART sandboxes with synthetic patients; a local FHIR server seeded with Synthea data; test channels on the interface engine.
- Contract tests from the interface specification, with edge cases: repeating fields, escape sequences, `""` versus empty, missing optional segments, unknown Z segments, LF instead of CR, several `OBX` with the same code, corrections and cancellations, merges, daylight-saving transitions, and bursts after a downtime.
- Run `../scripts/hl7v2_check.py` on synthetic or approved sample feeds before and after mapping changes. It reports structural problems (MSH fields, delimiters, segment names, timestamps, numeric `OBX` values, units, statuses, assigning authorities, duplicate control IDs, escapes, line endings) by message, segment and field number, and never prints a field value:

```bash
python3 <productcraft>/modules/life-sciences/scripts/hl7v2_check.py samples/*.hl7
python3 <productcraft>/modules/life-sciences/scripts/hl7v2_check.py feed.hl7 --strict --json > hl7_report.json
python3 <productcraft>/modules/life-sciences/scripts/hl7v2_check.py --list-rules
```

  Exit 0 means no errors (and no warnings with `--strict`), 1 means findings, 2 means a usage error or no messages. A clean run says the structure is sound, not that codes, units or values are right.

## Compliance hooks

- In the US, the information blocking provisions of the 21st Century Cures Act shape what EHRs must make available and how fast; app registration terms and API rate limits still apply.
- An app working for a covered entity is usually a business associate and needs a BAA; an app the patient chooses under the right of access usually is not, but then consumer health and state privacy laws apply (`hipaa-engineering-controls.md`, `consumer-health-data.md`).

## Done when

- [ ] The standard and version were chosen from the server's CapabilityStatement or the interface specification, not assumed.
- [ ] Authorization uses PKCE or signed client assertions, minimum scopes, and patient context from the token.
- [ ] Searches page by links; writes are conditional or version-checked; retries are bounded.
- [ ] v2 receivers acknowledge after durable storage, deduplicate on control ID, and handle corrections, merges and time zones.
- [ ] Mappings and code tables are versioned; resources validate against the target profiles.
- [ ] Tests ran on sandboxes or synthetic data only; `hl7v2_check.py` is clean of errors on the sample feeds.
