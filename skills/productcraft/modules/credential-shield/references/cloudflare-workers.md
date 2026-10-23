# Cloudflare Workers and edge adapter (optional)

Apply this section only when the project actually uses Cloudflare and relevant features are available on its plan. Never assert a capability exists without verifying dashboard/config/plan state.

## Divide work across layers

- **Cloudflare WAF / Bot Management (where enabled):** high-level bot/rate controls, trusted edge connection metadata, managed challenges and analytics.
- **Workers:** apply lightweight trusted-context reads and app-owned authorization boundaries; do not authenticate a user with a fingerprint or trust public header copies of provider values.
- **Atomic state:** use a service with atomic counter semantics (e.g. Durable Objects or suitable supported managed rate-limiting service) for correctness-critical distributed budgets. Workers KV is eventually consistent, so do not treat a read-modify-write there as an atomic distributed limiter.
- **Identity:** maintain application-side and IdP-side MFA/passkeys/session protections. A WAF rule is not sufficient authentication hardening.

## Trusted context

Depending on Cloudflare products and plan, fields under `request.cf?.botManagement` may be populated with e.g. JA4 or bot signals. Guard all access; the available API and entitlements must be checked against the deployed platform. Requests bypassing Cloudflare or traffic to a public origin can defeat assumptions. Lock down origin paths where appropriate. Never trust client-supplied `cf-*` or `x-forwarded-*` substitutes if they can bypass the real edge.

```ts
// Illustrative read ONLY, not a finished Worker or a license guarantee.
// Values must come from a trusted Cloudflare request context.
function getTrustedEdgeSignals(request: Request & { cf?: { botManagement?: { ja4?: string; score?: number } } }) {
  const signals = request.cf?.botManagement;
  return {
    ja4: typeof signals?.ja4 === 'string' ? signals.ja4 : undefined,
    botScore: typeof signals?.score === 'number' ? signals.score : undefined,
  };
}
```

Do not recreate JA4 from headers. Some Cloudflare tiers do not make fields available. Validate the current product docs and actual deployment before writing policies.

## Implementation steps

1. Inventory DNS/zone/Worker routes, public origin bypass, WAF rules, request transforms, provider authentication path.
2. Check actual bot signals and managed challenges availability. Record unsupported signals explicitly.
3. Configure source rate controls with shared storage consistent with Workers execution semantics and a bounded key strategy.
4. Incorporate identifier HMAC and campaign signals in an application-side boundary. Correlate separate IPs in durable state without scanning every key on each request.
5. Verify Turnstile/challenge tokens server-side using the vendor-supported verification flow when using that product. A client widget or unchecked token is not protection.
6. Test and deploy with rules under observe-only or log-first, with feature flags and rollback instructions.

Official references:

- Cloudflare JA4/inter-request signals overview: https://blog.cloudflare.com/ja4-signals/
- Cloudflare Workers `request.cf` API: https://developers.cloudflare.com/workers/runtime-apis/request/#incomingrequestcfproperties
- Cloudflare Turnstile server-side validation: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- Cloudflare Durable Objects storage: https://developers.cloudflare.com/durable-objects/
