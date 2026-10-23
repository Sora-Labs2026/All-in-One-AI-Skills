# Security baseline: 20 controls

Every web app that stores user data should meet these 20 controls before launch. Use the list two ways:

- **Scoped check:** when a change touches auth, data access, queries, uploads, cookies, headers or dependencies, check only the controls that change touches.
- **Full review:** during the five-gate review, report every control in the baseline table of the LaunchGuard report as `PASS`, `FAIL`, `NEEDS_REVIEW`, `NOT_APPLICABLE` (justified) or `NOT_VERIFIED` (why).

Each control names its gate, the correct implementation, the common trap and how to verify it. A ticked box is not evidence: `PASS` needs inspected code or an executed test.

| # | Control | Gate | # | Control | Gate |
|---|---|---|---|---|---|
| 1 | Hide API keys | 1 | 11 | Rate-limit login | 3 |
| 2 | Purge Git secrets | 1 | 12 | Add bot protection | 3 |
| 3 | Use the public database key in the client | 1 | 13 | Parameterize queries | 4 |
| 4 | Enable row-level security | 2, 4 | 14 | Validate all input | 4 |
| 5 | Encrypt sensitive data | 2 | 15 | Escape user content | 4 |
| 6 | Enforce server-side auth | 4 | 16 | Restrict file uploads | 4 |
| 7 | Lock record access | 4 | 17 | Trim API responses | 2 |
| 8 | Block field tampering | 4 | 18 | Add security headers | 3 |
| 9 | Secure session cookies | 2 | 19 | Force HTTPS | 3 |
| 10 | Hash passwords | 2 | 20 | Scan dependencies | 3 |

## Secrets and keys

### 1. Hide API keys (Gate 1)
- **Do:** keep secret keys (payment, AI provider, email, database service role, signing secrets) on the server in environment variables or a secrets manager. Call third-party APIs from server code.
- **Trap:** `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_` and Next.js `next.config` `env` ship values to the browser. Obfuscation or a "hidden" frontend file is not secrecy.
- **Verify:** inspect the production bundle for secret-shaped values. Scanner rules: `SECRET_LIKE_LITERAL`, `PUBLIC_SECRET_NAMING`, `TRACKED_ENV_FILE`.

### 2. Purge Git secrets (Gate 1)
- **Do:** first **rotate or revoke** every secret that was ever committed. Then remove it from the working tree, untrack `.env` files with `git rm --cached` and add them to `.gitignore`. Rewrite history (`git filter-repo`, BFG) only with the owner's approval and a coordinated force-push.
- **Trap:** deleting the line or rewriting history does not un-leak a key: clones, forks, CI logs and caches keep it. `.gitignore` does not untrack files that are already committed.
- **Verify:** scan history with Gitleaks or an equivalent if installed (otherwise `NOT_VERIFIED`) and confirm rotation with the owner. Never rewrite history or force-push without explicit authorization.

### 3. Use the public database key in the client (Gate 1)
- **Do:** browsers and mobile apps get only the publishable/anon key (for example the Supabase anon or publishable key, or the Firebase web config). Service-role and secret keys stay on the server.
- **Trap:** a public key is only safe when row-level security or security rules restrict every table and bucket it can reach. Public key plus no RLS means a public database.
- **Verify:** search client code and bundles for service-role or secret keys, and verify control 4.

## Data access

### 4. Enable row-level security (Gates 2 and 4)
- **Do:** enable RLS on every table and storage bucket reachable with client keys, with explicit select, insert, update and delete policies based on the authenticated user or tenant membership.
- **Trap:** an always-true policy, a missing `WITH CHECK` on insert/update, or server code that uses the service-role key for user requests bypasses RLS entirely.
- **Verify:** with the public key, query each table as user A, user B and anonymous. A sees and changes only A's rows.

