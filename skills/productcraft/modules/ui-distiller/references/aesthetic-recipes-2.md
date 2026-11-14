# UI Distiller: Aesthetic recipes, part 2

Read this when someone asks for a look by its name ("make it claymorphic", "risograph", "like an arcade cabinet", "a bento grid", "agent-first") and the fourteen complete directions in [style-catalog.md](style-catalog.md) do not already cover it. Each recipe here is a compact, original starting point: mood, where it fits and fails, palette roles with measured contrast, a type pairing, shape and depth, motion, the signature detail, and an accessibility note. A recipe is a seasoning for a product, not a theme to paste; brand tokens and the request still win, and the taste detectors in [taste.md](taste.md) still apply.

## How to use a recipe

- **Pick one.** One recipe per product (`STY-01` in [style-options.md](../../../references/ui-rules/style-options.md)). A request that names two ("neobrutalist but premium") gets one base recipe and one borrowed trait, named in the report.
- **Map roles to tokens.** Palette roles use the same names as the catalog: `bg`, `surface`, `ink` (`--text`), `ink-2` (`--text-2`), `accent`, `on-accent`, plus named fields. Reference only tokens in components.
- **Contrast is measured, not assumed.** Every ratio below was computed with the WCAG 2.x relative-luminance formula; reuse the snippet in the catalog's "Applying a direction" section after any change. Normal text needs 4.5:1, large text (24px, or 18.7px bold) and control boundaries 3:1. A fill marked "boundary" is used with a border or label that carries the contrast, never as text.
- **Fonts.** Every face named is published under the SIL Open Font License 1.1 (check the license file in the version you download). Decorative display faces are for 32px and above; body text always uses a plain, legible face. Load only the weights in use, subset, `font-display: swap`.
- **Motion.** Durations stay in the `MOT-02` budget and every recipe keeps the `MOT-04` reduced-motion path: under `prefers-reduced-motion: reduce`, loops stop, parallax and tilt flatten, and state changes become instant or a short crossfade. Nothing flashes more than three times per second (WCAG 2.3.1). Engineering detail lives in [motion-engineering.md](motion-engineering.md).
- **Imagery.** Generated textures, mascots, illustrations and backgrounds follow [generation-prompting.md](../../creative-media/references/generation-prompting.md). Textures stay under body text at 6% opacity or less, or not at all.
- **Game, film and toy looks.** Recipes in the games family describe genres, never a specific title. Characters, sprites, sounds, logos, piece sets and maze layouts that belong to a franchise need a license; without one, draw your own.
- **Delight stays optional.** Easter eggs, sounds and playful animation never block a task and never sit in error recovery (see [ethical-persuasion.md](../../ethical-persuasion.md) for the no-pressure rules).

## Already covered elsewhere

| Look requested | Where it lives | What this file adds |
|---|---|---|
| Brutalism | style-catalog, Brutalist | Use recipe 14 when the brief says "friendly" or "colorful" brutalism. |
| Neumorphism | style-catalog, Soft tactile | Same safeguards apply to claymorphism (recipe 19). |
| Editorial, magazine | style-catalog, Editorial reading and Swiss grid | Poster-like editorial: recipe 12. |
| Print-inspired books and reports | Editorial reading, Swiss grid | Paper surfaces and print styles: recipe 27. |
| Flat | style-catalog, Flat poster (campaigns) and Calm product (apps) | For flat product UI, take Calm product, remove every resting shadow and separate layers by tone steps of at least 4% lightness. |
| Glassmorphism | [translucent-materials.md](translucent-materials.md) | Keep glass on floating chrome, blur 16-24px, a 1px top edge at about 30% white, and solve the tint with `glass_contrast.py`. |
| Café, cozy food and drink | style-catalog, Warm organic | Menu first, prices and opening hours above the fold, ordering in one tap, photography of the real counter. |

## A. Product and work tools

### 1. Agent workspace
- **Mood:** calm, conversational, outcome-first; the person states a goal and supervises. **Fits:** assistants, agent consoles, research and automation tools. **Fails:** where people need direct manipulation of many objects (spreadsheets, editors) as the main task.
- **Palette:** bg `#F6F6F3`, surface `#FFFFFF`, ink `#18191C` (16.2:1 on bg), ink-2 `#5B5E66` (6.0:1), accent `#2346B8` (7.3:1 on bg, also link text), on-accent `#FFFFFF` (8.0:1). Status uses the product's semantic set, always with an icon and a word.
- **Type:** Geist for interface and answers, Geist Mono for tool output, file paths and diffs. Answer text 16px, line height 1.55, measure 68-72ch.
- **Shape and depth:** composer as the hero, 56px minimum height, 12-16px radius, one soft shadow (`0 1px 2px rgb(0 0 0 / .06), 0 8px 24px -12px rgb(0 0 0 / .18)`); messages without bubbles; a step list with five states (queued, running, waiting for approval, done, failed); result cards with 8px radius and a 1px border.
- **Motion:** stream text in word or sentence chunks, never per-character animation; a running step shows a 1.2s indeterminate bar that becomes a static "Running" label under reduced motion; cards enter with a 160ms fade.
- **Signature:** a plan the person can read, edit and approve before anything irreversible happens, and a Stop control visible the whole time the agent runs.
- **Access:** `aria-live="polite"` on the step status only, never on the streaming answer; Enter sends, Shift+Enter adds a line, Esc stops; approval dialogs name the exact action and its cost. Goes generic with a centered greeting, four suggestion chips and a gradient orb.

### 2. Neutral utility kit
- **Mood:** monochrome, quiet, built from copy-in components on a utility-first CSS base. **Fits:** SaaS apps, internal tools, developer products. **Fails:** brands that need to be recognized; left untouched it is the most common look on the web.
- **Palette, light:** bg `#FFFFFF`, surface `#F7F7F8`, ink `#0C0C0E` (19.5:1), ink-2 `#5E5F66` (6.4:1), primary button `#18181B` with `#FAFAFA` text (17.0:1), input border `#8C8D95` (3.3:1). **Dark:** bg `#0A0A0C`, surface `#151518`, ink `#F2F2F3` (17.7:1), ink-2 `#A3A3AB` (7.9:1), primary `#EDEDEF` with `#111113` text (16.1:1), input border `#66666F` (3.5:1).
- **Type:** Geist or Inter for everything, 14px app body, 600 weight for titles; one mono for code.
- **Shape and depth:** radius 6px controls, 8px cards, 12px dialogs; 1px borders everywhere; focus as a 2px ring with a 2px offset; shadows only on popovers, menus and dialogs.
- **Motion:** 150ms color and opacity; menus scale from 0.96 with a 120ms fade from their trigger, never from 0.
- **Signature:** must be added: one brand accent used for the primary action and current item, and one display face for marketing pages. Without these two moves it reads as a template (taste detectors 1, 8, 15).
- **Access:** the default light border (about 1.3:1) is decorative only; inputs and toggles need the measured border above. Muted text must still pass 4.5:1.

