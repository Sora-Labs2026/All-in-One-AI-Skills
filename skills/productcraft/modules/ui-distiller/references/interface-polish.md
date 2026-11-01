# UI Distiller: Polish pass

Read this when a screen works and has the right hierarchy but still feels unfinished: it jumps when states change, text wraps badly, controls feel dead or cramped, edges look soft. Each item says what to look for and the fix, with the rule it serves. It complements [taste.md](taste.md) (which removes generic defaults) and [quality-gate.md](quality-gate.md) (which checks integrity); run it after both. Rule IDs point to `../../../references/ui-rules/`. Browser support notes are as of 2025.

## How to run it

1. Open the screen at 390px and 1440px with real data, in light and dark, and use it: hover, press, tab through, type, resize, change states, scroll.
2. Run the source scan for the mechanical items: `python3 <productcraft>/modules/ui-distiller/scripts/token_inventory.py src/` flags `transition: all`, `will-change: all` and raw values (see [design-system-construction.md](design-system-construction.md)).
3. Paste the layout-shift observer below into the console while you exercise the screen.
4. Fix in the shared components and tokens, not per screen. Report only what changed.

```js
// Logs every layout shift not caused by recent input, with the elements that moved.
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) if (!e.hadRecentInput)
    console.log("shift", e.value.toFixed(4), e.sources?.map((s) => s.node));
}).observe({ type: "layout-shift", buffered: true });
```

## Stability: nothing jumps

- **Labels that change length.** "Save" becoming "Saving…" resizes the button and moves its neighbours. Fix the width to the longest label, or overlay the spinner and hide the label visually (`ENG-03`, `FBK-10`).
- **Changing numbers.** Counters, timers, prices and table columns use `font-variant-numeric: tabular-nums` (`TYP-09`, `MOT-14`).
- **Scrollbars appearing.** A panel that gains a scrollbar shifts its content sideways. Use `scrollbar-gutter: stable` on scroll containers whose content length varies.
- **Images and media.** Give every image `width` and `height` attributes or `aspect-ratio` so space is reserved before it loads.
- **Web fonts.** Fallback text reflows when the web font arrives. Preload the main face, and tune the fallback with `size-adjust` and `ascent-override` in an `@font-face` rule so both faces occupy the same space.
- **Hover that changes weight or size.** Bold-on-hover widens text and pushes neighbours. Change color or background instead, or reserve the bold width.
- **Late content above the fold.** Banners and notices inserted after load push content down; reserve their space or place them where they do not displace anything (`FBK-14`).

## Text

- **Headings:** `text-wrap: balance` evens out short multi-line titles (engines limit balancing to a few lines).
- **Paragraphs and captions:** `text-wrap: pretty` avoids a single word on the last line (Chromium and recent Safari; elsewhere it falls back harmlessly). Not on code or preformatted text.
- **Long unbroken strings** (URLs, IDs, file names, emails) break narrow layouts. Use `overflow-wrap: anywhere` in tight containers, and `min-width: 0` on flex and grid children so truncation can work at all.
- **Truncation** with `text-overflow: ellipsis` only where the full value is reachable (a tooltip, a detail view, the accessible name).
- **Typography details:** real quotes and apostrophes; an en dash for ranges (`9–17`); a non-breaking space between a number and its unit (`12 GB`); `hyphens: auto` with the right `lang` for narrow columns of prose; `font-variant-numeric: slashed-zero` where codes mix 0 and O.
- **Font smoothing:** `-webkit-font-smoothing: antialiased` only affects macOS and makes text lighter. It can help light text on dark grounds; it is not a general fix, and it does not replace checking weight and contrast (`TYP-03`).

## Alignment and shape

- **Optical centering.** Geometric centering is not visual centering for play triangles, arrows, chevrons and asymmetric icons. Fix the SVG's viewBox, or nudge by 1-2px (`LAY-01` allows optical nudges outside the scale).
- **Icon and label.** Use `display: inline-flex; align-items: center` with the icon sized to the line height, one gap token between icon and text, and slightly less padding on the icon side of a button than on the text side.
- **Nested corners** concentric (`CMP-06`); radius from the scale (`CMP-05`).
- **Image edges.** Light images melt into light grounds. Add a neutral inset hairline: `outline: 1px solid rgb(0 0 0 / 0.08); outline-offset: -1px`, with a white-alpha version in dark mode. Keep it neutral; a brand-tinted edge reads as a border.
- **Borders and shadows.** One separation method per level (`LAY-07`); in dark mode separate with lighter surfaces and hairlines, not shadows (`DRK-03`, `DRK-09`). Shadows for floating surfaces only (`CMP-07`).

