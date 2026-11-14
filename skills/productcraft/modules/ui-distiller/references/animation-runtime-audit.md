# UI Distiller: Animation runtime audit

Read this when a page with a lot of motion feels janky, makes laptops hot or slows down the longer it stays open, when a marquee, skeleton, canvas, WebGL scene or physics effect keeps working while nobody can see it, or when a performance budget (Core Web Vitals) must be met without deleting the motion. Choosing and building motion is [motion-engineering.md](motion-engineering.md); general profiling and Web Vitals measurement are `../../engineering-practices/references/performance.md`; heavy 3D scenes are in `../../creative-media/GUIDE.md`.

The goal is not to remove motion. It is to make offscreen work stop, visible motion resume correctly, and every resource be released when its component leaves.

## Budgets

| Metric | Good at the 75th percentile | Motion-related causes |
|---|---|---|
| Largest Contentful Paint | 2.5 s or less | Hero video or canvas delaying the main image; entrance animations that hide the LCP element at opacity 0 until script runs |
| Interaction to Next Paint | 200 ms or less | Long tasks from animation setup, scroll handlers doing layout, heavy React re-renders per frame |
| Cumulative Layout Shift | 0.1 or less | Animating `height`, `top` or `margin`; content injected above existing content; skeletons not matching final size |

Measure on a mid-range profile: DevTools CPU throttling 4x, a slow 4G network preset, and one real mid-range phone when possible. Animations themselves should hold 60 frames per second (16.7 ms per frame) on that profile, or the display's rate where higher.

## 1. Inventory the motion sources

Search the code before profiling:

```bash
rg -n "requestAnimationFrame|setInterval|setTimeout|IntersectionObserver|ResizeObserver|MutationObserver|addEventListener\(|@keyframes|animation:|will-change|getContext\(|WebGLRenderer|gsap\.|ScrollTrigger|<video" src/
```

For each source note: owner component, what drives it (CSS, script loop, library timeline, video), whether it can be seen at all times, and how it is cleaned up. Effects that set up listeners, observers, loops, timers or media and have no matching cleanup are leak candidates.

## 2. Baseline in the browser

Profile the exact route at the top, middle and bottom of the page and at one phone width. In the console, list CSS animations that are running and whether their element is on screen:

```js
// paste in DevTools on the page under test
(() => {
  const vh = innerHeight, rows = [];
  for (const a of document.getAnimations()) {
    const el = a.effect?.target; if (!el) continue;
    const r = el.getBoundingClientRect();
    const onscreen = r.bottom > 0 && r.top < vh && r.width > 0 && r.height > 0;
    rows.push({ name: a.animationName || a.constructor.name, state: a.playState, onscreen,
                el: el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(" ")[0] : ""),
                pseudo: a.effect.pseudoElement || "" });
  }
  console.table(rows);
  return { running: rows.filter(r => r.state === "running").length,
           offscreenRunning: rows.filter(r => r.state === "running" && !r.onscreen).length };
})();
```

`document.getAnimations()` includes CSS animations, transitions and Web Animations, including pseudo-elements; it does not see `requestAnimationFrame` loops, canvas or WebGL rendering. For those, record a Performance panel trace while scrolled away from them and look for recurring "Animation frame fired" tasks and GPU activity.

For long-session slowdowns also record: DOM node count (`document.getElementsByTagName("*").length`), canvas, image, video and iframe counts, the JS heap where the browser exposes it, after idling 30 seconds and after navigating away and back five times. Counts that climb after each round trip point at leaks. If heap figures are unavailable, say so rather than claiming there is no leak.

## 3. Stop what cannot be seen

**CSS animations:** toggle a class from an IntersectionObserver and pause by rule.

```js
const io = new IntersectionObserver((entries) => {
  for (const e of entries) e.target.classList.toggle("is-offscreen", !e.isIntersecting);
}, { rootMargin: "100px 0px", threshold: 0 });
document.querySelectorAll("[data-animated]").forEach((el) => io.observe(el));
```

```css
.is-offscreen, .is-offscreen *, .is-offscreen *::before, .is-offscreen *::after {
  animation-play-state: paused !important;
}
```

Observe the section and the animated children of long sections; an ancestor that is partly visible keeps its offscreen children running otherwise. Do not pause visible hero motion with an over-broad selector.

**Script loops (canvas, WebGL, physics):** `animation-play-state` does nothing for them. Gate the loop itself:

