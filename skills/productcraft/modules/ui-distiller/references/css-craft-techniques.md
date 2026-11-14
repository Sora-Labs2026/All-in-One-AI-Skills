# UI Distiller: CSS craft techniques

Read this when a surface needs a specific finishing technique: edges that fade instead of cutting off, a hairline border with a gradient, a layered shadow, a blur that strengthens toward an edge, a spotlight that reveals a second image, shapes that melt together, chamfered corners, visible layout structure (guide lines, frames, corner brackets), step numerals and figure details, or a dithered background. Each section says when the technique fits, how to build it, and what breaks. Taste comes first: [taste.md](taste.md) and [generic-tells-and-fixes.md](generic-tells-and-fixes.md) list the cases where these same techniques read as generated decoration (glows, gradient borders everywhere, fake grid lines and "01 / 02" markers standing in for structure, dithering that is not the brand). Rules referenced as `COL`, `CMP`, `MOT` and `STY` are in `../../../references/ui-rules/`. Support notes are as of late 2025.

## Choosing a technique

| Want | Technique | Cheapest correct tool |
|---|---|---|
| Content fades out at a scroll edge or a strip end | Alpha mask | `mask-image: linear-gradient(...)` |
| A premium edge on one key surface | Gradient border | Two backgrounds (`padding-box` and `border-box`) |
| Depth for floating layers | Layered shadow | Three to five stacked `box-shadow` layers as tokens |
| A soft blur under a header or above a bottom bar | Progressive blur | Stacked `backdrop-filter` bands with masks |
| Hover reveals a second treatment of an image | Spotlight mask | Radial `mask-image` driven by custom properties |
| Blobs that merge like liquid | Gooey filter | SVG blur plus alpha threshold |
| Engineered, technical silhouettes | Chamfered corners | `clip-path: polygon()` (or `corner-shape: bevel` where supported) |
| Visible measured structure | Frames and guide lines | Grid with 1px gaps, pseudo-element lines, background-drawn brackets |
| Ordered markers and steady figures | Number details | CSS counters, `font-variant-numeric` |
| A textured monochrome field | Ordered dither | Low-resolution canvas scaled with `image-rendering: pixelated` |

## Edge fades with alpha masks

A mask keeps the alpha of its image and discards color: opaque areas show the element, transparent areas hide it. Use for horizontal strips, scroll containers and image edges. Masks are unprefixed in all current engines; add `-webkit-mask-*` duplicates only if you still support Safari before 15.4.

```css
.fade-x { --fade: 48px;
  mask-image: linear-gradient(to right, transparent, #000 var(--fade), #000 calc(100% - var(--fade)), transparent); }
.fade-bottom { mask-image: linear-gradient(#000 70%, transparent); }
```

- Use a length (32-64px) rather than a percentage for strips, so the fade is the same on a phone and a wide screen.
- For a soft rather than total fade, end at `rgb(0 0 0 / 0.25)` instead of `transparent`.
- Fade a scroll container only on the side that has more content. With scroll-driven animations (`animation-timeline: scroll(self inline)`) animate two registered custom properties that feed the gradient stops; elsewhere, toggle classes from the scroll position.
- A mask also hides focus rings and hit areas inside the faded zone. Keep interactive items out of the fade, or pad the container so the first item starts after it.

## Gradient borders

For the one surface that deserves a refined edge: the selected plan, the active panel, a hero card. Not every card (`CMP-07`, taste detector on gradient borders).

```css
.edge {
  --fill: var(--surface-1);
  border: 1px solid transparent; border-radius: 16px;
  background:
    linear-gradient(var(--fill) 0 0) padding-box,
    linear-gradient(150deg, rgb(255 255 255 / 0.32), var(--accent-a30) 45%, rgb(255 255 255 / 0.06)) border-box;
}
```

When the surface already has its own background (an image, a glass blur), draw the ring on a pseudo-element and cut out its middle:

```css
.edge-ring { position: relative; border-radius: 16px; }
.edge-ring::after {
  content: ""; position: absolute; inset: 0; padding: 1px; border-radius: inherit; pointer-events: none;
  background: linear-gradient(150deg, var(--ring-a), var(--ring-b));
  mask: linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0);
}
```

