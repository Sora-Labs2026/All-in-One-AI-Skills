# Posters, covers and canvas compositions

Read this to make a single static visual: a poster, a flyer, an event or book cover, a social or link-preview card, an album or podcast square, a certificate, or an abstract canvas piece. Output is a PNG for screens or a print-ready PDF. Data-led graphics are in `infographics.md`; slides are in `revealjs-presentations.md` and `../../documents/references/powerpoint-pptx.md`.

Contents: write the brief · pick the tool · grid and hierarchy · type · color and images · make it with code · print specifics · check it · done when.

## Write the brief

Settle these in a few lines before drawing anything:
- **Job and audience.** What must a passer-by know or do after three seconds? Usually one message plus the facts that act on it (what, when, where, how to get in).
- **Medium and size.** Screen (pixel size and where it is shown) or print (trim size in mm or inches, printer or service, quantity).
- **Fixed content.** Exact wording, logos, mandatory credits and legal lines, supplied by the user. Never invent dates, prices, names or sponsor logos.
- **Brand.** Existing colors, faces and logo rules win (`BRD-01` to `BRD-04` in `../../../references/ui-rules/branding.md`). Without a brand, pick one direction from `../../ui-distiller/references/style-catalog.md` and say why it fits.
- **Rights.** Who supplied each image and font, and under what license.

A one-paragraph brief is enough. A long "design philosophy" essay adds nothing the brief does not.

## Pick the tool

| Need | Tool | Notes |
|---|---|---|
| Good typography: kerning, hyphenation, OpenType features, many scripts | HTML and CSS rendered by Chromium (Playwright `page.screenshot()` or `page.pdf()`) | Best text shaping available headless; CSS grid for layout; fonts load with `@font-face` |
| Vector geometry, crisp at any size, editable later | SVG written by code, rendered with `rsvg-convert`, Inkscape's command line or a browser | Keep text as text, not paths, unless the printer asks for outlines |
| Pixel effects: textures, blends, photo compositing | Pillow, or pycairo for vector-plus-raster | Pillow shapes complex scripts only when built with libraqm (`features.check("raqm")`) |
| A multi-page or data-driven PDF | reportlab, see `../../documents/references/pdf.md` | Registers TTF fonts and embeds them |
| Generative or abstract art as the image | `generative-art.md`, then place the result here | Keep the generator's seed in the credits |

Prefer one tool per piece. Rendering text in one tool and pasting it as an image into another loses sharpness and searchability.

## Grid and hierarchy

- **Margins first.** Set an outer margin from the short side (5-8% of it for posters, more for covers that will be trimmed or framed). Nothing important goes outside it.
- **A simple grid.** 4, 6 or 12 columns with a fixed gutter; align every text block and image edge to it. A baseline grid or a fixed line-height multiple keeps vertical rhythm.
- **Three levels of text at most:** the message (large, few words), the facts (date, place, action), and the small print (credits, sponsors, legal). Each level is visibly different in size or weight, not merely slightly larger.
- **One focal point** (`LAY-05`): the largest, highest-contrast element is the thing people should see first. If two things compete, shrink one.
- **Space is structure.** Group related items by proximity (`LAY-02`); leave real empty space around the message rather than filling every corner.
- **Squint test.** Blur a screenshot or view it at thumbnail size; the order of importance should survive as a few shapes of clearly unequal size.

Reading distance sets size. A common sign-making rule of thumb is about 25 mm of letter height for every 3 m of viewing distance (1 inch per 10 feet) for comfortable reading; print a section at 100% and look at it from the real distance before trusting any rule. For screens, design at the displayed size: a 1080 px square shown 360 px wide divides every type size by three.

## Type

- Two families at most, often one family in two weights. Choose faces with the weights and characters the content needs (accents, numerals, punctuation in every language used).
- Set display type tightly (line height 0.95-1.1, slightly negative tracking for large sizes); body and small print at 1.3-1.5 line height and normal tracking.
- Avoid widows and single-word last lines in headlines; break lines by meaning, by hand, for the few lines a poster has.
- **Licenses.** SIL Open Font License faces can be embedded in PDFs and used in images and print, commercially. Commercial fonts often license desktop use (which usually covers print and static images) separately from web, app and ebook embedding; check the license before embedding in a PDF that will be distributed or in an app-generated image. Keep license files with the project. `../../ui-distiller/references/style-catalog.md` lists checked OFL pairings.

## Color and images