### 3. Ink-only canvas
- **Mood:** radically reduced; white page, black as the only fill, typography carrying all weight. **Fits:** single-purpose tools, a prompt-led product, a launch page for a developer tool. **Fails:** dense apps, where black cards stack into heavy blocks, and anything that needs color-coded status.
- **Palette:** bg `#FFFFFF`, card `#000000` with white text (21:1), ink `#000000`, ink-2 `#5A5A5A` (6.9:1 on white). Secondary text on black cards uses `#B5B5B5` or lighter (10.2:1 on black); never the light-mode gray.
- **Type:** one grotesque (Inter or Schibsted Grotesk), two weights, a scale with a 3.5x jump from body to display.
- **Shape and depth:** edge-to-edge sections, no shadows, no borders except 1px black dividers; every control is a pill (`border-radius: 999px`), filled black for primary and outlined black for secondary.
- **Motion:** 120ms inversions on hover (black to white with a black outline); no entrances.
- **Signature:** one black surface per view, used for the thing that matters (the composer, the current result).
- **Access:** status needs words and icons because there is no color; focus ring must be visible on both white and black, so use a 2px outline plus a 2px offset in the opposite color.

### 4. Tonal layered surfaces
- **Mood:** structured, friendly, adaptive; elevation by tone, color generated from one seed. **Fits:** cross-platform apps, Android-first products, products that theme per user. **Fails:** brands with a fixed signature color that must never shift.
- **Palette:** bg `#FBF9FC`, container `#EEEBF2`, ink `#1B1B21` (16.4:1 on bg, 14.5:1 on container), ink-2 `#46464F` (8.9:1), primary `#3A57A6` (6.5:1) with `#FFFFFF` (6.8:1), primary container `#DDE3FF` with `#0E1A45` text (13.2:1). Generate the ramp in OKLCH from the seed at lightness steps 99, 95, 90, 80, 70, 60, 50, 40, 30, 20, 10, then recheck pairs.
- **Type:** Rubik or Manrope; a five-level scale (display, headline, title, body, label) with label 12-14px at 500.
- **Shape and depth:** a shape scale of 4, 8, 12, 16 and 28px tied to component size; five container tones instead of shadows; interaction shown by a state layer, an overlay of the content color at 8% for hover and 12% for focus and press (`color-mix(in oklch, currentColor 12%, transparent)` on `::before`).
- **Motion:** 200ms standard ease-out for small changes; 350-450ms with a strong decelerate (`cubic-bezier(.25,.1,0,1)`) for containers that grow into pages; shared-element transitions where supported.
- **Signature:** the seed color shows up in tinted containers, not only in buttons. On Android 12 and later, wallpaper-derived dynamic color can supply the seed; keep a brand fallback.
- **Access:** recheck contrast for every generated seed in CI, since a user-chosen seed can produce failing pairs; state layers alone are not focus indicators, so add a 2px outline.

### 5. Developer platform console (dark)
- **Mood:** fast, precise, quietly technical; deploy, monitor and manage from one place. **Fits:** hosting, CI, cloud and API dashboards. **Fails:** consumer apps, first-time users who need guidance more than density.
- **Palette:** bg `#0B0D10`, surface `#14171C`, ink `#E7E9EC` (16.0:1), ink-2 `#9AA2AD` (7.5:1), accent `#B3A4FF` (9.0:1 on bg) with on-accent `#16112E` (8.4:1); hairlines `rgb(255 255 255 / .08)`. A purple brand works here only when retuned for dark (`DRK-05`); otherwise use the brand hue.
- **Type:** Inter or IBM Plex Sans 13-14px with tabular figures; IBM Plex Mono or JetBrains Mono for hashes, branches, URLs and logs.
- **Shape and depth:** top bar only, no sidebar on overview pages; project cards 8px radius with 1px hairline; elevation by lighter surface steps (`DRK-03`); glass only on the sticky top bar, solved with `glass_contrast.py`.
- **Motion:** 120-160ms; a deploy row's status dot may pulse at 1.5s while building and stops under reduced motion; logs stream without animation.
- **Signature:** real status (commit, branch, duration, region) in the first row of every card, and copyable identifiers.
- **Access:** status dots always carry a text label; keyboard shortcuts listed in a `?` panel; dark is the default only with a working light theme (`DRK-07`). See also [dashboard-building.md](dashboard-building.md).

### 6. Enterprise components and builders
- **Mood:** orderly, efficient, consistent across hundreds of screens. **Fits:** admin consoles, data-entry products, no-code workflow builders with drag and drop. **Fails:** marketing pages and consumer products.
- **Palette:** bg `#F4F5F7`, surface `#FFFFFF`, ink `#1C2028` (15.0:1), ink-2 `#4F5866` (6.6:1), accent `#1B5BD6` (5.5:1) with `#FFFFFF` (6.0:1), input border `#868D99` (3.1:1).
- **Type:** IBM Plex Sans or Source Sans 3, 14px base, 12px minimum; right-aligned tabular numbers in tables.
- **Shape and depth:** 32px controls (40px on touch), radius 4-6px, form labels above on narrow screens and left-aligned at 120-160px on wide ones; tables with sticky header and density setting; builder canvas with an 8px dot grid at 12% ink.
- **Motion:** 100-150ms; drag uses a 2px accent insertion line, a lifted card with `0 8px 20px rgb(0 0 0 / .18)`, and auto-scroll when within 48px of a scroll edge.
- **Signature:** every drag has a keyboard twin: select with Space, move with arrows, drop with Space, cancel with Esc, each step announced in a polite live region.
- **Access:** drop zones show a dashed 2px border plus a text hint, not color alone; validation messages sit next to the field and in a summary. Extends the catalog's Dense data console.

