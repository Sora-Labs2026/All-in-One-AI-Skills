# UI rules: Layout and spacing

Spacing scale, grouping, alignment, hierarchy and grids. Rule IDs use the `LAY-` prefix; cite them in change reports.

## LAY-01. Use a 4/8 spacing scale

**Why:** Values drawn from one scale give every screen the same rhythm, while one-off numbers make layouts look accidental.

- **Do:** Take every padding, margin and gap from a token scale such as 4, 8, 12, 16, 24, 32, 40, 48.
- **Do:** Use padding for space inside an element and gap or margin for space between elements, both from the same scale.
- **Do:** Give repeated elements (cards, rows, chips) identical spacing.
- **Avoid:** Off-scale values such as 7, 13 or 22px, or different inner padding on sibling cards.
- **Note:** A 4px base and an 8px base are both fine; pick one and enforce it.

## LAY-02. Let spacing show what belongs together

**Why:** People read small gaps as "related" and large gaps as "separate", so spacing can carry structure without borders or labels.

- **Do:** Use tiers: about 4-8px between a label and its own input, 12-16px between items in a group, 24-32px between groups, and 40-48px between independent sections.
- **Do:** Keep every label clearly closer to its own field than to the field above it.
- **Do:** Leave the largest gap in a form just before the primary action, and keep qualifying text (for example consent text) close to the button it qualifies.
- **Avoid:** One uniform gap between labels, fields, buttons and sections.
- **Avoid:** Label placement that floats halfway between two inputs.

## LAY-03. Give content room to breathe

**Why:** Cramped layouts are hard to scan and tap; adding space is often the fastest way to make a busy screen calm.

- **Do:** Keep at least 16px between text and container edges, and 24px on roomy mobile cards.
- **Do:** Give every card in a set the same inner padding on all sides.
- **Do:** When a screen feels busy, try doubling the gaps inside cards and between sections before removing content.
- **Avoid:** Text or buttons touching card edges, or tight 4px gaps between headings and their content.
- **Avoid:** Spacing so large that related items stop looking related.

## LAY-04. Align to shared edges

**Why:** Near-miss alignment of a few pixels reads as sloppiness even when users cannot say why.

- **Do:** Align icons, text and buttons in a column to one left edge, and align numeric values such as prices to one right edge.
- **Do:** In card rows, make cards equal height and pin the action to the bottom (flex column with margin-top: auto) so buttons share a baseline.
- **Do:** Inspect layouts at high zoom or with guides to catch 1-6px offsets.
- **Avoid:** Centered body paragraphs next to left-aligned headings in the same block.

## LAY-05. One focal point per screen

**Why:** When every element has the same weight, users do not know where to look first.

- **Do:** Rank content with size, weight and color: one large title, quieter body text and one high-contrast primary action.
- **Do:** Run a squint test: with the screen blurred, the most important element should still stand out.
- **Do:** Vary emphasis deliberately, for example a featured card larger than regular ones.
- **Avoid:** Headline, body and button text at similar size and weight.
- **Avoid:** A loud primary button repeated on every row of a list.

## LAY-06. Remove elements that do not earn their place

**Why:** Every element competes for attention, so extras slow users down on the main task.

- **Do:** For each element, ask which user task it supports; remove or move it if the answer is none.
- **Do:** Move secondary details into detail views or disclosures.
- **Do:** Consolidate scattered secondary actions into one clearly placed control.
- **Avoid:** Decorative icons, duplicate buttons, "see all" links and filler added just because there is space.
- **Note:** Never remove information people need to decide or act, such as price, limits, errors or legal text.

## LAY-07. Group with space and tint before borders

**Why:** Every line adds visual noise; spacing and subtle background tints group content more quietly.

- **Do:** Separate list rows with consistent spacing instead of a divider under every item.
- **Do:** Give inputs such as search a light filled background instead of a box inside another bordered band.
- **Do:** Set off footers or action bars with a faint background tint.
- **Avoid:** Stacking borders, bands and outlines on the same element.
- **Note:** Dense data tables can still benefit from row separators.

## LAY-08. Lay out on a column grid

**Why:** A shared grid makes widths and gutters repeat, so edges line up across rows and screens.

- **Do:** Use about 4 columns on mobile, 8 on tablet and 12 on desktop, with fixed gutters such as 16px.
- **Do:** Size cards and tiles to whole columns, using CSS Grid or a layout primitive rather than hand-set widths.
- **Avoid:** Arbitrary component widths that share no edges, or gutters that change between rows of one layout.

## LAY-09. Chunk long content and disclose progressively

**Why:** Working memory is limited; short labeled sections are easier to scan than a wall of text.

- **Do:** Break long content into short titled sections with numbers or icons.
- **Do:** Show a one-line summary on detail cards and put secondary details in collapsible rows.
- **Do:** Keep the primary action visible after the summary, not after all the text.
- **Avoid:** Hiding information needed for the decision (price, key specs) inside collapsed sections.

## LAY-10. Keep text and images in separate tracks

**Why:** Text that wraps around a small inline image keeps changing line length, which breaks reading rhythm.

- **Do:** Put the image full width above or below the paragraph, or give image and text their own columns.
- **Do:** Stack image above text on narrow screens.
- **Avoid:** Floating a small image inside a paragraph so lines are short beside it and long below it.

## LAY-11. Let feature media break out of the text column

**Why:** In long-form pages, images wider than the reading column add rhythm and immersion while text keeps a comfortable measure.

- **Do:** Define grid tracks for a narrow text column plus wider "breakout" and "full-bleed" tracks for media.
- **Do:** Keep body text at a readable measure while hero and key images use the wider tracks.
- **Avoid:** Forcing every image in a long article to the narrow text width.
- **Note:** Optional technique for editorial layouts.

## LAY-12. Vary image sizes in editorial galleries

**Why:** A few larger images give the eye an entry point; a wall of identical thumbnails has none.

- **Do:** Let the lead image span a full row or a 2x2 block, with smaller images around it, using grid-column and grid-row spans.
- **Do:** Put the strongest image in the largest slot and keep gutters uniform.
- **Avoid:** Mixed sizes in product listings, where uniform tiles are better for comparison.

## LAY-13. Spacing recipe for a single-question mobile step

**Why:** One-field steps (email, name, code) look calm and structured when every gap follows a deliberate rhythm.

- **Do:** On a 375pt-wide frame: title about 28px with 8px to its description, text block about 96px from the top, 24px to a 56px-tall full-width input with 16px side margins.
- **Do:** Put a related secondary link 16px below the input, then a large gap before the bottom group.
- **Do:** Keep consent text 24px above a 56px full-width primary button that sits 16px above the keyboard or safe area.
- **Avoid:** Using the same gap within and between groups, or letting the button touch the keyboard.
- **Note:** Scale the values proportionally for other device sizes; read safe areas at runtime.
