# UI Distiller: Scroll and reveal effects

Read this when a page needs motion tied to scrolling: elements that appear as they enter, headlines that rise word by word, a progress rail through ordered steps, a pinned stage that scrubs a video or drawing, a long-form story page, a looping logo strip, or pointer-follow details on a marketing surface. The values and the when-to-animate rules live in `../../../references/ui-rules/motion.md` (budget `MOT-02`, reduced motion `MOT-04`, stagger `MOT-06`, scroll `MOT-16`, pausing `MOT-19`, split text `MOT-20`). Tool choice, tokens and choreography are in [motion-engineering.md](motion-engineering.md). This file covers the scroll-specific patterns those two do not. Browser support is as of late 2025; feature-detect before relying on it.

## First decide which kind of scroll motion it is

| Kind | What drives it | Reverses with scroll? | Use for | Default tool |
|---|---|---|---|---|
| **Triggered** | Crossing a line once | No, it plays once | Section entrances, headline reveals, counters | IntersectionObserver plus CSS, or `animation-timeline: view()` |
| **Scrubbed** | Scroll position, continuously | Yes, exactly | Reading-progress reveals, progress rails, parallax | CSS scroll-driven animations; JS progress for older engines |
| **Pinned** | Scroll position while a stage stays put | Yes | Product walkthroughs, video or frame sequences, card stacks | `position: sticky` in a tall section; GSAP ScrollTrigger for complex timelines |
| **Ambient loop** | Time | n/a | Logo strips, tickers | CSS keyframes with a pause control |

Most pages need one triggered entrance pattern and at most one scrubbed or pinned moment. A page where every section fades up is a generic tell (`MOT-06`, taste detector in [taste.md](taste.md)); a page with three pinned scenes feels like a trap.

## The contract every pattern keeps

1. **Readable without script.** The hidden start state is added only once script runs and motion is allowed. Gate it on a class set in the document head, never on the default stylesheet.
2. **Native scrolling.** Never change wheel speed or direction, never block keyboard, find-in-page or anchor jumps. Smooth-scroll libraries are an opt-in enhancement (see "Smoothed scrolling" below).
3. **Deterministic.** For scrubbed and pinned work, one normalized progress value (0 to 1) from scroll position is the only source of truth. Never timers, wheel deltas or autoplay.
4. **Reduced motion opts in to nothing.** Under `prefers-reduced-motion: reduce` content is visible, unpinned, in normal flow, and state changes (active step, final frame) still show (`MOT-04`).
5. **Cleaned up.** Observers, listeners, frames and timelines are released on route change.

```html
<script>
  // In <head>, before first paint: enable hidden start states only when motion is welcome.
  if (matchMedia("(prefers-reduced-motion: no-preference)").matches)
    document.documentElement.classList.add("motion-ok");
</script>
```

## Triggered entrances

**Defaults:** 12-24px rise (or 0.97-1 scale) plus opacity, 450-700ms, ease-out such as `cubic-bezier(0.2, 0.8, 0.2, 1)`, siblings 50-80ms apart, first four to six items only. Trigger when about 15-25% of the element is visible, with the root margin pulled up 5-10% so it fires slightly before the element reaches mid-screen. Play once. A light blur (4-8px to 0) adds softness on headlines and small cards only; never blur large images or full sections (`MOT-01`).

```css
.motion-ok [data-enter] { opacity: 0; translate: 0 18px; }
.motion-ok [data-enter].is-in {
  opacity: 1; translate: 0 0;
  transition: opacity 560ms var(--ease-out), translate 560ms var(--ease-out);
  transition-delay: calc(var(--i, 0) * 60ms);
}
```

```js
export function observeEntrances(root = document) {
  if (!document.documentElement.classList.contains("motion-ok")) return () => {};
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); }
  }, { threshold: 0.2, rootMargin: "0px 0px -8% 0px" });
  root.querySelectorAll("[data-enter]").forEach((el) => io.observe(el));
  return () => io.disconnect();
}
```

- Elements already in view at load must still reveal: IntersectionObserver reports the initial state on `observe()`, so this works only if the observer is created after the elements exist. In a framework, observe in the mount effect, not at module load.
- **CSS-only alternative** where supported (Chromium 115+, Safari 26+; Firefox behind a flag): `animation: enter linear both; animation-timeline: view(); animation-range: entry 10% cover 30%;` inside `@supports (animation-timeline: view())`. Because it is scrubbed it also reverses; use it where that is acceptable, and the observer where the design wants "once".
- Tailwind users put the start state in arbitrary utilities (`motion-safe:opacity-0`) and toggle a data attribute; keep the duration tokens in the theme, not scattered arbitrary values.

