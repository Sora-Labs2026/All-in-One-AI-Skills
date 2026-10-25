# CI/CD and release

Read this when you create or change a CI workflow, speed up a pipeline, handle a failing or flaky check, add a feature flag, plan a deploy, staged rollout or rollback, or prepare release notes.

The agent prepares pipelines, flags and plans. Deploying, changing production flags or rollout percentages, editing branch protection and publishing releases need the user's explicit permission.

## Pipeline shape

A pull-request pipeline answers "is this change safe to merge?" as quickly and reliably as possible.

1. **Install exactly what the lockfile says:** `npm ci`, `pnpm install --frozen-lockfile`, `yarn install --immutable`, `uv sync --locked`, `poetry install` after `poetry check --lock`, `cargo build --locked`, `go mod download` then `go mod verify`.
2. **Static checks first,** because they are cheap: formatter in check mode, linter, type checker (`tsc --noEmit`, `mypy`, `cargo clippy -- -D warnings`).
3. **Unit tests,** then **build,** then **integration tests** against real services started in the job (database and cache containers with health checks), then **end-to-end tests** for the few flows that matter most.
4. **Supply-chain and policy checks:** dependency audit, license policy, migration checks (`migration_check.py --strict` on new migration files), bundle-size budget.
5. Upload test reports, coverage and failure artifacts (screenshots, traces) so a red build can be understood without rerunning it.

Run independent stages as parallel jobs and stop early on the first hard failure.

## Keep it fast

A common target is feedback on a pull request in about ten minutes. When a pipeline is slower, in rough order of payoff:

- Cache dependency downloads keyed on the lockfile hash (for example `actions/setup-node` with `cache: npm`, or `actions/cache`).
- Split lint, type check, tests and build into parallel jobs; shard large test suites across runners.
- Run only what a change can affect: path filters for documentation-only changes, affected-project builds in monorepos (Nx, Turborepo, Bazel, Gradle build cache).
- Remove repeated work: install once per job, reuse build outputs between jobs as artifacts, avoid rebuilding containers that did not change (layer caching).
- Move very slow suites to the merge queue or a scheduled run, but keep them required before release.
- Measure the pipeline: time per job and the slowest tests, so you speed up what is actually slow.

## Keep it trustworthy

- **Required checks** on the default branch, enforced with branch protection or rulesets, and at least one review before merge. A merge queue keeps the default branch green when many pull requests land at once.
- **Deterministic builds:** pinned tool versions (`.nvmrc`, `.python-version`, `rust-toolchain.toml`, `packageManager` in `package.json`), frozen installs, no network calls to services you do not control in unit tests, fixed seeds and clocks in tests.
- **Flaky tests are bugs.** Record them, quarantine with an owner and an issue so they stop blocking others, then fix or delete them. Automatic reruns may hide flakiness only if every rerun is counted and reported.
- **Never weaken a gate to get green:** no disabled lint rules, skipped or deleted tests, lowered coverage or budget thresholds, `continue-on-error: true` or `|| true` without the user's agreement and a written reason. Fixing the code is the default.
- **Feed failures back precisely:** read the failing job's log, reproduce the exact command locally, fix, rerun the same command, then push.

## Secure the pipeline

Workflows run with credentials and are an attack path. Check at least:

- Least-privilege tokens: in GitHub Actions set `permissions:` explicitly (for example `contents: read`) at workflow or job level.
- Third-party actions pinned to a full commit SHA, with the version in a comment, updated by a dependency bot.
- No secrets for workflows triggered by forks; avoid `pull_request_target` combined with checking out the pull request's code.
- Cloud access through short-lived OIDC federation rather than long-lived keys stored as secrets.
- Untrusted input (branch names, PR titles, issue text) never interpolated directly into shell `run:` steps; pass it through environment variables.
- Production secrets never available to pull-request jobs.

Deeper CI and supply-chain review belongs to `../../code-security-review/GUIDE.md` and LaunchGuard control #20.

## Build once, deploy many

- Build one immutable artifact per commit (container image referenced by digest, package, bundle), stamp it with the commit SHA and version, and promote that same artifact through staging to production. Rebuilding per environment means production runs something that was never tested.
- Configuration and secrets come from the environment, not from the artifact.
- Expose the running version (a `/version` endpoint, a startup log line, an error-tracker release tag) so anyone can tell what is deployed.
- Use preview environments per pull request where the platform supports them, and a staging environment that resembles production in configuration, if not in size.
- Keep infrastructure and pipeline definitions as code, reviewed like application code.

