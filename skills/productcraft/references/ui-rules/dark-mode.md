# UI rules: Dark mode

Dark palettes, elevation, text tiers, accents, states and theme choice. Rule IDs use the `DRK-` prefix; cite them in change reports.

## DRK-01. Build dark mode as its own palette, not an inversion

**Why:** Inverting light colors produces glare and broken hierarchy; a dark theme needs its own tuned values.

- **Do:** Implement themes by remapping semantic color tokens per mode, so components need no theme-specific code.
- **Do:** Keep brand hues recognizable but retune their lightness and saturation for dark surfaces.
- **Avoid:** Automatic inversion of the light palette, or hard-coded colors that force separate dark components.

## DRK-02. Use a near-black base, not pure black

**Why:** Dark gray reduces harsh contrast and leaves room to show depth with lighter surfaces.

- **Do:** Use a near-black base such as #121212, or a dark tinted toward the brand hue.
- **Do:** Fill cards with a slightly lighter surface rather than outlining them.
- **Avoid:** Pure #000000 backgrounds, or #000000 cards on #000000 backgrounds.
- **Note:** A true-black option can suit OLED-focused media apps; offer it as a setting, not the default.

## DRK-03. Show elevation with lighter surfaces

**Why:** Shadows barely show on dark backgrounds, so lightness must communicate which layer is on top.

- **Do:** Step surfaces lighter as they rise, for example base #121212, card #1E1E1E, app bar #272727, menu #2E2E2E, dialog #383838.
- **Do:** Expose these as elevation tokens so components pick the right surface automatically.
- **Avoid:** One dark color for background, cards and dialogs, or black drop shadows as the only separation.

## DRK-04. Use dimmed whites for text tiers

**Why:** Pure white on near-black glares; graded off-whites keep reading comfortable and preserve hierarchy.

- **Do:** Use about 87% white (#E0E0E0) for primary text, about 60% (#A0A0A0) for secondary text and about 38% only for disabled elements.
- **Do:** Or use light grays tinted toward the background hue, and check each tier for contrast.
- **Avoid:** Long body text in pure #FFFFFF at bold weight on a dark base.
- **Note:** The 38% tier is below 4.5:1; it is acceptable only for disabled controls.

## DRK-05. Retune accent colors for dark surfaces

**Why:** A brand color tuned for white backgrounds often loses contrast or vibrates on dark ones.

- **Do:** Define a separate dark-theme accent token, usually a lighter and less saturated tone of the brand hue.
- **Do:** Check the button fill against the surface (at least 3:1) and the label against the fill (at least 4.5:1).
- **Do:** Soften semantic colors the same way, for example a lighter error red.
- **Avoid:** Reusing the saturated light-theme brand color unchanged, or deep 600-900 tones that sink into dark cards.

## DRK-06. Keep interactive states visible on dark surfaces

**Why:** Subtle hover and pressed changes that work on white often vanish on dark backgrounds.

- **Do:** Give buttons and links a clear hover and pressed change: a color shift, inversion, border or icon motion.
- **Do:** Show a 2px or thicker high-contrast focus ring on every focusable element.
- **Avoid:** A tiny opacity change as the only hover cue, or removed focus outlines.

## DRK-07. Let people choose the theme

**Why:** Preference for light or dark varies by person and context.

- **Do:** Default to the system setting (prefers-color-scheme) and offer a Light / Dark / System choice that persists.
- **Do:** Build colors as semantic tokens so both themes stay in sync.
- **Avoid:** Dark-only or light-only products with no way to switch.

## DRK-08. Check every screen in both themes

**Why:** Assets designed only against white, such as dark logos and shadows, silently break in dark mode.

- **Do:** Review every screen end to end in dark mode before shipping.
- **Do:** Provide a light logo variant or an SVG that uses currentColor.
- **Do:** Replace shadow-based separation with lighter surfaces or borders in the dark theme.
- **Avoid:** A black logo disappearing on a dark card.
