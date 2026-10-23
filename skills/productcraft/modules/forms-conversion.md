# Forms, onboarding, authentication UI, search and checkout

Related patterns in `../references/pattern-library.md`: 9, 24, 26-28, 30, 33, 35-36, 40, 58, 65, 67. For actual login abuse architecture, **also read** `credential-shield/GUIDE.md`. For payments/PII launch security, **also read** `launchguard/GUIDE.md`.

## Forms

- Persistent labels, examples and expected formats. A placeholder is not the label. Do not erase helpful constraints or a typed value when validation fails.
- Validate where helpful: after relevant blur/submit or after enough entry, not every character. Reserve space for inline errors and positive confirmations to keep the submit button stable.
- Preserve codes, OTPs, postal codes and numeric IDs as **strings**; `inputmode` can summon a numeric keypad without losing leading zeroes. Accept full-code paste and platform autofill where supported.
- Passwords: favor length and safe handling, password-manager paste, breached-password validation if supported; don't claim exact crack times based on simplistic heuristic.
- Keep user input when navigating multi-step forms; make steps meaningful, state clearly what remains, return without data loss. Long checkout needs transparent totals and any terms **before** commitment.
- Calendar date ranges need cross-month selection, locale formatting and timezone correctness; show presets only when they save common tasks.
- Search: descriptive prompts, relevant autocomplete, keyboard controls, filter transparency and useful zero-results recovery. Avoid fake popularity rankings.
- Uploads: per-file status, resilient retries, clear errors and an accessible browse button; enforce backend rules and safe storage.

## Checkout/payment constraints

- Payment gateway's certified/tokenized inputs handle PAN/CVC; application must not store raw card data. Server recomputes amounts and validates product/discount/ownership. Verify signatures, idempotency and settlement before access. A UI can show pending, never fake paid status.
- Ethical conversion: reduce unnecessary fields, state price/recurrence and restrictions, provide a clear path to cancel. Do not hide default add-ons, insert fake urgency, or trick users into consent. Read `ethical-persuasion.md`.

## Verification

Test autofill and copy-paste; wrong/expired code, repeated submit, slow responses, keyboard/focus, long name/locales, screen readers, validation timing, failed payment and recovery, third-party rejection, rate limits on OTP/resend and lookup.
