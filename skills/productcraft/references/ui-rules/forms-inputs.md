# UI rules: Forms and inputs

Labels, layout, controls, validation and multi-step forms. Rule IDs use the `FRM-` prefix; cite them in change reports.

## FRM-01. Visible labels; placeholders only for examples

**Why:** Placeholder text disappears while typing and is usually low contrast, so it cannot replace a label.

- **Do:** Show a persistent label above every input, linked with label for/id.
- **Do:** Use the placeholder only for an example of the expected format (for example name@example.com), or leave it empty.
- **Do:** Give any placeholder at least 4.5:1 against the field fill and set ::placeholder { color: <secondary text token>; opacity: 1 }, because some browsers fade placeholders by default.
- **Do:** Put essential instructions in helper text below the field; since a placeholder dark enough to pass can look like an entered value, put the example there too or prefix the placeholder with "e.g.".
- **Avoid:** Placeholder-only labels such as "Enter email", including a leading icon (person, lock) with a placeholder, or a placeholder that repeats the label.
- **Avoid:** Placeholder, helper, error or success text below 4.5:1.
- **Note:** A floating label resting inside an empty field is the field's only label, so it needs 4.5:1, and the floated label should stay at about 12px or larger; a static label above the field avoids both problems.

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
- **Do:** Let users type values they know instead of scrolling a long dropdown: enter a birth date as three short labeled fields (Day, Month, Year) with inputmode="numeric" and autocomplete="bday-day", "bday-month" and "bday-year", or as one field with the format in visible helper text and autocomplete="bday".
- **Do:** For phone numbers, pair a searchable country-code picker defaulted from the locale (autocomplete="tel-country-code") with a type="tel" national-number field (autocomplete="tel-national"), or use one autocomplete="tel" field that accepts a leading +; format as the user types and store the number in E.164.
- **Do:** Size fields to the answer: a single line for short values, a textarea for messages.
- **Avoid:** Email split into local part and domain boxes, or a one-line box for a long message.
- **Avoid:** Three dropdowns for a date of birth, or a date field whose only format cue is its placeholder.

## FRM-06. Choose the control by the kind of choice

**Why:** The control itself tells users whether one or many options can be chosen.

- **Do:** Use a visible radio group or segmented control for about 2-5 mutually exclusive options, and a select or combobox for long lists.
- **Do:** Use checkboxes for multi-select, a switch for on/off settings that apply immediately, and a single checkbox for yes/no choices submitted with a form.
- **Do:** Use chips for filters and tags, and labeled swatches for visual attributes such as color.
- **Avoid:** Hiding three or four short options in a dropdown, Yes/No in a dropdown, or checkboxes for mutually exclusive options.

## FRM-07. Type-to-filter for long lists

**Why:** Scrolling hundreds of items such as countries is slow; typing a few letters finds the item immediately.

- **Do:** Replace select menus longer than about 10 options (countries, time zones) with a combobox that filters as the user types and matches partial input, or put a filter field at the top of the list that takes focus when it opens.
- **Do:** Follow the ARIA combobox pattern: keep DOM focus in the input, move the highlight with arrow keys and aria-activedescendant, and let Escape close the list first and clear the text second.
- **Do:** Surface likely choices (for example the detected country) first, highlight the matched text, and announce the number of results in a polite live region.
- **Do:** Debounce lookups that call a server by about 150-250ms.
- **Avoid:** Hundreds of alphabetical options in a plain dropdown.

## FRM-08. Pair sliders with numeric inputs

**Why:** Sliders are fast for rough values but imprecise; people also need to see and type exact numbers.

- **Do:** Show the live value above the thumb or beyond the end of the track (not inside the track, where the thumb covers it), and label the minimum and maximum.
- **Do:** Increase values toward the trailing edge (right in left-to-right layouts, mirrored in right-to-left, up on vertical sliders) so the scale matches the arrow keys.
- **Do:** Pair the slider with editable number fields that stay in sync.
- **Do:** Prefer input type="range" with step (and a datalist for tick marks); give thumbs at least a 44px target and support arrow keys, Page Up/Page Down for larger jumps and Home/End.
- **Do:** Use a dual-thumb slider for ranges, name each thumb ("Minimum price", "Maximum price") and stop the thumbs from crossing.
- **Do:** In custom sliders, use setPointerCapture so dragging continues off the track, and touch-action: pan-y so vertical page scrolling still works.
- **Avoid:** A bare slider with no visible value, or a long dropdown of fixed numeric steps.

