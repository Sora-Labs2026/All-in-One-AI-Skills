# Generative and algorithmic art with p5.js

Read this to build art from code: flow fields, particle systems, packing and tiling, recursive growth, noise landscapes, pen-plotter drawings, or a numbered edition where every seed gives a different but reproducible piece. Examples target p5.js 1.11 and 2.x (2025-2026) in a browser. Check the version the project loads before writing against it.

Contents: when p5.js fits · setup and versions · reproducibility · structure a sketch · editions and features · export for screen, print and plotter · performance · the viewer page · originality, credits and accessibility · done when.

## When p5.js fits

| Goal | Use | Why not the others |
|---|---|---|
| A sketch people open and explore in a browser, with seeds and sliders | p5.js in one HTML page | Quickest loop from idea to pixels; runs anywhere |
| Heavy per-pixel work, shaders, thousands of moving 3D objects | p5.js `WEBGL` mode with a fragment shader, or plain WebGL/three.js | 2D canvas drawing stalls past tens of thousands of shapes per frame |
| A static print at poster size, or vector output for a plotter | The same algorithm written to emit geometry, then SVG or PDF | Raster canvases cap out at browser limits and blur when scaled |
| Batch renders on a server, no browser | Python with `cairo` or `Pillow`, or a headless browser driving the sketch | p5.js needs a DOM; headless Chromium works but is the heavier path |
| A looping GIF or short clip of the piece | Render frames, then follow `../../documents/references/animated-media.md` | It covers palettes, frame timing, size and flash checks |

## Setup and versions

- Load p5.js from a pinned version, never `latest`: `https://cdn.jsdelivr.net/npm/p5@1.11.3/lib/p5.min.js` or the 2.x build the project chose. For anything you publish or sell, vendor the file next to the page, so the piece still runs when a CDN changes.
- **p5.js 2.0 (2025) is a breaking release.** Asset loading moved to promises: `preload()` is gone and you write `async function setup() { img = await loadImage("a.png"); }`. Some 1.x add-ons, including SVG renderers, lag behind; check each add-on's supported major before upgrading. A 1.x sketch that uses `preload()` needs porting or the official compatibility add-on.
- Serve the folder over HTTP while developing (`python3 -m http.server 8000`). Loading fonts, images or JSON from `file://` fails in most browsers.
- Use instance mode (`new p5((p) => { p.setup = ...; })`) when the page holds more than one sketch or other scripts; global mode pollutes `window` with names like `random` and `color`.

## Reproducibility: same seed, same piece

A seed is a promise: the same seed and the same code produce the same work, today and in five years. Keep it with these rules.

1. **One source of randomness.** Every random decision goes through a seeded generator. `Math.random()`, `crypto.getRandomValues()`, `Date.now()` and unseeded library calls break the promise; search the code for them before calling it done.
2. **Own the generator for long-lived editions.** p5's `randomSeed()` and `noiseSeed()` are fine for sketches, but their sequences are implementation details that may change between majors. A small generator you ship with the piece cannot change under you:

```js
// FNV-1a: turn any string (a token id, a title, a date) into a 32-bit seed.
function hashSeed(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

// mulberry32: small, fast, public-domain generator; plenty for visual work, not for security.
function makeRng(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Separate streams per subsystem, so adding a random call to the palette code
// does not shift every particle that comes after it.
const stream = (seed, label) => makeRng(hashSeed(`${seed}:${label}`));
const layoutRng = stream(seed, "layout");
const paletteRng = stream(seed, "palette");
```

3. **Shuffle correctly.** `array.sort(() => rng() - 0.5)` is biased and its result depends on the engine's sort algorithm. Use Fisher-Yates with your generator.
4. **Decouple from frame rate and screen.** Step simulations with a fixed time step (`dt = 1 / 60`) and a fixed number of steps, not with `deltaTime` or wall-clock time. Work in canvas-relative units (`x * width`) so a larger canvas gives the same composition, not a cropped one.
5. **Pin pixel density.** On high-density screens p5 draws at `devicePixelRatio`, so the same sketch exports 1200 px on one laptop and 2400 px on another, and `pixels[]` changes length. Call `pixelDensity(1)` for exports, or render into a fixed-size buffer from `createGraphics()`.
6. **Expect tiny pixel differences across machines.** Anti-aliasing and floating-point rasterization differ between GPUs and browsers. "Reproducible" means the same geometry, colors and composition. Test that by hashing the generated geometry (the list of shapes and their coordinates, rounded) rather than the PNG bytes, and compare images with a tolerance.

## Structure a sketch

Keep three layers apart; it makes seeds, previews, high-resolution export and plotting all cheap:

1. `features(seed)`: pure function that decides the high-level traits (palette, density, composition type) from the seed, before any drawing.
2. `generate(seed, traits, params)`: pure function that returns geometry (polylines, circles, cells) in unit coordinates.
3. `render(geometry, target)`: draws that geometry to the screen canvas, an offscreen buffer at print size, or an SVG string.

Put every tunable value in one `params` object with a default, a range and a step, and derive UI controls from it. Read and write state from the URL hash (`#seed=4096&density=0.35`) so any view can be shared and reopened exactly.

Composition still matters in generated work: keep a margin, give the eye one area of highest density or contrast, and limit the palette to a few colors with clear roles. A palette chosen by seed from a short curated list beats random RGB values. When a seed produces a weak piece (empty, muddy, everything in one corner), fix the rules that allowed it rather than hand-picking seeds, unless the user wants a curated set.

