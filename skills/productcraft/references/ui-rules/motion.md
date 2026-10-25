# UI rules: Motion and animation

Durations, easing, reduced motion, layout transitions, springs, sequencing and performance. Rule IDs use the `MOT-` prefix; cite them in change reports.

## MOT-01. Animate transform and opacity

**Why:** Transform and opacity run on the compositor; animating layout properties forces reflow on every frame.

- **Do:** Move, scale and fade with transform and opacity, and fill meters with transform: scaleX() from transform-origin: left.
- **Do:** Use the individual translate, scale and rotate properties when several sources (hover, keyframes, script) animate one element, and give each property one owner.
- **Do:** When a rounded pill must change length, size it to its largest state and animate clip-path: inset(<v> <h> round 999px) toward zero inset; animate width on that one element with contain: layout style only when its content must reflow.
- **Do:** Move items along an arc by setting transform-origin to the arc's center, even far outside the element, and animating rotate (or use offset-path); counter-rotate inner text that must stay upright.
- **Do:** To fade between sharp and blurred or color and grayscale, stack a copy whose filter is set once and animate only its opacity, with alt="" on a duplicate image.
- **Avoid:** Animating top, left, width or height on many elements, or several sources writing the transform shorthand at once.
- **Avoid:** Animating filter: blur() or backdrop-filter on large layers such as a whole dashboard or form, which re-rasterizes them on every frame.

## MOT-02. Keep a duration budget

**Why:** Consistent, short durations keep interfaces responsive; long sequences belong only to rare moments.

- **Do:** Use about 100ms or less for press feedback, about 150-200ms for hover, focus and color changes, 200-450ms for panels, morphs and route changes, and finish staggered entrances within about 600ms.
- **Do:** Make exits shorter than entrances, about 60-70% of the entry (for example 250ms in, 150ms out), with separate enter and exit duration tokens.
- **Do:** Open menus, dropdowns and popovers in about 120-170ms with opacity and a small scale (0.95 to 1), and close them in about 75-100ms.
- **Do:** Keep celebrations under about 1.2s per segment and let users skip them.
- **Do:** Keep the next view usable immediately while decorative motion finishes.
- **Avoid:** Multi-second animation on routine actions, or blocking input until an animation ends.
- **Avoid:** Menus that take 300ms or more to open, or exits as slow as their entrances.

## MOT-03. Match easing to the motion

**Why:** Easing tells people whether something is arriving, leaving or physical.

- **Do:** Use ease-out for entrances and responses, ease-in for exits, and a spring or springy curve (linear() or an overshooting cubic-bezier such as cubic-bezier(.34, 1.56, .64, 1)) only for physical or celebratory moments.
- **Do:** Keep celebratory pops (like, favorite, rating) to about 5-15% overshoot on an inner icon, settled within about 600ms, while the count and pressed state update at once.
- **Do:** Set transform-origin to the corner or edge nearest the trigger and update it whenever collision logic flips the placement, so a surface grows out of what was clicked.
- **Do:** Store easings and durations as tokens and reuse them.
- **Avoid:** Bouncy overshoot on navigation and chrome people use constantly; keep it critically damped or under about 3% overshoot, settled within about 350ms.
- **Avoid:** "spring" as a CSS timing keyword: it is not valid, and one invalid easing drops the whole transition declaration, including its valid parts.

## MOT-04. Reduced motion removes decoration, never the state change

**Why:** Vestibular-sensitive users need motion off while still seeing what changed.

- **Do:** Wrap travel, parallax, 3D flips, loops and pointer-follow effects in @media (prefers-reduced-motion: no-preference), or check matchMedia in script.
- **Do:** Under reduced motion jump straight to end states, still updating counts, labels and icons, and replace looping loaders with a static indicator plus text.
- **Do:** Opt in to cross-document view transitions only inside @media (prefers-reduced-motion: no-preference) { @view-transition { navigation: auto; } }, and under reduced motion skip same-document transitions or set animation: none on the ::view-transition-group(*), -old(*) and -new(*) pseudo-elements.
- **Avoid:** Infinite decorative animation with no reduced-motion path, or skipping the state update along with the animation.