- Few colors with jobs: a ground, an ink, one accent. Check every text and background pair for contrast (`COL-01` in `../../../references/ui-rules/color-contrast.md`; 4.5:1 for small text, 3:1 for large). Text on photos needs a scrim, a solid band or a quiet area of the image (`COL-08`).
- Images: use the user's own, licensed stock, or properly labeled generated images (`generation-prompting.md`). Identifiable people need consent or a model release for promotional use; trademarks and logos other than the user's own and their sponsors' (with permission) stay out.
- Resolution: raster images at the final printed size need about 300 ppi; at 150 ppi they look soft up close. Upscaling invents detail (`image-enhancement.md`); prefer a better original.

## Make it with code

The HTML route, rendered to an exact size. It works for screen PNGs and for print PDFs:

```python
# pip install playwright && playwright install chromium   (ask before installing)
from pathlib import Path
from playwright.sync_api import sync_playwright

W_MM, H_MM, BLEED_MM = 297, 420, 3          # A3 portrait plus 3 mm bleed on each side
page_w, page_h = W_MM + 2 * BLEED_MM, H_MM + 2 * BLEED_MM

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(Path("poster.html").resolve().as_uri())
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.pdf(path="out/poster.pdf", width=f"{page_w}mm", height=f"{page_h}mm",
             print_background=True, prefer_css_page_size=False)
    page.set_viewport_size({"width": 1080, "height": 1350})   # 4:5 screen version; the CSS adapts to it
    page.screenshot(path="out/poster-1080.png", full_page=False)
    browser.close()
```

In the HTML, size the page with CSS (`@page { size: 303mm 426mm; margin: 0 }`), extend background colors and images into the bleed, and keep text inside a safe area at least 3-5 mm inside the trim. Load fonts from local files with `@font-face`, and wait for them before rendering, or the output uses a fallback face.

Write the poster as a small script plus its HTML or SVG, saved next to the output, so a change of date or wording is an edit and a rerun.

## Print specifics

Ask the printer, then follow their specification over any default here.
- **Bleed and trim:** 3 mm per side is common in Europe, 0.125 in (3.175 mm) in North America. The PDF page includes the bleed; crop marks only if the printer wants them.
- **Color:** most digital printers accept RGB PDFs and convert. For offset printing they may require CMYK with a named profile (for example a FOGRA or GRACoL characterization) and a total ink limit; convert with their profile using a tool that supports it (Ghostscript, Scribus) and expect bright RGB colors, especially saturated blues and greens, to dull. Rich black for large areas, plain black for small text.
- **Standards:** PDF/X-4 (live transparency) or PDF/X-1a (flattened, CMYK only) are the usual print-ready formats. A PDF's claim to conform is not proof; the printer's preflight is.
- **Fonts:** all embedded (`pdffonts out/poster.pdf` shows `emb yes` for every font).

## Check it

Render, then look, at real size:
1. `pdfinfo out/poster.pdf` shows the page size with bleed; `pdffonts` shows every font embedded.
2. Render the PDF to PNG (`pdftoppm -png -r 72` for an overview, `-r 300` for a detail crop) and view it, following `../../documents/references/convert-and-render.md`.
3. Check nothing important sits outside the safe area and nothing overlaps unintentionally. In the HTML route this snippet lists offenders:

```js
// Run with page.evaluate in the rendered page. Elements marked data-safe must stay inside #safe.
(() => {
  const safe = document.querySelector('#safe').getBoundingClientRect();
  const items = [...document.querySelectorAll('[data-safe]')].map((el) => [el, el.getBoundingClientRect()]);
  const outside = items.filter(([, r]) => r.left < safe.left || r.top < safe.top || r.right > safe.right || r.bottom > safe.bottom);
  const overlaps = [];
  items.forEach(([a, ra], i) => items.slice(i + 1).forEach(([b, rb]) => {
    if (ra.left < rb.right && rb.left < ra.right && ra.top < rb.bottom && rb.top < ra.bottom) overlaps.push([a.id, b.id]);
  }));
  return { outside: outside.map(([el]) => el.id || el.tagName), overlaps };
})();
```

4. Contrast for every text pair, measured, not guessed.
5. Proofread every fact against the brief: names, dates, times, addresses, prices, URLs. Scan any QR code and confirm where it goes.
6. Run the self-critique pass in `../../ui-distiller/references/taste.md` (first glance, blur, ornament inventory) and fix what it finds by refining what is there, not by adding decoration.
7. For posting online: write alt text that carries the poster's information (what, when, where), since an image of text is otherwise unreadable to screen readers, and put the key facts in the post text too.

## Done when

- The output has the stated pixel size or trim size plus bleed, and the printer's color and format requirements are met or the gaps are named.
- Every fact matches the brief; QR codes and links resolve to the right place.
- All fonts are embedded and licensed for this use; every image has a known source and license; generated images are labeled where required.
- Contrast passes for all text; nothing important is outside the safe area; the rendered image was looked at in full and at 100% detail.
- Alt text is written for screen versions, and the generating script is saved with the output.
