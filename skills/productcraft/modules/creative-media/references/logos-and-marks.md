# Logos, marks and identity boards

Read this when designing or refining a logo, producing the files a brand needs (lockups, favicons, app icons, one-color versions), using AI image tools in logo work, presenting identity concepts as boards, or showing other companies' logos on a page (customer and partner rows). Positioning and naming come first (`../../business-ops/references/brand-ideation-and-briefs.md`); documenting the finished system is `../../business-ops/references/brand-guidelines-and-audits.md`; iOS icon sets are `ios-app-icons.md`; the rulebook entries are `BRD-01` (grid and clear space) and `BRD-02` (small sizes) in `../../../references/ui-rules/branding.md`.

## Ground rules

- **A logo is a family of marks.** Plan the primary lockup, a compact mark for square and tiny spaces, and a one-color version from the start.
- **Design for the harshest use first:** 16 px in a browser tab, one color on a dark background, thread on fabric. A mark that only works at 300 px is a picture, not a logo.
- **Originality is checked, not assumed.** Search the category for lookalikes before presenting, and leave trademark clearance to counsel.
- **Generated images are sketches.** A model's raster output is never the deliverable; the final mark is redrawn as clean vector geometry by a person, and its creation is documented.
- **Show other companies' marks only with permission** and within their published usage rules.

## 1. Choose the structure

| Structure | What it is | Fits | Needs |
|---|---|---|---|
| Wordmark | The name set in type, often with one or two adjusted letters | Short, distinctive names | A compact fallback (initial or monogram) for small squares |
| Lockup | Symbol plus wordmark in a fixed arrangement (side by side, stacked) | Most new brands | Horizontal and stacked versions; symbol usable alone |
| Symbol alone | A mark with no name | Brands with years of recognition; secondary use for everyone else | Strong silhouette |
| Initial as symbol | One letter from the name drawn as the symbol | Long names; letters that suggest an image | The letter must read as both letter and image |
| Monogram | Two or three initials combined | Professional services, hospitality, heritage | Modern execution so it does not look dated |

A practical set for a new brand: horizontal lockup for headers and documents, stacked lockup for square layouts, symbol or initial for favicons, app icons, avatars and embroidery.

## 2. Choose the type register

Describe the register by its classification and what it signals in this category, then pick specific typefaces whose licenses allow logo use and modification:

- **Geometric sans** (circles and straight strokes): optimistic, modern; can feel cold or generic without one distinctive detail.
- **Humanist sans** (calligraphic stress without serifs): warm and professional; a safe choice where restraint matters.
- **Neo-grotesque sans:** neutral and contemporary; needs color or a symbol to be memorable.
- **Transitional or modern serif:** editorial, considered, authoritative.
- **Old-style serif:** heritage, institutional, literary.
- **Slab serif:** sturdy, declarative.
- **Custom lettering:** most distinctive, most expensive; justified only when a name must own its letters.

Choosing the category's default register signals competence; choosing against it signals a position. Decide which the brief wants. Check the font license: many desktop licenses forbid modifying outlines for a logo, and some require a separate logo or trademark license. Convert final lettering to outlines so the font is not needed downstream.

## 3. Choose the symbol approach

| Approach | Recognition | Risk | Saved by |
|---|---|---|---|
| Literal (the thing named) | Fast | Cliché | A specific, confidently drawn version |
| Abstract gesture (a quality: growth, balance) | Slow | Arbitrary | Clear formal logic that repeats in the system |
| Geometric reduction | Medium | Identical to hundreds of marks | Unusual proportions, a distinctive wordmark beside it |
| Letter-derived | Medium | Reads as just a letter | Exaggerating the double reading |
| Monogram | Medium | Old-fashioned | Contemporary drawing and spacing |

Match symbol weight to the wordmark: a hairline wordmark with a heavy symbol looks like two logos. One idea per mark; a symbol carrying three metaphors reads as a committee.

## 4. Test every candidate

Eliminate candidates that fail more than two of these:

| Test | Pass when |
|---|---|
| 16 and 32 px | The compact mark is recognizable in a real browser tab, light and dark |
| One color | Pure black on white and white on black still read; nothing depends on color or gradient |
| Silhouette | Filled solid, the outline alone is identifiable |
| Recall | After a two-second look, an unfamiliar person names its main feature |
| Sketch from memory | Someone can draw it roughly after 30 seconds |
| Lookalike search | An image search for the category's logos shows no near-twins |
| Scale set | Lockup proportions hold at 25%, 50%, 100% and 200%; thin strokes survive |
| Physical | Embroidery (strokes about 1 mm or more at 40 mm wide, no tiny counters, few thread colors), foil or engraving (one color, no hairlines) |
| Motion | It has a natural way to enter and exit (draw-on, assemble, reveal) |

Show 6 to 12 finalists that differ in structure or approach, not ten wordmarks in similar sans faces. For each: name and index, structure, type register and face, symbol approach, color values with one-color and reversed versions, where it excels and where it needs a fallback, what it signals, what it rejects, and three to five context mockups (site header, document, favicon at 16 and 32 px, avatar, merchandise).

## 5. Build the production files

**Clean vector geometry.** Draw with the fewest anchor points that give the curve; place points at the extremes of curves (where the tangent is horizontal or vertical) and keep handles horizontal or vertical. Snap to a construction grid and document it. Join overlapping shapes into single paths; remove stray points, hidden layers and clipping masks that do nothing.

