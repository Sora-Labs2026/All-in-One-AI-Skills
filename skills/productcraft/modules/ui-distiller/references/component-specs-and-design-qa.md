# UI Distiller: Component specifications, design QA and design review

Read this when specifying a component before or alongside code, generating a component for a particular framework, setting up the gates that stop design regressions, or reviewing a screen with a structured, scored critique. Token architecture is [design-system-construction.md](design-system-construction.md) and [design-system-operations.md](design-system-operations.md); the accessibility audit itself is `../../engineering-practices/references/accessibility-audit.md`; the component rules are `CMP-01` to `CMP-04` in `../../../references/ui-rules/components.md`.

## 1. The component specification

One page per component, in this order:

1. **Purpose and when not to use it** (a menu is not a navigation bar; a toast is not an error that blocks).
2. **Anatomy:** named parts (container, label, leading icon, trailing icon, helper text, counter), with which are optional.
3. **Variants:** a closed list with the intent of each (primary, secondary, quiet, destructive). One primary per view.
4. **Sizes:** each with height, horizontal padding, gap, font size and icon size, all as tokens; the smallest touch size at least 44 × 44 pt (iOS) or 48 × 48 dp (Android), and never under 24 × 24 CSS px on the web (WCAG 2.5.8).
5. **States** (table below), with the visual change and the semantic attribute for each.
6. **Token map:** every visual property to a semantic or component token, per variant and state.
7. **Accessibility:** role, accessible name source, keyboard model (from the WAI-ARIA Authoring Practices pattern), focus behavior, announcements.
8. **Content rules:** label length, truncation, wrapping, icon-only allowed or not.
9. **Responsive behavior and right-to-left mirroring.**
10. **Code reference** and the design-file component it maps to.

### States

| State | Trigger | Code | Typical visual change |
|---|---|---|---|
| Default | none | | base tokens |
| Hover | pointer over (only under `@media (hover: hover)`) | `:hover` | one step darker or lighter fill |
| Focus visible | keyboard focus | `:focus-visible` | 2 px ring, 2 px offset, 3:1 against adjacent colors |
| Pressed | pointer or key down | `:active`, `aria-pressed` for toggles | one more step, optional 0.97-0.98 scale |
| Disabled | not available | `disabled` or `aria-disabled="true"` | muted tokens; exempt from contrast but still legible; say why nearby when it matters |
| Loading | async work | `aria-busy="true"`, keeps its width | spinner or progress replaces or joins the label |
| Invalid | failed validation | `aria-invalid="true"` plus `aria-describedby` to the message | danger border and message, never color alone |
| Selected or current | chosen item | `aria-selected`, `aria-current`, `aria-checked` | fill or indicator plus a non-color cue |

When several apply, the higher row in this order wins: disabled, loading, invalid, pressed, focus visible, hover, selected styling layered on top. Write the precedence into the spec so designers and code agree.

## 2. Generating the component for a stack

Whatever the framework, the generated component must:

- read every value from the shared theme (CSS variables, a theme object, platform resources), with zero raw colors, sizes, durations or font names, and no raw palette utilities such as `bg-gray-500` when semantic utilities exist;
- render the native element (`<button>`, `<a>`, `<input>`; `Button` in SwiftUI; `Button` in Compose) or a tested headless primitive for complex widgets;
- implement every applicable state from the table and dark mode through the semantic tier;
- honor reduced motion and dynamic type or font scaling;
- be one shared component per control, reused everywhere: overlays share one dialog primitive with focus trap, `role="dialog"`, `aria-modal`, a labelled title, Escape to close and focus returned to the trigger;
- be delivered whole: complete files, no elided sections (`../../engineering-workflow/references/complete-deliverables.md`).

Stack notes: React with Tailwind CSS maps variants through a variant helper and semantic utilities generated from `@theme`; SwiftUI reads colors from asset-catalog colors with appearances and uses `ButtonStyle` for variants; Jetpack Compose reads a theme object or a custom `CompositionLocal` populated from generated tokens; Flutter reads a `ThemeData` extension built from the token output; web components expose parts and custom properties for theming.

Semantic intent must match the action: destructive actions use the danger role in the trigger and in the confirmation; secondary is a neutral outline or quiet style, not a second colored fill; the same action uses the same variant everywhere.

## 3. A states harness, rendered and looked at

Build one page per component that shows every variant × size × state, in light and dark, including long labels and right-to-left. Drive states with attributes (`data-state="hover"` mirrored to the hover styles, real `disabled`, `aria-invalid`, `aria-busy`), so a screenshot can show them all at once.

Automated contrast and accessibility checks prove names, roles and ratios; they do not prove the component looks or works right. Screenshot the harness and inspect it:

```js
// harness-shot.mjs
import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 3 });
await page.goto(process.argv[2]);
await page.addStyleTag({ content: "*,*::before,*::after{transition:none!important;animation:none!important}" });
await page.mouse.move(5, 5);                                   // park the pointer away from controls
for (const theme of ["light", "dark"]) {
  await page.evaluate((t) => document.documentElement.dataset.theme = t, theme);
  await page.locator("main").screenshot({ path: `out/harness-${theme}.png` });
}
const box = page.getByRole("checkbox", { name: "Email me" });   // functional check, not just pixels
await box.click(); if (!(await box.isChecked())) throw new Error("checkbox does not toggle");
await browser.close();
```

