# LaunchGuard | Pre-launch Security Review

> Date: [YYYY-MM-DD] | Repository: [name] | Revision: [short commit/hash or working tree] | Reviewer: [agent] | Environment: [local/staging/deployed]
>
> Scope: [frontend, API, workers, database policies, payment providers, auth, deployment]
>
> IMPORTANT: This report is a scoped engineering assessment, not a penetration test or compliance certificate. Do not include live credentials, session tokens, PII or executable exploits.

## Executive result

**Decision:** [GO (SCOPED) / CONDITIONAL GO / NO-GO / INSUFFICIENT EVIDENCE]

[2-5 sentences detailing evidence, important blockers and uncertainty.]

## Stack and trust boundaries

- Frontend/backend:
- Authentication and roles:
- Database, storage and RLS:
- Payments/webhooks:
- Third parties and data processing:
- Runtime/deployment:
- Test coverage available:
- Out-of-scope or inaccessible components:

## Five security gates

| Gate | Status | Evidence / tests | Blockers / gaps |
|---|---|---|---|
| 1. Secrets | [PASS/FAIL/NEEDS_REVIEW/NOT_VERIFIED/N/A] | [...] | [...] |
| 2. Personal data | [...] | [...] | [...] |
| 3. Production | [...] | [...] | [...] |
| 4. Critical logic | [...] | [...] | [...] |
| 5. Attacker perspective | [...] | [...] | [...] |

## Security baseline (20 controls)

Status per control: PASS / FAIL / NEEDS_REVIEW / NOT_APPLICABLE (why) / NOT_VERIFIED (why). See `references/security-baseline.md`.

| # | Control | Gate | Status | Evidence / test |
|---|---|---|---|---|
| 1 | Hide API keys | 1 | | |
| 2 | Purge Git secrets | 1 | | |
| 3 | Use the public database key in the client | 1 | | |
| 4 | Enable row-level security | 2, 4 | | |
| 5 | Encrypt sensitive data | 2 | | |
| 6 | Enforce server-side auth | 4 | | |
| 7 | Lock record access | 4 | | |
| 8 | Block field tampering | 4 | | |
| 9 | Secure session cookies | 2 | | |
| 10 | Hash passwords | 2 | | |
| 11 | Rate-limit login | 3 | | |
| 12 | Add bot protection | 3 | | |
| 13 | Parameterize queries | 4 | | |
| 14 | Validate all input | 4 | | |
| 15 | Escape user content | 4 | | |
| 16 | Restrict file uploads | 4 | | |
| 17 | Trim API responses | 2 | | |
| 18 | Add security headers | 3 | | |
| 19 | Force HTTPS | 3 | | |
| 20 | Scan dependencies | 3 | | |

## Findings (redacted)

| ID | Gate | Severity | Confidence | File:line / component | Summary | State | Owner |
|---|---|---|---|---|---|---|---|
| LG-001 | | | | | | | |

### Details by ID

#### LG-001: [title]
- Impact / risk:
- Evidence type and sanitized summary:
- Confirmed vs suspected:
- Remediation:
- Regression test:
- Verification result:
- Residual risk:

## Personal-data flow summary

| Category | Collection | Processing/storage | External sharing | Deletion/retention | Risk |
|---|---|---|---|---|---|
| | | | | | |

## Code/config changes made

- `[file]`: [small change + why]

## Verification log

| Command / test | Environment | Outcome (passed/failed/not run) | What it proves / does not prove |
|---|---|---|---|
| | | | |

## Provider/deployment-only actions

- [ ] Secret rotation/revocation required? [owner and status]
- [ ] Staging/production headers observed? [source and status]
- [ ] Database policies tested with realistic auth roles? [status]
- [ ] Webhook provider signatures and idempotency verified? [status]
- [ ] Monitoring/incident response and rollback ready? [status]

## Release decision and ownership

- Unresolved critical/high risks:
- Unverified core controls:
- Risk acceptances (names/approvals):
- Required next steps, owners and dates:
- Post-release monitoring plan:
