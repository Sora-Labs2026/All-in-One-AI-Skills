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

## FRM-17. Build one-time-code entry that accepts typing, paste and autofill

**Why:** Codes arrive by keyboard, clipboard and OS autofill; boxes that only handle keystrokes force people to retype.

- **Do:** Use one real input (styled as boxes) or one input per box, with inputmode="numeric", autocomplete="one-time-code", pattern="[0-9]*" and maxlength.
- **Do:** Spread a pasted code across all boxes, auto-advance on each digit, step back on Backspace in an empty box, and submit automatically on the last digit (say so in the helper text).
- **Do:** Give the group a label (role="group" or fieldset) and each box a name such as "Digit 2 of 4"; drive the box count from one constant used in the copy as well.
- **Do:** Optionally request SMS codes with the WebOTP API (navigator.credentials.get with otp transport "sms").
- **Avoid:** type="number" (spinners, lost leading zeros), blocked paste, or a heading that says 4 digits beside 6 boxes.

## FRM-18. Wire sign-in fields for password managers

**Why:** Correct field semantics let browsers and password managers fill credentials, which removes most sign-in friction.

- **Do:** Use a real form with visible labels, type="email" with autocomplete="username" (or "email"), and autocomplete="current-password" on sign-in or "new-password" on sign-up.
- **Do:** In native apps set the platform equivalents (for example keyboardType="email-address", autoCapitalize="none", textContentType and secureTextEntry).
- **Do:** Put "Forgot password?" beside the password field, state the duration on any "remember me" option, and carry the typed email across when switching between sign-in and sign-up.
- **Avoid:** Marking a sign-in password as new-password, or bare inputs with no type, label or autocomplete.

## FRM-19. Add a show-password toggle and keep password rules visible

**Why:** Revealing what was typed reduces errors, and rules that vanish on the first keystroke cause failed submissions.

- **Do:** Make the toggle a button type="button" inside the field's trailing edge with aria-label ("Show password") and aria-pressed, swapping the input type without moving the caret.
- **Do:** Keep rules such as "8 characters or more" in persistent helper text linked with aria-describedby.
- **Do:** If you show a strength meter, pair the color with a text label and estimate strength with a pattern-aware estimator rather than length times character-set size.
- **Avoid:** A non-focusable eye icon, or rules stated only in the placeholder.

## FRM-20. Collect PINs and amounts with a clear keypad and a live readout

**Why:** Money and PIN entry need large keys, a visible value and a second check for invisible typos.

- **Do:** Show the amount large and centered with any converted value beneath it, updating on each key.
- **Do:** Prefer a native input with inputmode="decimal" (amounts) or inputmode="numeric" (PINs); if a custom keypad is required, use real buttons of at least 48px with labels for symbol keys and also accept hardware keyboards.
- **Do:** Mask PINs as filling dots, use autocomplete="new-password" for creation, and follow "Create PIN" with "Confirm PIN", clearing both and explaining on mismatch.
- **Avoid:** Echoing PIN digits in plain text, or a custom keypad as the only input path.

## FRM-21. Make upload zones state their limits and track each file

**Why:** Uploads fail in many ways; stating limits up front and showing per-file status prevents surprises.

- **Do:** Show accepted types, size limit and file count in the zone, and accept drop, paste and a real file input behind a visible browse button.
- **Do:** Highlight the zone on dragenter and dragover, and list each file with name, size and progress, then done or failed with a reason and a retry.
- **Do:** Show an aggregate summary ("3 of 4 uploaded, 1 failed") with clear and per-file remove controls that have accessible names.
- **Avoid:** Drag-and-drop as the only route, silent rejection, or failed files dropped from the list.

## FRM-22. Write settings toggles as full rows that apply immediately

**Why:** Each switch should say what it does, take effect at once and be easy to hit.

- **Do:** Build each row as a label, a one-line description and a trailing switch (role="switch" with aria-checked, or a native checkbox styled as a switch), with the whole row as the target.
- **Do:** Show the on state by knob position and fill, not color alone, and offer undo or confirmation for security-sensitive changes.
- **Avoid:** Switches with no visible label, or switches whose change only applies after a separate Save.

## FRM-23. Prefill quick-add forms with sensible defaults

**Why:** Option rows with realistic defaults let people create an item by typing one field.

- **Do:** Put the single required field first and focused, and show the other options as rows with an icon, label, current value and chevron that open pickers.
- **Do:** Choose defaults that cover the common case and show them as real values.
- **Avoid:** Turning every option into a required step, or chevron rows that are not tappable.

## FRM-24. Make date and time pickers show context and valid ranges

**Why:** Scheduling is easier when people see the surrounding week or month and cannot pick impossible ranges.

- **Do:** Use a week strip (day name above date, selected day filled, today marked differently) for near-term dates, with arrows for other weeks and a way to open a full calendar.
- **Do:** Bind the end date's minimum to the start date, use a two-thumb slider or paired fields for time windows, and echo the choice in plain words ("3 days, Fri 7 to Mon 10").
- **Do:** Give each day a full-date accessible name and aria-selected or aria-pressed, with targets of at least 40-44px.
- **Avoid:** Return dates earlier than pick-up dates, or selected days marked by color alone.

## FRM-25. Wire payment card fields for autofill and verification

**Why:** Autofill tokens and formatting cut card-entry time and errors.

- **Do:** Use autocomplete="cc-name", "cc-number", "cc-exp" and "cc-csc" with inputmode="numeric", group the number as the user types, show the detected network and use an MM / YY expiry.
- **Do:** Prefer the payment provider's hosted fields, and label the pay button with the exact amount and a short security note.
- **Avoid:** type="number" for card numbers, or a decorative card preview as the only place the entered data is visible.

## FRM-26. Show recent and saved values under search-like inputs

**Why:** Many entries repeat; showing recents removes typing entirely.

- **Do:** List recent or saved values (places, contacts, searches) under the field with an icon, bold name and muted detail, filtering as the user types.
- **Do:** Set enterkeyhint and suitable autocomplete values on the inputs.
- **Avoid:** Hiding recents until the user starts typing.

## FRM-27. Keep native semantics under custom-styled controls

**Why:** However decorative a slider, knob or switch looks, keyboard and assistive-technology users need it to behave like the real control.

- **Do:** Style the native element (input type="range" with appearance: none, a checkbox for switches), or use role="slider" or role="switch" with the matching aria-value or aria-checked attributes and full keyboard support.
- **Do:** Show the value as text with units and expose it through aria-valuetext ("96 dB, loud"), and keep thumbs at least 44px.
- **Do:** Communicate thresholds or danger zones with a label and marker, not only a color gradient.
- **Avoid:** Div-only sliders or drag-only knobs.

## FRM-28. Verify on the server and send credentials only to your own backend

**Why:** Client-side checks can be bypassed, and generic form builders are not built to receive passwords.

- **Do:** Verify one-time codes, totals and permissions on the server, and post sign-in forms to your own authentication endpoint over HTTPS.
- **Avoid:** Hard-coded codes compared in client code, or passwords collected through a third-party form embed.
