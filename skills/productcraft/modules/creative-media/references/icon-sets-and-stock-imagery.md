# Icon sets, stock imagery and the asset pipeline

Read this when choosing or applying an icon family (including two-tone "duotone" styles), picking stock or library photos for mockups and production (avatars, headshots, portraits, hero backgrounds, wallpapers), cropping and sizing them, or setting up how images are stored, processed and served. The icon rules are `ICO-01` to `ICO-12` in `../../../references/ui-rules/icons-imagery.md`; generated images follow `generation-prompting.md`; image repair is `image-enhancement.md`; loading performance is `../../engineering-practices/references/performance.md`; image search visibility is `../../search-visibility/references/image-search.md`.

## Ground rules

- **One icon family, one style per surface** (`ICO-01`). Mixing outline, filled, duotone, emoji and bitmap icons in one control set is the fastest way to look unfinished.
- **Every image has a recorded source and license** before it appears in anything shared. "Found on the web" is not a license.
- **Ship local, optimized files.** No hotlinking from photo libraries, icon CDNs or other sites in production; copy approved files into the project or your own media service.
- **Faces are personal data and likeness.** Use people photos only under a license that covers your use, with model releases for commercial and sensitive contexts.

## 1. Choosing an icon family

| Style | Strengths | Weak spots |
|---|---|---|
| Outline (1.5-2 px stroke at 24 px) | Light, neutral, pairs with most type | Thin at 16 px; active state needs a second form |
| Filled | Strong at small sizes, good for active states | Heavy in dense toolbars |
| Duotone (main shape plus a lighter secondary layer) | Richer, branded feel in feature lists and empty states | Too decorative for dense controls; secondary layer must not carry meaning |
| Rounded vs sharp corners | Rounded feels friendly; sharp feels technical | Must match the radius language of the interface |

Pick a family that covers the product's needs (count the icons you need first), ships as SVG under a license compatible with your product (MIT, ISC, Apache-2.0, SIL OFL for icon fonts, or a paid license read in full), offers outline and filled pairs if you use filled for active states (`ICO-08`), and is drawn on the same grid (usually 24 × 24 with a 2 px live-area margin).

## 2. Using icons well

- **Sizes:** 16 px in dense tables and inline with 13-14 px text, 20 px in buttons and menus, 24 px in navigation and toolbars, 32-48 px only in illustrations and empty states. Align the icon's optical center with the text's x-height center, not the line box.
- **Labels:** pair icons with words in navigation and feature lists. An icon-only control needs an accessible name (`ICO-04`) and a tooltip on pointer devices; use icon-only only for universal actions (close, search, more, play).
- **Color:** drive icons with `currentColor` so they follow text color and themes. Non-text contrast 3:1 against the background for icons that carry meaning (WCAG 1.4.11).
- **Delivery:** inline SVG for a handful; an SVG sprite with `<symbol>` and `<use href="#id">` for many; component imports with tree shaking in frameworks. Copy icon paths exactly from the family's files; hand-drawn approximations look broken.

```html
<svg class="icon" aria-hidden="true" focusable="false"><use href="#i-calendar"></use></svg>
<style>
  .icon { width: 1.25em; height: 1.25em; vertical-align: -0.2em; flex: none; }
  .icon { fill: none; stroke: currentColor; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; }
</style>
```

### Duotone icons

A duotone icon has two layers: the primary shape at full strength and a secondary shape (a fill or background part) at reduced strength. Implement it so both layers follow the theme:

```css
.duo { color: var(--icon-primary, currentColor); }
.duo .secondary { fill: currentColor; opacity: var(--icon-secondary-opacity, .4); }
.duo .primary   { fill: currentColor; }
/* or two colors: .duo .secondary { fill: var(--icon-secondary, currentColor); } */
```

- Keep the secondary opacity between 0.3 and 0.5; check it still separates from the background in dark mode (secondary layers on dark grounds often need a higher value).
- Never use the secondary layer to carry state or meaning; it disappears in forced-colors mode, where both layers become one system color. Test with forced colors on.
- Use duotone for larger, calmer placements (feature lists, settings categories, empty states) and plain outline or filled versions for dense controls, from the same family.

## 3. Choosing photos

| Use | Ratio | Deliver at | Look for |
|---|---|---|---|
| Avatar | 1:1 | 256, 512, 1024 px | Face centered, simple background, eyes near the upper third |
| Headshot card | 4:5 (or 3:4) | 800 × 1000, 1200 × 1500 | Shoulders up, neutral background, even light |
| Editorial portrait | 3:4 or 4:5 | 1500 × 2000 | Context and story; candid rather than posed |
| Hero or section background | 16:9 (desktop), 4:5 or 9:16 crop for phones | 1920 × 1080, 2400 × 1350, 2880 × 1620 | 30 to 50% calm negative space where text will sit; horizon kept level |
| Wallpaper | 16:10 desktop, 9:16 phone | 2560 × 1600, 1080 × 1920 | Low detail, no faces, no text |
| Social banner | 3:1 | 1500 × 500 | Subject away from overlay areas (`banners-and-social-graphics.md`) |

