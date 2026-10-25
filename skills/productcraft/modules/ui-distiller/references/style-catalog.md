# UI Distiller: Style catalog

Read this when a project has no visual language yet, when the user asks for a direction ("make it feel premium", "more playful", "like a terminal"), or when a redesign needs a coherent system instead of piecemeal fixes. Each entry is a complete starting system: when it fits, a palette with measured contrast, a freely licensed font pairing, the character of its spacing, shape and motion, and how it goes generic.

These are starting points, not themes to paste. The project's brand, tokens and request win (`../GUIDE.md`, step 4). When a brand exists, keep its colors and faces and borrow only what it lacks: proportions, type scale, shape and motion character. Use one direction per product (`STY-01`); a marketing site may be louder than the app behind it while sharing palette and type. For single treatments such as glass or glows, see `STY-` rules in `../../../references/ui-rules/style-options.md`. To keep any direction from sliding into defaults, run the detectors in [taste.md](taste.md).

## Choosing a direction

Answer three questions from the product, not from preference:

1. **How long and how often do people use it?** Hours a day calls for calm, low-motion systems; a single visit can carry a louder one.
2. **How much information does one screen hold?** Dense data needs small radii, borders and compact rows; sparse pages can carry large type and fields of color.
3. **How loudly should the brand speak?** Public services and money speak quietly; launches and events can shout.

| Product | Usually fits | Usually wrong |
|---|---|---|
| Daily B2B tool, admin, settings | Calm product, Dense data console | Flat poster, Brutalist |
| Monitoring, trading, logs, analytics | Dense data console | Playful consumer, Gallery quiet |
| Developer docs, API reference | Technical documentation, Retro terminal (for a developer brand) | Premium dark for long reading |
| Publication, reports, long articles | Editorial reading, Swiss grid | Soft tactile |
| Public service, health, benefits | Civic clarity | Brutalist, Retro terminal |
| Consumer habit or social app | Playful consumer, Calm product | Dense data console |
| Media, film, music, pro creative tool | Premium dark | Civic clarity as the only theme |
| Food, wellness, craft, local business | Warm organic, Gallery quiet | Retro terminal |
| Hotel, restaurant, fashion, architecture | Gallery quiet, Editorial reading | Dense data console |
| Launch, event, campaign page | Flat poster, Brutalist, Swiss grid | Soft tactile |
| A handful of large physical controls | Soft tactile (with its safeguards) | Soft tactile for whole apps |

Write one line in the report on why the direction fits this audience and task. If two directions fit, pick the quieter one for anything used daily.

## Applying a direction

- **Tokens.** Map the palette onto semantic tokens and reference only those (`CMP-02`, `COL-09`). Names below match the ProductCraft reference screens: `--bg` (page ground), `--surface` (panels, fields, tiles), `--text`, `--text-2` (secondary text), `--accent` (primary action, links, current item), `--on-accent` (text on the accent), `--border` (input and control outlines), `--focus`. Fields are extra grounds, each with its own ink.
- **Status colors** (success, warning, error) come from the product's semantic set and are not part of these palettes (`COL-06`, `COL-10`). Check them against each direction's ground.
- **Dark mode.** Only some entries list a dark palette. For the others, build the dark theme as its own palette (`DRK-01` to `DRK-05`) and check it the same way.
- **Contrast.** Every ratio below was computed with the WCAG 2.x relative-luminance formula. If you change any value, recompute: normal text needs 4.5:1, large text and meaningful UI boundaries 3:1 (`COL-01`). This standard-library check reproduces the numbers:

```python
def luminance(hex_color):
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

def ratio(fg, bg):
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

print(f"{ratio('#1A1A18', '#FAFAF8'):.1f}:1")  # 16.7:1, Editorial text on ground
```

