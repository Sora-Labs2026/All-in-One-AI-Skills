# Images for search: formats, delivery, alt text at scale, metadata and AI labels

Read this when images matter for search or for page speed: choosing formats and sizes, responsive images and lazy loading, image URLs, CDNs and image sitemaps, writing alt text for thousands of images, photo metadata and licensing, and labeling AI-generated or AI-edited images. The short version for one page is in `on-page-elements.md` ("Images"); Core Web Vitals causes and budgets are in `../../engineering-practices/references/performance.md`; preview images for social cards are in `structured-data-and-social-cards.md`; accessibility law is in `../../legal-ready/references/accessibility.md`.

## What image search uses

- **The page around the image:** the title, headings, caption and the text near the image are the main context. An image on a page about something else is hard to rank for anything.
- **The `<img>` element:** Google indexes images in `<img>` (including inside `<picture>`), not images set only as CSS backgrounds. The `src` (or `srcset`) URL must be crawlable: not blocked by `robots.txt`, not behind authentication, returning the right `Content-Type`.
- **`alt` text** and the **file name** add context; neither rescues an image on an unrelated page.
- **Structured data** links images to features (product, recipe, article images) and to licensing details.
- **The image itself:** visual search (Lens and similar) recognizes objects and scenes. Original, clear, relevant photos give it something to work with; stock images used by thousands of sites rarely stand out.

## Formats

| Format | Use for | Notes |
|---|---|---|
| AVIF | Photos and complex images where file size matters most | Best compression in most cases; slower to encode |
| WebP | Photos and graphics, the safe modern default | Supports transparency and animation |
| JPEG | Photo fallback | Universal |
| PNG | Graphics needing lossless quality or transparency where WebP is not used | Large for photos |
| SVG | Logos, icons, diagrams | Scales without loss; sanitize SVGs from untrusted sources, since they can carry scripts |
| GIF | Avoid for animation | Use a muted looping video or animated WebP instead |

Google Search documents support for indexing AVIF, WebP, JPEG, PNG, GIF, SVG and BMP. Browser support for AVIF and WebP is near universal in current browsers (check a support table such as caniuse before dropping a fallback). Serve modern formats with `<picture>` and `type` fallbacks, or let an image CDN choose by the `Accept` header, which then must send `Vary: Accept` or use a cache key that includes the format.

```html
<picture>
  <source type="image/avif" srcset="/img/tr3-blue-640.avif 640w, /img/tr3-blue-1280.avif 1280w" sizes="(max-width: 700px) 100vw, 640px">
  <source type="image/webp" srcset="/img/tr3-blue-640.webp 640w, /img/tr3-blue-1280.webp 1280w" sizes="(max-width: 700px) 100vw, 640px">
  <img src="/img/tr3-blue-640.jpg" width="640" height="480" alt="Trail Runner 3 in blue, side view, showing the lugged sole">
</picture>
```

## Sizes and delivery

- **Serve what the layout needs:** `srcset` with width descriptors and an accurate `sizes`, so phones do not download desktop images. Never upscale a small original; it adds bytes, not detail.
- **Reserve space:** `width` and `height` attributes (or CSS `aspect-ratio`) on every image, to prevent layout shift.
- **Compression and quality** are a visual judgment per image type; check results by eye at the sizes served, and set byte budgets per template with the project (`../../engineering-practices/references/performance.md`), not from generic tables.
- **Large previews:** Discover and large image previews in results need images at least 1,200 pixels wide and the page must allow them (`max-image-preview:large`). Feature pages (Article, Product, Recipe) list their own image requirements; read the current page.
- **Stable image URLs.** Image search history attaches to the image URL. Renaming files, changing CDN paths or adding cache-busting query strings that change with every deploy restart that history; version with content hashes that change only when the image changes, and redirect old image URLs during migrations.
- **Image CDNs on another host** are fine. Make sure their `robots.txt` allows crawling, they serve the right content type, and URLs do not expire (signed URLs that expire break indexing).

## Lazy loading

- Use native `loading="lazy"` for images below the first screen. It is supported in current browsers and keeps the real `src` in the HTML.
- **Never lazy-load the Largest Contentful Paint image** (usually the hero or the main product photo). Give it `fetchpriority="high"` and, where useful, a preload.
- JavaScript lazy loaders that keep the real URL in `data-src` until a scroll event can hide images from crawlers, which do not scroll like users. Prefer native lazy loading; if a library is needed, make sure the real `src` is set when the image enters the viewport (`IntersectionObserver`) and check the rendered HTML with URL Inspection.
- `decoding="async"` on non-critical images keeps decoding off the critical path.

## Image sitemaps

- Add `<image:image>` entries with `<image:loc>` to the page's sitemap entry when images load from another host, through scripts, or from galleries that are hard to discover. Google allows up to 1,000 images per page entry.
- Google deprecated the other image sitemap tags (`caption`, `title`, `license`, `geo_location`) in 2022; leave them out of new sitemaps. Licensing goes in structured data or photo metadata (below).

```xml
<url>
  <loc>https://www.example.com/products/trail-runner-3</loc>
  <image:image><image:loc>https://cdn.example.com/img/tr3-blue-1280.jpg</image:loc></image:image>
</url>
```

(The `urlset` element declares `xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"`.)

## Alt text at scale

`alt` text is first an accessibility requirement (WCAG 2.x success criterion 1.1.1) and second a search signal. Write it for a person who cannot see the image.

