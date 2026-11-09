# UI Distiller: Generic tells, fixes and screen makeovers

Read this when a screen "looks AI-made" and you need a fast, concrete pass:

- a scan list of the tells that make interfaces look generated;
- the fix for each;
- three worked makeovers: a sign-in screen, a one-time-code screen and an AI assistant chat;
- interface motion numbers.

It complements [taste.md](taste.md), which has the detectors and the self-critique pass, and [interface-polish.md](interface-polish.md), which covers stability, alignment and states. Run `scripts/tell_scan.py` on the source first: it finds the tells that can be measured in code.

A tell is not a law. Each item is a default people now read as "nobody decided this". Keep it when the product has a stated reason, and write the reason down.

## 1. Tells to scan for

| # | Tell | What it looks like | Fix |
|---|---|---|---|
| 1 | Decorative tags and pills | Badges such as "New", "AI-powered" or "v2", and rows of category pills that say nothing a heading doesn't | Delete them. Keep a badge only for a real, changing status |
| 2 | Redundant labels | A label repeating its heading, an icon plus a word plus a tooltip for the same thing | One carrier per meaning |
| 3 | Italics as decoration | A random word italicized in each headline | Use plain type, and emphasis only where speech would stress it |
| 4 | The fashionable display serif | The same high-contrast serif on every "premium" page | Choose type from the brand and the reading task ([style-catalog.md](style-catalog.md)) |
| 5 | Tight negative tracking everywhere | Body and UI text squeezed below 0 | Negative tracking only on large display sizes; 0 for body text |
| 6 | Too much detail | Dense dashboards, micro-labels and decorative charts in a hero | Show the one thing the screen is for, and cut the rest |
| 7 | Dividers everywhere | Rules between every row and section | Group with spacing first; keep a rule only where spacing can't separate |
| 8 | Many tints and opacities of one hue | Ten near-identical purples, text at 60%, 50% and 40% opacity | A small token set: two or three text levels and one accent ([token_inventory.py](../scripts/token_inventory.py) finds near-duplicates) |
| 9 | Every block in a bordered card | Boxes inside boxes | Cards only for things that move or repeat as units; otherwise use whitespace |
| 10 | Over-detailed diagrams | Architecture art with 20 boxes in a marketing section | Three to five labelled parts, or a real screenshot |
| 11 | Verbose, redundant copy | Three sentences that say "fast, simple, powerful" | Cut by half; make it specific ("Imports 10,000 rows in under a minute") |
| 12 | Code-style breadcrumbs | `// data products`, `<section>` and other fake-code eyebrows | A plain heading |
| 13 | Numbered sections | "01 / Features", "02 / Pricing" on a page that isn't a sequence | Number only real steps |
| 14 | Eyebrow above every heading | A small all-caps kicker on each section | At most one on a page, where it adds context |
| 15 | Dithering, scanlines and ASCII art | Retro texture as decoration | Use it only when it is the brand; otherwise real imagery |
| 16 | Squircles and pill buttons on everything | One radius language copied from a phone OS | One radius scale; nested radii concentric (inner = outer − padding) |
| 17 | Monospace everywhere | Mono for headings, labels and prose | Mono only for code, data, IDs and aligned figures |
| 18 | All-caps subtitles | Shouted secondary text | Sentence case; reserve caps for short labels, with added tracking |
| 19 | Gradient backgrounds | Purple-to-blue or orange-to-pink fields and glows | A solid surface plus one accent color; a gradient only with a reason (light, depth, a brand asset) |
| 20 | Periods in headlines | "Built for teams." on every heading | Headlines without terminal periods unless the voice is deliberately sentence-like across the whole product |

## 2. Fixes that lift any screen

1. **Show the actual product.** Use a real screenshot or a live demo instead of abstract art.
2. **Enlarge the main feature.** Give the one thing the page sells most of the space.
3. **Make headlines specific.** Write what it does, for whom and with what result, not a mood.
4. **Emphasize one call to action.** Make one primary button per view; the others become secondary or links.
5. **Use a design system.** Tokens for color, type, spacing, radius and motion, applied everywhere ([design-system-construction.md](design-system-construction.md)).
6. **Add one accent color.** Use it for the primary action and the active state, and keep the rest neutral.
7. **Keep icons consistent.** Use one icon family, one stroke weight and one size grid.
8. **Remove embellishments.** Drop glows, blobs, noise, floating particles and decorative shadows.
9. **Raise text contrast.** At least 4.5:1 for body text and 3:1 for large text and UI parts, measured (`COL-01`).
10. **Wrap headlines properly.** Use `text-wrap: balance` for headings and `pretty` for paragraphs. Never leave an orphan word; set a max width in `ch`.
11. **Align by eye, not by pixels.** Nudge play icons, arrows and round glyphs for optical centering.
12. **Use tabular numerals.** `font-variant-numeric: tabular-nums` for prices, tables, timers and counters, so digits don't jump.
13. **Add loading states.** Use a skeleton with the final layout's shape instead of an empty table or a spinner over nothing.
14. **Animate useful feedback.** Animate state changes the user caused ("Added", "Saved", "Copied"), not decoration.
15. **Use mono only where needed:** code, keys, IDs and numbers that must align.

## 3. Screen makeovers

### Sign-in screen

