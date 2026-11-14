# UI Distiller: Aesthetic recipes

Read this when a brief names a specific look ("dark glass with a laser", "warm paper SaaS", "archival book reader", "tactile hardware controls") rather than a broad direction. [style-catalog.md](style-catalog.md) chooses a direction from the product; this file turns a named aesthetic into a buildable system. Each recipe gives the mood, palette roles with measured contrast, a type pairing, radius and border language, depth, the one signature move, where it fits and fails, an accessibility note, and how it goes generic.

The values are Sora Labs starting points. A brand's colors and faces win (`../GUIDE.md`, step 4); keep the proportions and the logic, swap the hues, and remeasure. Every face named is published under the SIL Open Font License 1.1; confirm the license file in the exact version you download and follow the font-loading rules in the catalog. Every ratio was computed with the WCAG 2.x formula shown in the catalog; normal text needs 4.5:1, large text and control boundaries 3:1 (`COL-01`).

## Pick a recipe

| The brief says | Start with | Neighbors |
|---|---|---|
| Quiet, premium, editorial, agency or studio | 1 Editorial agency grid | 2, 3, 4 |
| Warm, light, calm, process or onboarding | 3 Warm stone minimal | 6, 7 |
| Bookish, archive, research, lore, long reading | 5 Archival reader | style-catalog *Editorial reading* |
| Light but technical, product demo inside a frame | 6 Paper technical | 8 |
| Airy, aspirational, sky, serene | 9 Sky atmosphere | 11 |
| Dark and premium with blue | 10 Navy with a cobalt block | 11, 14 |
| Dark glass, frosted, workspace, console | 13 Glass workspace | 12, 14, 15 |
| Engineered, framed, monochrome, infrastructure | 16 Framed monochrome shell | 17, 21 |
| Signal color on dark, analytics, build systems | 18 Emerald signal console | 19, 20 |
| Exploded diagram, teardown, spec sheet | 21 Annotated wireframe | 16 |
| Tactile, pressed, hardware, physical | 22 Raised and pressed material | 23, catalog *Soft tactile* |
| Photography leads, cinematic | 24 Photo stage | catalog *Gallery quiet* |
| Raw, declassified, blueprint, print meets terminal | 25 Industrial blueprint | catalog *Brutalist*, *Retro terminal* |

Use one recipe per product (`STY-01`). If a brief mixes two, take the base recipe and borrow one named trait from the other.

## The shared frame kit, and when it becomes a tell

About half of these recipes share a kit: a centered shell with thin vertical rails, small square corner marks, 1px gradient borders, monospace micro-labels and a fixed atmospheric layer. Used carelessly the kit is itself a generated look (taste detectors 11 and 12 in [taste.md](taste.md); *Swiss grid* "goes generic" in the catalog). Rules that keep it honest:

- **Rails sit on real column edges.** Draw them from the same grid tokens the content uses (`--shell-max`, `--gutter`), never at arbitrary offsets. If no content aligns to a rail, delete it.
- **Corner marks: at most four per container, 4-6px squares, one container level only.** Never on cards inside cards.
- **Monospace only for data:** IDs, timestamps, coordinates, versions, step numbers, units. Headings and paragraphs stay in the text face.
- **Uppercase labels 11-12px with 0.06-0.1em tracking**, and only when they add a fact the heading lacks.
- **Decorative lines are exempt from 3:1** only when nothing interactive depends on them; input and control outlines still need 3:1 (`COL-01`).

**1px gradient border.** Two ways, both widely supported:

```css
/* A: two backgrounds; simplest, works with any radius, inner fill must be opaque or a gradient */
.edge { border: 1px solid transparent; border-radius: 20px;
  background: linear-gradient(var(--fill), var(--fill)) padding-box,
              linear-gradient(160deg, rgb(255 255 255 / .42), rgb(255 255 255 / .06) 55%, rgb(255 255 255 / .16)) border-box; }
/* B: masked pseudo-element; use when the fill must stay translucent for backdrop blur */
.edge-glass { position: relative; }
.edge-glass::before { content: ""; position: absolute; inset: 0; padding: 1px; border-radius: inherit; pointer-events: none;
  background: linear-gradient(160deg, rgb(255 255 255 / .4), transparent 60%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude; }
@media (forced-colors: active) { .edge, .edge-glass { border: 1px solid CanvasText; } }
```

Keep the brightest stop of the edge at the top-left (light from above); a bright stop at the bottom reads as a rendering error.

**Atmospheric layer** (beams, meshes, particles, clouds): one fixed element behind content, `aria-hidden="true"`, `pointer-events: none`, device pixel ratio capped at 1.5, paused with an IntersectionObserver when off-screen and on `visibilitychange` when the tab is hidden, frozen to a single frame under `prefers-reduced-motion: reduce`, and replaced by a static gradient when WebGL is missing or `navigator.hardwareConcurrency` is 4 or less (`STY-12`). Headlines and navigation stay real DOM. Ambient loops run 20-40s; anything that changes brightness does so at under one cycle per second and never flashes more than three times per second (WCAG 2.3.1).