## MOT-05. Pause what nobody can see

**Why:** Animation loops that keep running off-screen or after motion settles waste battery and main-thread time.

- **Do:** Start requestAnimationFrame loops on demand and stop them once values settle.
- **Do:** Pause loops when the element is off-screen (IntersectionObserver) or the tab is hidden (visibilitychange).
- **Avoid:** Perpetual loops for effects that are idle or invisible.

## MOT-06. Stagger related entrances briefly

**Why:** A short stagger gives grouped elements a readable order instead of everything popping at once.

- **Do:** Offset siblings by about 40-80ms (about 25-35ms for short rows of small items such as rating stars or step dots), animating opacity plus a small translate (8-24px) or scale (0.96 to 1), and stagger only the first few items of long lists.
- **Do:** Animate dialogs, menus and confirmations once as a container (about 150-200ms) and show their title, body and buttons together.
- **Do:** Use animation-fill-mode: backwards on delayed entrances so items wait invisibly instead of flashing.
- **Do:** Keep content visible by default and add the hidden start state only when scripts run and motion is allowed.
- **Avoid:** Staggering dozens of items one by one, or content hidden until scripts load.
- **Avoid:** The same scroll-triggered fade-up on every section or a hover lift on every card; keep entrances to one orchestrated moment and use motion elsewhere to answer an action or show a change.

## MOT-07. Morph one element instead of crossfading two

**Why:** When the same surface grows into the next state, people keep track of where they are; crossfades create muddy double images.

- **Do:** Use the View Transitions API (document.startViewTransition with a shared view-transition-name) or FLIP to grow a button into its panel and shrink it back.
- **Do:** Let the container settle first (about 250-450ms), then fade the inner content (about 150ms), with the anchor fixed at the trigger.
- **Do:** Give each view-transition-name to only one rendered element: set it inline on the clicked element just before startViewTransition() and clear it once transition.finished resolves.
- **Avoid:** Scaling text during a morph, stacking two headlines in place, or chaining several morphs without user input.
- **Avoid:** One shared view-transition-name on every card in a list, which aborts the transition.

## MOT-08. Use FLIP for layout changes

**Why:** Measuring first and animating only transform gives smooth layout transitions without layout thrash.

- **Do:** Measure with getBoundingClientRect, apply the change, compute the offset and play element.animate() from the inverted transform back to none.
- **Do:** Measure an untransformed wrapper, because a rotated or scaled element reports its bounding box, not its real size.
- **Do:** Animate new items from where they came from, such as the drop point of an upload.
- **Avoid:** Moving elements by animating left, top or width.

## MOT-09. Move one shared indicator between items

**Why:** A single highlight that glides between options explains a change of selection better than items flashing on and off.

- **Do:** Render one indicator (pill, underline or dot) and move it with transform to the active item, about 180-250ms ease-out or a spring with a damping ratio of about 0.8-1 (for example stiffness 400, damping 40).
- **Do:** Keep it behind the label so text keeps its contrast, and jump without the slide under reduced motion.
- **Do:** To recolor the label where the pill is, overlay an aria-hidden copy of the labels in the on-indicator color, clipped with clip-path: inset() to the indicator's current edges; driving the leading edge with a stiffer spring than the trailing one stretches the pill without animating width.
- **Avoid:** Re-mounting a separate indicator per item, animating its left and width every frame, or a wobbly spring that overshoots visibly and takes most of a second to settle.

## MOT-10. Sequence animations on real completion events

**Why:** Chained guessed timeouts drift out of sync; completion events keep multi-step sequences correct and cancellable.

- **Do:** Await element.animate(...).finished, or listen for animationend and transitionend filtered by name, before the next step.
- **Do:** For multi-part scenes, run every part on one shared duration with keyframe percentages, and end state changes from the animation events.
- **Do:** Give each phase a state class or data attribute so it is easy to reverse or skip.
- **Avoid:** Nested setTimeout chains or fixed waits that drift from the CSS durations.

## MOT-11. Register custom properties you animate

