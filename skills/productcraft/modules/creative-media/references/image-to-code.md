# From image to interface: design comps, references and faithful builds

Read this when the input is a picture and the output is working UI: a screenshot or mockup the user wants built, a design comp you generate first and then implement, or a set of phone-screen concepts for an app. The aim is to rebuild the design system the image implies (palette, type scale, spacing, radius, layout), then build real, accessible components with it and prove the result matches. Token structure is `../../ui-distiller/references/design-system-construction.md`; taste checks are `../../ui-distiller/references/taste.md`; prompting image models is `generation-prompting.md`.

## Ground rules

- **Match the system, not the pixels of someone else's work.** Rebuild layout, scale and color logic; never lift photographs, illustrations, logos, brand names or written copy from a reference you do not own. Replace them with the user's assets or clearly marked placeholders.
- **A reference image describes one state.** Hover, focus, error, loading, empty, long text and small screens are your job to design in the same language.
- **Measure, do not guess.** Sample colors from pixels, measure sizes against a known scale, and write the values down before writing CSS.
- **Accessibility wins ties.** A sampled color that fails contrast is adjusted, and the adjustment is noted.

## 1. Read the reference like a specification

Write a short spec before any code:

| Aspect | What to record |
|---|---|
| Canvas | Image width in pixels and the device it represents; the scale factor (a 2880 px wide desktop shot is a 1440 px viewport at 2x) |
| Palette | One page background family, surface tints, text colors (primary, secondary, muted), one action color, at most one accent, border colors, status colors if shown |
| Type | Classification and feel (geometric, grotesque, humanist, serif, mono); size of each level in CSS pixels; weight; line height; tracking on large headings |
| Spacing | The base unit (most designs use 4 or 8); section gaps, card padding, gaps between items |
| Shape and depth | Radius per element type; borders versus shadows; shadow softness and offset |
| Layout | Column grid and max width; the arrangement per section (split, stacked, asymmetric, dense grid); alignment lines |
| Components | Each distinct control and card with its anatomy |
| Imagery | Photo, illustration or product shots; crop and treatment |

### Sampling colors

```python
# palette.py: python3 palette.py ref.png 12   (Pillow; prints the dominant colors and their share)
import sys
from PIL import Image
img = Image.open(sys.argv[1]).convert("RGB")
img.thumbnail((400, 400))
q = img.quantize(colors=int(sys.argv[2]), method=Image.Quantize.MEDIANCUT)
pal, counts = q.getpalette(), sorted(q.getcolors(), reverse=True)
total = sum(c for c, _ in counts)
for c, i in counts:
    r, g, b = pal[i * 3:i * 3 + 3]
    print(f"#{r:02X}{g:02X}{b:02X}  {100 * c / total:5.1f}%")
```

Group the results by role. Anti-aliased edges and photos produce in-between colors; ignore anything under about 1% unless it is clearly a button or link color, and sample buttons and text directly with a picker at 100% zoom. JPEG and screenshots of screens shift colors slightly; round to a sensible value and build tonal ramps from it in OKLCH so lighter and darker steps keep the same hue.

### Measuring type and spacing

Divide measured pixel sizes by the scale factor. Cap height is about 0.7 of the font size for most sans faces, so a capital "H" 45 px tall at 2x is roughly 32 px type. Snap sizes to a scale (for example 12, 14, 16, 20, 24, 32, 40, 56), spacing to the base unit, and note where the reference itself is inconsistent; resolve such cases toward the scale.

## 2. Turn the spec into tokens

Write primitives (the measured values), semantic roles (background, surface, text levels, action, border, focus) and only the component tokens the design truly needs, in one token file. Verify every approved text pair in light and dark before building (4.5:1 body, 3:1 large text and controls). If the reference shows only a light theme and the product needs dark, design the dark semantic layer deliberately; do not invert.

If the look is close to one of the directions in `../../ui-distiller/references/style-catalog.md`, start from that direction's structure and replace its values with the measured ones; this keeps decisions consistent where the image is silent.

## 3. Build

