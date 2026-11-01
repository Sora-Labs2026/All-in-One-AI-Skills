# Finding records a reviewer can check

The findings JSON in [fix and verify](fix-and-verify.md#findings-json) already requires who can trigger each finding, its preconditions, impact, severity, confidence and evidence. Add the fields below when findings drive a decision: a launch gate, a disclosure, a bounty payout, a fix-or-accept call by someone who did not do the audit. With them, a reviewer can re-derive each rating from the record instead of trusting the prose, and the next run can match findings across revisions.

`code_audit.py findings` still validates the base format. `audit_record.py rigor` checks the fields here for every live `CONFIRMED` and `LIKELY` finding. `POSSIBLE` leads and `FALSE_POSITIVE` records are skipped.

## Fields

| Field | Content | Required for |
|---|---|---|
| `invariant` | The rule the code must keep, in one sentence: "an invoice is returned only to members of its tenant" | `CONFIRMED`, `LIKELY` |
| `root_cause_key` | A stable key for the root cause, built from code names rather than line numbers: `invoices/find-by-id-without-tenant`. Matches `^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$` and does not end in a line number | `CONFIRMED`, `LIKELY` (recommended on all records) |
| `impact_level` | The level the demonstrated impact alone gives (step 1 of the [severity rules](audit-phases.md#phase-6-rate-severity)), before any adjustment | `CONFIRMED`, `LIKELY` |
| `severity_reason` | One sentence: who, what they get, under which conditions | `CONFIRMED`, `LIKELY` |
| `preconditions` | Typed list, see below; `[]` when there are none | `CONFIRMED`, `LIKELY` |
| `access_class` | `OPEN`, `ANY_ACCOUNT`, `ROLE_OR_OWNERSHIP`, `SERVICE_ONLY`, `OPERATOR_ONLY` or `UNCLEAR`, from [entry points and context](entry-points-and-context.md#3-classify-access-for-every-entry-point) | Optional |
| `trace` | Ordered steps from source to sink | `LIKELY`, and `CONFIRMED` with `STATIC_CONFIRMED` evidence |
| `reproduction` | Interface, steps and the observed result | `CONFIRMED` with `TESTED_LOCAL`, `TESTED_STAGING` or `DEPLOYED_OBSERVED` evidence |
| `owner_check` | The non-destructive observation that settles the `unverified_condition` | `LIKELY` |

Keep `root_cause_key` the same in every state the root cause passes through: lead, likely, confirmed, refuted, fixed. Variants closed by the same change share the finding and its key. Variants that need separate fixes get their own findings and keys. Two live findings with one key are a merge the report forgot.

## Typed preconditions

Each entry is `{"kind": ..., "detail": ...}`. The kind says how the precondition moves severity under the module's rating rules. The detail says what exactly is needed.

| Kind | Use for | Effect on the rating |
|---|---|---|
| `account` | Any account, where signup is open and free | None: open signup is no barrier |
| `role` | A privileged role, staff, an invite-only or paid account the attacker cannot simply obtain | Lower one level |
| `internal_network` | Reach only from the internal network or another service | Lower one level |
| `local_access` | A local account or process on the machine | Lower two levels |
| `physical_access` | Hands on the device | Lower two levels |
| `user_action` | The victim must click, open, approve or visit something | Lower one level per condition, at most two |
| `configuration` | A non-default setting must be on | Same |
| `timing` | A narrow race or timing window | Same |
| `third_party` | Behavior of an outside service the attacker does not control | Same |
| `data_state` | A state the attacker can arrange (a record exists, a feature is used) | None |

Reach kinds do not add up; the largest one applies. A confirmed boundary crossing is never rated below `LOW`, and nothing is rated above its `impact_level`. The validator computes this ceiling for each finding. It reports a severity above the ceiling as a warning, not an error: a human may have a reason, and that reason belongs in `severity_reason`.

Worked example: an admin of tenant A can read tenant B's audit log. The impact, cross-tenant read of sensitive data, starts at `HIGH`. Becoming a tenant admin takes nothing more than creating a tenant, so the precondition is `account`, not `role`, and the ceiling stays `HIGH`. If tenants are created only by sales, the precondition is `role` and the ceiling is `MEDIUM`. The record makes that judgment visible instead of burying it.

## Traces

```json
"trace": [
  {"step": "source", "file": "apps/api/routes/invoices.ts", "line": 18, "note": "invoiceId from the URL path"},
  {"step": "hop", "file": "apps/api/services/invoices.ts", "line": 40, "note": "passed to getInvoice unchanged"},
  {"step": "sink", "file": "apps/api/db/invoices.ts", "line": 12, "note": "findUnique({ where: { id } }) with no tenant filter"}
]
```

A trace runs source, then hops, then sink, with repository-relative files and real line numbers. A one-step trace is a source or a sink. Every hop where a control could have applied belongs in the trace, including the ones that did not apply. The note says why it did not ("`requireTenant` runs only on `/api/admin/*`"). The [triage](triage-and-false-positives.md#4-trace-from-the-sink-backwards) sink-first table is a good way to build it.

## Reproductions in the target's own interface

```json
"reproduction": {
  "interface": "library",
  "steps": ["python -m pytest tests/security/test_archive_paths.py::test_dotdot_entry -q"],
  "observed": "extract_all wrote tmp/outside.txt; test asserted the path stays under tmp/extract and failed"
}
```

HTTP is one interface among several: `http`, `rpc`, `message`, `cli`, `library`, `file`, `ipc`, `browser`, `policy`. A parser finding is reproduced with a fixture file, a library finding with a function call, a desktop finding with an IPC call or a crafted link, an infrastructure finding with a locally rendered policy. The steps run locally with synthetic data, so a reviewer can repeat them without an account, a deployment or production access. `observed` is the actual output that was seen, not the expected one. Stop at the smallest effect that proves the boundary was crossed.

## LIKELY findings and owner checks

A `LIKELY` finding has a complete trace and one decisive fact outside the repository. Three fields make it actionable:

- `unverified_condition`: the fact, stated narrowly. "Production sets `AUTH_REQUIRED=true`", not "deployment config unknown".
- `owner_check`: how the owner settles it by observing, not by attacking: read a setting, a dashboard or a rendered manifest; check whether a route is reachable from outside with a plain request to their own staging host. Never "send this payload to production".
- Optional `local_check`: a local experiment that would settle it, if one exists.

A `LIKELY` finding is rated as if the condition holds, and the report says so.

## Refuted records are kept

A `FALSE_POSITIVE` keeps its `root_cause_key` and a `rejection_reason` that cites the protecting line or the failed screening question. The next run then skips the same claim on unchanged code. A claim refuted at one revision is raised again when the protecting code changes.

## Verify the final records

The independence rule in [audit phases](audit-phases.md#independence-and-duplicates) applies to candidates. Apply it once more to the records you are about to report:

1. Before writing the report, give each `CONFIRMED` and `LIKELY` record to a reviewer who neither found nor proved it. Give them the record only, not the hunter's notes.
2. The reviewer re-opens every cited file and line, rebuilds the input shape and the interface, checks each precondition and visible control, and checks that the severity does not exceed the demonstrated impact. They also check that the proposed fix enforces the invariant at the decision point instead of moving trust elsewhere. For `LIKELY` records, they check that the unverified condition really cannot be settled from the repository.
3. Wording and line-number corrections can be applied directly. A change of verdict, root cause, trace, reproduction, impact or severity goes to another fresh reviewer before it lands. If no fresh reviewer is available, drop the record from the report, keep it as a lead, and say the run is incomplete.
4. Write the report from the verified records only. The prose never changes a verdict, a severity or a precondition, and a clean run reports zero findings instead of padding the list with `LOW` ones.

## Example

```json
{"id": "CSR-004", "title": "Tenant admin reads another tenant's audit log", "class": "broken object-level authorization",
 "cwe": "CWE-639", "file": "apps/api/db/audit.ts", "line": 12,
 "root_cause_key": "audit-log/list-without-tenant-scope",
 "invariant": "audit entries are listed only for the caller's tenant",
 "actor": "admin of any tenant", "access_class": "ROLE_OR_OWNERSHIP",
 "preconditions": [{"kind": "account", "detail": "anyone can create a tenant and becomes its admin"}],
 "impact": "reads other tenants' audit entries, including member emails and IP addresses",
 "impact_level": "HIGH", "severity": "HIGH",
 "severity_reason": "HIGH: anyone who creates a tenant reads every tenant's audit log; no other conditions.",
 "confidence": "CONFIRMED", "status": "OPEN", "evidence_type": "TESTED_LOCAL",
 "evidence_summary": "two-tenant test lists tenant B's entries for tenant A's admin",
 "reproduction": {"interface": "http", "steps": ["seed tenants A and B", "GET /api/admin/audit?tenant=B as A's admin"],
                  "observed": "200 with 14 entries from tenant B"},
 "fix": "derive tenantId from the session in listAuditEntries; ignore the query parameter"}
```

```bash
python3 <productcraft>/modules/code-security-review/scripts/audit_record.py rigor --findings security/code-audit-findings.json
```

## Done when

- Every live `CONFIRMED` and `LIKELY` finding has an invariant, a stable root-cause key, an impact level, typed preconditions and a severity reason. Tested ones have a reproduction, static ones a trace, and likely ones an owner check.
- `audit_record.py rigor` reports no errors, and every severity-ceiling warning is either resolved or explained in `severity_reason`.
- Each reported record was re-checked by a reviewer who did not find or prove it, and material changes had a second fresh check.
- Severities above `MEDIUM` are marked for human confirmation, as the severity rules require.
