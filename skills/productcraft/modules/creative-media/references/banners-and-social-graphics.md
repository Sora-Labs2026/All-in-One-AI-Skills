# Banners, ad units and social graphics

Read this when making a fixed-size graphic that lives inside someone else's frame: a profile header or cover, a social post or story image, a link-preview card, a display ad, an email header, a website section banner, or a printed roll-up. The single-canvas craft (grid, hierarchy, type, print output) is `posters-and-canvas.md`; brand rules are `themes-and-brand-application.md`; generated backgrounds follow `generation-prompting.md`; a landing-page hero is page layout, not a banner (`../../ui-distiller/GUIDE.md`).

## Ground rules

- **Build the copy as live text**, in HTML and CSS or a layout tool, over a background. Never ask an image model to render the headline: generated text misspells, cannot be edited, and is invisible to translation and assistive technology.
- **Sizes and crop rules belong to each platform and change often.** Look up the current specification on the platform's help pages, record the date and the numbers you used, and design to them. The figures below are common at the time of writing, not guarantees.
- **One message, one action.** A banner is read in under two seconds.
- **Honest advertising.** No fake buttons, fake close icons, fake system dialogs, countdowns that reset, or claims without a source (`../../ethical-persuasion.md`, `../../legal-ready/references/honest-commerce.md`).

## 1. Common formats

| Placement | Typical pixels | Ratio | Notes |
|---|---|---|---|
| Link preview (Open Graph card) | 1200 × 630 | 1.91:1 | Shown small in feeds and chats; keep text large and central |
| Square feed post | 1080 × 1080 | 1:1 | Some feeds crop to 4:5 previews |
| Portrait feed post | 1080 × 1350 | 4:5 | Takes the most feed height |
| Vertical story or short video cover | 1080 × 1920 | 9:16 | Top and bottom ~250 px are covered by interface |
| Wide profile header | 1500 × 500 | 3:1 | Avatar overlaps one corner; crops differ on phones |
| Professional network banner | about 1584 × 396 | 4:1 | Avatar overlaps lower left |
| Video channel art | 2560 × 1440 | 16:9 | Only a central strip (about 1546 × 423) shows on every device |
| Display ads: medium rectangle, leaderboard, half page, mobile banner | 300 × 250, 728 × 90, 300 × 600, 320 × 50 | various | Standard ad-unit sizes; deliver at 2x too for sharp screens |
| Email header | 600 wide, 200-300 high | ~3:1 | Many clients block images; the message must survive without it |
| Site section banner | 1200-1920 wide | ~3:1 to 4:1 | Responsive: design the crop for mobile separately |

## 2. Safe zones and cropping

- Keep the headline, logo and action inside the central 70 to 80% of the canvas; leave at least 40 to 60 px from every edge on a 1080 px canvas.
- Mark platform overlays on a guide layer: avatar circles on profile headers, interface bars on stories, the play button and duration badge on video covers.
- When one design must serve several ratios, compose for the narrowest first and extend the background outward; do not scale a wide design into a square.
- Check every export against the platform's own preview (upload privately or use its preview tool) on a phone and a desktop.

## 3. Hierarchy and type

- **Three zones:** identity (logo or name), message (headline plus at most one supporting line), action (button-like label, URL or code).
- Headline at least 6% of the canvas height on social formats (about 64 px on a 1080 px square); never body text under 24 px at 1080 px wide or 12 px on a 300 × 250 ad.
- At most two typefaces; at most seven words per line and three lines of headline.
- Text contrast 4.5:1 against the actual pixels behind it, measured over the busiest part of an image (use a scrim: a gradient from 60% black to transparent behind the text is usually enough on photography). Verify with the sampler in step 6.
- Feed ads with mostly text are often shown less; keep text to a small share of the image and let the image carry the idea.
- The action reads as a verb and an outcome ("Start the free plan"), sits in a consistent position (lower right or lower center), and at 1080 px is at least 88 px tall so it scales to a comfortable 44 px when shown at half size.

## 4. Art direction options

Offer two or three directions that differ in kind, each tied to the purpose:

| Direction | Good for | Watch out for |
|---|---|---|
| Type-led: oversized headline on a flat field | Announcements, launches, events | Needs a strong typeface and short copy |
| Product-led: real screenshot or product photo, cropped tight | Features, releases | Small interface details become noise; crop to one area and enlarge |
| Photo-led: full-bleed image with a scrim | Lifestyle, travel, food | Licensing, contrast, crop on narrow ratios |
| Data-led: one big number with its source | Reports, milestones | The number must be sourced and dated |
| Illustration or geometric pattern | Brands with an illustration system | Off-brand if improvised |
| Duotone photo in brand colors | Series of posts that must match | Faces can look harsh; check skin tones |

For a series, fix the grid, type sizes, logo placement and color logic, and vary only the image and copy.

## 5. Build with HTML and export exactly