## FRM-09. Selectable tiles for a few comparable options

**Why:** When options differ by one or two key values, large tiles are easier to compare and tap than tiny radios.

- **Do:** For 2-6 options, lay out tiles with the main value bold (for example 1TB) and the secondary value below (for example the price).
- **Do:** Give unselected tiles a visible border (about 3:1 against the surface), and mark the selected tile with an accent border of 2px or more plus a round radio indicator or a check in a circle.
- **Do:** Keep radio semantics (role="radiogroup", arrow-key navigation, checked state).
- **Avoid:** Tiles for long or plain-text lists, or selection shown by a subtle color change only.
- **Avoid:** Square checkboxes on single-choice tiles, which suggest several can be chosen, or white tiles set off from a white surface only by a soft shadow.

## FRM-10. Design every field state

**Why:** Fields that change with state show users where they are and whether input is valid.

- **Do:** Define default, focused, filled, autofilled, read-only, disabled, error and success states.
- **Do:** Reserve a helper-text slot under each field so messages appear without shifting the layout.
- **Do:** Pair status colors with an icon and text, and keep success distinct from focus: mark validity with an icon and short text, and reserve border changes for focus and error.
- **Do:** Render read-only values with the readonly attribute so they stay focusable and selectable, keep their text at 4.5:1 or more, and show they cannot be edited by removing the border or tinting the fill; keep disabled styling for controls that cannot be used.
- **Do:** Style autofilled fields for each theme: browsers ignore background-color on :autofill (and :-webkit-autofill), so paint the fill with an inset box-shadow and set -webkit-text-fill-color for the text.
- **Avoid:** Disabled fields that look empty or enabled, or states shown by border color alone.
- **Avoid:** Read-only values greyed out like disabled controls, or a success border identical to the focus ring.

## FRM-11. Show specific errors inline, next to the field

**Why:** An error far from its field makes users hunt for the problem.

