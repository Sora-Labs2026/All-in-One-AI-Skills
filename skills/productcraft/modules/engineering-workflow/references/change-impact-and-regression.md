# Change impact, regression scope and test traceability

Read this before a change that crosses modules, alters stored data or an interface, touches authentication or deployment, or is costly to undo; when someone asks for the blast radius or which tests a change needs; when "changing A broke B" has happened before; and after implementing, to check the result against what was planned. For a change inside one module, the callers check in `reviewing-changes.md` and the blast-radius step of `../../codebase-map/GUIDE.md` are enough.

The analysis is read-only. It proves the impact from real dependencies, marks what it cannot prove as `unverified`, and turns the result into checks that run.

## 1. Map the impact before the change

Answer each row with evidence, not with guesses from directory names:

| Surface | Questions | Evidence |
|---|---|---|
| Code | Entry points, direct callers, downstream consumers, generated code, compatibility layers | `map_codebase.py --focus <file>`, `git grep -n "<symbol>"`, the build tool's dependency graph |
| Data | Schemas, migrations, stored formats, caches and cache keys, idempotency keys, historical rows | Migration folder, models, serializers, `../../engineering-practices/references/data-and-migrations.md` |
| Interfaces | APIs, events, file formats, CLIs, SDKs; who consumes and who provides | Contract files, client code, `../../engineering-practices/references/api-contracts.md` |
| Tests | Which existing tests prove the affected behavior; which are missing | Tests importing the changed code (`tested_by` in the map), section 4 below |
| Docs | README, ADRs, runbooks, API docs, agent instruction files that would become wrong | `git grep -n "<name>" -- '*.md'` |
| Release | Deploy order, compatibility window, flags, rollback, irreversible effects | `../../engineering-practices/references/ci-and-release.md` |

- A migration, a breaking interface change, an authentication change or a production release without a written rollback, compatibility window and list of irreversible effects is a blocker for the plan. Write the rollback; do not run it on anyone's behalf.
- Keep the impact note in the reply for a small change. For a high-risk one, ask whether the project has a place for such notes before writing a file.
- **Done when:** every row has evidence or an `unverified` mark, and each changed surface maps to a check in the plan.

## 2. Choose the regression scope

A change needs: the changed module's tests, the tests of every consumer whose inputs can change, contract tests for each changed interface, and the smoke path through the product. Use the build tool's graph when it has one:

| Tool | Affected-only run |
|---|---|
| Nx | `npx nx affected -t test --base=origin/main` |
| Turborepo | `npx turbo run test --affected` (2.1 and later), or `--filter=...[origin/main]` (changed packages and their dependents) |
| pnpm workspaces | `pnpm --filter "...[origin/main]" test` |
| Maven | `mvn -pl <module> -amd verify` (the module and every module that depends on it) |
| Gradle | `./gradlew :<project>:buildDependents` |
| Bazel | `bazel query "rdeps(//..., //lib/billing:billing)"`, then `bazel test` on the test targets it lists |
| Go | `go test ./...`; the test cache reruns only packages whose inputs changed |
| Jest, Vitest | `npx jest --changedSince=origin/main`; `npx vitest run --changed origin/main` |
| pytest | The pytest-testmon plugin selects tests from recorded coverage (`pytest --testmon`) |

Affected-only runs follow the static graph. Dynamic imports, configuration and data files, shared databases, generated code and anything reached over the network are invisible to it. Use selection for fast feedback while working; the full suite still runs before merge or in CI.

## 3. A regression ledger when there is no graph

Repositories without such a tool, such as data pipelines, script collections and mixed-language services, can keep a short ledger. Start one when there are three or more interdependent modules, or on the day of the first "A broke B" incident; not before.

For each module record: its paths; its downstream consumers and how each edge was established (an import scan command, a build file, the pipeline definition); its **acceptance command**; and its propagation rule. A JSON ledger works with the bundled helper:

```json
{
  "always": ["ruff check ."],
  "modules": {
    "ingest":  {"paths": ["pipelines/ingest/"], "check": "pytest tests/ingest -q", "downstream": ["clean"]},
    "clean":   {"paths": ["pipelines/clean/"], "check": "python scripts/reconcile.py --stage clean",
                "downstream": ["report"], "unverified_downstream": ["export"]},
    "report":  {"paths": ["pipelines/report/"], "check": "python scripts/golden_diff.py report"},
    "export":  {"paths": ["pipelines/export/"], "check": null}
  }
}
```