Look for: controls that do not respond (a decorative overlay above the real input without `pointer-events: none`), glyphs off-center in their box, check and indeterminate marks drawn with different methods and therefore different weights, focus rings clipped by `overflow: hidden`, labels that wrap or overflow in the narrow sizes, and the same component styled differently on two pages.

**Overflow check.** Load each harness at 280, 320 and 414 px wide and fail on horizontal scroll (`document.documentElement.scrollWidth > innerWidth`). The usual causes: fixed widths (use `width: 100%; max-width: N`), default list padding, non-wrapping rows (add `flex-wrap: wrap` or a scroll container for tabs), and grid minimums wider than the screen (`minmax(min(16rem, 100%), 1fr)`; prefer `auto-fit` over `auto-fill` so cards stretch).

**Animating open and closed.** Disclosure components animate their height, not only an icon. Without measuring in script:

```css
.panel { display: grid; grid-template-rows: 0fr; transition: grid-template-rows var(--duration-normal) var(--ease-out); }
.panel[data-open="true"] { grid-template-rows: 1fr; }
.panel > .inner { overflow: hidden; min-height: 0; }
@media (prefers-reduced-motion: reduce) { .panel { transition: none; } }
```

Keep `hidden` or `inert` on collapsed content so it leaves the tab order, removing it before opening and adding it after the closing transition ends.

## 4. The design QA gates

Build the gates from fast and cheap to slow and human:

| Layer | Runs on | Blocks merge when |
|---|---|---|
| Token validation | every commit | invalid JSON, unresolved alias, missing `$type`, naming violation |
| Contrast over token pairs | every commit | any approved text, control or focus pair below its threshold in any theme |
| Raw-value lint | every commit | a raw color, length, duration or font family in component code; `transition: all` (the inventory ratchet in [design-system-construction.md](design-system-construction.md) catches growth) |
| Automated accessibility | every pull request | any serious or critical axe violation on any harness state (open menus, error states, dialogs) |
| Rendered contrast | every pull request | computed text color against its composited background below threshold on the rendered page, including hover and focus |
| Visual regression | every pull request | an unapproved screenshot difference |
| Manual accessibility | each release | the signed checklist is incomplete |

**Visual regression matrix:** variants × sizes × states × light and dark × key widths (390, 768, 1280) × right-to-left for components with direction. Freeze what moves: disable transitions and animations, fix the clock and random seeds, load fonts before capture, use deterministic data. Generate baselines in CI's environment, not on a laptop; font rendering differs.

**Manual release checklist:** complete key flows with keyboard only; one screen reader per platform; 400% zoom reflow at 320 CSS px; text spacing override (WCAG 1.4.12); reduced motion on; forced colors (Windows contrast themes) on; dark mode; the largest system text size on phones.

## 5. Structured design review

Use this when asked for a critique, a score or a heuristic evaluation of an existing screen or flow.

1. **Context first:** the screen's job, its users, platform, constraints and the stage (concept, built, live).
2. **Score six dimensions** from 1 to 5 with a sentence of evidence each, and weight them:

| Dimension | Weight | Evidence to cite |
|---|---|---|
| Hierarchy and clarity | 20% | First-glance answers to "where am I, what matters, what next" (GUIDE non-negotiable) |
| Consistency | 20% | Token use, repeated components, spacing rhythm ([taste.md](taste.md) measurements) |
| Accessibility | 20% | Contrast, focus, names, targets, motion (`../../engineering-practices/references/accessibility-audit.md`) |
| Usability | 20% | The heuristics below |
| Responsiveness | 10% | 390, 768 and 1440 px; long content; zoom |
| Performance | 10% | Layout shift, input delay, heavy media ([animation-runtime-audit.md](animation-runtime-audit.md)) |

   Report the weighted total with the per-dimension scores; the findings matter more than the number.
3. **Heuristic pass.** Check the ten classic usability heuristics and cite violations by number:
   1. The system shows its status promptly.
   2. Words and concepts come from the user's world, not the system's.
   3. Users can leave, undo and go back easily.
   4. Conventions are consistent within the product and with the platform.
   5. Errors are prevented before they happen.
   6. Options are visible; users recognize rather than remember.
   7. Experts get shortcuts without burdening novices.
   8. Only relevant information is shown; decoration does not compete.
   9. Error messages say what happened and how to fix it, in plain words.
   10. Help is findable and task-focused when needed.
4. **Generic-tell pass** with [generic-tells-and-fixes.md](generic-tells-and-fixes.md).
5. **Findings table,** ordered by severity:

| # | Severity | Where | Finding | Heuristic or criterion | Fix (token or component level) |
|---|---|---|---|---|---|
| 1 | Critical | Checkout, payment step | Error appears only as a red border | H9, WCAG 3.3.1 | Message linked with `aria-describedby`; focus moves to first invalid field |

Severity: critical (blocks a task or excludes users), major (slows or confuses most users), minor (friction with a workaround), enhancement (polish). Each fix names the token or component to change, so it is actionable.

## Done when

- [ ] Each component spec has purpose, anatomy, variants, sizes, the state table with attributes and precedence, token map, accessibility model and content rules.
- [ ] Generated code uses only theme values, native or tested primitives, every applicable state, and arrives as complete files.
- [ ] A states harness was screenshotted in both themes and inspected; interactive checks toggled real controls; no overflow at 280-414 px.
- [ ] Fast gates block on token, contrast, raw-value and axe failures; visual regression covers themes, widths and right-to-left with frozen motion; the manual checklist is signed per release.
- [ ] Reviews give weighted scores with evidence, heuristic citations, and a severity-ordered findings table with token-level fixes.
