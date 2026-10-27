# Organizing invoices and receipts

Read this to turn a folder of invoices, receipts, credit notes and bills (PDFs, e-invoice XML, scans and phone photos) into consistently named files in a clear folder structure, with a ledger CSV for the user or their accountant. These are financial records with personal data: accuracy and privacy come before speed. This is bookkeeping support, not tax or accounting advice; categories and deductibility are the user's or their accountant's decision.

Contents: ground rules · set up · extract the data · parse amounts and dates · validate · name and file · the ledger · plan, review and apply · verify · done when.

## Ground rules

1. **Originals stay untouched.** Work on a copy of the inbox, or leave originals in place and file copies. Record a SHA-256 of every original so you can show later that none changed.
2. **Local only.** Do not upload documents to online OCR, conversion or AI services without the user's explicit permission. Use local tools.
3. **Minimal exposure.** Do not paste document contents into the conversation beyond what the task needs. The ledger holds no full card numbers, bank account numbers or passwords; mask to the last four characters where a reference is needed.
4. **No guessing.** A field that cannot be read with confidence is marked for review, not filled with a plausible value. Never invent invoice numbers, dates, amounts or vendors.
5. **No sending.** Do not email, upload or share the results; hand them to the user.
6. **Ask, then move.** Renames and moves follow the plan-review-apply cycle in `file-organization.md`.

## Set up

Agree with the user:
- the folder, the period (calendar or fiscal year, which can differ), and the document types included;
- the folder scheme: by year then category, by year then vendor, or the accountant's preferred layout;
- the category labels, if any (the user's or the accountant's list; propose a short list if they have none);
- the file name pattern (default below) and the ledger columns their accounting software or accountant expects.

## Extract the data

Use the most reliable route each file offers, in this order:

1. **Structured e-invoice data.** More and more invoices carry machine-readable XML, either as the whole invoice (UBL or UN/CEFACT CII syntax, for example XRechnung or Peppol documents) or embedded in a PDF/A-3 (Factur-X and ZUGFeRD, attachment usually named `factur-x.xml` or `zugferd-invoice.xml`). Several EU countries now require structured invoices (Germany requires every business to be able to receive them since January 2025; France phases in from September 2026); check the current rules where the user is. XML gives exact values, so prefer it to the PDF text.

```bash
pdfdetach -list invoice.pdf                     # poppler: lists embedded files
pdfdetach -saveall -o extracted/ invoice.pdf
```

```python
import xml.etree.ElementTree as ET   # does not fetch external entities; still cap input size

NS = {"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
      "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
      "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"}

def read_cii(path):
    root = ET.parse(path).getroot()
    text = lambda xp: (root.findtext(xp, namespaces=NS) or "").strip()
    total = ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
    return {
        "number": text("rsm:ExchangedDocument/ram:ID"),
        "date": text("rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString"),   # format 102 = YYYYMMDD
        "vendor": text(".//ram:SellerTradeParty/ram:Name"),
        "currency": text(".//ram:InvoiceCurrencyCode"),
        "net": text(total + "ram:TaxBasisTotalAmount"),
        "tax": text(total + "ram:TaxTotalAmount"),
        "gross": text(total + "ram:GrandTotalAmount"),
        "due": text(total + "ram:DuePayableAmount"),
    }
```

UBL documents carry the same facts under `cbc:ID`, `cbc:IssueDate`, `cac:AccountingSupplierParty`, `cac:TaxTotal/cbc:TaxAmount` and `cac:LegalMonetaryTotal` (`cbc:TaxExclusiveAmount`, `cbc:TaxInclusiveAmount`, `cbc:PayableAmount`).

2. **The PDF's text layer.** `pdftotext -layout invoice.pdf -` or pdfplumber for tables (`../../documents/references/pdf.md`). Find fields by their labels, in every language the documents use ("Invoice date", "Rechnungsdatum", "Date de facture"), and take the total from the labeled total line, not the largest number on the page.
3. **OCR for scans and photos**, locally: OCRmyPDF with Tesseract and the right language packs (ask before installing), producing a searchable PDF you can then read as in step 2:

```bash
ocrmypdf --language eng+deu --rotate-pages --deskew --output-type pdfa scan.pdf work/scan-ocr.pdf
ocrmypdf --image-dpi 300 --language eng receipt.jpg work/receipt.pdf     # a phone photo
```

OCR misreads digits (`8` and `B`, `0` and `O`, `1` and `7`, lost decimal points). Treat every OCR value as low confidence until validated.

4. **Manual review** for whatever remains: list the file and the missing fields for the user.

## Parse amounts and dates

Use `Decimal`, never floats, and refuse to guess when the format is ambiguous:

