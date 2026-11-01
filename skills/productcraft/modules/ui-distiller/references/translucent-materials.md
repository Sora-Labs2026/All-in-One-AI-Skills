# UI Distiller: Translucent materials ("glass") done accessibly

Read this when a design calls for translucent, blurred surfaces: glass navigation bars and toolbars on the web, or Apple's 2025 design language (introduced as Liquid Glass with iOS 26, iPadOS 26 and macOS 26) in a native app. It covers where glass belongs, how to keep text legible over unknown content, fallbacks for user settings, performance, and how to verify. Glass is an optional treatment (`STY-05`, `STY-15` in `../../../references/ui-rules/style-options.md`); taste detector 22 in [taste.md](taste.md) explains why it is suspect by default.

## Where glass belongs

- **On the layer that floats above content:** tab bars, toolbars, navigation bars, floating action groups, popovers, sheets, menus. Seeing the content move beneath tells people where they are.
- **Not on content:** cards, list rows, article text, form panels and tables stay opaque. A translucent card over a translucent bar is glass on glass; avoid it.
- **One level at a time.** Do not stack glass surfaces; each layer halves the predictability of what is behind the text.
- **Tint carries meaning, not decoration.** A tinted glass control should be the primary action, not a color accent repeated across the screen (`COL-02`).

## Legibility: design for the worst backdrop

Text on glass is drawn over whatever scrolls beneath it, so its contrast is not one number. The composited surface color is `tint × alpha + backdrop × (1 − alpha)`, computed per channel in sRGB the way browsers composite. Blur and saturation only mix and push backdrop colors within the RGB range, so the worst case is set by the extremes of that range: white behind light-on-dark text, black behind dark-on-light text.

Compute the minimum tint opacity instead of guessing:

```bash
# White text on a black tint, any backdrop: the smallest alpha that keeps 4.5:1
python3 <productcraft>/modules/ui-distiller/scripts/glass_contrast.py --text "#FFFFFF" --tint "#000000" --solve --min 4.5
# Secondary text at 80% opacity, checked at a chosen alpha
python3 <productcraft>/modules/ui-distiller/scripts/glass_contrast.py --text "#FFFFFF" --text-alpha 0.8 --tint "#101418" --alpha 0.6
# Only the colors that can actually appear behind the bar (sampled from the real imagery)
python3 <productcraft>/modules/ui-distiller/scripts/glass_contrast.py --text "#111111" --tint "#FFFFFF" --alpha 0.4 \
  --backdrop "#2B4A6F" --backdrop "#E8D9C4" --backdrop "#F7F7F5"
```

For white text on black tint the answer is about 0.54 for 4.5:1, which matches the guidance in `STY-05`. Use the "any backdrop" result unless the content beneath is fixed and known; a user-uploaded photo or a video can be anything. Then confirm on real screenshots over the worst content you have: a white photo, a black video frame, dense text.

Ways to need less tint: put the text on a slightly more opaque inner pill; increase weight and size (large text needs 3:1, `COL-01`); add a subtle shadow behind glyphs as reinforcement (never as the only fix); or switch the bar to opaque once content scrolls beneath it (`STY-05`).

## Web implementation

```css
.toolbar {
  background: var(--surface);                      /* solid default: legible everywhere */
  border: 1px solid transparent;                   /* becomes a visible edge in forced-colors mode */
}
@supports (backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)) {
  .toolbar {
    background: rgb(16 20 24 / 0.6);               /* alpha from glass_contrast.py, not by eye */
    -webkit-backdrop-filter: blur(16px) saturate(140%);
    backdrop-filter: blur(16px) saturate(140%);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.12);   /* top highlight reads as a glass edge */
  }
}
@media (prefers-reduced-transparency: reduce), (prefers-contrast: more) {
  .toolbar { background: var(--surface); -webkit-backdrop-filter: none; backdrop-filter: none; }
}
@media (prefers-contrast: more) { .toolbar { border-color: var(--border-strong); } }
@media (forced-colors: active) { .toolbar { border-color: CanvasText; } }
```