- **Fonts.** Every face named here is published under the SIL Open Font License 1.1, which allows use, embedding and self-hosting in commercial products; keep the license file next to self-hosted copies, do not sell the font files on their own, and rename any modified version whose license lists a Reserved Font Name. Confirm the license file shipped with the exact version you download. Load only the weights in use, subset, use `font-display: swap`, keep a fallback stack of the same kind, and preload at most the one display weight seen above the fold (`TYP-01`). Prefer self-hosting for privacy-sensitive or EU-facing products: loading fonts from a third-party server sends each visitor's IP address to that server, and a 2022 German regional court ruling held that doing so without consent breached the GDPR. A system stack needs no font files and no license.
- **Motion values** stay inside the budget of `MOT-02` and the easings of `MOT-03`, and every direction keeps the reduced-motion path of `MOT-04`.

## The directions

### 1. Editorial reading

**Use for:** publications, long articles, essays, annual reports, content-led marketing. **Avoid for:** dense tools, dashboards, checkout flows.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#FAFAF8` | |
| `--surface` | `#F1F0EC` | |
| `--text` | `#1A1A18` | **16.7:1 on bg**, 15.3:1 on surface |
| `--text-2` | `#5B5A55` | 6.6:1 on bg, 6.1:1 on surface |
| `--accent` (oxblood: links, current item, primary button) | `#7A1F2B` | 9.8:1 on bg, so it also passes as link text |
| `--on-accent` | `#FFFFFF` | 10.2:1 on accent |

- **Type:** Newsreader for headings and running text, using its optical sizes (OFL 1.1), with Instrument Sans for labels, captions and controls (OFL 1.1). Fallbacks `Georgia, "Times New Roman", serif` and `system-ui, sans-serif`. Body 18-20px, line height about 1.6, measure 60-70ch; display three to five times the body size.
- **Space and shape:** 8px base; generous vertical rhythm (about 96-160px between sections on desktop, 56-80px on phones); images square-cornered; 2-4px radius on inputs and buttons only; no shadows. A rule appears only as a typographic device, such as above footnotes.
- **Motion:** almost none on reading content. Link underline changes about 150ms; disclosures about 200ms ease-out; no entrance animation on paragraphs.
- **Signature:** a decisive type scale and a real reading measure.
- **Goes generic when:** a cream ground with a clay accent and an italic accent word arrives (taste detectors 2 and 10), or hairlines separate everything.

### 2. Swiss grid

**Use for:** institutions, studios, conferences, information-rich corporate pages, wayfinding. **Avoid for:** playful consumer products, care contexts that need warmth.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#FFFFFF` | |
| `--surface` | `#F2F2F2` | |
| `--text` | `#111111` | **18.9:1 on bg**, 16.9:1 on surface |
| `--text-2` | `#575757` | 7.2:1 on bg, 6.5:1 on surface |
| `--accent` (cobalt) | `#1438A6` | 9.8:1 on bg, passes as link text |
| `--on-accent` | `#FFFFFF` | 9.8:1 on accent |

- **Type:** Archivo as the single family (OFL 1.1): 400 and 600 for text, 800 and its width axis for display. Fallback `"Helvetica Neue", Arial, sans-serif`. Flush left, ragged right, tabular figures for data.
- **Space and shape:** a strict 12-column grid with one gutter; 8px base; radius 0; no shadows; hierarchy from size, weight and position only; asymmetric compositions on the grid with equal side margins.
- **Motion:** 150-200ms ease-out, movement along the grid axes, no scale bounce.
- **Signature:** visible alignment, with two or three shared left edges on the whole page, and one very large size against small ones.
- **Goes generic when:** drawn grid lines, crosshairs and "01 / 02 / 03" markers stand in for real structure, or everything is centered.

### 3. Calm product

**Use for:** B2B software, productivity tools, admin and settings-heavy products used every day. **Avoid for:** campaigns that need a loud identity, long-form reading.

