# PowerPoint (.pptx) with python-pptx

Read this when a presentation is an input or the deliverable. Snippets target `python-pptx` 1.0.

Contents: model · templates and slide size · create · extract text · edit a template · reorder and delete slides · design checks · checks before delivery.

## How python-pptx sees a presentation

A presentation has slide masters, each with slide layouts; every slide is created from a layout and inherits its placeholders (title, body, picture, date, footer, slide number) and their positions. Shapes on a slide are placeholders, text boxes, pictures, tables, charts (graphic frames) and groups. Text lives in text frames made of paragraphs and runs, as in Word.

python-pptx has no rendering engine. It cannot tell whether text fits its box, whether shapes overlap visually, or how a chart looks. Render every slide to an image and look (`convert-and-render.md`).

## Templates and slide size

- Start from the user's template (`Presentation("brand.pptx")` or a `.potx` saved as `.pptx`) whenever one exists: it carries the fonts, colors, logo and layouts. List what it offers before choosing layouts:

```python
from pptx import Presentation
prs = Presentation("brand.pptx")
for i, layout in enumerate(prs.slide_layouts):
    print(i, layout.name, [(ph.placeholder_format.idx, ph.placeholder_format.type) for ph in layout.placeholders])
```

- Choose layouts by name, not index; indexes differ between templates.
- The library's built-in default template is 4:3 (10 x 7.5 in). Setting `prs.slide_width` to 13.333 in makes the slides 16:9 **but moves nothing**: titles and bodies stay in the left part of the slide. Prefer a real 16:9 template. If you must widen the default, stretch the master and layout placeholders too:

```python
from pptx import Presentation
from pptx.util import Inches

A_XFRM = "{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm"

def widen_to_16x9(prs, new_width=Inches(13.333)):
    factor = new_width / prs.slide_width
    prs.slide_width = new_width
    for master in prs.slide_masters:
        for container in [master, *master.slide_layouts]:
            for ph in container.placeholders:
                if ph._element.spPr.find(A_XFRM) is None:
                    continue                    # inherits its position from the master
                ph.left, ph.width = int(ph.left * factor), int(ph.width * factor)
    return prs

prs = widen_to_16x9(Presentation())
```

- Set `prs.core_properties.author` (and title). The default template's properties name someone unrelated to the user.

## Create

```python
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

prs = Presentation("brand.pptx")
layouts = {layout.name: layout for layout in prs.slide_layouts}

s = prs.slides.add_slide(layouts["Title Slide"])
s.shapes.title.text = "Q3 business review"
s.placeholders[1].text = "Finance team, October"

s = prs.slides.add_slide(layouts["Title and Content"])
s.shapes.title.text = "Highlights"
body = s.placeholders[1].text_frame
body.text = "Revenue up 12% on plan"
for text, level in [("North led growth", 1), ("Churn down to 2.1%", 0)]:
    para = body.add_paragraph()
    para.text, para.level = text, level
s.notes_slide.notes_text_frame.text = "Mention the one-off contract in North."

s = prs.slides.add_slide(layouts["Title Only"])
s.shapes.title.text = "Revenue by region"
data = CategoryChartData()
data.categories = ["North", "South", "East"]
data.add_series("Q2", (120, 98, 80))
data.add_series("Q3", (135, 101, 86))
chart = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(1.6), Inches(7.5), Inches(5.2), data).chart
chart.has_legend = True
chart.legend.position = XL_LEGEND_POSITION.BOTTOM
chart.legend.include_in_layout = False

table = s.shapes.add_table(4, 3, Inches(8.6), Inches(1.6), Inches(4.2), Inches(2.0)).table
for r, row in enumerate([("Region", "Q2", "Q3"), ("North", "120", "135"), ("South", "98", "101"), ("East", "80", "86")]):
    for c, value in enumerate(row):
        cell = table.cell(r, c)
        cell.text = value
        cell.text_frame.paragraphs[0].font.size = Pt(14)
        if c:
            cell.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT

s = prs.slides.add_slide(layouts["Blank"])
s.shapes.add_picture("photo.png", Inches(0.5), Inches(0.5), width=Inches(8))   # give width or height, not both, to keep aspect
box = s.shapes.add_textbox(Inches(8.8), Inches(0.5), Inches(4), Inches(1.5))
box.text_frame.word_wrap = True
run = box.text_frame.paragraphs[0].add_run()
run.text = "Site visit, September"
run.font.size, run.font.bold = Pt(24), True
run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
prs.save("deck.pptx")
```