## Deploy strategies

- **Rolling:** replace instances gradually; needs every version pair to coexist (API and schema compatibility).
- **Blue/green:** bring up the new version beside the old and switch traffic at once; fast rollback by switching back, costs double capacity during the switch.
- **Canary:** send a small share of traffic to the new version, compare it with the old one, then widen.
- In every strategy, schema changes follow expand/contract (`data-and-migrations.md`): expand before the deploy, contract after it has been stable.

## Feature flags

Flags separate deploying code from releasing behavior.

| Kind | Purpose | Lifetime |
|---|---|---|
| Release | Hide unfinished or newly shipped work | Days to weeks; remove after full rollout |
| Operational kill switch | Turn off an expensive or risky path during an incident | Long-lived, documented in the runbook |
| Experiment | Compare variants | Until the decision; then remove |
| Permission or plan | Gate features by customer or plan | Long-lived; this is product logic and belongs in the entitlement model |

- Every flag has an owner, a purpose and, for release flags, a removal date. Removing a flag means deleting the dead branch, its tests and its configuration.
- Evaluate flags on the server for anything that affects security, money or data; client-side flags are visible and editable by users.
- Default to the safe behavior when the flag service is unreachable, and cache flag values with a bounded staleness.
- Test both states of every flag in CI. Avoid nesting flags; each combination is another product to test.
- Use the project's flag client; OpenFeature is a vendor-neutral API many providers support.

## Progressive rollout

Write the plan before the deploy and agree on it with the user:

```
Change:            <what is being released, flag name>
Stages:            internal users -> 1% -> 5% -> 25% -> 50% -> 100%
Bake time:         <for example 1 hour per stage, 24 hours before 100%>
Watch:             error rate, p95/p99 latency, saturation, <business signal>, new error types
Advance when:      canary within agreed tolerance of baseline, e.g. errors <= baseline + 10%, p95 <= baseline + 20%
Roll back when:    errors > 2x baseline, p95 > baseline + 50%, any data-integrity problem, any security issue
Rollback method:   <flag off | redeploy previous artifact digest | other>, owner, expected time
Schema state:      <expand already applied; no contract until this rollout is complete and stable>
Communication:     <who is told at each stage and on rollback>
```

- Assign users to cohorts by a stable hash of the user or account ID, so a person does not flip between versions.
- Compare canary against the current baseline at the same time, not against last week.
- Avoid starting rollouts right before nobody will be watching (end of day, before holidays) unless the change is low risk and automated rollback exists.

## Rollback

- Know the fastest lever before deploying: turning a flag off (seconds), redeploying the previous artifact (minutes), a forward fix (longest, riskiest under pressure).
- Rollback must never require reversing a schema change; that is what expand/contract buys.
- Write the rollback command into the plan and, where possible, practice it in staging.
- After a rollback, keep the evidence (dashboards, logs, timeline) and record what happened before trying again.

## Measuring delivery

Four delivery measures are widely used to see whether the process is improving: how often you deploy, how long a commit takes to reach production, what share of deploys cause a failure needing remediation, and how long recovery takes. Use them to find bottlenecks, not to rank people.

## Release notes

Versioning, tags and changelog entries are covered in `git-and-pull-requests.md`. Release notes describe user impact, call out breaking changes with migration steps, and list deprecations with their removal dates.

## Checks (done when)

- [ ] The pipeline ran green on the final commit, and no gate was weakened (or the user agreed in writing).
- [ ] Installs are frozen to the lockfile and tool versions are pinned.
- [ ] Workflow permissions are least-privilege and third-party actions are pinned.
- [ ] Each new flag has an owner, a default-safe fallback, tests for both states and a removal date.
- [ ] A rollout and rollback plan exists for risky changes, and the user approved it before anything touched production.

## Anti-patterns

- Skipping, deleting or muting tests to unblock a merge.
- A different build for each environment.
- Releases that need the database rolled back to undo.
- Flags that stay forever; flags evaluated in the browser for paid or sensitive features.
- Big-bang releases without a staged rollout or a written rollback.
- Rerunning a red pipeline until it passes without recording the flake.
- `permissions: write-all`, unpinned third-party actions, secrets available to fork pull requests.