### 7. Corporate and retail trust
- **Mood:** reliable, brand-aligned, unsurprising in a good way. **Fits:** corporate sites, B2B services, electronics and appliance shops, financial products. **Fails:** when it hides behind stock photos and abstract claims.
- **Palette:** bg `#FFFFFF`, surface `#F2F4F7`, ink `#132036` navy (16.3:1), ink-2 `#4A5468` (7.6:1), accent `#0D5196` (8.0:1) with `#FFFFFF` (8.0:1).
- **Type:** Source Sans 3 for text with Source Serif 4 for large statements, or IBM Plex Sans alone.
- **Shape and depth:** 12-column grid, 4-8px radius, product cards with fixed image ratio (1:1 for products, 3:2 for people); one shadow level for hover lift.
- **Motion:** 150-200ms; product image swaps on hover at 200ms; no parallax.
- **Signature:** facts with sources (customers, figures with dates, certifications); in a shop, price, stock, delivery date and specs visible on the card and comparable side by side.
- **Access:** spec tables as real `<table>` markup; prices read correctly by screen readers (no split spans); filters usable by keyboard.

### 8. Conversion-first page
- **Mood:** direct and fast; one page, one action, nothing in the way. **Fits:** sign-up, trial, waitlist, single-product checkout. **Fails:** multi-audience sites and anything that needs exploration.
- **Palette:** bg `#FFFFFF`, surface `#F5F5F2`, ink `#141518` (18.3:1), ink-2 `#55585F` (7.1:1), action color `#A8400C` (6.2:1, used only for the primary action) with `#FFFFFF` (6.2:1).
- **Type:** Inter or Figtree; headline 40-56px stating the outcome; body 18px.
- **Shape and depth:** single column 640-720px; the action repeats about every 1 to 1.5 screens; proof placed next to the action; forms of three to five fields, built per [forms-conversion.md](../../forms-conversion.md).
- **Motion:** almost none; speed is the feature: LCP 2.5s or less and INP 200ms or less at the 75th percentile.
- **Signature:** the action color appears nowhere except on the action.
- **Access:** no fake timers, stock counters or pre-checked consent ([ethical-persuasion.md](../../ethical-persuasion.md)); errors next to fields; the button says what happens ("Start 14-day trial").

## B. Quiet and literary

### 9. Spacious minimal
- **Mood:** clean, sleek, airy; less on screen so each element counts. **Fits:** portfolios, product pages with few features, settings-light apps. **Fails:** dense tools, catalogs with hundreds of items.
- **Palette:** bg `#FFFFFF`, surface `#F5F5F3`, ink `#151515` (18.3:1), ink-2 `#5C5C5C` (6.7:1), accent `#2443C2` (7.9:1) with `#FFFFFF`. Distribute roughly 60% ground, 30% ink and surface, 10% accent.
- **Type:** Hanken Grotesk or Inter, two weights; display 3-5x body.
- **Shape and depth:** 8px grid; section padding 128-192px on desktop and 72-96px on phones; component padding 24-32px; radius 8px or 0, one choice; no resting shadows.
- **Motion:** 200-300ms fades; one hero entrance at most.
- **Signature:** whitespace used as hierarchy: the most important element has the most space around it.
- **Access:** large empty areas must not hide navigation or push the action below the fold on phones; never thin gray text to look "light" (taste detector 7).

### 10. Serif refinement
- **Mood:** graceful, understated, considered. **Fits:** studios, publishing tools, calm productivity software, premium services. **Fails:** loud consumer apps and dense data.
- **Palette:** bg `#FBFBF9`, surface `#F1F1ED`, ink `#1A1916` (17.0:1), ink-2 `#5D5A53` (6.6:1), accent `#2C4A3B` deep green (9.4:1) with `#FFFFFF` (9.8:1).
- **Type:** Instrument Serif for display at 400 only, Instrument Sans for interface; or Source Serif 4 with Source Sans 3 for products with longer text.
- **Shape and depth:** hairlines at 12% ink, radius 2-4px, generous line height (1.6), no shadows.
- **Motion:** 200-250ms ease-out; underline grows from left on links.
- **Signature:** a large serif headline set with tight tracking (-0.01em) above a small, precise sans interface.
- **Access:** light serif weights fail below about 20px on low-density screens; body text stays at 400 or heavier in the sans.

### 11. Warm journal
- **Mood:** authoritative, editorial, almost achromatic, warm without being sweet. **Fits:** research products, long-form publications, blogs, essays, documentation with a voice. **Fails:** dashboards and anything the cream-and-clay formula would make anonymous (taste detector 2).
- **Palette:** bg `#F2F1ED` stone (low chroma, not yellow), surface `#E9E7E1`, ink `#23221F` (14.1:1), ink-2 `#57554F` (6.6:1), accent `#8E3B22` (6.6:1) with `#FFFFFF` (7.5:1), used for links and at most one action per screen.
- **Type:** Young Serif or Fraunces for headlines, Literata for long text at 18-20px and 1.6 line height, a plain sans for interface labels.
- **Shape and depth:** reading measure 62-70ch; radius 4px; no shadows; footnotes and pull quotes as typographic devices.
- **Motion:** none on reading content; 150ms link transitions.
- **Signature:** the accent held in reserve, so when it appears it means "go here".
- **Access:** avoid the formula by changing at least one of its three parts: an ink-colored or oxblood accent, a sans display, or a non-cream ground.

### 12. Editorial poster bands
- **Mood:** graphic, warm, confident, like a printed poster cut into sections. **Fits:** product launches, agencies, conference sites, opinionated tools. **Fails:** apps used all day.
- **Palette:** cream band `#F3EDE2` with ink `#1A120B` (15.9:1), orange band `#D9692A` with the same ink (5.3:1), amber detail `#F0A92E` (ink 9.2:1). White text on these oranges fails; keep ink on them.
- **Type:** Schibsted Grotesk or Space Grotesk, display 72-140px on desktop with `clamp()`, tight leading (0.95).
- **Shape and depth:** full-bleed bands that alternate, radius 0, no shadows, oversized numerals and rules as graphic elements.
- **Motion:** band colors switch hard; one headline slide-up of 400ms on load.
- **Signature:** two grounds only, alternating with intent: statement bands in orange, evidence bands in cream.
- **Access:** neighboring bands differ in lightness, not only hue; check every band with every text color used on it.