- One width (1px; 1.5-2px only for a large active surface), radius inherited, three stops at most: a highlight, the accent, a near-transparent fade. Keep stop opacity under about 0.4 so the edge frames rather than competes.
- Tune separately for light and dark themes; an alpha that glows on dark disappears on white.
- A rotating border (`@property --angle { syntax: "<angle>"; inherits: false; initial-value: 0deg; }` feeding a `conic-gradient(from var(--angle), ...)`) is for a single in-progress or featured state, 4-8s per turn, off under reduced motion (`MOT-04`), and never the only sign of state.
- A gradient edge is not a focus indicator. Keep a solid `:focus-visible` outline with at least 3:1 contrast (`COL`).
- An animated metallic border rendered with WebGL is in [webgl-backgrounds-and-3d.md](../../creative-media/references/webgl-backgrounds-and-3d.md); keep this CSS border as its fallback.

## Layered shadows

One blurred shadow looks like a smudge; real objects cast a tight contact shadow plus a wide soft one. Stack layers whose offset and blur roughly double while each stays faint, and keep them as three tokens (`CMP-07`): low for controls, mid for cards that float (menus, popovers), high for dialogs and drag previews.

```css
:root {
  --shadow-ink: 220 25% 12%;   /* tint toward the page hue, not pure black */
  --elev-1: 0 0 0 1px hsl(var(--shadow-ink) / 0.07), 0 1px 2px hsl(var(--shadow-ink) / 0.08);
  --elev-2: 0 0 0 1px hsl(var(--shadow-ink) / 0.06), 0 1px 2px -1px hsl(var(--shadow-ink) / 0.08),
            0 4px 8px -4px hsl(var(--shadow-ink) / 0.08), 0 12px 20px -8px hsl(var(--shadow-ink) / 0.08);
  --elev-3: 0 0 0 1px hsl(var(--shadow-ink) / 0.05), 0 2px 4px -2px hsl(var(--shadow-ink) / 0.06),
            0 8px 16px -6px hsl(var(--shadow-ink) / 0.08), 0 24px 40px -12px hsl(var(--shadow-ink) / 0.12),
            0 48px 80px -24px hsl(var(--shadow-ink) / 0.14);
}
```

- The first layer (a 1px spread ring) replaces the border, so a surface never carries both.
- Negative spread on the larger layers keeps the shadow under the object instead of haloing its sides.
- Elevation change on interaction (hover lift) moves one step, never two, and animates by cross-fading a pseudo-element that holds the higher shadow, since animating `box-shadow` repaints every frame.
- Dark mode: shadows barely read; separate with a lighter surface and an inner top highlight (`inset 0 1px 0 rgb(255 255 255 / 0.06)`).
- In Tailwind CSS 4 declare these as `--shadow-1` to `--shadow-3` in `@theme`, so `shadow-1` works and arbitrary `shadow-[...]` strings disappear from markup.

## Progressive blur

A blur that grows toward an edge, so content scrolling under a header or above a bottom bar softens gradually instead of meeting a hard line. CSS cannot vary a blur radius across one element, so stack bands: each layer blurs twice as much as the one before and is masked to an overlapping band.

```html
<div class="pblur" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
```

```css
.pblur { position: fixed; inset: 0 0 auto; height: 96px; pointer-events: none; z-index: 20; }
.pblur > i { position: absolute; inset: 0;
  --s: calc(var(--k) * 100% / 6);                 /* band start */
  backdrop-filter: blur(calc(0.5px * pow(2, var(--k))));
  mask: linear-gradient(to top, transparent var(--s), #000 calc(var(--s) + 16%), #000 calc(var(--s) + 33%), transparent calc(var(--s) + 50%)); }
.pblur > i:nth-child(1) { --k: 0 } .pblur > i:nth-child(2) { --k: 1 } .pblur > i:nth-child(3) { --k: 2 }
.pblur > i:nth-child(4) { --k: 3 } .pblur > i:nth-child(5) { --k: 4 } .pblur > i:nth-child(6) { --k: 5 }
```

