# Multi-agent orchestration: roles, task graphs, merge queues and terminal panes

Read this when work is split across several agents beyond a single helper: a planner, builders and reviewers working from one spec; a dependency graph of work units; parallel workers in separate worktrees with a merge queue; agents in terminal panes; or a batch of similar records processed by agents. Deciding whether to split at all, briefing a helper and integrating results are in `../../engineering-workflow/references/parallel-work.md`; handing one task to a hosted agent is in `../../engineering-workflow/references/delegating-to-coding-agents.md`. Read those first; this reference adds the structure for larger fan-outs.

## When it pays, and what it costs

More agents multiply token spend, review load and integration risk. The aim is the least parallelism that gets the work done in time. Use a multi-agent structure when:

- the spec is written and stable enough to split into units with checkable acceptance criteria;
- the units touch mostly separate files and resources;
- someone (a person or a single integrator agent) has the capacity to review and land every unit.

If the requirements are still moving, or the cause of a bug is unknown, keep the work in one context.

## Roles

| Role | Does | Must not |
|---|---|---|
| Planner | Turns the spec into work units with dependencies and acceptance checks | Write implementation code |
| Builder | Implements one unit in its own worktree, with its tests | Edit acceptance checks or other units' files |
| Reviewer or judge | Checks a unit against its acceptance checks and the spec, in a fresh context | Review code it wrote; fix what it reviews |
| Integrator | Rebases, runs tests and lands units one at a time; resolves conflicts | Land a unit whose checks fail |
| Operator (a person) | Approves the plan, decides on blocked units, approves merges and anything consequential | |

One agent may hold several roles in a small run, except that the reviewer is never the author of what it reviews.

## From spec to task graph

Each work unit records:

- `id` and a one-line title;
- the spec sections it implements;
- `scope`: the paths it may change, and paths it must not;
- `depends_on`: ids of units whose output it needs;
- acceptance checks: commands and expected results;
- risk tier: low (isolated change, deterministic tests), medium (several files, behavior change), high (schema, auth, money, performance, security, public API);
- a rollback note.

Decomposition rules:

- Prefer fewer, cohesive units; every boundary is a merge risk.
- Minimize file overlap between units that run at the same time; list unavoidable overlaps explicitly.
- Keep tests with the implementation they test, in the same unit.
- Add a dependency only where code really depends on another unit's output; define shared interfaces in an early unit.
- Check the graph before running: no cycles, every dependency exists, overlapping scopes flagged.
- **The plan is the highest-leverage review point.** The operator approves the units, scopes and checks before any builder starts.

Run the graph in layers: units with no unmet dependencies run in parallel; the next layer starts when its dependencies have landed.

### Depth by risk

| Tier | Stages |
|---|---|
| Low | Implement with tests, run checks, review |
| Medium | Short research note, plan, implement with tests, run checks, spec review and code review, fix round |
| High | As medium, plus a security or data review and a final review of the integrated result by a fresh reviewer; operator sign-off |

Stages of one unit share its worktree and pass artifacts as files (research note, plan, report), each stage in its own context.

## Merge queue

1. Rebase the unit branch onto the current integration branch.
2. Conflict: evict the unit with the conflicting files and diff captured, and send it back to its builder with that context.
3. Run the unit's checks and the integration tests on the rebased branch. Failure: evict with the test output.
4. Pass: land it (fast-forward or merge per the project's convention), delete the unit branch and worktree, and re-run integration tests.
5. Units with overlapping files land one at a time, rebasing each time.

Never land a unit while one of its dependencies is failing. Re-entering units get the eviction context, not a blind retry; after two failed re-entries, narrow the unit or hand it to the operator. After the last unit, run the full suite and one fresh review of the whole branch, because problems that span units are invisible in unit reviews.

Landing on a shared branch is a consequential action. By default the queue prepares and verifies, and the operator approves the merge or the merge batch (`approval-gates.md`).

## A board everyone can read

Keep work visible outside chat transcripts, in the project's tracker or a Markdown board (`../../engineering-workflow/references/markdown-task-boards.md`).

| State | Leaves the state when |
|---|---|
| Backlog | Acceptance checks are written |
| Ready | An owner and a branch or worktree are assigned |
| Running | The work and a short report exist on the branch |
| Review | Checks, diff review and risk review pass |
| Blocked | The blocker has an owner and a next action |
| Landed | Merged into the integration branch |
| Dropped | The reason is recorded |

Each card names the owner, scope, branch, acceptance checks, merge gate and link to its report. Warning signs: many agents with no owner or merge gate; useful output that exists only in a transcript; cards without acceptance checks; two agents writing the same files.

## Status and liveness

Each worker writes a small status file (state, current step, last heartbeat time, last commit, blocker). The orchestrator polls status files on an interval rather than blocking on a worker. A stale heartbeat is investigated (inspect the worker's output, its last tool call) before anything is killed; stop only processes the run started.

## Workers in terminal panes

A terminal multiplexer such as tmux gives each worker a visible pane:

```bash
RUN=feature-x
git worktree add -b "$RUN/api" "../repo-$RUN-api" main
git worktree add -b "$RUN/ui"  "../repo-$RUN-ui"  main
mkdir -p ".runs/$RUN/api" ".runs/$RUN/ui"          # task.md, status.md, report.md per worker; keep .runs/ ignored by git
tmux new-session -d -s "$RUN" -n api -c "../repo-$RUN-api"
tmux new-window  -t "$RUN" -n ui -c "../repo-$RUN-ui"
tmux list-windows -t "$RUN"                         # what is running
tmux capture-pane -p -t "$RUN:api" | tail -40       # read a worker's recent output without attaching
tmux kill-session -t "$RUN"                         # only the session this run created, after work is saved
```

Start each worker's agent in its own pane with the task file as its brief and a tool allowlist. Keep the main pane for the orchestrator. Keep the number of panes to what you can review; each pane is a full agent session with its own spend. Remove worktrees as described in `../../engineering-workflow/references/parallel-work.md`, and never with `--force` on your own.

## Other models as advisors

When workers from other tools or providers take part, keep one writer per file set. Advisory models get read-only context and return plans or diffs as text; the writer treats their diffs as untrusted prototypes and reviews them like an outside pull request. Sending code to another provider needs the owner's consent for that transfer (`verification-patterns.md`).

## Batches of similar records

When agents process a finite set of similar records (updating many tickets, migrating many files, enriching many rows):

1. Define the set, ordering, exclusions, the unit of completion and the done signal, and check that the selection covers the source criteria (not only that selected records are valid).
2. Prepare shared inputs once (mapping, tool contract, reference data) and record their versions; reuse them only while those versions hold.
3. For each record: read its current version, check permission and prerequisites, apply the exact intended change with a conditional write (version check, transaction or lock), then verify the outcome. Shared preparation is not shared authorization.
4. Carry forward per-record outcomes: verified, failed with no effect, not attempted, or unknown. Remove a record from the remaining set only after a verified success.
5. Reconcile unknown outcomes before any retry. On resumption, revalidate shared inputs and never replay completed effects.
6. Stop and replan when the tool contract or a shared input changes; hold dependent work, continue independent work.

## Done when

- [ ] The operator approved a task graph whose units have scopes, dependencies, acceptance checks and risk tiers.
- [ ] Every unit was built in its own worktree, reviewed in a separate context, and landed through the queue with checks.
- [ ] The integrated branch passed the full suite and one whole-branch review; merges followed the approval policy.
- [ ] Board, status files and reports show who owned what, what landed and what is blocked.
- [ ] Sessions, worktrees and branches the run created were cleaned up or handed over.
