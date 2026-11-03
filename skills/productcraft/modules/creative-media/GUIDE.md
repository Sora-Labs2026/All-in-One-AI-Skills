# Creative Media

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Make visual and media work that is accurate, reproducible, accessible and cleared for use: generative art from code, posters and covers, infographics, themed slides and documents, reveal.js talks, programmatic video, prompts for image and video models, enhanced images, ebooks, and tidy folders of files and invoices. Each output is built by a script that can be rerun, checked by looking at the rendered result, and delivered with its credits. The user's content, rights and files come first; aesthetics serve them.

**Boundaries.** Word, Excel, PowerPoint and PDF file mechanics, document-to-Markdown conversion, animated GIFs and short clips live in `../documents/GUIDE.md`; this module links to them instead of repeating them. Interface design is UI Distiller (`../ui-distiller/GUIDE.md`) and the UI rulebook (`../ui-rules.md`, including the `BRD` brand-identity rules); charts inside a product are `../data-and-product-surfaces.md`; charts made in analysis code are `../data-engineering/references/plotting.md`. Asset licenses for a launch are `../legal-ready/GUIDE.md`. Rendering on cloud infrastructure is `../cloud-infrastructure/GUIDE.md`.

## When to activate

- Art or visuals made with code: p5.js sketches, flow fields, particle systems, seeded editions, plotter drawings.
- A static design: poster, flyer, cover, social or link-preview card, certificate, abstract canvas piece.
- An infographic: statistics, a comparison, a timeline, a process or a map as one designed graphic.
- One look across slides, documents, spreadsheets, pages and charts; applying a brand guide or a chosen direction to them.
- A presentation built with reveal.js.
- Video from code with Remotion: demos, explainers, data-driven or templated clips, captioned cuts.
- Writing or improving prompts for image or video generation models, keeping a generated series consistent, or calling a generation API.
- Improving images: upscaling, denoising, sharpening, tone and color, background removal, metadata stripping, export formats.
- Markdown into an EPUB ebook.
- Sorting a messy folder by type and date, renaming files consistently, finding duplicates; organizing invoices and receipts into named files and a ledger.
- Motion graphics, kinetic type, logo or product animations, perfect loops and 3D shots made in code (HTML with GSAP, Three.js, Remotion, Blender) and rendered frame by frame to MP4 or GIF.
- Math and technical explainer animation with Manim: equations, plotted functions, geometry, algorithm states.
- Editing recorded footage: selects from a transcript, frame-accurate cuts, captions, audio levels, color, reframing, export, an editable timeline.
- Making recordings searchable: transcripts, shots, on-screen text, keyword and semantic search, clips from results.
- Matching a reference look: measuring color, tone and cut rhythm into a style pack and applying it consistently without copying the references.
- Calling hosted models for images, video, speech, voices, music or sound effects inside a pipeline, with budgets, consent and labels.
- A product demo video of a web interface, scripted and repeatable.
- A presentation as a single HTML file without reveal.js, or a `.pptx` rebuilt for the web.
- iOS app icons at every size and appearance, and icon assets inside an Apple-platform app.
- Checking an animated character's motion state in Blender: facing, ground contact, foot sliding, scale.
- Converting, extracting, OCRing, redacting, signing or filling documents through a hosted API.
- **Not for** UI screens and components, office-file editing or PDF forms (documents), or GIF emoji and short loops (documents, animated media).

## Ground rules