**Why:** Unregistered custom properties cannot interpolate, so color and number tweens snap halfway.

- **Do:** Declare them with @property (syntax "<number>", "<color>", "<percentage>", with initial-value) and transition or animate them directly.
- **Do:** Drive several visuals (position, shadow, color, glow) from one registered variable with calc() so they stay consistent.
- **Do:** Keep calc() types valid and provide an instant fallback where @property is unsupported.
- **Avoid:** Expecting plain custom properties to animate, or type-mismatched calc() that silently drops the whole declaration.

## MOT-12. Use springs for interruptible physical motion

**Why:** Damped springs feel physical and can be interrupted mid-motion, unlike fixed-duration tweens.

- **Do:** Integrate with the frame's delta time (v += (-k * x - c * v) * dt; x += v * dt) and stop when position and velocity fall below a small threshold.
- **Do:** Write spring results into custom properties or transforms, and use CSS linear() spring approximations where a fixed end point is enough.
- **Do:** Choose damping from the damping ratio c / (2 * sqrt(k * m)): about 0.8-1 for panels, navigation and indicators (k = 210, c = 26 gives about 0.9 and settles in about 0.3s), about 0.3-0.4 only for playful toys, which visibly ring; settling takes roughly 4 / (ratio * sqrt(k / m)) seconds.
- **Do:** Keep simple on and off visuals near-instant; springs are for movement.
- **Avoid:** Frame-rate-dependent integration without delta time, or long wobbly settles on primary navigation.

## MOT-13. Move content in the direction of navigation

**Why:** Content that slides the way the user went preserves spatial orientation.

- **Do:** Slide in the direction of travel only between ordered siblings: steppers, in-page tabs, pagers, carousels, and push or pop within a stack.
- **Do:** Compute the direction from the old and new index and slide the outgoing view out on that side while the next enters from the other.
- **Do:** Overlap the tweens slightly and use a strong ease-out.
- **Do:** For top-level destinations such as bottom tabs and sidebar sections, switch instantly or fade through: old content out over about 90-150ms, new content in over about 150-210ms with an optional 0.92 to 1 scale, while the navigation shell stays still.
- **Avoid:** Sliding the same way whether the user went forward or back.
- **Avoid:** Sliding between sections whose order is arbitrary, or a blank gap longer than about 100ms between outgoing and incoming content.

## MOT-14. Animate changing numbers without jitter

**Why:** Counting to a new value signals fresh data, but changing digit widths make the layout twitch.

- **Do:** Show a skeleton until the value is known, then render it directly; tween only from the previous real value to a new one when live data changes.
- **Do:** Tween over about 300-800ms with ease-out, format each frame with Intl.NumberFormat, and use tabular numerals with a minimum width.
- **Do:** Tween figures derived from the counter (totals, percentages) in step with it, or update them when it ends.
- **Do:** Expose only the final value to assistive technology and show it immediately under reduced motion.
- **Avoid:** Counters inside live regions (every frame gets announced), or replaying the count on every visit or re-render.
- **Avoid:** Counting up from 0 on load, 0 as a placeholder for an unloaded number, or counting fixed facts such as lead times, years or guarantees.

## MOT-15. Use clip-path for reveals and shape morphs

**Why:** Clip-path reveals are cheap and can grow a dot into a fill or open a panel from the tap point without layout work.

- **Do:** Animate between shapes of the same function (inset to inset, circle to circle) expressed in lengths, for example circle(0 at x y) to circle(150% at x y).
- **Do:** For pills use inset() with round 999px, and draw a resting dot as the same inset() with large side values so the reveal never switches functions.
- **Do:** Use negative inset values so focus rings and shadows are not clipped, and keep clipped content out of the focus order until revealed.
- **Do:** Clip the interactive element itself when a control morphs, since clip-path also limits hit testing, and keep the clipped shape at least 24x24px (WCAG 2.2 SC 2.5.8), preferably 44px.
- **Do:** Drive reveals from the disclosure state ([aria-expanded="true"] on the trigger or data-state="open"), not from :hover.
- **Avoid:** Mixing shape functions, which snaps instead of animating.
- **Avoid:** Content that unclips only on hover, so keyboard and touch users can never open it.