| Role | Light | Dark |
|---|---|---|
| `--bg` | `#F6F7F9` | `#111418` |
| `--surface` | `#FFFFFF` | `#1A1F26` |
| `--text` | `#1C2330` | `#E6E9EE` |
| `--text-2` | `#566072` | `#A3ACB9` |
| `--accent` (deep teal) | `#0B6E6E` | `#5CC8C8` |
| `--on-accent` | `#FFFFFF` | `#0A1F1F` |
| `--border` (inputs) | `#8A93A3` | retune per `DRK-06` |

- **Measured, light:** **text 14.7:1 on bg**, 15.8:1 on surface; text-2 5.9:1 on bg; on-accent 6.1:1; accent 5.7:1 on bg (passes as link text); input border 3.1:1 on surface. **Dark:** **text 15.2:1 on bg**, 13.6:1 on surface; text-2 8.1:1; on-accent 8.6:1; accent 8.3:1 on surface.
- **Type:** Figtree (OFL 1.1), or the system stack `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`, which loads nothing. App body 14-16px; marketing body 16-18px.
- **Space and shape:** 4/8 scale; 16-24px panel padding; radius 6px for inputs and buttons, 8px for cards, 12px for dialogs; resting cards separated by a tone step or a 1px border, one method throughout; shadow tokens only for menus, popovers and dialogs (`CMP-07`).
- **Motion:** 120-200ms ease-out for hover, press and menus; 200-300ms for panels and sheets; no decorative entrances inside the app.
- **Signature:** the product's real data and states rendered with care; one accent with one job.
- **Goes generic when:** the framework's default indigo, a gradient hero over a mock dashboard, or identical KPI tiles with icon circles appear (taste detectors 1, 18, 27).

### 4. Dense data console

**Use for:** operations consoles, monitoring, trading, analytics, logs, internal tools used for hours. **Avoid for:** consumer onboarding, marketing pages.

| Role | Light | Dark |
|---|---|---|
| `--bg` | `#FFFFFF` | `#0F1115` |
| `--surface` | `#F4F5F7` | `#171A20` |
| `--text` | `#16181D` | `#E3E6EA` |
| `--text-2` | `#4F5563` | `#9AA1AD` |
| `--accent` | `#2550B8` | `#7AA7FF` |
| `--on-accent` | `#FFFFFF` | `#0B1530` |
| `--border` (inputs, table frame) | `#8C929D` | retune per `DRK-06` |

- **Measured, light:** **text 17.8:1 on bg**, 16.3:1 on surface; text-2 7.5:1; on-accent 7.2:1; accent 7.2:1 on bg; border 3.1:1. **Dark:** **text 15.1:1 on bg**, 13.9:1 on surface; text-2 7.3:1; on-accent 7.6:1; accent 7.3:1 on surface.
- **Type:** IBM Plex Sans for interface text and figures with `tabular-nums`, IBM Plex Mono for IDs, code and log lines (both OFL 1.1). Fallbacks `system-ui, sans-serif` and `ui-monospace, Menlo, Consolas, monospace`. Base 13-14px, never under 12px (`TYP-04`).
- **Space and shape:** 4px base; rows 32-36px compact and 40-44px comfortable, with a density setting; radius 2-4px; 1px borders and row separators belong here (`LAY-07` note); sticky header row and identifier column; shadows only on popovers and menus.
- **Motion:** 120ms or less, or none; no entrance animation when data refreshes (`CMP-18`); a changed cell may hold a tint that fades over one to two seconds, replaced by a static marker under reduced motion.
- **Signature:** aligned figures, keyboard speed and exceptions first (`CMP-19`).
- **Goes generic when:** it turns dark-by-default with neon series and glows, a hue per series, or cards where a table belongs.

### 5. Playful consumer