- Six bands from 0.5px to 16px look continuous at 60-120px tall. Taller areas need seven or eight bands; the last band should extend to the edge (no fade-out at its end). If `pow()` is unavailable in your targets, write the radii out (0.5, 1, 2, 4, 8, 16px).
- `backdrop-filter` blurs only what is painted behind the element, and its cost grows with area and radius ([translucent-materials.md](translucent-materials.md)). Keep it to strips, never full panels, and drop to two or three bands on low-end devices.
- Blur alone does not make text on top legible. Pair it with a tinted gradient scrim and measure contrast at the worst scroll position (`scripts/glass_contrast.py`).
- Fallback where `backdrop-filter` is missing: the gradient scrim alone.

## Spotlight reveal on hover

Two pixel-aligned images stacked; the upper one (color, X-ray, finished material) shows only inside a feathered circle that follows the pointer.

```css
.spot { position: relative; overflow: clip; --x: 50%; --y: 50%; --r: 0px; }
.spot img { display: block; width: 100%; height: 100%; object-fit: cover; }
.spot .alt { position: absolute; inset: 0; pointer-events: none;
  mask: radial-gradient(circle var(--r) at var(--x) var(--y), #000 45%, rgb(0 0 0 / 0.5) 70%, transparent); }
@media (hover: none) { .spot .alt { display: none; } }
```

- Write `--x`, `--y` (in px relative to the element, from `getBoundingClientRect()`) and `--r` from one rAF loop that eases toward the pointer (factor 0.12-0.2 per frame) and stops when settled (`MOT-05`, `MOT-18`). Radius about 22% of the element width, clamped to 140-260px; ease it to 0 on `pointerleave` and window `blur`.
- Initialize the circle at the pointer on entry so it does not sweep in from the center; re-measure on scroll while hovered.
- Both images share dimensions, crop, `object-fit` and focal point; a one-pixel offset is obvious inside the circle.
- The alternate image is `alt=""` and `aria-hidden` when it shows the same subject. If it carries real information (before and after), add a visible toggle button for touch and keyboard users.
- Reduced motion: update the circle position directly, without trailing.

## Gooey merging shapes

Shapes that fuse when close and pull apart into droplets: blur them together, then cut the blurred alpha at a threshold so soft overlaps become one hard-edged mass.

```html
<svg width="0" height="0" aria-hidden="true" focusable="false"><filter id="goo" x="-20%" y="-20%" width="140%" height="140%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="soft"/>
  <feColorMatrix in="soft" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9" result="hard"/>
  <feComposite in="SourceGraphic" in2="hard" operator="atop"/>
</filter></svg>
<div class="blobs" style="filter: url(#goo)">...</div>
```

- The last matrix row multiplies alpha by 20 and subtracts 9: pixels above about 45% alpha become solid, the rest vanish. Raise the multiplier for crisper edges; the blur radius sets how far apart shapes start to bridge (roughly the blur radius times two).
- The final composite keeps the original children sharp inside the merged mass; drop it if the blobs carry no text or icons. Never put readable text through the filter.
- The whole filter region is re-filtered every frame its children move (`STY-12`): keep the region tight, the element small (a loader, a toggle, a menu that splits into items, a hero accent) and the blob count low (three to eight).
- Motion: slow drift on transforms, 4-10s loops with offset phases; loaders may move faster. Reduced motion shows one still composition.
- Plain CSS alternative on a solid background: `filter: blur(12px) contrast(20)` on the parent with a matching background color; it cannot be transparent.

## Chamfered corners

Diagonal cuts read as engineered and technical; use one cut size per component size and repeat it as a system.

```css
.cut { --c: 12px;
  clip-path: polygon(var(--c) 0, 100% 0, 100% calc(100% - var(--c)), calc(100% - var(--c)) 100%, 0 100%, 0 var(--c)); }
@supports (corner-shape: bevel) {
  .cut { clip-path: none; border-radius: var(--c) 0; corner-shape: bevel; }   /* border, shadow and outline follow the shape */
}
```