```python
import re
from decimal import Decimal, InvalidOperation

def parse_amount(text: str) -> Decimal | None:
    """'1.234,56', '1,234.56', '1 234,56', '(12.00)', '-12.30' -> Decimal; None when ambiguous ('1,234')."""
    negative = text.strip().startswith("(") and text.strip().endswith(")")
    s = re.sub(r"[^\d,.\-]", "", text.replace("−", "-"))
    if not re.fullmatch(r"-?[\d.,]*\d[\d.,]*", s):
        return None
    seps = [c for c in ",." if c in s]
    if len(seps) == 2:
        dec = s[max(s.rfind(","), s.rfind("."))]          # the later separator is the decimal one
    elif len(seps) == 1:
        sep = seps[0]
        if s.count(sep) > 1:
            dec = None                                     # 1.234.567: thousands only
        elif len(s) - s.rfind(sep) - 1 == 3:
            return None                                    # 1,234 or 1.234: depends on the locale; ask
        else:
            dec = sep
    else:
        dec = None
    for t in {",", "."} - {dec}:
        s = s.replace(t, "")
    if dec:
        s = s.replace(dec, ".")
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    return -value if negative else value
```

- **Currency:** keep the document's currency. A bare `$` can mean several currencies; take the code from the document or the vendor's country. Do not convert currencies unless the user gives the rate source and date.
- **Dates:** ISO (`2025-03-04`) and written months are unambiguous. `03/04/2025` is 3 April in most of the world and 4 March in the US; decide from the vendor's country or the document's language, and flag it when both readings are possible.
- **Which total:** the amount payable on an invoice (gross, including tax); credit notes and refunds are negative; a receipt's total may include a tip; "amount due" can differ from the total after a deposit. Record net, tax and gross separately when the document shows them.

## Validate

Flag the document for review when any of these fail:
- net + tax = gross, within a cent per tax line (rounding);
- the date lies in the agreed period and not in the future;
- vendor and number are present for invoices (receipts may lack a number);
- the currency is known;
- the same vendor and number, the same file hash, or the same vendor, date and amount appear more than once (possible duplicate: the emailed PDF and the portal download). Duplicates are flagged, never deleted.

## Name and file

Default name pattern, sortable and portable:

```text
YYYY-MM-DD_vendor_document-number_gross-CUR.ext
2025-03-14_northwind-traders_INV-20931_1240.00-EUR.pdf
2025-03-15_city-parking_receipt_6.50-GBP.jpg
2025-04-02_northwind-traders_CN-311_-120.00-EUR.pdf       # credit note
```

- Vendor slug: lowercase, hyphens, no punctuation, consistent for the same vendor (keep a small alias table: "Northwind Traders Ltd", "NORTHWIND" -> `northwind-traders`).
- Keep the original extension. File by the agreed scheme, for example `2025/` then category or vendor, and a `needs-review/` folder for anything flagged.
- Names that would collide get a suffix rather than overwriting; the planner handles this.

## The ledger

Write a CSV next to the files (UTF-8; add a byte-order mark if the user opens it in Excel):

| Column | Example |
|---|---|
| `date` | 2025-03-14 |
| `vendor` | Northwind Traders |
| `type` | invoice, receipt, credit note, bill |
| `number` | INV-20931 |
| `currency`, `net`, `tax`, `gross` | EUR, 1033.33, 206.67, 1240.00 |
| `category` | the user's label, or empty |
| `file` | 2025/office/2025-03-14_northwind-traders_INV-20931_1240.00-EUR.pdf |
| `sha256` | hash of the filed copy |
| `extracted_from` | xml, text, ocr, manual |
| `review` | the reasons it needs review, or empty |

Text cells that start with `=`, `+`, `-` or `@` can run as formulas when opened in a spreadsheet; neutralize them as described in `../../documents/references/excel-xlsx.md` (formula injection), while keeping numeric columns numeric. If the accountant's software needs another layout, write that as a second export from the same data.

## Plan, review and apply

Write a rename map (`source,target`) from the extracted data and check it with the planner, which never touches files:

```bash
python3 <productcraft>/modules/creative-media/scripts/organize_plan.py work/inbox \
  --from-csv renames.csv --dest work/filed --format text
```

It rejects targets that escape the destination, cleans characters that are invalid on common file systems, flags extension changes, and resolves collisions. Show the user the summary, the review items and the ledger totals; apply only after approval, following `file-organization.md` (apply and undo scripts, nothing overwritten).

## Verify

1. Every input file is accounted for: filed, in `needs-review/`, or listed as skipped with a reason. The counts add up.
2. Ledger totals per currency equal the sum over the filed documents; totals are reported per currency, never added across currencies.
3. Spot-check at least five documents, or about one in ten for large sets, by opening each file and comparing date, vendor, number and amounts with its ledger row.
4. The hashes of the originals are unchanged.
5. The ledger contains no full card or bank account numbers.

## Retention and next steps

How long records must be kept, and whether a scan may replace a paper original, depends on the country and the type of record (from several years to a decade or more, with rules for digital archives in some places). Tell the user to confirm with their accountant or tax authority before discarding any original, paper or digital. Suggest a routine (a monthly run over a single inbox folder) rather than an automated watcher that moves files unsupervised.

## Done when

- Every document is filed under the agreed scheme or flagged in `needs-review/` with the reason; nothing was deleted or overwritten, and originals are unchanged.
- The ledger matches the files: counts, per-currency totals and the spot checks agree; ambiguous dates, amounts and possible duplicates are flagged, not guessed.
- No document left the machine without permission, and the ledger holds no full payment card or account numbers.
- The report states how many values came from XML, text and OCR, and what the user still has to review.