**Masked headline reveal.** Each line in an `overflow: clip` wrapper, text from `translateY(105%)` to 0 over 560ms with `cubic-bezier(0.2, 0.8, 0.2, 1)`, 50ms between lines, headline and section titles only. Under reduced motion render the final state. Details in [motion-engineering.md](motion-engineering.md).

**Dark glass.** Text on blur is measured over the worst backdrop, not the page color: [translucent-materials.md](translucent-materials.md) and `scripts/glass_contrast.py`. Where a recipe below gives a tint and alpha, the alpha is the "any backdrop" answer for its secondary text unless stated.

**Native apps.** Map roles to asset-catalog colors (iOS) or a Compose `ColorScheme` plus extra tokens (Android). Prefer system materials over custom blur; skip canvas atmospheres on battery-powered screens used for long sessions; honor Reduce Motion and Reduce Transparency on iOS and the animator duration scale on Android (`ValueAnimator.areAnimatorsEnabled()`).

## A. Quiet light: editorial, agency, minimal

### 1. Editorial agency grid
*Calm authority from a strict grid, very large type and a lot of deliberate emptiness.*
- **Palette:** `--bg #F4F3F0`, `--surface #FFFFFF`, `--text #151515` (16.5:1 on bg), `--text-2 #5E5D59` (5.9:1), `--accent #2A3D63` ink blue (9.7:1; white on it 10.8:1), `--border #8B8983` (3.2:1 on bg, inputs only), hairlines `#DEDCD6` decorative.
- **Type:** Schibsted Grotesk throughout: display 600 at `clamp(48px, 9vw, 152px)`, tracking -0.035em, line height 0.95; body 16-17px at 1.55; labels 500, 11px uppercase.
- **Shape and line:** radius 0 on images, 2px on buttons, 24px only on the one overlapping lower panel; hairline row separators in service lists.
- **Depth:** none except the lower white panel that slides over the previous section with `0 -24px 48px rgb(20 20 20 / .06)`.
- **Signature:** a headline spanning 8-10 of 12 columns with a narrow 3-column note pinned to its baseline; architectural photography at 21:9.
- **Motion:** masked headline, 900ms image settle from `scale(1.04)` to 1, row hover shifts text 4px right in 200ms.
- **Fits:** studios, architecture, consultancies, a portfolio. **Fails:** anything with dense tasks or many calls to action.
- **Access:** huge display type must still wrap at 320px width (`clamp` floor at 40px); hover shifts never carry meaning.
- **Goes generic when:** labels sit above every heading, or the grid is drawn instead of used.

### 2. Nested shells
*Hierarchy by containment: a light page, a dark rounded block inside it, cards inside that.*
- **Palette:** page `#FAFAF9` with `--text #131313` (17.8:1) and `--text-2 #5A5955` (6.7:1); dark block `#121315` with `#EDEDEB` (15.9:1) and `#A3A39E` (7.3:1); inner card `#1C1D20` (text-2 still 6.7:1); accent brass `#E8C872` on dark (11.5:1) with ink `#1A1609` on brass (11.1:1).
- **Type:** Onest, 600 for headings, 400 body at 16px.
- **Shape and line:** radii nest concentrically: page shell 0, dark block 32px, cards 20px, buttons 12px, so inner radius = outer radius minus padding (`CMP-06`); cards use the gradient border from the kit.
- **Depth:** contrast does the work; one soft shadow on the dark block only.
- **Signature:** a pricing or capability block as a dark island with three cards, one of which is visibly the recommended plan.
- **Motion:** 300ms fades; nothing else.
- **Fits:** agencies, service menus, pricing pages. **Fails:** more than three nesting levels; app screens.
- **Access:** keep 24px or more between shell levels so each boundary is perceivable without color; the recommended plan also carries a text label.
- **Goes generic when:** every section becomes a dark island, which removes the contrast that made the first one matter.

### 3. Warm stone minimal
*Light, unhurried, process-oriented; warm neutrals instead of clinical white.*
- **Palette:** `--bg #EFEBE4`, shell `#F7F4EF`, panel `#E6E1D8`; `--text #23211D` (13.5:1 on bg, 14.6:1 on shell); `--text-2 #67625A` (5.1:1 on bg); `--accent #2F6170` slate teal (5.8:1 on bg, white on it 6.9:1); `--border #8C867C` (3.3:1 on shell); one dark inset card `#23211D` with `#F7F4EF` text (14.6:1).
- **Type:** Albert Sans 400/600; body 16px; headings modest, about 2.5x body on a marketing hero.
- **Shape and line:** 6px radius on controls, 10px on panels; 1px borders in a darker stone; an equal-column process grid with shared baselines.
- **Depth:** a single painted radial wash behind the shell (`radial-gradient` from `#F7F4EF` to `#E9E4DB`), no card shadows.
- **Signature:** a four-step process strip whose active step is the only accent on the page.
- **Motion:** 200ms fades, 24s background wash drift that stops under reduced motion.
- **Fits:** approval flows, operations products, B2B onboarding. **Fails:** brands that need energy.
- **Access:** low-contrast structure is fine for decoration, but every input keeps the 3:1 border and every status has a word.
- **Goes generic when:** it drifts to cream plus terracotta plus italic serif (taste detector 2).

