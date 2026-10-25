# UI rules: Icons and imagery

Icon consistency, metaphors, accessible names and image use. Rule IDs use the `ICO-` prefix; cite them in change reports.

## ICO-01. Use one icon family and one style

**Why:** Mixed icon styles look assembled from scraps and can make one icon seem selected.

- **Do:** Use a single icon library with one style (outline or filled), one stroke width for the whole product (for example 1.5 or 2) and one size grid (for example 20 or 24px), optically centered.
- **Do:** Size icons from the adjacent text, about 16px beside 14px labels and 20px beside 16px text, and nudge directional glyphs such as play and arrows about 1px toward their point so they look centered.
- **Do:** If filled icons mean "active", apply that rule to every item.
- **Avoid:** Filled and outline icons, or different stroke widths, in the same bar or list.

## ICO-02. Use conventional icon metaphors

**Why:** Familiar icons are recognized instantly; novel metaphors make users guess.

- **Do:** Use widely understood icons: gear for settings, sliders for filters, bookmark for save-for-later, paper plane for send, lock for privacy, globe for language, a play triangle for resume after pause and a circular arrow only for retry or refresh.
- **Do:** Add a text label wherever an icon could be ambiguous.
- **Do:** When one button toggles between states (pause and resume), swap the icon and the accessible name together ("Pause upload", "Resume upload").
- **Do:** Reserve trailing chevrons for rows that open a deeper level, and mark an option chosen in place with a check instead.
- **Avoid:** Custom metaphors for common actions, or an icon that conventionally means something else.

## ICO-03. Add leading icons to long settings and navigation lists

**Why:** A familiar icon beside each label is a second cue that makes long lists faster to scan.

- **Do:** In long settings and navigation lists that people scan by category, place one 20-24px icon from the same set at the start of each row, in a single aligned column.
- **Do:** Keep the text label and mark decorative icons aria-hidden.
- **Avoid:** Long text-only settings lists, or icons that replace the label.
- **Avoid:** Decorative icons on short lists, table rows or every label in a form.

## ICO-04. Give icon-only controls a name

**Why:** Screen readers and new users cannot interpret an unlabeled glyph.

- **Do:** Give every icon-only control an aria-label and a tooltip with the same text.
- **Do:** Prefer visible labels for primary navigation and uncommon actions.
- **Do:** Include any visible text in the accessible name, ideally at its start (WCAG 2.2 SC 2.5.3 Label in Name), and mark decorative alternate words shown on hover aria-hidden.
- **Avoid:** Unnamed icon buttons, names that differ from the visible tooltip, or controls that reveal their label or destination only on hover, which touch users never see.

## ICO-05. Use imagery that supports the message

**Why:** Images that do not illustrate the message add noise; relevant visuals speed understanding.

- **Do:** Choose images or illustrations that show what the headline promises, in a style consistent with the brand.
- **Do:** When no real imagery exists, prefer in order: your own photographs of the product, the real interface rendered with believable data, drawings of the product's own objects in its palette, then type and color alone.
- **Do:** Keep content backgrounds calm and let product imagery provide the visual interest.
- **Avoid:** Generic stock photos as filler, or decorative blobs and shapes behind product grids and text.
- **Avoid:** Generic 3D characters, isometric people or generated scenes that do not depict the product, or stock and generated pictures passed off as photos of the actual product, premises or staff.

## ICO-06. Crop images to keep the subject visible

**Why:** Cropping that cuts off the subject makes a card lose its meaning.

- **Do:** Use object-fit: cover with object-position set to the subject's focal point, and check crops at each breakpoint.
- **Avoid:** Stretched images (object-fit: fill) or automatic center crops that cut off faces or products.

## ICO-07. Normalize SVG strokes for progress and scaling

**Why:** A few SVG attributes keep line weights stable when graphics scale and make progress strokes trivial to drive.

- **Do:** Set pathLength="1" and drive stroke-dasharray and stroke-dashoffset in 0-1 units for rings, borders and draw-on lines.
- **Do:** Add vector-effect="non-scaling-stroke" to strokes in responsively scaled SVGs, and transform-box: fill-box on parts that rotate or scale around their own center.
- **Do:** Start rings at 12 o'clock with a -90 degree rotation and round line caps.
- **Avoid:** Calling getTotalLength every frame, or a solid spinning ring for something that is not loading.

## ICO-08. Switch from outline to filled for active icons

**Why:** Swapping an outline icon for its filled version is a clear, low-cost state change.

- **Do:** Use outline icons at rest and the filled version only for the selected or active state, with the label weight increased; show hover and :focus-visible with a color or background tint of the same glyph instead.
- **Do:** Transition only the properties that change (color, opacity, transform) for about 200-300ms.
- **Avoid:** transition: all, or hover animation as the only sign of interactivity on touch devices.
- **Avoid:** Filling icons on hover, which makes the hovered item look selected, or swapping a line icon for a full-color illustration on hover, which mixes two styles in one row.

## ICO-09. Ship a still fallback for animated illustrations

**Why:** Animated illustrations can fail to load or need pausing; a still frame keeps the page meaningful.

- **Do:** Include a static image of the key frame alongside any Lottie or canvas animation, with the alt text on one of them and the other aria-hidden.
- **Do:** Show the still when scripts fail or prefers-reduced-motion is set.
- **Avoid:** An empty box until the animation library loads.

## ICO-10. Generate repeated SVG parts in code

**Why:** Radial or repeated details are easier to tune when generated in a loop than drawn by hand.

- **Do:** Create nodes with document.createElementNS("http://www.w3.org/2000/svg", "rect"), rotate each by i * 360 / count, build once, then animate the group with one transform.
- **Do:** Draw evenly spaced ticks with one circle and a dash pattern where possible.
- **Avoid:** document.createElement for SVG elements (they land in the HTML namespace and do not render), or one DOM node per tick when a dash pattern would do.

## ICO-11. Keep pixel art crisp

**Why:** Default smoothing blurs pixel art and bitmap-style lettering.

- **Do:** Set image-rendering: pixelated on scaled sprites and canvases and scale by whole-number factors.
- **Avoid:** Fractional scaling of pixel assets, or pixel fonts for body text.

## ICO-12. Do not use emoji as interface icons

**Why:** Emoji render differently on every platform, ignore color tokens and stroke weights, and are read aloud by their names, so they rarely fit the rest of the interface.

- **Do:** Use one vector icon set for navigation, buttons, bullets, status and feature headings, or no icon at all.
- **Do:** Keep emoji where they are user content: reactions, messages, names and user-chosen labels.
- **Do:** If an emoji must appear as decoration, wrap it in an element with aria-hidden="true" and keep the meaning in visible text.
- **Avoid:** Emoji in navigation items, buttons, headings, list bullets or empty states.
- **Avoid:** An emoji as the only carrier of a status or meaning.
