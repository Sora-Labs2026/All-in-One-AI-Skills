# Engineering Practices

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Shape *what* production code should look like once a change reaches beyond a single function: contracts other code depends on, schemas holding real data, calls that can fail, latency users feel, telemetry on-call needs, pipelines and releases, dependencies, written decisions, large restructurings, TypeScript types, git history and work handed to the next session. Each topic has one focused reference. Read only the ones the change touches.

**How the work is done** (goal and done-when checks, planning, test-first, root-cause debugging, smallest change, verification, self-review, subagents and worktrees, finishing a branch) lives in `../engineering-workflow/GUIDE.md`. This module does not repeat it. Security review lives in `../launchguard/GUIDE.md`, `../code-security-review/GUIDE.md` and `../credential-shield/GUIDE.md`.

## When to activate

- The change adds or alters an API, schema, event, public function or module boundary, a database table or migration, a network call or background job, a CI workflow, a release or feature flag, a dependency, a TypeScript type model, or a refactor spanning many files.
- The user asks about performance, logging, metrics, tracing, alerts, rollout, rollback, ADRs, documentation, commit or PR quality, or how to pause and resume work.
- **Not for** a copy edit, a style tweak or a change inside one function with no callers outside it. Those follow the Quick track of the workflow module.

## Ground rules

1. **Start from the project, not this file.** Read the existing conventions, configs and versions first: OpenAPI or schema files, migration tool and folder, CI workflows, `tsconfig.json`, lockfile, logger, feature-flag client, ADR folder, commit style (`git log --oneline -20`). Follow them. Propose a different convention only with a reason, and ask before changing it.
2. **Check the installed version.** Library and framework APIs differ between major versions. Read the version from the lockfile before writing code against an API, and use that version's documentation when it is available. If it is not, say which version you assumed.
3. **Compatibility before cleverness.** Anything another process, client, team or past release can observe is a contract. Before changing it, list who depends on it and how the change stays compatible during rollout.
4. **Measure before and after.** Performance, reliability and pipeline-speed claims need numbers from the same command under the same conditions. No number, no claim.
5. **Reversible by default.** Prefer changes that can be turned off or rolled back in minutes: additive schema steps, flags, small commits. Mark anything irreversible (drops, data rewrites, public removals, history rewrites) and ask before doing it.
6. **Hands off production.** Do not run migrations, deploys, flag changes, rollouts, load tests or `EXPLAIN ANALYZE` against production or shared systems, and do not push, tag or publish, without explicit permission. Prepare the exact commands and hand them over instead.
7. **Tools advise, evidence decides.** Linters, audits, analyzers and the bundled migration checker produce candidates. Report what actually ran and what it showed; mark the rest `NOT VERIFIED` with the reason.
8. **Do not lower the bar to get green.** No new `any`, `@ts-ignore`, disabled lint rules, skipped tests, loosened thresholds, `continue-on-error` or `|| true` without the user's agreement and a written reason.

## Pick the references