**Use for:** habit and hobby apps, social products, learning for teens and adults, food ordering. **Avoid for:** money, health records, enterprise, any moment where users are anxious.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#FFFFFF` | |
| `--surface` | `#F5F3EE` | |
| `--text` | `#1E1B16` | **17.2:1 on bg**, 15.5:1 on surface |
| `--text-2` | `#5A554C` | 7.4:1 on bg, 6.7:1 on surface |
| `--accent` (raspberry) | `#B8235A` | 6.1:1 on bg |
| `--on-accent` | `#FFFFFF` | 6.1:1 on accent |
| Field: sun | `#FFD84D` with ink `#1E1B16` | 12.4:1 |
| Field: mint | `#9FE3C3` with ink `#0E2A1E` | 10.4:1 |

- **Type:** Bricolage Grotesque for display (OFL 1.1) with Figtree for text (OFL 1.1). Fallback `system-ui, sans-serif`.
- **Space and shape:** 8px base and generous padding; 16-24px radius on cards and sheets, pill buttons and chips; optional 2px outlines in ink; flat color fields instead of gradients; any shadow is a short solid offset, not a blur.
- **Motion:** springs only for physical or celebratory moments (`MOT-12`), about 300-500ms and skippable; everyday controls 150-250ms without overshoot; a static celebration state under reduced motion.
- **Signature:** confident fields of color and a characterful display face, in a few places.
- **Goes generic when:** emoji become icons, mascots appear everywhere, every card gets its own pastel, every tap bounces.

### 6. Premium dark

**Use for:** film, music and other media, professional creative tools, luxury goods, evening hospitality. **Avoid for:** long reading as the only theme, form-heavy admin, public services by default (offer a light theme, `DRK-07`).

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#0E0E10` | |
| `--surface` | `#18181B` | |
| `--text` (warm off-white) | `#ECEAE6` | **16.1:1 on bg**, 14.8:1 on surface |
| `--text-2` | `#A8A49C` | 7.8:1 on bg, 7.1:1 on surface |
| `--accent` (champagne) | `#C9A96E` | 8.6:1 on bg |
| `--on-accent` | `#17140E` | 8.2:1 on accent |

- **Type:** Cormorant Garamond for display at 32px and above only (OFL 1.1), Manrope for text and controls (OFL 1.1). Light text on dark looks heavier: keep body at regular weight and add a little line height.
- **Space and shape:** generous spacing; elevation by lighter surfaces (`DRK-03`) and hairlines at about 8-12% white (`DRK-09`); either sharp 0-4px corners or one large radius for media cards, chosen once; no shadows, no glows.
- **Motion:** 250-450ms ease-out fades and crossfades; one signature reveal, such as media opening to full width; a cut or plain crossfade under reduced motion.
- **Signature:** the media itself, large, on a quiet ground, with the accent in small doses.
- **Goes generic when:** a neon accent, glowing borders, glass cards or gradient text appear (taste detectors 3, 6, 22).

### 7. Brutalist

**Use for:** portfolios, independent publishers, events, counter-culture brands, community sites for developers. **Avoid for:** payments, health, enterprise, audiences that need reassurance.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#F4F4F0` | |
| `--surface` | `#FFFFFF` | |
| `--text` | `#0A0A0A` | **18.0:1 on bg**, 19.8:1 on surface |
| `--text-2` | `#3D3D3D` | 9.9:1 on bg |
| `--accent` (safety orange fill) | `#F54C00` | 3.2:1 against bg as a fill |
| `--on-accent` | `#0A0A0A` | 5.6:1 on accent (white fails here) |
| `--border` | `#0A0A0A` | 18.0:1 on bg |

- **Type:** Archivo Black for display with Archivo for text (one family, OFL 1.1), and Space Mono for metadata (OFL 1.1). Monospace is part of this direction's language; keep paragraphs in Archivo.
- **Space and shape:** structure on show: 2-3px solid ink borders, radius 0, hard offset shadows with no blur (for example `4px 4px 0 #0A0A0A`) on raised controls; deliberate tension inside the grid but equal side margins; very large type.
- **Motion:** instant or stepped, 0-100ms with `steps()`; hover inverts colors or moves the offset shadow while the hit box stays still (`ENG-04`, `BTN-12`).
- **Signature:** rawness that is still consistent and legible; the structure is the decoration.
- **Goes generic when:** random rotations and overlaps hide content, "raw" gray text drops below contrast, or focus styles are removed for the look.

