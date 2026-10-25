# UI Distiller: Taste

Read this when a screen works but looks generated, and once more before shipping any new screen or page. It lists the defaults that make an interface look like every other quickly generated one, how to spot each, what to put in its place, and a short self-critique pass.

It extends, and does not repeat, the anti-pattern table in [design-rules.md](design-rules.md) (banners, vanity cards, nested cards, icons on every row) and the checklist in [quality-gate.md](quality-gate.md). Rule IDs such as `COL-02` point to `../../../references/ui-rules/`; cite them in the change report. For a whole visual direction, use [style-catalog.md](style-catalog.md).

## Stance

- **A default is not wrong; it is undecided.** Every item below is *suspect*, not banned. Keep it when the brand, the request or the content gives a reason you can state in one sentence, and write that sentence in the report.
- **The brief wins.** If the user asks for a gradient, glass or a neon accent, build a good one: contrast-checked, consistent, with fallbacks. These detectors apply to the axes the brief leaves open.
- **Deleting decoration is only the first step.** A screen that loses its ornaments and gains nothing looks like a wireframe. Give the freed space to substance: the real content at the right size, the real product, one committed visual move. Do not trade one decoration for another.
- **Function first.** No detector justifies lower contrast, hidden labels, removed warnings or missing states. The priorities in `../GUIDE.md` still hold.

## Before styling: collect what belongs to this product

Write down three to six facts that no competitor shares: the product's real data and units, the words its users use, the object or output it produces, the constraint it lives with, the place or moment it serves. These are the raw material for the headline, the imagery and the one distinctive move. If the brief gives none, read the codebase, fixtures and copy; ask only if nothing specific exists.

**Swap test.** Replace the product name with a direct competitor's. If the headline, palette, imagery and section order still fit unchanged, nothing has been decided yet. Run it on the first screen and again on the last section, because pages often open with something specific and then fall back on stock blocks.

## Detectors

Each entry: what to look for, the principle it breaks, what to do instead, and when it is fine.

### Color

**1. Default violet, indigo or blue-to-pink gradient** on the hero, buttons or glows.
- Look for: hues around 240-300° at high saturation with no brand reason; framework default indigo and violet values (for example `#6366F1`, `#4F46E5`, `#8B5CF6`) left untouched; `linear-gradient` on primary buttons.
- Principle: color should carry identity or meaning; an unbranded default carries neither, and a gradient makes label contrast change along the button (`COL-11`, `PRN-04`).
- Instead: one flat accent taken from the brand or the product's own material; a solid primary button. With no brand, choose a direction in `style-catalog.md`.
- Fine when: the brand owns the hue. Flatten it where it carries text, retune it for dark mode (`DRK-05`) and check the lightest stop.

**2. Warm cream ground with a terracotta or clay accent and a high-contrast serif.** The usual "make it warmer and more editorial" fix, now a recognizable generated look in its own right.
- Look for: a visibly yellow off-white ground (hue about 30-60°, lightness above 90%), a rust or clay accent (hue about 10-30°), a serif display face, often together.
- Principle: warmth produced by formula is as anonymous as the cold default it replaced.
- Instead: warmth from a low-chroma stone or putty ground, a deep green, brown or oxblood ink, real photography, or one saturated warm color applied flatly across a whole section (see *Warm organic* and *Editorial reading* in the catalog).

**3. Near-black page, one neon accent, glows.**
- Look for: background below about 8% lightness, a single acid green, electric cyan or magenta, blurred `box-shadow` halos around buttons and cards.
- Principle: on dark surfaces depth comes from lighter surface steps (`DRK-03`); glows reduce legibility and read as decoration (`STY-06`).
- Instead: a tinted near-black with two or three surface steps, an accent retuned for dark (`DRK-05`), separation by hairline and lightness (`DRK-09`).

**4. The accent everywhere.**
- Look for: the accent on headings, icons, bullets, borders, badges and decorative shapes as well as actions. Count its roles on one screen; more than about three is suspect.
- Principle: emphasis is relative. An accent seen in ten places stops meaning "act here" (`COL-02`, `COL-04`).
- Instead: accent on the primary action, the current location, focus and links. Headings in ink, icons in a neutral.

**5. A different hue per card, category or chart series by default.**
- Look for: each feature card in its own pastel; more than four hues on a screen whose items are not categories.
- Principle: a color difference claims a category difference; when none exists the color is noise (`COL-14`, `CMP-18`).
- Instead: neutral cards; one hue and its tints per chart; color only on the series or category that answers the question.

**6. Gradient-filled headline text.**
- Look for: `background-clip: text` with a transparent fill.
- Principle: emphasis belongs to words, size and position. Contrast varies glyph by glyph, and when backgrounds are dropped (printing without background graphics, forced-colors mode) the text can disappear.
- Instead: solid ink. If the brand requires it, set a solid `color` first, check the lightest stop, and reset to a solid color in print and under `@media (forced-colors: active)`.