- Build the page shell and grid first, then sections top to bottom, then components with every state.
- One shared component per control (button, input, card, dialog); no section-specific copies with slightly different padding.
- Real semantics: headings in order, buttons are buttons, links are links, form fields have labels, the dialog traps and returns focus.
- Responsive from the start: write down what each section does at 390 px, 768 px and 1440 px before coding it. Reference images are usually desktop only; mobile is a design decision, not a squeeze.
- Images use the user's assets or placeholders with the correct ratio and `object-fit: cover`, so swapping them later changes nothing else.
- Motion only where the reference implies it, with reduced-motion fallbacks (`../../ui-distiller/references/motion-engineering.md`).

## 4. Prove it matches

Render the build at the reference's viewport and compare.

```js
// compare.mjs: render at the reference viewport and save a screenshot for side-by-side review
import { chromium } from "playwright";
const [url, w, h, dpr] = [process.argv[2], 1440, 900, 2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dpr });
await page.goto(url, { waitUntil: "load" });
await page.addStyleTag({ content: "*,*::before,*::after{transition:none!important;animation:none!important}" });
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: "out/build.png", fullPage: false });
await browser.close();
```

```python
# side_by_side.py: python3 side_by_side.py ref.png out/build.png out/compare.png
import sys
from PIL import Image, ImageChops
a, b = (Image.open(p).convert("RGB") for p in sys.argv[1:3])
b = b.resize(a.size)
diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 40 else 0)
sheet = Image.new("RGB", (a.width * 3, a.height), "white")
for i, im in enumerate((a, b, diff.convert("RGB"))):
    sheet.paste(im, (i * a.width, 0))
sheet.save(sys.argv[3])
print(f"differing pixels: {100 * sum(1 for v in diff.getdata() if v) / (a.width * a.height):.1f}%")
```

The difference percentage is a guide, not a target: different copy and placeholder images will always differ. Look at the sheet for structural misses: wrong column widths, wrong vertical rhythm, missing elements, a heavier type weight, a different radius. Then check what the image could not show: keyboard focus, every state, 390 px width, 200% zoom, dark mode if supported.

## 5. Generating design comps first

When the user wants a high-quality page and there is no design yet, generating reference images before coding can help, provided the images become a specification and not a mood board.

**For websites:**

- Generate one wide image per section (hero, proof, features, product detail, pricing, FAQ, final call to action, footer) rather than one tall compressed board; small boards hide the detail you need to measure.
- Keep one palette, one type direction and one spacing rhythm across every section image; restate them in each prompt.
- Vary composition between sections (centered statement, split, offset media, dense grid, full-bleed image) so the page does not repeat one layout; vary hero scale deliberately (huge statement, medium split, small and quiet).
- Ask for flat, front-on screenshots of a browser viewport without device frames, at a stated width; ask for legible but placeholder copy, then write the real copy yourself.
- Avoid the generic tells listed in `../../ui-distiller/references/generic-tells-and-fixes.md`: nested cards inside cards, glowing gradients behind every section, pill badges on every heading.
- The hero must fit a small laptop viewport (about 1280 × 720) with the headline and primary action visible.

**For mobile apps:**

- Generate each screen of a flow as its own image at phone proportions (about 390 × 844 points), with the same status bar, navigation pattern, type and icon style on every screen.
- Show screens inside a plain device frame only for presentation; build from the unframed screen.
- Respect platform conventions in the comp: bottom tab bar or navigation drawer as the platform expects, 44 pt (iOS) or 48 dp (Android) touch targets, system text sizes that scale with the user's settings.
- Generate the states that matter: empty, loading, error, filled, and one with long text.

Treat each generated image as a reference under section 1. Generated text, icons and charts in comps are placeholders; rebuild them with real copy, a real icon family (`icon-sets-and-stock-imagery.md`) and real data.

## Pitfalls

- Copying a reference's brand assets or copy into the build "for now".
- Eyedropping one pixel of an anti-aliased edge and building the palette from it.
- Building only the pictured state; no focus, error or mobile layout.
- A different palette per section because each section image was sampled separately.
- Equating a low pixel-difference score with a good build, or a high one with a bad build.

## Done when

- [ ] A written spec lists canvas scale, palette roles, type scale, spacing unit, radius and depth, layout per section and components.
- [ ] One token file holds the measured values; every approved text pair passes contrast in each theme, with adjustments noted.
- [ ] Components exist once each with all states; the page works at 390, 768 and 1440 px and at 200% zoom.
- [ ] A side-by-side sheet against the reference was reviewed and structural differences fixed or explained.
- [ ] No third-party imagery, marks or copy from the reference ship in the build.
