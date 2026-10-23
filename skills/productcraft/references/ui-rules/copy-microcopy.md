# UI rules: Copy and microcopy

Button labels, plain language, confirmations and casing. Rule IDs use the `COP-` prefix; cite them in change reports.

## COP-01. Label buttons with the outcome

**Why:** A verb that names the result tells users exactly what will happen.

- **Do:** Use verb plus object: "Save changes", "Add to basket", "Delete project", "Pay $12.96".
- **Do:** Keep the label consistent with the screen title and the confirmation message.
- **Avoid:** "Yes", "No", "OK", "Submit" or "Done" when a specific verb exists, or a bare noun as a label.

## COP-02. Keep button labels on one line

**Why:** Wrapped button text looks broken and gets worse on small screens and in translation.

- **Do:** Write labels of 1-3 words and test at the narrowest supported width (320px) and in long languages.
- **Do:** Shorten the copy or let the button go full width instead of wrapping.
- **Avoid:** Labels that break onto two lines, or shrinking the font below the standard button size.

## COP-03. Write labels in plain language

**Why:** Internal or marketing jargon confuses users who have never seen those terms.

- **Do:** Name settings by their effect ("Hide balances", "Help and support"), and be specific with legal links ("Privacy policy", "Terms and conditions").
- **Do:** Use standard wording for account actions: "Log out", "Close account".
- **Do:** Phrase toggle labels as the state that turning them on produces.
- **Avoid:** Team-internal feature names, single vague nouns, or the same word for two different rows.

## COP-04. Keep confirmations short

**Why:** People skim, so brief messages are understood faster.

- **Do:** Use one or two words for routine confirmations ("Saved", "Copied") next to the relevant icon.
- **Do:** Add detail only when users need it to decide or act.
- **Avoid:** Full exclamatory sentences for simple confirmations.

## COP-05. Ship no placeholder copy

**Why:** Leftover template words are the first thing users notice and they undermine trust.

- **Do:** Search the UI and code for "Title", "Button", "Label", "Text", "Lorem ipsum" and similar strings before shipping.
- **Do:** Use realistic sample data in demos and empty fixtures.
- **Avoid:** A checkout card headed "Title" with a button labeled "Button".

## COP-06. Avoid all-caps labels

**Why:** Mixed case keeps word shapes recognizable, so it reads faster and feels calmer.

- **Do:** Write labels in sentence case or title case and apply one convention across the product.
- **Do:** Keep source strings in natural case and set text-transform: none on buttons.
- **Avoid:** All-caps primary buttons or long all-caps labels.
