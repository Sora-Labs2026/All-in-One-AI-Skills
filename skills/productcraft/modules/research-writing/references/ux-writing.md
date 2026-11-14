# UX writing: interface copy and copy reviews

Read this when writing or reviewing the words inside a product: buttons, labels, errors, empty states, confirmations, notifications, onboarding, settings and help text. The rulebook entries are `COP-01` to `COP-14` in `../../../references/ui-rules/copy-microcopy.md`; brand voice and the tone table by context are `../../business-ops/references/brand-guidelines-and-audits.md`; persuasive copy and its limits are `../../ethical-persuasion.md`; form labels and validation behavior are `../../forms-conversion.md`; translation catalogs are `../../engineering-practices/references/i18n-catalog-sync.md`.

## Principles

1. **Clear before clever.** The reader is busy and trying to do something else.
2. **Short, but complete.** Remove words that carry nothing; keep the ones that prevent a mistake.
3. **Useful.** Every message helps the reader act: what to do, what happens next, what changed.
4. **Human.** Write as a capable colleague would speak; no system language, no blame.
5. **Honest.** No hidden costs, no pressure, no ambiguity about consequences.

**Tone follows stress.** The more anxious or blocked the reader, the plainer and calmer the words: no jokes in errors, payments, deletions, security or outages. Delight belongs in low-stakes success and empty moments, and even there it must not slow the task.

## Patterns

### Buttons and links

- Start with a verb and name the outcome: "Save changes", "Send invoice", "Download report (PDF, 2 MB)". Avoid "OK", "Submit", "Yes".
- The same action uses the same words everywhere; the button that opens a dialog and the button that confirms it match.
- Links say where they go: "View billing history", not "Click here" or "Learn more" alone (if "Learn more" is kept for space, give it an accessible name that includes the topic).
- Keep labels on one line (`COP-02`); plan for languages that run 30 to 50% longer.

### Confirmations of destructive actions

- The title asks the specific question: "Delete project 'Harbor redesign'?"
- The body says what will be lost and whether it can be undone: "Its 48 files and comments are deleted for everyone. This cannot be undone."
- The confirming button repeats the action and object: "Delete project". The other button stays "Cancel".
- For high-stakes, irreversible actions (deleting an account, a production database, all data), add a deliberate step such as typing the name, and prefer undo or a grace period over a dialog where possible (WCAG 3.3.4 for legal, financial and data submissions).

### Error messages

Formula: **what happened, why if it helps, and how to fix it**, next to the place where the fix happens.

| Instead of | Write |
|---|---|
| Invalid input | Enter a date in the format DD/MM/YYYY, for example 07/03/2026 |
| Error 403 | You don't have access to this folder. Ask its owner, Dana Ruiz, to share it with you. |
| Something went wrong | We couldn't save your changes because the connection dropped. Your edits are kept on this device; try again when you're back online. |
| Password must meet requirements | Use at least 12 characters. (Show which rules are met as the user types.) |

- Never blame ("You entered an invalid..."); describe the field and the fix.
- No codes or stack traces as the main message; put a reference code in smaller text for support when it helps.
- Keep the user's input; never clear a form because of one error.
- Connect messages to fields with `aria-describedby` and announce summaries; color is never the only signal (`../../forms-conversion.md`).

### Empty states

Say what will appear here and why it is worth it, then give the first action: "No invoices yet. Invoices you send appear here with their payment status. [Create an invoice]". Distinguish first use, no results for a filter ("No invoices match 'March' and 'Overdue'. [Clear filters]"), and cleared-out states ("All caught up"). Never a bare "No data".

### Success and status

- Confirm the outcome in the words of the action: "Invoice sent to accounts@harbor.example". Say what happens next if anything does.
- After success, relabel or move to the next step (`COP-09`).
- Status messages that appear without focus moving are announced with `role="status"` (polite).
- Loading text says what is loading when it takes long: "Importing 1,240 contacts (about a minute)".

### Notifications

- Lead with the change and who caused it: "Dana commented on 'Q3 plan'".
- Only notify for things the person would want to know now; batch the rest.
- Every notification links to the place where the person can act; settings let them turn each type off.
- Push and email subjects are specific and never bait.

### Onboarding and help text

- One idea per step; let users skip and return.
- Explain an unusual interaction in two or three words where it happens (`COP-14`).
- Help text answers the question a user has at that moment, beside the field, before they make the mistake.

### Labels and settings

- Nouns for labels, plain words for settings ("Show weekends in calendar"), with the consequence when it is not obvious ("Others in your team will see your status").
- Toggles describe the on state; avoid negative labels ("Disable notifications" off = notifications on is confusing).

## Mechanics

- Sentence case for all interface text; no all-caps labels (`COP-06`).
- Numerals for numbers ("3 files"), formatted for the reader's locale (`COP-08`).
- Contractions are fine where the voice allows; consistent person ("you" for the reader).
- Persistent labels on fields; placeholders only for examples, never as labels.
- No instructions that rely on color, shape or position alone ("click the green button on the right").
- Spell out units and abbreviations on first use or in an accessible name.

## Inclusive language

- Describe people neutrally and only when relevant; use the terms communities use for themselves.
- Gender-neutral by default ("they", "everyone", "team").
- Avoid idioms, metaphors and cultural references that do not translate; avoid violent or ableist figures of speech ("kill the process" in interfaces for general audiences, "crazy fast", "blind spot").
- Names, addresses and dates come in many shapes; do not encode one culture's format in copy or validation.

## Writing for translation

- Never build sentences by joining fragments ("You have " + n + " new " + item); use full message strings with placeholders and plural rules (ICU MessageFormat or the platform's equivalent).
- Leave room for expansion; avoid text in images.
- Give translators context: where the string appears, its maximum length, what each placeholder holds.

## Copy review checklist

Run every string through this before shipping:

1. Reads naturally aloud, in one breath where it is a label or button.
2. Actions start with a verb and name the outcome.
3. No jargon, internal names or system terms the user would not use.
4. Errors say what happened and how to fix it; no blame, no dead ends.
5. Empty states give the value and the first action.
6. Destructive confirmations name the object and repeat the action on the button.
7. Sentence case, numerals, locale formats; no all caps.
8. Labels are persistent; no color-only or position-only instructions.
9. Inclusive, translatable, no concatenated strings; within length limits.
10. Tone matches the reader's state; nothing pressures, hides a cost or fakes urgency.

For a review, deliver a redline table: location, current text, proposed text, reason (checklist number or rule ID).

## Done when

- [ ] Every string in scope passes the ten-item checklist, or the exception is noted with a reason.
- [ ] Errors follow the what-why-how pattern beside the field; empty states give value and action.
- [ ] Destructive actions have specific confirmations or undo.
- [ ] Strings are complete messages with placeholders and context notes for translators.
- [ ] A redline table records changes for review.
