# UI Distiller: Delight details

Read this when a product already works and needs character: the small, specific moments that make an action feel answered, an object feel physical or a milestone feel earned. Patterns are grouped by family; each row says how to build it, where to start with numbers and the guard that keeps it honest. Easter eggs, hidden games, seasonal modes, playful 404 pages, year-in-review and campaign sites are in [playful-moments.md](playful-moments.md). Durations, easing and reduced-motion rules are the `MOT` rules in `../../../references/ui-rules/motion.md`, and the implementation practice (tokens, springs, View Transitions, FLIP, drag) is [motion-engineering.md](motion-engineering.md); this file builds on both and does not repeat them.

## Before adding delight

- **Earn the slot.** Delight sits last in the priorities in `../GUIDE.md`. A detail must confirm an action, show where something went, make a value easier to feel, or mark a moment that matters to the user. If it does none of these, it is decoration (taste detector 34 in [taste.md](taste.md)).
- **State first, show second** (`MOT-17`). Update the data, count, focus and live-region text at once; the animation runs alongside, can be interrupted and never gates the next input.
- **One signature moment per flow.** Everything else gets plain, fast feedback. Two competing flourishes cancel each other out.
- **Wear-out schedule.** Novelty fades and the tenth confetti burst annoys. Play the full version the first one to three times, then a short version (same shape, about a third of the duration, a quarter of the particles), and keep the count per user and per feature.
- **Honest by construction** ([`../../ethical-persuasion.md`](../../ethical-persuasion.md)). No delight that hides a price, a consent choice or a limitation; rewards follow real actions; no randomized reward loops, no celebration that pressures spending, no animation that makes Allow or Upgrade louder than the alternative.
- **A plain path for every gesture and sensor.** Swipes, holds, drags and tilts need a button or menu equivalent (`MOB-11`, WCAG 2.2 SC 2.5.1 and 2.5.7), and anything driven by device motion must also work from the interface and be possible to switch off (SC 2.5.4).
- **Reduced motion keeps the meaning.** Keep the state change plus an opacity or color cue of 200 ms or less; drop travel, particles, tilt, parallax and loops. Web: `prefers-reduced-motion`. iOS: `UIAccessibility.isReduceMotionEnabled` or SwiftUI `@Environment(\.accessibilityReduceMotion)`. Android: `ValueAnimator.areAnimatorsEnabled()` returns false when the animator duration scale is 0.
- **Light and contrast.** Sparkles, fireworks, glitter and flicker count as flashes: at most three per second (`MOT-21`). Measure text contrast on the busiest frame of an effect, not on the empty background.
- **Art and rights.** Mascots, doodles and illustrations that are generated follow [`../../creative-media/references/generation-prompting.md`](../../creative-media/references/generation-prompting.md); characters, teams, films and other tie-ins need a license.

| How often a person meets it | Budget | Examples |
|---|---|---|
| Many times a day (tabs, toggles, send, like) | 200 ms or less, overshoot 3% or less, never delays the result | Tab icon nudge, count roll |
| A few times a week (create, complete, file, connect) | 300-700 ms, one flourish, interruptible | Toss into a folder, completion ripple |
| Rare and earned (first project, perfect score, yearly) | Up to about 1.2 s per segment and 3 s in all, tap to skip | Fireworks on a perfect audit |

**Haptics.** Pair a haptic with the visual hit (within about 10 ms), one per user action, never during continuous scroll except at detents, and only through the system API so the user's haptics setting applies. Sound stays opt-in (`FBK-20`).

| Moment | iOS | Android | Web |
|---|---|---|---|
| Detent, picker step, slider stop | `UISelectionFeedbackGenerator`, SwiftUI `.sensoryFeedback(.selection, trigger:)` | `HapticFeedbackConstants.CLOCK_TICK` | Nothing, or `navigator.vibrate(8)` where supported (not iOS Safari) |
| Hold threshold reached, snap | `UIImpactFeedbackGenerator(style: .medium)` | `LONG_PRESS` | `navigator.vibrate(15)` where supported |
| Success, failure | `UINotificationFeedbackGenerator` `.success`, `.error` | `CONFIRM`, `REJECT` (Android 11+) | Nothing; the visual and the live region carry it |

## 1. Press, hold and swipe

Fits frequent actions that have a faster or stronger variant. Never the only way to do something.

| Pattern | Build | Guard |
|---|---|---|
| **Hold to escalate** | A tap fires the normal action at once; holding past 500-700 ms charges a ring or scale (1 to about 1.25) in proportion to time, then fires the stronger variant with a burst and a medium haptic. Release early and it stays a tap | The stronger variant is also in the long-press or More menu; it never carries a hidden cost |
| **Long-press preview and menu** | Lift the item (scale 1.03, deeper shadow), dim the rest to about 40% black, grow the menu from the item's nearest edge in 150-200 ms; a reactions row staggers 20-30 ms per item from scale 0.6. Support press, slide and release to pick, as well as tap | Same menu on right-click and from a visible More button; Escape closes; focus moves into the menu |
| **Swipe to reply or act** | Row tracks the finger 1:1 to about 25% of its width, then resists (section 4). The action icon scales 0.6 to 1 as progress reaches the threshold (64-80 px), with a tick haptic at the threshold; release past it fires, before it springs back in about 250 ms | Rules in `MOB-11` and pattern 44; `touch-action: pan-y` keeps vertical scroll |
| **Swipe through a stack** | The top card follows the finger with rotation of dx × 0.05 degrees, capped at 12 degrees; the next card scales 0.95 to 1 as the top one leaves; commit past 35% of the width or above about 0.5 px/ms | Buttons for each outcome, arrow keys, and Undo for the last card |
| **Drag to dismiss** | Opacity follows distance; dismiss when the projected rest point passes half the height or on a fast flick, and leave with the release velocity rather than a fixed duration | Undo for about 5 s when the dismissal hides content |
| **Overscroll actions** | Pulling past the edge reveals a target (back arrow, summary, search, a peeking character) that fills with pull distance; label it ("Release to go back") and commit on release past 72-96 px | Never repurpose an edge where the system already means back or refresh; the same action exists as a control |
| **Custom pull to refresh** | Trigger at 64-80 px with resistance; map pull progress (0-100%) to the artwork's pose, loop only while the real request runs, end within 250 ms of the response, then show "Updated just now". iOS `.refreshable`, Compose `PullToRefreshBox` with a custom indicator; on the web, `overscroll-behavior-y: contain` on the app's own scroller | A Refresh button for keyboard and mouse; no artificial minimum spin (`FBK-02`) |

