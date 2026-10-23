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
