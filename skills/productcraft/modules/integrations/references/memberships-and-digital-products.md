# Membership, digital-product and metered platforms

Read this when an app sells or gates access through a membership, course, community or digital-product platform (hosted checkout, memberships, license keys, apps embedded in the platform), or consumes an API priced per call or per credit. Payments through Stripe directly are in `payments-stripe.md`; the shared webhook and reliability rules are in `webhooks.md` and `reliability-and-testing.md`.

These platforms differ in names and endpoints but share a shape: products have plans or prices; a purchase creates a membership with a status and a period; license keys and course access hang off the membership; webhooks announce changes. Many act as merchant of record (they collect tax and handle payments), which changes who issues refunds and what your legal pages must say. Confirm that with the owner first.

## Keep your own entitlements

- Store an `entitlements` row per user and product: status, valid-until, source (platform and membership ID), and the timestamp or version of the last event applied.
- Change it only from verified webhooks (activated, renewed, payment failed, canceled, refunded, disputed) and from a scheduled reconciliation that lists memberships at the platform.
- Read access from your table. It is fast, it keeps working during a platform outage, and it is the one place to change the policy.
- Link the buyer to your user at checkout: pass your user ID in the checkout's metadata and read it back from the verified event. Matching by email is a fallback that needs confirmation, since people buy with a different address. Never accept a user ID from the browser after checkout.
- Write the status policy down with the owner:

| Platform state | Typical policy |
|---|---|
| Active, trialing | Grant |
| Payment failed, past due | Keep access for a stated grace period, then revoke |
| Canceled at period end | Keep access until valid-until |
| Expired, refunded, charged back | Revoke now |

## Gate access on the server

- Check the entitlement in every server path that serves protected content: route handlers, API endpoints, file downloads and video URL signing. A client-side redirect is a convenience, not a gate.
- Serve paid files and media through short-lived signed URLs. Premium content at a guessable public URL is free content.
- Cache checks briefly and invalidate the cache when an event changes the entitlement.

## License keys

- Validate on a server: yours, or the platform's validation endpoint, over HTTPS with the key in the request body or a header. Keys in URL query strings end up in access logs, proxies and browser history.
- Rate-limit validation per key and per client IP, and rely on platform-generated high-entropy keys.
- Enforce activation limits if the product has them, and support deactivation so customers can move machines.
- For offline use, cache a validation result *signed by your server* (an asymmetric signature verified with a public key embedded in the app) with an expiry. A local "licensed = true" flag is trivially edited.
- Never embed a platform secret key in a distributed app, plugin, extension or mobile build; anything shipped can be extracted.

## Platform keys and embedded apps

- Account-level keys act on the whole business; app keys act for installations of your app; OAuth tokens act for one user. Use the least powerful that works, and per-installation credentials for anything multi-tenant (`oauth-and-tokens.md`).
- Apps rendered inside the platform's interface receive a platform-issued user token or signed request. Verify it on your server for every request; never trust user or company IDs in query parameters.

## Webhooks from these platforms

- Verify signatures over the raw body with a constant-time comparison (example code that compares digests with `!==` or `==` is common and wrong), check the timestamp when one is sent, and dedupe by event ID (`webhooks.md`).
- Events for one membership can arrive out of order; apply only events newer than the stored version, or re-fetch the membership and apply its current state.
- Payloads can be partial or change shape between API versions; fetch the membership before granting or revoking.

## Cancellations, refunds and disputes

- Apply the owner's policy promptly, record the reason, and tell the customer what changed.
- Refunds and cancellations through the API move money or remove access; in live mode they need explicit approval (`../../launchguard/references/safe-operations.md`).
- Consumer rules apply to subscriptions and digital content: easy cancellation, clear renewal terms, withdrawal rights in some regions. See `../../legal-ready/GUIDE.md` and `../../ethical-persuasion.md`.

## Metered and credit-priced APIs

Data APIs often charge per call or per credit and enforce a rate limit on top.

- **Know the meter before building:** price per call, what counts (each page of a paginated list, retries, failed calls), free tier, rate limit, and the owner's monthly cap.
- **Spend less:** cache results for as long as the provider's terms allow, coalesce identical in-flight requests, batch where offered, and never call on every page view what could be refreshed on a schedule.
- **Cap spend:** read the provider's usage or balance endpoint from monitoring, alert at thresholds, and stop calling (a circuit breaker with a clear error) at the cap instead of running up a bill.
- **Retry less:** transient errors only; a validation error retried ten times costs ten calls.
- **Bound user-driven fan-out:** a feature that lets any user trigger "fetch everything for this address or account" needs per-user quotas.
- **Read the data terms:** caching limits, redistribution, attribution and commercial-use conditions.

## Testing

- Use the platform's test mode or sandbox where it exists; otherwise a zero-priced test product in a separate test store, never the live catalog.
- Cover with fakes and signed fixtures: purchase grants access; renewal extends it; failed payment enters grace then revokes; refund and chargeback revoke; duplicate and out-of-order events change nothing extra; a platform outage leaves access as the policy says.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Access decided by calling the platform on every request | Local entitlements updated by events and reconciliation |
| Buyer matched to a user by a browser-supplied ID | Your user ID in checkout metadata, read from the verified event |
| License key in the URL or a platform secret in the shipped app | Body or header to a server; no secrets in distributed builds |
| Digest compared with `==` | Constant-time comparison |
| Metered API called without a cap | Usage alerts and a hard stop at the owner's limit |

## Done when

- [ ] Entitlements live in your database, change only through verified, deduplicated events and reconciliation, and follow a written status policy (tested for grant, renew, grace, revoke and out-of-order events).
- [ ] Every protected path checks entitlements on the server; paid media uses signed URLs.
- [ ] License validation keeps keys out of URLs, is rate-limited and works offline only through signed, expiring results.
- [ ] Metered APIs have caching, a spend cap and usage alerts agreed with the owner.
