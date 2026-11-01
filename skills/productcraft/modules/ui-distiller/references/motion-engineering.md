# UI Distiller: Motion engineering

Read this when a change needs more than one transition: choosing the animation tool, motion tokens, springs, choreography of several elements, shared-element transitions with the View Transitions API or FLIP, a React animation library, drag gestures, checking performance and building a complete reduced-motion path. The values and the when-to-animate rules are the `MOT` rules in `../../../references/ui-rules/motion.md` (durations `MOT-02`, easing `MOT-03`, reduced motion `MOT-04`, morphs `MOT-07`, FLIP `MOT-08`, springs `MOT-12`). This file is the implementation practice; it does not repeat those values. Browser support is stated as of late 2025; check current support before relying on a feature without a fallback.

## First, should it move?

Animate only to explain a change (what appeared, where it went, what caused it) or to answer an action. If you cannot name which of the two a motion does, remove it (`MOT-17`, taste detector 34 in [taste.md](taste.md)). Everything below assumes the motion has passed this test.

## Choose the tool

| Need | Use | Why not the alternatives |
|---|---|---|
| Hover, focus, pressed, open and closed states | CSS `transition` | Transitions retarget from the current value when the user reverses midway; keyframes restart from their first frame |
| A one-off entrance or a looping indicator | CSS `@keyframes`, with `@starting-style` for entry transitions of newly displayed elements | Script is unnecessary |
| Sequences, cancellation, awaiting completion | Web Animations API: `element.animate()`, `.finished`, `.cancel()`, `getAnimations()` | Timers drift from the animation (`MOT-10`) |
| The same element in two layouts or two routes | View Transitions API, or FLIP by hand | Crossfading two copies leaves double images (`MOT-07`) |
| Progress tied to scrolling | CSS scroll-driven animations (`animation-timeline`) as enhancement (`MOT-16`) | Scroll listeners run on the main thread |
| React components that animate out when they unmount, layout animations, drag | A React animation library such as Motion (`motion/react`, formerly published as Framer Motion) | Unmount happens before CSS can play an exit |
| Long authored timelines (scroll stories, SVG choreography) | A timeline library | Check its license and bundle size first |
| Hundreds of moving marks, particles | Canvas or WebGL with one `requestAnimationFrame` loop (`MOT-05`) | Hundreds of DOM nodes per frame stutter |

Use the platform first. Add a library only when it removes real code (exit animations, layout projection, gesture physics), not for a fade.

## Tokens: one source for CSS and script

Name tokens by role, define them once, and read them everywhere (`MOT-03`, `CMP-02`).

```css
:root {
  --dur-press: 90ms;   --dur-state: 160ms;
  --dur-enter: 260ms;  --dur-exit: 170ms;   /* exits about two thirds of entrances (MOT-02) */
  --dur-morph: 320ms;
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);   /* arrivals and responses */
  --ease-in: cubic-bezier(0.55, 0, 1, 0.45);    /* departures */
  --ease-move: cubic-bezier(0.65, 0, 0.35, 1);  /* on-screen moves */
}
```

```js
// motion-tokens.js: read the same values in script, so CSS and JS cannot drift apart
const css = getComputedStyle(document.documentElement);
export const ms = (name) => parseFloat(css.getPropertyValue(name)) || 0;   // "260ms" -> 260
export const ease = (name) => css.getPropertyValue(name).trim();
// element.animate(frames, { duration: ms("--dur-enter"), easing: ease("--ease-out") })
```

If tokens are generated from a token file (see [design-system-construction.md](design-system-construction.md)), generate the CSS and the JS module from it instead of reading computed styles.

## Springs in practice

- **Prefer springs for things the user drives:** drag release, swipe, a panel the user can reverse quickly. A spring carries velocity into the new target; a fixed-duration tween restarts.
- **Think in damping ratio and settle time** rather than raw constants (`MOT-12` gives the formulas). Several libraries accept a perceptual form (a duration plus a bounce amount); prefer it, because designers can reason about it, and keep the chosen values as tokens.
- **For fixed start and end points in CSS,** sample the spring once and express it with `linear()`. This is not interruptible with velocity; use it for one-way moves.

```js
// Sample a unit-mass spring from 0 to 1 into a CSS linear() easing and the time it needs to settle.
export function springToLinear({ stiffness = 300, damping = 30, stops = 40 } = {}) {
  const dt = 1 / 240; let x = 0, v = 0, t = 0; const ys = [];
  while (t < 5) {
    v += (-stiffness * (x - 1) - damping * v) * dt;   // semi-implicit Euler: velocity first
    x += v * dt; t += dt; ys.push(x);
    if (Math.abs(1 - x) < 1e-3 && Math.abs(v) < 1e-3) break;
  }
  const step = Math.max(1, Math.round(ys.length / stops));
  const pts = ys.filter((_, i) => i % step === 0).map((y) => +y.toFixed(4));
  return { easing: `linear(0, ${pts.join(", ")}, 1)`, durationMs: Math.round(t * 1000) };
}
// springToLinear() -> damping ratio about 0.87, a barely visible overshoot, settles in about 0.35 s
```