1. **Facts come from the user.** Dates, prices, names, statistics, quotes, logos and credits on any output are supplied or sourced, never invented. Missing facts get clearly marked placeholders and a question.
2. **Original work, real consent.** Do not imitate a living artist's signature style on request; describe the qualities the user wants and build an original direction. Never depict real, identifiable people (face or voice) without their documented consent, never use another organization's trademarks or branding to suggest a connection, and never produce fake evidence (documents, receipts, screenshots, news images). The full rules for generated media are in `references/generation-prompting.md`.
3. **Every asset has a source and a license.** Fonts, images, icons, music, footage, code borrowed from others, and generated media are listed in a credits file with their license and required attribution. Keep provenance metadata that tools embed, and label AI-generated media where the platform or the law requires it.
4. **Accessible by default.** Measured contrast for every text pair (`COL-01`), alt text or a text alternative for every meaningful image and graphic, captions for speech, no flashing above three per second (`MOT-21`), and a pause or still for continuous motion (`MOT-19`, `MOT-04`).
5. **Rebuildable.** Generate outputs with a small script saved next to them; pin library versions; record seeds, parameters and model versions. A fix is then an edit and a rerun, and the result can be reproduced.
6. **Look before you claim.** "Looks right", "fits", "readable" and "on brand" need a rendered image you actually viewed at real size (and at 100% for detail). Name any check that could not run.
7. **The user's files and data are safe.** Originals stay untouched; reorganizations are planned as a dry run and applied only after approval; nothing is overwritten or deleted by the agent (deletion follows the stop-check in `../agent-safety/GUIDE.md`); personal and financial documents are processed locally and never uploaded without permission.
8. **Hosted generation costs money and has terms.** Estimate cost and stay under the user's cap; keys stay out of the chat and the code; read the provider's terms for commercial use and for uploaded material; never retry a billed job blindly and never work around a safety filter.

## Check the toolbox

```bash
python3 - <<'EOF'
import importlib
for m in ("PIL", "cv2", "playwright", "fontTools", "matplotlib", "rembg"):
    try:
        mod = importlib.import_module(m)
        print(f"{m:11} {getattr(mod, '__version__', 'installed')}")
    except ImportError:
        print(f"{m:11} MISSING")
EOF
for c in node npx pandoc ffmpeg ffprobe magick exiftool rsvg-convert pdftoppm pdffonts java ocrmypdf tesseract realesrgan-ncnn-vulkan manim scenedetect blender; do
  printf '%-24s ' "$c"; command -v "$c" || echo MISSING
done
```

Use what is installed. Ask before installing packages, browsers, models or system tools, and prefer a project virtual environment or a local `node_modules`. Model downloads for upscaling and background removal are large and fetched on first use; say so before triggering one.

## Route by task

