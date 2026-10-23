# The five LaunchGuard gates

Sequence: secrets -> personal-data flow -> production readiness -> critical logic -> attacker perspective. Complete all gates even if the early ones find blockers. Assess both frontend and backend.

## Gate 1: Secret leak prevention

**Inventory:** cloud/payment/AI/email/database/OAuth credentials, tokens, private key material, signing secrets, storage credentials; consumer-facing publishable keys; per-environment separation; secrets-management access rights.

**Check:** hard-coded strings in source/comments/fixtures; tracked `.env`; Git history; archives, `.next`, `dist`, `build`, mobile binary, sourcemaps; Next `next.config env`, `NEXT_PUBLIC_`, Vite `VITE_`, React `REACT_APP_`; accidental server imports into client; environment variable propagation; logs/traces; CI/PR output; response dumps; object storage buckets; publicly accessible config endpoints. `gitignore` alone does not untrack previously committed files.

**Public != secret:** Supabase publishable or legacy anon key is designed for client use, with correct RLS/grants; legacy service role/new secret keys cannot reach browser. Stripe publishable is client-safe; secret key is not. Other providers differ: check documentation. Rotate exposed credentials, invalidate compromised sessions if needed, and assess credential copies in Git history/releases. Never place real values in audit report.

**Tests:** Git index and history scans with appropriately configured scanner if available; build/bundle inspection; test that server-only module is not imported to client; unauthorized access tests for public Supabase endpoints. Secret scanning can return false negatives, especially dynamic values.

## Gate 2: Personal data flow

Create per-field map: collection -> frontend -> backend -> database/cache/queue -> logs -> external processors -> export/deletion -> retention. Distinguish password inputs, session cookies, payment metadata, PII, user-uploaded files, and AI prompts/outputs.

**Check:** log redaction and telemetry sampling; analytics/email/AI-provider fields; API allowlist/serialization, no sensitive ORM object spread; encrypted transit and storage as required; appropriate password hashing; cookie attributes, CSRF, idle/absolute session life; no access tokens or sensitive data in browser storage absent justified threat model; RLS/tenant isolation; deletion/export pipelines including downstream processors, backups and retention policies.

**Tests:** synthetic user A vs B can access only own resources; serializer omits `passwordHash`, secrets and unnecessary fields; logs never emit sensitive marker fixtures; deletion is idempotent and respects legal retention.

## Gate 3: Production readiness

**Check:** required env vars names/startup failure; no debug mode, test creds, staging webhooks, hidden admin/seed routes; clean errors with request IDs; security headers and deployment-level verification; response `Cache-Control` for private data; CORS origin/method/credential handling; CSRF for cookie-authenticated mutations; HTTPS DB and cloud connectivity, least-privilege DB roles; rate limiting/abuse controls per endpoint and account; secure uploads/object storage; dependency advisories and pinned builds; backup/restore/incident readiness; robots/meta tags are not access control; protect docs/metrics/health endpoints with context-aware rules.

**Notes:** Hardcoding CSP `script-src 'self'` can break legitimate Next.js/nonced scripts or payment SDKs. Setting HSTS includeSubDomains/preload without checking subdomains can break deployment. `X-Frame-Options: DENY` is inappropriate for an intended embedded app. Do not apply a naive five-per-minute limit to all users behind the same NAT.

**Tests:** clean environment startup with missing critical variable; production-mode error sanitization; deployed/staging headers; explicitly allowed CORS origin vs disallowed; secure cookies on HTTPS; negative check for forgotten debug endpoints.

## Gate 4: Critical security logic

**Authn vs authz:** authentication identifies caller; route, row and action authorization checks whether caller is allowed. Inspect every endpoint with user-supplied IDs, pagination filters, tenant IDs, admin actions, GraphQL resolvers, server actions and storage access. Owner or tenant comes from verified context, not an untrusted request.

**Session/reset:** reset and email-verify tokens random, one-time, bound to user, expiry and revocation. Fixed 15 minutes is a *guide recommendation*, not a universal mandate; choose risk-appropriate lifetime and provider behavior. JWT should validate signature, intended algorithms, issuer/audience, expiry. Expired sessions should not authorize actions; define logout and refresh token revocation.

**Payments:** server derives amount and currency from trusted price definitions; verifies provider callbacks and raw-body requirements; event ID deduplication; replay-safe state transitions, pending->paid->refunded/cancelled; receipt checks and reconciliation; only verified captures/settlement according to product semantics trigger entitlement. Client redirects/thank-you pages are not proof of payment. Stripe, Dodo Payments, Razorpay and others have different schemas and signatures: use actual provider docs.

**Other:** parameterized queries; HTML encoding and sanitized rich text; bounded file type/size processing; no path traversal or unsafe user-supplied fetch destinations; background job authorization; AI prompt injection causing tool misuse, retrieval of data outside caller's ACL.

**Tests:** cross-user and cross-tenant access; guest access; forged role fields; arbitrary order IDs; duplicate webhooks; failed payments; negative/zero/overflow pricing; expired reset token, token replay; upload disguised executable and oversized file; malicious user input safe output.

## Gate 5: Attacker mindset

Record concrete attempted misuse scenarios *in local automated tests* instead of weaponizing them against production. Start with high-impact assets: personal data, admin access, money/credits, sensitive exports, secret-bearing workflows. Use a two-user+two-tenant fixture, role hierarchy, one unpaid order, one paid order and one duplicate provider event when applicable.

For every attack case:
- Entry point and actor
- Assumed privilege and object ownership
- Invalid state/payload category (not a destructive exploit)
- Expected denial or safe behavior
- Executed test and result
- Fix and regression test if failure

**Abuse concerns:** account enumeration, mass signup/spam, unauthenticated endpoint resource load, duplicate promo/referral redemption, abusive retries and queues, billing race conditions. Do not change product's trial/credit semantics without checking requirements.

## Additional safety issues beyond the five gates

- CI/CD integrity, dependency and lockfile risks, infrastructure IAM permissions, backups/restores and rollback readiness.
- LLM-powered apps: prompt injection through untrusted documents; tool permissions; model-to-service authorization; PII sent to external models; output moderation where relevant; cost/compute abuse; server-side secret containment.
- Third-party processors: limit data disclosure and confirm service-specific controls. Legal/compliance status depends on region and business; audit evidence is not legal advice.
