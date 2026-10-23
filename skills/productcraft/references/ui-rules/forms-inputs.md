# UI rules: Forms and inputs

Labels, layout, controls, validation and multi-step forms. Rule IDs use the `FRM-` prefix; cite them in change reports.

## FRM-01. Visible labels; placeholders only for examples

**Why:** Placeholder text disappears while typing and is usually low contrast, so it cannot replace a label.

- **Do:** Show a persistent label above every input, linked with label for/id.
- **Do:** Use the placeholder only for an example of the expected format (for example name@example.com), or leave it empty.
- **Do:** Put essential instructions in helper text below the field.
- **Avoid:** Placeholder-only labels such as "Enter email", or a placeholder that repeats the label.

## FRM-02. Top-aligned labels in a single column

**Why:** Labels stacked above fields along one edge create a straight scan path that works at every width.

- **Do:** Stack each field full width with its label above it, aligned to the same edge as the submit button.
- **Do:** Let short related pairs (first and last name, city and postcode) share a row when space allows.
- **Avoid:** Unrelated fields side by side, or labels in a left column that force a zig-zag eye path on mobile.
- **Note:** Left-aligned labels can suit wide desktop forms that must stay vertically compact.

## FRM-03. Group long forms under section headings

**Why:** Headings and spacing break long forms into chunks users can understand and complete.

- **Do:** Split long forms into titled groups (for example Personal information, Billing address, Change password) using fieldset/legend or real headings.
- **Do:** Make section headings clearly larger than field labels and leave more space between groups than between fields.
- **Avoid:** Seven or more unrelated fields in one undifferentiated column.

## FRM-04. Ask for less and let the product do the work

**Why:** Every field adds effort and abandonment risk; the system should absorb complexity it can handle.

- **Do:** Remove fields that are not needed for the task, and collect optional details later.
- **Do:** Prefer one full-name field over separate first and last name when the data model allows.
- **Do:** Prefill known data from the account or device, set autocomplete attributes, suggest addresses and reuse saved payment methods, keeping prefilled values visible and editable.
- **Avoid:** Asking again for information the product already has.

## FRM-05. Use the input type that matches the data

**Why:** Purpose-built inputs bring up the right keyboard, enable autofill and signal the expected answer.

- **Do:** Set type, inputmode and autocomplete (type="email", type="tel", inputmode="numeric", autocomplete="one-time-code").
- **Do:** Use one field for an email address, allow paste and trim whitespace before validating.
- **Do:** Let users type values they know, such as a birth year, instead of scrolling a long dropdown.
- **Do:** Size fields to the answer: a single line for short values, a textarea for messages.
- **Avoid:** Email split into local part and domain boxes, or a one-line box for a long message.

## FRM-06. Choose the control by the kind of choice

**Why:** The control itself tells users whether one or many options can be chosen.

- **Do:** Use a visible radio group or segmented control for about 2-5 mutually exclusive options, and a select or combobox for long lists.
- **Do:** Use checkboxes for multi-select, a switch for on/off settings that apply immediately, and a single checkbox for yes/no choices submitted with a form.
- **Do:** Use chips for filters and tags, and labeled swatches for visual attributes such as color.
- **Avoid:** Hiding three or four short options in a dropdown, Yes/No in a dropdown, or checkboxes for mutually exclusive options.

## FRM-07. Type-to-filter for long lists

**Why:** Scrolling hundreds of items such as countries is slow; typing a few letters finds the item immediately.

- **Do:** Replace long select menus with a combobox that filters as the user types and matches partial input.
- **Do:** Support arrow-key navigation and ARIA combobox semantics, and surface likely choices (for example the detected country) first.
- **Avoid:** Hundreds of alphabetical options in a plain dropdown.

## FRM-08. Pair sliders with numeric inputs

**Why:** Sliders are fast for rough values but imprecise; people also need to see and type exact numbers.