| Image role | `alt` |
|---|---|
| Decorative (borders, mood images that add nothing) | `alt=""` so screen readers skip it |
| Informative (product photo, illustration of a step) | What it shows that matters in this context, concisely |
| Functional (an image that is a link or button) | What the link or button does ("Search", "Go to the home page") |
| Text in an image | The text itself |
| Complex (chart, diagram, map) | A short `alt` naming it, and the full description or data in nearby text or a table |

`alt` belongs to a placement, not to a file: the same photo can need different text on a product page and in a blog post about trail grip. For large sites:

1. **Inventory** images per template and placement, with current `alt` and the page context. A crawler export or a query on the CMS gives this.
2. **Classify** each placement as decorative, informative, functional or complex. Templates often settle whole classes at once (gallery thumbnails, icons, avatars).
3. **Draft from data first.** Product images can be described from structured fields (product name, color, angle, view). For editorial images, a vision model can draft text; treat drafts as unreviewed, never auto-publish them, and do not let them identify people by face or infer sensitive traits (health, ethnicity, religion).
4. **Review** a person-checked sample per template and every image where accuracy matters (medical, safety, legal, product claims). Fix the template or prompt, not only the sample.
5. **Store** the text in the CMS field for that placement, so it survives redesigns, and translate it with the page.
6. **Check** in CI: informative images without `alt`, `alt` equal to the file name, `alt` starting with "image of", the same `alt` on every image in a gallery, and keyword lists. `scripts/seo_check.py` reports missing `alt`; an accessibility checker covers the rest (`../../legal-ready/references/accessibility.md`).

There is no required character count; screen readers read the whole text. Keep it short because people listen to it, and put long descriptions in the page.

## Photo metadata and licensing

- Google Images reads IPTC photo metadata embedded in the file: **Creator**, **Credit Line**, **Copyright Notice**, **Web Statement of Rights** and **Licensor URL** (for the licensable badge), and **Digital Source Type** (for AI labels). Alternatively, `ImageObject` structured data can carry `license`, `acquireLicensePage`, `creditText`, `creator` and `copyrightNotice`.
- **Check the pipeline.** Image CDNs, resizers and format converters often strip metadata by default. Test that the fields survive to the served file, or re-apply them after conversion.
- **Strip what should not be public.** Camera metadata can include GPS coordinates and device details. Remove location data from photos of homes, people and private places before publishing.
- **Rights:** publish only images the business owns or has licensed for this use, with credits where the license requires them. Stock licenses may forbid some uses (logos, sensitive subjects).

Reading metadata changes nothing; writing it changes files. Run audits read-only and make changes in the build or asset pipeline:

```bash
exiftool -csv -IPTC:By-line -IPTC:CopyrightNotice -XMP-iptcExt:DigitalSourceType -GPSLatitude -r public/img/ > image-metadata.csv
```

## AI-generated and AI-edited images

- **Label them in the file.** The IPTC Digital Source Type vocabulary has values for fully generated images (`trainedAlgorithmicMedia`), real images edited or extended with generative tools (`compositeWithTrainedAlgorithmicMedia`), composites (`compositeSynthetic`) and algorithmic images not from trained models (`algorithmicMedia`). Google reads this field to label images as AI-generated in some surfaces, and Merchant Center asks for it on AI-generated product images.
- **Content Credentials (C2PA)** attach signed provenance to files; many generation tools add them. Keep them through the pipeline where possible.
- **Disclose where people would expect to know,** next to the image or in the caption, especially for news, health, reviews and anything presented as documentary.
- **Never present a generated image as a photograph** of a real product, the premises, the team, customers or results. Product images must show the product as sold; consumer protection law treats misleading images like misleading claims (`../../legal-ready/references/honest-commerce.md`).
- **The law is moving.** The EU AI Act's transparency duties (Article 50) apply from 2 August 2026: providers of generative systems must mark outputs as machine-detectable, and deployers must disclose deepfakes. Transition periods for some of these duties have been proposed; check the position in force and the Commission's guidance and codes of practice. Other jurisdictions have their own rules. This is general information, not legal advice; check with counsel.
- Generation tools' terms differ on commercial use and ownership. Record the tool, date and terms for each published generated image.

## Measuring

- **Search Console Performance** with the search type set to Image shows clicks and impressions from image search; Discover has its own report.
- **URL Inspection** shows whether the page is indexed and renders its images; there is no per-image index report, so sample important images by searching for them in image search and noting what appears, with the date.
- Report image changes with like-for-like windows, since image traffic is often small and noisy (`search-measurement.md`).

## Done when

- [ ] Meaningful images are `<img>` or `<picture>` elements with crawlable, stable URLs, modern formats with fallbacks, `srcset` and `sizes`, and dimensions set.
- [ ] Below-the-fold images lazy-load natively; the LCP image is not lazy-loaded and has `fetchpriority="high"`.
- [ ] Image sitemaps, where used, contain only `image:loc` entries.
- [ ] Every placement has `alt` text appropriate to its role, drafted from data or a model and reviewed by a person on a recorded sample; decorative images have `alt=""`.
- [ ] Rights, credits and IPTC fields are correct in served files, and location metadata is stripped where it should not be public.
- [ ] AI-generated or edited images carry Digital Source Type metadata and visible disclosure where expected, and none is presented as a photo of something real.
