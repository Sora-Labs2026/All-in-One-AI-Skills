# UI Distiller: Design rules

Read this reference when developing a visual language or deciding whether to keep visual elements. These are heuristics, not a universally imposed theme.

## Content: ruthless but responsible

- Replace generic slogans with direct, specific meaning. Prefer "12 invoices need review" to "Your intelligent workspace is ready to transform productivity".
- Avoid echoing the same noun in page title, card title, button label, and explanatory paragraph unless needed to disambiguate.
- Prefer a number with a clear label, units, scope, and timeframe to a big unlabeled number. "Collected today: $1,260" is better than "Revenue 1,260" if the former is the actual measure.
- Remove empty introductions, congratulatory banners, motivational microcopy, "learn more" buttons without distinct purpose, and repetitive decorative subtitles.
- Keep explanatory text when the task is unusual, high-stakes, irreversible, or easy to misunderstand. Compress jargon, not caveats.
- Preserve screen reader context, form labels, live regions, error and success messages, accessible names, and details needed for keyboard navigation. Some visually redundant information is semantically essential.

## Typography and scanning

- Use a small, disciplined hierarchy: page context; key figure/headline; section heading; body; metadata. Don't indiscriminately use huge headings or tiny gray captions.
- Build priority via weight, contrast, size, alignment, and space. Avoid over-highlighting with several simultaneous accents.
- Keep body copy readable, line lengths controlled, and long strings wrapped or truncated with a path to full content.
- Align labels, data, and actions so comparisons are obvious. Use tabular numerals when available for financial or operational columns.
- Use precise labels, e.g. "Outstanding balance" over "Insights". Avoid all-uppercase meta labels unless they improve scanning within a known design language.

## Color and surfaces

- Begin with project brand colors and semantic states. Keep a clear neutral foundation. Avoid introducing unrelated color just to make a screenshot "pop".
- Use accent color primarily for the main action, active navigation, and meaningful selected states. Error, warning, and success colors should communicate true status.
- A background, border, shadow, or card is justified when it conveys grouping, clickability, emphasis, or state. Otherwise remove it.
- Prefer proximity and consistent alignment to nested cards and separator lines. Beware borders around every child in a bordered parent.
- Avoid gradient/glass/glow as a default; allow it deliberately when integral to a brand or interactive meaning.

## Composition and density

- The first viewport should contain real task value rather than just a banner. A productive dashboard can start with status and a work queue instead of a hero and four cards.
- Anchor the dominant content. Provide one clear primary action. Place secondary actions where they are contextually relevant.
- Prefer fewer high-value sections over an impressive-looking grid of redundant features.
- Avoid unbounded maximum widths for long copy, but don't arbitrarily narrow data tables or workflows.
- Whitespace is structure. Remove excessive empty vertical gaps, and retain enough separation to avoid crowding.
- Expand advanced detail through honest disclosure or secondary navigation, not through hover-only access or hidden gestures.

## Interaction quality

- Interactive elements must look interactive. Static text must not look like a button or link.
- Ensure persistent text labels for inputs, visible focus, helpful errors, disabled/loading indications, and feedback after action.
- Follow WCAG 2.2 AA where applicable, including text contrast around 4.5:1 for normal text and 3:1 for large text; make pointer targets at least 24 x 24 CSS px or provide a qualifying spacing/exception. Prefer larger targets for touch comfort.
- Validate keyboard order, accessible names, semantic landmarks, dark-mode contrast (if supported), 200% text zoom, and small-screen reflow.
- Respect reduced-motion preferences. Motion must convey state or orientation rather than decorate routine interactions.

## Anti-pattern detection, with judgment

Visual and verbal defaults (color, type, surfaces, imagery, copy, motion) and their replacements are covered in `taste.md`.

| Symptom | More intentional alternative |
| --- | --- |
| Giant welcome banner in a working app | Immediate task, status, and a short contextual title |
| Four to eight equal-size vanity-stat cards | One meaningful result/alert plus concise supporting figures |
| Cards inside cards with every item outlined | Grid/list hierarchy from spacing and typography |
| Long generic marketing headline | Specific value statement with proof and primary CTA |
| Icons on every row and label | Icons only when they speed recognition or convey status |
| Dividers between every element | Section spacing and alignment; dividers at true boundaries |
| Accents, badges, and bold text everywhere | One dominant signal and restrained semantic emphasis |
| Empty-state illustration consumes whole screen | Clear empty-state explanation and next useful action |
| Wide "hero" padding hiding content | Comfortable but compact task-first layout |
| Repeated help text on obvious actions | Clear control labels, help only for non-obvious outcomes |
| Perfectly symmetrical uniform cards | Content-driven composition respecting relative importance |
| Over-minimal hidden controls | Predictable, discoverable actions and progressive disclosure |

## Never optimize for screenshots at the expense of use

Do not delete important data, conceal settings, substitute fake content, weaken text contrast, remove error or trust information, or convert dynamic features into nonfunctional illustrations. Good visual editing means retaining sufficient information for accurate choices.
