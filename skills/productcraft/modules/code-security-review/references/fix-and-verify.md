# Fix, verify and report

Phases 7 and 8. Fixing happens only when the user asked for fixes. The report is written either way.

## Before changing code

Sort each confirmed finding by who should act:

| Kind of fix | Examples | Action |
|---|---|---|
| **Local and clear** | Add an owner check to a query, bind a parameter, switch to a safe loader, escape an output | Fix it, with a test |
| **Needs an owner decision** | Changes product behavior, auth or session policy, pricing or entitlement rules, a public API contract, CSP or CORS that may break integrations, a data migration | Propose the change and its trade-off; do not apply it |
| **Pattern across many call sites** | The same unsafe helper used in dozens of places | Convert it in batches (see "Many call sites" below) |
| **Outside the repository** | Key rotation, provider or cloud settings, IAM, branch protection | List it as an owner action with the exact step |

If a correct fix would spread across many files, if you are unsure it is right, or if it depends on facts you do not have, hand over the diagnosis and a proposed approach instead of a diff.

Protect the user's work: do not stash, reset or overwrite uncommitted changes; do not commit or push unless asked; when asked to commit, stage only the files you changed, never everything in the tree.

Record a baseline first: run the build and the test suite before any change and note which tests already fail or are flaky, so that new failures can be told apart from old ones.

## Write the failing test first

A test that fails before the fix and passes after it is the best evidence that the bug existed and is gone, and it guards against the bug returning. Write it first and run it against the current code: if it passes there, either the claim or the test is wrong.

| Class | Test idea |
|---|---|
| Object or tenant access | Two synthetic users (and two tenants). User A requests, updates and deletes B's record by ID through every route that reaches it; expect 403 or 404 and no change. A still reaches A's own record |
| Mass assignment | Send `role`, `isAdmin`, `ownerId`, `price` or `tenantId` in create and update bodies; expect them ignored or rejected |
| Injection | Pass a marker such as `x' OR '1'='1` or `$(echo marker)` as data; assert the query uses a bound parameter or the argument array contains the marker as one element, and that results are unchanged |
| XSS | Render `<img src=x onerror=alert(1)>` and a `javascript:` link through the real template or component; assert the output is escaped or sanitized |
| Path traversal | Request `../`, encoded `%2e%2e%2f`, absolute paths and symlinks; assert the resolved path stays under the base directory |
| SSRF | Supply internal addresses, alternate IP notations and redirects to them; assert the request is refused before any connection |
| Token handling | Expired, wrong-audience, wrong-algorithm, tampered and reused tokens are rejected |
| Races and double use | Run the two operations concurrently against a local test database (barrier, two connections); assert one succeeds and one fails cleanly |
| Deserialization and parsers | Feed a minimal hostile document; assert a safe error and no side effect |

Use synthetic fixtures, dummy secrets and no network. Make concurrency tests deterministic instead of relying on sleeps. If the project has no test setup, write the smallest harness in its language next to the code, or record why no meaningful test can run.

## Fix the root cause

- **Put the check where the verified identity meets the data or the dangerous call.** Scoping the query by the session user in the data layer protects every route that uses it; a check in one router does not.
- **Prefer the framework's own mechanism:** bound parameters and query builders, ORM scopes and policy objects, auto-escaping templates, allowlists for identifiers, safe YAML and XML loaders, `execFile`-style argument arrays instead of shell strings, canonical path resolution followed by a base-directory check, and an outbound URL allowlist checked after DNS resolution and on every redirect.
- **Fix every variant** found during [variant analysis](variant-analysis.md), or list the ones left open in the report.
- **Keep the diff small and in the project's style.** No unrelated refactors, renames or formatting. No new dependency unless the fix needs one.
- **Say when behavior changes.** If the safe version rejects input that used to be accepted, note it for the owner.

Changes that look like fixes but are not:

| Not a fix | Why | Instead |
|---|---|---|
| Blocking the exact payload (`../`, `<script>`, `' OR`) | Other encodings and shapes reach the same state | Canonicalize, then allowlist, or bind and escape by context |
| Catching and ignoring the error | Hides the bug; the side effect may already have happened | Reject before the side effect |
| A check in the client or one route only | The sink is still reachable another way | Move the check to the shared decision point |
| Reading identity from a different request field | Still attacker-controlled | Use the verified session or token |
| Validating before decoding or normalizing | The decoded value differs from the checked one | Normalize first, then validate the exact value used |
| Disabling the failing assertion or test | Removes the evidence, not the bug | Fix the code |
| Special-casing the test input | Passes the test, leaves the bug | Fix the rule the test exercises |