```js
// Hold to escalate. Keyboard and assistive-technology activation fire `click`, which stays a plain tap.
export function holdToEscalate(button, { holdMs = 600, onTap, onHold }) {
  let start = 0, raf = 0, fired = false;
  const tick = (now) => {
    const p = Math.min(1, (now - start) / holdMs);
    button.style.setProperty("--charge", p.toFixed(3));        // CSS scales the ring or icon from this
    if (p === 1) { fired = true; onHold(); return; }
    raf = requestAnimationFrame(tick);
  };
  const reset = () => { cancelAnimationFrame(raf); button.style.setProperty("--charge", "0"); };
  button.addEventListener("pointerdown", (e) => { if (e.button === 0) { fired = false; start = performance.now(); raf = requestAnimationFrame(tick); } });
  button.addEventListener("pointerup", reset); button.addEventListener("pointerleave", reset);
  button.addEventListener("pointercancel", () => { reset(); fired = true; });   // scrolled away: do nothing
  button.addEventListener("contextmenu", (e) => e.preventDefault());          // this control only
  button.addEventListener("click", () => { if (!fired) onTap(); fired = false; });
}
```

## 2. Morphs and shared elements

Fits when the next thing is the same object in another state. Unrelated destinations fade through instead (`MOT-13`).

| Pattern | Build | Guard |
|---|---|---|
| **Shared element, list to detail** | The mechanics are in `MOT-07` and [motion-engineering.md](motion-engineering.md). The delight layer: carry the image and title across, fade the detail chrome in after the container settles, and let a downward drag shrink the detail back toward its cell under the finger. iOS 18 `.navigationTransition(.zoom(sourceID:in:))`; Compose `SharedTransitionLayout` with `Modifier.sharedElement` | Instant swap where unsupported or under reduced motion |
| **Grow from the trigger** | The control becomes the header of what it opens: a selected day pill stretches into the search field, a channel header unfolds into its menu, a profile chip opens its menu. Reveal with `clip-path: inset()` from the trigger's rectangle in 220-300 ms; content fades in once the morph is about 60% done | Overshoot of 8% or less, and only on rarely used menus; everyday menus stay critically damped |
| **Persistent control changes meaning** | A floating action button stays put while its icon swaps (rotate 90 degrees, scale 0.8 to 1, opacity) in 150-200 ms and its color follows the new action; a speed dial fans its items out along an arc with a 30 ms stagger | Update `aria-label` with the icon; the new action is announced by its name |
| **Mode switches** | Between two modes (guest and host, design and code) the shared indicator slides (`MOT-09`), items in both modes glide to their new places with FLIP, and items unique to one mode fade; 250-350 ms in all | Announce the new mode in a polite live region; one indicator only |
| **Spatial page turns** | Cube between people's stories: rotateY ±90 degrees about the shared edge with `perspective: 1000px`, 300-400 ms, tracking the finger while dragged. Card flip: rotateY 180 degrees in 400-500 ms, `backface-visibility: hidden`, the hidden face `inert` | Crossfade of 150 ms under reduced motion |
| **Map and globe morphs** | Animate the map camera (zoom, pitch, bearing), never a screenshot; switching to a globe uses the map library's globe projection (MapLibre GL JS 5 has one). Alternative routes: the chosen line thickens from 4 to 6 px and rises above the others, which fade to 40% | `jumpTo` instead of `flyTo` under reduced motion |
| **Theme switch reveal** | A View Transition whose new snapshot is revealed by a circle growing from the toggle (code below), 400-500 ms | Skip entirely under reduced motion; switch `color-scheme` inside the update callback so nothing flashes |