## Word-by-word headline reveals

Three variants, from calmest to most theatrical. All split only short display text (one to three lines), keep the full sentence for assistive technology and never split text that contains links or buttons unless the splitter preserves them (`MOT-20`).

| Variant | Look | Numbers |
|---|---|---|
| **Fade and rise** | Each word fades up from slightly below | 16-20px, 700-800ms, 50-80ms per word, strong ease-out such as `cubic-bezier(0.16, 1, 0.3, 1)` |
| **Masked rise** | Words slide up from behind an invisible line, as if printed into place | Each word inside an `overflow: clip` wrapper, start at `translate: 0 105%`, 650-900ms, 25-45ms per word |
| **Scrubbed reading** | Words brighten as the reader scrolls past, pacing a statement | Dim state opacity 0.15-0.3, reveal span 1.2-2.2 viewport heights per paragraph, no easing on the mapping |

Splitter that keeps inline markup intact (emphasis, links, accent spans stay real elements), so it also suits paragraphs for the scrubbed variant:

```js
export function splitWords(container) {
  const original = container.cloneNode(true);          // keep for cleanup
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => n.parentElement.closest("[data-no-split], script, style, button, input")
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  const texts = []; while (walker.nextNode()) texts.push(walker.currentNode);
  let i = 0;
  for (const node of texts) {
    const frag = document.createDocumentFragment();
    for (const part of node.data.split(/(\s+)/)) {
      if (!part) continue;
      if (/^\s+$/.test(part)) { frag.append(part); continue; }
      const w = document.createElement("span");
      w.className = "w"; w.style.setProperty("--i", i++); w.textContent = part;
      frag.append(w);
    }
    node.replaceWith(frag);
  }
  container.style.setProperty("--n", i);
  return () => container.replaceWith(original);
}
```

Because the words stay inside the original elements and are not hidden from assistive technology, the sentence still reads normally; no `aria-label` copy is needed, which also avoids the label and the visible text drifting apart. For the masked variant wrap each `.w` in a second span with `display: inline-block; overflow: clip; padding-block: 0.1em` so descenders are not cut.

**Scrubbed reading without per-word script:** script writes one number per frame on the container; CSS works out every word.

```css
.reading .w { opacity: clamp(var(--dim, 0.2), calc(var(--p, 1) * var(--n) - var(--i)), 1); }
/* word i reaches full opacity when p = (i + 1) / n; the last word exactly at p = 1 */
```

```js
const box = el.getBoundingClientRect();     // inside one rAF per scroll event
const p = Math.min(1, Math.max(0, (innerHeight * 0.85 - box.top) / (box.height + innerHeight * 0.6)));
el.style.setProperty("--p", p.toFixed(4));
```

Default `--p` is 1, so without script every word is fully visible. The final state must meet normal text contrast; only the dim state may be quieter. Initialize after `document.fonts.ready` when line breaks matter to the composition.

## Progress rails through ordered steps

For onboarding explainers, roadmaps, case-study timelines and "how it works" sections. Build the ordered list with real headings first; the rail decorates it.

- One quiet base line plus one fill line on top, scaled with `transform: scaleY(p)` from `transform-origin: top` (or `scaleX` from the left for horizontal rails).
- Measure from the center of the first marker to the center of the last, not section edges, so the fill head and the active marker agree at every boundary.
- A step becomes active when the fill head passes its marker. Expose it with `aria-current="step"` only if the current step means something to the user; never announce progress through a live region.
- Layout: a left rail for long or uneven content (the safe default and the mobile form); centered alternating only on wide screens with balanced content; horizontal only for four to six short labels with keyboard-reachable overflow.
- If markers jump to steps, they are real links with `scroll-margin-top` equal to any sticky header height.
- Reduced motion: show reached steps discretely (fill snaps to the active marker) without interpolation.

## Pinned stages and scrubbed sequences

A tall section (`height: calc(var(--scroll-vh) * 1svh)`) holds a `position: sticky; top: 0; height: 100svh` stage. Progress is:

```js
const r = section.getBoundingClientRect();
const p = Math.min(1, Math.max(0, -r.top / (r.height - innerHeight)));
```