| Task | Read | Minimum check before calling it done |
|---|---|---|
| Generative or algorithmic art, seeded editions, plotter output | `references/generative-art.md` | Same seed gives the same geometry hash twice; no unseeded randomness; export size pinned; trait distribution tabulated for editions |
| Poster, cover, flyer, social card, canvas piece | `references/posters-and-canvas.md` | Rendered at final size and viewed; facts proofread; fonts embedded and licensed; safe area and contrast checked |
| Infographic | `references/infographics.md` | Every number traced to `data.csv` and a source; honest encodings; readable at display width; alt text plus a text or data alternative |
| Theme or brand across slides, documents, pages and charts | `references/themes-and-brand-application.md` | Theme spec as data with measured pairs; applied through each format's theme mechanism; every page rendered and reviewed |
| reveal.js presentation | `references/revealjs-presentations.md` | Runs offline with pinned assets; overflow check clean; every slide screenshot reviewed; PDF export checked |
| Video from code with Remotion | `references/remotion-video.md` | `ffprobe` confirms duration, size, frame rate and codec; full render watched; captions and loudness checked; license checked |
| Prompts for image or video models; generation APIs | `references/generation-prompting.md` | Output reviewed at full size; safety and likeness rules met; generation log kept; labels where required |
| Upscale, denoise, sharpen, fix color, remove backgrounds, strip metadata | `references/image-enhancement.md` | Before and after compared at 100%; originals untouched; metadata handled; model licenses allow the use |
| Markdown to EPUB | `references/ebooks-epub.md` | EPUBCheck has no errors; Ace report reviewed; opened in two readers |
| Organize a folder, rename files, find duplicates | `references/file-organization.md` and `scripts/organize_plan.py` | Plan approved; nothing deleted or overwritten; counts match before and after; undo script saved |
| Invoices and receipts into named files and a ledger | `references/invoices-and-receipts.md` and `scripts/organize_plan.py --from-csv` | Ledger matches files; totals per currency; ambiguous values flagged; spot checks done; nothing uploaded |
| Motion graphics, kinetic type, loops or 3D shots rendered from code | `references/directed-motion.md`, `scripts/motion_contract_check.py` and `scripts/motion_timing.py` | Brief filled with numbers; lint clean and one frame hashed identically twice; contact sheet viewed and notes name frames; holds, contrast and flash limits met; `ffprobe` and loudness checked |
| Math or technical explainer animation | `references/manim-explainers.md` | Storyboard written; pinned Manim version and seeded randomness; mathematics checked independently; captions; `ffprobe` on the deliverable |
| Editing recorded footage: cuts, captions, levels, color, reframing, export | `references/video-editing.md` | Originals untouched; cuts frame-accurate; loudness measured; captions checked; export matches the destination; timeline validated |
| Searching video and audio; clips from search results | `references/media-indexing-and-search.md` | Consent and retention recorded; records carry hash, time range and model version; quality measured on a saved query set |
| Matching a reference look (grade and cut rhythm) | `references/reference-look-measurement.md` and `scripts/cut_rhythm.py` | References private and absent from the output; output re-measured against the pack metric by metric; shot lengths follow the distribution |
| Hosted generation of images, video, speech, music or sound | `references/hosted-media-generation.md` after `references/generation-prompting.md` | Plan and cap approved; requests validated against the current schema; no double submissions; consents, licenses, provenance and labels recorded |
| Product demo video of a web interface | `references/ui-demo-videos.md` | Rehearsal passes; demo data only; video trimmed and captioned; privacy pass done |
| HTML slide deck without reveal.js; pptx rebuilt for the web | `references/html-slide-decks.md` | Runs offline; no slide overflows; keyboard and screen-reader checks; PDF matches the slides |
| iOS app icons and in-app icon assets | `references/ios-app-icons.md` and `scripts/asset_catalog_check.py` | Checker clean; opaque 1024 store icon; viewed on a home screen in each appearance; licenses recorded |
| Motion faults in an animated Blender scene | `references/blender-motion-inspection.md` | Read-only inspection of a copy with auto-run off; findings with frames, names, coordinates and tolerances; confirmed by renders |
| Documents through a hosted processing API | `references/hosted-document-apis.md` | Owner approved the upload and data terms; each result verified with independent tools; remote copies deleted |
| Office files, PDFs, document to Markdown, GIFs and short clips | `../documents/GUIDE.md` | That module's checks |

Several often combine: a launch video needs `references/remotion-video.md`, `references/themes-and-brand-application.md` and maybe `references/generation-prompting.md`; a conference talk needs `references/revealjs-presentations.md`, the theme reference and `references/infographics.md` for its data slides.

A product walkthrough usually chains `references/ui-demo-videos.md` (capture), `references/video-editing.md` (cut, captions, levels, export) and sometimes `references/hosted-media-generation.md` (narration); a series that must share one look adds `references/reference-look-measurement.md`; a lecture adds `references/manim-explainers.md` for its derivations.

## Workflow

### 1. Write the brief

From the request, the files or one short question: purpose, audience, where it appears and at what size, the fixed content (exact wording, data, logos), the brand or direction, the rights situation, and for generation or rendering services the budget.

**Done when:** you can state the deliverable in one sentence ("a 1080 x 1350 PNG and an A3 PDF with 3 mm bleed, Harbor theme, text from the user's brief, one licensed photo") and every fact on it has a source.

### 2. Gather assets and rights

Collect fonts, images, data, footage and music into the project folder, and start `credits.md` (below). Reject assets with unknown origin or a license that does not allow the use; ask for a replacement.

### 3. Build with a script

