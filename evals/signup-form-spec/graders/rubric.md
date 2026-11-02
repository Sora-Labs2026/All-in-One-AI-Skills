---
type: llm
weight: 2
---
PASS only if the answer does all of the following:
- Uses visible labels, not placeholder-only labels.
- Validates on blur or on submit, not with errors shown on every keystroke while the user is still typing.
- Writes specific error messages and ties them to their fields (for example with `aria-describedby` or `aria-invalid`).
- Gives the password a show or hide control and length-based rules, not arbitrary composition rules.
- Keeps the user's input after a failed submit and shows a loading state that prevents double submission.
FAIL if it recommends placeholder text as the only label, or errors that fire while the user types the first characters.