## Verification ladder

Run the steps in order and stop at the first failure.

1. **Build, type checks and lint** pass.
2. **The new regression test** failed before the fix and passes after it. Record both runs.
3. **The existing suite** has no new failures compared with the baseline.
4. **Try to get around the fix.** Use other encodings, other routes and methods into the same code, nested objects, case and Unicode variants, and concurrent requests. Someone who did not write the fix (for example a sub-agent given only the diff and the finding) tends to find gaps the author misses.
5. **Review the diff** (`git diff`) for new problems: new parsing of untrusted input, a check weakened elsewhere to make the fix work, error messages that leak internals, behavior changes outside the finding.
6. **Simplify.** If a smaller change enforces the same invariant, use it.

A finding becomes `FIXED` only when steps 1 to 3 ran and passed and the record lists the regression test and the commands with their results. If a step could not run, keep the finding `OPEN`, describe the applied change as unverified, and mark the missing step `NOT_VERIFIED`.

For a patch someone else wrote (a pull request, an upstream commit, an AI-generated change), or when the step 2 test might not reach the bug, use [patch validation](patch-validation.md): pinned base and patched copies, a reach marker before each assertion, root-cause variants and a revert check.

## Many call sites

When the same unsafe pattern appears in many places, do not patch them all in one diff. List the call sites with the safe replacement for each, cover them with a parameterized test that fails until each one is converted, convert them in batches small enough to review, and keep the remaining list in the report until it is empty. A Semgrep or CodeQL rule that flags the old pattern in CI stops new copies while the work is under way.

## Make the lesson stick

- Keep every regression test in the normal test suite.
- When a confirmed finding has a recognizable shape in the code, write a Semgrep or CodeQL rule for it and propose it as a CI check. Rules match code shape only, so treat them as a floor, not as proof the class is gone. How to write, test and measure one: [static analysis](static-analysis-rules.md).
- Add the finding's commit or ID to the evidence column of the matching threat in `security/threat-model.md`.

## Report

### Files

| File | Content |
|---|---|
| `security/code-audit-findings.json` | Machine-readable coverage and findings; validate with `code_audit.py findings --file security/code-audit-findings.json` |
| `security/code-audit-report.md` | The human report described below |
| `security/threat-model.md` | From phase 2 |
| `security/code-audit-map.json`, `-history.json`, `-workflows.json` | Raw helper output: keep local, never paste into tickets |

Even redacted findings point at weak spots. Check whether `security/` is ignored or tracked, and ask before committing audit files or sharing them outside the team (see the note on audit outputs in [LaunchGuard safe operations](../../launchguard/references/safe-operations.md)).

### Findings JSON

```json
{
  "audit": {"repository": "shop", "revision": "3f2c1ab", "mode": "full", "scope": ["apps/api", "apps/web"],
            "out_of_scope": ["infra/"], "date": "2026-10-24"},
  "coverage": [
    {"id": "C-01", "surface": "GET /api/orders/:id", "boundary": "user to other users' orders",
     "class": "access control", "status": "FAIL", "findings": ["CSR-001"]},
    {"id": "C-02", "surface": "POST /api/search", "boundary": "anonymous to database", "class": "SQL injection",
     "status": "PASS", "evidence": "apps/api/search.ts:10-40 binds every value; sort column from an allowlist"},
    {"id": "C-03", "surface": "POST /webhooks/payments", "class": "signature verification", "status": "NOT_VERIFIED",
     "reason": "webhook secret configuration lives in the provider dashboard"}
  ],
  "findings": [
    {"id": "CSR-001", "title": "Any user can read any order", "class": "broken object-level authorization",
     "cwe": "CWE-639", "baseline_control": 7, "file": "apps/api/orders.ts", "line": 42,
     "actor": "any self-registered user", "preconditions": [],
     "impact": "reads other customers' orders, names and shipping addresses",
     "confidence": "CONFIRMED", "severity": "HIGH", "status": "OPEN", "evidence_type": "TESTED_LOCAL",
     "evidence_summary": "tests/orders.authz.test.ts: user A receives user B's order (200) before the fix",
     "fix": "scope findOrder by session user id in apps/api/db/orders.ts", "owner": "api team"}
  ]
}
```