| The change touches | Read | Minimum check before calling it done |
|---|---|---|
| HTTP, GraphQL or RPC endpoints, webhooks, events, public functions, module boundaries | `references/api-contracts.md` | Each change classified compatible or breaking; one error shape; list endpoints paginated; non-idempotent creates handle retries |
| Tables, columns, indexes, constraints, migrations, backfills | `references/data-and-migrations.md` | Every step works with both the old and new app version; `scripts/migration_check.py` run on new migration files; down path or forward-only reason written |
| Calls to databases, services, queues or third-party APIs; error handling | `references/resilience.md` | Every outbound call has a timeout; retries only on transient errors with backoff and jitter; failure path tested |
| Slowness, load, caching, query plans, bundle size, Core Web Vitals | `references/performance.md` | Baseline and after numbers from the same method; change kept only if it beats the noise |
| Logs, metrics, traces, alerts, dashboards, runbooks | `references/observability.md` | Structured events with a request or trace ID; no secrets or personal data; alerts are symptom-based with a runbook |
| CI workflows, build speed, deploys, feature flags, rollout, rollback | `references/ci-and-release.md` | Pipeline green with no weakened gate; rollout and rollback plan written; flags have an owner and removal date |
| Adding, upgrading, auditing or removing packages | `references/dependencies.md` | Need justified; lockfile committed and diff reviewed; changelog read for upgrades; audit result recorded |
| READMEs, ADRs, API docs, code comments, changelogs, agent instruction files | `references/docs-and-decisions.md` | Commands in docs were run; ADR written for costly-to-reverse choices; docs updated in the same change |
| Renames, extractions, framework migrations, legacy restructuring across many files | `references/large-refactors.md` | Behavior pinned by tests first; each step green and mergeable; no behavior change mixed into mechanical commits |
| TypeScript types, `tsconfig`, runtime validation, type-level APIs | `references/typescript.md` | `tsc --noEmit` clean; untrusted input parsed by a schema; no new unchecked casts |
| Commits, branches, pull requests, conflicts, tags, release notes | `references/git-and-pull-requests.md` | Each commit one logical change; PR states what, why, evidence, risk and rollback |
| Pausing, ending or handing over unfinished work; resuming someone else's | `references/session-handoff.md` | State file lets a fresh agent resume without the old conversation; claims re-verified on resume |

Templates: `assets/adr-template.md` for decision records and `assets/handoff-template.md` for session state files.

Several topics often apply together. A new endpoint backed by a new column typically needs `api-contracts`, `data-and-migrations`, `resilience` and `observability`. Read them in the order the change will ship: schema first, then the code that uses it, then its telemetry and release.

## Topic essentials

Use these when the reference is not needed. Open the reference when a bullet raises a question.

### Contracts
- Additive changes are safe. Removing, renaming, retyping, newly requiring or re-meaning anything is breaking: version it or deprecate first, measure remaining usage, then remove.
- One error format across the API (Problem Details, RFC 9457, unless the project has its own), stable machine-readable codes, no internals in bodies.
- Paginate every list with a default and a maximum page size, a deterministic order and, for large or busy collections, a cursor.
- Every create or charge that a client may retry honors an idempotency key or is documented as unsafe to retry.

### Data and migrations
- Never rename or retype in place on a live table. Expand (add), migrate (dual-write, backfill), contract (remove) across separate releases.
- Backfills run in small, resumable, throttled batches outside the schema migration, and finish with a count query that proves completion.
- Enforce invariants in the database (NOT NULL, UNIQUE, FK, CHECK). Index what queries filter and join on, including foreign keys.

### Resilience
- Every network call has a timeout, and the caller's deadline is longer than the sum of what it waits on.
- Retry only transient failures, only idempotent operations (or with an idempotency key), with capped exponential backoff and jitter, at one layer.
- Decide the degraded behavior for each dependency. Never report success for an action that did not complete.

### Performance
- Name the metric and target, measure a baseline, profile, fix the largest cost, re-measure the same way, keep or revert.
- Look first for N+1 queries, missing or unusable indexes, unbounded result sets, oversized payloads and heavy work on the request path or main thread.
- For web pages: LCP at most 2.5 s, INP at most 200 ms, CLS at most 0.1, judged at the 75th percentile of real visits.

### Observability
- Write down the questions on-call will ask, then emit only signals that answer them.
- Structured logs with stable event names and a request or trace ID; metrics as rate, errors and latency histograms with bounded labels; traces propagated across every hop and queue.
- Page on user-visible symptoms tied to an objective; everything else goes to a ticket or a dashboard.

### CI and release
- Fast, deterministic pipeline: frozen installs, cached dependencies, parallel jobs, required checks on the default branch.
- Build one artifact and promote it. Separate deploy from release with flags; roll out in stages with abort criteria agreed in advance.
- The fastest rollback is written down before the deploy, and it never requires undoing a schema change.

### Dependencies
- Prefer what the platform or project already has. Vet a new package for maintenance, license, size, install scripts and exact name.
- Commit the lockfile, install frozen in CI, upgrade one major at a time after reading its changelog, and triage audit findings by reachability.

