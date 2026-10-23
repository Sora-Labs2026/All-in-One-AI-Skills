# UI rules: Typography

Typefaces, type scale, weight, size, line length, letter spacing and text color. Rule IDs use the `TYP-` prefix; cite them in change reports.

## TYP-01. Use one or two typefaces and build hierarchy inside them

**Why:** Several unrelated typefaces look improvised; one family varied by size, weight and color stays coherent.

- **Do:** Use the platform system stack (system-ui, -apple-system, Roboto) or one neutral, well-hinted UI sans for body, labels and buttons.
- **Do:** Reserve any expressive display face for large headlines, if at all.
- **Do:** Load only the weights in use, subset fonts, use font-display: swap and keep a system fallback stack.
- **Avoid:** Mixing script, serif and sans faces within one card or heading.
- **Avoid:** Decorative faces for paragraphs, form labels or button text.

## TYP-02. Keep a short type scale

**Why:** Many slightly different font sizes read as noise; a few deliberate steps create clear levels.

- **Do:** Define about 5-6 sizes as tokens or utility classes, each with a fixed line height and weight, for example Display 32, Title 24, Heading 18, Body 16, Small 13.
- **Do:** Start from platform ramps where they apply (iOS body 17pt, Android body 16sp, web body 16px) and step headings with a ratio of about 1.2-1.25.
- **Avoid:** Ten or more sizes on one page, or 1px nudges used to fix layout problems.
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
- **Do:** Use a line height of about 1.4-1.6 for body text and tighter (1.1-1.3) for large headings.
- **Avoid:** Paragraphs that stretch across the full width of wide screens.

## TYP-06. Leave body tracking alone and use capitals sparingly

**Why:** Extra letter spacing breaks up word shapes, and long runs of capitals are slow to read.

- **Do:** Keep letter-spacing at the font default for body text.
- **Do:** Use uppercase only for short eyebrows, tags and overlines, set smaller with about +0.05-0.1em tracking, applied with text-transform so screen readers do not spell words out.
- **Do:** Use slight negative tracking only on very large display headings, if needed.
- **Avoid:** Widened tracking on paragraphs, or headlines and paragraphs in all caps.

## TYP-07. Make headings darker than body text

**Why:** A near-black, heavier heading above a slightly lighter body creates an instant reading order.

- **Do:** Set titles in the strongest text color token and a heavier weight.
- **Do:** Set supporting text in a medium gray that still reaches at least 4.5:1 against its background.
- **Avoid:** Titles in the same light gray as body copy, or low-contrast gray for errors and other critical messages.

## TYP-08. Style same-role text identically

**Why:** When all prices, dates or labels look the same, users learn the pattern once.

- **Do:** Define named text styles (eyebrow, H1, H2, body, caption, price) and apply them everywhere.
- **Do:** Give every value with the same role the same size, weight and color.
- **Avoid:** Coloring each highlighted word or price differently for variety.