| Field | Rule (enforced by `code_audit.py findings`) |
|---|---|
| `id`, `title`, `class`, `file`, `confidence`, `status`, `evidence_type`, `evidence_summary` | Always required; `id` unique; `file` repository-relative |
| `severity`, `actor`, `preconditions` (list), `impact` | Required for `CONFIRMED` and `LIKELY`; forbidden for `POSSIBLE` (severity) |
| `fix` | Required for open `CONFIRMED` and `LIKELY` findings |
| `unverified_condition` | Required for `LIKELY`: the one fact outside the repository |
| `next_check` | Required for `POSSIBLE`: the exact test or read that settles it |
| `evidence_type` | `CONFIRMED` cannot use `INFERRED` or `NOT_TESTED` |
| `rejection_reason` | Required for `FALSE_POSITIVE` |
| `regression_test`, `verification` | Required for `FIXED` |
| `accepted_by` | Required for `ACCEPTED` |
| Coverage `evidence` / `reason` / `findings` | `PASS` needs evidence; `NOT_APPLICABLE` and `NOT_VERIFIED` need a reason; `FAIL` lists finding IDs; a cell cannot pass while a confirmed finding it lists is open |
| Any string | Must not contain a secret-shaped value |

Optional fields: `cwe`, `baseline_control` (LaunchGuard control number), `line`, `owner`, `variants` (other locations with the same root cause), `chain` (IDs of linked findings), `cvss_vector`.

### Report structure

```markdown
# Code security review: <repository>

> Date | Commit (+ uncommitted files) | Depth: full / diff <base>...<head> / focused | Reviewer: agent (+ human, if any)
> Scope and out of scope | What was allowed to run | Environment: local / staging
> This is a scoped code review, not a penetration test, certification or guarantee. No secrets, tokens or personal data appear below.

## Result
Audit result: FAIL / NEEDS_REVIEW / PASS (scoped) / INSUFFICIENT_EVIDENCE, as printed by `code_audit.py findings`.
Two to four sentences: the most important findings, what was not covered, what the owner must do next.

## Coverage
Cells by status; every NOT_VERIFIED and NOT_APPLICABLE cell with its reason; areas not reached in this pass.

## Confirmed findings
| ID | Severity | Title | Who can trigger it | Location | Status |
Then one section per finding (template below).

## Likely findings
Same table plus the unverified condition and the owner check that settles it.

## Leads (not vulnerabilities)
ID, location, why it is suspicious, next check. No severity.

## Hardening notes
Improvements with no demonstrated boundary crossing.

## Changes made
File, change, finding ID, regression test.

## Verification log
| Command or test | Environment | Result (passed / failed / not run) | What it proves and does not prove |

## Owner actions
Rotations (ROTATION REQUIRED), provider and repository settings to check, decisions needed.

## Limitations
What the review could not see; recommend a qualified human review for high-value systems.
```

Finding detail template:

```markdown
### CSR-001 [HIGH] Any user can read any order
- Location: apps/api/orders.ts:42 (also apps/api/export.ts:17, same root cause)
- Who can trigger it: any self-registered user; preconditions: none
- What happens: user A requests /api/orders/<B's id> and receives B's order with name and address
- Evidence: TESTED_LOCAL, tests/orders.authz.test.ts (failed before the fix)
- Severity reason: other users' personal data, reachable by anyone who signs up
- Fix: scope the query by the session user in apps/api/db/orders.ts; covers both routes
- Verification: regression test passes; full suite 212 passed, 0 new failures; bypass attempts with the list and export routes refused
- LaunchGuard: baseline control 7
- Remaining risk: none known in reviewed code
```

### Findings in code you do not own

Reporting a bug in a dependency or another project is the user's decision; ask before sending anything. If they agree: confirm the bug in a published release, use only the project's private security contact (its `SECURITY.md`, its `security.txt` or the hosting platform's private reporting), say which tools were used and what a person checked, and keep the details private until a fix is out or a date is agreed, following coordinated vulnerability disclosure practice.

## Done when

- Every applied fix has a regression test that failed before and passes after, and the ladder results are recorded.
- Fixes that need an owner decision, a migration or an action outside the repository are listed, not applied.
- `code_audit.py findings` reports no errors, and the report's result line matches its output.
- The report states the depth, scope, coverage gaps, every command run with its result, and contains no secret values.