**7. Everything in soft gray** to look refined.
- Look for: body text under 4.5:1, or the secondary text color used for primary reading.
- Principle: a page set in pale gray reads unfinished and excludes low-vision readers (`COL-01`, `TYP-07`).
- Instead: running text in the full text color; gray only for metadata that still passes 4.5:1.

### Type

**8. One untouched default face with no hierarchy decision.**
- Look for: headings barely larger or heavier than body text; on a marketing hero, a headline under about twice the body size.
- Principle: hierarchy needs real contrast in size and weight (`LAY-05`, `TYP-02`).
- Instead: decide the scale. On a page, the display size is several times the body (three to five times is common); in an app, titles are about 1.5-2 times body with a heavier weight. A system or neutral UI face is right for most app screens; for a brand-led page choose the face deliberately.

**9. Many near-equal sizes.**
- Look for: more than about eight distinct computed font sizes on a page (ten in a dense app), or two sizes within 2px doing different jobs.
- Principle: sizes that are almost the same look like mistakes, not levels (`TYP-02`).
- Instead: merge into a five- or six-step scale; sizes that are hard to tell apart become one size.

**10. The accent word:** one word of a headline in italic serif, a second color, a highlight or a gradient.
- Principle: it splits one line into two typographic voices and points at a word instead of saying something (`TYP-01`).
- Instead: one face and one color per headline; put the important word first or last.

**11. A label above every heading:** tiny, tracked, uppercase ("FEATURES", "WHY US", "OUR PROCESS").
- Principle: a label that repeats the heading adds nothing, and small capitals are slow to read (`TYP-06`, `COP-06`).
- Instead: put the information in the heading or its first sentence. Keep a small label only where it adds facts the heading lacks: a category, a step, a status, an error code (`SCR-18`).

**12. Monospace as costume** for navigation, captions, labels or marketing figures.
- Principle: fixed width helps code, identifiers and alignment; elsewhere it slows reading and becomes a third typographic voice (`TYP-01`).
- Instead: the text face with `font-variant-numeric: tabular-nums` for figures (`TYP-09`); monospace for code, keys, IDs, hashes and log lines, or where it is the whole direction (see *Retro terminal*).

**13. A sentence posing as a headline:** twelve or more words wrapping to three or four lines.
- Look for: more than two lines at 390px or 1440px width.
- Principle: a headline is read in one glance; detail belongs in the supporting line (`SCR-11`).
- Instead: about four to eight words saying what it is or does, one supporting sentence directly below, `text-wrap: balance`. Edit the wording rather than the font size.

### Composition

**14. Everything centered.**
- Look for: more than about half of the text blocks centered; centered paragraphs longer than three lines; centered heading, paragraph and two buttons repeated in every section.
- Principle: a shared left edge is where the eye returns; a centered stack has no edge to scan from (`LAY-04`).
- Instead: left-align by default and center one deliberate moment: a short hero line, an empty state, a one-line dialog.

**15. The equal-weight card grid:** three or more identical cards, each an icon, a title and two lines of copy.
- Principle: identical treatment says "equally important" (`LAY-05`, `CMP-09`), which is rarely true.
- Instead: rank the items. Give one the lead (larger, with a real image or product fragment) and set the rest as a compact list; or use rows of claim and proof; or a table when items are compared. Uniform tiles stay right for genuinely comparable items such as products and search results (`CMP-21`).

**16. The stock section order** (hero, logo strip, three features, testimonial, pricing, closing call to action) whatever the content.
- Principle: each section should earn its place (`LAY-06`); `SCR-22` is a sensible default order, not a template.
- Instead: outline the page first as the statements a visitor must come to believe, each paired with the evidence for it. A section with no statement to carry is cut; the rest follow the order of the visitor's questions.

**17. Every section in the same layout.**
- Look for: tag each section with its arrangement (split, list, grid, table, full-bleed). Matching tags on adjacent sections, or one arrangement used for most of the page, mean the sections were stamped from one mold.
- Instead: vary neighbors while keeping one grid, one pair of side margins and one spacing scale.

**18. The hero formula:** centered headline, subtitle, two equal buttons, a mock screenshot below, a gradient behind.
- Instead: lead with the most characteristic thing in the product's world (the real interface doing its job, the product photographed, a working calculator), one primary action and a text link (`BTN-01`, `SCR-11`).

**19. Leftover space:** tall empty bands from stacked padding, or text in one half of a section with nothing in the other.
- Principle: space groups and separates (`LAY-02`, `LAY-03`); space that nothing balances reads as missing content.
- Instead: put the section's image, list or figure in the empty half, enlarge the main element, or reduce the gap. Space between sections should exceed every gap within a section, so groups read as groups.

