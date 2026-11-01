# Open-source investigation: claims, organizations, products and events

Read this when the user wants to verify a claim, find where and when a photo or video was made, check who stands behind a company, website or product, test a product's certifications or recall history, or reconstruct the timeline of a public event from open sources. Everyday web research is in `web-research-and-extraction.md`; judging sources in `appraising-evidence.md`; reasoning traps in `critical-thinking-and-bias.md`; patents and trademarks in `patent-search.md`.

## Scope gate

**In scope:** claims, organizations, products, public events and public infrastructure (domains, hosting, published records). Public figures only in their public role and only for the facts the claim needs.

**Out of scope, always:** locating, identifying or profiling private individuals. That means no home or work addresses, routines, relatives, vehicles or travel of private people; no identifying people by their faces; no linking a private person's accounts across platforms; no inferring health, sexuality, religion, politics or other sensitive traits; no collecting private-life details "for context". When a request turns toward a private person ("who is the man in this photo", "where does this account owner live"), stop, say why, and offer the part of the task that concerns the claim, the organization or the event. A person's name appears in a report only when an authoritative public record ties it to the claim (an officer in a company registry, a signatory on a regulatory filing), and only as much as the claim needs.

**Methods:** lawful public sources only. No logins the user is not entitled to, no getting around paywalls or access controls, no breached databases, leaked credentials or stolen documents, no pretexting or contacting subjects on the user's behalf. Infrastructure research stays passive (records and archives, no scanning or probing; that is security testing and needs authorization, see `../../code-security-review/GUIDE.md`). Follow site terms and robots rules. Purchases of data or paid tools happen only with the user's agreement.

## 1. Turn the request into claims

- Split the question into atomic claims, each with who, what, where, when or how many: "this video shows the flood in town X", "it was filmed in May 2025", "company Y is owned by company Z", "product W is certified to standard S".
- For each claim, write what evidence would confirm it and what would refute it, and the precision needed (country or exact street; year or hour).
- Keep separate claims separate. A correct location says nothing about the date; a real company says nothing about who controls it; an authentic document says nothing about whether its contents are true.
- Inventory what the user supplied (files, links, screenshots) and the budget (time, paid tools) before searching.

A synthetic illustration (invented facts, for the method only): "this video shows last week's warehouse fire at company Y's site in town X" splits into four claims with different evidence.

| Claim | Confirms | Refutes |
|---|---|---|
| The video shows town X | Several fixed features matched to imagery of X from one camera position | A better match elsewhere, or a feature that cannot exist in X |
| It was filmed last week | Shadows, weather and construction state consistent with those dates; no earlier copy | An earlier upload of the same footage |
| The building is company Y's site | Registry or planning records tying that address to Y | Records showing another occupant |
| There was a fire there last week | Fire service or local authority notice; independent local reports | Official records of no incident; the footage traced to another event |

## 2. Preserve before analyzing

- For every source: URL, retrieval time in UTC, a saved copy, and an archived snapshot (for example in the Internet Archive) when the page may change or disappear.
- Hash every file you were given or downloaded (SHA-256) and keep originals untouched. Work on copies and log each transformation: crop, enhance, frame extraction, transcoding.
- Record which frame (timestamp) of a video you analyzed.
- When results may end up in legal, regulatory or human-rights proceedings, follow the Berkeley Protocol on Digital Open Source Investigations (UN OHCHR and UC Berkeley, first published in 2020) for collection, preservation and verification, and keep a chain-of-custody log.

## 3. Where the evidence usually is

| Subject | Primary records | Corroborating sources | Common traps |
|---|---|---|---|
| Organizations | Company registries in the right jurisdiction (filings, officers, registered address, status), Legal Entity Identifiers (GLEIF), securities filings (SEC EDGAR and national equivalents), regulator and charity registers, court records, procurement notices, sanctions lists (UN, US OFAC, EU, UK) | Annual reports, archived versions of the company's own site, local-language news | Same name in another jurisdiction; brand versus legal entity versus parent; registries that publish what filers declare without checking it |
| Products | Regulator databases (device and drug approvals, recalls, safety alerts, enforcement letters), consumer-product recall registers, radio equipment authorizations, certification bodies' public certificate registries, patent and trademark records | Accredited lab reports, teardowns, documented user reports | Certificates for a different model or variant; copied marks without a certificate number; self-declarations presented as third-party certification |
| Events | Official notices and statements, court and police records, original footage and photos, public satellite imagery, weather and sun-position records, seismic and other monitoring networks | Local reporting in the local language, eyewitness material with provenance | Media recycled from an earlier event; time-zone mistakes; counts that change as reports update |
| Websites and infrastructure | Registration data through RDAP (registrant details are often redacted since 2018), DNS records and history, certificate transparency logs, web archives | Hosting and network ownership data | Shared hosting, CDNs and privacy services do not show common ownership |
| Organizational accounts and pages | Links from the organization's verified official site to the account, and back | Archived versions, platform transparency pages | Look-alike handles and logos; purchased or recycled accounts |
| Documents | The issuing body's own copy or register, reference numbers checked with the issuer, comparison with known genuine documents | File metadata as a lead | Metadata is editable and stripped by scanning and messaging apps |

