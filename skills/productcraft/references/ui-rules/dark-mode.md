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

## DRK-09. Separate dark surfaces with hairlines and one bright primary

**Why:** On near-black screens, depth reads best from lighter surfaces and faint borders, and one bright action anchors the screen.

- **Do:** Separate cards and popovers with 1px borders at about 6-12% white in addition to lighter surface steps.
- **Do:** Make the primary action a light or single-accent fill and keep secondary actions outlined or ghost.
- **Do:** Raise small label grays until they reach 4.5:1.
- **Avoid:** Several competing accents on one dark screen, or light-theme drop shadows used as the elevation cue.

## DRK-10. Name the theme toggle and tune each theme

**Why:** A theme switch must say what it does, and effects tuned for one theme rarely work unchanged in the other.

- **Do:** Make the toggle a button with role="switch" and aria-checked, or aria-pressed, plus a visible label or accessible name naming the mode.
- **Do:** Default to prefers-color-scheme, persist the choice, and swap a full token set (text, surfaces, CTA, glows, shadows) per theme.
- **Do:** Re-check hero text and primary button contrast in every theme.
- **Avoid:** Icon-only toggles without a name, or one CTA color that loses contrast in the other theme.

## DRK-11. Keep theme transitions brief and optional

**Why:** A transition that grows from the toggle links cause and effect, but it must never slow the switch down.

- **Do:** Wrap the theme change in document.startViewTransition() and expand ::view-transition-new(root) with clip-path from a circle at the toggle's center.
- **Do:** Swap instantly when the API is missing or prefers-reduced-motion is set, and keep any reveal under about 500ms.
- **Avoid:** Full-screen overlays that block input during the change.