### 8. Retro terminal

**Use for:** developer tools, command-line products' websites, technical status pages, security or hacker-themed games. **Avoid for:** general consumers and long prose; keep the contrast and flash limits strictly for photosensitive and low-vision users.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#0B0F0B` | |
| `--surface` | `#121812` | |
| `--text` (phosphor) | `#A8F0A0` | **14.4:1 on bg**, 13.4:1 on surface |
| `--text-2` | `#73B86B` | 8.1:1 on bg, 7.6:1 on surface |
| `--accent` (amber) | `#FFB547` | 11.0:1 on bg |
| `--on-accent` | `#1A1200` | 10.6:1 on accent |

- **Type:** JetBrains Mono for everything (OFL 1.1); VT323 only for large display text at 32px and above (OFL 1.1). Fallback `ui-monospace, Menlo, Consolas, monospace`.
- **Space and shape:** a character grid, with spacing in `ch` and line-height units; radius 0; borders as 1px lines in text-2, or box-drawing characters in decorative `aria-hidden` blocks; no shadows; a real focus outline, not just an inverted block cursor.
- **Motion:** content appears whole; a typed effect is acceptable for a one-line prompt, never for text people must read. Caret blink with `steps()`. No flicker or animated scanlines: anything that flashes stays under three flashes per second (WCAG 2.3.1). Static scanlines, if used, are very faint, off under reduced motion and never behind body text.
- **Signature:** real commands and real output as the content.
- **Goes generic when:** falling-character rain, glitch transitions and fake hacking text replace content, or green-on-black runs through long documentation.

### 9. Soft tactile (neumorphic, used carefully)

**Use for:** a few large physical-feeling controls: smart-home dials, media transport, a timer. **Avoid for:** forms, tables, whole apps, many small controls, low-vision audiences without a high-contrast mode.

| Role | Hex | Measured |
|---|---|---|
| `--bg` = `--surface` | `#E4E8EE` | |
| `--text` | `#1C2230` | **12.9:1 on bg** |
| `--text-2` | `#475063` | 6.6:1 on bg |
| `--accent` ("on" fill) | `#2C55C9` | 5.3:1 against bg |
| `--on-accent` | `#FFFFFF` | 6.5:1 on accent |
| `--border` (every control) | `#788191` | 3.2:1 against bg |
| Shadow pair | dark `#BCC3CF`, light `#FFFFFF` | dark shadow only 1.4:1 against bg |

- **Why the extra border:** the extruded shadow alone is about 1.4:1 against the ground, far below the 3:1 that WCAG 1.4.11 asks of a control's boundary, so every interactive control also gets the 1px border.
- **Type:** Rubik (OFL 1.1), softly rounded; fallback `system-ui, sans-serif`; labels 16px and up.
- **Space and shape:** controls 56px and larger; radius 16-24px; paired shadows at small offsets (for example `6px 6px 14px #BCC3CF, -6px -6px 14px #FFFFFF`); the "on" state is the accent fill with a white icon and a text label, never only an inset shadow (`COL-07`); focus is a 2px accent outline with offset.
- **Motion:** 150-200ms press in which the shadow turns inset and the fill changes; no slow pulsing.
- **Signature:** a few tactile controls on a calm field.
- **Goes generic when:** it spreads to whole screens, labels go gray on gray, or state shows only through shadow depth.

### 10. Warm organic

**Use for:** food and drink, wellness, sustainability, craft and makers, gardening, local businesses. **Avoid for:** technical tools, finance dashboards.

