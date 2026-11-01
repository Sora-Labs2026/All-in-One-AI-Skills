# iOS app icons and in-app icon assets

Read this to produce an app icon for iPhone and iPad (and the matching macOS, watchOS or visionOS icons), its dark and tinted appearances, the layered icons of Apple's 2025 design, and the icon images used inside an app: symbols, vector glyphs and the occasional 1x/2x/3x PNG set. It covers sizes, file formats, licensing and verification. Designing the mark itself follows `BRD-01` and `BRD-02` in `../../../references/ui-rules/branding.md`; icon consistency inside the interface follows `ICO-01` to `ICO-04`. Facts are as of Xcode 26 (2025).

Contents: what Xcode needs now · designing the app icon · appearances and layered icons · the full size set when you need it · in-app icons · licenses · checks · done when.

## What Xcode needs now

- **Since Xcode 14,** an iOS app icon can be a single 1024 × 1024 image; Xcode generates every smaller size at build time. Use the single-size option unless you hand-tune small sizes.
- **iOS 18 (2024)** added dark and tinted appearances of the home screen icon, supplied as extra images in the same app icon set.
- **Xcode 26 (2025)** adds Icon Composer, which builds layered `.icon` files (a background and foreground layers) that the system renders with the new translucent material and specular highlights in default, dark, tinted and clear styles, across Apple platforms from one source.
- **App Store requirement:** the default-appearance 1024 × 1024 icon must be a square, opaque PNG without an alpha channel; uploads with one are rejected. Do not round the corners yourself; the system applies the mask.

## Designing the app icon

- Start from vector artwork (SVG, PDF, or the design file) on a square canvas, full bleed, no pre-applied corner radius or drop shadow.
- One bold symbol at about 55-65% of the width, strong figure-ground contrast, no words, no thin strokes (`BRD-02`). The brand's logo is rarely a good icon as-is: simplify it.
- Preview at real sizes on device home screens next to other apps, on light, dark and photo wallpapers. Small sizes show what survives: Spotlight and Settings sizes are about 40 and 29 points.
- Keep the master file (vector source plus the 1024 export) in the repository with the export settings, so the icon can be rebuilt.

## Appearances and layered icons

**App icon set with appearances** (`Assets.xcassets/AppIcon.appiconset/Contents.json`, single size):

```json
{
  "images": [
    { "filename": "AppIcon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024" },
    { "appearances": [{ "appearance": "luminosity", "value": "dark" }],
      "filename": "AppIcon-1024-dark.png", "idiom": "universal", "platform": "ios", "size": "1024x1024" },
    { "appearances": [{ "appearance": "luminosity", "value": "tinted" }],
      "filename": "AppIcon-1024-tinted.png", "idiom": "universal", "platform": "ios", "size": "1024x1024" }
  ],
  "info": { "author": "xcode", "version": 1 }
}
```

- **Dark:** the foreground artwork adjusted for a dark background; follow Apple's current icon template for how the background is supplied.
- **Tinted:** a grayscale image; the system colors it with the user's tint, so the artwork's luminance carries all the shape.
- If you supply neither, the system derives them, often poorly; check how the derived versions look before deciding.

**Layered icons (Icon Composer):** export the background and each foreground element as separate layers (SVG or PNG), assemble them in Icon Composer, adjust per-style settings, and add the `.icon` file to the project as the app icon. Keep layers few and simple; the material adds depth, so do not paint it in. Preview every style and platform in Icon Composer before committing.

## The full size set when you need it

Generate individual sizes only for older toolchains, a non-Xcode build, or when the smallest sizes need hand-tuning.

| Use | Points | Scales | Pixels |
|---|---|---|---|
| iPhone home screen | 60 | 2x, 3x | 120, 180 |
| iPad home screen | 76 | 2x | 152 |
| iPad Pro home screen | 83.5 | 2x | 167 |
| Spotlight | 40 | 2x, 3x | 80, 120 |
| Settings | 29 | 2x, 3x | 58, 87 |
| Notifications | 20 | 2x, 3x | 40, 60 |
| App Store | 1024 | 1x | 1024 |

