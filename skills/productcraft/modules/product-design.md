# Product design and visual editing

Route to the full [UI Distiller guide](ui-distiller/GUIDE.md) for comprehensive screen restyling. This module makes the matching entries in `../references/pattern-library.md` selectively actionable.

## Audit the screen, then implement

- Identify its first question, key evidence, urgent exception and single next action. On dashboards prefer a current queue or essential KPI over a greeting or oversized hero.
- Annotate components PROMOTE / KEEP / COMPRESS / DEMOTE / REMOVE and make the new layout before fiddling with colors. Avoid useless dividers, repeated subtitles, inflated cards, identical-priority metrics and filler text.
- Define a small semantic token system: surface levels, emphasis colors, states, typography scale, 4/8-based spacing, radii, elevations and motion lengths, reusing project tokens whenever possible (patterns 2, 12, 13, 21, 51, 52, 55, 59).
- Visually hierarchy is relative. One unmistakable primary action usually beats a rainbow of strong CTAs. Keep contrast, keyboard focus and color-independent state labels.
- Use micro spacing for relationships, macro spacing between real sections, active whitespace for focus. A large blank region that buries the task is not premium design (pattern 16).
- Radius and density should correspond to the domain. A clinical admin table and consumer marketing page need different levels of density (patterns 3, 53).
- For colors, gradients, glass, 60/30/10 and golden ratio: treat as conditional composition ideas, never enforced formulas. Only apply gradients/transparency when specifically useful and legible (patterns 13, 14, 18, 20).
- Use responsive container-first grids, and rearrange rather than hide tasks when there is insufficient width (patterns 17, 54).
- Keep icon family coherent, icons optically proportional to text and controls semantically labelled (pattern 59).

## Concrete review questions

1. What primary information is visible before scrolling on a common mobile width and desktop viewport?
2. Are important exceptions/alerts visible without becoming banner noise?
3. Can the next task be accomplished without guessing where to click?
4. Is any card, label, separator, gradient, chart, tooltip or microcopy redundant?
5. Did simplification remove helpful task data, financial details, errors, accessibility context or legally required disclosures?

## Test

Desktop and 320/360/390/768 widths as available; zoom and long text. Inspect empty/loading/error states. Use actual screenshots or browser tests where access exists; do not invent a visual pass. Preserve existing branding unless the task requests redesign.
