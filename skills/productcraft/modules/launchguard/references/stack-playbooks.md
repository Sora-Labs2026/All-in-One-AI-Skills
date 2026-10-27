# Stack and provider playbooks

Select ONLY the patterns relevant to the inspected repository; verify current vendor docs before editing.

## Next.js / React / Vite / SPA

- A React/SPA route guard is UX, never the authorization boundary. Server API/edge/database must authorize each sensitive action.
- `NEXT_PUBLIC_`, `REACT_APP_`, `VITE_` variables intended for browser; Next.js `next.config.* env` can embed values even without `NEXT_PUBLIC_`. Check rendered HTML and production bundles.
- SSR, server actions and route handlers require session validation **and** object-scoped authorization. Never treat read-only server components as free of auth concerns.
- Guard RSC/client component boundaries, cache poisoning/sensitive caching, open redirect callback URLs, CSRF when auth uses automatically sent cookies, session cookie attributes, CSP compatible with framework and external payment scripts.
- Avoid XSS through untrusted HTML, markdown renderers, file names, and AI-generated page content.

- While writing framework code, the matching stack reference adds version-specific hooks (server and client boundaries, caching per major version, patched releases, HTML sinks): `../../stacks/references/nextjs.md`, `../../stacks/references/react.md`, `../../stacks/references/vue-nuxt.md`, `../../stacks/references/angular.md`. WordPress plugins and Shopify apps: `../../stacks/references/wordpress.md` and `../../stacks/references/shopify.md`.

## Supabase / Postgres

- Browser Supabase publishable/legacy anon key is normal; secret/service-role key is server-only and bypasses RLS when used as administrative context.
- Audit RLS enabled on exposed tables **and** policies with real `anon`/`authenticated` users, across two users and tenants; `USING` and `WITH CHECK` on writes; storage bucket policies, views/functions, security-definer RPCs and search_path implications.
- JWT claims/user_metadata used for authorization must come from trustworthy sources; avoid accepting arbitrary `user_id`/`org_id` body parameters. Avoid service-role data access that bypasses ownership checks.
- Migrations and seed paths can introduce accidental public read. PostgreSQL should use restricted service identities and encrypted connections appropriate to deployment.

## Cloudflare Workers / Pages / D1 / R2 / KV / Durable Objects

- Use secret bindings for privileged keys; distinguish Worker server env from build-time browser variables. Never commit `.dev.vars` real values.
- Enforce per-route authentication in Worker handlers (including admin actions and cron/queue consumers when applicable); tenant-scoped D1 queries and R2 object key authorization. Public asset domains and object URLs require deliberate read policy.
- Respect cache keys and private response caching, header trust through Cloudflare edge, and anti-abuse controls with durable/consistent storage when needed. Do not claim KV guarantees atomic race-free counters.
- Test payment webhook signature against unmodified raw body when provider requires it; use provider's exact algorithm and tolerance rules.

## Express / Fastify / Django / Rails / Laravel / other

- Use supported framework security middleware and server auth policies, but review actual configuration and route registrations.
- Helmet/security headers should be tuned to legitimate CSP/frame needs. Django/Flask debug flags must be disabled in production. Django CSRF/session cookie/allowed hosts, Laravel CSRF/trusted proxies, Rails strong params/session secrets, etc. require framework-aware checks.
- Audit ORM mass assignment, raw query construction, dangerous file upload handling and object ownership on serializers/endpoints.

## Custom auth and external identity providers

- Identify whether identity provider or app owns password storage, reset, MFA, lockout, session invalidation and detection. Do not rebuild a strong provider flow gratuitously.
- Require authenticated subject and verified claims; handle signing key rotation/audience/issuer; check account deletion, stale entitlements, tenant switching and privileged service tokens.
- For deep distributed credential stuffing, use the Credential Shield module (`../../credential-shield/GUIDE.md`); LaunchGuard verifies integration and local negative tests.

## Payments: Stripe / Razorpay / Dodo Payments / etc.

- Inventory checkout creation -> payment state -> webhook verification -> durable idempotency -> entitlement grants -> cancellations/refunds -> reconciliation.
- Provider-specific secrets/signature algorithms, raw-body requirements, event schemas, unique transaction identifiers, and retry policies are NOT interchangeable. Check current provider docs and existing integration.
- Verify each webhook's claimed `customer`, `product`, `subscription` or `order` association against trusted records before changing another user's entitlements.
- Use one ledger/source of truth for grants/credits and transaction ids, with transactions/unique constraints to handle races. Be explicit about pending vs success and delayed/cancelled states.

## AI / LLM apps

- Keep provider API keys server-side. Validate user permissions before retrieval, embeddings, tools, vector search filters and backend actions.
- Treat prompt content, model output and retrieved data as untrusted. Do not let the model's narrative bypass permission checks or execute privileged tool actions without authorization.
- Minimize user data shipped to model/observability providers; confirm retention, logging and deletion. Limit token/cost/resource abuse by user/account and support safe failure.