### Docs and decisions
- Document why, not what. An ADR records a decision that is costly to reverse, with the options considered and the consequences.
- Docs change in the same PR as the behavior they describe, and every command in them has been run.

### Large refactors
- Pin behavior with tests, change structure in small green steps, and keep mechanical changes in their own commits and PRs.
- Use automated, syntax-aware tools for wide renames. Migrate callers through a parallel path, then delete the old one.

### TypeScript
- `strict` on, `tsc --noEmit` in CI (bundlers strip types without checking them).
- Parse untrusted data with a schema and infer types from it. Prefer `unknown`, narrowing, discriminated unions and `satisfies` over `any`, `as` and `!`.

### Git and pull requests
- Small branches, one logical change per commit, messages that explain why. Review your staged diff before every commit.
- No force-push, history rewrite, `reset --hard` or branch deletion without permission. Resolve conflicts by intent and rerun the checks.

### Session handoff
- Before stopping, write a short state file: goal, status per step, branch and commit, uncommitted files, commands run with results, decisions, open questions, next steps.
- On resume, trust the repository over the note: check `git status` and rerun the recorded checks before building on them.

## Migration safety helper

`scripts/migration_check.py` is a read-only, standard-library checker for SQL migration files. It never connects to a database, edits files or uses the network. It flags destructive drops and truncates, in-place renames and type changes, NOT NULL columns without defaults, table-rewriting defaults, index and constraint builds that lock writes, `CONCURRENTLY` inside a transaction, unbatched full-table updates and deletes, missing lock timeouts and up migrations without a down file. Rules specific to PostgreSQL or MySQL apply only with that `--dialect`.

```bash
python3 <productcraft>/modules/engineering-practices/scripts/migration_check.py db/migrations/20261025_add_status.sql
python3 <productcraft>/modules/engineering-practices/scripts/migration_check.py --dialect mysql --format json migrations/
python3 <productcraft>/modules/engineering-practices/scripts/migration_check.py --list-rules
```

`<productcraft>` is the folder where the ProductCraft skill is installed. Run it on the migration files the change adds, not the whole history. A reviewed, intended finding (such as the final drop of an expand/contract change) is acknowledged with a comment above the statement, `-- migration-check: allow DROP_COLUMN <reason>`, and is still listed. `--strict` exits 1 while open HIGH or WARN findings remain. A clean result is not proof of safety; timing on a production-sized copy is.

## What to report

Add these to the workflow module's report and to `../../assets/review-template.md`:

- References used, and for each the minimum check from the table above: met, not met or `NOT VERIFIED` with the reason.
- Compatibility notes: who consumes the changed contract or schema, and how old and new versions coexist during rollout.
- Numbers for any performance or pipeline claim: baseline, result, method and run-to-run spread.
- Migration checker output summary and how each open finding was handled.
- Commands the user still has to run (migrations, deploys, flag changes), with their rollback.

## Working with other ProductCraft modules

- `../engineering-workflow/GUIDE.md`: tracks, planning, test-first, debugging, verification, review, parallel work and finishing a branch. It decides how to proceed; this module shapes what the result looks like.
- `../launchguard/GUIDE.md` and `../launchguard/references/security-baseline.md`: authorization, input validation, response trimming, headers and dependency scanning are security controls; check the matching control when a contract, query or dependency changes (for example #7 lock record access, #13 parameterize queries, #17 trim API responses, #20 scan dependencies).
- `../code-security-review/GUIDE.md`: deep, code-level review of whether a change is exploitable, including CI and supply-chain paths.
- `../credential-shield/GUIDE.md`: rate limiting and abuse defense for login and account recovery; do not build a competing throttle here.
- `../interaction-feedback.md` and `../ui-rules.md`: honest pending and error states in the interface when a backend call is slow or degraded.
- `../language-choice.md`: a new service or performance-critical component whose language is not fixed yet.
