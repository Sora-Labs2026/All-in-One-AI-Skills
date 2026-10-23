# UI rules: Style options

Optional visual treatments. Use only when the brand or the request calls for them, never as defaults. Rule IDs use the `STY-` prefix; cite them in change reports.

> These treatments are **never defaults**. Use one only when the project's brand or the request asks for it, and keep every rule in the other files (contrast, targets, focus, reduced motion) in force.

## STY-01. Commit to one visual style

**Why:** A consistent style gives a product a coherent personality; mixing styles looks unplanned.

- **Do:** If a named style is wanted, apply its traits consistently: glass (translucent blurred panels with thin light borders), soft extruded (controls in the background hue shaped by paired light and dark shadows), bold flat (saturated fills, thick dark outlines, hard offset shadows) or flat minimal (solid fills, no depth effects).
- **Do:** Verify contrast for text, controls and focus states in the chosen style.
- **Avoid:** Mixing several styles in one product.
- **Note:** Translucent and soft-extruded styles often fail contrast for controls and text; check every state.

## STY-02. Floating tab bar

**Why:** A floating, rounded tab bar can give a mobile app a distinctive feel while keeping destinations in reach.

- **Do:** Inset a fully rounded bar from the screen edges above the safe area, with a soft shadow and 4-5 destinations.
- **Do:** Mark the active tab with a filled icon and label inside a contrasting pill, and keep labels or accessible names on every tab.
- **Do:** Add bottom padding to the scroll container so the bar never hides content.
- **Avoid:** Hiding labels on inactive tabs without accessible names, or more than five destinations.

## STY-03. Emphasized create action in the tab bar

**Why:** One larger accent button can separate an app's core create action from ordinary navigation.

- **Do:** Use it for exactly one action (create post, add entry), with an accessible label.
- **Do:** Prefer a detached floating button at the trailing edge over a slot inside the row of destinations.
- **Avoid:** Emphasizing more than one item, or using the emphasized slot for a regular destination.

## STY-04. Signature glow button

**Why:** A luminous, layered treatment can make one special action, such as an AI "Generate" button, feel distinct.

- **Do:** Build it from consistent layers: a radial gradient fill, a fading 1px highlight stroke, soft inset highlights and tinted drop shadows.
- **Do:** Verify the label meets 4.5:1 against the lightest part of the gradient.
- **Avoid:** Using it on more than one action per screen, or heavy blur and blend layers on low-end devices.

## STY-05. Translucent blur on floating chrome

**Why:** Blurred translucent bars and inputs over imagery add depth while keeping context visible.

- **Do:** Use a translucent fill with backdrop-filter blur, plus a subtle gradient so text stays readable.
- **Do:** Provide a solid fallback for reduce-transparency settings and browsers without backdrop-filter.
- **Avoid:** Stacked heavy blurs that cost performance or drop text contrast.

## STY-06. Additive glows on dark backgrounds

**Why:** Decorative light effects look natural when they brighten what is beneath them instead of sitting on top as opaque blobs.

- **Do:** Build glows from a small bright core and a larger dim halo with an additive blend (mix-blend-mode: plus-lighter or screen).
- **Do:** Keep glows behind content, never behind body text.
- **Avoid:** Glows that reduce legibility or cost noticeable rendering time.

## STY-07. Glossy showcase icon tile

**Why:** A layered gradient tile with a soft halo and glow gives hero or store artwork depth and polish.

- **Do:** Use a square tile with continuous corners at about 24% of its size, a gradient between neighboring hues and a white glyph.
- **Do:** Add a faint, larger halo tile and a blurred same-gradient glow beneath it, built with pseudo-elements and filter: blur().
- **Avoid:** Using this treatment for small in-app icons, or many large blur filters on performance-sensitive pages.

## STY-08. Tint surfaces with colors from the imagery

**Why:** Echoing a product photo's dominant color in its card gives a cohesive, characterful look.

- **Do:** Use a light tint of the image's dominant color for the card background and a darker shade of the same hue for text and icons.
- **Do:** Verify text contrast on the tint.
- **Avoid:** Tints strong enough to weaken the product or the text, or this treatment in dense data UI.

## STY-09. Atmospheric background imagery

**Why:** A deeply cropped, toned-down image used full-bleed adds mood without adding controls.

- **Do:** Crop a high-resolution image until it reads as texture, lower its intensity and blend it with a color layer that matches the palette.
- **Do:** Add an overlay wherever text or a logo sits on top and check contrast.
- **Avoid:** Upscaled low-resolution images, or heavy images on pages where load time matters.

## STY-10. Overlap elements for depth

**Why:** Slight overlaps, such as an avatar crossing the edge of a cover image, create layering that ties sections together.

- **Do:** Let avatars overlap cover images with a ring in the surface color, and use overlapping avatar stacks for groups of people.
- **Avoid:** Overlaps that hide content or shrink touch targets.