- Sizes: 6-10px on controls, 12-18px on cards, 20-32px on large panels. Pair opposite corners (top-left with bottom-right).
- `clip-path` also clips borders, shadows and focus outlines. For a bordered shell, clip an outer element painted in the border color and an inner element inset by 1px with the same polygon; draw focus with `outline` on an unclipped wrapper or a `drop-shadow()` filter on the parent. `corner-shape` (Chromium 139+) avoids all of this; treat it as enhancement.
- Keep at least 44px control height and enough horizontal padding that text never sits under the cut.
- Do not mix chamfers and fully rounded pills at the same hierarchy level.

## Visible structure: guide lines, frames and brackets

For editorial, technical and developer-facing pages where the grid is part of the look. Lines must sit on real container and section edges; drawn lines that do not match the actual layout are a generic tell.

```css
:root { --max: 1200px; --gutter: clamp(16px, 4vw, 40px); --rule: color-mix(in oklab, currentColor 14%, transparent); }
.shell { position: relative; }
.shell::before { content: ""; position: absolute; inset: 0 max(var(--gutter), (100% - var(--max)) / 2);
  border-inline: 1px solid var(--rule); pointer-events: none; }
.wrap { width: min(100% - 2 * var(--gutter), var(--max)); margin-inline: auto; }   /* content uses the same numbers */

.cells { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1px; background: var(--rule); border: 1px solid var(--rule); }
.cells > * { background: var(--surface-0); padding: clamp(16px, 2.5vw, 32px); }   /* the gaps become hairlines */
```

- **Guide lines:** two vertical 1px lines at the content edges, 10-16% ink, behind content, `pointer-events: none`. Same width rules for every section.
- **Corner ticks:** 5-7px squares or plus marks centered on section corners (`translate: -50% -50%`), drawn by pseudo-elements on the section, slightly stronger than the lines.
- **L-brackets:** eight 1px background gradients (`linear-gradient(var(--tick) 0 0) top left / 16px 1px no-repeat`, and so on) mark corners without extra markup.
- **Hairline cell grids:** the gap-as-line pattern above keeps every divider exactly 1px and aligned, even when cells wrap.
- **Nested frames:** an outer frame sets global bounds; inner blocks sit inset by one spacing step with their own fill and a radius smaller than the outer one (inner radius = outer radius minus inset). Two levels at most; a third becomes boxes inside boxes.
- **Texture:** a diagonal hatch (`repeating-linear-gradient(135deg, transparent 0 10px, var(--hatch) 10px 11px)`) at 3-5% ink, only on empty cells, never behind body text.
- One line color, one bracket size, one gap across the page. On phones keep the outer lines but collapse to one column; lines must never crowd text closer than the gutter.

## Number details

Numerals carry rhythm and precision; small typographic decisions show care.

- **Step markers (01, 02, 03):** only when the order is real (process steps, a ranked list, chapters). Use an ordered list and CSS counters so the numbers cannot drift from the content: `ol { counter-reset: step } li::before { counter-increment: step; content: counter(step, decimal-leading-zero); }`. The marker is secondary: small size, tabular figures, muted color that still reaches 3:1, consistent position (top-left of the card, in the gutter, or on the rail). A numbered section heading on a page whose sections have no order is a generic tell.
- **Tabular figures** (`font-variant-numeric: tabular-nums`) for anything that updates or aligns: prices, timers, counters, table columns (`MOT-14`). Proportional figures in prose.
- **Slashed zero** (`font-feature-settings: "zero"`) for codes, IDs and serials where O and 0 are confusable, if the face supports it.
- **Fractions and units:** `font-variant-numeric: diagonal-fractions` for recipes and measurements; a no-break space between number and unit (`12&nbsp;kg`); units smaller or lighter than the figure in large display numbers, never baseline-misaligned.
- **Large stat numerals:** set with tighter tracking (-0.02em to -0.04em) and lining figures; format with `Intl.NumberFormat` for locale separators.
- **Old-style figures** (`oldstyle-nums`) suit running text in editorial faces; never in tables.

## Ordered-dither backgrounds

A monochrome field of large square pixels thresholded by a Bayer matrix: technical, archival, slightly retro. Fits only when that texture is the brand (generic tell 15 otherwise). Render a tiny canvas, one pixel per cell, and let CSS scale it up with crisp edges; this costs a few thousand pixel writes per frame instead of one draw call per cell.

