# HTML slide decks without a framework

Read this to build a presentation as a self-contained HTML file: a deck to email or host as one file, slides generated from content by a script, a talk with custom interactive pieces, or a `.pptx` rebuilt for the web. For reveal.js decks use `revealjs-presentations.md`; for a `.pptx` that others will edit, `../../documents/references/powerpoint-pptx.md`; colors and fonts come from `themes-and-brand-application.md`. Browser features cited are supported in current engines as of 2025.

Contents: choose the approach · pick one layout model · a minimal deck · content and type · choosing a look · builds and motion · speaker notes · fonts and assets · converting a pptx · PDF export · checks · done when.

## Choose the approach

| Situation | Use |
|---|---|
| One file, no dependencies, full control of design and interaction | A hand-built deck (this file) |
| Speaker view, plugins, mature PDF export, a team that knows it | reveal.js (`revealjs-presentations.md`) |
| Writing speed matters most; slides from Markdown | A Markdown deck tool such as Marp or Slidev |
| Colleagues will edit in an office suite, or the venue requires it | `.pptx` |

## Pick one layout model

**Fixed canvas, scaled to fit (recommended for talks).** Design every slide on a 1920 × 1080 canvas in pixels and scale the whole canvas to the window, letterboxing the rest. The layout is identical on every screen and PDF pages come out exact.

**Fluid slides.** Each slide is `100dvh` tall with type set by `clamp()`. Better for decks read on phones, but nothing guarantees content fits; you must check overflow at several window sizes and split slides that overflow.

Do not mix them in one deck.

