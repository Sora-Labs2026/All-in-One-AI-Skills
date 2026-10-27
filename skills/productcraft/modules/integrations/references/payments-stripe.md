# Payments with Stripe

Read this when code takes payments, runs subscriptions, issues refunds or pays out to others through Stripe. The checkout and payment UI (honest pending states, error recovery) is in `../../forms-conversion.md`; the pre-launch review of payment entitlements is LaunchGuard's payments playbook in `../../launchguard/references/stack-playbooks.md`. Other payment providers follow the same shape; their key types, signature schemes and event names differ, so check their documentation.

Stripe's API is versioned by date and its SDKs change between majors. Read the installed SDK version and the pinned API version before writing code, and check names against the current docs.

## Choose the integration

| Need | Use | Trade-off |
|---|---|---|
| One-time payments or subscriptions with the least code | Checkout (hosted page or embedded) | Stripe handles cards, wallets, 3-D Secure, many local methods and tax collection; less control over the UI |
| Payment form inside your own page | Payment Element with PaymentIntents (or Checkout Sessions in a custom UI mode) | More code: you own confirmation, redirects and the states in between |
| Selling without building anything | Payment Links | Fulfillment still needs webhooks |
| Self-service plan changes, cancellations and card updates | Billing customer portal | Configure which actions are allowed in the dashboard |
| A marketplace or platform paying out to sellers | Connect | Business decisions first: merchant of record, fees, refunds and disputes liability |

Do not start new work on the legacy Charges API or Sources; PaymentIntents and Checkout handle Strong Customer Authentication.

## Setup

- **Packages:** the server SDK for your language (`stripe` on npm and PyPI) and, in the browser, `@stripe/stripe-js` (plus `@stripe/react-stripe-js` for React). Stripe.js must load from `js.stripe.com`; do not bundle or self-host it.
- **Keys:** publishable keys (`pk_test_`, `pk_live_`) may ship to clients; secret keys (`sk_`) stay on the server; restricted keys (`rk_`) give a service only the permissions it needs; each webhook endpoint has its own signing secret (`whsec_`). Test mode and live mode are separate: objects, prices, customers and webhook secrets do not cross.
- **Pin the API version** in the client constructor so a dashboard change does not alter responses under you. Webhook endpoints carry their own API version; upgrade them deliberately.
- **Configuration:** `.env.example` holds placeholders such as `STRIPE_SECRET_KEY=sk_test_REPLACE_ME`. The user enters real values (`../../agent-safety/references/guided-setup.md`).

## Money and prices

- Amounts are integers in the currency's smallest unit. Zero-decimal currencies (JPY, KRW) take the whole amount; a few currencies have three decimals. Check Stripe's currency list instead of assuming two decimals.
- Define prices in Stripe (Price objects, ideally found by `lookup_key`) or in server configuration. The client sends a product or plan identifier and a validated quantity, never an amount.
- Use Stripe Tax or a tax service; do not hand-roll VAT or sales tax rules.

## One-time payments with Checkout

```ts
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!); // also pass apiVersion: the version this code targets

export async function startCheckout(userId: string, orderId: string, lookupKey: string) {
  const { data } = await stripe.prices.list({ lookup_keys: [lookupKey], active: true, limit: 1 });
  if (data.length === 0) throw new Error("Unknown price");
  return stripe.checkout.sessions.create(
    {
      mode: "payment",
      line_items: [{ price: data[0].id, quantity: 1 }],
      client_reference_id: orderId,
      metadata: { orderId, userId },
      success_url: `${process.env.APP_URL}/orders/${orderId}?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${process.env.APP_URL}/cart`,
    },
    { idempotencyKey: `order_${orderId}:checkout` },
  );
}
```

**Fulfillment** runs in one idempotent function, called from the webhook and again from the success page:

1. On `checkout.session.completed`, retrieve the session (expand line items if needed) and check that `client_reference_id` and metadata match an order you created for that user.
2. If `payment_status` is `paid`, move the order from `pending` to `paid` with a guarded update (`UPDATE orders SET status='paid' WHERE id=$1 AND status='pending'`) and grant access only when that update changed a row.
3. If it is `unpaid` (bank debits and other delayed methods), wait for `checkout.session.async_payment_succeeded` or `checkout.session.async_payment_failed`.
4. The success page shows *pending* until the order is `paid`; it never grants access on its own evidence.

## Custom UI with PaymentIntents

