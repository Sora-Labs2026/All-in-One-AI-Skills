# Repository health audit

Read this when someone asks for an audit, a health check or a review of a whole codebase, package or service rather than of one change: what is broken or fragile, what will not survive the expected load, which risky code has no test, what is slow, and what could be removed or reorganized. The deliverable is a ranked report. The audit itself changes no code; fixes start only after the user chooses them.

Neighbors: a security audit is `../../code-security-review/GUIDE.md` (this audit notes obvious security gaps and hands them over); reviewing a single change is phase 7 of `../../engineering-workflow/GUIDE.md`; staging a large cleanup is `large-refactors.md`.

## 1. Agree the scope and the load

- **Scope:** whatever the user named (repository, package, directory). If they named nothing, take the repository and decide where to spend depth.
- **Load assumption:** a script one person runs now and then, an internal tool, a public service with concurrent users, a nightly job over millions of rows. Ask when it is unclear; otherwise write down your assumption. Every scale finding is judged against this load and no larger one.
- **Orient with the map:** `../../codebase-map/scripts/map_codebase.py` gives entry points, routes, fan-in, cycles and files nothing imports. Then read the README, build and deploy configuration, dependency manifests, CI workflows and the test layout.
- **Follow the main flows** from where data enters to where it is stored and where it leaves. Read every line of the paths that are expensive to get wrong: payments, permissions, writes and deletes, scheduled jobs, state shared between processes, parsers of outside input.
- **Large codebases:** spend depth on those paths and on hotspots (big, widely imported, frequently changed files; the churn command is in the codebase-map guide), skim the rest, and keep a list of what you skipped.

## 2. Run what the project already checks

On a clean tree and without changing anything, run the test suite (with coverage if it is configured), the type checker and the linters. A failure or new warning is itself a finding, with the output as its evidence. Never run deploy, migration or publish steps, or anything that reaches shared or production systems.

Static analyzers propose candidates; you decide. Use what is installed, or ask before installing:

| Signal | Python | JavaScript / TypeScript | Go | Rust | Any language |
|---|---|---|---|---|---|
| Unused code | `vulture` | `knip` (files, exports) | `staticcheck` (U1000), `deadcode` | compiler `dead_code` warnings | |
| Unused or undeclared dependencies | `deptry` | `knip` (dependencies) | `go mod tidy -diff` (Go 1.23+) | `cargo machete`, `cargo udeps` | |
| Copy-paste duplication | | | | | `jscpd` |
| Complexity (a lead only) | `radon cc -s`, Ruff `C901` | ESLint `complexity` | `gocyclo` | Clippy `cognitive_complexity` | |

## 3. Where to look, in priority order

| Priority | Area | Look for |
|---|---|---|
| 1 | Wrong answers and crashes | Boundary inputs: nothing, a single item, the final item, maximum sizes, rounding and currency, time zones and daylight saving, text encodings. Callers that ignore something a function can return or raise. One business rule coded in two places with different results |
| 2 | Lost or corrupted data, obvious security gaps | Exceptions caught and dropped; multi-step writes with no transaction, or in an order that leaves bad state when a step fails; outside input used unchecked; credentials in source; routes with no visible permission check. Anything that may be exploitable goes to the code security review |
| 3 | Breaks under the assumed load | A read, check, then write sequence that two requests can interleave; a query inside a loop over records; collections, caches or queues with no bound; nested loops over growing input; work that every instance repeats; in-memory state several processes must agree on; network calls with no timeout (`resilience.md`, `performance.md`) |
| 4 | Untested risk | Code where a silent mistake is expensive (parsers, money, permissions, migrations, concurrency) and no test would fail if it broke. Name the one test that would protect it; a coverage percentage is not the goal |
| 5 | Slowness people feel | A slow path that runs often at the assumed load is a finding; micro-optimizations go under Optional |
| 6 | Code that costs more than it gives | Unreachable code and options nobody sets; two helpers with the same job (say which to keep); a dependency replaceable by the standard library or a few lines; a layer with one implementation that adds indirection and serves no test; near-duplicates that must always change together; a module mixing unrelated responsibilities (split where responsibilities separate; length alone is no reason) |

## 4. Make each finding hold up

- **Show how it fails.** Every finding names the input or situation and the wrong outcome it produces. Without one it is at most an open question in the report.
- **Dead-code claims need a search.** `git grep` the name everywhere (code, tests, fixtures, configuration, templates) and think about indirect uses: plugin registries, routes looked up by name, reflection, package exports. The map's list of unimported files only suggests where to look (codebase-map, step 4).
- **Demonstrate when it is cheap and safe:** a failing test in a scratch branch or copy, a query plan on a local database, one timing command run twice. Mark each finding *demonstrated* or *reasoned*.
- **Deliberate limits are not defects.** If a comment or ADR records the limit and when to revisit it, leave it out unless the assumed load is already past it.
- **Fixes stay small:** the least change that removes the failure, ideally one that removes code. No new layers, frameworks or settings. Style preferences and vague concerns stay out of the report.

## 5. The report

Write for someone who has never opened this code: everyday words, and a short definition the first time a technical term appears.

1. **Summary:** what the code is for, the scope you covered and the load you assumed, in a few sentences.
2. **Findings,** grouped by the severity scale of `../../engineering-workflow/references/verification-and-review.md` (Blocker, Should fix, Optional) and numbered in one sequence across the groups, so the user can pick them by number. Keep the list to roughly twenty and say how many smaller ones you dropped.
3. **Checks run:** each command and its result, including failures that predate the audit.
4. **Not covered:** parts you skipped, and checks that could not run, as `NOT VERIFIED: <check> - <why> - confirm with <command>`.
5. **Bottom line:** whether the code is in good shape, or which finding to start with.

A finding looks like this:

> **3. Two clicks can refund an order twice** · Blocker · demonstrated
> `payments/refunds.py:88-104`. `issue_refund()` looks for an existing refund, calls the payment provider, then stores the refund.
> - **Case:** two requests that arrive within the provider's response time both find no refund, so the provider pays out twice. Two concurrent calls in a scratch test reproduce it.
> - **Smallest fix:** a unique constraint on `refunds.order_id`, and an idempotency key derived from the order ID on the provider call (`api-contracts.md`, idempotency).
> - **Cost of leaving it:** duplicate refunds that finance has to reverse by hand.

## Done when

- [ ] Scope, assumed load and skipped parts are stated.
- [ ] The project's tests, type checks and linters ran, or are marked `NOT VERIFIED` with the reason.
- [ ] Every finding has a location, a failing case, the smallest fix, the cost of leaving it and an evidence label.
- [ ] No code was changed. Fixes the user picks go through the engineering workflow, each with a test that fails first.
