# Contract drafts from templates, schedules, and e-signature preparation

Read this when the task is generating agreement drafts (master services, non-disclosure, referral or reseller agreements and similar) from a template for many counterparties, keeping a rolling schedule of deals under an executed agreement, or preparing a document for electronic signature. Word and PDF mechanics are in `../../documents/references/word-docx.md` and `../../documents/references/pdf.md`; website terms and privacy policies are `../../legal-ready/GUIDE.md`.

**Everything produced here is a draft for review by a qualified lawyer.** The agent does not give legal advice, choose legal terms, decide whether a clause is enforceable, or confirm that a document is ready to sign.

## Ground rules

- **Clause text comes from counsel-approved templates.** The agent fills variables and assembles approved alternatives; it does not write new legal provisions. If a needed clause is missing, leave a visible directive (`[[COUNSEL: limitation of liability for this role]]`) and list it in the report.
- **Every output is marked DRAFT** in the file name and on the first page until counsel and the signatory approve the execution version. A successful build proves the file was generated, nothing more.
- **Never invent party facts:** legal names, registration numbers, addresses, signatories and titles come from the owner or from the counterparty's own submission. Blank lines are better than guesses.
- **Executed agreements are immutable.** Changes go through the amendment or notice procedure the agreement itself specifies.
- **Nothing is sent, uploaded for signature or signed without the owner's explicit approval** of that document version, those recipients and that action. The agent never signs, declines or voids on anyone's behalf and never opens a signing link meant for someone else.

## Template plus spec

Keep the legal text and the deal data apart so drafts are reproducible and diffable:

- **Template:** one Markdown or Word template per agreement type, with fixed approved text and named placeholders (`{{COUNTERPARTY_LEGAL_NAME}}`, `{{EFFECTIVE_DATE}}`, `{{ROLE_CLAUSE}}`). Version it; record which counsel review approved which version.
- **Spec:** one small structured file (JSON or YAML) per counterparty with only the variable facts and choices (role, fees, governing schedule entries). Required fields are few; optional ones render as blank lines for completion.
- **Clause alternatives:** where the deal type changes a clause (for example who pays a referral fee), keep the approved variants in a table keyed by the choice, and reject unknown choices instead of falling back silently.
- **Build:** fill placeholders, render tables, add the DRAFT notice, convert to the delivery format (pandoc or a Word library), then open and render the result to check it (`../../documents/GUIDE.md`). Fail the build when any placeholder is left unfilled or a value is malformed.

A minimal spec, with the fields the counterparty completes at signing left out so they render as blank lines:

```json
{
  "output_name": "Example Supplier MSA",
  "short_name": "Example Supplier",
  "role": "supplier",
  "effective_date": "2026-11-15",
  "legal_name": null,
  "schedule": [
    ["1", "2026-11-15", "Project Alpha", "supplier", "12 months", "standard"]
  ]
}
```

And the template line it fills, with a counsel directive still open:

```markdown
This Agreement is made on {{EFFECTIVE_DATE}} between [[OUR LEGAL NAME]] and {{COUNTERPARTY_LEGAL_NAME}}.

{{ROLE_CLAUSE}}

[[COUNSEL: confirm the liability cap for supplier-role agreements]]
```

Keep a build log per draft: template version, spec file hash, build time, converter version and the list of open directives. Diff each new draft against the previous one for the same counterparty before it goes to review.

Implementation safety, because specs and templates are inputs:

- Escape values inserted into tables or markup, so a pipe, bracket or HTML tag in a company name cannot break the structure or inject content.
- Validate output file names (no path separators, no `..`, no reserved device names) and write only inside the chosen output folder.
- Converters such as pandoc can read local files and URLs referenced in the input; run them on reviewed templates, in a restricted environment, with a timeout.
- Keep generated files out of version control; the template and specs are the source.

## Rolling schedules under an executed agreement

Some framework agreements let the parties add entries (projects, introduced parties, order forms) by written notice. Handle them as follows:

1. Read what the executed agreement actually authorises to be added by notice, the notice channel, the recipient and any objection period. Anything outside that authority needs a signed amendment.
2. Agree the entry internally first (commercial terms, approvals); internal discussions and margins never go to the counterparty.
3. Draft a dated notice that states only what the agreement allows: the entry, its terms and fee, and the reference to the agreement.
4. The owner approves the exact notice; an authorised person sends it through the agreed channel; record proof of delivery and any objection.
5. Update the tracked schedule data and rebuild a *consolidated draft view* for internal reference, labelled as such. It does not replace the signed agreement and the notice.

## Preparing documents for e-signature

- **Prefer the provider's API or template features over driving its web editor.** Most e-signature services can place fields from anchor text or text tags embedded in the document (a hidden string such as `\sig1\` where the first signer's signature goes), or from saved templates with defined roles. This is repeatable and testable; dragging fields in a browser is not.
- **Recipients and routing:** set signing order; map each signer to a role; add copy recipients as "receives a copy", never as signers. Every field belongs to exactly one recipient; check that ownership before saving.
- **Signature page:** place the signature blocks on their own page with a stable layout, and check the converted document's actual pagination, since fonts and renderers move text.
- **If browser automation is the only route** (no API access): the human signs in; the automation never enters credentials or codes; it verifies the exact site origin and the intended envelope before every action; positions come from calibrated numeric coordinates rather than drag-and-drop; it stops on any mismatch; it saves as draft by default.
- **Evidence before sending:** a rendering or screenshot of each page with fields, the recipient list and the document's hash, for the owner to review. Name evidence files with random identifiers, not with recipient names.
- **Default to "save as draft".** Sending requires an explicit approval bound to that envelope, those recipients and that document version; any change needs a new approval.

## Legal effect of electronic signatures (general information)

Electronic signatures are broadly valid for commercial contracts in the US (the federal ESIGN Act and state laws based on UETA) and the EU (the eIDAS Regulation, which distinguishes simple, advanced and qualified electronic signatures; only a qualified signature is automatically equivalent to a handwritten one across member states). Some documents are excluded or need a specific form in many jurisdictions, for example wills, certain family-law and real-estate documents, notarised deeds and some court documents. Counsel decides which signature type a document needs.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Editing the generated Word file by hand | Change the template or the spec and rebuild, so the source stays the truth |
| A stale draft sent instead of the current one | Version and date in the file name and footer; remove old outputs on rebuild |
| A clause variant chosen by an unknown role falling back to a default | Reject unknown choices at build time |
| Signature fields assigned to the wrong recipient | Check field ownership per recipient before saving; review the evidence |
| Using a consolidated schedule view as if it were the signed agreement | Label it as a draft view; keep the executed document and notices as the record |
| Personal data of signatories spread across tools | Keep contact details in one place and share them only where the signing process needs them |

## Checks (done when)

- [ ] Every draft is built from a versioned, counsel-approved template and a spec, carries the DRAFT notice, and has no unfilled placeholders; open directives for counsel are listed.
- [ ] Inserted values are escaped; output paths are validated; the converted file was opened and rendered.
- [ ] Party facts come from the owner or the counterparty, never from guesses.
- [ ] Schedule entries were added only within the executed agreement's notice authority, with approval and delivery evidence recorded.
- [ ] E-signature envelopes have correct recipients, order and field ownership, were reviewed from evidence, and were saved as drafts unless the owner approved sending that exact envelope.
