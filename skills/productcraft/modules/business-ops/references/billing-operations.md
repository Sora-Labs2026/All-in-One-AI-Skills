# Billing operations: customer billing cases, revenue facts and reconciliation

Read this when the task is operating billing, not building it: a customer says they were charged twice, cannot cancel or wants a refund; someone asks for revenue, subscription or refund figures; pricing or "per seat" claims need checking against what the product enforces; or invoices, payments, payouts and the ledger must be reconciled. Building payment flows, webhooks and entitlements is `../../integrations/references/payments-stripe.md`; filing invoices and receipts is `../../creative-media/references/invoices-and-receipts.md`; refund and cancellation pages are `../../legal-ready/references/policies-and-consent.md`. Figures and treatment here are general information, not accounting or tax advice.

## Ground rules

- **Read before you write.** Inspect the customer's billing state in full before any refund, cancellation, credit or plan change.
- **Live actions need explicit approval.** Refunds, cancellations, credits, price changes and dunning settings in live mode are executed only after the owner approves the exact action and amount (`../../launchguard/references/safe-operations.md`). Prefer test mode or a draft to show what would happen.
- **Least data in the answer.** Never show secret keys or full card data; mask emails and identifiers in shared reports unless the reader needs them.
- **Say how fresh the numbers are.** Label figures as live (with the time of the query) or a snapshot (with its timestamp and source).
- **Classify before acting.** A refund is one possible outcome, not the default.

## Customer billing cases

### 1. Identify the account

Start from the strongest identifier: provider customer ID, subscription or invoice ID, then email. Summarise: customer, active and cancelled subscriptions, recent invoices and payments, refunds, disputes, and anomalies (two active subscriptions for one person, a seat count that does not match usage).

### 2. Classify

| Case | Evidence that distinguishes it | Usual remedy |
|---|---|---|
| Accidental duplicate purchase | Two subscriptions minutes apart, same user, second never used | Cancel the duplicate, refund its charge |
| Deliberate team or multi-seat purchase | Seats assigned to different people, or the buyer says so | Keep it; explain the billing model; consider moving to organisation billing |
| Failed or incomplete checkout | Payment requires authentication, card declined, `incomplete` status | Send the customer to finish or update the payment method; no refund needed |
| Missing self-serve control | Customer could not find how to cancel, change plan or get an invoice | Give the portal link or cancel as requested; log the product gap |
| Product failure or unmet promise | Outage, a feature missing that was advertised, a support failure | Refund or credit per the owner's policy; log the product issue |
| Dispute (chargeback) opened | A dispute object on the charge | Do not also refund the charge: the dispute already reversed the funds. Accept it or submit evidence before the deadline |

### 3. Take the safest reversible action first

1. Restore self-service (portal, cancellation, invoice access).
2. Fix the broken state (cancel the duplicate, correct the seat count).
3. Refund only the affected charge, with an idempotency key and a reason recorded.
4. Write a short, plain follow-up to the customer stating what was done, the amount and when it will appear.
5. Log the product or website gap separately from the support case.

### 4. Handoff format

```text
CUSTOMER      identifiers (masked) and plan
STATE         subscriptions, invoices, anomalies, data time
DIAGNOSIS     case type and the evidence for it
ACTION        proposed or approved action, amount, reversibility
MESSAGE       draft reply to the customer
PRODUCT GAP   what should change so this does not recur
```

## Failed payments and dunning

- Distinguish soft declines (insufficient funds, temporary issues: retry on a schedule) from hard declines (stolen card, closed account: stop retrying, ask for a new method) and authentication requests (the customer must complete them on-session).
- Tell customers before access changes, with a link to update the payment method; keep the grace period and access rules written down with the owner (see the status policy in the Stripe reference).
- Measure recovery from retries and from reminder emails separately so changes can be judged.

## Revenue facts

Define every metric before quoting it and keep the definition with the number:

| Metric | Define |
|---|---|
| Gross sales | Paid charges in the period, before refunds, disputes and fees, excluding failed and incomplete attempts |
| Net revenue | Gross minus refunds and lost disputes; state whether provider fees and taxes are excluded |
| Monthly recurring revenue (MRR) | Active recurring subscriptions normalised to a month (annual / 12), excluding one-time charges and taxes; state the treatment of discounts, trials, paused and past-due subscriptions |
| Churn | Customer or revenue churn, gross or net of expansion, over a stated period and cohort |

Common errors: counting failed attempts as sales, counting a duplicate subscription as two customers, mixing currencies without a dated exchange rate, and mixing test-mode data with live data. Revenue recognition for accounts (deferred revenue on annual plans) follows the company's accounting policy; leave it to the accountant.

## Checking what the product actually enforces

When pricing pages, sales copy or support answers describe billing behaviour ("per seat", "team plan", "usage limits", "cancel anytime"), verify it in code and data before repeating it:

- Find the entitlement path: how checkout quantity becomes seats or quota, where limits are checked, what happens on downgrade and cancellation.
- Compare with what the website says. A claim the code does not enforce is a misleading claim (`../../legal-ready/references/honest-commerce.md`) and a source of refund requests.
- Report three things separately: the revenue fact, the customer impact, and the code-backed product truth, then the recommendation.

## Reconciliation

Money moves through several records that must agree: invoices (what was billed), charges and refunds (what moved at the provider), payouts (what reached the bank, net of fees, refunds and dispute amounts) and the ledger (what the accounts say).

1. Export each source for the same period and time zone, with amounts in integer minor units and currency codes.
2. Match on stable identifiers (invoice ID, charge ID, payout ID), not on amounts or dates alone.
3. Explain every difference: timing (a charge on the 31st paid out on the 2nd), fees, refunds and disputes netted from payouts, currency conversion, partial payments, credit notes, and manual entries.
4. List unmatched items on both sides with their age; never force a match by adjusting amounts.
5. Keep the reconciliation as a repeatable script or spreadsheet with the inputs' timestamps, so the next period is the same procedure.

## Checks (done when)

- [ ] The billing state was read in full and the case classified with evidence before any action.
- [ ] Every live refund, cancellation or credit had the owner's approval of the exact action and amount, and an idempotency key.
- [ ] Figures carry their definition, currency and data time; live and snapshot data are not mixed.
- [ ] Billing claims on the website were checked against the entitlement code.
- [ ] Reconciliation differences are explained or listed as open items; nothing was forced to match.
