# Variant analysis: from one confirmed bug to all of its siblings

Use this after a finding is `CONFIRMED` (or a strong `LIKELY`), before a fix is closed, when an outside report names one location, and when history shows a past security fix. The question is no longer "is there a bug?" but "where else does the same mistake live?". It is not a discovery method for code with no known bug; use the hunting phases for that.

## 1. Write the defect as a rule that was broken

The symptom ("invoice 42 leaked") is too narrow to search for. Write what is missing:

> In `<component>`, `<value and where it comes from>` reaches `<operation>` without `<the check or transformation that must come first>`, so `<actor>` can `<outcome>`.

For logic bugs without a data flow, write the rule instead: "`canEdit(user, doc)` must return false when the user has no role in the document's workspace; it returns true when `doc.workspaceId` is null".

Worked example used below: a Node API with Prisma. `GET /api/invoices/:id` calls `prisma.invoice.findUnique({ where: { id } })`; the session's tenant is never part of the filter.

> Record IDs taken from the URL reach Prisma lookups on tenant-owned models without the session's `tenantId` in the `where` clause, so any signed-in user can read other tenants' records.

The defect statement decides the whole hunt. If it names only `invoice`, the hunt finds only invoices.

## 2. Ask why a sibling would exist

How the bug got there predicts where its relatives are.

| How the mistake spreads | Where to look |
|---|---|
| A handler was copied | The same directory, files added in the same commit (`git show --stat <commit>`), files with the same structure |
| An API is misunderstood (here: assuming `findUnique` is tenant-scoped) | Every call of that API, anywhere in the repository |
| A shared helper has the flaw | Every caller of the helper, and callers of those callers |
| A past fix was partial | The fix commit: which sites it changed, and which sites of the same shape it did not |
| A framework convention is applied inconsistently (a decorator, a middleware list, a route group) | Every route or handler declared without it |
| The same feature exists in several services or languages | The equivalent code in the other services |

Before searching, list the concrete names that play the same role in this codebase (other tenant-owned models: `payment`, `project`, `member`) and check that each exists with `rg -n`. A list of plausible names that the code does not use wastes a search.

## 3. Calibrate on the known instance

Write the narrowest search that finds exactly the confirmed location, and run it.

```bash
rg -n 'invoice\.findUnique\(\{\s*where:\s*\{\s*id\s*\}' .
```

If it does not find the known bug, your understanding of the code is wrong, and every wider search built on it would be too. Read the code again before going on.

## 4. Widen one dimension at a time

Change one thing per step, run it, read every new hit, and write down the counts before the next step.

| Step | Dimension widened | How |
|---|---|---|
| 1 | Names: other models with the same ownership | `rg` over the model names (below) |
| 2 | Shape: any lookup by id whose filter lacks the tenant | Semgrep pattern rule (below) |
| 3 | Operation: `update`, `delete`, `upsert`, `count`, raw SQL on the same tables | Add the operations to the rule; search raw queries |
| 4 | Flow: any request value that reaches an unscoped query | Semgrep taint rule or CodeQL query with the project's request source |
| 5 | Time and place: other branches, old releases still deployed, other services | Git pickaxe search; other repositories only with the user's go-ahead |

```bash
rg -n -e '\.(invoice|payment|project|member)\.find(Unique|First)\(' .      # step 1
rg -n -e '\$(queryRaw|executeRaw)(Unsafe)?\b' .                          # step 3, raw SQL
git log --all --oneline -S 'findUnique({ where: { id'                      # step 5, history
```

```yaml
rules:
  - id: tenant-lookup-without-tenant-filter
    languages: [typescript, javascript]
    severity: WARNING
    message: Lookup by id on a tenant-owned model without tenantId; check that the caller scopes it to the session tenant.
    patterns:
      - pattern-either:
          - pattern: prisma.$MODEL.findUnique({ where: { id: $ID } })
          - pattern: prisma.$MODEL.findFirst({ where: { id: $ID } })
          - pattern: prisma.$MODEL.update({ where: { id: $ID }, ... })
          - pattern: prisma.$MODEL.delete({ where: { id: $ID } })
      - pattern-not: prisma.$MODEL.$OP({ where: { ..., tenantId: $T, ... }, ... })
      - metavariable-regex:
          metavariable: $MODEL
          regex: ^(invoice|payment|project|member)$
```