## 4. Verifying images and video

1. **Find the earliest copy.** Run reverse image searches on several engines and on key frames, search distinctive visible details and likely captions in the local languages, and note platform upload times. The earliest copy you found is not necessarily the original; say so.
2. **Describe before naming.** List what is visible (text and script, signage, road markings, architecture, terrain, vegetation, weather, light and shadows) before proposing a place. Leave private vehicles' plates and bystanders' faces out of the analysis and the report.
3. **Geolocate with several independent features.** Narrow to candidate areas, then match fixed features (skyline, building outlines, road layout, terrain) in satellite and street-level imagery, and reproduce the camera position and direction. One matching sign is a lead; several independent features in the right spatial arrangement are evidence. Check the strongest alternative location and record why it fails.
4. **Establish time separately.** Shadow length and direction against a sun-position calculator for the candidate place, weather archives, construction or seasonal state visible in dated imagery. An upload time only proves the media existed by then.
5. **Check for manipulation honestly.** Error-level analysis and similar filters are unreliable on recompressed media; look for physical inconsistencies (light direction, reflections, shadows, repeated textures). Visual tells of AI generation become less reliable with each model generation. Content credentials (C2PA) show a signed edit history when present; their absence proves nothing.
6. **Treat metadata as a lead,** since platforms strip it and anyone can edit it.

## 5. Organizations, products and infrastructure

- **Pin the exact entity:** legal name, jurisdiction and registration number or LEI. Then map brand to operating company to parent with dated filings, and note which links are documented and which are inferred.
- **Check claims at the regulator, not the marketing page:** licensed or registered, recalls, warning letters, enforcement actions, sanctions.
- **Certification claims** need a certificate number that resolves in the issuing body's own registry and matches the exact model; test reports carry weight only from accredited labs.
- **Infrastructure links** (same IP address, same analytics ID, same certificate) are hypotheses about common control. Corroborate them with records before stating them, and never use them to reach a private person.

## 6. Weighing the evidence

- **Count origins, not copies.** Trace each report to its source; ten articles from one press release or one wire story are one source.
- **Compete the hypotheses.** List the explanations, including "something else", and score each piece of evidence for consistency with each (analysis of competing hypotheses). Evidence that fits every explanation does not help; seek the evidence that discriminates, and look hardest for evidence against the leading explanation.
- **State confidence on a scale you define** in the report (for example almost certain, likely, roughly even, unlikely), and use it the same way throughout. Confidence follows the weakest link the conclusion depends on.
- **Absence is weak evidence.** A search with unknown coverage that finds nothing proves nothing; say what was searched.
- **Stop** when the budget is spent, when new sources only repeat known origins, or when the next step would need non-public access. Deliver the best supported answer with its gaps.

## 7. Report

- The answer first, with its confidence and the main reason.
- A claims table: claim, status (confirmed, supported, unresolved, contradicted, false), key evidence with links and dates, and what the evidence does not establish.
- Alternatives considered and why they were rejected.
- Method: searches, tools, dates, and what was deliberately not pursued for privacy or legal reasons.
- An index of preserved items with hashes and archive links.
- Minimal personal data: no private individuals' details; blur bystanders' faces and private plates in any images included.

Before the user publishes accusations against an organization, suggest a right of reply and a legal review for defamation risk, and avoid re-sharing manipulated or graphic media without context.

## Done when

- [ ] The scope gate was applied; no private individual was located, identified or profiled.
- [ ] Each claim has confirming and refuting evidence defined, and a status with sources and dates.
- [ ] Originals are preserved with hashes, archive links and a transformation log.
- [ ] Location and time were established separately, each with independent evidence, and the strongest alternative was tested.
- [ ] Source independence was traced, confidence is stated on a defined scale, and gaps are listed.
