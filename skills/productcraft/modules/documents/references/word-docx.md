# Word (.docx) with python-docx

Read this when a Word document is an input or the deliverable. Snippets target `python-docx` 1.2 (comments need 1.2 or later). Check the installed version first: `python3 -c "import docx; print(docx.__version__)"`.

Contents: model in one paragraph · create · read in body order · edit without losing formatting · comments · tracked changes · checks.

## How python-docx sees a document

A document is a body of block items (paragraphs and tables, in order), split into sections (page size, orientation, margins, headers and footers). A paragraph holds runs; a run is a stretch of text with one set of character formatting. Word splits text into runs unpredictably (spell-check, edits, revision IDs), so one visible word can sit across several runs. Styles live in the document, which is why starting from the client's own `.docx` or `.dotx` keeps their fonts, headings and numbering.

`python-docx` has no layout engine: it cannot tell you page count, where a page breaks or whether a table fits. Render to find out (`convert-and-render.md`).

## Create

```python
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Inches, Pt

doc = Document()                        # or Document("client-template.docx") to inherit its styles
doc.styles["Normal"].font.name = "Liberation Sans"
doc.styles["Normal"].font.size = Pt(11)
doc.core_properties.title = "Quarterly report"
doc.core_properties.author = "Finance team"   # set it: templates may carry someone else's name

doc.add_heading("Quarterly report", level=0)  # level 0 = Title style
doc.add_heading("Summary", level=1)
p = doc.add_paragraph("Revenue grew ")
p.add_run("12%").bold = True
p.add_run(" against plan.")
doc.add_paragraph("First point", style="List Bullet")
doc.add_paragraph("Step one", style="List Number")

rows = [("Region", "Q1", "Q2"), ("North", "120", "135"), ("South", "98", "101")]
table = doc.add_table(rows=1, cols=3)
table.style = "Table Grid"
for cell, text in zip(table.rows[0].cells, rows[0]):
    cell.text = text
    cell.paragraphs[0].runs[0].bold = True
for row in rows[1:]:
    for cell, text in zip(table.add_row().cells, row):
        cell.text = text

doc.add_picture("chart.png", width=Inches(4))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

landscape = doc.add_section()                  # new section for a wide appendix
landscape.orientation = WD_ORIENT.LANDSCAPE
landscape.page_width, landscape.page_height = landscape.page_height, landscape.page_width

doc.sections[0].header.paragraphs[0].text = "Company confidential"
doc.save("report.docx")
```

Notes:
- Style names (`"List Bullet"`, `"Table Grid"`, `"Heading 1"`) must exist in the document. A client template may name them differently or in another language; list them with `[s.name for s in doc.styles]`.
- Setting `orientation` does not swap the page dimensions; swap width and height yourself, as above.
- Prefer styles over direct formatting so the user can restyle the document later.
- Build the file from a script saved next to the output, so a fix is a rerun, not a manual patch.

## Read in body order

`doc.paragraphs` and `doc.tables` are separate lists and lose the order between them. Walk the body instead:

```python
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

def iter_block_items(document):
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)

doc = Document("input.docx")
for block in iter_block_items(doc):
    if isinstance(block, Paragraph):
        print(block.style.name, block.text)
    else:
        print([[cell.text for cell in row.cells] for row in block.rows])
```

- Headers and footers: `section.header.paragraphs`, plus `first_page_header` and `even_page_header` when those are enabled.
- Text boxes, footnotes and endnotes are not exposed by the API. For a full-text read use `pandoc input.docx -t gfm` (keeps headings, lists and tables) or read the XML parts.
- Merged table cells repeat: `row.cells` returns the same cell object for each grid column it spans.
- **Tracked changes trap:** `paragraph.text` skips runs inside insertions. A paragraph reading "due in 45 days" with a tracked insertion of "45 days" comes back as "due in ." See tracked changes below.

## Edit without losing formatting

Rules: open the original, change only what the task needs, save under a new name. Never rebuild a client document from extracted text; that discards styles, numbering, fields and section settings.

Replacing text when a token may be split across runs (the replacement takes the formatting of the run where the match starts):

```python
from docx import Document

def replace_in_paragraph(paragraph, old, new):
    count = 0
    while old:
        runs = paragraph.runs
        full = "".join(r.text for r in runs)
        start = full.find(old)
        if start < 0:
            return count
        end, pos, first = start + len(old), 0, True
        for run in runs:
            r_start, r_end = pos, pos + len(run.text)
            pos = r_end
            if r_end <= start or r_start >= end:
                continue
            cut_from, cut_to = max(start - r_start, 0), min(end - r_start, len(run.text))
            run.text = run.text[:cut_from] + (new if first else "") + run.text[cut_to:]
            first = False
        count += 1
    return count

def iter_all_paragraphs(document):
    """Body, table cells (nested tables too), headers and footers."""
    def walk(container):
        yield from container.paragraphs
        for table in getattr(container, "tables", []):
            for row in table.rows:
                for cell in row.cells:
                    yield from walk(cell)
    yield from walk(document)
    for s in document.sections:
        for part in (s.header, s.footer, s.first_page_header, s.first_page_footer, s.even_page_header, s.even_page_footer):
            if not part.is_linked_to_previous:
                yield from walk(part)

doc = Document("template.docx")
n = sum(replace_in_paragraph(p, "{{client_name}}", "Acme Ltd") for p in iter_all_paragraphs(doc))
doc.save("acme-letter.docx")
```