## Editions and features

For a numbered set where each piece comes from a hash or a token number:

- Derive the seed from the identifier with a stated function (`hashSeed("edition-7:" + tokenId)`) and publish that function with the work.
- Compute traits in `features()` and render nothing until they are fixed. Traits that buyers or viewers see (names, rarity) must come from the same code as the image.
- Check the distribution before release: run `features()` for every seed in the edition (no drawing needed) and tabulate how often each trait occurs. Rare traits should be rare on purpose, not because of a bug.
- Write a manifest with the seed, the parameters, the code commit or file hash, the library version, the output size and the hash of the generated geometry. That record is what lets you or anyone else regenerate a piece and prove it is the original.
- Freeze the code and its dependencies before minting or selling. A "fix" after release changes pieces that people already own.

## Export for screen, print and plotter

- **Screen PNG:** `saveCanvas("piece-4096", "png")` after the final frame; include the seed in the file name.
- **Large raster:** render into `createGraphics(w * k, h * k)` with your unit-coordinate geometry, then save that buffer. Browsers limit canvas size (roughly 16,000 px per side and a total pixel budget that varies by browser and memory), so very large prints are better as vectors or rendered in tiles.
- **Print:** state the physical size and render at 300 ppi at that size (an A3 poster at 297 x 420 mm is about 3508 x 4961 px). Color for print is covered in `posters-and-canvas.md`.
- **Vector and plotter:** write SVG yourself from the geometry (a few lines per shape type), or use an SVG renderer add-on that supports your p5 major. Plotters draw strokes, not fills: express fills as hatching, merge touching segments into long paths, sort paths to shorten pen-up travel, and drop segments shorter than the pen width. vpype (open source) does sorting, merging and layer splitting from the command line. Preview the SVG at real size and check total path length, which predicts plot time.

## Performance

- Static pieces: build everything in `setup()`, draw once, call `noLoop()`. Animated pieces: keep per-frame work proportional to what changes.
- Trails and accumulation: draw new strokes onto a persistent buffer instead of redrawing all history every frame.
- Thousands of particles are fine in 2D; tens of thousands want plain arrays of numbers (or typed arrays) instead of objects created every frame, and fewer `push()`/`pop()` calls.
- Neighbor searches (packing, flocking, collisions) need a grid or quadtree; an all-pairs loop is `n^2` and stalls past a few thousand elements.
- `loadPixels()`/`updatePixels()` over a full high-density canvas is slow; work on a smaller buffer or move per-pixel math to a shader.
- Measure with the browser's performance panel before optimizing, and test on a modest laptop and a phone, not only a fast desktop.

## The viewer page

A single self-contained HTML page with:
- the canvas at a fixed aspect ratio that fits the viewport without scrolling;
- seed controls: the current seed shown as text, previous, next, random, and a field to type a seed;
- one labeled control per parameter, with its current value shown and a reset to defaults;
- download PNG (and SVG where the piece supports it), with the seed and parameters in the file name;
- a short caption: title, the seed, and what the parameters do.

Build controls as native `<input type="range">`, `<input type="number">` and `<button>` elements with visible `<label>`s, so they work with a keyboard and a screen reader (`../../ui-rules.md`, forms and buttons categories). Debounce regeneration on slider drags for expensive pieces. Style the page quietly; the art is the subject (`../../ui-distiller/references/style-catalog.md`, the "Gallery quiet" direction, is a good default frame).

## Originality, credits and accessibility

- **Living artists.** Techniques such as flow fields, circle packing, truchet tiles or L-systems are common ground. A living artist's recognizable series (their compositions, palettes and named motifs) is not. When asked to copy one, say so plainly and offer an original direction built from the qualities the user likes ("sparse, monochrome, long parallel strokes"). Never use an artist's name as a label or selling point without their permission.
- **Borrowed code.** Sketches shared on sketch-sharing sites often carry a Creative Commons ShareAlike or NonCommercial license by default. Check before reusing code in a commissioned or sold piece, credit the author in the page and the manifest, and keep the license text.
- **Fonts and images** used inside the piece need licenses that cover the output's use (`../../legal-ready/references/business-children-email-assets-rights.md`, item 19).
- **Motion safety.** Animated pieces respect `prefers-reduced-motion` (pause and show a still, with a play control), never flash more than three times per second (`MOT-21` in `../../../references/ui-rules/motion.md`), and give continuous motion a pause control (`MOT-19`).
- **Text alternative.** Give the canvas a role and label (`<canvas role="img" aria-label="...">`) or a caption describing what the piece shows; regenerate the description from the traits when it differs per seed.

## Done when

- The same seed and parameters regenerate the same geometry: two runs give an identical geometry hash, and the exported image matches by eye (or within a small pixel tolerance) on a second browser.
- No unseeded randomness or time dependence remains (`Math.random`, `Date`, `performance.now` used only for profiling).
- The export has the stated pixel or physical size, with `pixelDensity` pinned.
- For an edition: the trait distribution was tabulated over every seed, and the manifest is written.
- The viewer works with a keyboard, has labels, respects reduced motion, and runs smoothly on a modest machine.
- Credits and licenses for any borrowed code, fonts or images are listed.