```js
function createLoop(canvas, draw) {
  let raf = 0, last = 0, visible = false, disposed = false;
  const frame = (t) => {
    const dt = Math.min((t - last) / 1000, 1 / 30);   // cap the step after a pause
    last = t; draw(dt);
    if (visible && !disposed) raf = requestAnimationFrame(frame);
  };
  const io = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting && document.visibilityState === "visible";
    cancelAnimationFrame(raf);
    if (visible && !disposed) { last = performance.now(); raf = requestAnimationFrame(frame); }
    canvas.dataset.animationActive = String(visible);   // lets tests verify the gate
  });
  io.observe(canvas);
  const onVis = () => io.unobserve(canvas) || io.observe(canvas);   // re-evaluate on tab switch
  document.addEventListener("visibilitychange", onVis);
  return () => { disposed = true; cancelAnimationFrame(raf); io.disconnect(); document.removeEventListener("visibilitychange", onVis); };
}
```

Browsers already throttle `requestAnimationFrame` in background tabs, but not for an offscreen element in a visible tab. Cap the time step so physics does not jump after a pause.

**Marquees, tickers, skeleton shimmer, autoplaying video:** pause when offscreen; pause video with `video.pause()` and resume on entry; keep skeleton shimmer under about 1.5 s per cycle and remove it as soon as content arrives.

**Library timelines:** pause or kill scroll-driven and looping timelines whose trigger area is far away; libraries with scroll triggers usually expose enable and disable methods per trigger.

## 4. Release everything on teardown

Every effect that creates something returns a cleanup that undoes it:

- cancel animation frames and clear every timeout and interval;
- disconnect intersection, resize and mutation observers;
- remove window and document listeners with the same function reference used to add them;
- kill library tweens and timelines, including those animating plain objects such as shader uniforms;
- for WebGL: dispose geometries, materials, textures and render targets, call the renderer's dispose and force-context-loss methods, and remove its canvas;
- stop media streams' tracks and pause detached audio and video;
- guard async loaders with a disposed flag and dispose results that arrive after unmount.

In React, copy `ref.current` into a local variable inside the effect and use that in the cleanup; the ref may point elsewhere by cleanup time.

## 5. Make visible motion cheap

- Animate `transform` and `opacity` only; for size changes use FLIP or the grid-row technique ([motion-engineering.md](motion-engineering.md)). Animating `filter: blur()`, `box-shadow` or `backdrop-filter` over large areas costs paint on every frame; fade a pre-blurred layer instead.
- `will-change` only on elements about to animate, removed afterwards; never on many elements at once.
- Scroll effects: prefer CSS scroll-driven animations (`animation-timeline: view()`) or IntersectionObserver over scroll listeners; when a listener is required, make it passive and read layout once per frame.
- Canvas and WebGL: cap device pixel ratio at 2 (1.5 on phones), reduce particle counts on small screens, and render a static fallback image first so LCP never waits for a shader to compile.
- Entrance animations never hide the LCP element: render it visible and animate secondary elements.
- Load animation libraries only on routes that use them, and import only the parts used.
- Reduced motion: under `prefers-reduced-motion: reduce`, replace movement with instant changes or short fades, stop loops and parallax, and do not start canvas loops at all (show the still).

## 6. Verify

Repeat the same profiles after the change:

- `offscreenRunning` is 0 at the top, middle and bottom of the page; visible animations still run and resume on scroll-back.
- Canvas loops report `data-animation-active="false"` when offscreen (assert it in a Playwright test after scrolling).
- Node, canvas and media counts return to their baseline after five route round trips and a 30-second idle.
- Web Vitals in the lab meet the budget on the throttled profile; field data confirms within the next measurement window.
- The page's normal interactions (filters, search, navigation) still work; the console is clean on a fresh tab.

Report what was running before and after, per section, with the route and viewport; separate measured facts from risks found by reading code.

## Pitfalls

- Deleting animations to make a profile pass.
- Trusting one measurement at the top of a long page.
- Assuming CSS pausing covers script loops or pseudo-elements it did not select.
- Unbounded stress loops that crash the tab and are then blamed on the wrong component.
- Screenshots offered as performance evidence.

## Done when

- [ ] Every motion source is inventoried with its owner and cleanup.
- [ ] Offscreen CSS animations and script loops are paused, visible ones resume, and reduced motion stops loops.
- [ ] Teardown releases loops, timers, observers, listeners, timelines, media and GPU resources; route round trips return to baseline counts.
- [ ] Visible motion uses compositor-friendly properties and never delays the LCP element.
- [ ] Before and after figures (offscreen counts, Web Vitals on the throttled profile, node counts) are reported with routes and viewports.