## MOT-16. Treat scroll-driven effects as enhancement

**Why:** Scroll-linked motion can tell a product story, but content must work without it and scrolling must stay native.

- **Do:** Use animation-timeline: view() with animation-range where supported, or IntersectionObserver, animating only transform and opacity.
- **Do:** For pinned stages use position: sticky inside a tall section with 100svh height, provide a skip link, and show static images under reduced motion.
- **Avoid:** Scroll-jacking, changing scroll speed, or unrevealed text left too faint to read.

## MOT-17. Never make people wait for decoration

**Why:** Animation that holds back a real result or the next input costs time on every use.

- **Do:** Send the request immediately and let any themed animation play alongside it, using a short minimum display time only to avoid flicker.
- **Do:** Keep the actual state change (item in cart, signed in, sent) independent of the animation finishing: update counts and swap local views at once, with at most about a 250ms morph.
- **Do:** Show in-progress or confirmed text within about 400ms and run any themed scene beside it, skippable and removed under reduced motion.
- **Do:** When the result arrives during a looping animation, end the loop then instead of finishing the cycle, waiting at most about 250ms to align it.
- **Avoid:** Artificial delays before network calls, or multi-second sequences in front of frequent actions.
- **Avoid:** A loader in front of a purely local view switch, or a text label replaced by a bare icon while the animation plays.

## MOT-18. Enable pointer-driven effects only for fine pointers

**Why:** Tilt, cursor labels and parallax need a precise pointer and get in the way elsewhere.

- **Do:** Enable them only when matchMedia("(hover: hover) and (pointer: fine)") matches, run updates from one requestAnimationFrame loop that stops once the motion settles, and keep angles small.
- **Do:** Return early from pointer handlers unless event.pointerType === "mouse", since hybrid devices also fire pointerenter and pointerleave for touch and pen.
- **Do:** Settle the effect while a field inside is focused, and keep the system cursor visible.
- **Do:** Write pointer-driven custom properties on the component that reads them, not on :root, and register them with inherits: false when only that element uses them.
- **Avoid:** Running these effects on touch devices or under reduced motion.

## MOT-19. Make long-running motion pausable

**Why:** Anything that moves for more than five seconds alongside other content must be stoppable.

- **Do:** Give marquees, autoplaying video and looping backgrounds a pause control, pause on hover and focus, and stop them under reduced motion.
- **Do:** Autoplay video only muted, with playsinline and a poster image.
- **Avoid:** Unmuted autoplay, or essential information only inside a moving ticker.

## MOT-20. Split text for animation without breaking screen readers

**Why:** Wrapping each word or letter in an element makes screen readers spell text out unless the full string is preserved.

- **Do:** Put the full text in an aria-label on the container and aria-hidden on the generated spans.
- **Do:** Animate words and letters with separate wrappers so transforms do not overwrite each other, and limit split animation to short headlines.
- **Avoid:** Per-letter animation on body copy, split spans exposed to assistive technology, or will-change: transform on every split span, which keeps each on its own layer; set it on the container only while the entrance runs, if at all.

## MOT-21. Keep flashing below seizure thresholds

**Why:** Rapid flicker can trigger seizures in people with photosensitive epilepsy, and WCAG 2.2 SC 2.3.1 (Level A) allows no more than three flashes in any one second above the flash thresholds.

- **Do:** Keep any flicker, strobe, glitch, blink or lightning effect to three flashes or fewer in any one-second window.
- **Do:** If faster flicker is essential, keep it small (well under a quarter of the viewport; the WCAG reference area is about 341x256 CSS px) with a luminance swing under 10% of maximum.
- **Do:** Remove decorative flicker entirely under prefers-reduced-motion, and prefer a single fade or a cut to rapid light-dark alternation for transitions and alerts.
- **Avoid:** Flickering the whole page background or a full-viewport light on and off, including retro CRT and terminal effects.
- **Avoid:** Rapid alternation involving saturated red.
