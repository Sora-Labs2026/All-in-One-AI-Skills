# UI rules: Components and design system

Foundations, tokens, core components, radius, elevation and common component patterns. Rule IDs use the `CMP-` prefix; cite them in change reports.

## CMP-01. Set foundations before drawing screens

**Why:** Settling color, type, spacing, radius and elevation scales first prevents one-off values and keeps screens consistent.

- **Do:** Define tonal ramps for the brand hue and a neutral gray, a 5-6 step type scale, a 4- or 8-based spacing scale, and small radius and elevation scales.
- **Do:** Build screens only from those scales.
- **Avoid:** Choosing values ad hoc screen by screen.

## CMP-02. Layer tokens and name them by purpose

**Why:** Referencing named decisions instead of raw values lets one change propagate everywhere and makes theming possible.

- **Do:** Use three tiers: primitives (blue-500 = #2563EB), semantic tokens (color-action-primary) and component tokens (button-bg-default).
- **Do:** Name semantic and component tokens by purpose, not appearance (button-primary, not blue-button).
- **Do:** Rebrand by changing primitives and support dark mode by remapping the semantic tier per theme, using the same names in code as in design files.
- **Avoid:** Hex, spacing or radius values hard-coded inside components.

## CMP-03. Build a few core components completely

**Why:** A small, fully specified set covers most screens and stays maintainable.

- **Do:** Start with button, input, card, avatar and navigation.
- **Do:** Give each explicit variants (primary, secondary, ghost, destructive), sizes (sm, md, lg) and states (default, hover, pressed, focus, disabled, loading).
- **Do:** Build one configurable Button component (variant, tone, size, leading or trailing icon, icon-only, badge) instead of styling buttons per screen.
- **Avoid:** Dozens of half-finished components, or components that only have a default state.

## CMP-04. Document how each component is used

**Why:** Short, consistent documentation turns a library into a shared language for design and code.

- **Do:** Give each component one page: when to use it, do and don't examples, properties and accessibility requirements (contrast, focus ring, target size).
- **Do:** Record version, status and owner, and keep release notes.
- **Avoid:** Shipping or changing components without usage guidance or a changelog.

## CMP-05. Pick one radius scale that fits the brand

**Why:** Corner rounding sets the tone, and a consistent scale makes components feel like one system.

- **Do:** Choose one tier and store it as tokens: sharp (0-2px) for formal products, moderate (4-16px) for neutral ones, or pill (height/2) for friendly ones.
- **Do:** Apply it consistently to buttons, inputs, chips and cards, scaling with component size.
- **Avoid:** Sharp, rounded and pill buttons mixed on one screen without a reason.

## CMP-06. Keep nested corners concentric

**Why:** An inner element with the same radius as its container leaves an uneven gap at the corners.

- **Do:** Set inner radius = outer radius - padding (a 24px card with 8px padding gets a 16px inner radius).
- **Do:** Use a small or zero inner radius when padding is equal to or larger than the outer radius.
- **Avoid:** The same radius on a card and the image inset inside it.

## CMP-07. Keep elevation soft and consistent

**Why:** Dark, tight or overused shadows look heavy and dated; soft, consistent elevation separates layers cleanly.

- **Do:** Use low-opacity, diffuse shadows with blur about twice the offset and no horizontal offset, for example 0 8px 24px rgba(15,23,42,.08), tinted toward the background hue rather than pure black.
- **Do:** Define a few elevation tokens (sm, md, lg) and reserve the strongest for floating layers such as menus and dialogs.
- **Do:** Or separate cards with a 1px light border, using one method for every card in a set.
- **Avoid:** Default heavy black shadows on every card and button, or shadows and strong borders on the same element.

## CMP-08. Size components to their content

**Why:** Content-driven sizing keeps padding consistent when labels change or are translated.

- **Do:** Let buttons hug their label plus fixed padding, fixing only the dimension that must stay constant (such as height).
- **Do:** Use flex or grid gaps for lists and cards so repeated items keep consistent spacing.
- **Do:** Use full width only where the layout calls for it, such as a bottom action on mobile.
- **Avoid:** Fixed button widths that clip longer labels, or absolute positioning that breaks when content changes.

## CMP-09. Same look, same meaning

**Why:** Elements that look alike are read as related, so visual treatments must map consistently to meaning.

- **Do:** Style every element with the same function identically: one button style per emphasis level, one link color, one chip shape.
- **Do:** Use one shared component for parallel items such as pricing tiers, and emphasize the recommended one with a single deliberate variant.
- **Do:** Group items that share a state together (for example unread items first).
- **Avoid:** Reusing a highlight style for unrelated purposes, or letting heading and icon colors drift between sibling cards.

## CMP-10. Give segmented controls an inset track

**Why:** An inset track makes segmented options read as one control.

- **Do:** Wrap the options in a track with about 4-8px inset, and show the selected option as a raised or contrasting pill.
- **Do:** Give each option button-like padding and keyboard support.
- **Avoid:** Segmented options placed directly on the page background with no track.

## CMP-11. Keep tooltips short and reachable without hover

**Why:** Brief contextual help explains a control without cluttering the layout, but hover-only help excludes touch and keyboard users.

- **Do:** Show tooltips on hover, keyboard focus and tap, anchored to the trigger, with one or two short sentences or a 1-4 word label.
- **Do:** Give icon buttons an aria-label matching their tooltip, and give first-run hints an explicit "Got it".
- **Avoid:** Essential instructions that exist only in a tooltip, or interactive content inside tooltips.

## CMP-12. Use modals for focused tasks and popovers for light context

**Why:** Blocking overlays interrupt; they should be reserved for tasks that need full attention.

- **Do:** Use a modal (scrim, trapped focus, visible close, Escape to dismiss, Cancel plus one primary action) for focused edits.
- **Do:** Use a non-blocking popover anchored to its trigger for short contextual content, dismissed by an outside click or Escape.
- **Do:** Return focus to the trigger when either closes.
- **Avoid:** Blocking overlays for trivial information, or dialogs with no visible way out.

## CMP-13. Give avatars fixed sizes and fallbacks

**Why:** Avatars personalize the interface, but missing photos must never break the layout.

- **Do:** Use a fixed size scale (for example 24, 32, 40, 48, 64px).
- **Do:** Fall back from photo to initials to a generic person icon, and place status badges at the bottom-right, scaled with the avatar.
- **Do:** Add a 2-4px ring in the surface color when an avatar overlaps a photo or another avatar.
- **Avoid:** Broken-image icons or arbitrary avatar sizes per screen.

## CMP-14. Structure action menus

**Why:** Account and overflow menus stay scannable when items are grouped and the exit action is isolated.

- **Do:** Open with a header that identifies the context (avatar, name), then group related items with dividers and leading icons.
- **Do:** Show shortcut hints right-aligned on desktop, and place Sign out or destructive items last in their own group.
- **Avoid:** A long undivided list, or Sign out mixed into everyday items.

## CMP-15. Make cards self-contained modules

**Why:** One topic per bounded card makes feeds and dashboards scannable and lets them reflow responsively.

- **Do:** Give each card one topic: a title, one key value, supporting metadata and at most one or two actions.
- **Do:** Keep padding, radius and separation identical across sibling cards.
- **Avoid:** Unrelated data or several competing buttons in one card.

## CMP-16. Make selected items obvious

**Why:** A small checked box alone is easy to miss in a list.

- **Do:** Change the whole row when selected (accent fill or tint, stronger border) and keep a check or checkbox as a non-color cue.
- **Avoid:** A selected row that looks identical to unselected ones except for a tiny checkbox.

## CMP-17. Give KPI tiles a fixed anatomy

**Why:** Dashboards are scanned tile by tile; a fixed structure makes every number interpretable at a glance.

- **Do:** Order each tile as a small label, a large value with tabular numerals, then a delta with arrow, sign and comparison period ("+4.9% vs last month"), with an optional icon or sparkline.
- **Do:** Render tiles from a data array of raw values mapped to one component, formatting with Intl.NumberFormat at render time.
- **Do:** Add a hover lift only when the tile opens a detail view, and give it a focus style too.
- **Avoid:** Up or down shown by green and red alone, hover lift on non-interactive tiles, or preformatted strings that cannot be sorted.

## CMP-18. Make charts answer one question and reveal exact values

**Why:** A chart is only useful if the reader knows what it shows, over what period, and can read exact values.

- **Do:** Give each chart a title, a one-line summary, a time-range control and labeled axes, and highlight the current or key series while muting the rest.
- **Do:** Show exact values in tooltips on hover and keyboard focus, put the total in the center of donuts, and list values beside legend entries.
- **Do:** Provide a text or table alternative and wrap charts in a responsive container.
- **Avoid:** Color-only legends, tiny low-contrast axis labels, glossy or 3D bars that distort comparison, or entrance animations replayed on every refresh.

## CMP-19. Build operational tables for triage

**Why:** Lists are read by status and recency; those must be scannable without decoding.

- **Do:** Use real table markup with th scope="col", right-aligned numbers with tabular numerals, and status pills with words.
- **Do:** Add filter tabs with counts above the table, show relative times with the absolute timestamp in a time element, and highlight the selected row with aria-selected beside a detail pane.
- **Avoid:** Column widths that jump when the selection changes, or status shown by a colored dot alone.

## CMP-20. Give list rows a leading visual, two lines and a trailing value

**Why:** A consistent row anatomy makes transactions, devices and people lists scannable.

- **Do:** Place an avatar, logo or icon first, primary text above secondary text, and the key value right-aligned at the end.
- **Do:** Keep signs on money values (-$24.00, +$240.00) with tabular numerals, group long lists under date headers, and keep tappable rows at least 48px tall.
- **Avoid:** Red and green as the only difference between debits and credits, or truncated trailing values.

## CMP-21. Keep product cards comparable

**Why:** Uniform cards let shoppers compare quickly across a grid.

- **Do:** Use a fixed image aspect-ratio with object-fit: cover, then category, name, price (right-aligned or accent), rating with its count, and one add action with an accessible name that includes the product.
- **Do:** Make the title the card's link and keep the add button outside the link; use grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)) for the grid.
- **Avoid:** Price or the add action shown only on hover, varying image heights, or nested interactive elements.

## CMP-22. Give carousels controls, position and a pause

**Why:** Rotating content hides information, so people need control over it.

- **Do:** Provide labeled previous and next buttons, a position indicator ("3 of 8"), keyboard arrows and scroll snapping.
- **Do:** Pause on hover and focus and offer a pause control if anything autoplays; treat 3D coverflow as optional styling over the same controls.
- **Avoid:** Autoplay without a way to stop it, drag as the only way to move, or the only copy of critical information inside a carousel.

## CMP-23. Give segmented controls and chips real selection semantics

**Why:** Compact toggles are fast, but assistive technology must know what is selected.

- **Do:** Use native radios or role="radiogroup" with role="radio" and aria-checked for single choice, and toggle buttons with aria-pressed or checkboxes for multi-select chips.
- **Do:** Move selection with arrow keys using a roving tabindex, and show the selected state with fill plus a check or weight change.
- **Do:** Let horizontal chip rows scroll with the last chip peeking past the edge.
- **Avoid:** ARIA roles without the matching keyboard behavior, or a faint tint as the only selected cue.

## CMP-24. Make swatch pickers named radio groups

**Why:** Swatches are single-choice inputs and must be operable and named like one.

- **Do:** Build them as a radio group, give each swatch a text name, and mark the selected one with an offset ring plus the visible variant name.
- **Do:** Keep the hit area at least 44px even when the visible dot is small, and update an accent token so the whole product view reflects the choice.
- **Avoid:** Unnamed color dots, or a per-variant accent that fails contrast on its background.

## CMP-25. Keep the current selection visible and removable

**Why:** People should always see what they picked and be able to undo it without reopening a menu.

- **Do:** Show the selected value in the trigger, or as a chip with a labeled remove button.
- **Do:** Announce changes in a polite live region and use listbox or menu semantics with Escape returning focus to the trigger.
- **Avoid:** Replacing the labeled trigger with an unlabeled icon once a value is chosen.

## CMP-26. Route accents through one token per theme or variant

**Why:** When every accent use reads one custom property, re-theming and per-item colors stay consistent.

- **Do:** Define the accent once (for example --accent) and set it per theme or variant with a data attribute, using it for text, fills, borders, glows and focus.
- **Do:** Check each variant's accent against its own background.
- **Avoid:** Repeating accent hex values across many rules.

## CMP-27. Use a large fixed radius for pills

**Why:** A fixed large radius keeps semicircular ends at any width, while 50% turns wide elements into ellipses.

- **Do:** Use border-radius: 999px for pills, chips, pill buttons and indicators.
- **Avoid:** border-radius: 50% on non-square elements.

## CMP-28. Prefer the native share sheet

**Why:** The system share sheet lists the user's own apps; a custom icon row is only a fallback.

- **Do:** Call navigator.share when navigator.canShare allows it, and otherwise expand a row of labeled share targets plus "Copy link" with immediate confirmation.
- **Avoid:** Unlabeled brand icons, or a share row that opens on hover.

## CMP-29. Give feeds and notifications a fixed item anatomy

**Why:** A predictable order makes long feeds and notification lists scannable.

- **Do:** Show avatar, name, relative time and an overflow menu with an accessible name, then body text clamped to 2-3 lines with an in-place "See more", then media and reactions with counts.
- **Do:** For notifications, put the actor in bold, the action text and a relative time, entering with a short slide and fade.
- **Avoid:** Wrapping a card that contains buttons in one big link, or autoplaying video with sound.

## CMP-30. Lay out media players in the familiar order

**Why:** Familiar control order lets people operate a player without hunting.

- **Do:** Show artwork, title and artist, a progress bar with elapsed and total time, then shuffle, previous, a larger play or pause, next and repeat.
- **Do:** Give icon buttons accessible names and reflect toggles such as shuffle and repeat with aria-pressed.
- **Avoid:** A play button the same size and weight as the secondary controls.

## CMP-31. Build checklists from real checkboxes with a live count

**Why:** Clear done states and a running tally give a sense of progress.

- **Do:** Use labeled checkboxes, show done items with a check, line-through and reduced emphasis, and update "3 of 8 completed" in a polite live region.
- **Do:** Name delete buttons after their item and offer undo.
- **Avoid:** Deleting with no undo, or low-contrast placeholder text on dark surfaces.

## CMP-32. Lay out receipts and money summaries for checking

**Why:** Financial summaries must be easy to verify line by line.

- **Do:** Use label and value rows with tabular numerals and right-aligned amounts, listing subtotal, discount (with a minus sign), fees, tax with its rate and a bold total, plus a reference number.
- **Do:** Render receipts as real text that can be selected, printed or downloaded.
- **Avoid:** Marking discounts by red alone, or decoration that covers the figures.
