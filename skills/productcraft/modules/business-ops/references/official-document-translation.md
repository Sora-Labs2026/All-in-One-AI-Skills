# Translating visa and other official documents

Read this when the user needs a translation of an official document for a visa, immigration, university, court or licensing application: bank and income statements, employment or retirement letters, certificates of birth, marriage or education, business licences, identity documents. Extracting text from scans and building the output PDF are covered in `../../documents/references/pdf.md`; this file covers what makes a translation acceptable to an authority.

## Ground rules

- **Never alter facts.** Names, numbers, amounts, currencies, dates, document numbers, addresses and stamps are reproduced exactly. Do not round, convert currencies, "correct" apparent errors in the original, summarise, or omit anything, including footers, seals and handwritten notes.
- **A machine translation is a working draft, not a certified translation.** Never print "certified translation", a translator's statement or a signature on output the agent produced. Certification is a statement by a qualified human translator, made under the receiving authority's rules.
- **These documents are highly sensitive personal data** (identity, finances, family details). Process them locally where possible; do not upload them to third-party OCR or translation services without the user's explicit agreement; do not keep copies longer than needed.
- **Ask, do not guess,** when the official spelling of a name, the meaning of an abbreviation or an illegible entry matters.

## What authorities usually require (check the current rules of the receiving authority)

Requirements differ by country and by agency and change over time; read the authority's current guidance for the specific application.

| Authority (examples) | Typical requirement |
|---|---|
| US Citizenship and Immigration Services | A full English translation with the translator's certification that it is complete and accurate and that they are competent to translate from the language into English |
| UK Home Office | A translation with the translator's confirmation that it is accurate, the date, the translator's full name and signature, and their contact details |
| Australian Department of Home Affairs | Translations made in Australia by a translator accredited by the national accreditation authority (NAATI); translations made outside Australia accompanied by the translator's details |
| Immigration, Refugees and Citizenship Canada | A translation by a certified translator, or an affidavit from the translator when they are not certified; the translation must be accompanied by a copy of the original |

Some authorities also require notarisation, an apostille or legalisation of the original or of the translation, or a translator registered in a particular country. Others refuse translations made by the applicant or a relative.

## Workflow

1. **Confirm the purpose:** which authority, which application, which target language, and the authority's current translation rules. If certification is required, plan for a qualified translator to review and certify the draft.
2. **Get a clean image:** correct orientation (honour EXIF rotation), full page including edges, legible stamps. Ask for a better scan rather than guessing illegible parts.
3. **Extract text** with OCR, then check it against the image line by line, especially digits, dates and names. OCR confuses 0 and O, 1 and l, and similar-looking characters in many scripts.
4. **Translate completely and literally enough to be checkable,** keeping the original's structure: headings, tables, field labels and their values in the same order. Prefer the authority's or the official English terms for institutions and titles where they exist; otherwise translate descriptively and keep the original term in brackets once.
5. **Names:** use the spelling in the person's passport. If the passport is not available, transliterate with the standard system for the language (for example Hanyu Pinyin for Mandarin, with the family name as the passport shows it) and flag it for the user to confirm.
6. **Dates and numbers:** render dates in an unambiguous English form with the same day, month and year ("8 October 2026", never "10/8/2026", which readers in different countries read differently), and add a translator's note when the original uses a calendar or era system that needs explaining. Keep currency codes, amounts and digit groupings exactly; do not convert.
7. **Non-text elements:** describe them in brackets where they appear: `[Round red seal: "Example City Public Security Bureau"]`, `[Signature]`, `[Handwritten: "approved"]`, `[Illegible]`, `[Photograph]`. Translate the text inside seals and stamps.
8. **Translator's notes** go in brackets marked as such and only explain, never add facts.
9. **Output:** a document that pairs a copy of the original with the translation (side by side or original first, then translation), page-numbered, with the document title and the source language. Leave space and a clear placeholder for the qualified translator's statement, name, signature, date and contact details if certification is needed; do not fill it.
10. **Verify** against the image: every field translated, every number and date identical, names consistent across all of the applicant's documents.

## Example layout of a draft translation

```text
DRAFT TRANSLATION FOR REVIEW BY A QUALIFIED TRANSLATOR
Source language: Chinese (Simplified)    Target language: English
Document: Certificate of Employment      Pages: 1 of 1

[Letterhead: "Example Technology Co., Ltd." with company logo]

CERTIFICATE OF EMPLOYMENT

This is to certify that LI Mingyu (passport spelling to be confirmed),
ID card No. [masked in this example], has been employed by our company since
15 March 2018 as Senior Engineer, with an annual salary of
RMB 360,000.

[Round red seal: "Example Technology Co., Ltd. - Human Resources Department"]
[Signature]
Date: 8 October 2026

[Translator's note: "RMB" (renminbi) renders 人民币 in the original; the ISO currency code is CNY.]
```

The identity number is masked only in this example; a real translation reproduces it exactly as printed.

Placeholder for the certification, to be completed only by the qualified translator:

```text
TRANSLATOR'S STATEMENT
[[TRANSLATOR: wording required by the receiving authority]]
Name: [[TRANSLATOR]]   Qualification or accreditation: [[TRANSLATOR]]
Signature: ____________   Date: ____________   Contact: [[TRANSLATOR]]
```

## Pitfalls

| Pitfall | Fix |
|---|---|
| Adding "This is a certified translation" to machine output | Remove it; leave the certification block for a qualified translator |
| "Cleaning up" an amount or a date that looks wrong | Reproduce exactly; add a translator's note if needed; tell the user |
| Different spellings of the same name across documents | Use the passport spelling everywhere; list any mismatch for the user |
| Omitting stamps, footers, back pages or small print | Translate or describe every element on every page |
| Translating titles and institutions loosely | Use official English names where they exist; keep the original in brackets |
| Uploading identity documents to an online service without asking | Local processing by default; explicit consent for any upload |

## Checks (done when)

- [ ] The receiving authority's current translation rules were identified, including certification, notarisation or apostille needs.
- [ ] Every element of every page is translated or described; nothing is summarised or omitted.
- [ ] All numbers, amounts, dates and identifiers match the original exactly; names match the passport.
- [ ] The output does not claim certification; a placeholder is left for a qualified translator where required.
- [ ] The documents were processed locally or with the user's explicit consent, and temporary copies were removed.