| Role | Hex | Measured |
|---|---|---|
| `--bg` (stone) | `#F2F0EB` | |
| `--surface` | `#E8E5DD` | |
| `--text` (green-black) | `#1E2A22` | **13.1:1 on bg**, 11.8:1 on surface |
| `--text-2` | `#52605A` | 5.8:1 on bg, 5.3:1 on surface |
| `--accent` (forest) | `#2E6A4E` | 5.6:1 on bg, passes as link text |
| `--on-accent` | `#FFFFFF` | 6.4:1 on accent |
| Field: ochre | `#E2B144` with ink `#2A2210` | 8.0:1 |

- **Type:** Fraunces for display, with its soft optical sizes (OFL 1.1), and Work Sans for text (OFL 1.1).
- **Space and shape:** relaxed spacing; 8-12px radius, or one organic image mask used consistently; no hard shadows; paper texture, if any, at very low opacity and never behind body text; photographs of the real materials lead, and accent colors may be sampled from them (then rechecked, `COL-11`).
- **Motion:** 250-400ms gentle ease-out; slow image fades; no stacked parallax layers.
- **Signature:** the subject's own materials and colors, set in flat fields.
- **Goes generic when:** it drifts to cream, terracotta and an italic serif accent word, or leaf and blob illustrations replace real pictures (taste detectors 2, 26).

### 11. Civic clarity (accessible first)

**Use for:** government and public services, healthcare, benefits, utilities, education administration, and any product for broad audiences including older and low-vision users. **Avoid for:** nothing as a baseline; campaigns can add a louder layer on top.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#FFFFFF` | |
| `--surface` | `#F0F0F0` | |
| `--text` | `#1B1B1B` | **17.2:1 on bg**, 15.1:1 on surface |
| `--text-2` | `#454545` | 9.6:1 on bg (meets the 7:1 enhanced level) |
| `--accent` (links, primary button) | `#0B5C9E` | 6.9:1 on bg |
| `--on-accent` | `#FFFFFF` | 6.9:1 on accent |
| `--focus` (outline) | `#C05600` | 4.6:1 on bg |
| `--border` (inputs) | `#565C65` | 6.7:1 on bg |

- **Type:** Public Sans (OFL 1.1); for audiences with many low-vision readers, Atkinson Hyperlegible Next (OFL 1.1). Body 18px (never under 16px), line height 1.5-1.6, links underlined.
- **Space and shape:** 8px base; targets 44px or larger (`MOB-01`); radius 0-4px; 1-2px input borders; focus as a 3px solid outline with a 2px offset; shadows only on dialogs; single-column forms (`FRM-02`).
- **Motion:** minimal, 200ms or less; nothing moves on its own; no auto-advancing carousels (`CMP-22`).
- **Signature:** plain language and an obvious next step on every screen.
- **Goes wrong when:** decoration creeps in, helper text turns pale gray, or actions become icon-only.

### 12. Flat poster

**Use for:** launches, events, festivals, campaigns, single-purpose landing pages. **Avoid for:** daily-use apps, long reading.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#FFFFFF` | |
| `--text` | `#141414` | **18.4:1 on bg** |
| `--text-2` | `#4A4A4A` | 8.9:1 on bg |
| `--accent` (primary button: ink) | `#141414` | 18.4:1 on bg |
| `--on-accent` | `#FFFFFF` | 18.4:1 on accent |
| Field: vermilion | `#FF5A1F` with ink `#141414` | 5.9:1 (white fails here) |
| Field: deep teal | `#0F3D3E` with ink `#F4EFE6` | 10.4:1 |
| Field: yellow | `#FFD23F` with ink `#141414` | 12.8:1 |

- **Type:** Big Shoulders for display, condensed (OFL 1.1), with Hanken Grotesk for text (OFL 1.1). Display headlines of two to five words sized with `clamp()` (`TYP-11`).
- **Space and shape:** full-bleed fields that meet edge to edge; very large type; radius 0 or fully round, chosen once; no shadows, no gradients; every field uses its own ink, and neighboring fields differ in lightness, not only in hue.
- **Motion:** hard cuts between fields; fast slides of 200-300ms; one bold entrance on load; cuts only under reduced motion.
- **Signature:** one field per section, committed to.
- **Goes generic when:** fields turn into gradients, the palette grows past three or four fields, or mid-tone text sits on mid-tone fields.

