# Processing documents through hosted APIs

Read this when documents must be converted, extracted, OCRed, redacted, watermarked, signed or filled through a hosted document-processing API instead of local tools. Local tools come first: Word, Excel, PowerPoint and PDF mechanics, LibreOffice and pandoc conversion, and document-to-Markdown are in `../../documents/GUIDE.md`; OCR and extraction of invoices and receipts in `invoices-and-receipts.md`. This file covers when a hosted service is justified, what to settle before the first upload, the request pattern, and how to verify each kind of result. Provider details differ and change; the practice below holds across them (2025).

Contents: local or hosted · before the first upload · the request pattern · conversion · extraction · OCR · redaction · watermarks · signatures · form filling · cost and limits · testing · done when.

## Local or hosted

| Need | Local first | Hosted is justified when |
|---|---|---|
| Office to PDF | LibreOffice headless | Layout fidelity for complex Office files matters and local output was checked and found wrong |
| Text and tables from digital PDFs | pdfplumber, pypdf, Camelot | Tables span pages, have merged cells, or arrive in volume |
| OCR | Tesseract, OCRmyPDF | Handwriting, many languages, poor scans, or throughput beyond local capacity |
| Redaction | A dedicated local redaction tool | The organization already uses a vetted service, and its output is verified as below |
| Signatures | A local signing library with the organization's certificate | Legally recognized e-signatures with identity checks and audit trails are needed |

A hosted call is an upload of the document to a third party. That is the decision to make consciously, not a convenience.

## Before the first upload

- **Permission from the data owner** for this provider and this purpose. Documents often contain personal data, health information, financial records or privileged legal material (`../../documents/GUIDE.md` already forbids online converters without explicit permission).
- **Contract and data terms:** a data processing agreement (GDPR Article 28 for personal data in scope); sub-processors; the region where documents are processed and stored; retention after processing and how to delete; whether uploads are used to train models; encryption in transit and at rest. For US protected health information, a business associate agreement is required before any upload. Security certifications are evidence, not guarantees.
- **Start with synthetic documents** that reproduce the real layout, and switch to real documents only after the checks below pass.
- **Keys** in the environment or a secret store; never in code, logs, chat or test fixtures (`../../agent-safety/GUIDE.md`).

## The request pattern

Most services take a multipart upload plus a JSON description of the operation, or an upload step that returns a document ID followed by processing calls; large jobs run asynchronously.

```bash
curl --fail-with-body -sS -X POST "$DOC_API_BASE/process" \
  -H "Authorization: Bearer $DOC_API_KEY" \
  -F "file=@contract.docx" \
  -F 'instructions={"output":{"type":"pdf","pdfa":"2b"}}' \
  -o out/contract.pdf
```

(The endpoint and instruction fields above are placeholders; use the provider's documented schema.)

- Check size, page and rate limits before sending a batch; split large files where the operation allows.
- Record each request: input file hash, operation, provider request ID, time, output hash. Never log document contents.
- On a timeout, check the job's status before resubmitting; a blind retry processes and bills twice.
- Delete remote copies through the API when the service supports it, and confirm the deletion.
- Process a copy; keep the original untouched.

## Conversion

- Accept or reject tracked changes and resolve comments before converting, or the PDF may show them, or silently drop them.
- Compare input and output: page count, page images side by side (render both, `../../documents/references/convert-and-render.md`), tables, headers and footers, footnotes, hyperlinks.
- `pdffonts out.pdf` shows every font embedded; substituted fonts change line breaks and page count.
- For archiving, request PDF/A and validate it with an independent validator such as veraPDF; a file named PDF/A is not proof.

## Extraction

- Check reading order on multi-column pages and tables that cross pages.
- Reconcile numbers: row counts, column totals and grand totals against the document; numbers with locale formats (1.234,56) parsed correctly; units and currencies kept.
- Flag low-confidence fields for a person instead of guessing; extracted values are drafts until checked.

## OCR

- Set the document languages explicitly; deskew and clean poor scans first.
- Produce a searchable PDF (the image plus a text layer) and keep the original image.
- Measure accuracy on a sample: hand-transcribe a few pages and compute the character or word error rate, separately for printed text, handwriting and tables. Report it with the results.

## Redaction

Redaction removes information permanently; a black box drawn over text is not redaction.

- Pattern presets (emails, phone numbers, card numbers, national identifiers) find formats, not meaning: they miss names, addresses and context, and they hit false positives. A person reviews every proposed redaction before it is applied.
- **Verify the output:**
  1. Extract all text (`pdftotext out.pdf -`) and search for every redacted term; nothing may remain.
  2. Check metadata (`pdfinfo -meta out.pdf`, `exiftool out.pdf`), bookmarks, annotations, form fields, attachments and hidden layers.
  3. Make sure earlier revisions are gone: PDFs saved incrementally can keep the original content in the file. Rewrite the file (for example with qpdf) and repeat step 1.
  4. Look at every redacted page as an image.
- Keep the unredacted original under access control and record what was redacted and why.

## Watermarks

A visible watermark marks status ("DRAFT", "CONFIDENTIAL"); it does not protect anything and can be removed. Keep it from covering content, and make sure it does not break text extraction and screen-reader access for the real content.

## Signatures

- **Only with the signer's authorization.** Never sign on someone's behalf, and never treat a signature as a formality.
- A self-signed certificate shows that the file has not changed since signing, and only to someone who trusts that certificate; it does not identify a person to a third party.
- Legally recognized electronic signatures depend on the jurisdiction: in the EU, eIDAS defines simple, advanced and qualified signatures; in the US, the ESIGN Act and UETA. Use a service that provides the required level, identity verification and an audit trail. Contracts are drafts for a lawyer (`../../legal-ready/GUIDE.md`).
- Add a trusted timestamp and long-term validation data for documents that must stay verifiable for years (PAdES).
- Verify signatures independently after signing, for example with `pdfsig out.pdf` and a second validator.

## Form filling

- List the form's fields first (names, types, checkbox and radio export values, required fields), then map data to them.
- Facts come from the user or a source system, never invented (`../GUIDE.md`, ground rule 1); unknown values stay empty and are reported.
- Read the values back from the filled file, then decide with the user whether to flatten it (no further edits) or leave it editable.

## Cost and limits

Pricing is usually per page or per document, often with different rates per operation (OCR and signing cost more). Estimate a batch from page counts before running it, stay under the user's cap, and report the actual cost.

## Testing

- Unit-test request building and response handling against recorded responses with the network disabled; use synthetic documents as fixtures.
- Keep a small regression set of real-world layouts (synthetic content) and re-run it when the provider changes versions; compare outputs by page images and extracted text.
- Tests never contain real keys; build fake ones at runtime where a value is required.

## Done when

- The owner approved uploading these documents to this provider, and the data terms (processing agreement, region, retention, training use) were checked and recorded.
- Every operation's output was verified with the checks above, by independent tools, not by the provider's success message.
- Redactions were confirmed by text extraction, metadata review and a rewrite; signatures were validated independently.
- Remote copies were deleted where possible, and requests, hashes and costs are logged without document contents.
