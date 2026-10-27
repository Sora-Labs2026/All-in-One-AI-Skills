# De-identifying clinical data: DICOM, tables, notes and signals

Read this before clinical data is shared, published, used to train a model, moved out of the environment it was collected in, or shown to any hosted service, including this conversation. It covers the legal frames (HIPAA Safe Harbor and Expert Determination, GDPR), where identifiers hide in each data type, pseudonyms and date shifting, tools, and the bundled header checker `../scripts/dicom_phi_check.py`.

**Guardrail.** This is engineering guidance, not legal advice. The data owner's privacy officer, a qualified expert or the ethics board decides whether a dataset counts as de-identified. Never fabricate patient data to fill gaps or to test; use generated synthetic data and label it synthetic.

## Pick the frame before the tool

| Frame | What it means | What you must produce |
|---|---|---|
| HIPAA Safe Harbor (45 CFR 164.514(b)(2)) | Remove 18 kinds of identifiers of the patient and of relatives, employers and household members, and have no actual knowledge that the rest could identify anyone | Rules that remove each kind, applied everywhere the data lives, and a record that it was done |
| HIPAA Expert Determination (164.514(b)(1)) | A qualified expert applies statistical or scientific methods and documents that the re-identification risk is very small | The expert's written determination; keeping shifted dates or 5-digit ZIP codes is possible only under this route |
| HIPAA limited data set (164.514(e)) | Dates, city, state and ZIP may stay; direct identifiers go | A data use agreement. It is still protected health information, not de-identified |
| GDPR and UK GDPR | Health data is special-category data (Article 9). Pseudonymised data is still personal data (Recital 26); only data that no one can reasonably re-identify is anonymous | A lawful basis plus an Article 9 condition, a DPIA for large-scale health processing, processor contracts, and an honest statement that pseudonymised data remains personal data |

Ask the user which frame applies and who signs off. If nobody knows, say so; do not pick one silently.

## The Safe Harbor list, and where each item hides

| Identifier kind | Typical hiding places |
|---|---|
| Names | DICOM `PatientName`, `OtherPatientNames`, SR person names; note headers and signatures; file and folder names |
| Geography smaller than a state | Addresses, `InstitutionAddress`, free-text history. A 3-digit ZIP prefix may stay only if its area has more than 20,000 people; otherwise it becomes `000` |
| Dates (except year) tied to the person, and ages over 89 | Birth, admission, discharge, death and study dates; timestamps in waveforms and logs; ages 90 and over must be grouped as 90 or older |
| Telephone and fax numbers, email addresses | Contact fields, referral letters, scanned forms |
| Social security, medical record, health plan and account numbers | `PatientID`, `AccessionNumber`, order numbers, barcodes on slide labels, insurance fields |
| Certificate or license numbers, vehicle identifiers | Free text, scanned documents |
| Device identifiers and serial numbers | Implant serials, `DeviceSerialNumber`, wearable device IDs |
| URLs and IP addresses | Portal links in notes, export metadata, server logs |
| Biometric identifiers, full-face photographs and comparable images | Clinical photos, 3D head CT and MR (a surface rendering shows the face), voice recordings |
| Any other unique number, characteristic or code | Rare diagnoses with small counts, study IDs built from MRNs, pseudonyms derived from identifiers |

## Where identifiers hide in DICOM

- **Header attributes**, including inside nested sequences (`RequestAttributesSequence`, `OtherPatientIDsSequence`, SR content trees).
- **Private tags.** Vendor blocks can copy names, IDs and dates. Remove them unless a vetted list says a specific private attribute is safe.
- **UIDs.** Original UIDs link back to the hospital archive, and some embed dates, device serials or the site's registered root. Replace them consistently.
- **Pixels.** Burned-in text in ultrasound, secondary captures, angiography, scanned documents and dose screens; overlays; slide label and macro images; faces in head volumes. A header tool never sees these.
- **Embedded documents and reports.** Encapsulated PDFs and SR free text.
- **Around the files.** File names, folder paths (often `NAME_MRN/DATE`), DICOMDIR records, transfer logs, spreadsheets that map files to patients.

The standard approach is the Basic Application Level Confidentiality Profile in DICOM PS3.15 Annex E, plus options chosen for the use case: retain longitudinal information with modified dates, retain patient characteristics (age, sex, size, weight), retain device identity, retain UIDs, retain safe private attributes, and the clean options (pixel data, recognizable visual features, graphics, structured content, descriptors). Record what was applied in `DeidentificationMethod` and `DeidentificationMethodCodeSequence`, and set `PatientIdentityRemoved` to `YES` only after it is true.

Tools: pydicom with explicit rules (`ds.walk`, `ds.remove_private_tags()`), the `deid` recipe-based package, `dicognito`, and the RSNA anonymizer and CTP pipeline for site-scale work. For pixels: OCR-assisted detection of burned-in text plus human review, and a defacing tool for head volumes (check what defacing does to the analysis). For whole-slide files: drop label and macro images (`whole-slide-pathology.md`).

