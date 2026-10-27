# Apply a theme or brand to slides, documents and pages

Read this to give a set of artifacts one consistent look: a deck, a report, a spreadsheet, a reveal.js talk, an HTML page, the charts inside them, or all of these for one event or client. It covers turning a brand or a chosen direction into a theme specification, and applying that specification to each format so it survives editing. Choosing a direction is `../../ui-distiller/references/style-catalog.md`; brand rules are `BRD-01` to `BRD-05` in `../../../references/ui-rules/branding.md`, with a worked brand page in `../../../examples/brand.html`.

Contents: the theme specification · where the values come from · apply it per format · fonts across machines · brands that are not yours · check it · done when.

## The theme specification

Write the theme once, as data, before touching any file. Roles, not just a list of hex values:

```json
{
  "name": "Harbor 2026",
  "color": {
    "bg": "#F7F5F0", "surface": "#FFFFFF", "text": "#1C2430", "text2": "#4A5566",
    "accent": "#0F6A73", "onAccent": "#FFFFFF", "border": "#C9CED6",
    "series": ["#0F6A73", "#C2571A", "#5B6B8C", "#8A7A2E", "#9C4F78"],
    "dark": {"bg": "#12171E", "text": "#E8ECF1", "accent": "#5CC2CB", "onAccent": "#0B1F22"}
  },
  "font": {"heading": "Source Serif 4", "body": "Source Sans 3", "mono": "Source Code Pro",
           "fallback": {"heading": "Georgia, serif", "body": "Arial, sans-serif"}},
  "scale": {"slideBodyPx": 36, "slideTitlePx": 64, "docBodyPt": 11, "docH1Pt": 22},
  "approvedPairs": [["text", "bg", "14.3:1"], ["text2", "bg", "6.9:1"], ["accent", "bg", "5.8:1"],
                    ["onAccent", "accent", "6.3:1"], ["dark.text", "dark.bg", "15.2:1"],
                    ["dark.onAccent", "dark.accent", "8.1:1"]]
}
```

- Every text color is listed with the backgrounds it may sit on and the measured ratio (`BRD-03`). Measure with the snippet in `../../ui-distiller/references/style-catalog.md` ("Applying a direction"); the ratios above were computed that way, and any changed value needs a new measurement.
- Chart series colors are a separate list, distinguishable for common color-vision deficiencies and in grayscale (`infographics.md`, Color).
- Status colors (success, warning, error) come from the product's semantic set if one exists.
- Sizes are given per medium: slides in pixels on the slide canvas or points on the slide, documents in points.

## Where the values come from

1. **An existing brand:** take colors, faces and logo files from the owner's brand guide or design tokens. Do not sample colors from a screenshot or a logo JPEG; ask for the official values. If the brand accent fails contrast for small text, keep it for large text and shapes and add a darker variant for text (`BRD-03`, `COL-11`).
2. **No brand:** pick one direction from the style catalog that fits the audience and occasion, and write one sentence on why. Do not invent a set of named themes for the user to browse unless they ask for options; two or three variants of one direction are easier to choose between.
3. **A client's or event's brand you were given:** use exactly what they supplied, within their usage rules (clear space, minimum sizes, forbidden recolors).

## Apply it per format

Apply the theme where the format keeps it: in the template, master, styles or variables, not as hard-coded colors on each element. Then later edits by other people stay on theme.

| Format | Where the theme lives | How to apply it | Pitfall |
|---|---|---|---|
| HTML page | CSS custom properties on `:root` | Map the spec to `--bg`, `--text`, `--accent` and use only the variables | Hard-coded colors left in components |
| reveal.js | Theme CSS variables such as `--r-background-color`, `--r-main-color`, `--r-main-font`, `--r-heading-font`, `--r-heading-color`, `--r-link-color` | Load a base theme, then override the variables in your own stylesheet after it | Overriding selectors instead of variables, which breaks when the base theme updates |
| PowerPoint (.pptx) | The theme part of the slide master (`ppt/theme/theme1.xml`): color scheme (`dk1`, `lt1`, `dk2`, `lt2`, `accent1` to `accent6`, `hlink`, `folHlink`) and font scheme (major for headings, minor for body) | Set the theme in a template (PowerPoint or LibreOffice: edit the master, save as `.potx` or `.pptx`), then build slides from it with python-pptx; color shapes with theme colors (`MSO_THEME_COLOR.ACCENT_1`), not RGB | python-pptx cannot edit theme XML; RGB-colored shapes ignore later theme changes |
| Word (.docx) | Styles (`styles.xml`) and the document theme (`word/theme/theme1.xml`) | Edit the styles (Normal, Heading 1-3, Title, Caption, table style) in a template or reference document; with python-docx set `doc.styles["Heading 1"].font`; with pandoc pass `--reference-doc` | Direct formatting on runs, which overrides styles; East Asian text needs its own font slot (`w:eastAsia`) |
| Excel (.xlsx) | Workbook theme and named cell styles | Build from a styled template; define named styles for headers, inputs and totals in openpyxl | Fills in saturated accents behind small numbers |
| Charts (matplotlib) | An `.mplstyle` file or `rcParams` | Set `axes.prop_cycle` to the series colors, `font.family`, text and axis colors; register font files with `matplotlib.font_manager.fontManager.addfont(path)` | Library default colors leaking into one chart |
| Charts (Chart.js, Vega-Lite) | Global defaults or a config object | Set default colors and fonts once at startup | Per-chart overrides drifting apart |
| PDF (reportlab) | Your own style objects | Register TTF fonts, define paragraph styles and colors from the spec | Base-14 fonts silently used when registration fails |