- Render each size from the vector source (`rsvg-convert -w 120 -h 120 icon.svg -o icon-120.png`) rather than shrinking the 1024 export; vector rendering at the target size keeps edges crisp. If you must downscale, use a high-quality filter (`magick icon-1024.png -filter Lanczos -resize 120x120 icon-120.png`, or `sips -z 120 120` on macOS).
- Hand-check the 40, 58 and 60 pixel files at 100%: details that vanish at those sizes should be simplified in a small-size variant of the artwork.
- Remove the alpha channel from the store icon explicitly (`magick in.png -background "#0F766E" -alpha remove -alpha off AppIcon-1024.png`, using the icon's own background color).

Other platforms use their own formats: Android adaptive icons (108 dp foreground and background layers of which the central 72 dp are visible, with key content inside the central 66 dp, plus a monochrome layer for themed icons) and web app manifest icons (192 and 512 pixel PNGs, with a maskable variant whose content sits inside the central safe zone). Do not reuse the iOS export unchanged.

## In-app icons

- **Prefer system symbols on Apple platforms.** `Image(systemName:)` and `UIImage(systemName:)` scale with Dynamic Type, match text weight, support monochrome, hierarchical, palette and multicolor rendering, and need no asset files.
- **Custom symbols:** export a symbol template from the SF Symbols app, draw your glyph in it, and import it into the asset catalog as a symbol image, so it behaves like a system symbol.
- **Vector assets:** add an SVG or PDF to an image set with "Preserve Vector Data" and a single scale; Xcode renders the scales it needs, and there are no 1x, 2x and 3x files to keep in step. Set the rendering intent to template when the icon should take the tint color:

```json
{
  "images": [{ "filename": "receipt.svg", "idiom": "universal" }],
  "info": { "author": "xcode", "version": 1 },
  "properties": { "preserves-vector-representation": true, "template-rendering-intent": "template" }
}
```

- **PNG sets** only when the source is raster: provide the point size at 2x and 3x (current iPhones and iPads use these scales), exactly double and triple the 1x pixel size, exported from the same artwork.
- **One family and one style** throughout the app (`ICO-01`), matched in weight to the text beside it; every icon-only control has an accessible label (`ICO-04`).

## Licenses

- **SF Symbols** may be used only in apps for Apple platforms, under Apple's license; they must not be used in app icons, logos or other trademark-related uses, and should not be rasterized for use on other platforms or the web.
- **Open icon sets** (many use MIT, ISC or Apache-2.0; some Creative Commons licenses require attribution) are fine in app icons and interfaces within their terms. Record the set, version and license in `credits.md`, and keep any required notice in the app's acknowledgements.
- **Fetching icons from an online icon service** at build or design time is a dependency and a network call; download the chosen icons once, commit them with their license, and do not rely on the service at runtime.
- An app icon must not imitate another company's icon or trademark (`../../legal-ready/GUIDE.md`).

## Checks

```bash
python3 <productcraft>/modules/creative-media/scripts/asset_catalog_check.py MyApp/Assets.xcassets
python3 <productcraft>/modules/creative-media/scripts/asset_catalog_check.py . --json   # every catalog in the project
```

The script reads each app icon set and image set without changing anything: Contents.json is valid; every referenced file exists and no stray files sit in a set; PNG sizes match size × scale; app icons are square; the default 1024 icon has no alpha channel (it also detects transparency declared with a tRNS chunk); image-set scales are consistent; dark and tinted appearances are reported. Exit 0 means clean, 1 means findings.

Then:
1. Build the app and look at the icon on a device or simulator home screen in light, dark and tinted modes, and in Spotlight and Settings.
2. For layered icons, review every style in Icon Composer's preview.
3. Run the App Store upload validation (Xcode's Validate App) before release; it catches icon problems the build accepts.

## Done when

- The icon is built from a vector source kept in the repository, with a 1024 opaque store icon and the appearances the product supports (or a reviewed `.icon` file).
- `asset_catalog_check.py` reports no errors or warnings, and the icon was viewed on a home screen in each appearance and at small sizes.
- In-app icons are system symbols, custom symbols or vector assets from one family, with accessible labels.
- Licenses for symbols and icon sets are recorded, and SF Symbols are not used in the app icon or outside Apple platforms.
