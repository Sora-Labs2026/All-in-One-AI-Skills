# UI rules: Front-end engineering

Native elements, state management, robustness and progressive enhancement. Rule IDs use the `ENG-` prefix; cite them in change reports.

## ENG-01. Start from native elements

**Why:** Native elements bring focus, keyboard activation, form behavior and correct announcements for free.

- **Do:** Use button type="button" for actions, a href for navigation, mailto links and downloads (a download), and a real form with a submit button.
- **Do:** Check that forms work unstyled and without scripts, then layer validation and animation on top, adding novalidate only when your script replaces native messages.
- **Avoid:** Div click handlers, or role="button" without tabindex and key handling.

## ENG-02. Model async controls as a state machine

**Why:** Download, pay, send and add buttons have mutually exclusive states; independent flags allow impossible combinations and double submissions.

- **Do:** Declare the allowed transitions (idle to working to done or failed, and back) and reflect the current state in one data-state attribute that all styling reads.
- **Do:** Ignore activation unless the state allows it, set aria-busy and disabled or aria-disabled while working, and auto-reset after a short confirmation when the action repeats.
- **Do:** For optimistic toggles keep the confirmed and the pending value separately: render pending at once, promote it on success, restore the confirmed value with a short error and Retry on failure, and send only the latest state after rapid toggles.
- **Avoid:** Separate loading, success and error booleans that can all be true, or a second click restarting the request mid-flight.

## ENG-03. Keep button size stable across label changes

**Why:** Swapping "Pay" for "Done" changes width and shifts the layout under the pointer.

- **Do:** Render every state label in the same grid cell (display: grid with each label at grid-area: 1 / 1) and show the active one with visibility, so the widest sets the size.
- **Do:** Hide inactive labels from assistive technology and announce the new state in a live region; keep icon-only phases named (aria-label="Pay $248.00").
- **Avoid:** Replacing the label text and letting the button resize, or exposing all stacked labels to screen readers at once.

## ENG-04. Keep the hit box still and animate an inner layer

**Why:** If the element receiving pointer events moves, hover flickers and clicks miss.

- **Do:** Give the outer link or button a fixed box and apply transforms to an inner span, driving state from a data attribute set on pointerenter and pointerleave (or, with a motion library, from hover and tap gestures on the outer element that propagate to the inner span).
- **Do:** Limit CSS transitions on script-animated elements to colors; a transition-all utility re-eases every frame the script writes and makes the motion lag.
- **Avoid:** Scaling or translating the element that receives pointer events.

## ENG-05. Make hidden and covered content inert

**Why:** Content that is visually hidden or covered must not take focus or be read out.

- **Do:** Set inert on inactive panes, covered forms and non-current wizard steps, switching it at the moment content is fully covered, then move focus to the first field of the new view.
- **Do:** Make the page behind an open dialog or sheet inert, and restore focus to the trigger on close.
- **Avoid:** Visually hidden but focusable fields, or aria-hidden on containers that hold focusable controls.

## ENG-06. Drive one root state attribute

**Why:** One state on the component root keeps visuals, tokens and semantics in sync.

- **Do:** Toggle a single class or data attribute on the root and style descendants from it.
- **Do:** Update inert and aria attributes in the same function that changes the state.
- **Avoid:** Scattered per-element flags that can contradict each other.

## ENG-07. Render repeated UI from data and format at render time

**Why:** Defining tiles, rows and menus as data keeps markup consistent and values computable.

- **Do:** Map arrays of raw values ({ title, value, change, icon }) to one component keyed by a stable id, never the array index, so per-item state (playing media, expanded text, a half-typed reply) stays with its row when items are inserted or reordered.
- **Do:** Store numbers and dates raw and format them at render with Intl.NumberFormat and Intl.DateTimeFormat.
- **Avoid:** Copy-pasted near-identical markup per item, or preformatted strings that cannot be sorted or summed.

## ENG-08. Enhance heavy visuals progressively

**Why:** Canvas, WebGL and animation libraries can fail or load late; the interface must stay usable and themable without them.

- **Do:** Ship a CSS or static fallback and remove it only after the enhanced version has painted.
- **Do:** Keep colors and sizes in CSS custom properties and read them from script with getComputedStyle.
- **Do:** Lazy-load heavy libraries and show loading progress for large assets.
- **Avoid:** Hard-coded colors and sizes in script, or a selected state that disappears when scripts fail.

## ENG-09. Schedule clocks and countdowns against real time

**Why:** Interval timers drift; scheduling against the wall clock keeps displays accurate.

- **Do:** Schedule each tick for the next whole second (1000 - Date.now() % 1000 ms) and read the time again from Date.
- **Do:** Render times in a time element with tabular numerals and keep rotating hands moving forward.
- **Do:** Announce only meaningful thresholds, never every tick.
- **Avoid:** setInterval counting its own ticks, or a live region on a clock that changes every second.

## ENG-10. Persist interface preferences safely

**Why:** Theme, sidebar, sound and similar choices should survive reloads without breaking when storage is unavailable.

- **Do:** Store small preferences in localStorage wrapped in try/catch and fall back to defaults when it fails.
- **Do:** Read system preferences (prefers-color-scheme, prefers-reduced-motion) for first-run defaults.
- **Avoid:** Crashing or blocking rendering when storage is blocked.

## ENG-11. Package reusable widgets as custom elements

**Why:** A custom element configured by attributes drops into any stack without a build step.

- **Do:** Register the element as a module, configure it through attributes, reflect its state on the host and style states with :host([state="done"]).
- **Avoid:** Shipping test-only attributes (such as simulated progress) without a real progress source.

## ENG-12. Match system chrome to the theme and clean up listeners

**Why:** Status-bar colors, orientation locks and leaked listeners cause flashes, jank and memory leaks in apps.

- **Do:** Initialize the shell before the first frame (preload assets, set transparent system bars with icon brightness from the active theme).
- **Do:** Set both the iOS status-bar brightness flag and the Android icon brightness flag for each theme, checking what each means: in some toolkits one describes the bar background and the other the icons, so the same look needs opposite values.
- **Do:** Over a full-bleed map or photo under a transparent bar, set icon brightness per screen from the content behind it, or add a 24-48px top gradient scrim.
- **Do:** Lock orientation only when the layout truly cannot adapt, and dispose controllers, listeners and subscriptions when screens close.
- **Avoid:** Hard-coded dark status-bar icons in both themes, or listeners left running after a screen is gone.

## ENG-13. Test the flows users depend on

**Why:** Automated flow tests catch regressions in the screens people use most.

- **Do:** Write integration or end-to-end tests that launch the app, walk the main paths (browse, detail, checkout; sign in, verify) and assert visible text and states.
- **Do:** Cover the failure path (wrong code, declined payment) as well as success.
- **Avoid:** Relying only on manual tapping in a simulator.