- **Do:** Validate a field first on blur or submit, show the message directly under the field with a red border and an error icon, and say how to fix it.
- **Do:** Once a field shows an error, re-validate on every input so the message clears as soon as the value is valid; raise new errors only at the next blur or submit.
- **Do:** Link the message with aria-describedby, set aria-invalid="true" and move focus to the first invalid field on submit.
- **Do:** Give the message text at least 4.5:1 with a darker error-text token (for example #DC2626 or darker on white); the brighter red can stay on the border and icon, which need 3:1.
- **Do:** Keep required and type for semantics but add novalidate when your script renders the inline messages, because the browser's validation bubble shows one field at a time and then disappears.
- **Do:** For new passwords, show a live checklist limited to length (at least 8 characters, or 15 when the password is the only factor) and "not a common or breached password".
- **Avoid:** A list of errors under the submit button, a generic "Error found" banner, or validating on every keystroke before the user has finished.
- **Avoid:** Flagging empty fields the user only tabbed through, or relying on the browser's built-in validation bubble.
- **Note:** Sign-in is the exception: for wrong credentials show one generic message ("Email or password is incorrect") rather than marking a field, so the form never reveals which credential was wrong or whether the account exists.

## FRM-12. Mark required and optional fields one consistent way

**Why:** Users need to know what they can skip; clutter on every label slows them down.

- **Do:** When most fields are required, mark only the exceptions with "(optional)" inside the label element, in muted text that still reaches 4.5:1 (for example #767676 or darker on white).
- **Do:** Otherwise mark required fields with an asterisk and explain it once at the top of the form.
- **Do:** Always set required or aria-required on the input.
- **Avoid:** "(required)" in red on every label, or a symbol whose meaning is never explained.

## FRM-13. Show formats with hints and gentle masks

**Why:** Showing the expected format prevents errors before they happen.

- **Do:** Show patterns such as MM/YY or DD/MM/YYYY in persistent helper text or a mask, taking the date order from the user's locale (Intl.DateTimeFormat formatToParts) instead of hard-coding one.
- **Do:** Insert separators as the user types (card numbers in groups of four separated by single spaces, or 4-6-5 for 15-digit cards) and strip them before validating.
- **Do:** Keep the caret in place when reformatting by counting the digits before it, not characters, and size the field for the longest formatted value plus any icon, with tabular digits.
- **Do:** Accept pasted values in common formats.
- **Avoid:** Blank date or phone fields with no hint, or rejecting input because separators differ.
- **Avoid:** A caret that jumps to the end after an edit in the middle, or spaced hyphens between card-number groups.
- **Note:** Masks must not block editing or confuse screen readers.

## FRM-14. Split long forms into steps with visible progress

**Why:** Short steps with a progress indicator reduce overwhelm and show how much is left.

- **Do:** Group about 3-4 related fields per step and show a stepper or progress bar.
- **Do:** End each step with a primary "Next" and a secondary "Skip" for optional steps.
- **Do:** Keep entered data when users move back or reload: put the step in the URL and keep the draft in sessionStorage, excluding card numbers, security codes, passwords and one-time codes, and clear it on submit.
- **Avoid:** Hiding how many steps remain, or splitting very short forms into many steps.
- **Avoid:** Saving payment or credential fields to localStorage or other persistent client storage.

## FRM-15. Use boxed fields, not underline-only fields

**Why:** Enclosed fields are recognized as editable and have a clear tap area.

- **Do:** Render inputs as outlined or filled boxes about 44-56px tall with a visible focus style.
- **Do:** Give the boundary that identifies the field at least 3:1 against the surface it sits on (WCAG 2.2 SC 1.4.11), in both themes: about #949494 or darker on white, about #656565 or lighter on #18181B.
- **Do:** On filled fields whose fill cannot reach 3:1 against its surface, add a border or bottom line that does.
- **Avoid:** Bare underlines that look like dividers, or fields and code cells set apart from the card only by a soft shadow.
- **Avoid:** Faint borders or fills around 1.1-1.3:1 (for example #E5E7EB on white) on inputs; keep those for decorative card edges.

## FRM-16. Give rich-text editors familiar controls

**Why:** People writing formatted content should not need markup knowledge.

- **Do:** Provide a toolbar with bold, italic, underline, lists, link and image, plus a compact floating toolbar on text selection.
- **Do:** Explain where the content will appear and end with a secondary Cancel and a primary Save.
- **Avoid:** Raw markup for basic formatting in consumer-facing editors, or equally weighted Cancel and Save buttons.

## FRM-17. Build one-time-code entry that accepts typing, paste and autofill

**Why:** Codes arrive by keyboard, clipboard and OS autofill; boxes that only handle keystrokes force people to retype.

- **Do:** Prefer one real input styled as boxes, with inputmode="numeric", autocomplete="one-time-code", pattern="[0-9]*" and maxlength equal to the code length.
- **Do:** If separate boxes are unavoidable, put autocomplete="one-time-code" on the first box only, do not cap boxes at maxlength=1, and on the input event spread any multi-digit value (autofill or paste) across the boxes before moving focus.
- **Do:** Strip non-digits in the input handler (typing, paste and autofill alike), auto-advance on each digit, step back on Backspace in an empty box, and submit automatically only when exactly the expected number of digits is present (say so in the helper text).
- **Do:** Give the group a label (role="group" or fieldset) and each separate box a name such as "Digit 2 of 6"; drive the box count from one constant used in the copy as well.
- **Do:** For 6-digit codes, a small gap between two groups of three helps checking; draw it as an aria-hidden decoration, never as an extra box, character or tab stop.
- **Do:** Optionally request SMS codes with the WebOTP API (navigator.credentials.get with otp transport "sms").
- **Avoid:** type="number" (spinners, lost leading zeros), blocked paste, or a heading that says 4 digits beside 6 boxes.
- **Avoid:** maxlength=1 or single-character guards (such as /^\d?$/) on boxes that must accept autofill, the one-time-code hint repeated on every box, or a pasted code silently truncated into a wrong one.

## FRM-18. Wire sign-in fields for password managers

**Why:** Correct field semantics let browsers and password managers fill credentials, which removes most sign-in friction.

- **Do:** Use a real form with visible labels, type="email" with autocomplete="username" (or "email"), and autocomplete="current-password" on sign-in or "new-password" on sign-up.
- **Do:** In native apps set the hints for both platforms: textContentType for iOS (username on the email field, password or newPassword) and the Android autofill hint (autoComplete), plus keyboardType="email-address", autoCapitalize="none" and secureTextEntry.
- **Do:** When one view toggles between sign-in and sign-up, switch the password autocomplete, the confirm-password field and the submit endpoint together (or render two forms), and carry the typed email across; on sign-in the browser should offer saved logins, not a generated password.
- **Do:** Put "Forgot password?" beside the password field and state the duration on any "remember me" option.
- **Avoid:** Marking a sign-in password as new-password, or bare inputs with no type, label or autocomplete.

## FRM-19. Add a show-password toggle and keep password rules visible

**Why:** Revealing what was typed reduces errors, and rules that vanish on the first keystroke cause failed submissions.

- **Do:** Make the toggle a button type="button" inside the field's trailing edge with aria-label ("Show password") and aria-pressed, swapping the input type without moving the caret.
- **Do:** Keep rules such as "8 characters or more" in persistent helper text linked with aria-describedby, and accept at least 64 characters, paste and password-manager fill.
- **Do:** If you show a strength meter, pair the color with a text label, base its tiers on a pattern-aware estimator's guess count (dictionary words, names, dates, repeats, keyboard runs) rather than length times character-set size, and debounce the label so it is not announced on every keystroke.
- **Avoid:** A non-focusable eye icon, or rules stated only in the placeholder.
- **Avoid:** Composition rules (an uppercase letter, a digit, a symbol), or a meter that rewards character classes.

## FRM-20. Collect PINs and amounts with a clear keypad and a live readout

**Why:** Money and PIN entry need large keys, a visible value and a second check for invisible typos.

- **Do:** Show the amount large and centered with any converted value beneath it, updating on each key.
- **Do:** Prefer a native input with inputmode="decimal" (amounts) or inputmode="numeric" (PINs); if a custom keypad is required, use real buttons of at least 48px with labels for symbol keys and also accept hardware keyboards.
- **Do:** Mask PINs as filling dots, use autocomplete="new-password" for creation, and follow "Create PIN" with "Confirm PIN", clearing both and explaining on mismatch.
- **Avoid:** Echoing PIN digits in plain text, or a custom keypad as the only input path.

## FRM-21. Make upload zones state their limits and track each file

**Why:** Uploads fail in many ways; stating limits up front and showing per-file status prevents surprises.

- **Do:** Show accepted types, size limit and file count in the zone, and accept drop, paste and a real file input behind a visible browse button.
- **Do:** Switch the zone's border, tint and copy together as soon as dragenter fires, call preventDefault in dragover so drop fires, and count dragenter/dragleave (or set pointer-events: none on children while dragging) so the highlight does not flicker.
- **Do:** Word the drag-over state generically ("Drop 2 files to upload"), because file names and sizes are only readable after drop; pre-check types from DataTransfer.items where the browser exposes them.
- **Do:** List each file with name, size and its own progress bar, then done or failed with a reason and an inline Retry; freeze a failed bar at its last confirmed percentage and resume from the last acknowledged chunk where the upload protocol allows.
- **Do:** Show an aggregate summary ("3 of 4 uploaded, 1 failed") with clear and per-file remove controls that have accessible names.
- **Avoid:** Drag-and-drop as the only route, silent rejection, or failed files dropped from the list.
- **Avoid:** A highlight that fades in slowly behind the pointer, or restarting a broken upload from zero when it could resume.

## FRM-22. Write settings toggles as full rows that apply immediately

**Why:** Each switch should say what it does, take effect at once and be easy to hit.

- **Do:** Build each row as a label, a one-line description and a trailing switch (role="switch" with aria-checked, or a native checkbox styled as a switch), with the whole row as the target.
- **Do:** Show the on state by knob position and fill, not color alone, and give the off-state track a fill or outline of at least 3:1 against its surface in both themes (for example a 2px mid-gray outline).
- **Do:** Flip the switch at once with a small pending indicator in the knob until the server confirms; on failure move it back, restore aria-checked and say what happened near the row.
- **Do:** Offer undo or confirmation for security-sensitive changes.
- **Do:** When a page mixes instant toggles with fields that need an explicit save, say which group applies immediately, give the rest a sticky bar with an unsaved-changes notice, Cancel and Save, and warn before leaving with unsaved edits.
- **Avoid:** Switches with no visible label, or switches whose change only applies after a separate Save.
- **Avoid:** An off-state track so pale that it disappears into a light or dark card.

## FRM-23. Prefill quick-add forms with sensible defaults

**Why:** Option rows with realistic defaults let people create an item by typing one field.

- **Do:** Put the single required field first and focused, and show the other options as rows with an icon, label, current value and chevron that open pickers.
- **Do:** Choose defaults that cover the common case and show them as real values.
- **Do:** For new calendar entries, prefill the day selected in the calendar, start at the next half hour (or a morning time on future days) and end one default duration later; when the start moves, move the end by the same amount so the range cannot invert.
- **Avoid:** Turning every option into a required step, or chevron rows that are not tappable.

## FRM-24. Make date and time pickers show context and valid ranges

**Why:** Scheduling is easier when people see the surrounding week or month and cannot pick impossible ranges.

- **Do:** Use a week strip (day name above date, selected day filled, today marked differently) for near-term dates, with arrows for other weeks and a way to open a full calendar.
- **Do:** Bind the end date's minimum to the start date, use a two-thumb slider or paired fields for time windows, and echo the choice in plain words ("3 days, Fri 7 to Mon 10").
- **Do:** Define presets such as "Last 7 days" inclusively (today and the 6 days before) and show the resolved dates.
- **Do:** For date ranges, show two months side by side on desktop, and on phones a full-screen sheet of vertically scrolling months with a range summary and a sticky Confirm.
- **Do:** Give each day a full-date accessible name and aria-selected or aria-pressed, with targets of at least 40-44px.
- **Avoid:** Return dates earlier than pick-up dates, or selected days marked by color alone.

## FRM-25. Wire payment card fields for autofill and verification

**Why:** Autofill tokens and formatting cut card-entry time and errors.

- **Do:** Use autocomplete="cc-name", "cc-number", "cc-exp" and "cc-csc" with inputmode="numeric", group the number as the user types, and use one MM / YY expiry field that matches the card.
- **Do:** Show the detected network only once the prefix is unambiguous (some networks need up to six digits), with a neutral card icon until then, and report an incomplete number only after the field loses focus.
- **Do:** Explain the security code in helper text ("3 digits on the back, 4 on the front for some cards") rather than a "***" placeholder.
- **Do:** Prefer the payment provider's hosted fields, and label the pay button with the exact amount and a short security note.
- **Do:** Mark any live card preview aria-hidden and keep it out of the tab order; under reduced motion swap to the back face instantly instead of flipping.
- **Avoid:** type="number" for card numbers, or a decorative card preview as the only place the entered data is visible.
- **Avoid:** Separate month and year dropdowns for the expiry date.

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
- **Do:** Give unchecked checkboxes and radios a 1.5-2px border of at least 3:1 against the surface, and keep the check mark at 3:1 or more against the checked fill.
- **Avoid:** Div-only sliders or drag-only knobs.
- **Avoid:** Unchecked boxes or radios drawn as a pale, borderless fill.

## FRM-28. Verify on the server and send credentials only to your own backend

**Why:** Client-side checks can be bypassed, and generic form builders are not built to receive passwords.

- **Do:** Verify one-time codes, totals and permissions on the server, and post sign-in forms to your own authentication endpoint over HTTPS.
- **Avoid:** Hard-coded codes compared in client code, or passwords collected through a third-party form embed.