Test it like any rule ([static analysis](static-analysis-rules.md)): a `ruleid:` case for the known bug written with the shorthand `{ id }` as the code has it, `ok:` cases with `tenantId` present, and an unrelated model. Check how shorthand properties parse with `--dump-ast` rather than assuming.

**When to stop widening.** If more than about half of the new hits at a step are noise, that step widened too far. Undo it and widen a different dimension instead. Read noise as you go: each false positive tells you which assumption was too loose, which you lose if you review them all at the end.

**Always search the whole repository**, not the directory of the first bug. The sibling in `jobs/export.ts` or `admin/` is the normal case.

## 5. Judge every hit

For each hit, read the function, its callers and the origin of each value, then answer three questions:

| Question | What settles it |
|---|---|
| Reachable: does any entry point lead here? | A call path from a route, job, webhook or CLI, cited by file:line |
| Controllable: can the actor choose the value that matters? | The value's origin: URL, body, token claim, stored user data, or a constant |
| Unprotected: is the specific protection from the defect statement really missing on this path? | The absence of the tenant filter and of any equivalent (a tenant-scoped client wrapper, a Prisma client extension that adds `tenantId`, database row-level security) |

- A hit with a different but equally strong protection is a false positive. Record which protection, at which line.
- A hit that is unprotected but unreachable today (no caller yet, a feature flag that is off) is still a finding, at lower severity, with a note on what would make it reachable. A new caller is one pull request away.
- A hit you cannot settle stays `POSSIBLE` with the exact `next_check`.

Edge cases that hide real variants:

- **Both sides missing.** `if (record.ownerId === user.id)` passes when both are `undefined`, for example an anonymous user and a record created without an owner. Ask what each side holds for anonymous callers, deleted users and legacy rows.
- **Empty collections.** `requiredRoles.every(r => user.roles.includes(r))` is true when `requiredRoles` is empty; Python's `all([])` is true too. A policy loaded from a missing config entry becomes "allow".
- **Substring checks.** `"admin-readonly".includes("admin")` and `role.startsWith("admin")` grant more than intended.
- **Names that lie.** A function named `isBlocked` that returns true for allowed users makes every call site look right and be wrong. Check return semantics against the name and the docstring once, then every caller.

## 6. Record the hunt

Keep a hunt log in the report, so a reviewer can repeat it and see where it stopped:

| # | Search and tool | Dimension widened | Hits | Real | Noise | Kept or undone |
|---|---|---|---|---|---|---|
| 1 | `rg` exact match | none (calibration) | 1 | 1 | 0 | kept |
| 2 | `rg` four models | names | 6 | 4 | 2 | kept |
| 3 | Semgrep rule | shape | 11 | 6 | 5 | kept |
| 4 | Semgrep, `count` and raw SQL added | operation | 29 | 7 | 22 | undone |

- Variants that one change closes (they share the decision point) go into the original finding's `variants` list. Variants that need separate fixes become their own findings and reference each other.
- Group false positives by reason ("scoped by `tenantClient()`: 9 sites") instead of listing each one.
- Cite file:line for every confirmed variant and describe what the line does. Quote at most the one line that shows the problem, and never a secret.
- Include the searches that found nothing. "Raw SQL on tenant tables: 0 hits" is coverage.

## 7. Close the class, not the instance

- Fix at the shared decision point when there is one: a data-access layer or client extension that always applies the session tenant, or row-level security in the database, so new code inherits the protection.
- Turn the search with the best precision into a CI rule, with the real variants (sanitized) as its `ruleid:` tests and the false-positive reasons as `ok:` tests.
- Re-run the final searches after the fix. The expected result is zero unprotected hits; any remaining hit is either a new finding or a recorded exception.

## Done when

- The defect statement names the missing protection, not just the location.
- The calibration search found the known instance.
- Each widening step has counts in the hunt log, and the reason the hunt stopped is written down.
- Every hit is a finding, a variant of one, a false positive with the protecting line, or a `POSSIBLE` lead with its next check.
- A CI rule or a shared fix is proposed, so the class does not come back.