### 5. Encrypt sensitive data (Gate 2)
- **Do:** use TLS for every connection (browser, database, third-party APIs) and provider encryption at rest. Add field-level encryption with managed keys (KMS) for high-risk fields such as stored third-party OAuth tokens, government IDs or health data.
- **Trap:** passwords are hashed (control 10), never encrypted. Don't invent cryptography or store the key beside the data. Encryption does not replace access control.
- **Verify:** confirm database connections require TLS and list how each sensitive field is stored. At-rest settings live in the provider console and are `NOT_VERIFIED` without access.

### 6. Enforce server-side auth (Gate 4)
- **Do:** every API route, server action, RPC, GraphQL resolver and background job derives the user from a verified session or token on the server.
- **Trap:** hiding buttons or routes in the UI is not authorization. Middleware matchers often miss API routes, server actions and newly added paths.
- **Verify:** call each protected endpoint with no session and with an expired session. Expect 401/403 and no data.

### 7. Lock record access (Gate 4)
- **Do:** every read or write by ID checks that the record belongs to the caller or the caller's tenant, using the identity from the session, never from the request body or query.
- **Trap:** insecure direct object references, such as `GET /api/orders/123` returning anyone's order. Unguessable IDs such as UUIDs are not authorization.
- **Verify:** user A requests user B's record by ID and gets 403 or 404. Repeat across tenants.

### 8. Block field tampering (Gate 4)
- **Do:** allowlist the fields a client may write (schema or DTO). Set `userId`, `role`, `isAdmin`, `plan`, `price`, `paid` and `credits` on the server only, and recompute prices and totals server-side.
- **Trap:** spreading the request body into an ORM create or update (mass assignment) lets users promote themselves or change prices.
- **Verify:** send extra privileged fields in create and update requests. They are ignored or rejected.

## Sessions and login

### 9. Secure session cookies (Gate 2)
- **Do:** session cookies set `HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict`), a scoped path and domain, and a bounded lifetime. Rotate the session ID on login and privilege change, and invalidate it on logout.
- **Trap:** keeping session or refresh tokens in `localStorage` exposes them to any XSS. `SameSite` alone is not full CSRF protection for cookie-authenticated mutations.
- **Verify:** inspect `Set-Cookie` headers in an authorized local or staging run. Scanner rule: `INSECURE_COOKIE_FLAG`.

### 10. Hash passwords (Gate 2)
- **Do:** use the auth provider, or Argon2id (preferred), scrypt or bcrypt with current cost parameters through a maintained library.
- **Trap:** MD5, SHA-1, SHA-256 or any other fast hash, reversible encryption or plaintext. Never log passwords.
- **Verify:** find the hashing call and its parameters. Scanner rule: `WEAK_PASSWORD_HASH`.

### 11. Rate-limit login (Gate 3)
- **Do:** limit attempts per account identifier across all IPs and per source on login, signup, password reset, OTP send/verify and MFA, with graduated delays and challenges.
- **Trap:** hard lockouts let attackers lock out real users. Per-IP limits alone miss distributed attacks, and strict per-IP limits block offices and mobile carriers behind shared NAT.
- **Verify:** design and test with the [Credential Shield](../../credential-shield/GUIDE.md) module.

### 12. Add bot protection (Gate 3)
- **Do:** add an accessible challenge (for example Cloudflare Turnstile, hCaptcha or reCAPTCHA) to signup, risky logins, password reset and abused public forms, and **verify the token on the server**.
- **Trap:** a client-only check is bypassable. A challenge on every login hurts real users and is not account-takeover protection on its own; pair it with controls 10 and 11 and MFA.
- **Verify:** submit without a token and with a reused token. The server rejects both.

## Input and output

### 13. Parameterize queries (Gate 4)
- **Do:** use prepared statements, query builders or ORM bindings for every value. Choose identifiers such as column names and sort order from an allowlist.
- **Trap:** string concatenation or interpolation in raw SQL helpers (`$queryRawUnsafe`, `.raw()`, `execute(f"...")`), and NoSQL operator injection such as `{"$gt": ""}` from unvalidated JSON.
- **Verify:** review every raw-query call site and test quote and operator payloads against a local test database.