- Create the PaymentIntent on the server with the server-computed amount, `automatic_payment_methods: { enabled: true }`, your order ID in metadata and an idempotency key. Return its `client_secret` only to the session that owns the order.
- Confirm in the browser with the Payment Element (`stripe.confirmPayment`); Stripe.js runs 3-D Secure when the bank asks for it.
- The final state comes from `payment_intent.succeeded`, `payment_intent.payment_failed` and the `processing` status for slow methods, delivered by webhook. The browser's result is a hint for the UI only.
- Saving a card for later uses a SetupIntent or `setup_future_usage`. Off-session charges can still be declined with `authentication_required`; bring the customer back on-session to authenticate.

## Subscriptions

- **Customer:** create one Stripe Customer per user, once (idempotency key such as `user_8412:customer`), and store its ID. Creating a customer per checkout leads to duplicates and lost payment methods.
- **Mirror the subscription** in your database: ID, status, price, current period end, `cancel_at_period_end`. Derive entitlements from that row, not from a separate flag set at checkout.
- **Status policy** (write it down with the owner): `active` and `trialing` grant access; `past_due` keeps access for a stated grace period; `canceled`, `unpaid` and `incomplete_expired` remove it; `incomplete` means the first payment still needs action.
- **Events to handle:** `checkout.session.completed` (subscription mode), `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`, and `customer.subscription.trial_will_end` if you notify before trials end.
- **Plan changes** prorate by default; decide the proration behavior explicitly. Let the customer portal handle cancellations and card updates and react to the resulting events.
- **Test time-based behavior** (renewals, trial ends, failed renewals) with test clocks instead of waiting.

## Refunds and disputes

- Refunds go through the API with an idempotency key; react to refund and `charge.refunded` events to adjust entitlements according to the owner's policy.
- `charge.dispute.created` starts a deadline for evidence. Whether to revoke access during a dispute is a business decision for the owner.
- In live mode, never create refunds, cancel subscriptions or change prices without explicit approval (`../../launchguard/references/safe-operations.md`).

## Connect

- Decide with the owner before coding: merchant of record, who pays Stripe fees, who absorbs refunds and disputes, and the charge type (direct charges on the connected account, destination charges, or separate charges and transfers).
- Onboard connected accounts through Stripe-hosted onboarding or embedded components, and route money only to accounts whose capabilities are enabled; listen for `account.updated`.
- Events from connected accounts arrive at a Connect webhook endpoint and carry the account ID; verify them and route by account. Calls made on behalf of an account pass its ID explicitly.

## Local development and tests

- The user signs in to the Stripe CLI. `stripe listen --forward-to localhost:3000/api/webhooks/stripe` forwards test events and prints a local signing secret; `stripe trigger <event>` fires events.
- Documented test cards: `4242 4242 4242 4242` succeeds, `4000 0025 0000 3155` requires 3-D Secure, `4000 0000 0000 0002` is a generic decline, `4000 0000 0000 9995` declines for insufficient funds. Any future expiry and any CVC work.
- Unit-test fulfillment with a fake Stripe adapter and signed webhook fixtures (`webhooks.md`). Stripe's open-source mock server (`stripe-mock`) helps adapter tests that need realistic responses.

## Security and compliance

- Checkout, Elements and Stripe.js keep raw card data off your servers, which keeps PCI DSS scope small; confirm the applicable self-assessment with Stripe's integration guide. Never accept card numbers in your own inputs.
- The Content Security Policy must allow Stripe's scripts and frames; a copied strict policy breaks payments (LaunchGuard baseline).
- Webhook payloads contain names, emails and addresses. Do not log them whole.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Amount or price ID taken from the client | Server resolves the price from a product or lookup key |
| Access granted on the success redirect only | Idempotent fulfillment from the verified webhook, reused by the success page |
| Delayed payment methods treated as failures or successes | Handle `processing`, `unpaid` sessions and the async events |
| Both `checkout.session.completed` and `payment_intent.succeeded` grant access | One guarded state transition; the second event becomes a no-op |
| Price IDs hard-coded, different between test and live | Lookup keys or per-environment configuration |
| Subscription `incomplete` ignored | Prompt the customer to finish authentication; do not grant access |
| Floating-point money | Integer minor units plus currency code |

## Done when

- [ ] Amounts, prices and quantities are decided on the server; the client cannot change what is charged (tested).
- [ ] Fulfillment and entitlements change only through verified, deduplicated webhooks and one guarded transition; a duplicate event grants nothing extra (tested).
- [ ] Every create, refund and customer creation carries an idempotency key.
- [ ] Test mode flows pass: success, 3-D Secure, decline, delayed method, and for subscriptions a renewal and a failed renewal on a test clock.
- [ ] The API version is pinned and the go-live steps (live keys, live webhook endpoint and secret, portal configuration) are listed for the owner.
