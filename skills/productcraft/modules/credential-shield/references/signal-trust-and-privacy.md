# Trusted signals and privacy discipline

## Signal table

| Signal | May help with | Trust source | Pitfall |
|---|---|---|---|
| Attempt/failure count by normalized login ID | distributed per-account abuse | Server-side auth flow | Attacker can induce counts; avoid hard lockout |
| Distinct accounts per verified source | spraying | Trusted ingress + bounded counter | Shared Wi-Fi, workplace NAT, carrier networks |
| Distinct sources per target | proxy spread | Trusted ingress + bounded counter | VPN churn and mobile carrier changes |
| Campaign-wide failure spike | incidents and correlation | Aggregated server results | Traffic spikes alone are not guilt |
| JA3/JA4 | broad connection/client cohort | Verified edge only, when licensed/available | Not user-unique; spoofable/shared |
| Bot score / reputation | supporting evidence | Trusted managed service | Plan-specific, false positives |
| User-Agent | consistency hint | Public user claim | Trivial to forge |
| Remembered device | reduce unnecessary friction | Server-issued, signed/rotatable proof | Stealable, not an authentication factor |
| Network origin / ASN | support source cohorts | Trusted address/lookup | Dynamic and shared networks |
| Session history | normal behavior context | Authenticated server session | Handle users without prior history |

## Header rules

- Do not use `X-Forwarded-For`, `CF-Connecting-IP`, `True-Client-IP`, or custom bot headers on blind trust. Verify access only from the configured proxy chain or authenticated, signed ingress; strip incoming look-alikes at the edge.
- If the edge cannot be verified, fall back to the underlying socket/transport source or mark source attribution untrusted. Do not add precision by guessing.
- Do not derive a made-up JA4 from a user-agent, HTTP header order, or JavaScript device characteristics. True TLS fingerprinting happens at the trusted network edge.
- Never merge accounts based on similar UA/JA4. These are campaign signals, not identity.

## Account IDs and normalization

Resolve canonical username/email using existing app-specific rules. Unicode case-folding, Gmail-style dots/plus addressing, and Unicode confusables must **not** be newly normalized without explicit support in the authentication system. A changed normalization algorithm can merge distinct users or create mismatch/enumeration bugs.

Use a server-only HMAC secret over normalized identifier, with namespaced key version, e.g. `HMAC_SHA256(secret, 'login-risk:v1:' + canonical_identifier)`. Use server-backed secrets manager. No raw email/username in public logs or metrics; never hash unkeyed addresses as identifiers (dictionary attack). Include non-existent identifiers in behavior counters. Retain only bounded, purpose-limited abuse data with a retention policy and access controls.

## Telemetry and privacy

- Log decision class, reason codes, policy version, request ID, trusted network cohorts (only if policy permits), duration, and challenge outcome.
- Never log raw passwords, passkeys, MFA codes, challenge solutions, security answers, refresh/access/session tokens, cookies, or full authorization headers.
- Do not include raw login identifier or fingerprint as a metrics label. Cardinality would explode, and sensitive data could leak.
- Use aggregates/approximate distinct counts with explicit retention TTL. Encrypt sensitive supporting evidence if long-term incident retention is justified and access-controlled.
- Monitor legitimate-user impact: known-good login success, challenge abandonment, reset/login conversion, accessible alternatives, and unusual friction on shared networks.