| Renderer | Choose when | Key practice |
|---|---|---|
| **Video** | Photographic or pre-rendered camera moves | Encode for seeking: no audio, keyframe every 1-6 frames (`ffmpeg -an -c:v libx264 -crf 20 -g 4 -movflags +faststart`); fetch to a Blob URL or serve with byte ranges; write `currentTime` at most once per frame; poster until the first frame paints |
| **Image sequence** | Exact art-directed frames (product assembly, rotation) | 60-150 WebP or AVIF frames; load the current and neighbouring frames first; decode with `createImageBitmap`; draw to a canvas sized with DPR capped at 2; never block first paint on the whole set |
| **Canvas or SVG drawing** | Diagrams, line drawings, charts | Redraw only when progress changes; SVG stroke reveals via `stroke-dashoffset` |
| **DOM states** | Interface walkthroughs, feature callouts | Drive custom properties, transforms, opacity and `clip-path`; keep copy as real text |
| **Real-time 3D** | Only when depth or a camera move is the idea | See [webgl-backgrounds-and-3d.md](../../creative-media/references/webgl-backgrounds-and-3d.md) |

- 200-400 viewport heights is plenty for one sequence; past that people feel stuck. Offer a skip link to the next section (`MOT-16`).
- Copy that explains each state sits in a separate layer and appears at named progress stops (for example 0, 0.4, 0.75), never baked into frames.
- Mobile: shorten the scroll distance, or replace the pin with stacked stills and captions below about 768px.
- Reduced motion: no pin; show the chosen poster or the key frames in flow with their captions.

**Sticky card stack** (projects or features that pile up): each card is `position: sticky` with `top: calc(10vh + var(--i) * 12px)`; earlier cards scale toward 0.92-0.96 and dim slightly as the next arrives. Use a scroll-driven animation on each card where supported, and leave the plain sticky pile as the fallback; it already works. Keep the last card released before the footer.

**Horizontal gallery on vertical scroll:** pin the section and translate the track by `-(trackWidth - viewportWidth) * p`. Keyboard and touch users must still reach every item: provide prev and next buttons or let the track scroll natively below the pin breakpoint.

## Long-form story pages

When an article, case study or launch narrative becomes one scrolling journey:

1. **Reduce the story to five to seven beats:** hook, problem, idea, mechanism, proof, outcome, one action. Write a ledger first: id, what the visual shows, a 3-8 word headline, one sentence of body, the exact fact or asset that proves it, one motion verb, scroll weight (0.7-1.8 viewports).
2. **Pick one renderer for the whole page:** pre-rendered video for cinematic places and products, real-time 3D for spatial systems the user may explore, or DOM, SVG and type for metrics and reports (the most accessible and lightest; prefer it when the story is mostly proof).
3. **Write a one-page style brief:** three mood words, one world metaphor, four to six colors with one accent, one display and one reading face, one material language, one motion grammar (glide, orbit, crane, lateral track), three clichés to avoid. Generated footage or stills follow [generation-prompting.md](../../creative-media/references/generation-prompting.md), including its likeness and labelling rules; pre-rendered shots follow [directed-motion.md](../../creative-media/references/directed-motion.md).
4. **Keep the facts honest:** every number traces to the source; no invented testimonials or metrics; charts keep truthful scales with values available as text.
5. **One primary call to action,** in the last beat, reachable without scrolling the whole story (also linked from the header).

A preloader is justified only when the first beat cannot render without a heavy asset. Show real progress, cap it near 1.5s, and reveal content as soon as it is usable; never invent a loading screen for atmosphere (`MOT-17`).

## Smoothed scrolling and GSAP

Smooth-scroll libraries such as Lenis interpolate the scroll position for a weighted feel. They add input latency and can fight assistive tools, so use them only on brand-led pages, never in apps, and never under reduced motion. Keep native scrollbars, anchors and keyboard paging working.

GSAP with ScrollTrigger is worth adding when the page has several pinned timelines, labelled scenes or needs exact refresh coordination. Since 3.13 (2025) all GSAP plugins, SplitText included, are free; its license is not an OSI open-source license, so read the standard terms before shipping. Setup that keeps both in step and respects motion preferences:

```js
gsap.registerPlugin(ScrollTrigger);
const mm = gsap.matchMedia();
mm.add({ ok: "(prefers-reduced-motion: no-preference)", wide: "(min-width: 900px)" }, ({ conditions }) => {
  if (!conditions.ok) return;                          // everything stays in its end state
  const lenis = new Lenis({ lerp: 0.12 });             // optional
  const raf = (t) => lenis.raf(t * 1000);
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add(raf); gsap.ticker.lagSmoothing(0);
  if (conditions.wide) buildPinnedScenes();            // pins only on wide screens
  buildEntrances();
  return () => { gsap.ticker.remove(raf); lenis.destroy(); };   // runs when a query stops matching
});
```