### 14. Validate all input (Gate 4)
- **Do:** validate on the server with a schema library (for example Zod, Valibot, Pydantic or Joi): types, lengths, ranges, formats and enums, rejecting unknown fields. Client validation is for UX only.
- **Trap:** validating the form but trusting the API body, and accepting unbounded strings or arrays.
- **Verify:** send malformed, oversized and extra-field payloads directly to the API.

### 15. Escape user content (Gate 4)
- **Do:** rely on the framework's automatic escaping and encode for the output context (HTML, attribute, URL, JavaScript). When rendering user HTML or Markdown, sanitize with a maintained allowlist sanitizer such as DOMPurify, and add a Content-Security-Policy as defense in depth.
- **Trap:** `dangerouslySetInnerHTML`, `v-html`, `innerHTML`, template `safe` filters, unsanitized Markdown, and `javascript:` URLs in user-supplied links.
- **Verify:** in a local test, render `<img src=x onerror=alert(1)>` and a `javascript:` link. Nothing executes. Scanner rule: `UNTRUSTED_HTML_SINK`.

### 16. Restrict file uploads (Gate 4)
- **Do:** enforce size limits and allowed types on the server by checking file content (magic bytes), not just the extension or `Content-Type`. Generate random storage names, keep files in a private bucket or outside the web root, serve them through authorized or short-lived signed URLs, and never execute them.
- **Trap:** SVG or HTML uploads served from your own domain can run scripts, public buckets expose every file, and trusting the client's filename enables path traversal.
- **Verify:** upload an oversized file, a renamed executable and an SVG containing script, then request another user's file.

### 17. Trim API responses (Gate 2)
- **Do:** return only the fields the screen needs through explicit selects, DTOs or serializers. Error responses carry a message and request ID, not stack traces.
- **Trap:** returning whole ORM objects leaks password hashes, tokens, internal flags and other users' emails. Hiding fields in the frontend still sends them over the network.
- **Verify:** inspect real JSON responses from user, order and admin endpoints, and trigger an error in production mode.

## Platform

### 18. Add security headers (Gate 3)
- **Do:** set `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `frame-ancestors` (or `X-Frame-Options`), `Referrer-Policy` and `Permissions-Policy` in the framework or at the edge.
- **Trap:** a copied strict CSP breaks framework scripts and payment SDKs (use nonces or hashes), and denying all framing breaks apps meant to be embedded. Headers in source code are not proof they are deployed.
- **Verify:** observe the headers on an authorized staging or production URL, otherwise mark `NOT_VERIFIED`.

### 19. Force HTTPS (Gate 3)
- **Do:** redirect HTTP to HTTPS at the edge, send HSTS, mark cookies `Secure`, use TLS for database and API connections, and fix mixed content.
- **Trap:** HSTS `includeSubDomains` or `preload` breaks subdomains that do not serve HTTPS, and preload is hard to undo. Disabled certificate verification (`verify=False`, `rejectUnauthorized: false`) silently removes TLS protection.
- **Verify:** request the HTTP URL and check the redirect and HSTS header. Scanner rule: `TLS_VERIFICATION_DISABLED`.

### 20. Scan dependencies (Gate 3)
- **Do:** commit lockfiles, run the ecosystem's audit tool (`npm audit`, `pip-audit`, `osv-scanner`, `cargo audit`), enable Dependabot or Renovate, and check new packages for typosquatting and abandoned maintainers before adding them.
- **Trap:** auto-upgrading major versions without tests, ignoring advisories in production dependencies, and trusting install scripts from unknown packages.
- **Verify:** run the available audit tool and record the result. If the tool or network is unavailable, mark `NOT_VERIFIED`.

## Beyond the baseline

The baseline is a floor, not the whole review. The [five gates](five-gates.md) also cover payment webhooks and entitlements, CSRF, SSRF, password reset tokens, logging and personal-data retention, CORS, debug endpoints, backups, and AI prompt injection and tool permissions.