Unit-test helpers like this one: the last stop is 1, the duration is finite, and the overshoot stays under the bound you chose.

## Choreography

When several elements move for one change, decide the order before writing code.

1. **One lead.** The element the user acted on, or the one that changes meaning, moves first. Related elements follow 30-60ms later; the backdrop fades alongside without its own beat.
2. **Order follows meaning:** reading order for lists, the direction of travel for navigation (`MOT-13`). Stagger only the first few items (`MOT-06`).
3. **Overlap, do not chain.** Start the next part when the previous is roughly two thirds done; the whole change stays inside the budget in `MOT-02`.
4. **Container before content on entry, together on exit** (`MOT-07`). Exits are shorter and use the departure easing.
5. **One moving focus at a time.** If two regions must change, let one move and the other fade.

Write the plan as a table and review it before coding:

| Element | Property | Start | Duration | Easing |
|---|---|---|---|---|
| Clicked row → detail panel | position and size (shared element) | 0ms | `--dur-morph` | `--ease-move` |
| Backdrop | opacity 0 → 1 | 0ms | `--dur-enter` | `--ease-out` |
| Panel body text | opacity 0 → 1 | 200ms | 150ms | `--ease-out` |
| Close (reverse) | all of the above together | 0ms | `--dur-exit` | `--ease-in` |

## Shared-element transitions with the View Transitions API

```js
function navigateWithTransition(update, { types = [] } = {}) {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!document.startViewTransition || reduce) { update(); return; }   // same end state, no motion
  try { return document.startViewTransition({ update, types }); }     // object form carries types
  catch { return document.startViewTransition(update); }              // older engines take only a callback
}
```

- **Support (late 2025):** same-document transitions in Chromium 111+, Safari 18+ and Firefox 144+; cross-document transitions for multi-page sites (`@view-transition { navigation: auto; }`) in Chromium 126+ and Safari 18.2+. `view-transition-class` and transition types are newer than the core API; feature-detect, and treat the transition as enhancement.
- **Name exactly one element per name** at the moment of capture (`MOT-07`). For lists, set `view-transition-name` on the clicked item just before starting and clear it when `transition.finished` settles. Use `view-transition-class` to style many named elements with one rule.
- **Direction with types:** pass `types: ["forward"]` or `["back"]` and style `html:active-view-transition-type(forward)::view-transition-old(main)` (no space before the pseudo-element) so back navigation mirrors forward (`MOT-13`).
- **Aspect ratio changes** stretch the snapshots by default. Set `height: 100%` and an `object-fit` on `::view-transition-old(x)` and `::view-transition-new(x)`, or morph a wrapper whose proportions stay constant, and crossfade text instead of scaling it.
- **React:** the DOM must be updated by the time the update callback returns (or its returned promise resolves), but React batches state updates; wrap them in `flushSync` inside the callback. Routers in several frameworks offer a built-in flag or hook for view transitions; use it rather than wrapping navigation by hand. React's own view-transition component was still experimental in 2025.
- **Keep it short.** During the transition the page shows snapshots; long transitions feel like input lag.

## FLIP by hand

Use FLIP when you need interruption mid-move or a fallback for engines without View Transitions. Read all positions, change the DOM, read again, then write animations: never interleave reads and writes in one loop.