```js
// n x n Bayer thresholds in (0, 1), built recursively: M(2n) = [4M, 4M+2; 4M+3, 4M+1]
function bayer(n) {
  let m = [[0]];
  while (m.length < n) m = [...m.map((r) => [...r.map((v) => 4 * v), ...r.map((v) => 4 * v + 2)]),
                            ...m.map((r) => [...r.map((v) => 4 * v + 3), ...r.map((v) => 4 * v + 1)])];
  return m.map((r) => r.map((v) => (v + 0.5) / (n * n)));
}
export function dither(canvas, field, { cell = 6, levels = [8, 24, 52, 120, 230] } = {}) {
  const w = Math.ceil(innerWidth / cell), h = Math.ceil(innerHeight / cell), t = bayer(4);
  canvas.width = w; canvas.height = h;               /* CSS: width 100%; height 100%; image-rendering: pixelated */
  const ctx = canvas.getContext("2d"), img = ctx.createImageData(w, h);
  return (time) => {
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const v = field(x / w, y / h, time) + (t[y & 3][x & 3] - 0.5) * 0.22;     // field returns 0..1
      const g = levels[Math.max(0, Math.min(levels.length - 1, Math.floor(v * levels.length)))];
      const i = (y * w + x) * 4; img.data[i] = img.data[i + 1] = img.data[i + 2] = g; img.data[i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
  };
}
```

- The field function shapes the composition: broad soft masses from layered sine waves or value noise, a vignette so edges fall to near-black, one brighter mass off-center. Avoid random per-frame noise; it flickers.
- Cell size 5-10 CSS px keeps the matrix visible. Palette: four to six grays from near-black; the brightest level appears rarely.
- Animate slowly (a drift of a few percent of the field per second), redraw at most 30 times per second, pause when hidden (`MOT-05`), and render one still frame under reduced motion. A shader version for full-screen animated fields is in [webgl-backgrounds-and-3d.md](../../creative-media/references/webgl-backgrounds-and-3d.md).
- Text over the field sits on a calm zone or a solid panel; measure contrast against the brightest cell that can appear behind it.

## Tailwind CSS notes

- Tokens first: in Tailwind 4, colors, radii, shadows, durations and easings live in `@theme` as CSS variables, so `bg-surface-1`, `shadow-2` and `ease-out-soft` replace arbitrary values. Arbitrary values (`p-[13px]`) are a migration smell ([design-system-construction.md](design-system-construction.md)).
- Techniques that need several declarations (gradient border, progressive blur bands, chamfer) become `@utility` definitions or component classes, not 300-character arbitrary-property strings in markup.
- Class names must appear whole in source. Map variants to complete strings (`{ success: "bg-success-9", danger: "bg-danger-9" }`), never concatenate `"bg-" + tone`. Use a variant helper such as `cva` for components with several axes.
- `motion-safe:` and `motion-reduce:` variants express `MOT-04` directly; put start states behind `motion-safe:`.
- Order stays deterministic only within Tailwind's layers; put overrides in a later layer rather than relying on class order in the attribute.

## Pitfalls

- A gradient border, glow or layered shadow on every card, so nothing stands out (`CMP-07`).
- Masks and clip paths that cut off focus rings or make edge items unreachable.
- Progressive blur over large panels or video, or used as the only legibility fix.
- Gooey filters on big regions or around text; dither and hatch textures behind body copy.
- Guide lines and brackets that do not land on the real container edges, or a different gutter per section.
- Decorative "01 / 02" numbering on unordered sections.

## Done when

- [ ] Each technique appears where it means something (a selected state, a floating layer, a real edge), not on every element.
- [ ] Focus outlines remain visible and complete on masked, clipped and chamfered elements; touch targets keep 44px.
- [ ] Text contrast is measured over the worst backdrop for blurred, dithered and textured areas.
- [ ] Animated variants (rotating border, drifting blobs, dither) pause off-screen and are static under reduced motion.
- [ ] Lines, frames and markers align to the actual container at 390, 768 and 1440px.
- [ ] Values are tokens (Tailwind `@theme` or custom properties), with no stray arbitrary values in markup.