## Tables, notes and signals

- **EHR tables.** Drop direct-identifier columns, then handle quasi-identifiers: age, sex, ZIP, dates, rare diagnoses, extreme lab values, very long stays. Check group sizes (k-anonymity) on the combinations someone could know, and suppress small cells in published tables; many data use agreements forbid cells below 11.
- **Free-text notes.** Rule- and model-based scrubbers (for example Microsoft Presidio or Philter) miss things. Measure recall on a hand-annotated sample from the same source before trusting a tool, and keep a human review step for anything published.
- **Signals.** EDF and BDF headers have patient and recording fields; WFDB headers have comment lines; device exports carry serials and timestamps. Shift or strip timestamps with the same per-patient offset as the clinical data.
- **Genomic data** is inherently identifying. De-identification of genomes is not achievable by removing fields; access control and data use agreements carry the protection.

## Pseudonyms, dates and the key

- Same person, same pseudonym across files, modalities and time. Under HIPAA a re-identification code must not be derived from information about the person, and its mechanism must not be disclosed (164.514(c)). The safe default is a random study ID per patient kept in a crosswalk table. A keyed hash (HMAC with a secret held by the custodian) is a common engineering choice; agree it with the privacy officer first. A plain hash of an MRN is reversible by brute force and is not acceptable.
- Shift all dates of one patient by the same random offset so intervals survive. Keep the offset in the crosswalk. Shifted dates are still dates for Safe Harbor purposes; keeping them needs Expert Determination.
- Replace UIDs through a consistent mapping (one new UID per original UID across the whole dataset), so series and references still link.
- The crosswalk lives with the custodian, encrypted and access-controlled, never in the shared dataset, the repository or the chat.

## How the agent works with identifiable data

- Run code where the data already lives. Print schemas, counts and aggregate statistics, not rows, values or images, into the conversation.
- Do not send identifiable data to a hosted model, API or web service unless the user confirms the organization allows it (a business associate agreement under HIPAA, a processor agreement under GDPR, and the dataset's own use terms).
- Never create realistic-looking fake patients to stand in for real ones in reports. For tests, use generators such as Synthea for EHR, `neurokit2` simulators for signals, or programmatically built phantoms, and mark the output synthetic.

## The bundled header checker

`../scripts/dicom_phi_check.py` reads DICOM Part 10 files with the standard library only (implicit and explicit VR, big endian, deflated and encapsulated pixel data, nested and undefined-length sequences) and lists identifying attributes that still hold values. It is read-only, never uses the network and hides values unless asked.

```bash
python3 <productcraft>/modules/life-sciences/scripts/dicom_phi_check.py deid_out/                     # summary across all files
python3 <productcraft>/modules/life-sciences/scripts/dicom_phi_check.py --per-file --strict deid_out/
python3 <productcraft>/modules/life-sciences/scripts/dicom_phi_check.py --uid-root 2.25 \
    --allow-pattern 'PatientID=SUBJ-[0-9]{4}' --allow-category date --json deid_out/ > phi_report.json
python3 <productcraft>/modules/life-sciences/scripts/dicom_phi_check.py --list-checks
```

- **HIGH**: patient identifiers with a value (names, IDs, birth date, addresses, phone numbers, accession and order numbers, insurance numbers), ages over 89, and header flags saying the pixels show burned-in text or a recognizable face.
- **WARN**: staff names, institution and device details, study-level IDs, free-text fields, dates, private groups, UIDs outside `--uid-root`, overlays, embedded documents, modalities prone to burned-in text without `BurnedInAnnotation` set to `NO`, head CT, MR or PET volumes, and `PatientIdentityRemoved` not `YES`.
- Accept a documented decision with `--allow KEYWORD`, `--allow-pattern KEYWORD=REGEX` (the value must fully match, checked without printing it) or `--allow-category` (for example `date` after documented shifting). Allowed findings stay in the report as INFO.
- Exit 0 means no HIGH findings (and no WARN with `--strict`); 1 means findings; 2 means a file could not be parsed or no DICOM files were found. Use `--force` only for raw datasets without the preamble.
- It does not look at pixels, embedded documents, file names or the folder structure. A clean run is one piece of evidence, not the determination.

## Checks (done when)

- The frame (Safe Harbor, Expert Determination, limited data set, GDPR) and the person who signs off are named.
- The rules are written down: which attributes are removed, replaced or kept, which profile options apply, how dates, UIDs and pseudonyms are handled.
- `dicom_phi_check.py` reports no HIGH findings; every WARN is fixed or allowed with a written reason.
- Pixels were reviewed: all ultrasound, secondary capture, scanned and screen-capture images, a sample of the rest, slide label images removed, head volumes defaced if faces matter.
- Free-text scrubbing recall was measured on a labeled sample; small cells are suppressed in outputs.
- File and folder names carry no identifiers; the crosswalk is stored separately with access control.
- Nothing identifiable was printed into the conversation or sent to a service without confirmed permission.