- **Prefer reconciliation over loose assertions.** A command that compares output with a golden sample, checks that totals match upstream, or counts rows in and out is harder to weaken by accident than a mock.
- **A module without a command is a gap, not a pass.** An edge nobody has verified mechanically blocks an all-green verdict until someone confirms it or includes the module.
- **Refresh edges from evidence** (rerun the recorded scan), never by hand-editing a list.
- **The verdict is the exit code** of each command. The person auditing reports; the author of the change fixes and asks for a rerun.
- **Attribute failures carefully.** If the base was green, only A changed and B is now red, trace the handoff from A to B. If B was already red at the base, report it as pre-existing, not as caused by A. Small change batches make this easy.

`../scripts/affected_checks.py` reads the ledger and the changed files and prints the plan: modules changed directly, every downstream module reached, the checks in dependency order, modules without a check, unverified edges and files no module claims. It never runs the commands.

```bash
python3 <productcraft>/modules/engineering-workflow/scripts/affected_checks.py --ledger regression.json --git origin/main
python3 <productcraft>/modules/engineering-workflow/scripts/affected_checks.py --ledger regression.json \
  --changed pipelines/ingest/read.py --exempt "ingest=logging change only" --json
```

`--git BASE` collects changes since the merge base plus staged, unstaged and untracked files (a clean working tree alone proves nothing). `--exempt MODULE=REASON` stops propagation from a module and prints the reason; use it only when the change cannot alter what downstream modules receive. `--strict` exits 1 while a gap or unverified edge remains; exit 2 means an invalid ledger, argument or git failure.

## 4. Requirements and bugs, linked to tests

Link each acceptance criterion, business rule, known risk and fixed bug to the test that proves it, using what the project already has: identifiers in test names (`test_ac07_rejects_second_import`), a registry file, or the issue tracker. Link the criteria; do not copy them, or the copy drifts.

- **States:** missing, in progress, unverified, covered, not applicable. "Not applicable" needs a reason such as a schema, type or lint rule that guards it better; "hard to test" is not one.
- **Covered means** the test exists, asserts the behavior rather than "was called" or "returned 200", runs in the standard test command or a clearly named group, passed in a run you saw, and uses the criterion's real input and boundary.
- **Every bug fix** gets a regression test that reproduces the real failure shape through the same entry point, or a written reason with manual verification steps. Without either, the defect is not closed.
- **Inventory before adding.** List existing tests by module or flow, level (unit, integration, contract, end-to-end, smoke), what each protects and what external systems it needs. Mark possible duplicates and stale tests for a person to decide; an inventory never deletes or rewrites tests.
- A quick check of links: `git grep -n "AC-07" -- tests/` per identifier, and the acceptance list in `requirements-and-acceptance.md` side by side with the results.

## 5. Contract tests across a boundary

When a client and a provider are built and released separately, one machine-readable contract (OpenAPI, JSON Schema, GraphQL SDL, protobuf) is the single source, and four kinds of evidence point at it:

1. **The contract itself** validates (schema lint, breaking-change check against the released version).
2. **Consumer:** types, mocks and fixtures generated from or validated against the contract, and consumer tests that use them.
3. **Provider:** the real serialized responses and messages validated against the contract, not just internal types. Property-based API testing from the schema (for example Schemathesis for OpenAPI) or consumer-driven contracts (for example Pact) do this systematically.
4. **Integration:** at least one real path across the boundary, or a recorded gap.

Green consumer tests and green provider tests that do not share the contract prove nothing about compatibility. Change the contract first, regenerate consumer assets, then rerun both sides and the integration path.

## 6. After the change: compare plan and result

- Does the change solve the problem the request stated?
- Does the diff stay inside the declared scope (`../scripts/diff_scope.py --scope <paths>`)? Anything extra is either authorized and added to the impact note, or removed.
- Does the evidence cover each criterion, rather than merely showing that a command ran?
- Were contracts, ADRs, the ledger, docs and agent instruction files updated where the change made them wrong?
- What remains: temporary code, compatibility shims, unfinished migration steps, follow-up issues?

Report it as a short table: planned surface, actual change, evidence, open item.

## Done when

- [ ] Every surface in section 1 has evidence or an `unverified` mark, and high-risk changes have a written rollback and compatibility window.
- [ ] The regression scope covers the changed module, its consumers, changed contracts and the smoke path, and each check's exit code is reported.
- [ ] Affected-only selection, if used, is backed by a full-suite run before merge.
- [ ] Each acceptance criterion and fixed bug points to a test that passed, or to a stated reason and manual check.
- [ ] The final diff was compared with the plan, and leftovers are listed.

## Anti-patterns

- Guessing dependencies from folder names, or treating one old scan as permanent truth.
- "The changed module's tests pass" offered as proof that its consumers still work.
- A ledger or registry that copies requirements, mirrors every test function, or replaces the tracker.
- Declaring green while an affected module has no check.
- Separate client and server field lists maintained by hand.