Write the generator (HTML and a render script, a p5.js sketch, a Remotion composition, a Python pipeline) next to the outputs, not inside the user's application unless that is the feature. Keep data, layout and rendering separate. Pin versions; record seeds.

### 4. Render and look

Render at the real output size. View the result whole and in detail, on the target medium where possible (a phone-width viewport, a projector resolution, a printed proof at 100%). Run the reference's checks.

### 5. Check accessibility, facts and rights

Contrast measured; alt text, captions or text alternatives written; motion and flashing within limits; facts proofread against the brief; every asset in `credits.md`; generated media logged and labeled where required.

### 6. Deliver

Hand over the outputs and the source folder, and report as below.

## Credits and provenance

Keep a `credits.md` (or the project's existing asset inventory) next to the outputs:

```markdown
| Asset | Used in | Source | Author or owner | License | Attribution required | Changes made |
|---|---|---|---|---|---|---|
| fonts/SourceSerif4-*.ttf | headings | official release | Adobe | OFL-1.1 | no (keep OFL.txt) | none |
| photos/harbor.jpg | cover | stock library, order 12345 | photographer name | standard stock license | no | cropped, graded |
| images/bg-texture.png | slide 1 | generated | user | per model terms (recorded in generation log) | label as AI-generated where required | upscaled 2x |
| sketch.js (flow field core) | poster | sketch-sharing site | author name | CC BY-SA 4.0 | yes, in caption | rewritten parameters |
```

For a product launch, merge this into the inventory described in `../legal-ready/references/business-children-email-assets-rights.md` (item 19).

## What to report

- Output files with sizes or durations, and the source folder that rebuilds them.
- The brief in one sentence, and the direction or theme used with a one-line reason.
- Checks that ran and their results (render reviewed, contrast ratios, overflow check, EPUBCheck, `ffprobe`, loudness, planner summary), and checks that did not run with the reason.
- Rights: the credits file, any generated media and how it is labeled, consents obtained, licenses the user must confirm (for example a commercial font or Remotion's company license).
- For file work: counts moved, skipped and flagged; where the plan and undo script are; that nothing was deleted.
- Up to three things for the user to double-check (`../../SKILL.md`, always-on behavior 8), such as a fact you could not verify or a license tier only they can confirm.

## Working with other ProductCraft modules

- `../documents/GUIDE.md`: `.pptx`, `.docx`, `.xlsx` and PDF mechanics, rendering pages to images, document-to-Markdown conversion, and `../documents/references/animated-media.md` for GIFs and short clips, including the flash-rate check.
- `../ui-rules.md` and `../../references/ui-rules/`: contrast (`COL`), type (`TYP`), motion (`MOT`), icons and imagery (`ICO`) and brand identity (`BRD`); `../../examples/brand.html` shows a brand guideline page.
- `../ui-distiller/references/style-catalog.md` for complete visual directions with checked palettes and OFL font pairings; `../ui-distiller/references/taste.md` for the self-critique pass.
- `../data-and-product-surfaces.md` and `../data-engineering/references/plotting.md` for chart choice and honest charts.
- `../legal-ready/GUIDE.md` for asset licenses, consent and claims in marketing material.
- `../integrations/GUIDE.md` and `../agent-safety/GUIDE.md` for calling hosted generation APIs with keys handled safely.
- `../cloud-infrastructure/GUIDE.md` before any cloud rendering resources are created.
- `../ui-distiller/references/motion-engineering.md` for easing, springs and choreography shared by interfaces, slides and video; `../ui-distiller/references/translucent-materials.md` for glass surfaces and their contrast.
- `../builder-tools/references/playwright-web-testing.md` for the headless browser used to render and check pages, posters and slides.
- `../research-writing/GUIDE.md` for the content side of research posters, talks and paper pages: venue rules, verified citations and reporting standards.

## Scripts

`scripts/organize_plan.py` is a read-only, standard-library, deterministic dry-run planner. It never moves, renames, creates or deletes anything. It proposes moves into folders by type, by date or both (dates from file names, else modification time in UTC), or checks an explicit `source,target` CSV; resolves every name collision with a numbered suffix, ignoring case by default; skips hidden, system, temporary and symlinked entries; keeps project folders and app bundles whole; and with `--hash-duplicates` flags identical content. Output as text, JSON (the undo log), or POSIX shell scripts to apply and to undo the plan, both of which skip any target that exists and never overwrite.

```bash
python3 <productcraft>/modules/creative-media/scripts/organize_plan.py ~/Downloads
python3 <productcraft>/modules/creative-media/scripts/organize_plan.py ~/Scans --by date --recursive --hash-duplicates --format json
python3 <productcraft>/modules/creative-media/scripts/organize_plan.py inbox --from-csv renames.csv --dest filed --format sh
```

`<productcraft>` is the folder where the ProductCraft skill is installed. Exit codes: 0 nothing needs review, 1 some items need review, 2 usage error. Tests: `python3 -B -m unittest discover -s <productcraft>/modules/creative-media/tests -v`.

`scripts/cut_rhythm.py` is a read-only, standard-library, deterministic analyzer of cut rhythm. It reads detected shot boundaries (an FFmpeg `showinfo` log, a scene-list CSV or a plain list of times), reports the shot-length distribution (median, median absolute deviation, percentiles, cuts per minute, in frames and beats when given `--fps` and `--bpm`) and flags suspect very short shots; with `--plan SECONDS --seed N` it draws a reproducible plan of shot lengths from that distribution, snapped to frames or beats. Exit codes: 0 no warnings, 1 warnings, 2 usage error.

`scripts/asset_catalog_check.py` is a read-only, standard-library checker for Xcode asset catalogs. It reads every app icon set and image set: valid Contents.json, referenced files present and no stray files, PNG pixel sizes against size and scale, square icons, no alpha channel in the default 1024 App Store icon, consistent image-set scales, and which dark and tinted appearances exist. Exit codes: 0 clean, 1 errors or warnings, 2 usage error.

`scripts/motion_contract_check.py` is a read-only, standard-library lint for animation code (HTML, JS, TS, CSS). It flags what makes rendered frames differ from run to run or impossible to seek: wall-clock reads and unseeded randomness (errors); timers, delta clocks, autoplaying media and CSS transitions; GSAP timelines never paused or seeked; web fonts with no ready wait; and a missing way to freeze an exact frame. Silence a deliberate line with a `motion-ok` comment. Exit codes: 0 clean, 1 findings, 2 usage error.

`scripts/motion_timing.py` turns direction into whole frames: milliseconds to frames, a beat grid computed from absolute time (with a drift warning), loop length and whether each cycle fits it, GIF delays in hundredths that add up to the exact loop, motion-blur subframe times for a given shutter angle, and minimum reading holds. Exit codes: 0 ok, 1 warnings, 2 usage error.

```bash
python3 <productcraft>/modules/creative-media/scripts/motion_contract_check.py motion/ --json
python3 <productcraft>/modules/creative-media/scripts/motion_timing.py beats --fps 30 --bpm 128 --bars 8
python3 <productcraft>/modules/creative-media/scripts/motion_timing.py gif --fps 30 --frames 90
python3 <productcraft>/modules/creative-media/scripts/cut_rhythm.py scenes.log --duration 62.4 --fps 25 --plan 30 --seed 7
python3 <productcraft>/modules/creative-media/scripts/asset_catalog_check.py MyApp/Assets.xcassets
```

## References

- `references/generative-art.md`: read when making art with code: p5.js versions, seeded generators and streams, reproducibility across machines, editions and trait checks, export for print and plotters, performance, the viewer page.
- `references/posters-and-canvas.md`: read when making a poster, cover, card or canvas piece: brief, tool choice, grid and hierarchy, type and licenses, HTML-to-PDF rendering, print bleed and color, layout checks.
- `references/infographics.md`: read when facts or numbers become one graphic: takeaway headline, sourced data file, choosing the form, honest encodings, sizes for the display, color-vision-safe palettes, building with code.
- `references/themes-and-brand-application.md`: read when one look must span slides, documents, sheets, pages and charts: theme spec as data, where each format keeps its theme, fonts across machines, brands that are not yours.
- `references/revealjs-presentations.md`: read when building a reveal.js talk: offline setup, canvas size and type, writing slides, code, math and charts, motion, notes, PDF export, overflow and screenshot checks.
- `references/remotion-video.md`: read when making video from code: license, the frame model, timing, media and fonts, async data, captions, loudness, rendering, cloud rendering, checks.
- `references/generation-prompting.md`: read when prompting image or video models: when not to generate, image and video prompt structure, shot language, consistency, hosted and local models, safety and likeness rules, labels and provenance, output review.
- `references/image-enhancement.md`: read when improving images: honest limits, re-capture first, operations and order, Pillow, OpenCV, Real-ESRGAN, rembg and ImageMagick recipes, color and metadata, formats, untrusted files.
- `references/ebooks-epub.md`: read when turning Markdown into EPUB: structure, metadata and identifiers, pandoc build, styling for readers, covers and fonts, accessibility metadata, EPUBCheck and Ace, Kindle and stores.
- `references/file-organization.md`: read when organizing or renaming files: ground rules, scope, choosing a scheme, the planner, review, apply and undo, duplicates, portable names, photo dates.
- `references/invoices-and-receipts.md`: read when filing invoices and receipts: e-invoice XML, text and OCR extraction, amount and date parsing, validation, naming, the ledger, privacy and retention.
- `references/directed-motion.md`: read when animating from code to studio quality: the render contract (every frame a pure function of time), a numeric brief with a banned list, default easing, spring, duration, stagger, hold and beat numbers, the frame-level review loop with contact sheets, rendering with a browser and FFmpeg, sound sync and loudness, perfect loops, MP4 and GIF delivery, tools by role with their licenses, failures and fixes.
- `references/manim-explainers.md`: read when making a math or technical explainer: when Manim fits, setup and versions, storyboard, a complete scene, render flags, transform and updater pitfalls, style, narration, accessibility, checks.
- `references/video-editing.md`: read when cutting recorded footage: ingest and proxies, a transcript-based paper edit, frame-accurate cuts, captions, cleaning and ducking audio, two-pass loudness, color, reframing, export settings, timeline handoff, rights.
- `references/media-indexing-and-search.md`: read when making recordings searchable: consent and retention, transcripts, shots and keyframes, on-screen text, keyword and vector indexes, hybrid search, clips, measuring retrieval quality, live sources, hosted services.
- `references/reference-look-measurement.md`: read when matching a reference look: measuring rather than copying, the style pack, color by luminance zone, robust tone statistics, cut rhythm, building a LUT, applying and verifying.
- `references/hosted-media-generation.md`: read when calling hosted generation models: authorization and caps, model choice, schema checks, the job lifecycle without double billing, uploads, voices and consent, music licenses, provenance and labels.
- `references/ui-demo-videos.md`: read when recording a product demo of a web app: demo environment, discover, rehearse, record with a visible cursor, pacing, captions from the step log, privacy.
- `references/html-slide-decks.md`: read when building a single-file HTML deck: fixed canvas or fluid slides, a minimal accessible controller, builds, notes, fonts, pptx conversion, PDF export, overflow checks.
- `references/ios-app-icons.md`: read when producing iOS app icons and in-app icons: single-size icons, dark and tinted appearances, layered icons, the full size set, symbols and vector assets, licenses, the catalog checker.
- `references/blender-motion-inspection.md`: read when an animated Blender scene looks wrong: safe headless inspection, an extraction script, facing, contact, sliding, crossover, twist and scale checks, renders for compositing, the report.
- `references/hosted-document-apis.md`: read when processing documents through a hosted API: local or hosted, data terms before upload, the request pattern, and verification of conversion, extraction, OCR, redaction, signatures and forms.
