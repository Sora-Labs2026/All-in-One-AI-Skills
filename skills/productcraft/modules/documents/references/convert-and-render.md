# Convert between formats and render pages to images

Read this to convert documents (LibreOffice headless, pandoc), to turn documents into Markdown for language models, search and retrieval, and to produce page images for visual verification. Tested with LibreOffice 24.2, pandoc 3.1 and poppler 24; the Markdown converter notes apply to MarkItDown 0.1 and Docling 2.x (2025-2026), so check the installed versions.

Contents: LibreOffice headless · pandoc · documents to Markdown · render to images · look at the images · fidelity limits.

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

## Documents to Markdown

Use this when documents must become Markdown or plain text for a language model, a search index, a retrieval pipeline, a diff, or a move into a docs site. Markdown keeps structure (headings, lists, tables, links) and drops layout, so it is for reading and indexing, not for rebuilding the original.

| Input | Tool | Notes |
|---|---|---|
| `.docx` | pandoc (`-t gfm --extract-media=media`, above) | Best structure from Word; `--track-changes` controls what revision text appears |
| `.pptx`, `.xlsx`, `.docx`, PDF with a text layer, HTML, EPUB, mixed folders | MarkItDown (MIT; Python 3.10+; `pip install 'markitdown[docx,pptx,xlsx,pdf]'`) | Fast and text-first; slides with their notes, one table per sheet; little layout awareness |
| PDFs with columns, complex tables or formulas | Docling (MIT; downloads layout and table models on first use) | Slower; better reading order and table structure; can export Markdown or JSON |
| Scanned PDFs and images | OCR first (`pdf.md`, scanned pages), then one of the above | Report OCR output as uncertain |
| Spreadsheets for analysis | pandas per sheet, kept as CSV, or `DataFrame.to_markdown()` (needs `tabulate`) | Markdown tables lose types and formulas; language models read CSV well |

```bash
markitdown in/report.pdf -o out/report.md
markitdown in/deck.pptx -o out/deck.md
docling in/paper.pdf --to md --output out/
```

```python
from markitdown import MarkItDown

md = MarkItDown(enable_plugins=False)       # third-party plugins stay off unless vetted
result = md.convert("in/quarterly.docx")    # local paths only; see the security notes below
with open("out/quarterly.md", "w", encoding="utf-8") as handle:
    handle.write(result.text_content)
```

Licenses and services:
- Some PDF-to-Markdown libraries are AGPL-licensed (PyMuPDF and its Markdown helper, unless a commercial license is bought), and some converters ship model weights with commercial-use limits. That matters when the converter is bundled into a product or service; check before adopting one.
- MarkItDown's optional image descriptions and cloud document-analysis features send content to an outside service. Use them only with the user's permission and keys handled as in `../../agent-safety/GUIDE.md`.

Security, since converters parse untrusted files:
- Convert copies, with a timeout and size limits, and in an isolated worker when an application converts uploads (`../../launchguard/references/security-baseline.md`, file uploads).
- MarkItDown can also fetch and convert URLs. In a server, pass only local files or streams you have validated, never a URL taken from user input (server-side request forgery).
- Third-party converter plugins are code with your permissions; vet them first (`../../agent-safety/references/vetting-extensions.md`).

Check the result before using it:
- Headings are present and nested in order; multi-column pages read in the right order.
- Tables survived: merged cells and multi-row headers are often flattened or shifted. Compare each table with the rendered page.
- Repeated page headers, footers and page numbers are removed; words hyphenated at line ends are rejoined; ligatures (such as `ﬁ`) and odd spaces are normalized.
- Footnotes, captions and image alt text are kept or deliberately dropped; images become links or placeholders.
- Hidden content (comments, tracked changes, speaker notes, hidden sheets) is included or excluded on purpose, per ground rule 5 in `../GUIDE.md`.
- Word counts and a few key numbers match a plain `pdftotext` or pandoc extraction of the same file.
- Record the converter and its version in front matter or a log, so the output can be regenerated the same way.

For retrieval, split by headings and keep the source file and page or slide number with each chunk; chunking and evaluation are in `../../ml-engineering/references/rag-systems.md`.


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