**SVG for screens.**

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 32" role="img" aria-labelledby="logo-title">
  <title id="logo-title">Northfield</title>
  <path fill="currentColor" d="..."/>
</svg>
```

- Set a `viewBox` and no fixed `width` or `height`, so CSS sizes it; trim the box to the artwork plus the documented clear space.
- Use `fill="currentColor"` for one-color marks so the surrounding text color themes it; use CSS custom properties for two-color marks.
- Optimize with SVGO (keep `viewBox`, keep `title`), then compare the optimized file against the original at 400% to catch distorted curves.
- Text converted to outlines; no embedded rasters; no editor metadata.
- When the logo links home, the link's name comes from the `title` or an `aria-label` on the link; do not repeat the brand name twice to screen readers.

**Favicons and touch icons** from the compact mark, drawn for the size rather than scaled down:

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png"><!-- 180 x 180, opaque -->
<link rel="manifest" href="/site.webmanifest"><!-- 192 and 512 px PNGs; a maskable icon with the mark inside the central 80% -->
```

An SVG favicon can carry its own dark variant with `@media (prefers-color-scheme: dark)` inside a `<style>` element. Check every icon in a real browser tab and on a phone home screen.

**Delivery matrix.** Per mark (lockup horizontal, lockup stacked, symbol): full color, one color dark, one color light, reversed on the brand's dark color; as SVG and PDF (vector), PNG at 512, 1024 and 2048 px wide with transparency, and print files in the print house's color space (CMYK or spot colors, converted with their profile, never by eye). Name files consistently (`northfield_lockup-horizontal_one-color-dark.svg`) and include a short usage sheet: clear space, minimum sizes, color values and what not to do.

## 6. AI image tools in logo work

- **Use them to explore**, not to finish: mood, symbol ideas, letter treatments. Write prompts that state the structure ("flat vector symbol, one color, no gradient, no text, centered, plain background") and the exclusions; generated letters are unreliable, so set type yourself.
- **Never prompt for a living designer's style or an existing company's mark.** Describe qualities instead (`generation-prompting.md`, "Safety, likeness and rights").
- **Vectorizing a raster sketch:** upscale with a model meant for flat graphics (photographic upscalers add grain and texture to flat color), trace to vector, then rebuild the curves by hand following section 5. Auto-traced paths have hundreds of uneven points and wobbly curves that show at large sizes.
- **Rights.** In several jurisdictions purely machine-generated images get no copyright protection, so a mark needs substantial human authorship to be protectable. Keep the record: prompts, model and version, selections, and every manual change. Tools differ in what they disclose about training data and whether they offer indemnity; for commercial identity work, prefer tools with clear terms and record which one was used. This is general information; the owner's counsel decides.
- **Mockups:** place the mark on product, signage or fabric with your own photography or licensed mockup files; warp it with a displacement map from the photo's luminance so it follows folds, and blend shadows over it. Mark generated mockups as concepts.

## 7. Identity boards and brand worlds

An identity board shows a direction as one composed image or slide: the mark, palette chips with values, type specimen, two or three applications, an image that sets the mood, and one line of positioning. Keep typography sparse and the grid visible, and make every board in a set share the same layout so directions are comparable.

When asked for new concepts "in the family of" a supplied reference image:

- State a target distance in words: **distant** (only mood and contrast shared), **related** (medium and tone shared; palette, layout and type new), **neighbor** (composition logic, texture and palette relationships shared; subjects, arrangement and letterforms new). Never closer than neighbor.
- List the reference's reusable grammar (density, layering, surface, light, type scale and placement, human presence) and its signature elements, which you must not reproduce: specific people and poses, distinctive objects and their arrangement, the exact layout, any name, slogan, mark or letterform.
- For a set of several brands, hold four to six constants (ratio, medium, palette relationship, wordmark scale and placement, tone) and give each brand its own name, meaning, setting, human action and signature motif. Generate one brand per request.
- Check every output: the name spelled exactly and shown once, no stray text, the brand's meaning visible, at least four signature elements different from the reference, and the set reading as one family. Save new versions beside old ones (`name-v2.png`); never overwrite.
- Keep the reference out of the deliverable and out of shared assets unless the owner has the rights (`reference-look-measurement.md`, "Measure, do not copy").

## 8. Other companies' logos on your pages

Customer, partner, integration and press rows:

- **Permission first:** a customer logo implies endorsement; get written consent and keep it on file. Use the company's own press kit files and follow its usage rules (clear space, colors, no alterations).
- Open-source brand icon collections are convenient for integration lists, but their license covers the drawing, not the trademark; usage rules still apply.
- **Normalize visually:** one treatment for the row (all one neutral color, or all full color), equal optical size rather than equal width (wide wordmarks need a smaller height than square symbols; balance by visible area), aligned on a shared center line.
- Mark each logo up as an image with the company name as its text alternative; when a logo links somewhere, the link name says where.
- Never fetch logos from search results or another site at runtime; store approved files locally.

## Done when

- [ ] The set includes a primary lockup, a stacked or square version and a compact mark, each in full color, one color and reversed.
- [ ] Every finalist passed the 16 px, one-color and silhouette tests in a real browser and on a dark background; lookalike search recorded.
- [ ] Vector files are clean (few points, outlined text, `viewBox`, `currentColor` where one-color) and match the originals at 400%.
- [ ] Favicon, touch and manifest icons exist and were viewed in a tab and on a home screen.
- [ ] AI-assisted work has a creation record; generated rasters are not shipped as the mark.
- [ ] Third-party logos have written permission, use the owners' files and share one visual treatment.
