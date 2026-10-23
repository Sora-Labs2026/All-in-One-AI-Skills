# Verification and tool matrix

## Evidence standard

For each control store: ID, gate, route/file/config, status, severity (if FAIL), rationale, code location, evidence/test id, verification environment, remediation owner and next action. A grep hit is **not** proof of a vulnerability; a missing grep hit is **not** proof of safety.

Evidence classes:
- `STATIC_CONFIRMED`: source/config inspected with reasoning; limited to what file reveals.
- `TESTED_LOCAL`: local controlled test executed with real assertion and recorded output.
- `TESTED_STAGING`: user-authorized staging test with synthetic data and scoped permissions.
- `DEPLOYED_OBSERVED`: direct observed headers/runtime behavior in authorized environment.
- `INFERRED`: hypothesis requiring follow-up; cannot be a PASS.
- `NOT_TESTED`: missing tools/access/fixtures/knowledge.

## Recommended non-destructive tools if already installed

- Secret scanning: Gitleaks (worktree/history), other approved scanners; redact output. If unavailable, inspect by code search and the bundled `preflight_scan.py`, marking Git history as NOT_VERIFIED.
- SAST: project-specific linters, Semgrep/Bandit/CodeQL where existing, but do not auto-install/execute remote packages in sensitive repos without approval.
- Dependencies: `npm audit --omit=dev` (consider full developer build chain separately), `pip-audit`, `cargo audit`, `osv-scanner`, framework-specific; network and service availability may limit evidence.
- Framework tests: `npm test`, `pytest`, etc. only after reading scripts for dangerous side effects; use test DB/dummy keys and no irreversible writes.
- Browser/deployment: check response headers and cookies only at explicitly authorized local/staging URLs, not random public hosts.
- Provider verification: official API/provider docs, sandbox and dashboard configuration; cloud-console checks are NOT_VERIFIED without access.

## Bundled read-only heuristic scanner

Run: `python3 scripts/preflight_scan.py --root /path/to/repo --json-out /path/to/repo/security/launchguard-scan.json`

What it does: bounded local text scan of common source/config filetypes; detects some credential-like literals (without writing them), suspicious public-variable names, potential debug/CORS/TLS bypass/unsafe HTML/logging patterns, tracks Git-indexed `.env` names when Git exists. Reports `candidate` findings as redacted file+line only.

What it cannot do: cryptographic secret validation, full Git-history scanning, execution tracing, effective cloud configuration, true authorization checks, RLS policy quality, confirmed XSS/SQLi, full SCA or penetration tests. Requires reasoning, broader tools and negative tests.

Do not attach the raw scan artifact to public tickets or send it externally unless reviewed. No credential values are included, but filenames still identify system structure.

## Minimum negative tests

1. Guest access to each protected resource -> unauthorized response with no private fields.
2. User A requests user B's resource -> forbidden/404, even with guessed/sequential IDs; A can access own.
3. User A in tenant 1 requests tenant 2's record -> deny.
4. Regular user sends fake admin role fields -> not elevated; privileged API rejects.
5. User modifies payment amount, quantity, discount or order ownership -> server authoritative.
6. Repeat provider webhook/event -> exactly one grant and no duplicate financial effect.
7. Unpaid/refunded/cancelled transaction -> no undeserved current entitlement.
8. Reset token expired/used/mismatched -> rejected.
9. API errors redact secrets, stack traces and unnecessary PII; diagnostic details stay server-side redacted.
10. Sensitive fields omitted from response serializers and logs.
11. Production build/browser bundle does not contain privileged credentials.
12. Abnormal traffic abuse cases tested only with bounded local fixtures.
13. Upload can reject excessive size/invalid type; object read/write checks ownership.
14. Account deletion removes/anonymizes eligible data while retaining legal records when justified.

Skip checks ONLY with documented N/A; if the relevant feature exists but cannot be tested, mark NOT_VERIFIED.