### 13. Technical documentation

**Use for:** developer docs, API references, knowledge bases, changelogs. **Avoid for:** marketing heroes.

| Role | Light | Dark |
|---|---|---|
| `--bg` | `#FFFFFF` | `#121417` |
| `--surface` (sidebar, callouts) | `#F5F7F9` | `#1A1D21` |
| `--text` | `#1D2127` | `#E4E7EB` |
| `--text-2` | `#575E68` | `#9EA6B0` |
| `--accent` (links) | `#0A5FC4` | `#78B4FF` |
| `--on-accent` | `#FFFFFF` | `#0A1A2E` |
| Code block ground | `#F1F3F5` | use `--surface` |

- **Measured, light:** **text 16.2:1 on bg**; text-2 6.6:1; links 6.1:1 on bg and 5.7:1 on surface; code 14.5:1 on its ground; on-accent 6.1:1. **Dark:** **text 14.9:1 on bg**; text-2 7.5:1; links 8.6:1 on bg and 7.9:1 on surface; on-accent 8.1:1.
- **Type:** Source Sans 3 for text and Source Code Pro for code (both OFL 1.1), or `system-ui` with `ui-monospace`, which loads nothing.
- **Space and shape:** 4/8 scale; article measure 65-75ch; sidebar 240-280px; code blocks with 6px radius and a copy button; 1px borders on callouts; no shadows; anchor links on headings.
- **Motion:** none beyond about 150ms hover and disclosure; smooth anchor scrolling only when reduced motion is not requested.
- **Signature:** fast search, accurate examples, copyable code.
- **Goes generic when:** the docs home becomes a gradient hero, callouts carry emoji, or prose is set in monospace.

### 14. Gallery quiet

**Use for:** hotels, restaurants, fashion, architecture and art portfolios, high-end products. **Avoid for:** dense tools; slow connections unless images are optimized.

| Role | Hex | Measured |
|---|---|---|
| `--bg` | `#F7F6F4` | |
| `--surface` | `#EEECE8` | |
| `--text` | `#161514` | **16.9:1 on bg**, 15.5:1 on surface |
| `--text-2` | `#625E58` | 6.0:1 on bg, 5.5:1 on surface |
| `--accent` (deep navy: links, booking button) | `#1F2B45` | 13.1:1 on bg |
| `--on-accent` | `#FFFFFF` | 14.1:1 on accent |

- **Type:** EB Garamond for display and short text (OFL 1.1), with Libre Franklin for navigation, captions and forms (OFL 1.1).
- **Space and shape:** very generous margins; large photographs with consistent crops and one grade; radius 0; no shadows; thin rules rarely; small navigation.
- **Motion:** slow crossfades of 400-700ms; image-led reveals; no scroll hijacking (`MOT-16`); instant swaps under reduced motion.
- **Signature:** one strong photograph per screen next to the facts guests need: dates, rates and how to book.
- **Goes generic when:** stock imagery, tiny pale text or hidden prices take over.

## Adapting and combining

- **Brand first.** Map the brand's colors onto the roles above, then recheck every pair; a brand accent that fails as a fill with white text gets a dark `--on-accent` instead (`COL-11`).
- **One direction, two volumes.** A product can run a louder version of its direction on marketing pages and a quieter one in the app: same palette and type, different scale, density and motion.
- **Do not blend directions** inside one screen (`STY-01`). If a request mixes two ("premium but playful"), pick the base direction and borrow exactly one trait from the other, named in the report.
- **Record the choice.** Put the chosen tokens in the project's token file with each approved text and background pair and its ratio (`BRD-03`), so later work starts from decisions rather than from defaults.
