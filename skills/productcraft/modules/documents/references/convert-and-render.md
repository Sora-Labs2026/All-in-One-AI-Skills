# Convert between formats and render pages to images

Read this to convert documents (LibreOffice headless, pandoc) and to produce page images for visual verification. Tested with LibreOffice 24.2, pandoc 3.1 and poppler 24.

Contents: LibreOffice headless · pandoc · render to images · look at the images · fidelity limits.

## LibreOffice headless

```bash
# One profile directory per job: avoids clashes with a running LibreOffice and between parallel jobs.
PROFILE="file://$(mktemp -d)"
soffice -env:UserInstallation="$PROFILE" --headless --convert-to pdf  --outdir out/ report.docx
soffice -env:UserInstallation="$PROFILE" --headless --convert-to pdf  --outdir out/ deck.pptx
soffice -env:UserInstallation="$PROFILE" --headless --convert-to docx --outdir out/ legacy.doc    # .doc  -> .docx
soffice -env:UserInstallation="$PROFILE" --headless --convert-to xlsx --outdir out/ legacy.xls    # .xls  -> .xlsx
soffice -env:UserInstallation="$PROFILE" --headless --convert-to pptx --outdir out/ legacy.ppt    # .ppt  -> .pptx
```

Useful filter options:

```bash
# Tagged (accessible structure) PDF, declared as PDF/A-2b
soffice --headless --convert-to 'pdf:writer_pdf_Export:{"UseTaggedPDF":{"type":"boolean","value":"true"},"SelectPdfVersion":{"type":"long","value":"2"}}' --outdir out/ report.docx

# Every sheet of a workbook to its own UTF-8 CSV (out/book-<Sheet>.csv); the last field (-1) means all sheets
soffice --headless --convert-to 'csv:Text - txt - csv (StarCalc):44,34,UTF8,1,,0,false,true,false,false,false,-1' --outdir out/ book.xlsx
```

Rules:
- Convert a **copy**; write to a separate `--outdir`. The output keeps the input's base name, so two inputs with the same name overwrite each other.
- `soffice` usually exits 0 even when an input fails to load, and it may open a damaged or mislabelled file as plain text and convert that instead. After every conversion, check the output exists, has the expected type, and re-opens with the matching library (`pdfinfo`, `Document`, `load_workbook`, `Presentation`).
- Run it with a timeout (`timeout 180 soffice ...` or `subprocess.run(..., timeout=180)`). A dialog, a corrupt file or a lock can make it hang.
- Do not run conversions on untrusted files with macros enabled; headless conversion does not run macros by default, so do not change that.
- PDF-declared conformance (PDF/A) is a claim in the file, not proof. Use a PDF/A validator if conformance matters, and say whether you ran one.

## pandoc

```bash
pandoc notes.md -o notes.docx                                   # Markdown -> Word (title/author from YAML front matter)
pandoc notes.md --reference-doc=brand-reference.docx -o notes.docx   # use a styled reference document
pandoc -o custom-reference.docx --print-default-data-file reference.docx   # starting point for a reference doc
pandoc input.docx -t gfm --extract-media=media -o input.md      # Word -> Markdown, images saved to media/
pandoc --track-changes=all input.docx -t markdown               # show insertions and deletions with authors
pandoc input.html -o output.docx                                # HTML -> Word
```

- The reference document controls styles only (fonts, heading styles, table style, margins). Edit its styles in Word or LibreOffice, not its text.
- pandoc maps structure (headings, lists, tables, emphasis, links, images, footnotes), not layout. Expect to lose text boxes, columns, exact spacing and complex tables when going from `.docx` to Markdown and back. Use it to draft structured documents or to read them, not to round-trip a designed document.
- pandoc does not produce PDF without a LaTeX engine or another PDF engine installed; when none is present, go Markdown to `.docx` with pandoc, then `.docx` to PDF with LibreOffice.

## Render to images

```bash
pdftoppm -png -r 80 out/report.pdf pages/report          # pages/report-1.png, -2.png ...
pdftoppm -png -r 150 -f 3 -l 3 out/report.pdf pages/p3   # one page at higher resolution for detail
```

Office files go through PDF first: `.docx`/`.xlsx`/`.pptx` to PDF with LibreOffice, then `pdftoppm`. For a deck or a long document, one contact sheet is quicker to review than twenty files:

```python
from pathlib import Path
from PIL import Image

def contact_sheet(pngs, out, columns=3, thumb_width=480, gap=12):
    thumbs = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        im.thumbnail((thumb_width, thumb_width * 2))
        thumbs.append(im)
    rows = (len(thumbs) + columns - 1) // columns
    cell_h = max(t.height for t in thumbs)
    sheet = Image.new("RGB", (columns * (thumb_width + gap) + gap, rows * (cell_h + gap) + gap), "#888888")
    for i, t in enumerate(thumbs):
        sheet.paste(t, (gap + (i % columns) * (thumb_width + gap), gap + (i // columns) * (cell_h + gap)))
    sheet.save(out)

contact_sheet(sorted(Path("pages").glob("deck-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1])), "pages/deck-sheet.png")
```

Sort pages numerically, as above: a plain sort puts page 10 before page 2.

## Look at the images

Open the PNGs with the image-viewing tool you have and check, per page:
- **Content**: everything that should be there is there, in order; no placeholder tokens; numbers match the source.
- **Layout**: no text cut off, overflowing a box or running off the page; tables fit the width and repeat headers on continuation pages; no orphaned headings at the bottom of a page; images not stretched.
- **Consistency**: same fonts, sizes and margins throughout; titles in the same place on every slide; headers, footers and page numbers right on every page.
- **Readability**: text large enough for the medium; enough contrast (`modules/ui-rules.md`, color and contrast category).

If you cannot view images in this environment, say that the visual check was not done, and fall back to text checks (`pdftotext -layout`, page counts, the inspector) without claiming the layout is right.

## Fidelity limits to report

- LibreOffice is not Microsoft Office. Line breaks, page count, chart styling, SmartArt and some effects can differ. A clean LibreOffice render is strong evidence, not proof, of how the file looks in Word, Excel or PowerPoint.
- Missing fonts are substituted. Check with `fc-match "<font name>"` and `pdffonts` on the rendered PDF; metric-compatible substitutes (for example Carlito for Calibri, Liberation Sans for Arial) keep line breaks close, others do not. Name substitutions in the hand-off.
- Conversions from PDF to Word or PowerPoint produce positioned text boxes, not an editable document. Offer text extraction or a rebuild instead, and say why.
