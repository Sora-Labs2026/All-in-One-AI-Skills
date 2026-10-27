# Presentations with reveal.js

Read this to build a talk as an HTML presentation with reveal.js: a conference or meetup talk, a lecture, a code walkthrough, a deck that lives in a repository, or slides that must run in a browser. Examples use reveal.js 5.x (5.1 and later, 2024-2026). For a `.pptx` the recipient will edit in PowerPoint, use `../../documents/references/powerpoint-pptx.md` instead. Colors and fonts come from `themes-and-brand-application.md`.

Contents: when reveal.js fits · a minimal deck · canvas size and type · writing the slides · code, math and charts · motion · speaker notes and presenting · PDF export · checks · accessibility · done when.

## When reveal.js fits

Choose reveal.js when the talk benefits from the web: live code highlighting, embedded demos or iframes, math, version control and review in pull requests, or hosting as a page. Choose a `.pptx` when colleagues will edit it in an office suite, when the venue requires PowerPoint, or when the user's organization has a PowerPoint template. Either way, offer a PDF for handouts and as a fallback.

## A minimal deck

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shipping safer migrations</title>
  <link rel="stylesheet" href="vendor/reveal.js/dist/reset.css">
  <link rel="stylesheet" href="vendor/reveal.js/dist/reveal.css">
  <link rel="stylesheet" href="vendor/reveal.js/dist/theme/white.css">
  <link rel="stylesheet" href="vendor/reveal.js/plugin/highlight/monokai.css">
  <link rel="stylesheet" href="theme.css">   <!-- your variables, loaded after the base theme -->
</head>
<body>
  <div class="reveal"><div class="slides">
    <section><h1>Shipping safer migrations</h1><p>Platform team · 12 March 2026</p></section>
    <section>
      <h2>Two releases, not one</h2>
      <p>Add the column in release 1; drop the old one in release 2.</p>
      <aside class="notes">Mention the outage in May as the reason we adopted this.</aside>
    </section>
  </div></div>
  <script src="vendor/reveal.js/dist/reveal.js"></script>
  <script src="vendor/reveal.js/plugin/notes/notes.js"></script>
  <script src="vendor/reveal.js/plugin/highlight/highlight.js"></script>
  <script>
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    Reveal.initialize({
      width: 1920, height: 1080, margin: 0.04, center: false,
      hash: true, slideNumber: "c/t", controls: true, progress: true,
      transition: reduce ? "none" : "fade", backgroundTransition: "none", autoAnimate: !reduce,
      plugins: [RevealNotes, RevealHighlight],
    });
  </script>
</body>
</html>
```

- **Vendor the library** (`npm install reveal.js@5` and copy `dist/` and `plugin/`, or download a release) and self-host fonts, so the talk works on venue Wi-Fi or none. If you use a CDN while drafting, pin the exact version (`https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js`) and never `@latest`; unpinned plugin and chart URLs are a common way a deck breaks the night before.
- Serve the folder over HTTP while working (`python3 -m http.server`). External Markdown slides, the speaker view and some plugins do not work from `file://`.
- Keep one HTML file, one `theme.css`, and an `assets/` folder for images with their credits.

## Canvas size and type

reveal.js lays out every slide on a fixed canvas (`width` x `height`, default 960 x 700) and scales it to the screen. Pick 1920 x 1080 (or 1280 x 720) for 16:9 projectors and design every size in pixels on that canvas.

- On a 1920 x 1080 canvas, 2 px corresponds to 1 pt on a standard 16:9 PowerPoint slide (13.33 x 7.5 in). So body text of 36 px or more (18 pt equivalent) is the floor; 44-56 px reads better in large rooms. Titles around 64-96 px.
- One type scale for the whole deck, set through the theme variables (`--r-main-font-size`, heading sizes) rather than per-slide overrides.
- Check the venue's projector resolution and aspect ratio. A 16:9 deck letterboxes on a 4:3 projector; make sure nothing important depends on the edges.

## Writing the slides

- **One point per slide**, stated as a sentence in the title ("Two releases, not one"), with the evidence below it. A topic word as a title ("Migrations") makes the audience work out the point.
- **Few words on screen.** The speaker carries the explanation; the slide carries what must be seen: a diagram, a number, a code fragment, a short list. If a slide needs a paragraph, it belongs in the notes or a handout.
- **Real text, not pictures of text.** Headings in heading elements, lists as lists, so search, translation, screen readers and the PDF export all work.
- **Vertical stacks** (`<section>` inside `<section>`) are optional detail the presenter may skip. Use them sparingly; audiences and presenters lose their place in two dimensions.
- **Layout with CSS grid** in a few named classes in `theme.css` (two columns, media and text, three stats). Reuse them instead of styling each slide by hand.
- **Images:** `class="r-stretch"` fills the remaining height; set `alt` on every meaningful image, `alt=""` on decorative ones; keep credits on the slide or in a credits slide.
- **Markdown slides** are fine for text-heavy decks (`<section data-markdown><textarea data-template>...</textarea></section>` with the Markdown plugin), but layouts and fragments are easier in HTML.

## Code, math and charts