### Surfaces and shape

**20. One radius on everything:** the same 12-16px on buttons, inputs, cards, tooltips, avatars and images.
- Principle: radius should follow element size and the brand's tier (`CMP-05`), and nest concentrically (`CMP-06`).
- Instead: a small scale chosen once (for example 4 / 8 / 12, or 0 / 2 / 4 for a sharp brand), pills only for chips and toggles (`CMP-27`).

**21. The same soft shadow under every card.**
- Look for: more than a few resting elements with a `box-shadow` in one viewport.
- Principle: a shadow means "above the page"; if everything floats, nothing does (`CMP-07`).
- Instead: a tone step or a 1px border for resting surfaces; shadows for menus, popovers, dialogs and drag previews.

**22. Glass over a busy background:** blurred translucent cards over photos, video, text or moving gradients.
- Principle: the text's contrast depends on whatever passes behind it (`COL-12`), and stacked blurs cost rendering time.
- Instead: an opaque surface, or glass only on floating chrome over calm imagery with a contrast floor and fallback (`STY-05`).

**23. Stacked separators:** border, shadow and tint on the same element; a hairline between every row and section.
- Instead: one separation method per level (`LAY-07`); dividers only at real boundaries. Data tables may keep row lines.

### Icons, imagery and illustration

**24. Emoji as icons** in navigation, buttons, feature headings, bullets and empty states.
- Principle: emoji render differently on every platform, ignore color tokens and stroke weight, are read aloud by their names ("rocket", "sparkles"), and read as filler (`ICO-01`).
- Instead: one vector icon set, or no icon. Emoji stay where they are user content: reactions, messages, names.

**25. An icon in a tinted rounded square** on top of every card.
- Instead: no icon unless it speeds recognition; a real image or product fragment for features.

**26. Stock-looking illustration:** generic 3D characters, isometric people, abstract blobs and waves, generated scenes that do not show this product.
- Principle: imagery should show what the headline promises (`ICO-05`).
- Instead, in this order: the project's own photographs or product; the real interface built in code with believable data; drawings of the product's own objects in its palette; type and color alone. Stock or generated pictures must never pass as photographs of the actual product, premises or staff.

**27. A fake dashboard hero** of gray bars, a donut and placeholder numbers.
- Instead: a real interface fragment with data that adds up, trimmed to the single result that supports the headline.

**28. Decorative status:** a pulsing dot beside "Live" or "Online", or a ticking counter, with no real data behind it.
- Principle: status colors and motion assert a state (`COL-06`, `FBK-17`); asserting a false one is dishonest.
- Instead: remove it, or wire it to the real state.

### Copy

**29. Hero copy anyone could sign:** "Unlock the power of", "supercharge", "seamless", "effortless", "revolutionize", "X, reimagined", three one-word sentences, "not just X, it's Y".
- Principle: specificity is credibility; a sentence a competitor could publish unchanged says nothing (design-rules.md, *Content*).
- Instead: what it is, for whom, and one concrete outcome, number or fact from the brief.

**30. Labels without outcomes:** "Get started", "Learn more", "Explore", "Submit" (`COP-01`).

**31. Invented proof:** logo strips, testimonials, star rows, "trusted by 10,000+ teams" without a source. Remove; see [../../ethical-persuasion.md](../../ethical-persuasion.md) and `COP-13`. Let the product itself be the proof.

**32. Decorative meta-text:** strings of keywords separated by dots, an arrow after every link label, an em dash in most sentences, founding years and invented version numbers used as texture.
- Instead: plain sentences; an arrow only where it means "leaves this page"; punctuation used as punctuation.

**33. Placeholder data:** sample names and companies, `example.com`, round vanity totals, totals that do not equal the sum of their rows (`COP-05`).

### Motion

**34. Decorative motion by default:** the same fade-and-rise on every section, a hover lift on every card, bounce easing on everyday controls, loops that mean nothing, content invisible until a reveal fires, a preloader on a page that has already loaded, typewriter or scrambled headlines.
- Principle: motion should explain a change or answer an action (`MOT-02`, `MOT-17`); repeated decoration costs attention on every visit.
- Instead: one orchestrated moment at most (a load sequence or one reveal), feedback motion on interaction, content visible without scripts (`MOT-06`), honest loading (`FBK-19`), a reduced-motion path (`MOT-04`).

### App screens

Dashboards and admin screens have their own defaults; most are covered by pattern 55 in `../../../references/pattern-library.md` and by `SCR-01` and `CMP-17` to `CMP-19`. Check quickly for: a personal greeting where the page title belongs; a row of identical metric tiles decorated with icons, colored percentage badges and mini-charts whether or not the trend matters; curved, filled area charts; loud status chips; a different icon color per category; header furniture that is the same on every screen; a fixed number of columns whatever the item count. Replace with: a title naming the object or task, one leading figure, changes stated with their comparison period, plain lines unless the filled area means something, quiet status tints with readable same-hue text, neutral icons, and actions only where they are real.