## Interaction states

- **Focus:** style `:focus-visible`, not `:focus`, so mouse clicks do not leave rings while keyboard focus always shows one (`BTN-02`, including two-tone rings on colored and image surfaces; `DRK-06` in dark mode).
- **Hover only where hover exists:** wrap hover styles in `@media (hover: hover)` so touch devices do not keep a "stuck" hover after a tap.
- **Press feedback within about 100ms** (`FBK-01`): a slight scale such as `scale(0.97)` on an inner layer or a tone shift. Keep the hit box still and animate an inner element (`ENG-04`).
- **Disabled versus unavailable:** a natively `disabled` button cannot be focused or explain itself. When the user needs to learn why, use `aria-disabled="true"` with a visible reason and block the action in the handler.
- **Explicit transitions:** list the properties (`transition-property: background-color, transform`), never `all`; separate enter and exit durations (`MOT-02`); use CSS transitions for states because they retarget when the user reverses (see [motion-engineering.md](motion-engineering.md)).
- **Icon swaps** (copy to check, play to pause): crossfade with a small scale instead of an instant swap, and update the accessible name at the same moment.
- **Entry and exit of popovers and dialogs:** `@starting-style` gives newly shown elements an entry transition, and `transition-behavior: allow-discrete` lets `display` wait for the exit to finish (both in all major engines since 2024; transitioning `overlay` for top-layer elements is Chromium-only).

## Touch and scrolling

- **Hit areas** of at least 44px on touch, enlarged with padding or a pseudo-element (`MOB-01`, `MOB-10`), without overlapping neighbours:

```css
.icon-button { position: relative; }
.icon-button::before { content: ""; position: absolute; inset: -10px; }  /* 24px glyph -> 44px target */
```

- **Scroll chaining:** `overscroll-behavior: contain` on drawers, modals and chat panes so reaching their end does not scroll the page behind.
- **Anchors under a sticky header:** `scroll-margin-top` on headings (or `scroll-padding-top` on the scroller) equal to the header height.
- **Overflow hints:** horizontally scrolling rows show that more exists (a partly visible item, an edge fade or arrows), not a clean cut at a column boundary.
- **Smooth scrolling** only inside `@media (prefers-reduced-motion: no-preference)`.
- **Tap highlight:** remove `-webkit-tap-highlight-color` only when the control has its own pressed state.
- **Selection:** `user-select: none` on control labels such as tabs and segmented buttons, never on content people may copy.

## Forms

- `autocomplete` tokens, `inputmode` and `enterkeyhint` on every field where they apply (`FRM`); `accent-color` to theme native checkboxes, radios and range inputs.
- On iOS, inputs with a font size under 16px zoom the page on focus; keep inputs at 16px or more (`TYP-04`).
- Placeholder text is a hint, never the label (`FRM-01`), and still needs readable contrast where it carries an example.

## Theme details

- `color-scheme: light dark` (or the single scheme you support) so scrollbars, form controls and the canvas match the theme; a `theme-color` meta per scheme (`ENG-12`).
- `::selection` colors with readable contrast in both themes.
- A z-index scale from tokens, and `isolation: isolate` on components that create their own stacking, so overlays do not fight.

## Report format

Report changes as rows; omit what you checked and left alone.

| Detail | Before | After | Where |
|---|---|---|---|
| Button label change | "Saving…" widened the button by 18px | Fixed width from longest label | `Button.tsx` |
| Scrollbar shift | Filter panel content jumped 15px | `scrollbar-gutter: stable` | `FilterPanel.css` |
| Transitions | `transition: all` in 7 components | Explicit properties, tokens | `tokens.css`, 7 files |

## Done when

- Exercising the main states logs no layout shifts outside user input.
- The source scan shows no `transition: all` or `will-change: all`, and no new raw values.
- Focus is visible on every control by keyboard and absent on mouse click; hover styles do not stick on touch.
- Text wraps cleanly at 390px and 1440px with the longest real content; numbers do not jitter.
- Every change is listed in the report with its location.