### 4. Warm monochrome bento
*Flat, editorial and tidy: tiles of equal care, soft pastel fields, no gradients, no shadows.* Extends the catalog's *Editorial reading* and *Calm product*; this recipe only adds the bento and the pastel fields.
- **Palette:** `--bg #F6F5F2`, tile `#FFFFFF`, `--text #191917` (16.1:1), `--text-2 #5D5B56` (6.2:1); fields with their own ink: sage `#DCE5D8`/`#1F2A1D` (11.5:1, secondary `#4A5547` 6.1:1), blush `#EBDCD6`/`#2E1F1A` (11.9:1), mist `#DBE2EA`/`#1A2330` (12.1:1).
- **Type:** Instrument Serif for display only, Commissioner for everything else.
- **Shape and line:** grid of 6 columns, `grid-auto-rows: minmax(160px, auto)`, tiles spanning 2-4 columns; 16px radius; 1px `#E4E2DC` tile outline or a field color, never both.
- **Depth:** none; separation by field and outline.
- **Signature:** one large tile holding the real product fact, the rest smaller (taste detector 15 still applies).
- **Motion:** 150ms hover tone shift; no entrances.
- **Fits:** personal sites, small product overviews, settings summaries. **Fails:** comparison data that belongs in a table.
- **Access:** DOM order follows reading order, not tile placement; one column under 640px.
- **Goes generic when:** every tile gets a different pastel and an icon in a rounded square.

### 5. Archival reader
*A lit page inside a dark reading room: serif text on warm paper, catalog navigation around it.*
- **Palette:** room `#16130F` with `#D9D0C0` (12.1:1) and `#9C9283` (6.0:1); paper `#EFE6D3`, facing page `#E6DBC4`; ink `#2A2119` (12.7:1), ink-2 `#5E5142` (6.2:1 on paper, 5.6:1 on facing page); accent oxblood `#7B2D26` (7.5:1 on paper, white on it 9.4:1).
- **Type:** Bodoni Moda for display at 40px and above, Literata for body at 19-20px with line height 1.6 and a 60-68ch measure, DM Mono 12px for index entries, folios and citations.
- **Shape and line:** paper edges square; the room uses thin rails and an index sidebar 240-280px; marginal notes in a dedicated grid column.
- **Depth:** a center crease as a narrow `linear-gradient(90deg, transparent 47%, rgb(60 40 20 / .14) 50%, transparent 53%)`; inset edge shading on each page; texture at 2-3% and only in the outer page margins.
- **Signature:** drop caps with `initial-letter: 3` (plus the `-webkit-` form for Safari; a floated fallback inside `@supports not (initial-letter: 3)`), marginalia, folio numbers.
- **Motion:** 250ms page crossfade, no page-curl simulation.
- **Fits:** archives, research tools, story-led products, documentation with a literary voice. **Fails:** quick-task interfaces.
- **Access:** two-page spreads only from about 1100px; one page below that; index is `<nav aria-label="Index">` with `aria-current`; marginal notes are `<aside>` and fall inline on phones.
- **Goes generic when:** it is a beige card with a serif and no index, folio or margin structure.

## B. Paper and technical light