- **Support (2025):** `backdrop-filter` works in all current engines (Safari still accepts the prefixed form, so write both). `prefers-reduced-transparency` is exposed only in Chromium-based browsers; Safari and Firefox do not report it to pages, so the default you ship must already be legible.
- **Forced colors** (Windows contrast themes) replaces backgrounds; the transparent border trick keeps an edge visible.
- **Dark and light themes** need their own tint and alpha; re-run the calculation for each pair.
- **Refraction effects** with SVG displacement maps work only in Chromium through `backdrop-filter: url()`; ship them as enhancement over the plain blur (`STY-15`).
- **Header over a hero:** start transparent, switch to glass or solid when content scrolls under it, using an IntersectionObserver sentinel or a scroll-driven animation (`STY-05`).

## Performance

- `backdrop-filter` re-samples and blurs everything behind the element whenever that content changes, so cost grows with the element's area, the blur radius and how much moves beneath it (scrolling lists, video).
- Keep glass to small floating chrome; never put it over full-screen video or on large scrolling panels. Do not animate the blur radius (`MOT-01`).
- Limit how many glass surfaces are visible at once, and profile scrolling on a mid-range phone with the Performance panel and Paint flashing ([motion-engineering.md](motion-engineering.md)).

## Apple platforms (iOS 26, iPadOS 26, macOS 26; Xcode 26, 2025)

- **Use the system components first.** Tab bars, toolbars, navigation bars, sheets, popovers and menus adopt the new material automatically when built with the 26 SDKs. Remove custom bar backgrounds and color fills that would hide it.
- **Custom glass in SwiftUI:** `.glassEffect()` applies the regular variant in a capsule; customize with a variant, tint, interactivity and shape, for example `.glassEffect(.regular.tint(.teal).interactive(), in: .rect(cornerRadius: 16))`. Group nearby glass views in `GlassEffectContainer(spacing:)` so they render together and can merge; give views a `.glassEffectID(_:in:)` with a shared `@Namespace` to morph between states inside `withAnimation`. Buttons can use `.buttonStyle(.glass)` or `.glassProminent`.
- **UIKit:** `UIGlassEffect` in a `UIVisualEffectView` (with `isInteractive` for touch response) and `UIGlassContainerEffect` for groups.
- **Back-deployment:** wrap new APIs in `if #available(iOS 26, *)` and fall back to the older materials (`.regularMaterial`, `.thinMaterial`) or opaque backgrounds on earlier versions.
- **Interactive only where it responds:** `.interactive()` belongs on controls, not on static labels.
- **Accessibility settings:** the system material becomes frostier and more opaque with Reduce Transparency, gains borders and contrast with Increase Contrast, and calms its motion with Reduce Motion. Custom effects must do the same: read `@Environment(\.accessibilityReduceTransparency)`, `\.colorSchemeContrast` and `\.accessibilityReduceMotion`, and switch to solid surfaces and simple transitions.
- **Widgets** appear in full-color, tinted and clear Home Screen styles: read `widgetRenderingMode`, mark accent content with `.widgetAccentable()`, and check every mode.
- **App icons** use layered glass in the 2025 design; see `../../creative-media/references/ios-app-icons.md`.

## Android

Material Design uses tonal, opaque surfaces rather than blur. Android 12 (API 31) added background blur for windows (`Window.setBackgroundBlurRadius`), but the system can turn cross-window blur off at runtime (battery saver, low-end devices); listen for that and fall back to a dimmed opaque surface. `RenderEffect.createBlurEffect` blurs a view's own content, not what is behind it. Default to opaque surfaces on Android unless the brand requires otherwise.

## Check it

1. Worst-case contrast computed with `glass_contrast.py` for every text tier on every glass surface, in each theme; numbers recorded in the report.
2. Screenshots over the worst real content (bright photo, dark video frame, dense text) at 390px and 1440px.
3. Fallbacks seen working: no `backdrop-filter` (test with the property disabled in DevTools), `prefers-contrast: more`, forced colors, and on Apple platforms Reduce Transparency, Increase Contrast and Reduce Motion, checked with Accessibility Inspector.
4. Focus rings visible over glass (two-tone ring, `BTN-02`).
5. Scrolling profiled on a mid-range device with glass visible; no dropped frames attributable to the blur.

## Done when

- Glass is used only on floating navigation and controls, one layer deep.
- Every text tier meets its contrast minimum over the worst case, by calculation and on screenshots.
- Solid fallbacks exist for unsupported engines and for every relevant user setting, and were exercised.
- Performance was profiled on a real or throttled device.