- **Do:** Show the live value, label the minimum and maximum, and use a dual-thumb slider for ranges.
- **Do:** Pair the slider with editable number fields that stay in sync.
- **Do:** Give thumbs at least a 44px target and support arrow keys and Home/End.
- **Avoid:** A bare slider with no visible value, or a long dropdown of fixed numeric steps.

## FRM-09. Selectable tiles for a few comparable options

**Why:** When options differ by one or two key values, large tiles are easier to compare and tap than tiny radios.

- **Do:** For 2-6 options, lay out tiles with the main value bold (for example 1TB) and the secondary value below (for example the price).
- **Do:** Mark the selected tile with an accent border plus a check or filled indicator.
- **Do:** Keep radio semantics (role="radiogroup", arrow-key navigation, checked state).
- **Avoid:** Tiles for long or plain-text lists, or selection shown by a subtle color change only.

## FRM-10. Design every field state

**Why:** Fields that change with state show users where they are and whether input is valid.

- **Do:** Define default, focused, filled, disabled, error and success states.
- **Do:** Reserve a helper-text slot under each field so messages appear without shifting the layout.
- **Do:** Pair status colors with an icon and text.
- **Avoid:** Disabled fields that look empty or enabled, or states shown by border color alone.

## FRM-11. Show specific errors inline, next to the field

**Why:** An error far from its field makes users hunt for the problem.

- **Do:** Validate on blur or submit, show the message directly under the field with a red border and an error icon, and say how to fix it.
- **Do:** Link the message with aria-describedby, set aria-invalid="true" and move focus to the first invalid field on submit.
- **Do:** For passwords, show a live checklist of requirements that updates while typing.
- **Avoid:** A list of errors under the submit button, a generic "Error found" banner, or validating on every keystroke before the user has finished.

## FRM-12. Mark required and optional fields one consistent way

**Why:** Users need to know what they can skip; clutter on every label slows them down.

- **Do:** When most fields are required, mark only the exceptions with a muted "(optional)".
- **Do:** Otherwise mark required fields with an asterisk and explain it once at the top of the form.
- **Do:** Always set required or aria-required on the input.
- **Avoid:** "(required)" in red on every label, or a symbol whose meaning is never explained.

## FRM-13. Show formats with hints and gentle masks

**Why:** Showing the expected format prevents errors before they happen.

- **Do:** Show patterns such as MM/YY or DD/MM/YYYY in persistent helper text or a mask.
- **Do:** Insert separators as the user types (card numbers in groups of four, or 4-6-5 for 15-digit cards) and strip them before validating.
- **Do:** Accept pasted values in common formats.
- **Avoid:** Blank date or phone fields with no hint, or rejecting input because separators differ.
- **Note:** Masks must not block editing or confuse screen readers.

## FRM-14. Split long forms into steps with visible progress

**Why:** Short steps with a progress indicator reduce overwhelm and show how much is left.

- **Do:** Group about 3-4 related fields per step and show a stepper or progress bar.
- **Do:** End each step with a primary "Next" and a secondary "Skip" for optional steps.
- **Do:** Keep entered data when users move back between steps.
- **Avoid:** Hiding how many steps remain, or splitting very short forms into many steps.

## FRM-15. Use boxed fields, not underline-only fields

**Why:** Enclosed fields are recognized as editable and have a clear tap area.

- **Do:** Render inputs as outlined or filled boxes about 44-56px tall with a visible focus style.
- **Avoid:** Bare underlines that look like dividers.

## FRM-16. Give rich-text editors familiar controls

**Why:** People writing formatted content should not need markup knowledge.

- **Do:** Provide a toolbar with bold, italic, underline, lists, link and image, plus a compact floating toolbar on text selection.
- **Do:** Explain where the content will appear and end with a secondary Cancel and a primary Save.
- **Avoid:** Raw markup for basic formatting in consumer-facing editors, or equally weighted Cancel and Save buttons.