- **Code:** the highlight plugin with `<pre><code class="language-sql" data-trim data-line-numbers="1-2|4">`. Step highlights (`|`) walk through code without extra slides. Escape `<`, `>` and `&` inside code blocks, or wrap the code in `<script type="text/template">`. Keep code at 28 px or larger on a 1920 canvas and under about 15 lines per slide.
- **Math:** the math plugin (KaTeX or MathJax). It loads its engine from a CDN by default; point it at a local copy for offline talks.
- **Charts:** a static SVG exported from your plotting code is the most reliable (`../../data-engineering/references/plotting.md`). For live charts, give the container a fixed height and create the chart when its slide is first shown, because reveal.js hides distant slides with `display: none` and a chart drawn into a hidden canvas gets zero size:

```js
const made = new WeakSet();
Reveal.on("slidechanged", ({ currentSlide }) => {
  currentSlide.querySelectorAll("canvas[data-chart]").forEach((el) => {
    if (made.has(el)) return;
    made.add(el);
    new Chart(el, { ...JSON.parse(el.dataset.chart), options: { responsive: true, maintainAspectRatio: false, animation: false } });
  });
});
```

Chart rules (zero baselines, direct labels, no dual axes) are in `../../data-and-product-surfaces.md`.

## Motion

- Default to no transition or a short fade. Slide, zoom and convex transitions and per-bullet fly-ins draw attention to the mechanics instead of the content.
- **Fragments** (`class="fragment"`) reveal items in order; use them when the order of an argument matters, not on every list.
- **Auto-animate** (`data-auto-animate` on consecutive slides, elements matched by `data-id`) is good for showing how a diagram or code changes between steps.
- Honor `prefers-reduced-motion` as in the minimal deck, and never flash content (`MOT-21` in `../../../references/ui-rules/motion.md`).

## Speaker notes and presenting

- Notes go in `<aside class="notes">` per slide. Press `S` for the speaker view (current and next slide, notes, timer); allow the pop-up and serve over HTTP.
- `?showNotes=separate-page` adds notes pages to a PDF export for rehearsal or for a speaker who presents from paper.
- Rehearse on the presenting machine at the projector resolution, with the browser in full screen (`F`), and confirm fonts, videos and demos work offline.
- Keep a PDF copy on a USB stick or in the cloud in case the laptop or browser fails.

## PDF export

reveal.js has a print mode: open the deck with `?print-pdf` in Chromium and print to PDF with no margins and background graphics on. Headless, with Playwright:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:8000/talk.html?print-pdf")
    page.wait_for_function("window.Reveal && Reveal.isReady()")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.pdf(path="out/talk.pdf", prefer_css_page_size=True, print_background=True)
    browser.close()
```

Set `pdfSeparateFragments: false` to export one page per slide instead of one per fragment step. Open the PDF and check page count against the slide count (`pdfinfo`).

## Checks

Measure every slide for overflow and capture a screenshot of each, then look at all of them (overflow is the most common defect in generated decks):

```python
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

Path("shots").mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://localhost:8000/talk.html")
    page.wait_for_function("window.Reveal && Reveal.isReady()")
    page.evaluate("Reveal.configure({ transition: 'none', backgroundTransition: 'none' })")
    total = page.evaluate("Reveal.getSlides().length")
    problems = []
    for i in range(total):
        info = page.evaluate("""(i) => {
          const slide = Reveal.getSlides()[i];
          const { h, v } = Reveal.getIndices(slide);
          Reveal.slide(h, v);
          const { width, height } = Reveal.getConfig();
          return { id: slide.id || `${h}.${v ?? 0}`, tall: slide.scrollHeight - height, wide: slide.scrollWidth - width };
        }""", i)
        page.evaluate("document.fonts.ready.then(() => true)")
        page.screenshot(path=f"shots/slide-{i + 1:02d}.png")
        if info["tall"] > 0 or info["wide"] > 0:
            problems.append(info)
    print(json.dumps(problems, indent=2))
    browser.close()
```

Fragments start hidden in these screenshots; the PDF export shows each slide's final state. Then review each screenshot for: text cut off or wrapping unevenly in columns, low contrast inside colored boxes (text inheriting the wrong color), missing icons or fonts (fallback faces, empty squares), images stretched or pixelated, and consistency of title position across slides. For many slides, a contact sheet is quicker (`../../documents/references/convert-and-render.md`). The general Playwright setup is in `../../builder-tools/references/playwright-web-testing.md`.

## Accessibility

- Each slide has a heading; reading order follows the visual order; images have alt text; contrast passes `COL-01` for every text and background pair, including code themes.
- reveal.js announces slide changes to screen readers through a live region and is keyboard-navigable; both depend on content being real text.
- Embedded video has captions; audio content has a transcript.
- Share the deck as HTML plus PDF, and put links in the notes or a resources slide as readable text, not only as QR codes.

## Done when

- The deck runs offline from its folder: library, plugins, fonts and images are local, and any CDN URLs are pinned.
- The overflow check reports nothing, and every slide's screenshot was reviewed.
- The PDF export has one page per slide (or per fragment when wanted), with backgrounds and fonts correct.
- Reduced motion is honored, contrast and alt text checks pass, and speaker notes exist where the talk needs them.
