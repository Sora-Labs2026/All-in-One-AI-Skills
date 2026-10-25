# UI rules: Dark mode

Dark palettes, elevation, text tiers, accents, states and theme choice. Rule IDs use the `DRK-` prefix; cite them in change reports.

## DRK-01. Build dark mode as its own palette, not an inversion

**Why:** Inverting light colors produces glare and broken hierarchy; a dark theme needs its own tuned values.

- **Do:** Implement themes by remapping semantic color tokens per mode, so components need no theme-specific code.
- **Do:** Keep brand hues recognizable but retune their lightness and saturation for dark surfaces.
- **Avoid:** Automatic inversion of the light palette, or hard-coded colors that force separate dark components.

## DRK-02. Use a near-black base, not pure black

**Why:** Dark gray reduces harsh contrast and leaves room to show depth with lighter surfaces.

- **Do:** Use a near-black base such as #121212, or a dark tinted toward the brand hue at about the same lightness (such as #110F1B).
- **Do:** Fill cards with a slightly lighter surface rather than outlining them.
- **Avoid:** Pure #000000 backgrounds, #000000 cards on #000000 backgrounds, or "colored blacks" so dark (such as #03000D) that they look and behave like pure black.
- **Note:** A true-black option can suit OLED-focused media apps; offer it as a setting, not the default.

## DRK-03. Show elevation with lighter surfaces

**Why:** Shadows barely show on dark backgrounds, so lightness must communicate which layer is on top.

- **Do:** Step surfaces lighter as they rise, for example base #121212, card #1E1E1E, app bar #272727, menu #2E2E2E, dialog #383838.
- **Do:** Expose these as elevation tokens so components pick the right surface automatically.
- **Avoid:** One dark color for background, cards and dialogs, or black drop shadows as the only separation.

## DRK-04. Use dimmed whites for text tiers

**Why:** Pure white on near-black glares; graded off-whites keep reading comfortable and preserve hierarchy.

- **Do:** Define text tiers as white alpha over the current surface: about 87% for primary text, 60% for secondary text and 38% only for disabled elements (#E0E0E0, #A0A0A0 and #6C6C6C on #121212).
- **Do:** If tiers are fixed or hue-tinted grays, check each on the lightest surface it can sit on: #A0A0A0 passes from #121212 to #2E2E2E but falls below 4.5:1 on a #383838 dialog, which needs about #AAAAAA or lighter.
- **Do:** Keep all text people read, including placeholders, captions, timestamps, chart ticks and inactive tab labels, at 4.5:1 or more; on near-black bases that means no dimmer than about #808080, and 60% white is the safer floor.
- **Avoid:** Long body text in pure #FFFFFF at bold weight on a dark base.
- **Avoid:** Gray hexes tuned on the base surface and reused unchanged in menus and dialogs, or meta text in the disabled tier or thin weights, which commonly falls to 2-3:1.
- **Note:** The 38% tier is about 3.6:1 on #121212; it is acceptable only for disabled controls, which WCAG exempts.

## DRK-05. Retune accent colors for dark surfaces

**Why:** A brand color tuned for white backgrounds often loses contrast or vibrates on dark ones.

- **Do:** Define separate dark-theme accent tokens, usually lighter and less saturated tones of the brand hue: one for fills and a lighter one for accent-colored text such as links, active tabs and outlined-button labels.
- **Do:** Check the button fill against the surface (at least 3:1) and the label against the fill (at least 4.5:1); once the accent fill is light, switch its label to a near-black on-accent token (white on #7FA6E8 is about 2.5:1, near-black about 7.5:1).
- **Do:** Soften semantic colors the same way: on #121212, red #DC2626 is about 3.9:1 and fails for small text, while #F87171 reaches about 6.8:1.
- **Do:** Check accent and status text on every elevation step it can appear on, not only the base: #CF6679 is 5.2:1 on #121212 but about 3.3:1 on a #383838 dialog.
- **Avoid:** Reusing the saturated light-theme brand color unchanged, or deep 600-900 tones that sink into dark cards.
- **Avoid:** White labels on a lightened accent fill, or one accent token used for both fills and small text.

## DRK-06. Keep interactive states visible on dark surfaces

**Why:** Subtle hover and pressed changes that work on white often vanish on dark backgrounds.

- **Do:** Give buttons and links a clear hover and pressed change: a color shift, inversion, border or icon motion.
- **Do:** Show a 2px or thicker high-contrast focus ring on every focusable element, drawn with outline and outline-offset rather than box-shadow alone, which forced-colors mode removes.
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
- **Do:** Ship dark variants of illustrations and dim bright photographs slightly in the dark theme (for example filter: brightness(.9)).
- **Do:** Replace shadow-based separation with lighter surfaces or borders in the dark theme.
- **Do:** Give embedded frames and players a container in the surface color, set color-scheme on the embedding page, and reveal the iframe on its load event (or show a dark poster first) so it never flashes white.
- **Avoid:** A black logo disappearing on a dark card.
- **Avoid:** Headlines or hero copy fixed to white and carried into the light theme; route their color through the theme's text token.

## DRK-09. Separate dark surfaces with hairlines and one bright primary

**Why:** On near-black screens, depth reads best from lighter surfaces and faint borders, and one bright action anchors the screen.

- **Do:** Separate cards and popovers with 1px borders at about 6-12% white in addition to lighter surface steps; use alpha white so one border token works on every surface.
- **Do:** Give inputs, outlined buttons and other control boundaries at least 3:1 against the surface (about #656565 on #18181B), since hairlines reach only about 1.2-1.5:1.
- **Do:** Make the primary action a light or single-accent fill and keep secondary actions outlined or ghost.
- **Do:** Raise small label grays until they reach 4.5:1.
- **Avoid:** Several competing accents on one dark screen, or light-theme drop shadows used as the elevation cue.
- **Avoid:** Card hairlines reused as the outline of inputs or outlined buttons.

## DRK-10. Name the theme toggle and tune each theme

**Why:** A theme switch must say what it does, and effects tuned for one theme rarely work unchanged in the other.

- **Do:** Make the toggle a button with role="switch" and aria-checked, or aria-pressed, plus a visible label or accessible name naming the mode.
- **Do:** Default to prefers-color-scheme, persist the choice, and swap a full token set (text, surfaces, CTA, glows, shadows) per theme.
- **Do:** Re-check hero text and primary button contrast in every theme.
- **Avoid:** Icon-only toggles without a name, or one CTA color that loses contrast in the other theme.

## DRK-11. Keep theme transitions brief and optional

**Why:** A transition that grows from the toggle links cause and effect, but it must never slow the switch down.

- **Do:** Wrap the theme change in document.startViewTransition() and animate ::view-transition-new(root) from clip-path: circle(0 at x y) to circle(r at x y) at the toggle's center, with r = Math.hypot() to the farthest viewport corner.
- **Do:** Give the keyframes both a start and an end circle so the reveal does not snap, and set animation: none on ::view-transition-old(root) so the old snapshot does not crossfade.
- **Do:** Ease the radius out over about 300-400ms so most of the screen changes early, and keep the whole reveal under about 500ms.
- **Do:** Swap instantly when the API is missing or prefers-reduced-motion is set, and update the toggle's own state and label immediately.
- **Avoid:** Full-screen overlays that block input during the change.
- **Avoid:** Reveals of 600ms or longer, or a linear radius that leaves most of the screen unswitched until late.
