# Infographics

Read this to turn facts, numbers or a process into one designed graphic: a statistic summary, a comparison, a timeline, a how-to, a hierarchy or a map, for a report, a slide, a social post or print. The chart rules themselves live in `../../data-and-product-surfaces.md` (charts section) and, for charts made in analysis code, `../../data-engineering/references/plotting.md`; this file adds the editorial and layout work around them.

Contents: message and data first · pick the form · honest encoding · layout for the medium · color · build it with code, not an image model · accessibility · check it · done when.

## Message and data first

1. **Write the takeaway as a sentence** before designing: "Rents rose faster than wages in nine of the ten largest cities, 2015-2025." That sentence becomes the headline. A topic label ("Housing costs") is not a takeaway.
2. **Collect the data into a file** (`data.csv`) with one row per number shown, its unit, its date or period, and its source. Every number on the graphic comes from that file; nothing is typed into the layout by hand.
3. **Cite sources** on the graphic (publisher, title or dataset, year) and keep the full references, with links or identifiers, in a `sources.md` next to it. Never invent, round up or "estimate" a statistic to fill a gap; leave the gap or say the figure is unavailable.
4. **Check the arithmetic.** Shares add up to 100% (or say why not), percentages and percentage points are not mixed up, rates state their base ("per 100,000 residents"), and comparisons use the same period and definition.
5. **Decide the audience's question.** Experts want precision and method notes; a general audience wants one clear comparison and context ("about 1 in 4").

## Pick the form

| The content is | Form | Watch for |
|---|---|---|
| A few headline numbers | Large figures with short labels and a comparison each ("up from 31% in 2020") | Numbers without a reference point mean little |
| Change over time | Line chart, or a timeline for events | Uneven time spacing drawn as even |
| Ranking or comparison of categories | Sorted horizontal bars | Truncated axes; more than ten or so bars |
| Parts of a whole | Stacked bar or a small number of labeled segments; a pie only for two to four parts | Many thin slices; parts that do not sum to the whole |
| A sequence of steps | Numbered steps in reading order with one verb each | Arrows that cross; steps that hide decisions |
| A hierarchy or structure | Tree or nested boxes | Depth beyond three levels on one graphic |
| Places | Map only when location matters; otherwise a ranked list | Choropleths of raw counts, which mostly show where people live; normalize per capita |
| Before and after, A versus B | Two columns with the same scale and order | Different scales on the two sides |

One graphic carries one main comparison. If the data needs three, make a sequence of three panels or three graphics.

## Honest encoding

- Bars and areas start at zero; their length or area is the value (`../../data-and-product-surfaces.md`).
- Scale icons and circles by **area**, not height or radius: doubling the radius quadruples the area and exaggerates the value fourfold. For pictograms, repeat a fixed-size icon (10 icons = 10 units) instead of stretching one.
- No 3D effects, perspective or exploded pies; they distort what the eye compares.
- Use the same scale for panels meant to be compared, and say so ("same scale").
- Round consistently and to what the source supports. "23.47%" from a survey of 400 people claims precision it does not have.
- Show uncertainty when the source gives it (ranges, error bars, "estimate"), and label projections as projections.
- Label directly on the marks instead of a separate legend whenever there is room.

## Layout for the medium

