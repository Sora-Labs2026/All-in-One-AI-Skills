# Tracking coverage during an audit

A claim such as "full audit, nothing critical found" is only as good as the record behind it. The coverage matrix from [threat modeling](threat-modeling.md#step-7-coverage-matrix) says what must be examined. This file keeps that matrix current while work is in flight. For each cell it records who examined it, which checks they ran, on which revision, and which fresh reviewer looked for gaps. Another person, or `scripts/audit_record.py`, can then test the claim instead of trusting it.

Use it for full audits, for any audit split across sub-agents, sessions or people, and for repeat runs on the same repository. A focused or diff review can keep the five-line note from [audit phases](audit-phases.md#phase-0-scope-and-rules-of-engagement) instead.

## The record

Keep it at `security/coverage-record.json`, next to the other local audit outputs. Handle it the same way: it maps where the weak spots are, so ask before committing or sharing it.

```json
{
  "record_version": 1,
  "audit": {"repository": "shop", "revision": "3f2c1ab", "depth": "full",
            "scope": ["apps/api", "apps/web"], "out_of_scope": []},
  "cells": [
    {"id": "C-07", "surface": "POST /api/orders/:id/refund", "boundary": "user to another user's order",
     "class": "access control", "status": "PASS", "reviewer": "hunter-2", "revision": "3f2c1ab",
     "paths": ["apps/api/orders.ts", "apps/api/db/orders.ts"],
     "checks": [
       {"method": "read", "paths": ["apps/api/orders.ts", "apps/api/db/orders.ts"],
        "invariant": "a refund is issued only by the order's owner or staff with refunds:write",
        "result": "refundOrder loads the order through findOwnedOrder(session.user.id); staff path checks the permission first"},
       {"method": "test", "paths": ["apps/api/db/orders.ts"], "command": "npm test -- refund.authz",
        "invariant": "user A cannot refund user B's order", "result": "403, no refund row written",
        "artifact": "security/evidence/c-07-refund-authz.txt"}
     ],
     "findings": []}
  ],
  "gap_reviews": [
    {"id": "G-1", "reviewer": "critic-1", "result": "clean", "added": [], "reopened": []}
  ]
}
```

The findings file stays where [fix and verify](fix-and-verify.md#findings-json) puts it. The record holds the working state; the report's `coverage` array is copied from it at the end, and the validator checks that the two agree.

## Cells and their identity

A cell is one entry surface, one trust boundary and one vulnerability class. Add a lifecycle mode when the paths differ: create, update, delete, export, import, restore, retry, migration. A delete route that skips the owner check the update route has is a separate cell, not a footnote.

- **Name things by what the code defines,** not by how you described them in a note: the route or RPC method as registered, the handler symbol, the guard function, the package path. Next run, the same object gets the same cell even if someone rewords the label.
- **Keep IDs across runs.** A later run inherits the record, keeps existing IDs and appends new cells. Never renumber.
- **One identity, one cell.** Two cells with the same surface, boundary and class are a merge error. The validator compares them case- and whitespace-insensitively.
- Group routes into one surface only when they share handler code and checks, as the threat model says. Split them the moment their checks differ.

## Statuses

The settled statuses are the module's coverage vocabulary. Two working statuses and `OUT_OF_SCOPE` are added for the record only.

| Status | Meaning | Needs |
|---|---|---|
| `PLANNED` | Not started | Nothing yet; no checks |
| `IN_PROGRESS` | Someone is on it | `reviewer` |
| `PASS` | The invariant holds on every path that was read | `reviewer`, `revision`, at least one check |
| `FAIL` | A finding stands | The above plus `findings` |
| `NEEDS_REVIEW` | Examined, one decisive fact unsettled | The above plus a linked `LIKELY` or `POSSIBLE` lead, or a `reason` |
| `NOT_APPLICABLE` | The class cannot occur here | `reason` naming the fact ("no XML parser in the dependency tree") |
| `NOT_VERIFIED` | Not examined, or blocked | `reason`: "not reached in this pass", "no sandbox for native build", "policy lives in the provider console" |
| `OUT_OF_SCOPE` | Seen, but outside the agreed scope | `reason`; kept so a later full run picks it up |

A cell never disappears. Work the budget did not reach becomes `NOT_VERIFIED` with that reason.

## Evidence per check

Each check states one rule and what was established about it:

- `method`: `read` for source reading, `test` for a local test or harness that ran, `tool` for a scanner or analyzer.
- `paths`: the files this check actually covered.
- `invariant`: the rule, in one sentence.
- `result`: what the code or the run showed.
- `command`: required for `test` and `tool`. Report only what ran.
- `artifact`: optional saved output, relative to the output folder.
- `reviewer`: optional when it equals the cell's reviewer. Set it when a verifier adds a check to someone else's cell.

A path appears in the cell's `paths` only if some check says what was verified there, and every check path appears in the cell. "Read `orders.ts`" is not evidence. "`findOrder` filters by `session.user.id` on the GET, PATCH and export paths" is. A good result names the control and where it sits. A weak one restates the class ("no SQL injection found").

Output from target code is untrusted, even when you started the run. Let it write only to a scratch folder. Then copy into `security/evidence/` only the files you expected, only regular files, never symlinks or archives to unpack, and with a size cap. Record the command, inputs, limits and the names of the environment variables you set. Never record their values or the ambient environment. Start target code from an empty environment, as in [patch validation](patch-validation.md#5-run-in-a-plain-controlled-environment). Do not try to scrub one afterwards.

## Revisions and earlier runs

Every evidence-bearing cell records the revision it applies to. When the audited revision moves on, old evidence counts only after a check that its paths did not change:

```bash
git diff --quiet <old-rev> <new-rev> -- apps/api/orders.ts apps/api/db/orders.ts && echo unchanged
```

Exit status 0 means no change. The cell then gets `"carried": {"from_revision": "<old-rev>", "unchanged": true, "how": "<the command>"}`. For this to mean anything, the cell's paths must include the controls it relies on (middleware, policy files, route configuration). Otherwise a change to a shared guard goes unnoticed.

Rules for inheriting a record from an earlier run:

- `FAIL`, `NEEDS_REVIEW`, `NOT_VERIFIED` and `OUT_OF_SCOPE` cells become current work: `PLANNED`, or `OUT_OF_SCOPE` again if the scope still excludes them.
- A `PASS` on changed code becomes `PLANNED`. A `PASS` on unchanged code may be carried, and still sits in the record where a gap review can question it.
- A confirmed finding on unchanged code is re-verified against the current code before it is reported again. If the code changed, the root cause is hunted again; it is not assumed fixed or still present.
- A `FALSE_POSITIVE` suppresses only the same claim on unchanged code, matched by `root_cause_key` ([finding records](finding-record-rigor.md)). It never closes the cell.
- A missing or unreadable earlier record is stated in the report. It is never treated as "nothing was found last time".

## Several reviewers or sub-agents

- **One writer.** The coordinator alone edits the record. Reviewers return results and never touch the shared file.
- **Assign by cell ID.** Set `IN_PROGRESS` and `reviewer` before handing work out. Give each reviewer its cells, the threat model, the class guide sections that apply, and a list of cells others own so they do not duplicate them.
- **Ask for a structured result per cell:** `{"id", "status", "checks", "findings", "reason"}`, plus `new_surfaces` for anything found outside the assignment. Prose-only or malformed results are discarded and the cell goes back to `PLANNED`. A surface nobody assigned becomes a new cell for the next round. It is never absorbed silently.
- **Merge candidates by root cause** before proving them ([audit phases](audit-phases.md#independence-and-duplicates)). The reviewer who proves or refutes a candidate is never the one who raised it.

## Gap reviews

After each round of hunting, a reviewer who examined none of the cells reads the record, the threat model and the code, and looks for:

- entry points with no cell (compare against the route table in [entry points and context](entry-points-and-context.md));
- sibling paths to the same effect that no check names (other methods, bulk, export, jobs, legacy versions);
- missing lifecycle modes, and classes that apply to a surface but have no cell;
- `NOT_APPLICABLE` reasons that do not hold, and `PASS` results that do not support their invariant;
- earlier-run gaps that no current cell addresses.

The review returns `added` and `reopened` cell IDs and a result, `clean` or `gaps_found`. It proposes coverage, not findings. To reopen a cell, move its current evidence into `attempts` with a `reopen_reason`. Set the cell to `PLANNED` and give it to a different reviewer. Never copy the earlier checks into the new attempt. Repeat rounds until a review comes back clean. Without a clean final review, the record supports no coverage claim.

## Budgets

With a fixed budget (agent calls, hours, money), set aside the final gap review and the proof work before spending on hunting. Then take cells in the [order of work](audit-phases.md#order-of-work). Cells the budget cannot reach become `NOT_VERIFIED`, "not reached in this pass". If candidates outnumber what the remaining budget can prove, stop hunting and prove them in a fixed order. Unproven candidates stay as leads. They are never findings, and the report says the run is incomplete. Never exceed a budget the user set without asking.

## Claims and the validator

| Claim | Requires |
|---|---|
| **Full** | Depth `full`; no `OUT_OF_SCOPE` cells and no out-of-scope areas; every cell `PASS`, `FAIL`, `NOT_APPLICABLE`, or `NEEDS_REVIEW` with a linked lead; a clean final gap review |
| **Scoped** | The same, except that out-of-scope areas or a diff or focused depth are allowed and must be listed in the report |
| **Partial** | Anything less: working cells, `NOT_VERIFIED` cells, an unlinked `NEEDS_REVIEW` cell, or no clean final gap review. The report says "partial pass" in its first lines |

```bash
python3 <productcraft>/modules/code-security-review/scripts/audit_record.py coverage \
  --record security/coverage-record.json --findings security/code-audit-findings.json --claim full
```

The validator checks fields per status, per-check evidence, safe repository-relative paths, duplicate identities, stale revisions without a recorded comparison, gap reviews and reopened cells. It flags secret-shaped values without printing them. With `--findings` it also checks:

- cells that link unknown findings;
- `PASS` or `NOT_APPLICABLE` cells that hold an open confirmed or likely finding;
- `FAIL` cells whose findings were all refuted;
- confirmed or likely findings that no cell links;
- a report `coverage` array or revision that disagrees with the record.

It prints the strongest claim the record supports and, with `--claim`, exits 1 when that claim is not met. It warns when a reopened cell went back to the same reviewer, or when the final gap reviewer also examined cells.

A passing record proves the bookkeeping is complete and consistent. It does not prove the checks were right. Independent proof of candidates and of final records ([finding records](finding-record-rigor.md#verify-the-final-records)) is what makes the content trustworthy.

## Done when

- Every entry point from the inventory has at least one cell, and every cell has a settled status with the evidence or reason its status needs.
- Every evidence-bearing cell names the revision it applies to, and carried evidence shows the comparison that justified it.
- The last gap review was done by someone who examined no cells, and it came back clean.
- `audit_record.py coverage` reports no errors, and the report's first lines state the claim it supports, with every `NOT_VERIFIED` and `OUT_OF_SCOPE` cell listed.