### 6. Paper technical
*Warm paper interior, dark surround, precise geometry: friendly to read, exact to look at.*
- **Palette:** surround `#1D1C1A` with `#E8E2D6` labels (13.2:1); paper `#F2EEE6`, layer `#E8E2D6`; `--text #1E1D1A` (14.6:1), `--text-2 #625D54` (5.6:1 on paper, 5.1:1 on layer); `--accent #1F5FBF` (5.3:1 on paper, white on it 6.1:1); `--border #8A8375` (3.2:1).
- **Type:** Golos Text for interface and copy; Fragment Mono 12px for timestamps, captions and window chrome.
- **Shape and line:** one large shell at 28px radius on the dark surround, crisp inner geometry at 4-8px; L-brackets 12px long at the shell's inner corners; a diagonal hatch at 3% on empty paper only.
- **Depth:** `0 30px 80px rgb(0 0 0 / .35)` under the shell; inner panels separated by tone.
- **Signature:** a working product mock (transcript, session list, editor) inside the paper, with real-looking data that adds up.
- **Motion:** masked headline, 300ms panel entrance, a live dot that breathes once every 2s.
- **Fits:** developer and productivity tools that want warmth. **Fails:** long documentation (use the catalog's *Technical documentation*).
- **Access:** hatch never under text; live indicators also say "Live" in text.
- **Goes generic when:** brackets and hatch appear on every panel.

### 7. Warm paper product (signal orange)
*A welcoming onboarding surface: warm paper, one orange that means "do this".*
- **Palette:** `--bg #F5F0E8`, card `#FFFDF9`; `--text #221E19` (14.6:1 on bg); `--text-2 #655D52` (5.7:1 on bg, 6.4:1 on card); orange fill `#B8440F` with white label (5.4:1), also passes as link text on bg (4.8:1); `--border #968C7E` (3.3:1 on card).
- **Type:** Plus Jakarta Sans 400/600; inputs 16px to avoid mobile zoom.
- **Shape and line:** 16px cards, 10px inputs and buttons; gradient border on the main card only.
- **Depth:** an orange-tinted shadow under the primary card, `0 24px 60px rgb(184 68 15 / .10)`.
- **Signature:** a split card: form on one side, a product panel with two or three floating objects showing the outcome (a statement, a card, a balance) on the other.
- **Motion:** 160ms focus ring growth, 6s float of the illustration objects at 6px amplitude, off under reduced motion.
- **Fits:** sign-up, onboarding, payments setup (pair with `../../forms-conversion.md`). **Fails:** dashboards with many statuses, where orange collides with warnings.
- **Access:** orange is not also the error color; errors use the product's semantic red plus an icon and text; follow `../../ethical-persuasion.md` for any urgency or social proof.
- **Goes generic when:** orange spreads to headings, icons and dividers (taste detector 4).

### 8. Technical split
*Two halves with two jobs: one immersive, one explanatory.* A layout system that takes the colors of whichever recipe it pairs with.
- **Palette (light/dark pair):** light half `#F4F4F1` with `#161616` (16.4:1) and `#5B5B57` (6.2:1); dark half `#101112` with `#ECECE8` (16.0:1) and `#9E9E99` (7.0:1); accent vermilion `#D9542C` on dark (4.7:1), `#B8401C` on light (5.0:1, white on it 5.5:1).
- **Type:** Chivo for text, Chivo Mono for spec rows and rails.
- **Shape and line:** 50/50 by default, 58/42 when the visual must dominate; each half has its own 24-32px inset frame; spec blocks as two-column rows with hairlines.
- **Depth:** an inset media window with a 1px edge in the visual half; nothing else.
- **Signature:** a sticky visual half (`position: sticky; top: 0; height: 100dvh`) while the explanatory half scrolls through specs.
- **Motion:** the visual swaps with a 300ms crossfade as each spec section enters, via IntersectionObserver.
- **Fits:** product detail, case studies, hardware, portfolios. **Fails:** content that is not naturally two-part.
- **Access:** stacks to one column under 900px with the visual first and short; the sticky half must not trap keyboard focus; swapped visuals have alt text or are `aria-hidden` if decorative.
- **Goes generic when:** both halves are equally dense and the split is only a vertical line.

## C. Atmospheric blue

### 9. Sky atmosphere
*Weightless and aspirational: a deep blue sky that lightens into cloud.*
- **Palette:** sky stops `#1747C9` (top) → `#2F6BDE` → `#BCD6F7` (horizon); white text 7.6:1 on the top stop, 4.9:1 on the middle, fails below it; pale text `#E4EEFF` 6.5:1 on top; grounded CTA `#0E1630` with white (17.9:1); ink `#0E1630` on the horizon zone (12.0:1).
- **Type:** Outfit 400/500 for display (no weights under 400 on gradient), 16-18px body.
- **Shape and line:** pills fully round; translucent white edges at 35%; tiny corner squares on the content shell.
- **Depth:** clouds, not shadows: a static `feTurbulence` fractal-noise layer (`baseFrequency` about 0.006-0.01, 4 octaves) rendered once into an image, plus 3 large radial gradients in white at 10-25%.
- **Signature:** copy placed only in the rich upper sky; the cloud-washed horizon carries logos or a dark CTA band.
- **Motion:** cloud image drifts with `translateX` over 80-120s; never animate the filter attributes themselves.
- **Fits:** travel, wellness, consumer AI, weather-adjacent or aspirational launches. **Fails:** dense apps, dark-mode-first products.
- **Access:** measure white text at the lightest point under its box; if a phone crop moves the text lower, switch to ink there.
- **Goes generic when:** one headline word turns italic serif (taste detector 10) or clouds become clip-art.

### 10. Navy with a cobalt block
*Crisp and architectural: deep navy everywhere, one saturated cobalt slab where the action is.*
- **Palette:** `--bg #060B18`, `--surface #0C1426`; `--text #F2F5FA` (18.0:1); `--text-2 #9DB0CC` (8.9:1, 8.3:1 on surface); cobalt block `#1D46C8` with white (7.6:1) and pale `#C9D6FF` support text (5.3:1); link blue `#7FA2FF` (8.0:1 on bg).
- **Type:** Readex Pro 300 for display at 56px and up (thin on dark only at large sizes), 400 for body.
- **Shape and line:** 24px radius on the cobalt block, gradient border from cobalt to transparent; footer and link index separated by white rules at 8%.
- **Depth:** one large blurred cobalt bloom (`filter: blur(80px)`, opacity .35) behind the block; nothing else glows.
- **Signature:** the cobalt slab as the conversion zone inside an otherwise quiet dark page.
- **Motion:** masked reveal, 200ms hover lift of 2px on link cards.
- **Fits:** infrastructure, finance-adjacent marketing, developer platforms. **Fails:** long reading as the only theme.
- **Access:** never put pale-blue text on cobalt at small sizes below the measured `#C9D6FF`; focus rings in white with a 2px offset, visible on both navy and cobalt.
- **Goes generic when:** cobalt floods every section or electric cyan glows appear.

### 11. Dark mesh shell
*A procedural blue field contained inside one hero shell, with a disciplined page around it.*
- **Palette:** `--bg #050A14`, shell `#0A1222`; `--text #F4F7FB` (18.4:1); `--text-2 #94A6BE` (8.0:1, 7.5:1 on shell); mesh stops `#1A3FA8`, `#2B2A7A`, `#2E5878` (decorative); primary CTA solid `#F4F7FB` with `#050A14` label (18.4:1); secondary CTA ghost with gradient edge.
- **Type:** Geologica 500 display, 400 body.
- **Shape and line:** 32px shell radius; 999px nav pill; 6px node dots.
- **Depth:** the mesh itself; a dark vertical scrim from 20% to 60% opacity behind the copy column so text never sits on the brightest blob.
- **Signature:** mesh built from 3-4 radial gradients whose centers move via registered `@property` custom properties (supported in all current engines), or a small canvas when you need warping; add 2% noise to prevent banding on 8-bit displays.
- **Motion:** 24-36s drift; nodes shimmer at most once every 4s; freeze under reduced motion.
- **Fits:** infrastructure, networks, platform launches. **Fails:** when the mesh is outside a container and becomes a full-page wallpaper.
- **Access:** test text contrast at the brightest mesh position, not an average frame.
- **Goes generic when:** it is a static purple-blue blob with no shell, rails or real content.

## D. Dark glass

### 12. Dark frosted panels
*Translucent smoky panels with a fine light edge.* Mostly covered by [translucent-materials.md](translucent-materials.md) and `STY-05`; this adds only the recipe values.
- **Palette:** page `#070B14`; glass tint `#0E1626`; `--text #E8ECF3`; `--text-2 #AAB4C3`; accent `#7FB0FF` (9.0:1 on page). Over the dark page alone the composited panel is about `#0B121F` and both tiers pass easily (15.8:1, 8.9:1); if anything bright can scroll behind, the tint needs alpha 0.64 for the primary tier and 0.80 for the secondary tier.
- **Type:** the system stack, which loads nothing.
- **Shape and line:** 20-24px radius; masked gradient edge (method B in the kit) at 1px; top inner highlight `inset 0 1px 0 rgb(255 255 255 / .1)`.
- **Depth:** `0 20px 50px rgb(2 6 16 / .45)` on floating panels only.
- **Fits / fails:** floating chrome over calm backgrounds / content panels over photos and video.
- **Access:** solid fallback under `prefers-reduced-transparency`, `prefers-contrast: more` and without `backdrop-filter`.

### 13. Glass workspace
*A calm dark workspace where glass is the layout language: nav pill, side shells, a quiet center stage.*
- **Palette:** monochrome: `--bg #09090B`, glass tint `#17171A`; `--text #EDEDEF` (17.0:1); `--text-2 #A6A6AE` (8.2:1); status dot `#7EE0B5` (12.5:1) as the only color. Worst-case alpha 0.64 (primary) and 0.84 (secondary); in practice put side shells on a near-opaque 0.85 fill and keep the lighter glass for the nav pill.
- **Type:** DM Sans 400/500; DM Mono 11-12px for system IDs and log rows.
- **Shape and line:** 999px nav, 16px shells, 10px rows; gradient edges at 30%.
- **Depth:** a soft radial wash behind the center headline; blurred particle field at 20% opacity behind everything.
- **Signature:** three columns on desktop (navigation, stage, operations) with at most three floating notes around the stage.
- **Motion:** notes drift 4px over 8s; 150ms row hover brightening.
- **Fits:** AI workspaces, intelligence tools, consoles. **Fails:** mobile-first products (on phones it becomes one column of plain dark cards, and that is correct).
- **Access:** glass on glass is not allowed; floating notes never cover the stage's primary action.
- **Goes generic when:** the center fills with cards and the calm stage disappears.

### 14. Laser beam behind glass
*A single thin beam of light behind a clean glass dashboard: cinematic, but disciplined.*
- **Palette:** `--bg #04060D`; `--text #EEF1F8` (17.9:1); `--text-2 #9AA6C2` (8.3:1, 7.7:1 on panel `#0D1220`); beam core `#FFFFFF`, halo `#4C6BFF`; CTA `#3A5BE0` with white (5.6:1).
- **Type:** Urbanist 500/600, 15-16px body.
- **Shape and line:** glass cards 18px; the beam has two parts: a 1-2px core and a separate 60-120px halo; never let the core grow to match the halo.
- **Depth:** core as a div with a vertical white-to-accent gradient; halo as a wider div with `filter: blur(32px)`, `mix-blend-mode: screen`, opacity .5; fog as one large, faint radial gradient near the beam's base. No WebGL needed.
- **Signature:** the beam passes behind the dashboard shell and lights its top edge where they cross.
- **Motion:** halo opacity eases between .45 and .6 over 6s; the core never pulses.
- **Fits:** security, observability, AI infrastructure launches. **Fails:** pages that need light mode first.
- **Access:** no text crosses the beam's core; measure text over the halo's brightest point; static under reduced motion.
- **Goes generic when:** the beam thickens into a neon bar or several beams appear.

### 15. Instrument dial
*A black instrument panel anchored by one large circular dial: precise, meditative.*
- **Palette:** `--bg #050505`; `--text #F2F2F2` (18.2:1); `--text-2 #9B9B9B` (7.3:1, 6.6:1 on `#141414` capsules); lines white at 8-14%; no hue.
- **Type:** Familjen Grotesk for copy; Azeret Mono 10-11px for degree labels and ring text.
- **Shape and line:** capsules 999px; a faint 64px grid with crosshairs aligned to the dial's center.
- **Depth:** build the dial in SVG: outer ring, a tick ring from one circle with `stroke-dasharray` (circumference ÷ 60 per tick), labels on `<textPath>`, a core with a soft white radial highlight.
- **Signature:** the dial sits on the grid's crosshair and the headline aligns to its horizontal axis.
- **Motion:** ring groups rotate with `transform-box: fill-box; transform-origin: center` at one turn per 90-180s, in opposite directions; static under reduced motion.
- **Fits:** time, scheduling, calibration, audio and hardware products. **Fails:** when the dial has no meaning for the product.
- **Access:** the dial is `aria-hidden`; any value it shows (a time, a level) also appears as text in a `<time>` or `<output>`.
- **Goes generic when:** the dial is decoration unrelated to what the product measures.

## E. Dark, framed and technical

### 16. Framed monochrome shell
*Identity from boundaries: an engineered black shell, gradient edges, uneven panels.*
- **Palette:** `--bg #08090A`, panel `#0F1012`, raised `#16171A`; `--text #ECEDEE` (17.0:1); `--text-2 #9A9DA3` (7.3:1); locked rows `#6B6E75` (3.7:1 on panel, only for rows that are also labeled "Locked"); no accent until the brand supplies one.
- **Type:** Bai Jamjuree 400/600; Martian Mono 11px for rails and section codes.
- **Shape and line:** 4-8px radius, rails that overshoot the shell by 24px, panels divided by 1px seams rather than gaps.
- **Depth:** gradient edges at 40% → 4%; one monochrome wave canvas inside a single panel.
- **Signature:** an asymmetric 7/5 panel grid with one hero, one visualization and one list panel; active list rows get a 2px left bar.
- **Motion:** a 1px scan line crosses a panel once on entry over 900ms.
- **Fits:** infrastructure, permissions, security, developer platforms. **Fails:** consumer warmth.
- **Access:** active state uses bar, weight and text color, not color alone.
- **Goes generic when:** edges glow or every panel gets a scan line.

### 17. Dither and beam
*Dark with grain: an ordered-dither texture gives the black material, a beam gives it direction.*
- **Palette:** `--bg #0A0A0C`, panel `#121216`; `--text #EAEAEE` (16.5:1); `--text-2 #9C9CA6` (7.3:1); accent from the brand (example `#FF6A3D`, 7.0:1 on bg, with ink `#1A0A04` on it 6.8:1); beam core near white, halo in the accent.
- **Type:** Space Grotesk for copy, Departure Mono for labels at 11-12px.
- **Shape and line:** 10px panels, 1px edges at 12%.
- **Depth:** dither as a tiled 4x4 Bayer pattern (a tiny inline SVG or PNG with `image-rendering: pixelated`) at 4-7% opacity, in empty regions only; or in a shader, threshold luminance against the Bayer matrix.
- **Signature:** dithered falloff around the beam's halo, smooth elsewhere.
- **Motion:** the beam sweeps once across the hero on load over 1.2s, then holds.
- **Fits:** premium dev tools, hardware, audio, games studios. **Fails:** text-heavy surfaces; tiny screens where the pattern aliases.
- **Access:** no dither behind text; check that zoom at 200% does not produce moiré.
- **Goes generic when:** dither covers everything and the UI looks low-resolution.

### 18. Emerald signal console
*Calm analytics on dark with a green that means "live" or "healthy".*
- **Palette:** `--bg #070A09`, surface `#0D1311`, raised `#131B18`; `--text #E5EEEA` (16.8:1); `--text-2 #8FA39B` (7.5:1, 6.6:1 on raised); `--accent #3ED598` (10.6:1 on bg), ink on it `#04140D` (10.1:1).
- **Type:** Onest for copy and figures with `tabular-nums`; Commit Mono for IDs and timestamps.
- **Shape and line:** 8px cards, 1px edges, 8px corner brackets on the outer shell only; a 32px grid at 3%.
- **Depth:** small underglow on one focus card, `0 0 0 1px rgb(62 213 152 / .25), 0 12px 40px rgb(62 213 152 / .08)`.
- **Signature:** neutral charts with green only on the series that answers the question.
- **Motion:** values update without entrances; a changed cell holds a tint for 1.5s.
- **Fits:** monitoring, analytics, energy, fintech operations. **Fails:** when green collides with the success status; make status a different hue or pair it with icons and words.
- **Access:** green is never the only carrier of state; check the accent against the semantic set.
- **Goes generic when:** green glows everywhere (taste detector 3).

### 19. Acid signal and live viewport
*A build console: a hard-framed shell, numbered stages, and a real-time 3D viewport in acid lime.*
- **Palette:** `--bg #0B0C0B`, surface `#121412`; `--text #EDEFEA` (16.9:1); `--text-2 #9AA096` (7.3:1); `--accent #B6F23A` (14.7:1), ink on it `#10140A` (14.0:1).
- **Type:** Chakra Petch for display and stage names, Azeret Mono for percentages and status.
- **Shape and line:** radius 0-2px, bracketed corners, a hard vertical divider between content and viewport.
- **Depth:** the viewport (Three.js points or instanced geometry, additive blending, fog) tinted with the accent; a static poster image while it loads.
- **Signature:** the stage list and the viewport are linked: selecting a stage changes what the scene shows.
- **Motion:** camera orbit at 0.05 rad/s, pointer influence damped; particle counts capped (start at 20k, measure).
- **Fits:** developer tools, synthesis or generation products, data infrastructure. **Fails:** anyone on a low-power device without the fallback.
- **Access:** viewport `aria-hidden` with a text summary beside it; full static fallback under reduced motion; lime fills always carry dark ink.
- **Goes generic when:** the scene is a random particle globe disconnected from the product.

### 20. Violet container with a focal object
*Technical containers with fashion: purple light, one strange beautiful object.*
- **Palette:** `--bg #08060D`, surface `#110D1A`; `--text #F1EDF8` (17.5:1); `--text-2 #A79DBB` (7.9:1); violet text `#C99BFF` (9.2:1); violet fill `#7C2FD6` with white (6.5:1); secondary blue light decorative only.
- **Type:** Unbounded for short display lines, Outfit for text.
- **Shape and line:** rounder than the other dark recipes (search bar 999px, cards 24px) balanced by straight rails and corner squares.
- **Depth:** one focal object (a glowing sphere, an orbit ring with rotating text, a floor of light) placed behind the headline, built in CSS or a small canvas.
- **Signature:** a large search or filter bar as the hero control.
- **Motion:** ring text rotates once per 40s; the sphere breathes 4% in scale over 8s.
- **Fits:** creative networks, talent and community platforms, fashion-tech. **Fails:** regulated or conservative audiences.
- **Access:** the focal object never sits behind the search bar's text; reduced motion stops rotation.
- **Goes generic when:** violet gradients appear on buttons and text (taste detectors 1 and 6).

### 21. Annotated wireframe
*A diagnostic view: one exploded wireframe object, labels routed to its parts, almost no color.*
- **Palette:** `--bg #060606`; `--text #EDEDED` (17.3:1); `--text-2 #8E8E8E` (6.2:1, 5.8:1 on label pills `#111111`); primary edges white at 55% (about `#8F8F8F`, 6.3:1), secondary edges at 30% (2.6:1, decorative only).
- **Type:** Instrument Sans for the one heading; Fragment Mono 11px for labels and metrics.
- **Shape and line:** 999px label pills, 1px routed connectors with 90° or 45° bends, dashed for inferred links.
- **Depth:** the object from edges only (Three.js `EdgesGeometry` with `LineSegments`, or hand-built SVG), parts separated along one axis.
- **Signature:** labels are real DOM text positioned by projecting each part's anchor point to screen space every frame the camera moves.
- **Motion:** 0.03 rad/s rotation, labels appear in order of the structure, top to bottom.
- **Fits:** product teardowns, hardware specs, architecture explainers. **Fails:** when there is no real structure to explain.
- **Access:** wrap in `<figure>` with a `<figcaption>` that lists the parts; a static SVG fallback; labels at least 11px and 4.5:1.
- **Goes generic when:** the object is unrelated art and the labels are lorem ipsum.

## F. Tactile

### 22. Raised and pressed material
*Controls that look manufactured: lit from above, raised at rest, inset when pressed.* Distinct from the catalog's *Soft tactile*, which is same-color extrusion.
- **Palette:** `--bg #E9ECF1`; surface gradient `#F7F8FA` → `#D5DAE2`; `--text #1E2532` (13.0:1 on bg, 10.9:1 on the darkest stop); `--text-2 #4F5869` (6.0:1, 5.1:1 on darkest); accent `#2D5BD7` (4.9:1, white on it 5.9:1); control border `#7A8395` (3.2:1).
- **Type:** Nunito Sans 600 for labels at 15px and up.
- **Shape and line:** 14-22px radius by size; a 1px gradient border light at top, darker at bottom.
- **Depth (raised):** `0 1px 2px rgb(30 40 60 / .14), 0 10px 24px rgb(30 40 60 / .16), inset 0 1px 0 rgb(255 255 255 / .75), inset 0 -1px 0 rgb(30 40 60 / .18)`. **Pressed:** shadows turn inward (`inset 0 3px 8px rgb(30 40 60 / .22)`), gradient flips, `translateY(1px)`.
- **Signature:** one material per component (plastic, enamel, ceramic or brushed metal), consistent light direction everywhere.
- **Motion:** press 90-120ms, release 180-220ms ease-out.
- **Fits:** media transport, audio, smart-home, calculators, a hero device. **Fails:** whole data-heavy apps.
- **Access:** the on state is fill plus label, never depth alone; 2px accent focus ring with 2px offset; emboss text-shadow at most `0 1px 0 rgb(255 255 255 / .6)` and remeasure.
- **Goes generic when:** leather, wood and chrome appear together, or every surface is raised.

### 23. Molded dark shell on a light page
*A black, precisely molded device-like shell placed on a pale page: high contrast, industrial-clean.*
- **Palette:** page `#E7E6E2` with `#16171A` text (14.4:1) and `#4F4E4A` (6.7:1); shell gradient `#17181B` → `#0E0F11`; shell text `#F3F3F1` (17.3:1), `#A2A39F` (7.6:1); signal `#FF8A3D` (8.2:1 on shell) with ink `#1A0C02` on it (8.2:1).
- **Type:** Manrope 500/700; mono only for readouts.
- **Shape and line:** shell 36px radius or 16px chamfer; modules 18px; white-to-transparent edges.
- **Depth:** shell `0 40px 90px rgb(10 10 12 / .35)`; modules with inset top highlight and inner shadow so they read as seated in the shell.
- **Signature:** small physical widgets inside the shell (a search plate, a document tile, an orbit, a progress sliver) built in code with real data.
- **Motion:** 400ms module lift on hover of 2px, slow highlight sheen once on load.
- **Fits:** AI and hardware products, premium developer tools. **Fails:** if the page content outside the shell is thin.
- **Access:** the shell must not be the only place content lives on phones; let it become full-bleed under 640px.
- **Goes generic when:** every module carries the same glossy highlight.

## G. Image-led and raw

### 24. Photo stage
*The photograph is the stage; a quiet grid and anchored copy sit on top.*
- **Palette:** white text and neutral grays over a scrim; for white text over any photo the scrim under the text box needs black at 0.54 alpha (normal text) or 0.42 (large text, 24px or 18.66px bold); a tinted scrim `#0B0D10` needs 0.57. Accent sampled from the image and remeasured (`STY-08`).
- **Type:** Figtree 500 display, 400 body.
- **Shape and line:** sparse nav, vertical rails at 12% white aligned to the grid, low-fill proof box with 1px edge.
- **Depth:** directional scrims (`linear-gradient` from the copy corner) reaching the required alpha only under text, clear elsewhere.
- **Signature:** copy anchored bottom-left, a quote or metric in an adjacent lane; the subject of the photo left unobstructed.
- **Motion:** 1.2s image fade on load, 10% parallax at most, off under reduced motion; no scroll hijacking (`MOT-16`).
- **Fits:** hospitality, real estate, outdoor, architecture, events. **Fails:** without a genuinely strong photograph.
- **Performance:** the hero is the LCP: AVIF/WebP, `fetchpriority="high"`, explicit width and height, `srcset` with `sizes`, and `<picture>` art direction so the phone crop keeps the subject clear of the copy.
- **Access:** alt text describes the scene when it carries meaning; generated imagery follows `../../creative-media/references/generation-prompting.md` and never passes as a photo of the real place or product.

### 25. Industrial blueprint
*Swiss print discipline meets a field terminal: rigid grid, extreme scale contrast, utilitarian color, analog wear.* Extends the catalog's *Brutalist* and *Retro terminal*; this recipe adds the fusion and the degradation layer.
- **Palette:** newsprint `#E9E7E1` with ink `#0D0D0D` (15.7:1) and `#3A3A38` (9.2:1); signal red text `#B01E17` (5.6:1, white on it 6.9:1); terminal panel `#0F0F0E` with `#E9E7E1` (15.5:1), `#B4B2AC` (9.0:1) and amber `#FFB000` (10.5:1).
- **Type:** Anton for condensed display at 10-20 times body size; Sometype Mono for everything below the display.
- **Shape and line:** radius 0; 2px ink rules; a 12-column grid with visible register marks only at the page corners; stamped labels (classification, revision, sheet number).
- **Depth:** none; print effects instead: a halftone on images (CSS `radial-gradient` dot mask or a pre-processed image), a 1-2px misregistration offset on display type, static noise at 4%.
- **Signature:** a data table or spec sheet as the hero, set like a drawing title block.
- **Motion:** stepped and instant, `steps(4)` at 120ms; no flicker, no animated glitches.
- **Fits:** portfolios, data-heavy editorial, developer tools with attitude, events. **Fails:** health, money, reassurance.
- **Access:** degradation never touches body text or controls; misregistered type stays `aria-hidden` duplicates of a clean heading; contrast is measured on the newsprint, not on white.
- **Goes generic when:** noise, glitch and fake redactions hide the content.

## Done when

- One recipe was chosen, with a one-line reason tied to the audience and task, and any borrowed trait is named.
- Every text and background pair in use, including over atmospheres, scrims and glass at their worst point, is measured and recorded with the tokens (`BRD-03`).
- Frame-kit pieces align to real grid tokens, and each surviving ornament has a stated job.
- Atmospheric layers are `aria-hidden`, capped, paused off-screen, frozen under reduced motion and replaced by a static fallback on weak devices.
- Nothing flashes more than three times per second; nothing moves on its own under reduced motion.
- Phone layouts were checked at 390px: shells, splits and bentos collapse to one readable column.
- The taste self-critique in [taste.md](taste.md) was run and its swap test passes.
