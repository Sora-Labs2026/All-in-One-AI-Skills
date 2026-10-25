# Legal Ready | Launch Readiness Report

> Date: [YYYY-MM-DD] | Repository: [name] | Revision: [short commit or working tree] | Prepared by: [agent] | Environment checked: [local/staging]
>
> Markets: [from the owner, e.g. EU, UK, US-CA] | Audience: [consumers/businesses; adults/mixed/children, from the owner]
>
> **General guidance, not legal advice.** This report records engineering evidence for common consumer, privacy, marketing and accessibility obligations. It does not establish compliance with any law. A qualified lawyer must review it, and the policies and flows it describes, before launch.

## Result

**Recommendation:** [READY FOR LEGAL REVIEW / READY FOR LEGAL REVIEW WITH BLOCKERS / NOT READY]

[2-5 sentences: what was checked, the main blockers, what could not be verified.]

## Facts supplied by the owner

| Fact | Value or status | Source |
|---|---|---|
| Legal entity and address | [value / `[[LEGAL: ...]]` open] | [who supplied it, when] |
| Markets and audience age | | |
| Products, billing model, refunds | | |
| Marketing channels (email, SMS, push) | | |
| Processors and transfer mechanisms | | |
| Retention periods | | |

## The 20 items

Status: PASS / FAIL / NEEDS_REVIEW / NOT_APPLICABLE (reason) / NOT_VERIFIED (reason). A PASS needs inspected code, an executed test or a recorded runtime capture. Scanner output alone is never a PASS.

| # | Item | Status | Evidence (files, tests, captures) | Gaps and next step |
|---|---|---|---|---|
| 1 | Privacy policy | | | |
| 2 | Terms of service | | | |
| 3 | Refund and cancellation policy | | | |
| 4 | Cookie policy | | | |
| 5 | Cookie consent banner (prior consent, equal reject, no pre-ticks, records, GPC) | | | |
| 6 | Form consents | | | |
| 7 | Collect only necessary data | | | |
| 8 | Third-party SDK, pixel and script audit | | | |
| 9 | Dark patterns removed | | | |
| 10 | No hidden fees | | | |
| 11 | No fake reviews or testimonials | | | |
| 12 | No unsupported claims | | | |
| 13 | Alt text | | | |
| 14 | Colour contrast | | | |
| 15 | Keyboard navigation | | | |
| 16 | Business and contact details | | | |
| 17 | Parental consent for children's data | | | |
| 18 | Unsubscribe link and one-click headers | | | |
| 19 | Asset licences | | | |
| 20 | Data deletion, access and export | | | |

## Runtime captures

| Capture | Environment and region | Non-essential requests or storage seen | File |
|---|---|---|---|
| First load, no click | | | |
| After "Reject all" | | | |
| After "Accept all" | | | |
| With GPC enabled | | | |
| Mobile test session | | | |

## Flow step counts (item 9)

| Flow | Steps | Compared with signup |
|---|---|---|
| Signup | | - |
| Cancel subscription | | |
| Delete account | | |
| Unsubscribe | | |

## Scanner run

- Command: `python3 <productcraft>/modules/legal-ready/scripts/legal_scan.py --root . --json-out legal/legal-scan.json`
- Result: [PASS n / NEEDS_REVIEW n / NOT_FOUND n]; each NEEDS_REVIEW and NOT_FOUND resolved or carried into the table above.
- Limits: source signals only; hosted pages, email-provider templates, tag containers and runtime behaviour were checked separately as recorded above, or are listed as NOT_VERIFIED.

## Open placeholders (launch blockers)

| Placeholder | File and line | Owner | Needed by |
|---|---|---|---|
| `[[LEGAL: ...]]` | | | |

## Questions for the lawyer

1. [From `references/laws-and-standards.md`, plus anything specific found here]

## Changes and tests

- Files changed:
- Tests added or run, with results:
- Not run, and why:
- Related checks in other modules (LaunchGuard controls, accessibility checks):
