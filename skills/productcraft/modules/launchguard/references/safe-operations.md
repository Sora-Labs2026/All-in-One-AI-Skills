# Safe operations and change control

## Without additional user approval

Allowed on the user's local/repository workspace: read-only inspection; bounded local static scans; reading Git status and history metadata; local test runs after inspecting test scripts; test fixtures and temporary synthetic accounts; low-risk targeted source changes if the user asks to fix issues; new tests and documentation. Avoid transmitting private source code, secrets, PII or hashes to external scanning services.

## Requires explicit approval and scoped authorization

- Any live/staging active attack simulation, brute forcing, phishing, password testing, vulnerability exploitation, account lockout testing, mass traffic, external network scanning or internal asset discovery.
- Deleting/recreating datasets; modifying real users or subscriptions; production environment secret rotation or revocation; provider dashboard changes; changing payment pricing, credit accounting, grants or refunds; database migration with downtime; destructive Git history rewriting; disabling services, security enforcement or logging; production deployment.
- Installing scanner binaries or running `curl | sh` or remote scripts; uploading private code to third-party services.

## Secrets leak response

If a real private credential appears in code, logs, Git history, or a publicly shipped bundle:
1. Do NOT output the credential. Record file+line/identifier category and exposure channels (redacted).
2. Remove from source/client bundle and move to correctly bound server-only runtime secret if safe to implement.
3. Mark ROTATION REQUIRED: the owner must rotate/revoke affected credential at its provider, update runtime secret bindings, invalidate applicable sessions, and review exposure/audit logs.
4. Check deployed artifacts, CI traces, backup retention, forked repositories and Git history. Changing `.gitignore` is not history removal. Coordinate any history rewrite; it may invalidate collaborators' clones.
5. Validate old credential was revoked only with authorized provider verification. Don't claim completion without evidence.

## A note on audit outputs

Even redacted findings can reveal vulnerable endpoints and paths. Write outputs inside a sensible private folder, review ignored/tracked state, and ask before public release. Do not paste an exploit proof or secret into README or commit history.

## False positives and functionality

Respect existing test fixtures/comments; do not delete or rewrite them based on regex. Compare app-required behavior before changing CSP, CORS, signup throttling, payment semantics, auth redirect URLs, session cookies, RLS rules or RBAC. Add negative tests first when practical. Prefer narrow fixes with rollback path.