- **Fit the message** (`ICO-05`): show the actual product, place or kind of person served. Skip clichés (handshakes, people laughing at laptops, glowing brains).
- **Represent people fairly:** a range of ages, bodies and backgrounds that reflects the real audience, without tokenism.
- **Crop for the subject** (`ICO-06`): set `object-position` per image so faces survive every breakpoint; for avatars and headshots, crop with the eyes about one third from the top and never cut at the chin or forehead.
- **Consistency in a set:** same light direction, color temperature and treatment; apply one grade or duotone if sources differ.
- **Prefer real photography of the real thing.** Generated people and places in marketing must not pass as customers, staff or real locations, and follow the labeling rules in `generation-prompting.md`.

## 4. Licenses and records

- **Free photo libraries** usually grant broad commercial use without required attribution, but restrict reselling the photo unchanged, using it to imply endorsement, and depicting identifiable people or trademarks in misleading ways. Their premium or partner sections often carry different terms. Read the license page and record its date.
- **Paid stock:** check standard versus extended licenses (print-run limits, products for resale, templates), seats, and whether "editorial use only" applies (news-style images without releases: never for ads or product pages).
- **Releases:** model releases for recognizable people, property releases for private places and distinctive buildings or artworks.
- **Attribution:** give credit where the license requires it, and as good practice in captions or a credits page where it does not.
- **Record per asset:** source page URL, author, license name and version, date downloaded, release status, where used. Keep this next to the asset (`../../business-ops/references/brand-guidelines-and-audits.md`, "Organizing the asset library").
- **In mockups**, mark placeholder photos so they cannot reach production unnoticed (a `placeholder-` file prefix and a build check that fails if one ships).

## 5. Processing and serving

- **Keep one master** (largest original, sRGB, metadata intact privately) and derive everything else by script.
- **Derive widths** that match the layout: for example 480, 768, 1080, 1440, 1920 and 2560 for full-width images; fewer for small slots.
- **Formats:** AVIF first, WebP next, JPEG fallback for photos; PNG or lossless WebP for screenshots and flat art; SVG for icons and logos. Animated content belongs in video (`MP4` with `muted playsinline` for loops) rather than GIF where the destination allows.
- **Strip location and camera metadata** from published files unless deliberately kept.
- **Serve responsively** with intrinsic dimensions so nothing shifts:

```html
<picture>
  <source type="image/avif" srcset="/img/harbor-768.avif 768w, /img/harbor-1440.avif 1440w, /img/harbor-2560.avif 2560w" sizes="100vw">
  <source type="image/webp" srcset="/img/harbor-768.webp 768w, /img/harbor-1440.webp 1440w, /img/harbor-2560.webp 2560w" sizes="100vw">
  <img src="/img/harbor-1440.jpg" width="2560" height="1440" alt="Ferry leaving the harbor at dusk"
       style="object-fit: cover; object-position: 50% 40%" fetchpriority="high">
</picture>
```

  The largest image above the fold gets `fetchpriority="high"` and no lazy loading; images below the fold get `loading="lazy" decoding="async"`.
- **Pipelines:** process at build time for marketing sites with few changes; use an image service that resizes and converts by URL parameters for large, changing catalogs; a content system's image API for editor-uploaded media. Whichever you choose, cap source upload size, require alt text at upload, and set long cache lifetimes with fingerprinted file names.
- **Budget:** keep the total image weight of a typical marketing page under about 500 KB on mobile, and the hero under about 150-200 KB.

```bash
# derive widths and formats from one master (ImageMagick 7 and libavif's avifenc)
for w in 768 1440 2560; do
  magick harbor-master.jpg -strip -resize "${w}x>" -quality 82 "harbor-$w.jpg"
  magick harbor-master.jpg -strip -resize "${w}x>" -quality 78 "harbor-$w.webp"
  avifenc --min 20 --max 32 "harbor-$w.jpg" "harbor-$w.avif"
done
```

## 6. Alt text

- Describe what the image contributes in this context, in one sentence; do not start with "image of".
- Decorative backgrounds and duplicated icons get `alt=""` or `aria-hidden="true"`.
- Headshots: the person's name and role if the text does not already say it.
- Images of text: the full text.

## Done when

- [ ] One icon family and style per surface; icons use `currentColor`, meet 3:1 where meaningful, have names when icon-only, and duotone layers carry no meaning and survive forced colors.
- [ ] Every photo has a license record, releases where needed, and no placeholder ships.
- [ ] Crops keep subjects at every breakpoint; sizes and ratios match the use table.
- [ ] Images are served locally in modern formats with `srcset`, intrinsic dimensions, correct loading priority and stripped metadata, within the page budget.
- [ ] Alt text written for every meaningful image.