- Scrubbed tweens use `ease: "none"`; smoothing comes from `scrub: 0.6-1.2` (seconds of catch-up), not easing. Eased tweens belong to triggered reveals inside the scene.
- Name scenes with timeline labels so they can be retimed in one place.
- Call `ScrollTrigger.refresh()` after fonts, images and late content change heights. In React use the official `useGSAP` hook (or `gsap.context()` and `revert()` in the effect cleanup) so triggers die with the component.
- Do not animate layout properties in scrubbed scenes; transforms, opacity and `clip-path` only.

## Looping strips (logos, tags, quotes)

- Render the list once for assistive technology, then a visual track holding two copies; the second copy gets `aria-hidden="true"` and `inert` so links are not focused twice.
- Animate the track `translate: 0 0` to `translate: -50% 0` with `linear infinite`. Set the duration from content width so speed stays constant: about 40-80px per second (`duration = halfTrackWidth / speed`).
- Give items fixed sizes so the loop never jumps when images load; fade the edges with a mask ([css-craft-techniques.md](css-craft-techniques.md)).
- A visible pause button is required when it runs longer than five seconds next to other content (`MOT-19`, WCAG 2.2.2); also pause on hover and `:focus-within`.
- Reduced motion: no loop; show a static wrapped row or a scroll-snap row.
- Never put content people must read carefully (prices, quotes they need to finish) in a moving strip.

## Pointer details on marketing pages

Magnetic buttons, cursor followers and layered pointer parallax are decoration; they obey `MOT-18` (fine pointers only, one rAF loop that stops when settled, off under reduced motion).

- **Magnetic control:** move an inner span, not the button, by at most 6-10px (about 0.15-0.25 of the pointer offset); the hit area stays still. Release over 300-450ms.
- **Pointer parallax layers:** depth factors 0.01-0.04 of the pointer offset, eased about 0.08-0.12 per frame. Text layers stay still.
- **Custom cursor:** rarely worth it. If used, keep the native cursor visible or use the follower only as a label over media ("View"), hide it on coarse pointers, and never let it hide the focus ring or the real target.
- **Spotlight reveals** (a second image under a soft radial mask that follows the pointer) are in [css-craft-techniques.md](css-craft-techniques.md); shader distortions and cursor trails are in [webgl-backgrounds-and-3d.md](../../creative-media/references/webgl-backgrounds-and-3d.md).

## Performance

- One scroll listener (passive) that schedules one `requestAnimationFrame` write pass; read geometry once per frame, then write. Prefer CSS scroll-driven animations, which run off the main thread.
- Cache section offsets and re-measure only on resize, font load and content change (`ResizeObserver`), not on every scroll.
- `will-change` only on elements animating now; never on every split word.
- Profile a pinned scene with 4x CPU throttling; scroll should show no Layout or Paint inside frames ([motion-engineering.md](motion-engineering.md)).
- Video and image sequences: measure transferred bytes; a scrubbed hero over about 8 MB on mobile needs a lighter variant.

## Pitfalls

- Content hidden by the default stylesheet, so a script error or slow bundle leaves a blank page.
- Reveals that replay on every pass, or fire on tiny scroll jitters near the threshold.
- Splitting with `innerHTML` and losing links, or exposing hundreds of word spans to screen readers.
- Pins that overlap the next section after late images load (missing refresh), or stretch past 400 viewport heights.
- Progress computed from section edges, so the rail head and the active step disagree.
- Smooth scrolling under reduced motion, or in an application screen.
- Duplicated marquee items reachable by keyboard twice.

## Done when

- [ ] The page reads completely with script disabled and with reduced motion on; no pins, loops or interpolation remain in that mode, but active states still show.
- [ ] Each triggered reveal plays once, starts slightly before mid-screen and finishes within the `MOT-02` budget.
- [ ] Scrubbed and pinned scenes reproduce the same state for the same scroll position, forward, backward and after a fast flick.
- [ ] Split text keeps its links, emphasis and natural screen-reader output; final text contrast passes.
- [ ] Rails, pins and strips work at 390, 768, 1024 and 1440px widths and at 200% zoom.
- [ ] Every loop running longer than five seconds has a pause control.
- [ ] Observers, triggers, smooth-scroll instances and frames are released on route change; a throttled profile shows no layout work during scroll.