```html
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  :root { --bg:#0E2A2F; --ink:#F4F1EA; --accent:#E8B04A; }
  html,body { margin:0 }
  .banner { width:1200px; height:630px; position:relative; overflow:hidden;
            background:var(--bg); color:var(--ink); font-family:"Brand Sans", system-ui, sans-serif; }
  .banner img.bg { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
  .scrim { position:absolute; inset:0; background:linear-gradient(90deg, rgb(0 0 0 / .62), rgb(0 0 0 / 0) 70%); }
  .copy { position:absolute; left:72px; top:96px; width:620px; }
  h1 { font-size:72px; line-height:1.02; letter-spacing:-0.01em; margin:0 0 20px; }
  p { font-size:30px; line-height:1.3; margin:0 0 36px; }
  .cta { display:inline-block; background:var(--accent); color:#1A1205; font-weight:700;
         font-size:28px; padding:18px 30px; border-radius:10px; }
  .logo { position:absolute; right:64px; bottom:56px; height:40px; }
</style></head>
<body><div class="banner" id="banner">
  <img class="bg" src="bg.jpg" alt=""><div class="scrim"></div>
  <div class="copy"><h1>Plan the whole trip in one place</h1>
    <p>Routes, tickets and bookings, shared with everyone going.</p><span class="cta">Start planning</span></div>
  <img class="logo" src="logo-light.svg" alt="">
</div></body></html>
```

```js
// export.mjs: node export.mjs  (Playwright for Node)
import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 2 });
await page.goto(new URL("./banner.html", import.meta.url).href);
await page.evaluate(() => document.fonts.ready);           // never export with a fallback font
await page.locator("#banner").screenshot({ path: "out/link-card_1200x630@2x.png" });
await browser.close();
```

- Export at 2x for screens, then downscale a 1x copy if the platform wants exact pixels. Re-encode photographic results as high-quality JPEG or WebP to meet file-size limits; keep flat graphics as PNG.
- Store the HTML and data, not only the image, so the next variant is a text edit.
- File names: `{placement}_{campaign}_{variant}_{width}x{height}.{ext}`, grouped by campaign folder.

## 6. Check before delivery

```python
# contrast_at.py: sample the rendered pixels behind a text box and report the worst ratio.
# python3 contrast_at.py out/link-card.png 72 96 692 400 F4F1EA
import sys
from PIL import Image
def lum(c):
    c = [v / 255 for v in c[:3]]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
img, (x0, y0, x1, y1), ink = Image.open(sys.argv[1]).convert("RGB"), map(int, sys.argv[2:6]), sys.argv[6]
L_ink = lum([int(ink[i:i + 2], 16) for i in (0, 2, 4)])
worst = min((max(L_ink, lum(p)) + 0.05) / (min(L_ink, lum(p)) + 0.05)
            for p in img.crop((x0, y0, x1, y1)).resize((64, 64)).getdata())
print(f"worst contrast {worst:.2f}:1")
```

Sample a box that covers the text area but excludes the glyphs themselves (or render once with the text hidden); the worst background pixel gives a conservative ratio.

- Pixel size and file weight match the specification you recorded.
- Viewed at real display size: a link card at about 500 px wide, a story on a phone, an ad unit at 1x.
- Safe zones clear on the platform preview; nothing important under an avatar or interface bar.
- Spelling, dates, prices and claims proofread against their sources.
- Alt text drafted for platforms that accept it: what the graphic says and shows, including the headline text.

## 7. Animated banners and display ads

- Keep animation short (about 15 seconds or less in total), loop at most three times, and end on a static frame that carries the full message.
- No flashing above three times per second and no large high-contrast strobes (WCAG 2.3.1); avoid rapid full-frame color changes entirely.
- Respect the ad network's file size, frame rate and click-tag rules; test the click-through in the network's preview.
- For animated images (GIF, animated WebP) see `../../documents/references/animated-media.md`; for video covers and clips see `video-editing.md`.

## 8. Print banners

- Build at final size or an exact scale, at 300 ppi at final size for close viewing and 100-150 ppi for large formats seen from meters away.
- Add 3 to 5 mm bleed on every side (more for roll-ups and fabric, per the printer), keep text 10 mm or more inside the trim, and supply crop marks only if the printer asks.
- Convert to the printer's CMYK profile at export (`posters-and-canvas.md`, "Print specifics") and proof the converted file: saturated screen blues and greens shift noticeably.
- Size type for distance: roughly 25 mm of letter height for every 10 m of reading distance.

## Done when

- [ ] Each format's current size and crop rules were looked up, dated and used; safe zones verified on the platform preview.
- [ ] Copy is live text with at most two typefaces; worst-case contrast behind text measured at 4.5:1 or better.
- [ ] Exports match pixel size and weight limits; source HTML kept with the images.
- [ ] Animated versions stay under the flash limit and end on a complete static frame.
- [ ] Claims sourced, images licensed, alt text supplied where the platform allows.