| Step | Change |
|---|---|
| Strip | Remove the gradient wash, the emoji in "Welcome back!" and stacked social buttons above the form |
| One action | One dark primary "Log in" button. Social providers become small secondary icons under "Or log in with" |
| Hierarchy | Logo, title, fields, primary button, then secondary options, in that order of weight |
| Place | A background that says what the product is about (for a travel app, a calm sky), kept low-contrast behind a solid card |
| Concentric corners | Inner radius = outer radius − padding (for example card 32, padding 8, field 24) |
| Elevation | One soft shadow on the card instead of borders everywhere |
| A brand detail | One small, specific mark (a physical-world motif that belongs to the product). Skip the generic lock icon |
| Microinteraction | The field gets focus and the label moves cleanly; the password toggle shows state |
| Continuity | On success, the card's mark expands into the next screen (a shared element transition), not a hard cut |
| End on a reward | The first screen after sign-in shows something valuable right away. People judge an experience largely by its peak and its end (the peak-end rule) |

### One-time-code screen

| Step | Change |
|---|---|
| Strip | Drop the purple gradient, the big "Verify" button and a heavy border on every box |
| Grouping | Six digits as two groups of three (`482-913`) to ease reading |
| Input | One real input with `autocomplete="one-time-code"`, `inputmode="numeric"` and paste support. Visual boxes can be drawn over it, but never six separate inputs that break paste and screen readers |
| Auto-submit | Submit when the last digit lands; show an inline "Checking…" state, not a separate button |
| Trust | Show where the code went (a masked number), when it expires and a resend option with a cooldown |
| Wrong code | Mark the digits in the error color, say "Wrong code" in text, keep focus and let the user retype. Rate limits and lockout follow [../../credential-shield/GUIDE.md](../../credential-shield/GUIDE.md) |
| Success | A short check-mark draw and "Verified", then continue; no confetti |
| Accessibility | One labelled field, errors announced (`aria-live`), and no reliance on color alone |

### AI assistant chat

| Step | Change |
|---|---|
| Strip | No "AI Assistant" purple header, robot avatar, sparkle icons or "Powered by AI" footer |
| Open with the task | A plain question ("What are we training for?") and a few suggested prompts as text links, not boxed chips |
| Show the work | List the steps the assistant takes with their duration ("Read your last 24 runs · 1.2 s", "Checking calendar"). Visible effort raises perceived value (the labor illusion), but show only steps that really ran |
| Origin-aware references | Citation markers open a popover that grows from the marker and shows the source data |
| No layout shift | Reserve space as text streams; never let the composer or earlier messages jump |
| Linked views | Hovering a phrase highlights the matching part of a chart, and the reverse (brushing and linking) |
| Human in the loop | Before an action with effects ("Add 36 runs to your calendar?"), ask with a clear primary and "Not now". After it, offer Undo |
| Texture with care | Film grain or warm color only if it suits the brand, and never under text without a contrast check |

## 4. Interface motion numbers

These are defaults for product UI, not rendered video (for video see [../../creative-media/references/directed-motion.md](../../creative-media/references/directed-motion.md)). They sit with the motion rules (`MOT`) and [motion-engineering.md](motion-engineering.md).

| # | Rule | Value |
|---|---|---|
| 1 | Entrances ease out | `cubic-bezier(0.22, 1, 0.36, 1)` or similar; never ease-in for an entrance |
| 2 | Dropdowns and menus | 150-250 ms |
| 3 | Stagger list rows | About 30 ms per row, first few rows only |
| 4 | Press feedback | Scale to 0.97 over about 150 ms |
| 5 | Moving knobs and thumbs | Stretch about 12% along the direction of travel, preserving area |
| 6 | Details settle after their container | Secondary parts trail by about 50 ms |
| 7 | Objects travel on arcs | A slight curve (for example a 32 px arc) rather than a straight line for longer moves |
| 8 | Confirm success | One short pulse with the success label, not a loop |
| 9 | Moves on screen | Ease-in-out |
| 10 | Popovers and menus start near full size | From scale 0.95, never 0 |
| 11 | Enter from the trigger | `transform-origin` at the trigger's side (for example top right under a button at top right) |
| 12 | Exit toward the trigger | The closing element shrinks back to where it came from |
| 13 | No bounce on everyday UI | Critically damped springs for menus, sheets and toggles; bounce only for playful moments |
| 14 | Don't tween while held | During a drag the element tracks the pointer directly; animate only on release |
| 15 | Exits are shorter | About 20-35% shorter than entrances in UI (for example 250 ms in, 200 ms out; `MOT-02` uses about two-thirds) |
| 16 | Overlap old and new states | Cross the exit and the entrance; no blank beat between them |
| 17 | Masks for reveals and color changes | Clip or mask text and fills instead of cross-fading them, which looks muddy |
| 18 | Swap icons with scale, opacity and blur | For example scale 0.8 to 1, opacity 0 to 1, blur 4 px to 0, over about 150 ms |
| 19 | Rubber band past bounds | Diminishing resistance beyond the limit, then spring back |
| 20 | Keep identity through change | An element that grows into a detail view is the same object (a shared element: a View Transition name or a layout ID), not a replacement |

Respect `prefers-reduced-motion`: keep opacity and color changes, and drop movement, scale and parallax ([motion-engineering.md](motion-engineering.md), "Reduced motion, completely").

## Done when

- [ ] `tell_scan.py` is clean, or every remaining finding has a written reason.
- [ ] The screen has one primary action and one accent color, a real product image or demo, and specific copy.
- [ ] Contrast, radii, numerals and headline wrapping were checked in the rendered page at phone and desktop widths.
- [ ] Motion follows the table above, and reduced motion was tested.
- [ ] The taste self-critique pass in [taste.md](taste.md) was run on the result.