The format-specific mechanics (templates, run-level edits, rendering) are in `../../documents/references/powerpoint-pptx.md`, `../../documents/references/word-docx.md` and `../../documents/references/excel-xlsx.md`; follow them for the file work and apply the theme values from the spec.

Generate a CSS file from the spec instead of copying values by hand:

```python
import json
spec = json.load(open("theme.json", encoding="utf-8"))
c, f = spec["color"], spec["font"]
css = [":root {"]
css += [f"  --{k}: {v};" for k, v in c.items() if isinstance(v, str)]
css += [f"  --font-heading: '{f['heading']}', {f['fallback']['heading']};",
        f"  --font-body: '{f['body']}', {f['fallback']['body']};", "}"]
css += [".reveal { --r-background-color: var(--bg); --r-main-color: var(--text);",
        "  --r-heading-color: var(--text); --r-link-color: var(--accent);",
        "  --r-main-font: var(--font-body); --r-heading-font: var(--font-heading); }"]
open("theme.css", "w", encoding="utf-8").write("\n".join(css) + "\n")
```

## Fonts across machines

A deck or document is opened on machines that may not have the theme's fonts, and the result reflows.
- **Embed when allowed.** PowerPoint and LibreOffice can embed fonts in the file when the font's embedding permissions allow it; PDFs embed fonts by default when the font allows it. Read the permission bits before relying on embedding:

```python
from fontTools.ttLib import TTFont        # pip install fonttools
fs = TTFont("fonts/SourceSans3-Regular.ttf")["OS/2"].fsType
print({0: "installable", 2: "restricted: do not embed", 4: "preview and print", 8: "editable"}.get(fs & 0x000E, fs))
```

- **Or choose faces that are present everywhere** the file will be opened (system fonts on the recipients' platform, or widely installed families) and say so in the hand-off.
- **License.** OFL fonts may be embedded and shipped. Commercial licenses separate desktop, web, app and ebook embedding; check the tier (`../../legal-ready/references/business-children-email-assets-rights.md`, item 19).
- **Check substitution** after rendering: `pdffonts` on the exported PDF lists each font actually used; `fc-match "Font Name"` shows what a Linux renderer would substitute.

## Brands that are not yours

- Apply a real organization's brand only for that organization, with their assets and guidelines, or for clearly internal work (a pitch deck to them, a mock-up marked as such).
- Never produce material that looks issued by an organization that did not issue it: their logo, colors and voice on a document, slide or notice they did not author can mislead and may infringe their trademark.
- Never redraw a logo from memory or approximate it; use the official file or leave a labeled placeholder.
- Keep third-party logos (partners, customers, sponsors) at the sizes and clear space their own guidelines require, and only with permission to show them.

## Check it

1. **Render every slide or page** and look at it (`../../documents/references/convert-and-render.md`). Check that title positions, sizes and colors match across slides, and that text inside colored shapes uses the paired ink.
2. **Contrast:** every text and background combination that actually appears, including text on accent fills, chart labels and table header rows, meets `COL-01`. Recheck the dark variant separately.
3. **Hard-coded values:** search the output for colors that are not in the spec. For Office files, unzip a copy and grep the XML for `srgbClr` values; for HTML and CSS, grep for hex values outside the theme file.
4. **Fonts:** `pdffonts` shows the theme's faces, embedded; no unexpected fallback.
5. **Edit test:** add a slide from the template's layout or a new heading in the document; it should come out on theme without manual formatting.

## Done when

- One theme specification exists as data, with measured contrast for every approved pair.
- Each artifact takes its colors and fonts from its format's theme mechanism, not from per-element overrides.
- Rendered output was reviewed page by page; contrast, fonts and consistency checks passed or the exceptions are named.
- Brand assets are official and used within their rules; fonts are licensed for how the files will be shared.