- **Reading order.** Headline, then the main visual, then supporting detail, then sources and credits in small type at the bottom. One column for phone-first graphics; a clear grid for print.
- **Size for the display, not the canvas.** An image 1080 px wide shown at 360 CSS px on a phone shrinks everything to a third. For body text to show at 14 px or more, it must be at least 42 px on that canvas; set the type scale from the displayed size.
- **Common sizes** (check each platform's current help, since they change): square 1080 x 1080, portrait 1080 x 1350, wide 1920 x 1080 for slides, link previews about 1200 x 630. For print, see `posters-and-canvas.md`.
- **Long scrolling graphics** read poorly as one huge image on phones. Prefer a short sequence of panels or a web page with real text and inline charts.
- **Whitespace and grouping** carry the structure (`LAY-02`); boxes and dividers around everything add noise. Icons only where they speed recognition, from one consistent set (`ICO-` rules in `../../../references/ui-rules/icons-imagery.md`).

## Color

- Gray for context, one accent for the point being made, a second color only for a real second category.
- For categorical data, use a palette tested for common color-vision deficiencies. The Okabe-Ito set is a widely used choice: `#E69F00` orange, `#56B4E9` sky blue, `#009E73` bluish green, `#F0E442` yellow, `#0072B2` blue, `#D55E00` vermillion, `#CC79A7` reddish purple, `#000000` black. Measured on white, only the blue reaches the 4.5:1 needed for text (5.2:1); yellow (1.3:1), orange and sky blue (about 2.3:1) and reddish purple (3.1:1) do not, and several also miss the 3:1 that bars and lines need against their background. Use them as fills with direct dark labels, add a thin dark outline to light bars, or place them on a ground where they reach 3:1.
- Sequential data (low to high) uses one hue from light to dark; diverging data (below and above a midpoint) uses two hues meeting at a neutral.
- Never let color be the only carrier of meaning (`COL-07`): add labels, patterns or position.
- Test: view the graphic in grayscale and with a color-vision-deficiency simulation (browser developer tools can emulate protanopia, deuteranopia and tritanopia), and measure text contrast (`COL-01`).

## Build it with code, not an image model

Image-generation models misspell labels, invent numbers and draw bars that do not match the data. Use them, at most, for a decorative illustration that carries no data, and label it as generated. Build the graphic itself from the data file:

- **SVG or HTML with CSS**, with charts from a charting library or hand-written SVG, rendered to PNG or PDF with a headless browser (the Playwright pattern in `posters-and-canvas.md`). Text stays real text: sharp, searchable, translatable.
- **matplotlib, plotnine or Vega-Lite** for the charts, exported as SVG and placed into the layout. `../../data-engineering/references/plotting.md` covers styling for each.
- Generate labels from the data, never by hand:

```python
import csv
from decimal import Decimal

rows = list(csv.DictReader(open("data.csv", newline="", encoding="utf-8")))
for row in rows:
    value = Decimal(row["value"])
    row["label"] = f"{value:.0f}%" if row["unit"] == "percent" else f"{value:,.0f} {row['unit']}"
assert len({r["period"] for r in rows}) == 1, "mixed periods on one chart"
```

Keep the build script, `data.csv` and `sources.md` with the output, so a corrected number is a one-line change and a rerun.

## Accessibility

- **Alt text** states the takeaway and the key numbers, not "infographic about housing". Where the graphic holds more than a sentence or two of information, publish the data or the full text alongside it (a table under the image, a linked page, or the post text).
- On a web page, prefer real HTML text and an SVG with `<title>` and `<desc>` over one flat image, and keep reading order logical for screen readers.
- Minimum sizes and contrast are measured at the displayed size, as above.
- Avoid animation for data graphics; if a version animates, follow the motion rules in `../../documents/references/animated-media.md`.

## Check it

1. Every number on the graphic traces to a row in `data.csv` and a source in `sources.md`. Spot-check at least three against the original source.
2. A script assertion or a manual pass confirms labels equal the data (no stale numbers from an earlier draft).
3. Encodings are honest: zero baselines, area scaling, shared scales where compared.
4. Render at the real display size (for example a 390 px wide phone viewport) and read every label without zooming.
5. Grayscale and color-vision checks pass; text contrast measured.
6. Alt text and the text or data alternative are written.

## Done when

- The headline states the finding, and the graphic shows exactly that comparison.
- All numbers are sourced, checked and generated from the data file; sources and their dates are visible.
- It reads at the displayed size on the target device, works without color, and has alt text plus a text or data alternative.
- Build script, data and sources are saved with the output.