- Merged cells appear once per spanned column in `row.cells`; the helper may visit them more than once, which is harmless for replacement but not for counting.
- `paragraph.runs` does not include runs inside hyperlinks or tracked insertions, so tokens there are not replaced. Check the result with the inspector (below) for leftover tokens.
- Adding content in the middle: create the new paragraph at the end, then move its XML with `anchor._p.addnext(new_paragraph._p)`.

## Comments

```python
para = doc.add_paragraph("Figures are unaudited.")
doc.add_comment(para.runs, text="Confirm with auditors before sending.", author="Reviewer", initials="RV")
print([(c.author, c.text) for c in doc.comments])
```

Comments are visible to every recipient. Remove or resolve review comments before delivering a final version unless the user wants them kept.

## Tracked changes: what is and is not possible

- **Reading.** `pandoc --track-changes=all in.docx -t markdown` shows insertions and deletions with author and date; `--track-changes=accept` and `--track-changes=reject` give the text as it would read after accepting or rejecting everything. In Python, read `w:t` (inserted and unchanged text) and `w:delText` (deleted text) from the XML:

```python
from docx.oxml.ns import qn

def accepted_text(paragraph):
    return "".join(t.text or "" for t in paragraph._p.iter(qn("w:t")))

def original_text(paragraph):
    parts = []
    for el in paragraph._p.iter(qn("w:t"), qn("w:delText")):
        if not any(a.tag == qn("w:ins") for a in el.iterancestors()):
            parts.append(el.text or "")
    return "".join(parts)
```

- **Writing a redline.** python-docx has no revision API. A simple tracked replacement of one run can be written as XML: a copy of the old run inside `w:del` (with `w:t` renamed to `w:delText`) followed by a new run inside `w:ins`, each with a unique `w:id`, `w:author` and ISO `w:date`. This renders as a redline in Word and LibreOffice. Keep it to run-level text replacements; paragraph insertions, moves, table and formatting revisions need more XML and careful testing.

```python
import copy, datetime as dt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def tracked_replace_run(run, new_text, author, rev_id):
    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = run._r
    deleted = copy.deepcopy(old)
    for t in deleted.findall(qn("w:t")):
        t.tag = qn("w:delText")
    ins_run = OxmlElement("w:r")
    if old.find(qn("w:rPr")) is not None:
        ins_run.append(copy.deepcopy(old.find(qn("w:rPr"))))
    t = OxmlElement("w:t"); t.text = new_text; t.set(qn("xml:space"), "preserve")
    ins_run.append(t)
    for tag, child, rid in (("w:del", deleted, rev_id), ("w:ins", ins_run, rev_id + 1)):
        el = OxmlElement(tag)
        el.set(qn("w:id"), str(rid)); el.set(qn("w:author"), author); el.set(qn("w:date"), when)
        el.append(child)
        old.addprevious(el)
    old.getparent().remove(old)
```

  Pick `rev_id` above every existing `w:id` in the document part. Verify by rendering and with `pandoc --track-changes=all`.
- **Accepting or rejecting all changes.** Not available in python-docx or pandoc output to `.docx` without flattening formatting. Options, in order: ask the user to accept in Word; or accept in the XML (remove `w:del` elements, unwrap `w:ins`) on a copy and verify; or, if formatting does not matter, regenerate from `pandoc --track-changes=accept`. Say which you used.
- **Comparing two versions into a redline** needs a word processor's compare feature; there is no reliable headless route here. Offer a text diff (`pandoc -t plain` on both, then `diff`) as an alternative and say so.

## Checks before delivery

1. Re-open with `Document(path)`: expected heading sequence, table count and contents, image count (`len(doc.inline_shapes)`), sections and orientation.
2. `python3 <productcraft>/modules/documents/scripts/ooxml_inspect.py out.docx`: no leftover `{{tokens}}`, TODO markers or filler text; tracked changes, comments and hidden text only where intended; metadata names the right people.
3. Render to PDF and PNG and look at every page of short documents, or the first, last and every page with a table, image or section change in long ones. Check page breaks, table widths, header and footer content, numbering and fonts.
4. State in the hand-off that the visual check used LibreOffice and which fonts were substituted, if any.
