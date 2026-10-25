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
- **Do:** In headlines and value statements, replace genre words (unlock, supercharge, seamless, next-generation, all-in-one) with a specific noun, number or outcome; if a competitor's name could be swapped in and the line still works, rewrite it.
- **Avoid:** Team-internal feature names, single vague nouns, or the same word for two different rows.
- **Avoid:** Slogan formulas such as three one-word sentences or "Not just X, it's Y".

## COP-04. Keep confirmations short

**Why:** People skim, so brief messages are understood faster.

- **Do:** Use one or two words for routine confirmations ("Saved", "Copied") next to the relevant icon.
- **Do:** Add detail only when users need it to decide or act.
- **Avoid:** Full exclamatory sentences for simple confirmations.

## COP-05. Ship no placeholder copy

**Why:** Leftover template words are the first thing users notice and they undermine trust.

- **Do:** Search the UI and code for "Title", "Button", "Label", "Text", "Lorem ipsum" and similar strings before shipping.
- **Do:** Run a spell-checker over the UI string files in CI, and read each page's copy against that page's topic to catch text pasted from elsewhere.
- **Do:** Seed demos and fixtures with plausible names, units and dates, and totals that equal the sum of their rows.
- **Avoid:** A checkout card headed "Title" with a button labeled "Button".
- **Avoid:** Round vanity figures, or demo tables whose totals do not add up.

## COP-06. Avoid all-caps labels

**Why:** Mixed case keeps word shapes recognizable, so it reads faster and feels calmer.

- **Do:** Write labels in sentence case or title case and apply one convention across the product.
- **Do:** Keep source strings in natural case and set text-transform: none on buttons.
- **Avoid:** All-caps primary buttons or long all-caps labels.

## COP-07. Say where the code went and when it can be resent

**Why:** Naming the destination and the wait prevents duplicate requests and doubt about the address used.

- **Do:** State the code length and the masked destination ("4-digit code sent to ••• 0142") with a link to change it.
- **Do:** Keep "Resend" visibly unavailable during a cooldown with a live label ("Resend in 0:24"), using aria-disabled so it stays focusable and explains the wait (BTN-10), and enable it at zero.
- **Do:** Announce only when resend becomes available, not every second.
- **Do:** Keep the destination sentence, the resend prompt, the countdown and any security note at 4.5:1 or better even while the Resend control looks unavailable, since they are information, not the disabled control; if the code expires on a different clock from the cooldown, label each timer ("Expires in 4:59", "Resend in 0:24").
- **Avoid:** Hiding the resend option until the timer ends, or styling enabled and disabled resend identically.

## COP-08. Format numbers with the viewer's locale everywhere

**Why:** Mixed separators make amounts ambiguous (99.560 next to 14,867).

- **Do:** Format every number, currency and date through Intl with the viewer's locale (account setting or navigator.language), applied consistently within a view, including chart axes, tooltips, tables, slider readouts and their aria-valuetext.
- **Do:** Take the currency code from the data and let the currency style place the symbol and set the decimals: new Intl.NumberFormat(locale, { style: 'currency', currency: record.currency }) gives $4,500.25 for en-US, 4.500,25 € for de-DE and no decimals for JPY.
- **Do:** Use compact notation ("$164.4K", "$5.05M") for axis ticks and donut centers, letting the formatter choose K, M or B, and full precision in tooltips and details.
- **Do:** Write dates with a named month through Intl.DateTimeFormat (for example { day: 'numeric', month: 'short', year: 'numeric' }), or as ISO 8601 (2025-12-05) in technical contexts, and pick plural nouns with Intl.PluralRules ("1 step", "18,839 steps").
- **Avoid:** Hand-built number strings, toFixed() for money, mixed decimal marks, or currency symbols on some values but not others.
- **Avoid:** A hard-coded locale, numeric-only dates such as 05-12-2025, or K or M appended to an already grouped number ("$5,050K").

## COP-09. After success, relabel with the outcome or the next step

**Why:** A button that still says "Send" after sending invites a second click.

- **Do:** Switch to a past-tense confirmation ("Sent", "Added", "Downloaded") with a check, or to the obvious next action ("Open file").
- **Do:** Make the confirmation visually quieter than the original call to action.
- **Avoid:** Leaving the original verb in place after success.

## COP-10. Translate raw numbers into consequences

**Why:** People act on outcomes ("safe for 2 hours") more than on units ("91 dB").

- **Do:** Pair a technical value with a plain-language consequence and a status word (Quiet, Loud, Danger), computed from a documented model.
- **Do:** Name the model in the interface; for sound exposure, the NIOSH limit allows 85 dBA for 8 hours and halves the time for every 3 dB above it (about 38 minutes at 96 dB), with no limit shown below 85 dB.
- **Avoid:** The raw number alone, or alarmist copy the model does not support.

## COP-11. State offer conditions up front

**Why:** Deals feel trustworthy when dates and limits are visible before the click.

- **Do:** Show the discount with a one-line benefit, its validity dates or channel limits, and a link to the terms.
- **Do:** Show the original price struck through (s or del) beside the new one and the saving.
- **Avoid:** Conditions hidden in fine print after the click, or "limited time" claims that keep reappearing.

## COP-12. Make trust and data-safety statements specific

**Why:** In finance and data products, concrete statements about access and control build trust before people connect accounts.

- **Do:** Use a few short cards, each with an icon, a 2-3 word title and one specific sentence (for example read-only access, encrypted connections, how to disconnect).
- **Do:** Place them next to the step that asks for access.
- **Avoid:** Vague security claims, or low-contrast gray body text in those cards.

## COP-13. Show ratings with their scale and sample size

**Why:** A bare star count is not believable; scale and count are.

- **Do:** Show the rating with its scale (4.9/5) and a real count of reviews or users, and link to the reviews.
- **Do:** Give outcome percentages and averages their base nearby: how many people, and when ("92% of 1,240 members surveyed in 2025").
- **Do:** Compute the average from the actual distribution and round it to one decimal the same way wherever it appears.
- **Avoid:** Ratings with no scale or count, percentages with no base or date, or invented figures; drop any claim you cannot back up.

## COP-14. Explain unusual interactions in two or three words

**Why:** When a control is not a standard button, a tiny instruction prevents confusion.

- **Do:** Place a short, quiet instruction beside the affordance ("Pull and release", "Hold to confirm") and provide a click or keyboard alternative.
- **Avoid:** Relying on users to discover a gesture with no hint.