- Charts made with `add_chart` are native and editable (the data sits in an embedded workbook). Prefer them to pasted images when the user will edit the deck.
- Put data in placeholders where the layout has them, so the template's styling applies; free text boxes ignore it.

## Extract text (slides, tables, groups, notes)

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

def iter_shape_text(shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shape_text(shape.shapes)
        elif shape.has_text_frame and shape.text_frame.text.strip():
            yield shape.text_frame.text
        elif getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                yield " | ".join(cell.text for cell in row.cells)

prs = Presentation("deck.pptx")
for n, slide in enumerate(prs.slides, start=1):
    notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
    print(n, slide.slide_layout.name, list(iter_shape_text(slide.shapes)), "notes:", notes)
```

Chart data is in `shape.chart.plots[0].categories` and each series' `values`. Text inside SmartArt is not exposed; render the slide or read its XML part.

## Edit a template without losing formatting

Replace text at run level so each run keeps its font, size and color. When a token is split across runs, collapse that paragraph into its first run (which keeps the first run's formatting):

```python
def replace_text_in_frame(text_frame, old, new):
    count = 0
    for para in text_frame.paragraphs:
        for run in para.runs:
            if old in run.text:
                run.text = run.text.replace(old, new)
                count += 1
        joined = "".join(r.text for r in para.runs)
        if old in joined:
            para.runs[0].text = joined.replace(old, new)
            for r in para.runs[1:]:
                r._r.getparent().remove(r._r)
            count += 1
    return count
```

Apply it to every shape with a text frame, every table cell, and the notes. Re-run text extraction afterwards and search for leftover tokens.

## Reorder, duplicate and delete slides

python-pptx has no public API for these; the slide order is the `sldIdLst` element.

```python
def move_slide(prs, old_index, new_index):
    ids = prs.slides._sldIdLst
    el = ids[old_index]
    ids.remove(el)
    ids.insert(new_index, el)

def delete_slide(prs, index):
    ids = prs.slides._sldIdLst
    sld_id = ids[index]
    prs.part.drop_rel(sld_id.rId)
    ids.remove(sld_id)
```

Duplicating a slide by copying its XML is fragile: charts, pictures and notes have relationships that must be copied too. Prefer creating a new slide from the same layout and filling it, or duplicate in the presentation application.

## Design checks that code cannot do

Look at the rendered slides for each of these:
- Text that overflows its placeholder, wraps into a third line in a title, or was shrunk by autofit to an unreadable size. python-pptx does not shrink text; `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` only sets a flag that the presentation application may honor on its next edit.
- Shapes overlapping or touching the slide edge, inconsistent margins, misaligned titles between slides.
- Contrast and size: body text readable from the back of a room (as a rule of thumb, no smaller than about 18 pt for projected slides), text over photos legible. For color contrast use the same ratios as screens (`modules/ui-rules.md`, color and contrast category).
- One message per slide; numbers in charts and tables match the source data.

## Checks before delivery

1. Re-open: slide count and order, layout names, titles, notes present where expected.
2. `python3 <productcraft>/modules/documents/scripts/ooxml_inspect.py deck.pptx`: no off-slide shapes, empty placeholders, leftover tokens or review comments you did not intend.
3. Render every slide to PNG and look at each one (a montage of thumbnails is fine for a first pass; open full size where something looks wrong).
4. Say in the hand-off that rendering used LibreOffice, which can differ from PowerPoint in font metrics and some effects.