## A minimal deck (fixed canvas)

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Safer database migrations</title>
<style>
  :root { --bg: #F7F6F2; --text: #1C1F22; --accent: #0F766E; --body: 40px; }
  html, body { margin: 0; height: 100%; background: #111; overflow: hidden; }
  .stage { position: absolute; left: 50%; top: 50%; width: 1920px; height: 1080px; transform-origin: center; }
  .slide { position: absolute; inset: 0; box-sizing: border-box; padding: 96px 120px; background: var(--bg);
           color: var(--text); font: var(--body)/1.35 "Source Sans 3", system-ui, sans-serif; }
  .slide[hidden] { display: none; }
  h1 { font-size: 96px; line-height: 1.05; margin: 0 0 32px; } h2 { font-size: 64px; margin: 0 0 40px; }
  .notes { display: none; }
  @media print {
    @page { size: 1920px 1080px; margin: 0; }
    html, body { overflow: visible; background: none; height: auto; }
    .stage { position: static; transform: none !important; }
    .slide, .slide[hidden] { display: block; position: relative; height: 1080px; break-after: page; }
    .live { display: none; }
  }
</style>
</head>
<body>
<main class="stage" aria-roledescription="presentation">
  <section class="slide" aria-roledescription="slide" aria-label="Safer database migrations">
    <h1>Safer database migrations</h1><p>Platform team, 12 March 2026</p>
    <aside class="notes">Open with the May outage.</aside>
  </section>
  <section class="slide" aria-roledescription="slide" aria-label="Two releases, not one" hidden>
    <h2>Two releases, not one</h2><p>Add the column in release 1; drop the old one in release 2.</p>
  </section>
</main>
<p class="live" aria-live="polite" style="position:absolute;left:-9999px"></p>
<script>
  const slides = [...document.querySelectorAll(".slide")], stage = document.querySelector(".stage");
  const live = document.querySelector(".live");
  let current = 0;
  function fit() {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    stage.style.transform = `translate(-50%, -50%) scale(${s})`;
  }
  function show(i, announce = true) {
    current = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach((el, n) => { el.hidden = n !== current; el.inert = n !== current; });
    history.replaceState(null, "", `#${current + 1}`);
    if (announce) live.textContent = `Slide ${current + 1} of ${slides.length}: ${slides[current].getAttribute("aria-label")}`;
  }
  addEventListener("keydown", (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.target.closest("input, textarea, select, [contenteditable]")) return;
    if (["ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); show(current + 1); }
    if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); show(current - 1); }
    if (e.key === "Home") show(0);
    if (e.key === "End") show(slides.length - 1);
    if (e.key === "f") document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
  });
  let x0 = null;
  addEventListener("pointerdown", (e) => { x0 = e.clientX; });
  addEventListener("pointerup", (e) => {
    if (x0 !== null && Math.abs(e.clientX - x0) > 60) show(current + (e.clientX < x0 ? 1 : -1));
    x0 = null;
  });
  addEventListener("resize", fit);
  addEventListener("hashchange", () => show(parseInt(location.hash.slice(1), 10) - 1 || 0));
  fit(); show((parseInt(location.hash.slice(1), 10) || 1) - 1, false);
</script>
</body>
</html>
```

- **Hash routing** (`#7`) keeps the position on reload and makes slides linkable.
- **Inactive slides are `hidden` and `inert`,** so keyboard focus and screen readers stay on the current slide (`ENG-05`); a polite live region announces each change with the slide's title.
- **No wheel navigation by default:** trackpads send bursts of wheel events and skip slides. If you add it, accept one step per gesture.
- **Swipe** uses pointer events with a distance threshold, so taps on links and buttons inside slides still work.

## Content and type

- One idea per slide, stated in the title; detail goes in the speaker notes.
- On a 1920 × 1080 canvas, body text of 36-40 px is the floor and titles around 64-96 px (`revealjs-presentations.md` explains the point conversion). When content does not fit, split the slide; never shrink type below the floor.
- Code: about 12 lines at a readable size, with the line under discussion highlighted.
- Charts built from data with code (`infographics.md`), each with a one-line takeaway as its title.

## Choosing a look

When the user has no theme, make two or three single-slide previews, each a different direction from `../../ui-distiller/references/style-catalog.md`, using the real title and one real content slide. Let the user choose or combine, then build the theme as custom properties (`themes-and-brand-application.md`). Run the taste detectors in `../../ui-distiller/references/taste.md` on the result; generic gradient decks are the most common failure.

## Builds and motion

- Builds (items appearing one at a time) as elements with `data-step="1"`, `"2"`; the controller reveals the next step before moving to the next slide. Builds help when the order of ideas matters; otherwise show the whole slide.
- Animate entries on slide change with class toggles and CSS transitions (opacity and a small translate, `MOT-02`), not scroll observers; slides do not scroll.
- Under `prefers-reduced-motion: reduce`, show slides and steps instantly (`MOT-04`). Nothing advances automatically without a pause control (`MOT-19`).

## Speaker notes

Keep notes in `<aside class="notes">` inside each slide. For a presenter view, open a second window (`window.open("notes.html")`) that shows the current notes, the next slide's title and a timer, and keep the two windows in step with a `BroadcastChannel`. Serve the folder over HTTP while presenting (`python3 -m http.server`), because windows opened from `file://` pages may not share a channel.

## Fonts and assets

- Self-host fonts as WOFF2; for a true single file, embed them as `data:` URLs in `@font-face`. Record font licenses (OFL and others) in `credits.md`.
- Images: inline small ones as `data:` URLs, or ship an `assets/` folder next to the HTML. Give every meaningful image alt text.
- No CDN links in the delivered file: venue networks fail.

## Converting a pptx

Extract content, then rebuild the design; slide layouts do not convert faithfully.

```python
from pptx import Presentation                      # python-pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE

def walk(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from walk(sh.shapes)
        else:
            yield sh

prs = Presentation("talk.pptx")
for n, slide in enumerate(prs.slides, 1):
    texts, images = [], []
    for sh in walk(slide.shapes):
        if sh.has_text_frame and sh.text_frame.text.strip():
            texts.append(sh.text_frame.text)
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            name = f"assets/s{n:02d}-{len(images) + 1}.{sh.image.ext}"
            open(name, "wb").write(sh.image.blob); images.append(name)
    notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
    print(n, texts, images, notes[:60])
```

Charts become images or lose their data, so rebuild them from the source data; SmartArt and animations do not survive; check embedded fonts and their licenses. Keep slide order and notes, then apply the chosen theme.

## PDF export

The print stylesheet above lays out every slide as one 1920 × 1080 page, with all build steps visible and controls hidden. Render it with a headless browser:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://127.0.0.1:8000/deck.html")
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.pdf(path="deck.pdf", prefer_css_page_size=True, print_background=True)
```

Check the result with `pdffonts deck.pdf` (fonts embedded) and by viewing every page. Exporting screenshots as pages also works but makes larger files whose text cannot be selected or searched; use it only when the browser's PDF output cannot reproduce an effect.

## Checks

1. **Overflow:** for each slide, compare every element's bounding box with the slide's box and list the ones that stick out; for fluid decks, repeat at 1920×1080, 1280×720, 1024×768, 390×844 and 844×390.
2. **Screenshot every slide** at presentation size and look at each one (`../../builder-tools/references/playwright-web-testing.md`).
3. **Keyboard only:** next, previous, Home, End, fullscreen; focus never lands on a hidden slide.
4. **Screen reader:** slide changes are announced with titles; images have alt text.
5. **Offline:** load the deck from a local server while aborting every request to any other host (a Playwright `page.route` handler), and confirm fonts and images still load.
6. **Contrast** of every text pair in the theme (`COL-01`); reduced motion honored.
7. **PDF** page count equals slide count, fonts embedded, nothing clipped.

## Done when

- The deck is one HTML file (or the file plus `assets/`) that runs offline, with one layout model.
- No slide overflows at its target sizes; every slide was viewed as a screenshot.
- Keyboard, screen-reader announcement, reduced motion and contrast checks pass.
- The PDF matches the slides, and credits list fonts and images.