```js
// Light/dark switch revealed as a circle from the toggle. CSS also needs:
// ::view-transition-old(root), ::view-transition-new(root) { animation: none; mix-blend-mode: normal; }
export function switchTheme(toggle, apply) {
  if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return apply();
  const r = toggle.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  const end = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  const t = document.startViewTransition(apply);
  t.ready.then(() => document.documentElement.animate(
    { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${end}px at ${x}px ${y}px)`] },
    { duration: 450, easing: "cubic-bezier(0.22, 1, 0.36, 1)", pseudoElement: "::view-transition-new(root)" }));
}
```

## 3. Sheets, drawers, sidebars and moving chrome

Sheet rules are `SCR-20`, modals are `CMP-12` and pattern 11, sheets versus dialogs is pattern 66. The rows below are the layer that makes them feel fluid.

| Pattern | Build | Guard |
|---|---|---|
| **Fluid sheets** | The sheet tracks the finger 1:1, resists above its top detent and snaps to the detent nearest the projected rest point; inner scrolling hands over to dragging only at `scrollTop === 0`. For modal sheets the page behind may scale to 0.94 with rounded corners. iOS `presentationDetents`; Compose `ModalBottomSheet` or `AnchoredDraggable`; web `<dialog>` plus pointer handling | Close button and Escape; ask before discarding typed input |
| **Sidebars** | Slide the sidebar with transform in 200-260 ms and move the main area with FLIP, or animate one container's width under `contain: layout`; collapsed mode keeps icons with tooltips | Remember the state; the toggle's icon shows which way it will go |
| **Composers and search bars** | A composer grows with its text up to about 40% of the viewport; the microphone morphs into a send arrow when text exists. A universal search pill expands into its panel, keeping the caret and typed text through the morph, and the first five results stagger 25 ms | Send and microphone are two named states, not one ambiguous button |
| **Split handles** | A divider between two views (calendar and to-do) snaps at one third, half and two thirds with a detent haptic; double-tap resets | `role="separator"` with `aria-valuenow` and `aria-orientation`; arrow keys move it 5% |
| **Chrome that appears when needed** | A back button slides out from behind the tab bar when the user goes one level deep (220 ms); carousel arrows appear while the pointer is over the carousel or it scrolls and stay while focused; a curved tab bar's notch follows the active tab through an SVG path or mask | Never hide controls on touch; targets stay 44 px |
| **Carousels and card stacks** | Controls and position are `CMP-22`. Delight: `scroll-snap-type: x mandatory` plus a scroll-driven animation (`animation-timeline: view(inline)`) that scales cards with their distance from center; a curved carousel rotates each card about 6 degrees per position around a far `transform-origin`; a stack shows three cards, each 8 px lower and scale 0.96 deeper | Buttons and a visible position; nothing important on cards that are rotated away |
| **Browsing surfaces** | Infinite canvas: pan with inertia, zoom toward the cursor or pinch point, render only tiles within one screen of the viewport. Immersive gallery: full bleed, chrome fades after 3 s idle with a fine pointer only, Escape exits. A grid of daily doodles or a themed journal animates a tile only on hover or focus | A plain list or grid view, keyboard panning, and decorative parallax only for fine pointers |

## 4. Physics: rubber band, inertia, magnetism

Fits anything the user drags or flings. Taps and keyboard moves get ordinary transitions.

| Pattern | Build | Guard |
|---|---|---|
| **Rubber band** | Past a bound, displacement shrinks with distance (code below); on release spring back with a damping ratio near 0.9 in 300-400 ms, with a light haptic at the limit. Use it on slider ends, a window resized below its minimum, control panels and lists | The value clamps; only the visual stretches. Listed as rule 19 in [generic-tells-and-fixes.md](generic-tells-and-fixes.md) |
| **Inertia and fling** | Project the rest point from release velocity and spring there starting at that velocity; something thrown off screen (a closing app, a dragged card) keeps its direction and speed | Keyboard moves land instantly or with a 150 ms ease |
| **Magnetism** | Drop targets within 60-100 px pull the dragged item with strength × (1 − d / r)², grow to 1.05 and highlight; release snaps | A Move to menu (`CMP-33`); the pull never hides which target is chosen |
| **Fluid sliders** | While held the thumb follows the finger with no transition (generic-tells rule 14), stretches about 10-12% along its travel (rule 5) and ticks at each step; a range slider for a stay shows "4 nights" and both dates as it moves | `input type="range"` semantics, Home, End and Page keys; a typed field for precise values |
| **Funnel minimize** | A window pours into its dock icon along a curve: a mesh warp in WebGL for the full effect, or `clip-path` plus transform keyframes for an approximation, 300-450 ms | Scale and fade toward the target in 150 ms under reduced motion |
| **Collision avoidance** | When two moving markers meet (a hover skimmer and the playhead), one yields: dip 6-8 px or shrink in 120 ms, then return | Neither marker's value is ever hidden |
| **Edge distortion** | Items in the last 48 px of a scroller scale toward 0.85 or curve away, driven by `animation-timeline: view()` with `animation-range: exit` | Only for glanceable grids such as emoji; never for text that must be read |
| **Desk toys** | A spinner decays by time, not frames (`ω *= 0.5 ** (dt / halfLifeMs)`); a squeaky toy squashes to 0.85 by 1.15, keeping its area, on a loose spring (ratio about 0.35); a 3D creature walked by dragging uses procedural legs in Three.js and pauses off screen | Optional, off the main path, stops when idle, sound opt-in |

```js
// Displacement past a bound: resistance grows with distance; c near 0.55 feels like native scrolling.
export const rubberBand = (over, size, c = 0.55) =>
  Math.sign(over) * (1 - 1 / ((Math.abs(over) * c) / size + 1)) * size;
