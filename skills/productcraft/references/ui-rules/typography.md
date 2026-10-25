# UI rules: Typography

Typefaces, type scale, weight, size, line length, letter spacing and text color. Rule IDs use the `TYP-` prefix; cite them in change reports.

## TYP-01. Use one or two typefaces and build hierarchy inside them

**Why:** Several unrelated typefaces look improvised; one family varied by size, weight and color stays coherent.

- **Do:** Use the platform system stack (system-ui, -apple-system, Roboto) or one neutral, well-hinted UI sans for body, labels and buttons.
- **Do:** Reserve any expressive display face for large headlines, if at all.
- **Do:** Load only the weights in use, subset fonts, use font-display: swap and keep a system fallback stack.
- **Do:** Check the font license before bundling, keep the license file with self-hosted copies, and self-host for privacy-sensitive products, since third-party font servers receive every visitor's IP address.
- **Avoid:** Mixing script, serif and sans faces within one card or heading, including a single italic-serif accent word in a sans headline, unless the brand system defines that treatment.
- **Avoid:** Monospace as a decorative "technical" voice for navigation, labels or marketing figures; reserve it for code, identifiers and keyboard keys, and use tabular-nums when figures must align.
- **Avoid:** Decorative faces for paragraphs, form labels or button text.

## TYP-02. Keep a short type scale

**Why:** Many slightly different font sizes read as noise; a few deliberate steps create clear levels.

- **Do:** Define about 5-6 sizes as tokens or utility classes, each with a fixed line height and weight, for example Display 32, Title 24, Heading 18, Body 16, Secondary 14, and Caption 12-13 only for captions, field labels and metadata.
- **Do:** Start from platform ramps where they apply (iOS body 17pt, Android body 16sp, web body 16px) and step headings with a ratio of about 1.2-1.25.
- **Do:** On iOS, take sizes from the Dynamic Type text styles (for example Large Title 34, Title 1 28, Body 17, Subheadline 15, Footnote 13, Caption 12pt) and apply them with .font(.body) or preferredFont(forTextStyle:), so they follow the user's text-size setting.
- **Do:** Audit computed sizes on the rendered page at phone and desktop widths: more than about 8 distinct sizes (about 10 in a dense app) signals drift, so merge strays into the nearest step.
- **Avoid:** Sizes outside the scale, two sizes within 2px doing different jobs, or 1px nudges used to fix layout problems.
- **Note:** Data-dense apps may need one or two extra steps, but every size still comes from the scale.

## TYP-03. Match weight to size and avoid thin weights

**Why:** Thin and light weights look elegant but are hard to read at small sizes and on poor screens.

- **Do:** Use Regular (400) as the minimum for body text and labels.
- **Do:** Use Semibold or Bold (600-700) for headings and button labels.
- **Avoid:** Weights 100-300 for body text or small labels, especially combined with light gray.
- **Avoid:** Long passages of small text set in bold.

## TYP-04. Keep text sizes readable on mobile

**Why:** Tiny text slows scanning and excludes people with low vision.

- **Do:** Keep body text at the platform default or larger (iOS 17pt, Android 16sp, web 16px).
- **Do:** Treat about 14px as the floor for list items and secondary text, and 12px as the floor for small field labels.
- **Do:** Use 16px for web form inputs so mobile browsers do not zoom on focus.
- **Avoid:** 8-10px labels or list text, especially in pale gray.

## TYP-05. Limit line length and set comfortable line height

**Why:** Very long lines make it hard to find the next line; tight leading makes paragraphs dense.

- **Do:** Cap body text at about 45-75 characters per line (for example max-width: 65ch).
- **Do:** Use a line height of about 1.4-1.6 for paragraphs, about 1.2-1.35 for one- or two-line labels, list titles and card titles, and 1.1-1.3 for large headings.
- **Do:** Let layouts survive the WCAG 2.2 SC 1.4.12 text-spacing overrides (line height 1.5, paragraph spacing 2em, letter spacing 0.12em, word spacing 0.16em) without clipping or overlap.
- **Avoid:** Paragraphs that stretch across the full width of wide screens, or fixed heights on text containers.

## TYP-06. Leave body tracking alone and use capitals sparingly

**Why:** Extra letter spacing breaks up word shapes, and long runs of capitals are slow to read.

- **Do:** Keep letter-spacing at the font default for body text.
- **Do:** Use uppercase only for short eyebrows, tags and overlines, set smaller with about +0.05-0.1em tracking, applied with text-transform so screen readers do not spell words out.
- **Do:** Use slight negative tracking only on very large display headings, if needed.
- **Do:** Add an eyebrow only when it states a fact the heading lacks (a category, step or status); keep it at 12px or larger and 4.5:1, de-emphasized by size, case and tracking rather than a lighter gray.
- **Avoid:** Widened tracking on paragraphs, headlines and paragraphs in all caps, or an eyebrow above every section that repeats its heading.

## TYP-07. Make headings darker than body text

**Why:** A near-black, heavier heading above a slightly lighter body creates an instant reading order.

- **Do:** Set titles in the strongest text color token and a heavier weight.
- **Do:** Set supporting text in a medium gray that still reaches at least 4.5:1 on every surface it appears on: the lightest passing gray is about #767676 on white, #737373 on #FAFAFA and #6E6E6E on #F2F2F2.
- **Avoid:** Titles in the same light gray as body copy, or low-contrast gray for errors and other critical messages.
- **Avoid:** Relative specs such as "50% lighter", or a secondary gray checked only on white (#6B7280 is 4.8:1 on white but 4.4:1 on #F3F4F6; iOS secondaryLabel is about 3.4:1 on white).

## TYP-08. Style same-role text identically

**Why:** When all prices, dates or labels look the same, users learn the pattern once.

- **Do:** Define named text styles (eyebrow, H1, H2, body, caption, price) and apply them everywhere.
- **Do:** Give every value with the same role the same size, weight and color.
- **Avoid:** Coloring each highlighted word or price differently for variety.

## TYP-09. Set numbers for comparison

**Why:** In finance and dashboard views the figures are the content, and they must align and compare at a glance.

- **Do:** Use font-variant-numeric: tabular-nums and right-align amounts in lists and tables.
- **Do:** Keep one decimal precision per column, and set currency symbols and units slightly smaller than the number.
- **Do:** Pair a large key figure with its unit and a plain qualifier ("120 bpm, normal"), plus a gauge or range when thresholds matter.
- **Avoid:** Lone numbers with no unit or meaning, or mixed precision within one column.

## TYP-10. Keep text as real, selectable text

**Why:** Text drawn into images, canvas or CSS content is hard to select, translate, search or read aloud.

- **Do:** Put headings, messages and receipts in HTML, and use CSS only to style them.
- **Do:** Layer decorative canvas or 3D effects behind or above real text with pointer-events: none.
- **Avoid:** User-facing messages in ::before or ::after content, or receipts and confirmations rendered as flat images.

## TYP-11. Use display and novelty type only as accents

**Why:** Oversized, condensed, dot-matrix or split-word type adds energy but loses legibility quickly.

- **Do:** Limit display type to short headlines (2-5 words) sized with clamp(), for example clamp(3rem, 10vw, 10rem), with line-height around 0.9-1.
- **Do:** Use novelty numerals only for one or two large figures (32px or more), keep their own dots or strokes at 3:1 or better, and keep a plain label beside them at 4.5:1.
- **Do:** When a headline is split or partly muted for effect, keep the full text as the accessible name and keep the muted part at 3:1 or better.
- **Avoid:** Display or dot-matrix faces for body text, small labels, tables or placeholders.
- **Avoid:** Display type over busy photography without a scrim.