## Measure before judging

Counts are evidence; impressions are not. Paste this read-only snippet into the browser console, or pass it to `page.evaluate` in a headless browser, at 390px and 1440px. It changes nothing on the page and only reports. Thresholds are advisory, like any scanner: a high count is a question to answer, not a verdict.

```js
(() => {
  const vis = [...document.querySelectorAll('body *')].filter((el) => {
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  });
  const st = new Map(vis.map((el) => [el, getComputedStyle(el)]));
  const own = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  const text = vis.filter(own);
  const tally = (items, key) => {
    const m = new Map();
    for (const it of items) { const k = key(it); if (k) m.set(k, (m.get(k) || 0) + 1); }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  };
  const vivid = (c) => {
    const [r, g, b, a = 1] = (c.match(/[\d.]+/g) || []).map(Number);
    if (r === undefined || a < 0.3) return null;
    const hi = Math.max(r, g, b), lo = Math.min(r, g, b);
    return hi > 40 && (hi - lo) / hi > 0.45 ? c : null;
  };
  const blocks = text.filter((el) => /^(P|H[1-6]|LI|BLOCKQUOTE|FIGCAPTION)$/.test(el.tagName));
  return {
    fontSizes: tally(text, (el) => st.get(el).fontSize),
    centeredBlocks: `${blocks.filter((el) => st.get(el).textAlign === 'center').length} of ${blocks.length}`,
    radii: tally(vis, (el) => (st.get(el).borderTopLeftRadius === '0px' ? null : st.get(el).borderTopLeftRadius)),
    shadowedElements: vis.filter((el) => st.get(el).boxShadow !== 'none').length,
    gradientFills: vis.filter((el) => st.get(el).backgroundImage.includes('gradient')).length,
    gradientText: vis.filter((el) => [st.get(el).backgroundClip, st.get(el).webkitBackgroundClip].includes('text')).length,
    blurredSurfaces: vis.filter((el) => (st.get(el).backdropFilter || st.get(el).webkitBackdropFilter || 'none') !== 'none').length,
    emoji: text.filter((el) => /\p{Emoji_Presentation}|\p{Extended_Pictographic}️/u.test(el.textContent)).map((el) => el.textContent.trim().slice(0, 40)),
    vividTextColors: tally(text.map((el) => st.get(el).color), vivid).slice(0, 6),
    vividFills: tally(vis.map((el) => st.get(el).backgroundColor), vivid).slice(0, 6),
  };
})();
```

Read the result against the detectors: more than about eight `fontSizes` (detector 9); `centeredBlocks` above half (14); more than three `radii` besides a pill value (20); several `shadowedElements` at rest (21); any `gradientText` (6); `blurredSurfaces` over busy content (22); any `emoji` in interface text (24); more than two or three entries in `vividTextColors` and `vividFills` together (4, 5). Run it on the before and after versions and put both sets of numbers in the report.

## Self-critique pass before shipping

Five minutes, on screenshots at 390px and 1440px. Judge rendered pixels: the source tells you what you meant, not what appeared.

1. **First glance.** Show yourself the screenshot for about a second, then write down what you remember. If it is a row of equal things, or nothing in particular, no element leads.
2. **Swap test** on the first screen and on the final section.
3. **Blur.** Blur the screenshot or step back from it: the order of importance should survive as a few shapes of clearly unequal size (`LAY-05`).
4. **Count.** Accent roles (about three at most), type sizes, radii, resting shadows, repeated section layouts. Use the snippet's numbers.
5. **Read aloud** every headline, button and section title. Mark any line a competitor could print and any word from detector 29. Rewrite them with facts from the product.
6. **Ornament inventory.** For each gradient, glow, blur, badge, icon, divider and animation, say what it tells the user. If nothing, remove it, then close the gap it leaves with content or scale.
7. **One committed move.** Name the single distinctive decision: a decisive type scale, a color field, the real product shown large, a live interactive element. If there is none, make one; if several compete, keep the strongest.
8. **Integrity.** Re-run [quality-gate.md](quality-gate.md): contrast, focus, reduced motion, real data, every needed label and state still present.

**Done when:** the swap test fails for the competitor (the screen only fits this product); every remaining suspect from the list above has a one-sentence reason in the report; the counts did not get worse; and the quality gate still passes.

**Report line**, added to the UI Distiller completion contract: `Taste: removed […]; kept […] because […]; distinctive move: […]; counts before → after: sizes 11 → 6, radii 5 → 3, resting shadows 14 → 2.` Report only what you measured.