// Rest point of a flick under exponential deceleration; rate 0.998 per ms is a normal scroll feel, 0.99 a fast stop.
export const restOffset = (velocityPxPerMs, rate = 0.998) => (velocityPxPerMs * rate) / (1 - rate);
// Magnetic pull toward a target within `radius`, as a 0..strength fraction of the remaining distance.
export const magnet = (dist, radius = 80, strength = 0.35) => (dist >= radius ? 0 : strength * (1 - dist / radius) ** 2);
```

## 5. Micro-animated icons

Fits navigation, tab bars, toolbars and toggles whose icon can act out its meaning. Not a wiggle on every hover (`interaction-feedback.md` motion policy).

| Pattern | Build | Guard |
|---|---|---|
| **Icons that act out their verb** | One motion per icon, tied to what it means: a bell swings ±12 degrees twice, a gear turns 60 degrees, a skip arrow spins once in its direction, a sidebar toggle's panel slides 2-3 px, a filter funnel drips. 250-450 ms on press or selection; hover gets at most a 1-2 px nudge in 150 ms. Each tab in a bar may have its own motion, but all share one duration family and one drawing style | Build with SVG parts (`transform-box: fill-box`) or a vector animation runtime (Lottie or Rive) with a still first frame (`ICO-09`) |
| **Icons that show state** | A password eye's lid closes in 150 ms; a lock's shackle lifts with about 6% overshoot; eyes close when private browsing turns on; a plane flies off when airplane mode ends; a "colorless" swatch drains the preview to grayscale through a filtered copy whose opacity animates (`MOT-01`). Swaps use scale 0.8 to 1, opacity and a 4 px blur (generic-tells rule 18) | The state lives in `aria-pressed` or the label, never only in the drawing |
| **Character toggles** | The knob of a switch is a small character that wakes when on | Native semantics (`role="switch"`, or `<input type="checkbox" switch>` in Safari 17.4+), 3:1 state contrast without the character |
| **Edit-mode jiggle** | Rotate ±1.5 degrees, alternating every 120-140 ms, each icon at a random phase, with a remove badge | Under reduced motion show the badges and a dashed outline instead; a Done button ends the mode |
| **Gentle nudges** | A "love this" heart fills from the bottom with a liquid edge; a favorite star pulses once (600 ms) after the person has opened the same project several times, at most once per item | No repeat nudging, no nudge on a paid action |
| **Brand marks that respond** | The logo animates once per hover intent (after a 150 ms dwell) on the control it belongs to, such as two shapes linking on Connect; app icons that animate do so in the product's own surfaces (the macOS Dock tile can draw custom content through `NSDockTile`) | 1 s or less; never on every page load |

## 6. Numbers, progress and status

Tweening rules are `MOT-14`; honest progress is `FBK-02`, `FBK-06` and `FBK-12`.

| Pattern | Build | Guard |
|---|---|---|
| **Rolling digits** | An odometer rolls only the digits that changed, up for increases and down for decreases, 350-500 ms with a 30 ms right-to-left stagger; separators that appear while editing a currency value hop in from 4 px in 150 ms. iOS `.contentTransition(.numericText(value:))`; Compose `AnimatedContent` with vertical slides | Tabular numerals; the real number is in text for assistive technology |
| **Progress rings and pies** | Drive a ring's `stroke-dashoffset` or a `conic-gradient` from a registered `@property --p` (`MOT-11`); at 100% the ring closes into a check in 300 ms. Activity rings glow only when a goal is truly met | Text value beside the ring; `role="progressbar"` |
| **Staged progress** | Named steps from real events ("Searching 3 sources", "Ranking", "Writing summary"), each ticking to a check | Never time-based fake stages (`FBK-12`) |
| **Score reveal** | A computed score (security, audit) sweeps its gauge while the actual checks finish, then shows the number and the top fix | The sweep follows real check completion; repeat visits show the value at once (`MOT-14`) |
| **Printed receipts and summaries** | A summary or credit receipt prints out of a slot: top-down `clip-path` reveal with a slight sway, a torn edge from a zigzag mask, 600-900 ms | Real, selectable DOM text available at once; tap skips; layout per `CMP-32` |
| **Ambient timers and clocks** | A bedside timer runs dim on black; the second hand sweeps normally and steps once per second in low-power mode (iOS `ProcessInfo.isLowPowerModeEnabled`, Android `PowerManager.isPowerSaveMode`); shift content a few pixels each minute on OLED to avoid burn-in. On the web, which has no low-power signal, use `steps(60)` to cut frames | Pauses when hidden; time also in text |
| **Unlock and verify** | After biometric success, the shackle opens and the account view rises, 300-400 ms in all. One-time-code inputs are covered by [generic-tells-and-fixes.md](generic-tells-and-fixes.md) and `FBK-13` | Nothing animates before verification succeeds (`FBK-11`) |

```js
// Odometer in <span class="odo" aria-hidden="true">, with the value also in visually hidden text. CSS: .col { display:inline-block;
// height:1.2em; overflow:hidden } .strip { display:flex; flex-direction:column; line-height:1.2em; transform:translateY(calc(var(--d) * -1.2em)) }
export function setOdometer(root, value, locale) {
  const chars = [...new Intl.NumberFormat(locale, { numberingSystem: "latn" }).format(value)];   // ASCII digits only
  while (root.children.length < chars.length) root.prepend(column());   // grow on the left: units keep their column
  while (root.children.length > chars.length) root.firstElementChild.remove();
  chars.forEach((ch, i) => {
    const col = root.children[i], digit = /\d/.test(ch);
    col.querySelector(".strip").hidden = !digit;
    col.querySelector(".sep").textContent = digit ? "" : ch;
    col.style.setProperty("--d", digit ? ch : "0");
  });
}
function column() {
  const col = Object.assign(document.createElement("span"), { className: "col" }); col.innerHTML = `<span class="sep"></span><span class="strip">${[..."0123456789"].map((d) => `<span>${d}</span>`).join("")}</span>`;
  return col;
}
```

Add `transition: transform 450ms` to `.strip` inside `@media (prefers-reduced-motion: no-preference)`. A 9 to 0 step rolls back through every digit; for counters that only rise, use an eleven-cell strip (0 to 9 then 0) and reset without a transition after the wrap.

## 7. Skeuomorphic objects

Fits when the object's behavior teaches the interaction (tearing a page means the day is done; a spinning record means playing) in emotional, occasional-use products such as journals, focus timers and music. Not in dense tools, forms or anything people need fast. Draw objects from CSS and SVG layers or 2x images, light every object from one direction across the product, and keep text as real DOM.

| Pattern | Build | Guard |
|---|---|---|
| **Tear-off and peel** | Drag along a perforation; the paper curls by rotating about the tear edge (CSS 3D, or a canvas mesh), commits past 40% or on a flick, and the tear starts the action (end the day, start a focus session) | A Start or Next button does the same |
| **Page flips** | rotateY about the spine in 450-600 ms with a shadow gradient on the turning page; an e-reader curl follows the finger; collections can open as flip books | A setting for slide or no animation; arrow keys; screen readers get continuous text |
| **Booklets, passports and invitations** | A passport cover swings open from its left edge; an invitation's flap rotates 180 degrees on X and the card rises 40%; under 1 s | The content is reachable by an Open button without any gesture |
| **Paper objects** | Postcards with a flip side whose back is a real labeled text area; stamps and postmarks; export as an image with alt text | Flip by button as well as gesture |
| **Players and media objects** | A platter turns at 33⅓ rpm (200 degrees per second) while playing and slows to a stop in 600 ms; the tonearm swings in on play; a cassette slides into the deck before playback; dragging a platter scrubs by angle | An ordinary scrubber and play button alongside |
| **Dials and timers** | Angle from `Math.atan2` of the pointer around the center; detents every minute or five with a tick haptic; a clock face whose hands set a send time | `role="slider"` with `aria-valuetext="25 minutes"`, arrow keys, and a typed time field |
| **Tactile controls and toolbars** | Metallic toggles from static gradients and inner shadows with a 160 ms knob slide; amplifier knobs and switches; game-pad style controls | Highlights do not animate every frame; state shows at 3:1 without the texture |
| **Seals and stamps** | A wax seal drops from scale 1.3 to 1 with about 6% overshoot in 300 ms and leaves a press shadow | Only on a real check (reviewed, verified), never as decoration on unchecked content |
| **Unwrapping** | Opening a new album tears its wrapper away; a zipper drawn along a path opens a screen; complete at 60% progress | Once per item; a button alternative |
| **Scratch and reveal** | Canvas with `globalCompositeOperation = "destination-out"`; sample cleared pixels on a coarse grid every 200 ms and finish at 50-60% | The reward was decided beforehand and is stated in text; nothing random is paid for; a Reveal button |
| **Hand-made marks** | Squiggly dividers generated from a seed per page so they stay stable between renders | `aria-hidden`, with `<hr>` semantics kept |

## 8. Sensors, tilt and light

Decoration only: the interface works the same with sensors off (WCAG SC 2.5.4).

| Pattern | Build | Guard |
|---|---|---|
| **Tilt-reactive depth** | Card tilts at most 6-8 degrees; its shadow moves the opposite way on a separate layer moved with transform (animating `box-shadow` repaints). iOS Safari needs `DeviceOrientationEvent.requestPermission()` from a tap; calibrate to the starting pose; low-pass the signal. iOS native: Core Motion attitude; Android: `Sensor.TYPE_ROTATION_VECTOR`. Pointer tilt on desktop only for fine pointers (`MOT-18`) | Off under reduced motion; stop listening when the card is off screen |
| **Reflections, holograms and iridescence** | A highlight band (`linear-gradient(105deg, transparent 40%, rgb(255 255 255 / .35) 50%, transparent 60%)`) whose position follows tilt or pointer; a holographic layer is a hue `conic-gradient` on a pseudo-element with `mix-blend-mode: color-dodge` at 30-50% opacity | Numbers sit on an opaque layer measured at 4.5:1; no full-screen blend on low-end devices |
| **Blacklight and hidden marks** | A mode button adds a violet tint and reveals marks drawn in a fluorescent color through a mask | Anything revealed is decorative or also stated in text |
| **Ambient context** | Home art follows the local time of day (dawn, day, dusk, night; sunrise times only if location was already granted for another reason); a mascot's mood in a widget follows the day (iOS WidgetKit timelines, Android Glance); raindrops run down weather cards only when it is raining, play once on open and settle | Never ask for location for decoration; moving decoration over 5 s needs a pause (`MOT-19`) |

```js
// Tilt to custom properties --tx and --ty in -1..1. Call from a tap so iOS can show its permission prompt.
export async function enableTilt(el) {
  const DOE = window.DeviceOrientationEvent;
  if (!DOE || matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (typeof DOE.requestPermission === "function" && (await DOE.requestPermission()) !== "granted") return false;
  let base = null, target = { x: 0, y: 0 }, cur = { x: 0, y: 0 }, raf = 0, last = 0;
  const clamp = (v) => Math.max(-1, Math.min(1, v / 30));            // 30 degrees of hand tilt = full effect
  addEventListener("deviceorientation", (e) => {
    if (e.beta == null) return; base ??= { b: e.beta, g: e.gamma };  // the pose the phone is held in now is neutral
    target = { x: clamp(e.gamma - base.g), y: clamp(e.beta - base.b) };
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(step); }
  });
  function step(now) {
    const k = 1 - 0.85 ** ((now - last) / 16.7); last = now;         // frame-rate independent smoothing
    cur = { x: cur.x + (target.x - cur.x) * k, y: cur.y + (target.y - cur.y) * k };
    el.style.setProperty("--tx", cur.x.toFixed(3)); el.style.setProperty("--ty", cur.y.toFixed(3));
    raf = Math.abs(target.x - cur.x) + Math.abs(target.y - cur.y) > 0.002 ? requestAnimationFrame(step) : 0;
  }
  return true;
}
```

## 9. Status-area surfaces

The status pill around the camera cutout on recent phones, the status bar, and on the web the favicon, title and app badge.

| Pattern | Build | Guard |
|---|---|---|
| **Content that emerges from the pill** | An app cannot draw into the system pill; it reaches it only through the live-activity API (ActivityKit) with its compact, minimal and expanded layouts, used for real ongoing work (a translation in progress, a timer, a delivery). Inside the app, elements can grow out of the pill's position: a profile QR code slides down from top center, a profile photo shrinks into the pill area as the header scrolls away, a light control drops from it, a short message pops from it on pull-down. Read the safe-area inset and treat devices without a pill as a plain top edge | Never imitate system prompts, notifications or permission dialogs; end the activity when the task ends; do not hard-code cutout geometry |
| **Status glyphs** | A low-battery or recording glyph pulses opacity 1 to 0.5 at 1 Hz or slower, only while the condition holds, with text ("Battery 8%") | A slow pulse, nowhere near three flashes per second |
| **Web favicon, title and badge** | Draw progress into the favicon (code below), prefix the title ("(42%) Export"), and use `navigator.setAppBadge()` for installed web apps; an in-app tab strip can show drifting notes while its audio element plays (`play` and `pause` events) next to a mute control | Throttle to about four updates a second; some browsers ignore favicon changes, so the title carries the same news |

```js
// Progress ring in the favicon; p in 0..1, or null to restore the original icon and title.
export function faviconProgress(p) {
  const link = document.querySelector('link[rel~="icon"]'); if (!link) return; link.dataset.original ??= link.href;
  const plain = document.title.replace(/^\(\d+%\) /, "");
  if (p == null) { link.href = link.dataset.original; document.title = plain; return; } const c = Object.assign(document.createElement("canvas"), { width: 64, height: 64 }), g = c.getContext("2d");
  g.lineWidth = 10; g.lineCap = "round"; g.strokeStyle = "#9aa0a6"; g.beginPath(); g.arc(32, 32, 24, 0, 2 * Math.PI); g.stroke();
  g.strokeStyle = "#1a7f37"; g.beginPath(); g.arc(32, 32, 24, -Math.PI / 2, -Math.PI / 2 + p * 2 * Math.PI); g.stroke();
  link.href = c.toDataURL("image/png"); document.title = `(${Math.round(p * 100)}%) ${plain}`;
}
```

## 10. Cursor-aware effects

Fine pointers only (`MOT-18`): check `matchMedia("(hover: hover) and (pointer: fine)")`, ignore non-mouse pointer events, keep the system cursor and settle while a field inside is focused.

| Pattern | Build | Guard |
|---|---|---|
| **Spotlight follow** | A soft highlight follows the pointer inside a button or card (code below); a rainbow border rotates a `conic-gradient` with the pointer's angle; a floating card rises 2-4 px with a deeper shadow over 200 ms | One surface type per page, not every card (`MOT-06`) |
| **Proximity reactions** | Within about 200 px a logo or character turns toward the pointer by up to 10 degrees and relaxes over 400 ms when it leaves | One `requestAnimationFrame` loop that stops when settled |
| **Content-aware and randomized hover** | Hover differs by content: videos preview muted after a 300 ms dwell, documents lift with a tilt of ±2 degrees seeded by the item's id so it never changes between visits, a shop tab releases three to five sprite butterflies for under 1.5 s with an animated tooltip | Once per hover intent; the same information on focus and tap |
| **Preview on hover** | An Upgrade button opens a popover of plan benefits after a 300 ms dwell, and also on focus and tap | Price and billing period stated plainly (`SCR-17`); nothing changes without a click |
| **Caret and text cursor** | `caret-color` steps through brand colors about once a second | Each color at 3:1 against the field; one fixed color under reduced motion |
| **Watching mascot** | A character's eyes follow the caret in an email field (position measured with a hidden mirror element) and cover them when the password field is focused | `aria-hidden`; never slows typing; reads nothing but caret position; the form works with it switched off (`SCR-13`) |
| **Show me where** | After a help-menu search, a pointer glides from the result to the real menu item and highlights it for 2-3 s | Highlight only under reduced motion |
| **Multiplayer cursors** | Live cursors are pattern 49. Delight: short emotes typed into cursor chat that fade after about 4 s, and a shake gesture that sends a high-five when two cursors meet (code below) | Opt-in presence, rate limits and an off switch |

```js
// Spotlight: write pointer position on the element that reads it (MOT-18); cache the rect on enter.
// .spot { background: radial-gradient(160px circle at var(--mx, 50%) var(--my, 50%),
//          color-mix(in oklab, var(--accent) 18%, transparent), transparent 70%), var(--surface); }
export function spotlight(el) {
  let rect = null; el.addEventListener("pointerenter", () => { rect = el.getBoundingClientRect(); });
  el.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || !rect) return;
    el.style.setProperty("--mx", `${e.clientX - rect.left}px`); el.style.setProperty("--my", `${e.clientY - rect.top}px`);
  });
}
// Shake: at least four horizontal reversals, each after 24 px or more of travel, within 600 ms.
export function onShake(target, cb, { turns = 4, minPx = 24, windowMs = 600 } = {}) {
  let lastX = null, dir = 0, travel = 0, times = [];
  target.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    const dx = lastX === null ? 0 : e.clientX - lastX, d = Math.sign(dx); lastX = e.clientX; if (!d) return;
    if (d === dir) { travel += Math.abs(dx); return; }
    if (dir && travel >= minPx) times.push(e.timeStamp);
    dir = d; travel = Math.abs(dx);
    times = times.filter((t) => e.timeStamp - t <= windowMs);
    if (times.length >= turns) { times = []; cb(e); }
  });
}
```

## 11. Celebrations, reactions and confetti

| Pattern | Build | Guard |
|---|---|---|
| **Reaction pops** | `MOT-03` sets the pop (5-15% overshoot, settled within 600 ms, count updated at once). Add a ring of 6-10 particles thrown 30-50 px over 400-600 ms, a heart that floats up 40-80 px and fades, or, on a double-tapped video, a heart at the tap point; following someone gets the same small burst | One burst per element per 300 ms; undoing plays nothing |
| **Social reactions** | A vote on a shared list drops the voter's avatar into the stack on a spring while the count rolls | Count and names available as text |
| **Completion moments** | A ripple spreads from the completed cell across the grid (delay = distance × 0.8 ms per px, capped at 400 ms) when a crossword or a check-in finishes; a finished workout morphs into its summary; a finished book slides onto the Read shelf | The summary is readable at once; tap skips |
| **Earned milestones** | Fireworks only for a real top result (a perfect audit score); an achievement badge drops in with one shine sweep in 1-1.2 s; achievements browse in a carousel | Rewards measure real work; no streak pressure or loss framing ([`../../ethical-persuasion.md`](../../ethical-persuasion.md)) |
| **Reward reveals** | Tap to crack a gem in two or three stages, then burst | The reward is fixed before the reveal and stated in text; nothing random is sold |
| **Confetti** | Canvas, 60-150 pieces (about 40 on low-end devices), aimed from the trigger, brand palette, about 1.2 s of emission and 3 s in all (code below), `pointer-events: none`, `aria-hidden` | A status message carries the news ("You're on the waitlist"); no invented queue positions |

```js
// Confetti from a point; resolves when every piece is gone. Skipped under reduced motion.
export function confetti(canvas, { x, y, colors, count = 100, ms = 2800 }) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return Promise.resolve();
  const dpr = Math.min(devicePixelRatio || 1, 2), g = canvas.getContext("2d");
  canvas.width = canvas.clientWidth * dpr; canvas.height = canvas.clientHeight * dpr; g.scale(dpr, dpr);
  const n = (navigator.hardwareConcurrency || 4) <= 4 ? Math.min(count, 40) : count;
  const parts = Array.from({ length: n }, (_, i) => {
    const a = -Math.PI / 2 + (Math.random() - 0.5) * 1.4, speed = 450 + Math.random() * 350;    // px/s, fanned upward
    return { x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, rot: Math.random() * 6, spin: (Math.random() - 0.5) * 12, c: colors[i % colors.length] };
  });
  return new Promise((done) => {
    let last = performance.now(); const t0 = last;
    (function frame(now) {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      g.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      const fade = Math.max(0, 1 - (now - t0 - ms * 0.7) / (ms * 0.3));
      for (const p of parts) {
        p.vy += 1200 * dt; p.vx *= 0.985; p.vy *= 0.985; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.spin * dt;
        g.save(); g.globalAlpha = fade; g.translate(p.x, p.y); g.rotate(p.rot); g.fillStyle = p.c; g.fillRect(-4, -2, 8, 4); g.restore();
      }
      if (now - t0 < ms) requestAnimationFrame(frame); else { g.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight); done(); }
    })(last);
  });
}
```

## 12. Deletion, tossing and transfer

The data changes first; the object's flight explains where it went.

| Pattern | Build | Guard |
|---|---|---|
| **Delete and undo** | The item tosses into the bin, whose lid opens and closes, and the badge updates; Undo plays the flight backward | Undo over confirmation for reversible deletes (`FBK-15`, patterns 38 and 68) |
| **Disintegrate** | The item breaks into particles that drift 20-40 px and fade over 500-800 ms: an animated noise mask (`mask-image` driven by a registered `@property --t`) or a WebGL pass; avoid rasterizing the DOM on every delete | Removed from the accessibility tree at the start; a 150 ms fade under reduced motion |
| **Toss to a destination** | A copy flies on an arc into its destination (downloads into the library, a link into the tab switcher, a message into a folder, a cancelled voice note's microphone into the bin), shrinking to the target's size in 350-500 ms; the target then bounces to 1.15 (code below) | The destination's count updates when the flight starts |
| **Arrivals** | An uploaded file drops into the list from the point where it was released (`MOT-08`) with per-file progress (pattern 36); a card added to a wallet slides into the stack with a slight 3D tilt and the stack resettles | Errors stay with the file they belong to |
| **Send-off** | Once the server confirms, a Verify button folds into a paper plane and flies off in 600-800 ms, leaving "Sent to a•••@example.com" | Never before confirmation (`FBK-11`) |
| **Stamps that confirm** | Choosing a report reason stamps the post "Reported" at -6 degrees in 250 ms | The state is also in text; reversible if the product allows it |
| **Ritual release** | Letting go of a journal entry burns it away from the bottom edge over 1.5-2 s | Irreversible, so confirm first (`FBK-08`); offer "Keep private" as the alternative; fade under reduced motion |
| **Clearing** | A cleared notification badge slides away while its count rolls down | |
| **Cooling-off countdown** | Before an irreversible, high-impact confirm button enables, a 3-5 s countdown with a reason ("Deleting 1,204 files. Available in 3 s") | Cancel works throughout; announce once, not every second; never on routine actions (`FBK-08`, pattern 37) |

```js
// Toss a visual copy of `source` along an arc into `target`. Update the real data before calling.
export async function toss(source, target, { duration = 420 } = {}) {
  const a = source.getBoundingClientRect(), b = target.getBoundingClientRect();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const ghost = source.cloneNode(true); ghost.setAttribute("aria-hidden", "true"); ghost.inert = true;
  Object.assign(ghost.style, { position: "fixed", left: `${a.left}px`, top: `${a.top}px`, width: `${a.width}px`,
    height: `${a.height}px`, margin: "0", pointerEvents: "none", zIndex: "1000" });
  document.body.append(ghost);
  const dx = b.left + b.width / 2 - (a.left + a.width / 2), dy = b.top + b.height / 2 - (a.top + a.height / 2);
  const lift = Math.min(120, Math.abs(dx) * 0.3 + 40), endScale = Math.min(1, b.width / a.width);
  const frames = Array.from({ length: 13 }, (_, i) => {
    const t = i / 12, e = t * t * (3 - 2 * t);                                  // smoothstep along the path
    const px = dx * e, py = dy * e - lift * 4 * e * (1 - e);                    // parabola that peaks mid-flight
    return { transform: `translate(${px}px, ${py}px) scale(${1 - (1 - endScale) * e}) rotate(${-12 * e}deg)`,
             opacity: t > 0.85 ? (1 - t) / 0.15 : 1 };
  });
  await ghost.animate(frames, { duration, easing: "linear" }).finished.catch(() => {}); ghost.remove();
  target.animate([{ scale: 1 }, { scale: 1.15 }, { scale: 1 }], { duration: 220, easing: "ease-out" });
}
```

## 13. Launch, onboarding and what's new

Launch screens are `FBK-19`; onboarding steps are `SCR-08` to `SCR-10`, `SCR-13` and `SCR-14`.

| Pattern | Build | Guard |
|---|---|---|
| **Launch screens** | Animate the mark only while real loading happens, then hand off by moving the mark into its place on the first screen (a shared element) instead of fading to blank. Android 12+ SplashScreen API: `windowSplashScreenAnimatedIcon` (keep it to about 1 s) and `setKeepOnScreenCondition` | Once per session; never held after content is ready |
| **Welcome intros** | One orchestrated sequence of 3 s or less: a slow gradient, a light particle field, a lens flare or a screen that frosts over step by step as setup progresses. Use a shader or a short video with a poster; pause off screen | Skip from the first frame; shown once; no bright bursts faster than three per second |
| **Gesture entry** | Swipe up to enter, slide to unlock, unzip to begin | A visible button does the same (`SCR-13`, `MOB-11`) |
| **Teach by doing** | A shortcut lesson asks the person to press the keys; on-screen keycaps sink 2 px and light up when the real `keydown` arrives, with platform modifiers (⌘ on macOS, Ctrl elsewhere) | Skip at any time; never blocks the app |
| **Unpacking** | Tablet onboarding as a box whose lid lifts, with one feature coming out per step | One job per step and a way back (`SCR-14`) |
| **What's new** | Three cards or fewer, in context, dismissible and reopenable from Help; a rotating 3D device with hotspots (`<model-viewer>` or Three.js with a poster and a plain list); a gradient sweep that reveals a new model's name once in 800-1200 ms; a card announcing a redesign with "Take a look" and "Not now" | Never between the person and the task they opened the app for |
| **Sign-in personality** | A logo that bounces once, or small interactive to-dos beside a login form | The form renders at once and works without the decoration (`SCR-13`) |

## 14. Empty, waiting, offline and error states

Rules: `FBK-09`, `FBK-22`, `SCR-18` and patterns 22 and 26. Games while waiting are in [playful-moments.md](playful-moments.md).

| Pattern | Build | Guard |
|---|---|---|
| **Interactive empty illustrations** | The illustration blinks or waves on hover or tap; SVG under about 20 KB or a vector animation under about 50 KB | `aria-hidden`; the one primary action stays primary |
| **No results with physics** | Result cards drop to the bottom with a slight rotation in about 500 ms, then the message offers a spelling fix and Clear filters | A fade under reduced motion; suggestions are real |
| **Reconnecting** | A plug or signal glyph animates only during each real retry and shows "Retrying in 4 s" with Retry now | Persistent status, not a toast (`FBK-22`) |
| **Caught up** | The end of a feed says "You're all caught up" with a calm way out. Mobile apps should not quit themselves (iOS guidance forbids it); offer a Close or end-of-feed screen instead | No infinite scroll past this point disguised as new content |

## 15. Data made tangible

Fits when a number has a physical analog people already understand (health, money, travel). When exact comparison matters, use a chart (`CMP-18`, `CMP-34`) and keep the object as a companion.

| Pattern | Build | Guard |
|---|---|---|
| **Quantities as objects** | A water bottle drains with each logged glass (fill height in proportion to what is left); subscriptions orbit as moons sized by cost (radius ∝ √cost, so area matches) and moving faster when billed more often; an illustration adds a figure for each seat selected | Exact values in text and a sorted list beside the picture |
| **Scales you can feel** | An effort or intensity picker whose illustration grows more intense per level; isometric illustrations that animate when a filter is chosen; moods that morph into their own shapes (SVG paths with equal point counts) | Every level and mood has a visible text label |
| **Journeys and timelines** | A trip view as a timeline of stops with a live dot interpolated between position updates and delays stated in minutes; a delay report with aircraft facts; a date browser that stacks one card behind the current one per day away from today, capped at seven with "+12" | Times in text with time zones; stale data marked |
| **Scrub through time** | A sky gradient computed from sun elevation per time zone while scrubbing; zoom from day to month to year by pinch and by buttons; a two-finger drag that tilts the calendar into 3D; an hourly weather slider with a detent per hour | The scrubber has keyboard steps; 3D views are optional |
| **Live scores and brackets** | A bracket highlights a team's path on hover or focus and zooms on phones; when a real goal event arrives, the ball bounces toward the scoring side | The score is announced in a polite live region; no simulated events |
| **Charts you can touch** | Bars grow from the baseline once on first view (600 ms or less, 30 ms stagger); scrubbing reads exact values with a detent haptic per bar | A data table alternative (`CMP-18`) |
| **Hardware made visible** | Configuring a physical button shows a 3D render of it pressing and lighting for the chosen action (image sequence or a small glTF) | A still image under reduced motion |

## 16. Voice, AI and agent presence

States follow `FBK-17`; assistant surfaces follow `SCR-24`, `SCR-26` and `SCR-28`.

| Pattern | Build | Guard |
|---|---|---|
| **Voice orb** | The orb answers real audio: RMS from a Web Audio `AnalyserNode` (`getFloatTimeDomainData`) at 30-60 Hz, smoothed with about 50 ms attack and 200 ms release, drives scale (1 to 1.12) and surface noise; distinct looks for listening, thinking, speaking and muted. A voice picker gives each voice its own orb color, motion and a short sample; invoking the assistant sends one glow around the screen edge in 300-500 ms; music recognition pulses rings with the input level | A status line in text with each state; nothing pulses when the microphone is off |
| **Effort and mode selectors** | A reasoning-effort control whose icon gains intensity per level, with a label that states the trade ("Slower, more thorough, uses more of your limit") | The cost is stated, not implied by the animation |
| **Agent at work** | The working indicator is driven by real steps (tool name, file, elapsed time); a command-line agent may animate its text logo for 500 ms or less at start | Skip the logo when output is not a terminal (`process.stdout.isTTY`), honor `NO_COLOR` and a flag to turn it off; never delay the prompt |
| **Agent permission requests** | A clear request names the tool, the exact command or files and the scope, with Allow once, Allow for this project and Deny of equal weight | No animated emphasis on Allow, no countdown that auto-approves |
| **Private and temporary modes** | Turning on a temporary chat darkens the surface and dresses its icon in a disguise in 400 ms or less | A persistent label ("Temporary chat: not saved to history") while it is on |
| **Personalizing an assistant** | Tone and trait panels slide between steps while a sample reply updates live | The preview is labeled as a sample |

## 17. Media, camera and capture

| Pattern | Build | Guard |
|---|---|---|
| **Playback ambience** | While a podcast plays, two to four small icons drift up at low opacity over 3-5 s each; a record spins while music plays; a like button glows for 1-2 s when the creator asks for likes, using timed markers the creator supplied | Stops with playback and under reduced motion; once per marker |
| **Camera open and controls** | An aperture opens in 250-350 ms while `getUserMedia` actually resolves; a zoom dial detents at each stop with a tick; a faceless profile camera replaces the face on device with an avatar or silhouette before anything is uploaded; an instant-camera widget ejects a print that develops from blurred and pale to full over 2-3 s | The camera indicator stays visible; nothing leaves the device before the person confirms |
| **Loupe** | A circular magnifier of 100-120 px at 2-3x sits above the finger so it is not covered, drawn from the high-resolution source | Arrow keys move it; it never replaces real zoom |
| **Scanning** | A scan line sweeps once per detection pass and dots appear on objects as real detections arrive | Stops when results arrive |
| **Spoiler reveal** | A shimmering noise cover over spoiler text disperses in 400 ms on tap | A button with `aria-expanded` ("Spoiler, show"); text hidden from assistive technology until revealed |

## Pitfalls

- Delight that replays on every visit or every render instead of following the wear-out schedule.
- Random effects that change between renders: seed them by item id, or hydration and layout shift follow.
- Particle systems with no cap, loops that never stop, sensors left listening off screen. Pause on `visibilitychange` and with IntersectionObserver (`MOT-05`).
- Hard-coded device geometry (cutout size, safe areas, notch positions) and gestures that fight system back and refresh.
- Animating `box-shadow`, `filter` or layout on large layers every frame; animate transform and opacity of a pre-drawn layer.
- Judging delight by clicks or time spent; judge it by task completion, complaints and opt-out rate.

## Done when

- [ ] Each detail has a named purpose, sits within the frequency budget and follows the wear-out schedule.
- [ ] The state change, count and live-region text update immediately; the animation can be interrupted and skipped.
- [ ] Every gesture, hold and sensor effect has a visible control or menu equivalent and works by keyboard.
- [ ] Reduced motion was tested on web, iOS and Android where shipped: meaning kept, movement gone.
- [ ] Flashing stays at three per second or fewer, and text contrast was measured on the busiest frame.
- [ ] Loops pause when hidden or off screen, particles are capped, and the flows were profiled at 4x CPU throttling or on a mid-range phone.
- [ ] No delight hides a cost, a consent choice or a limitation, and licensed characters or marks have rights on file.
