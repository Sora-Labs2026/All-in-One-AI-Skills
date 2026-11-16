# UI Distiller: Ten precision details

Read this for a fast finishing pass on a screen that is already well structured: ten small CSS decisions that separate a careful interface from an almost-right one. Each has the symptom, the fix and a check. Deeper treatment lives in [css-craft-techniques.md](css-craft-techniques.md), [interface-polish.md](interface-polish.md) and [generic-tells-and-fixes.md](generic-tells-and-fixes.md). `scripts/tell_scan.py` flags two of these in code (`VIEWPORT-100VH`, `GREY-GRADIENT`).

## 1. Concentric corners

**Symptom:** a rounded element inside a rounded container looks pinched at the corners, because both use the same radius.
**Fix:** inner radius = outer radius − the gap between them.

```css
.card  { --r: 24px; --pad: 8px; border-radius: var(--r); padding: var(--pad); }
.card > .media { border-radius: calc(var(--r) - var(--pad)); }   /* 16px */
```

When the gap is as large as the outer radius, the inner corner goes square (0), which is correct.
**Check:** zoom to 400% on a corner; the two curves should run parallel.

## 2. Translucent borders

**Symptom:** a fixed grey border (`#e4e4e7`) looks fine on white but sits like a pasted outline on colored or image backgrounds.
**Fix:** draw borders with black or white at low alpha so they take on the surface beneath.

```css
.tile { border: 1px solid rgb(0 0 0 / 0.1); }
@media (prefers-color-scheme: dark) { .tile { border-color: rgb(255 255 255 / 0.12); } }
```

**Check:** place the component on each surface color in the product. Where a border marks an input or a control's edge, it still needs 3:1 contrast against its surroundings (WCAG 1.4.11).

## 3. Palettes built in OKLCH

**Symptom:** a palette made with one HSL lightness ("all 50%") looks uneven: yellow glows and blue looks dark, because HSL lightness does not track perceived brightness.
**Fix:** pick colors in OKLCH, where `L` is perceptual. Keep `L` and chroma steady across hues for a set that feels even; vary `L` in fixed steps for a tonal scale.

```css
:root {
  --red:    oklch(0.68 0.17 25);
  --yellow: oklch(0.68 0.14 95);
  --blue:   oklch(0.68 0.15 255);
}
```

Very high chroma can fall outside sRGB; browsers map it into gamut, so check the rendered color. Supported in all current major browsers since 2023.
**Check:** convert the swatches to greyscale; equal-`L` swatches should read as equally light. Measure text contrast on each.

## 4. Gradients that stay vivid

**Symptom:** a gradient between distant hues (blue to orange) goes muddy grey in the middle, because the default interpolation passes through desaturated colors.
**Fix:** interpolate in OKLCH (or OKLab):

```css
.banner { background: linear-gradient(90deg in oklch, #2563eb, #f59e0b); }
```

`in oklch` takes the shorter hue arc by default; add `longer hue` for a rainbow sweep. Keep a plain fallback first for older browsers.
**Check:** sample the midpoint color; it should have chroma, not sit near grey.

## 5. Icon strokes that match the type

**Symptom:** thin 1px line icons beside medium-weight text look faint and unfinished.
**Fix:** match the icon's visual stroke to the text's stem weight at the size used. For outline icons drawn on a 24-unit grid and shown at 16-20px, a `stroke-width` around 1.75-2 usually matches 14-16px text at weight 500. Use one icon family and one stroke value throughout.

```css
.nav svg { width: 18px; height: 18px; stroke-width: 1.9; }
```

**Check:** compare a zoomed screenshot of a letter's vertical stem and an icon line; they should be close in thickness.

## 6. Masked edges on scrolling rows

**Symptom:** a horizontal carousel cuts items off with a hard edge, which reads as a rendering bug.
**Fix:** fade the edges with a mask, so content dissolves and the row reads as scrollable.

```css
.rail {
  overflow-x: auto;
  mask-image: linear-gradient(to right, transparent, #000 32px, #000 calc(100% - 32px), transparent);
}
```

Remove the leading fade when the row is scrolled to the start (toggle a class from the scroll position).
**Check:** keyboard focus on a partly faded item must still be visible; scroll the focused item fully into view.

## 7. Blurred icon swaps

**Symptom:** swapping one icon for another (copy → check, play → pause) flickers when it is a hard cut or a plain cross-fade.
**Fix:** cross the two icons with opacity, a small scale change and a short blur, over about 150-200ms.

```css
.icon { transition: opacity 180ms ease-out, transform 180ms ease-out, filter 180ms ease-out; }
.icon[data-hidden] { opacity: 0; transform: scale(0.8); filter: blur(4px); }
@media (prefers-reduced-motion: reduce) { .icon { transition: opacity 120ms linear; } .icon[data-hidden] { transform: none; filter: none; } }
```

Announce the new state in text for assistive technology ("Copied"), not only in the icon.

## 8. Depth in dark mode

**Symptom:** shadows barely show on dark backgrounds, so menus and cards sit flat on the page.
**Fix:** express elevation with lightness. The higher the layer, the lighter its surface, with a hairline translucent border and a shadow as a secondary cue.

```css
:root[data-theme="dark"] {
  --surface-0: oklch(0.17 0.01 260);   /* page */
  --surface-1: oklch(0.21 0.01 260);   /* card */
  --surface-2: oklch(0.26 0.01 260);   /* menu, popover */
}
```

**Check:** each step should be visibly distinct side by side; text keeps 4.5:1 on every surface.

## 9. Full-height sections on phones

**Symptom:** `height: 100vh` hides the bottom of a hero behind the mobile browser's toolbar, or the layout jumps as the toolbar shows and hides.
**Fix:** use dynamic viewport units, with a fallback:

```css
.hero { min-height: 100vh; min-height: 100dvh; }
```

Use `dvh` when the element should track the toolbar, `svh` for a stable height that always fits (no jump), and `lvh` for the largest size. Prefer `min-height` to `height`, so content can grow.
**Check:** open the page in a real mobile browser, scroll so the toolbar collapses and expands, and confirm that nothing important hides or jumps.

## 10. Product photos on tinted backgrounds

**Symptom:** product shots with white backgrounds show as white boxes on a beige or colored card.
**Fix:** for photos on pure white backgrounds, `mix-blend-mode: multiply` lets white take on the surface color while the product stays put.

```css
.product img { mix-blend-mode: multiply; }
```

This darkens light parts of the product too, and does nothing useful on dark surfaces. The robust fix is transparent images (PNG, WebP or AVIF with alpha) or a consistent studio background. Never multiply photos of people or images where color accuracy matters.
**Check:** compare light-colored products before and after; if they turn dingy, use cut-out images instead.

## Done when

- [ ] Nested radii are concentric, and borders adapt to their surface without losing control contrast.
- [ ] Palettes and multi-hue gradients are set in OKLCH, and their contrast is measured.
- [ ] Icon strokes match the text weight, from one family.
- [ ] Scrolling rows fade at their edges, and focus stays visible.
- [ ] Icon swaps blend, with a reduced-motion path and a text announcement.
- [ ] Dark mode separates layers by lightness.
- [ ] Full-height sections use `dvh` or `svh` with a fallback, tested on a real phone.
- [ ] Product images sit on their surfaces without white boxes.
- [ ] `tell_scan.py` raises no unexplained `VIEWPORT-100VH` or `GREY-GRADIENT` findings.