```js
export function flip(elements, mutate, { duration = 280, easing = "cubic-bezier(0.22, 1, 0.36, 1)" } = {}) {
  const first = new Map(elements.map((el) => [el, el.getBoundingClientRect()])); // visual position, mid-flight included
  elements.forEach((el) => el.getAnimations().forEach((a) => a.cancel()));        // drop the old move
  mutate();                                                                        // the real layout change
  const last = new Map(elements.map((el) => [el, el.getBoundingClientRect()]));   // read everything first
  for (const el of elements) {                                                     // then write
    const a = first.get(el), b = last.get(el);
    const dx = a.left - b.left, dy = a.top - b.top;
    const sx = b.width ? a.width / b.width : 1, sy = b.height ? a.height / b.height : 1;
    if (!dx && !dy && sx === 1 && sy === 1) continue;
    el.animate([{ transformOrigin: "0 0", transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` },
                { transformOrigin: "0 0", transform: "none" }], { duration, easing });
  }
}
```

- Scaling a box distorts its children, text and corner radius. Counter-scale the children, animate only position for text, or reveal size with `clip-path: inset(... round r)` instead of scale (`MOT-15`).
- Measure an untransformed wrapper when the element itself is rotated or scaled (`MOT-08`).

## A React animation library: idioms that matter

Examples assume Motion 12 (2025), imported from `motion/react`. Older code imports the same library from `framer-motion`; do not mix both packages in one tree.

- **Exit animations need three things:** the element is a direct child of `<AnimatePresence>`, it has a stable unique `key`, and it declares `exit`. Missing any one fails silently.
- **Modes:** the default plays exit and entry together; `mode="wait"` finishes the exit before the entry (one view swapping for another; keep exits short, because the user waits for both); `mode="popLayout"` removes the exiting element from layout at once so siblings reflow (custom child components must forward their ref).
- **Content visible without script.** The server renders the `initial` style, so `initial={{ opacity: 0 }}` on above-the-fold content hides it until JavaScript runs. Use `initial={false}` on `AnimatePresence` or on elements present at load, and animate only later changes (`MOT-06`).
- **Layout animations:** `layout` animates size and position changes with transforms; `layoutId` links two components as one shared element. Give children `layout` or `layout="position"` to stop text stretching; corner radius and shadow are corrected only when set through the library's style props, not CSS classes. Wrap siblings that affect each other in `LayoutGroup`. Each layout element is measured on every render, so keep layout animation to small subtrees.
- **Reduced motion:** wrap the app in `<MotionConfig reducedMotion="user">`, which drops transform and layout animation when the system asks and keeps opacity and color.
- **Bundle size:** load features lazily (`LazyMotion` with the `m` component) on pages where motion is not the product.
- **Motion values** (`useMotionValue`, `useTransform`, `useSpring`) update outside React rendering; never mirror them into state on every frame.

## Drag and swipe

- **Decide on release from position and velocity together:** project where the element would come to rest (current offset plus velocity times a short decay factor) and snap to the nearest allowed state. Express thresholds relative to the element (a third of a sheet's height), not as fixed pixels.
- **Let the page still scroll:** `touch-action: pan-y` on a horizontally swipeable row, `pan-x` on a vertical one; capture the pointer (`setPointerCapture`) once the gesture is recognized.
- **A single-pointer alternative is required** for every drag (WCAG 2.2 SC 2.5.7): buttons, a menu or keyboard moves (`CMP-33`).
- **Test on a touch device,** not only with a mouse: thresholds, scroll conflicts and inertia differ.

## Performance: measure, do not assume

- Animate `transform` and `opacity` (`MOT-01`). Confirm in the browser rather than trusting the code: in Chromium DevTools record the Performance panel with CPU throttling (4x or 6x) and look for Layout, Recalculate Style and Paint inside animation frames; turn on Paint flashing and Layer borders in the Rendering drawer; check the Layers panel for layer count and memory. Firefox and Safari have equivalent profilers.
- In the field, observe long animation frames (`PerformanceObserver` with type `long-animation-frame`, Chromium 123+) and Interaction to Next Paint; motion that delays the next paint after input is a regression even if it looks smooth.
- Set `will-change` just before a heavy animation and remove it afterwards; every promoted layer costs memory, and on phones that cost is visible.
- Time-base everything: 120 Hz displays run twice as many frames as 60 Hz ones, so count milliseconds, never frames.
- Test on a real mid-range phone or a throttled CPU before calling motion smooth.

## Reduced motion, completely

| Keep | Replace | Remove |
|---|---|---|
| Opacity and color changes of about 200ms or less, focus rings, progress that reports state | Slides, zooms and morphs with a short crossfade or an instant swap; parallax with a still; auto-advance with manual controls; looping spinners with a static indicator and text (`MOT-04`) | Decorative loops, pointer-follow effects, scroll-jacking, celebratory bursts |

- **Opt in, do not undo:** put movement inside `@media (prefers-reduced-motion: no-preference)` so the default is calm, instead of undoing it later with `!important`.
- **Script:** read `matchMedia("(prefers-reduced-motion: reduce)")`, listen for its `change` event, and pass the value to the library and to view transitions.
- An in-app "reduce motion" setting may override the system default for users who want less motion only here; store it as in `ENG-10`.
- Reduced motion does not cover moving content that runs on its own; that still needs a pause control (`MOT-19`, WCAG 2.2.2).

## Test motion

- **End states:** emulate reduced motion in tests (`page.emulateMedia({ reducedMotion: "reduce" })` in Playwright) and assert that the state change still happens. Before asserting positions with motion on, await `Promise.all(el.getAnimations().map((a) => a.finished))`.
- **Screenshots:** pass `animations: "disabled"` to Playwright's screenshot assertion so finite animations jump to their end.
- **Interruption:** reverse every animated control midway (open, then close at once) and check that nothing jumps.
- **Frame check:** record the screen and step through frame by frame for double images, jumps at the end and layout shift after the motion settles.

## Done when

- Every animation has a stated purpose, uses tokens, and stays inside the `MOT-02` budget.
- Shared-element moves work with View Transitions or FLIP and fall back to an instant change where unsupported.
- A profile with CPU throttling shows no layout or paint work inside animation frames on the main flows.
- Reduced motion keeps every state change and drops the movement; tests cover it.
- Drag has a non-drag alternative; interruption has been tried on every animated control.
