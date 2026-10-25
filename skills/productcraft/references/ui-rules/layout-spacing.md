# UI rules: Layout and spacing

Spacing scale, grouping, alignment, hierarchy and grids. Rule IDs use the `LAY-` prefix; cite them in change reports.

## LAY-01. Use a 4/8 spacing scale

**Why:** Values drawn from one scale give every screen the same rhythm, while one-off numbers make layouts look accidental.

- **Do:** Take every padding, margin and gap from a token scale such as 4, 8, 12, 16, 24, 32, 40, 48.
- **Do:** Use padding for space inside an element and gap or margin for space between elements, both from the same scale.
- **Do:** Give repeated elements (cards, rows, chips) identical spacing.
- **Do:** Apply the scale to padding, margins, gaps and component sizes; 1px borders, 2px focus outlines, line heights and 1-2px optical icon nudges sit outside it.
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
- **Avoid:** Lopsided sections with text in one half and nothing in the other, or empty bands from stacked section padding and margins.

## LAY-04. Align to shared edges

**Why:** Near-miss alignment of a few pixels reads as sloppiness even when users cannot say why.

- **Do:** Align icons, text and buttons in a column to one left edge, and align numeric values such as prices to one right edge.
- **Do:** In card rows, make cards equal height and pin the action to the bottom (flex column with margin-top: auto) so buttons share a baseline.
- **Do:** Inspect layouts at high zoom or with guides to catch 1-6px offsets.
- **Do:** Left-align text by default; center only short moments such as a one- or two-line hero, an empty state or a short dialog.
- **Avoid:** Centered body paragraphs next to left-aligned headings in the same block, or centered paragraphs longer than about three lines.

## LAY-05. One focal point per screen

**Why:** When every element has the same weight, users do not know where to look first.

- **Do:** Rank content with size, weight and color: one large title, quieter body text and one high-contrast primary action.
- **Do:** Run a squint test (filter: blur(6px) on the page root, or a screenshot shrunk to about 25%): the primary action should still be the most distinct shape; if several compete, quiet the secondary fills before enlarging the primary.
- **Do:** Vary emphasis deliberately, for example a featured card larger than regular ones.
- **Avoid:** Headline, body and button text at similar size and weight.
- **Avoid:** A loud primary button repeated on every row of a list.
- **Avoid:** Rows of three or more identical icon-title-blurb cards with no lead item; keep uniform tiles for genuinely comparable items such as products or search results.

## LAY-06. Remove elements that do not earn their place

**Why:** Every element competes for attention, so extras slow users down on the main task.

- **Do:** For each element, ask which user task it supports; remove or move it if the answer is none.
- **Do:** Move secondary details into detail views or disclosures.
- **Do:** Consolidate scattered secondary actions into one clearly placed control.
- **Avoid:** Decorative icons, duplicate buttons, "see all" links and filler added just because there is space.
- **Avoid:** Simplifying by fading the remaining text below 4.5:1 or replacing labeled primary navigation with a single icon button.
- **Note:** Never remove information people need to decide or act, such as price, limits, errors or legal text.

## LAY-07. Group with space and tint before borders

**Why:** Every line adds visual noise; spacing and subtle background tints group content more quietly.

- **Do:** Separate list rows with consistent spacing instead of a divider under every item.
- **Do:** Give inputs such as search a light filled background instead of a box inside another bordered band, and keep the field identifiable with a border or bottom edge at 3:1 or more against its surroundings.
- **Do:** Set off footers or action bars with a faint background tint.
- **Avoid:** Stacking borders, bands and outlines on the same element.
- **Avoid:** A near-white fill (about 1.1:1) as the only cue that an input exists.
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

- **Do:** On a 375pt-wide frame, place a 56pt navigation row with a 44x44 back target directly under the runtime top inset, then a title of about 28px about 8px below it, with 8px to its description.
- **Do:** Leave 24px to a 56px-tall full-width input with 16px side margins and a visible label above it, or a floating label that stays visible once filled.
- **Do:** Put a related secondary link 16px below the input, then a large gap before the bottom group.
- **Do:** Keep consent text 24px above a 56px full-width primary button that sits 16px above the keyboard or safe area.
- **Avoid:** Using the same gap within and between groups, a top offset hard-coded to one status-bar height, or letting the button touch the keyboard.
- **Note:** Scale the values proportionally for other device sizes; read safe areas at runtime.

## LAY-14. Bento grids need one leading tile

**Why:** Mixed-size tiles read as one system only when gaps, radii and padding are identical and one tile clearly leads.

- **Do:** Lay out with CSS Grid (for example repeat(12, 1fr) or grid-template-areas) and let tiles span columns and rows.
- **Do:** Use one gap value, one radius token and one inner padding for every tile.
- **Do:** Give exactly one tile the lead (larger, or the only accent fill) and collapse to a single column with that tile first on mobile.
- **Avoid:** Several radii, gaps or shadow styles on one screen, or several bright tiles competing for attention.

## LAY-15. Adapt the layout to each device class

**Why:** Stretching a phone layout to desktop wastes space, and shrinking a desktop layout onto a phone crowds it.

- **Do:** Switch patterns at breakpoints or container queries (around 600px and 1024px): phone with one column and bottom navigation, tablet with a side rail and two panes, desktop with a sidebar and multi-column grid.
- **Do:** Keep components and tokens shared across breakpoints so it still reads as one product.
- **Do:** Let tile groups reflow by available width, for example repeat(auto-fit, minmax(min(100%, 10rem), 1fr)), so four tiles become two per row before one.
- **Do:** For split layouts such as sign-in beside an illustration, drop or shrink the visual on mobile so the form comes first.
- **Avoid:** Proportionally shrinking a desktop split layout onto a phone.

## LAY-16. Scale spacing from a reference design, never the user's text size

**Why:** Scaling lengths from a reference frame keeps proportions, but text must still follow the user's accessibility settings.

- **Do:** Use flexible layout primitives (flex, grid, constraints) for structure and scale only spacing and radii if needed.
- **Do:** If a reference-frame scaler is used, compute its factor from the shorter screen side and clamp it to about 0.85-1.2, so tablets, landscape and split screen gain content rather than oversized chrome.
- **Do:** Respect the platform text scale (for example MediaQuery textScaler, allowFontScaling or rem units) and clamp only extreme values, for example with maxFontSizeMultiplier on dense UI.
- **Avoid:** Shrinking all fonts with screen width, applying a layout scale factor to font sizes, or assuming one phone size fits tablets and split screen.
- **Note:** Pixel-scaling helpers are debated; responsive layout is the better default.

## LAY-17. Build layouts that survive translation and right-to-left

**Why:** Fixed widths, physical left and right properties and one overflow rule for everything break as soon as text grows or direction flips.

- **Do:** Size labeled controls with min-width and padding, and plan for about 30% longer sentences and two to three times longer short labels.
- **Do:** Use logical properties (margin-inline-start, padding-inline, inset-inline-end, text-align: start) and set lang and dir on the root element.
- **Do:** Mirror directional icons such as back arrows and chevrons in right-to-left layouts, but not logos, clocks, media playback symbols or numbers.
- **Do:** Choose overflow by element type: buttons grow or go full width rather than clip, table cells truncate with the full text available, and titles clamp to two lines.
- **Avoid:** Fixed widths on buttons, tabs or chips that hold translated text.
- **Avoid:** overflow: hidden as a global default, or margin-left and padding-right in components that must flip.
- **Note:** Test with a long-word language and a right-to-left language before shipping.