### 13. Precision product showcase
- **Mood:** polished, exact, reverent toward the product. **Fits:** hardware, consumer electronics, a flagship app launch. **Fails:** products without great imagery; text-heavy services.
- **Palette:** bg `#FFFFFF`, alternate band `#F4F4F6`, ink `#1A1A1C` (17.4:1), ink-2 `#6A6A70` (5.4:1 on bg, 4.9:1 on band), accent `#1F5FD1` for links and buttons (5.8:1).
- **Type:** Inter with display optical tuning: 56-96px at 600, tracking -0.015em; body 17-19px.
- **Shape and depth:** product imagery large on plain bands, pill buttons, a sticky local navigation bar 48-52px tall, radius 18-24px on feature tiles.
- **Motion:** scroll-linked reveals of the product of 400-600ms equivalent; product turntables as video with a poster frame, paused offscreen and replaced by the poster under reduced motion.
- **Signature:** one product per screen, photographed with consistent lighting, and one sentence about it.
- **Access:** images with explicit `width` and `height`; captions carry the claims so the page reads without images; avoid gray text under 4.5:1.

## C. Loud and graphic

### 14. Neobrutalism
- **Mood:** raw structure made friendly: thick ink borders, hard shadows, vivid fills on a warm ground. **Fits:** creator tools, indie products, education, community sites. **Fails:** finance, health, enterprise.
- **Palette:** bg `#FFF3DC`, surface `#FFFFFF`, ink and borders `#111111` (17.2:1), ink-2 `#3F3F3F` (9.6:1), coral `#FF6A3D`, sky `#7FD6FF`, lime `#C6F36B` as fills with ink text (6.6:1, 11.7:1, 14.8:1). Fills are boundaries via the ink border, never text color.
- **Type:** Space Grotesk 700 for display, Inter for text.
- **Shape and depth:** 2-3px ink borders, radius 8-12px (unlike plain brutalism's 0), hard shadow `4px 4px 0 #111`. Thick-bordered variant: 4px borders, circles and triangles as decoration, `#FF5B00` fills (ink 6.1:1), spacing steps up to 48 and 64px.
- **Motion:** press moves the face `translate(4px, 4px)` while the shadow drops to 0, 80ms; draw the shadow on a wrapper so the hit area stays put.
- **Signature:** one fill color per component type, chosen once.
- **Access:** focus is a 3px outline in a contrasting fill plus offset, separate from the border; do not rotate text blocks.

### 15. Big type, high contrast
- **Mood:** bold, commanding, sometimes theatrical. **Fits:** campaigns, portfolios, premium brands with a strong voice, event pages. **Fails:** apps; any screen with many small actions.
- **Light palette:** bg `#FFFFFF`, ink `#0B0B0B` (19.7:1), ink-2 `#4C4C4C` (8.6:1), one field `#FFE03D` with ink (15.0:1). **Dark palette:** bg `#0C0C0C`, surface `#181818`, ink `#F3F3F1` (17.6:1), ink-2 `#A6A6A2` (8.0:1), signal `#E8402F` for large text or fills only (4.8:1 on bg).
- **Type:** Anton or Archivo Black at 96-220px with `clamp()`, leading 0.88-0.95, tracking -0.02em; a neutral sans at 16-18px for text.
- **Shape and depth:** radius 0; no shadows; dramatic compositions with type cropped by the viewport edge, light from one side on photography.
- **Motion:** one entrance per section (slide 24px, 500ms, ease-out); scroll-linked scale on one headline at most.
- **Signature:** a headline of two to four words that fills the width.
- **Access:** cropped words must still be readable or duplicated in an accessible name; avoid all-caps paragraphs; test 200% zoom for overflow.

### 16. Saturated color fields
- **Mood:** colorful, vibrant, expressive, energetic but structured. **Fits:** consumer apps, creative tools, festivals, youth brands. **Fails:** clinical, legal and money contexts.
- **Palette:** bg `#FFFFFF`, surface `#F4F1FB`, ink `#19151F` (18.0:1), ink-2 `#575160` (7.6:1), accent `#5B2BD9` (7.5:1) with white, fields `#FFB547`, `#43D3B0`, `#FF7AA8` each with ink (10.2:1, 9.6:1, 7.4:1). Do not put white on these fields.
- **Type:** Bricolage Grotesque or Syne for display, Figtree for text; a monospace-everywhere variant fails taste detector 12, so keep mono for labels at most.
- **Shape and depth:** 16-24px radius, flat fills, no gradients; one field per section, not per card.
- **Motion:** springy entrances for celebratory moments only, 300-450ms, settle without more than one overshoot.
- **Signature:** assign each field to a meaning (create, learn, share) and keep it.
- **Access:** do not let color be the only category signal; add icons and labels.

### 17. Gradient-rich
- **Mood:** luminous, soft, modern. **Fits:** creative tools, music, wellness, launch pages. **Fails:** when the gradient is the only idea (taste detectors 1 and 6).
- **Palette:** bg `#FFFFFF`, surface `#F6F4F2`, ink `#16141A` (18.3:1), ink-2 `#58545F` (7.4:1), action `#C2286A` solid (5.5:1) with white; gradient stops `#FF8B5E`, `#FFC85C`, `#5ECFC4` with ink text only (7.9:1 at the darkest stop).
- **Type:** Sora or Outfit; solid ink headlines, not gradient text.
- **Shape and depth:** `linear-gradient(in oklch, ...)` to avoid gray midpoints; a 3-5% SVG noise overlay to stop banding; gradients on backgrounds and illustrations, never behind long text or on buttons with labels.
- **Motion:** a slow hue drift (20-40s loop) only on a decorative background, paused offscreen and under reduced motion.
- **Signature:** one gradient family across the product, used in a few large places.
- **Access:** check text against the lightest and darkest point beneath it, not the average.

### 18. Artistic display
- **Mood:** high-contrast, crafted, gallery-like, led by one characterful display face. **Fits:** artist sites, galleries, music releases, cultural events. **Fails:** utilities and forms.
- **Palette:** bg `#111012`, surface `#1C1A1E`, ink `#F5F1EA` (16.9:1), ink-2 `#B4ADA3` (8.5:1), accent `#FF4F3A` (5.8:1) with `#111012` text, highlight field `#F2E14C` with `#111012` text (14.1:1).
- **Type:** a decorative display (Monoton, Shrikhand or a commissioned face) at 48px and up only; Manrope for everything else.
- **Shape and depth:** asymmetric layouts on a grid, art at full bleed, captions small and precise.
- **Motion:** image reveals with a clip-path wipe of 500-700ms; cuts under reduced motion.
- **Signature:** the art and one typographic gesture; everything else steps back.
- **Access:** decorative faces never carry navigation or body text; supply alt text written about the work.

## D. Tactile and dimensional

### 19. Claymorphism
- **Mood:** soft, puffy, playful, like molded clay. **Fits:** kids' and family products, onboarding illustrations, playful consumer apps, a few hero elements. **Fails:** forms, tables and long lists; dense screens become mush.
- **Palette:** bg `#EDEBFA`, surface `#FFFFFF`, ink `#1F1B3A` (14.0:1), ink-2 `#4F4A6B` (7.1:1), accent `#5C4AD6` (5.2:1) with white (6.2:1), pastel tiles `#FFD3C4` and `#C9F0DD` with ink (12.0:1, 13.3:1), control border `#8A84B0` (3.0:1).
- **Type:** Fredoka or Baloo 2 for display, Nunito for text.
- **Shape and depth:** radius 24-32px; the clay effect is two inset shadows plus one drop: `inset -6px -8px 14px rgb(0 0 0 / .10), inset 6px 6px 12px rgb(255 255 255 / .70), 0 14px 28px -10px rgb(60 40 140 / .30)`.
- **Motion:** press squashes to `scale(.97, .94)` over 90ms and springs back over 220ms; static under reduced motion.
- **Signature:** a handful of chunky clay objects (illustrations, icons, the main button) on calm flat surfaces.
- **Access:** like neumorphism, shadows give about 1.3:1, so controls need the measured border or a filled state with a label.

### 20. Skeuomorphism
- **Mood:** familiar, physical, crafted: real materials, light from above, controls that look operable. **Fits:** audio tools, instruments, cameras, games, nostalgic or craft products, onboarding for unfamiliar devices. **Fails:** large data apps; heavy textures slow pages.
- **Palette:** bg `#E7E2D8`, surface `#F7F4EE`, ink `#231F1A` (12.7:1), ink-2 `#544D43` (6.5:1), accent `#2F5D8C` (5.3:1) with white (6.9:1), control edge `#7C7466` (3.6:1).
- **Type:** Alegreya Sans for interface, Alegreya for headings; engraved labels via a 1px light `text-shadow` below dark text.
- **Shape and depth:** top-lit gradients (2-6% lightness change), a 1px inner highlight on top edges, layered shadows for real height; textures as tiled AVIF or WebP under 30KB each.
- **Motion:** physical: toggles slide 150ms, knobs rotate with pointer drag, buttons sink 1-2px on press. On iOS and Android pair presses with light haptics where the platform provides them.
- **Signature:** one material story (brushed metal studio, leather notebook, wooden desk) told consistently.
- **Access:** knobs and sliders expose `role="slider"` with arrow-key steps; the metaphor must never hide a label.

### 21. Isometric perspective
- **Mood:** spatial, explanatory, depth that guides attention. **Fits:** architecture of systems, onboarding diagrams, product tours, hero illustrations. **Fails:** text and forms set in perspective.
- **Palette:** bg `#F3F5FA`, surface `#FFFFFF`, ink `#141A2A` (15.9:1), ink-2 `#4C5568` (6.9:1), accent `#3047D9` (6.4:1) with white, block side shade `#C7CEE0`.
- **Type:** Plus Jakarta Sans or Outfit; labels stay flat and screen-aligned, pointing into the scene with leader lines.
- **Shape and depth:** true isometric planes with `transform: rotateX(54.74deg) rotateZ(-45deg)`, or the 2:1 pixel style with `rotateX(60deg)`; parents need `transform-style: preserve-3d` and a `perspective` of 1000-1600px for vanishing-point scenes; three shades per block (top, left, right).
- **Motion:** layers separate on hover by 8-16px along Z over 300ms; flatten under reduced motion.
- **Signature:** one scene per page that explains something real.
- **Access:** provide the same information as a list or caption; keep 3D layers under about a dozen to avoid compositing cost on phones.

### 22. Ledge buttons and friendly rounds
- **Mood:** bright, rounded, encouraging, tactile; a learning product that feels like a game. **Fits:** learning, habit and kids' apps, onboarding. **Fails:** serious tools and anxious moments.
- **Palette:** bg `#FFFFFF`, surface `#F4F7F2`, ink `#1E2420` (15.8:1), ink-2 `#56605A` (6.5:1), action `#23863A` with white text (4.6:1, use 16px bold or larger) and ledge `#17612A`. Pastel variant: bg `#FDFBF8`, surface `#F3EEFA`, accent `#7A3FA8` (6.6:1) with white (6.8:1).
- **Type:** Lexend or Nunito, 600-800 for buttons; a rounded display for headings.
- **Shape and depth:** radius 14-20px; buttons with a 4px solid ledge (`box-shadow: 0 4px 0 var(--ledge)`) and 2px light-gray borders on cards; illustrations with simple shapes and your own characters.
- **Motion:** press `translateY(4px)` with the ledge to 0 in 60ms; correct-answer celebrations 400-600ms and skippable; light haptic on iOS and Android.
- **Signature:** the pressable ledge on every primary action, and progress made visible.
- **Access:** targets 48px or larger; feedback by icon, text and color together; streaks and rewards never punish missing a day with guilt copy.

## E. Hand-made, print and nostalgia

### 23. Hand-drawn
- **Mood:** informal, human, sketchbook energy; pencil lines on warm paper. **Fits:** creative tools, education, personal sites, early-stage products wanting warmth. **Fails:** finance, enterprise, anything that must feel precise.
- **Palette:** bg `#FAF7F0`, surface `#FFFFFF`, ink `#222222` (14.9:1), ink-2 `#555149` (7.4:1), accent `#126E6A` teal (5.7:1) with white (6.1:1).
- **Type:** Caveat or Kalam for headings at 28px and up; Nunito or Atkinson Hyperlegible Next for body.
- **Shape and depth:** wobbly frames with uneven radii (`border-radius: 240px 18px 210px 14px / 14px 210px 18px 240px`), dashed outlines, offset "pencil" shadows (`3px 4px 0 #222`), SVG doodles; for rough edges, an SVG `feTurbulence` plus `feDisplacementMap` at scale 2-3 on decorative strokes only.
- **Motion:** stroke drawing with `stroke-dashoffset` over 600-900ms for one illustration; static under reduced motion.
- **Signature:** a few doodles that annotate real content (arrows to the action, circles around the key number).
- **Access:** handwriting never for body, links or form labels; keep focus outlines straight and clear.

### 24. Picture-book and comic
- **Mood:** cartoonish, energetic, children's-book or comic-panel warmth. **Fits:** kids' products, games, illustration-led brands, creative landing pages. **Fails:** serious services.
- **Palette:** bg `#FFF6E6`, surface `#FFFFFF`, ink and outlines `#141414` (17.2:1), ink-2 `#4A4436` (9.0:1), red `#C42A22` with white (5.7:1), yellow block `#FFC93C` with ink (12.0:1), blue block `#3E7BFA` with ink (4.8:1).
- **Type:** Bangers for comic headings or a rounded bold display for picture-book; Nunito for text.
- **Shape and depth:** 3px ink outlines, radius 20-28px, flat fills, almost no shadows; speech bubbles and halftone dots (a radial-gradient pattern at 10-15% ink) as decoration.
- **Motion:** pop-in of 250ms with one small overshoot for stickers; panels slide 300ms.
- **Signature:** original characters drawn for the product, never franchise ones.
- **Access:** children's audiences need larger targets (48px+), plain words, no manipulative rewards, and parental gates for purchases.

### 25. Risograph
- **Mood:** joyful, two-color print, slightly imperfect. **Fits:** zines, events, independent shops, creative studios. **Fails:** apps that need many states and colors.
- **Palette:** paper `#F7F4EC`, surface `#FFFFFF`, blue ink `#25389A` for headings and text (9.1:1), ink-2 `#4C4A55` (7.9:1), fluorescent pink `#F24C9E` only as fills with `#14141A` text (5.5:1, boundary 3.0:1). Pink text on paper fails.
- **Type:** Space Grotesk for display, a sturdy text face such as Work Sans.
- **Shape and depth:** overprint with `mix-blend-mode: multiply`; misregistration by duplicating a shape with a 2px offset; grain from SVG noise at 6-10% on fills, never under text; offset print shadows in blue.
- **Motion:** almost none; a 2px registration shift on hover, 120ms.
- **Signature:** two inks, overlapping where they meet to make a third color.
- **Access:** keep text in the dark ink; check blended overlaps that carry text as their own color pairs.

### 26. Dithered
- **Mood:** nostalgic, graphic, high-contrast, made of dots. **Fits:** developer tools, music, art direction for tech brands, game sites. **Fails:** photography that must stay accurate, such as products for sale.
- **Palette, light:** bg `#F4F3EF`, surface `#E6E4DE`, ink `#111111` (17.0:1), ink-2 `#4A4A4A` (8.0:1). **Dark:** bg `#0D0D0D`, ink `#EDEDED` (16.6:1), ink-2 `#A0A0A0` (7.4:1), accent `#FF6E2E` (7.0:1).
- **Type:** Space Grotesk or IBM Plex Sans; a pixel face only for tiny decorative labels.
- **Shape and depth:** images converted offline with ordered (4x4 or 8x8 Bayer) or error-diffusion dithering to one or two inks, shipped as PNG and scaled by whole numbers with `image-rendering: pixelated`; live versions as a WebGL fragment shader.
- **Motion:** a slow threshold shift on a hero image only, paused offscreen and under reduced motion.
- **Signature:** dithered imagery against crisp, undithered type.
- **Access:** never dither text or icons; fine dot patterns can shimmer when scaled or scrolled, so keep pattern cells at 2 device pixels or larger.

### 27. Paper and print
- **Mood:** tactile, quiet, page-like. **Fits:** notes and writing tools, reports, recipes, books and magazines on the web. **Fails:** dark-first media products.
- **Palette:** bg `#F6F4EF`, sheet `#FFFFFE`, ink `#1F1E1B` (15.2:1), ink-2 `#5A5750` (6.6:1), accent `#1E4D7A` (8.0:1) with white.
- **Type:** Source Serif 4 for reading, Work Sans for labels.
- **Shape and depth:** sheets lifted with `0 1px 0 rgb(0 0 0 / .06), 0 10px 20px -12px rgb(0 0 0 / .20)`; fiber texture at 3-4% or none; rules and margins from book design.
- **Motion:** sheets slide 220ms; page turns as a crossfade, not a 3D curl.
- **Signature:** a real `@media print` stylesheet that removes navigation, prints links as URLs and sets page margins with `@page`.
- **Access:** keep texture off text areas; the sheet edge needs a visible shadow or 1px border to separate from the ground.

### 28. Retro desktop
- **Mood:** late-century computer nostalgia: beveled gray windows, teal desktop, pixel labels, grain. **Fits:** games, music, art projects, playful portfolios, an optional theme. **Fails:** as the default for real work.
- **Palette:** desktop `#0F7A78` with white labels (5.2:1), window `#C3C3C3` with black text (11.9:1), ink-2 `#3B3B3B` (6.4:1 on window), title bar `#0A1F7A` with white (14.1:1), bevel light `#FFFFFF` and shadow `#7B7B7B`.
- **Type:** Silkscreen or Pixelify Sans at whole multiples of its pixel size for titles and buttons; a plain sans for paragraphs.
- **Shape and depth:** radius 0; bevels as stacked inset shadows (`inset -1px -1px #3A3A3A, inset 1px 1px #FFFFFF, inset -2px -2px #7B7B7B, inset 2px 2px #DFDFDF`), reversed when pressed.
- **Motion:** none, or stepped (`steps(4)`) window opening of 120ms.
- **Signature:** one real task done inside a window, not a fake desktop full of dead icons.
- **Access:** draggable windows need a keyboard way to move or a fixed layout on small screens; pixel text not below 16px.

### 29. Seventies throwback
- **Mood:** warm, groovy, sunlit; stripes, rounded display type, grain. **Fits:** food and drink, music, hospitality, lifestyle brands. **Fails:** technical and financial products.
- **Palette:** bg `#F5EBD7`, surface `#FFF8EA`, ink `#3A2414` brown (12.3:1), ink-2 `#6A4A33` (6.7:1), action `#B4471C` with white (5.4:1), mustard `#E2A72E` with ink (6.8:1), olive `#6F7A2E` with white (4.7:1).
- **Type:** Righteous or Shrikhand for display, Work Sans for text.
- **Shape and depth:** rounded radii (16px+), stripe bands from repeating linear gradients, grain at 4%.
- **Motion:** gentle 300-400ms; a slow sunset gradient only in a hero.
- **Signature:** three stacked stripes used once as a frame around the main message.
- **Access:** this ground is close to taste detector 2 (cream with clay); the stripes and brown ink keep it distinct, but recheck every pair.

## F. Games and arcade (genres, never titles)

### 30. Arcade pixel
- **Mood:** high-energy, coin-op cabinet, pixel type, dotted trails. **Fits:** game sites, events, playful developer pages, an optional theme. **Fails:** long reading and serious tasks.
- **Palette:** bg `#07081C`, surface `#11133A`, ink `#F4F4FF` (18.1:1), ink-2 `#A9ACD6` (9.0:1), yellow action `#FFD23A` with `#07081C` (13.7:1), maze lines `#3C55FF` (3.7:1 as boundary), pink `#FF6FB5` with dark text (7.7:1).
- **Type:** Press Start 2P for headings at 16, 24 or 32px, VT323 for large readouts at 24px+, Space Mono for body.
- **Shape and depth:** 0 radius or pill, chosen once; `border: 4px dotted` for trails; buttons press into a solid offset block (`box-shadow: 0 6px 0 #9C7A00`, pressed `translateY(6px)`); cabinet trim as stacked rings (`0 0 0 3px #FF5A5A, 0 0 0 6px #FFD23A, 0 0 0 9px #3CD47A, 0 0 0 12px #3C8CFF`).
- **Motion:** stepped sprite animation with `steps()`; attract-mode loops pause offscreen and under reduced motion; no flashing above three per second.
- **Signature:** a playable or interactive moment that is optional and dismissible.
- **Access:** sound off by default with a visible toggle; pixel fonts never below 16px; maze or game elements have text equivalents.

### 31. Falling blocks
- **Mood:** compact, high-energy, square cells in bright colors. **Fits:** puzzle games, leaderboards, playful progress displays. **Fails:** anything that is not a game or a game-like moment.
- **Palette:** well `#0F1222`, surface `#1A1E36`, ink `#F1F3FF` (16.8:1), ink-2 `#A6ABC9` (8.2:1), accent `#38D6E8` with dark text (10.6:1); a set of five to seven of your own piece colors.
- **Type:** a heavy condensed display (Anton or Bungee) for scores, tabular numerals for timers.
- **Shape and depth:** square cells on an 8px or 16px unit, each with a bevel (lighter top-left and darker bottom-right inset of 2px); compact layout with score, next piece and controls visible together.
- **Motion:** cell drops stepped by the game tick; line-clear flash at most twice, under 333ms per flash; reduced motion swaps the flash for a fill change.
- **Signature:** a grid that is the product, not wallpaper.
- **Access:** pieces distinguishable by shape and a pattern, not hue alone; remappable keys; pause on blur. Specific piece sets and trade dress of known games need a license.

### 32. Fantasy quest
- **Mood:** rich, ornate, premium game world: night skies, parchment, gold. **Fits:** game launches, tabletop and role-playing tools, fan-free original worlds. **Fails:** utilities.
- **Palette:** bg `#15101F`, surface `#221A30`, ink parchment `#EEE5CF` (14.9:1), ink-2 `#B9AE96` (8.5:1), gold `#D2AA52` with `#1A120A` text (8.5:1), crimson `#9C2335` with parchment text (6.2:1).
- **Type:** Cinzel for titles at 32px+, Alegreya for text.
- **Shape and depth:** ornate frames as SVG with `border-image` nine-slice; inner glow limited to one gold 1px line; illustrated backgrounds dimmed to 40% behind text panels.
- **Motion:** slow parallax of two layers at most (0.1-0.2 ratio) on desktop; embers and particles capped at a low count, off under reduced motion.
- **Signature:** an item or character card system with rarity shown by frame, icon and word.
- **Access:** rarity and faction colors always paired with labels; text panels solid, not translucent over art.

## G. Night and future

### 33. Cosmic
- **Mood:** deep space, sci-fi, spatial and immersive. **Fits:** astronomy, space and science products, music, game launches. **Fails:** daily tools and long reading on a starfield.
- **Palette:** bg `#070A1C`, surface `#111633`, ink `#ECEEFF` (17.1:1), ink-2 `#A3A8CC` (8.4:1), accent `#7FE3FF` with `#061428` (12.6:1), nebula `#C66BFF` for large display or decoration (6.5:1).
- **Type:** Orbitron for short display lines, Exo 2 for text.
- **Shape and depth:** starfield as a static image or a canvas drawn once (a few hundred points), nebula as soft radial gradients, panels solid with a hairline.
- **Motion:** star drift on a 60s+ loop, paused offscreen with IntersectionObserver and stopped under reduced motion.
- **Signature:** a sense of scale, such as one planet or object large on the first screen.
- **Access:** glow limited to display text; body on solid surfaces; avoid pure black (`DRK-02`).

### 34. Futuristic tech
- **Mood:** forward-looking, sleek, instrument-like; thin lines and corner brackets. **Fits:** hardware, mobility, AI and robotics companies, technical launches. **Fails:** warm consumer brands.
- **Palette:** bg `#F2F4F6`, surface `#FFFFFF`, ink `#0E1217` (17.0:1), ink-2 `#4C5561` (6.9:1), accent `#0057D9` (5.7:1) with white (6.2:1). For dark, use the console recipe 5 and the catalog's dark rules.
- **Type:** Chakra Petch or Oxanium for display only, Inter for text; tabular numerals in readouts.
- **Shape and depth:** chamfered corners with `clip-path: polygon(...)` at 8-12px, corner brackets as pseudo-elements, 1px technical rules; no glows on light grounds.
- **Motion:** precise and quick, 150-250ms with `cubic-bezier(.2,.8,.2,1)`; numbers counting up once on reveal.
- **Signature:** real specifications presented like an instrument panel.
- **Access:** chamfered shapes still need a visible focus outline (`outline` follows the box, so draw focus on a wrapper).

### 35. Neon signage
- **Mood:** electric, nightlife, attention-grabbing. **Fits:** bars, events, music, gaming nights, one hero. **Fails:** anything used daily; it is taste detector 3 when used as the whole product.
- **Palette:** bg `#0D0B14`, surface `#17141F`, ink `#F2EFF8` (17.2:1), ink-2 `#ABA4BB` (8.1:1), magenta `#FF4FD8` (6.8:1) with `#1A0614` text, cyan `#3EF0FF` (14.1:1).
- **Type:** Monoton or a script display for the sign at 64px+, Inter for everything else.
- **Shape and depth:** glow only on the sign: `text-shadow: 0 0 2px currentColor, 0 0 10px var(--glow), 0 0 28px var(--glow)`; tube outlines as SVG strokes with a matching `drop-shadow`.
- **Motion:** a single flicker on load at most; never periodic flicker; none under reduced motion.
- **Signature:** one sign, like a real storefront has one.
- **Access:** remove glows in `forced-colors: active`; glow does not count toward contrast, the core color must pass on its own.

### 36. Monospace console
- **Mood:** cyber-slick, dense, monochrome, hacker-chic; order books and terminals as fashion. **Fits:** trading, crypto and security tools, developer communities. **Fails:** general audiences and long prose. Distinct from the catalog's Retro terminal: no phosphor, more precision.
- **Palette, dark:** bg `#090B0A`, surface `#111412`, ink `#E6E9E6` (16.1:1), ink-2 `#8E968F` (6.5:1), up `#5BEA92` (12.8:1), down `#FF6B5E` (7.1:1). **Light variant:** white ground, black ink (21:1), ink-2 `#4D4D4D` (8.5:1).
- **Type:** JetBrains Mono or Space Mono for numerals and labels, a mono or a neutral sans for paragraphs; 12-13px dense, never under 12px.
- **Shape and depth:** hairline 1px borders, radius 0-2px, rows 24-28px, no shadows.
- **Motion:** changed cells tint for 600-1000ms then fade; falling-character rain only as an optional hero canvas, paused under reduced motion.
- **Signature:** aligned figures with real precision and keyboard-first navigation.
- **Access:** up and down never by color alone: add arrows or signs; respect `prefers-contrast: more` by raising ink-2.

## H. Layout and narrative

### 37. Bento grid
- **Mood:** modular, organized, scannable tiles of different sizes; contemporary with light and dark themes. **Fits:** feature overviews, personal dashboards, portfolio summaries. **Fails:** sequential stories and long text; a grid of equal tiles (taste detector 15).
- **Palette, light:** bg `#F3F3F1`, tile `#FFFFFF`, ink `#151515` (16.4:1), ink-2 `#5A5A57` (6.2:1), accent `#2D5BE3` (5.1:1). **Dark:** bg `#0E0F11`, tile `#17191C`, ink `#ECEDEE` (16.4:1), ink-2 `#9EA2A8` (7.5:1), accent `#86A8FF` (8.3:1).
- **Type:** Inter or Manrope; one title size per tile size.
- **Shape and depth:** `grid-template-columns: repeat(6, 1fr)`, `grid-auto-rows: minmax(168px, auto)`, gaps 12-20px, radius 20-24px; one lead tile spanning 4x2; tile internals use container queries (`container-type: inline-size`).
- **Motion:** tiles fade and rise 12px with 40ms stagger, 300ms each, once.
- **Signature:** each tile shows a real fragment (a chart, a control, a photo), not an icon and a sentence.
- **Access:** DOM order equals visual reading order; avoid `grid-auto-flow: dense` when it reorders focusable tiles; on phones tiles stack in priority order.

### 38. Geometric construction
- **Mood:** precise, structured, neutral; circles, squares and triangles on a visible system. **Fits:** architecture, engineering, design studios, education in math and science. **Fails:** warm, human-centered services.
- **Palette:** bg `#FAFAF9`, surface `#EFEFEC`, ink `#161616` (17.3:1), ink-2 `#565653` (7.1:1), accent `#B23A20` with white (6.0:1).
- **Type:** Space Grotesk or Outfit (geometric sans), one family.
- **Shape and depth:** shapes from `clip-path` and SVG, sized on the spacing scale; one motif repeated (for example a quarter circle) in a few places; radius either 0 or 50%.
- **Motion:** shapes rotate or translate in 90-degree steps, 300ms.
- **Signature:** a construction grid that actually aligns content.
- **Access:** decorative shapes `aria-hidden`; no information carried by shape alone.

### 39. Scroll storytelling
- **Mood:** narrative, emotional, guided; chapters revealed as people scroll. **Fits:** annual reports, mission pages, product launches, journalism. **Fails:** pages people come back to for a fact.
- **Palette:** bg `#FFFFFF`, surface `#F1EEE9`, ink `#17151A` (18.1:1), ink-2 `#56525C` (7.6:1), accent `#8C1D40` (8.9:1), night chapter `#14121A` with white ink.
- **Type:** DM Serif Display for chapter titles, Inter for text at 18-20px.
- **Shape and depth:** sticky scenes (`position: sticky; top: 0; height: 100svh`) with text steps scrolling past; scroll-driven animation with `animation-timeline: view()` inside `@supports`, IntersectionObserver as the fallback; see the scroll and reveal reference in this module.
- **Motion:** never take over the scroll wheel (`MOT-16`); each reveal 400-600ms equivalent; reduced motion shows every step at once.
- **Signature:** a chapter index so people can jump, and the story readable with JavaScript off.
- **Access:** all text in the DOM in order; charts that animate have a static final state and a table.

### 40. Exhibit canvas
- **Mood:** immersive, exhibit-like, playful; one continuous brand-colored canvas with rooms to explore. **Fits:** museums, brand worlds, campaign microsites, education with collectibles. **Fails:** task flows and dense information.
- **Palette:** canvas `#0E3B2D` deep green, surface `#155040`, ink `#F6F3E8` (11.2:1 on canvas, 8.4:1 on surface), ink-2 `#C2D3C8` (8.0:1), accent `#F7D046` with `#13261D` text (10.6:1).
- **Type:** Barlow Condensed for display at 40px+, Work Sans for text.
- **Shape and depth:** no alternating section grounds; rooms separated by scale, illustrations and white rules; collectible badges and a progress tracker as optional game layers.
- **Motion:** illustration loops 2-6s on hover or in view, paused offscreen; reduced motion shows the end frame.
- **Signature:** a reason to explore (a trail, collectibles, a map) that never gates information.
- **Access:** every exhibit item reachable by keyboard in a logical order; a "skip the tour" link to plain content.

## Done when

- One recipe chosen, with one line in the report on why it fits the audience and task, and any borrowed trait named.
- Palette mapped to semantic tokens; every text and boundary pair measured, including any color you changed, both themes where the recipe has them.
- Decorative faces only at display sizes; body text in a legible face at 16px or larger (14px in dense apps, never under 12px).
- Reduced motion verified: loops stopped, parallax flattened, state changes still visible; nothing flashes more than three times per second.
- Signature detail present, and the recipe's "fails" cases checked against this product.
- Franchise-like elements replaced by original art or covered by a license; playful layers optional and dismissible.
- The taste self-critique pass in [taste.md](taste.md) and the quality gate in [quality-gate.md](quality-gate.md) run on the result.
