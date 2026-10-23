# Authentication architecture and threat model

## Discovery map

Capture relevant source file paths, auth provider, data store, deployments, and current controls. For each endpoint record:

| Endpoint or flow | Own/hosted | Expensive operation | Known pre-auth controls | Correlation possible? | Verification gap |
|---|---|---|---|---|---|
| Password login | | password hash / provider request | | | |
| Login via API or mobile | | provider / password hash | | | |
| Login via SSO | | redirect/token exchange | | | |
| Reset / recovery | | email / token / DB | | | |
| OTP / MFA | | code / factor verification | | | |
| Registration | | account creation / email | | | |
| Passkey sign-in / enrollment | | cryptographic assertion | | | |

Not all providers permit app-defined pre-password checks or expose failure details. For hosted login, apply supported IdP features (bot detection, risk-based auth, brute-force protection, breached password protection, MFA), edge policies on owned entry points, and external metrics. Do not insert an interceptor only into the callback and claim to control the provider-hosted credential form.

## Trust boundaries

- **Public client:** user-agent, browser hints, display locale, self-reported device ID, arbitrary headers, form identifiers. Can be forged.
- **Trusted edge:** connection metadata, JA3/JA4 where supported, bot score, true remote address. Trust only through authenticated or privately networked ingress where public clients cannot inject/look-alike headers. Confirm verified integration.
- **Application server:** account normalization and secret HMAC keys, risk decision, challenge verification, credentials/IdP calls, audit events.
- **Atomic state:** shared store for distributed counters and windows. Verify consistency, backpressure, TTL, max key cardinality, time alignment, and partial outages.
- **Identity provider / auth store:** password verification, sessions, MFA/passkeys. Keep same binding and ordering across alternative auth flows.
- **Observability:** no password, OTP, bearer/session token, reset secret or raw form body. Minimize PII and retention; restrict access.

## Important attacker goals

1. Test breached username/password pairs from many low-volume IPs.
2. Password spray across many usernames while staying below per-IP limits.
3. Trigger massive password-hash work to degrade authentication availability.
4. Forge IP headers, UA, client fingerprints, challenge passes, or familiar-device flags.
5. Force soft/hard lockouts of legitimate users or exhaust counter-store cardinality.
6. Exploit recovery, mobile, old endpoints, or alternative login paths to bypass protections.

## Defense ordering

**Cheap controls:** configured WAF/proxy restrictions, malformed request rejection, admission queues, per-identifier HMAC counters, bounded shared source counters, trusted-edge risk indicators, verified challenge decisions.

**Expensive controls:** hash verification/IdP calls, additional authentication, e-mail/SMS sends, risk-provider lookups. Cache only privacy-safe metadata and honor token validity. Never cache password verification outcomes or use a bot score as a login factor.

## Alternatives based on stack

- **Self-managed Node / Python / Go, etc.:** middleware at each login surface, atomic distributed limiter, lightweight synchronous risk evaluator, background aggregation where possible.
- **Cloudflare Workers:** Durable Objects / supported rate-limit storage for correctness-sensitive decisions. Workers KV eventual consistency is not a substitute for atomic counters. Read `cloudflare-workers.md`.
- **Firebase / Supabase / Auth0 / Clerk / Cognito / similar:** apply provider supported protections, and only deploy custom middleware at app-owned boundaries. Do not put a public custom password checker in front of a hosted login unless supported and designed securely.
- **Mobile/native apps:** ensure enforcement is on server or IdP; no client-side rate limit is a security control.

## Definition of done

Every relevant entry point either has a verified protection boundary or is explicitly marked out of scope with a remediation owner. Tests show distributed-attack signals are surfaced and a legitimate user's clean login/recovery remains usable. Deployment mode is documented accurately.
