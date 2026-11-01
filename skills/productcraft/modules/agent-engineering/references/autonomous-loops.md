# Autonomous loops: goals, budgets, stop conditions and checkpoints

Read this before you design, start or review any loop in which an agent repeats work without a person approving each step: a fix-until-green loop, an iterate-until-the-reviewer-passes loop, a nightly maintenance job, a watcher that acts on change, or a scheduled agent run. Approval gates for consequential actions are in `approval-gates.md`; parallel workers and merge queues are in `multi-agent-orchestration.md`.

A loop does not make the model smarter. It repeats whatever the goal and the checker reward, faster than anyone can watch. Most of the design work is deciding what "done" means and what stops the loop when it is not getting there.

## Decide whether to build a loop at all

Build one only when all of these hold. If any fails, do the work by hand or as a single supervised run.

- The task recurs, or one run needs many similar iterations.
- Success can be checked by a program: a test command, a build, a schema validation, a reconciliation against an external total, a diff against a golden file.
- The agent has tools that actually run that check and see the result.
- The expected cost of the iterations fits the budget the owner will approve.

A repository that has no tests, no reference outputs and no lint gate does not deserve a loop yet. Build those first.

## Write a goal a machine can decide

1. **Done-when is a command or a comparison**, not an adjective. "All 212 tests in `tests/` pass and `ruff check` exits 0" is decidable; "make the code clean" is not. Read the goal to someone outside the project: if they cannot run one command and say yes or no, rewrite it.
2. **Boundaries sit next to the goal.** List what the loop must not do to reach it: delete, skip or weaken tests; lower a coverage or quality threshold; edit the checker, its fixtures or CI configuration; widen permissions; touch files outside the scope. A goal without boundaries invites the agent to satisfy the letter of the check (Goodhart's law).
3. **Prefer reconciliation over self-assertion.** Anchor done-when to something the agent did not write: an upstream total, a golden sample, a contract test owned by another team, a production replay. "My new tests pass" is the weakest possible evidence.
4. **Front-load clarification.** An unattended agent will not stop to ask at 2 a.m.; it will guess and keep going. Resolve every open question before launch, and list the cases the loop must leave for a person (ambiguous fixes, anything outside scope) as explicit skip-and-report rules.
5. **Name the fallback.** What happens when the loop cannot reach the goal: stop, write a report, leave the branch unmerged.

## Pick the loop type

| Situation | Type | How it ends |
|---|---|---|
| A clear end state (tests green, batch processed, document complete) | Goal-seeking | Stops when the check passes, or a stop condition fires |
| A state to keep (dependency freshness, a health check, an inbox to triage) | Maintaining | Runs on a schedule; acts only when something changed; each run is itself bounded |
| Wait for an external event (CI finishes, a review arrives) | Watch with exit | Polls at a fixed interval, stops when the condition holds or the deadline passes |

For a maintaining loop, let a document or queue drive it: a file or tracker that lists open items, where people write the request column and the loop writes only the result column, and state moves forward only (`open` to `in progress` to `done` or `needs person`). The loop acts only when an item changed since its last run. The exit code of the checker is final: if the check says failed, the item is failed, whatever the agent's summary says.

## Choose a skeleton

- **Sequential steps with a fresh context each.** Each step is one headless agent invocation with a narrow prompt, its own tool allowlist, and files on disk as the only hand-over. Order matters; a failing step stops the chain (`set -euo pipefail` in a shell driver). This is the right default.
- **Plan, build, judge.** A planner writes the spec and decidable acceptance checks; a builder implements and may not edit the acceptance checks; an independent judge (CI, a test command, or a separate reviewer context) decides pass or fail and returns the failure reason. The judge is never the builder. Details: `verification-patterns.md`.
- **Separate cleanup pass.** When a builder over-produces (redundant tests of language features, defensive checks for impossible states, leftover debug output), add a focused cleanup step with its own check rather than piling negative instructions onto the builder prompt.

Every component of a harness encodes an assumption about what the model cannot do alone (needs a planner, needs context resets, needs a separate judge). Re-test those assumptions when the model changes, and remove scaffolding that no longer earns its cost.

## Budgets: every loop has all three

| Budget | Typical limits | Enforced where |
|---|---|---|
| Time | Wall-clock cap for the whole run; timeout per step and per tool call | The driver process (`timeout`, a deadline check before each step), not the prompt |
| Iterations | Maximum loop count; maximum fix rounds per item | The driver's counter |
| Tokens and money | Maximum tokens or currency for the run, per step where the platform supports it | The driver, from usage reported by the API or CLI; a provider-side spend limit as the backstop |

- Pick numbers from a measured pilot run (cost and time per iteration times the iterations you will accept), not from habit. Write them in the run plan with the owner's agreement.
- Check the budget before starting each iteration, and assume the next one costs as much as the most expensive so far.
- A token budget the model is told about (some APIs offer advisory task budgets) helps it pace itself; it does not replace a hard cap enforced outside the model.
- Count everything: retries, judge calls, review passes and cache writes all spend.
- Track spend with `../scripts/usage_cost.py` on the run's usage log (`cost-caching-and-routing.md`).

## Stop conditions beyond the budget

Stop and report when any of these fires:

- **Success:** the done-when check passes, and the boundary checks pass too.
- **No progress:** the measured distance to the goal (failing tests, open items, error count) did not improve over N consecutive checkpoints. Two or three is a common choice; agree it with the owner.
- **Same failure repeated:** the same error signature (test id plus message, or a normalized stack trace) appears twice after attempted fixes. Retrying with reworded prompts is not a strategy.
- **Plateau in scored loops:** a judge's score has not risen across several rounds.
- **Boundary breach:** the diff touches a forbidden path, deletes or skips tests, or changes the checker. Stop immediately; do not let the loop repair its own breach.
- **Environment failure:** authentication errors, quota exhaustion, a missing service. These are not model failures; stop and report instead of burning iterations.
- **External stop signal:** a stop file, a flag in the tracker, or a signal from the operator. Check it before every step.

When a loop stops on anything but success, it leaves a report: which condition fired, the evidence, the last good checkpoint, and what a person should look at.

## Checkpoints and resumability

- **State on disk, not in context.** A small machine-readable state file (current step, last verified commit, items done, items failed with reasons, budget spent, pending approvals) plus a human-readable progress note. The repository and the state file are the source of truth; a restart is not proof that the previous step finished.
- **One commit per verified step** on the loop's own branch, so a bad step is one revert. Record the commit before each step and review the step as the range from it.
- **Idempotent steps.** Re-running a step after a crash must not duplicate effects. For anything with outside effects, record the intent before acting and the outcome after; when the outcome is unknown (timeout, crash mid-call), reconcile by reading the real state before any retry, and never assume a failed read means a failed write.
- **Carry failures forward.** Feed the next attempt the captured error output and what was already tried, not just "try again".
- **Resume from state**, re-running the recorded checks before trusting them; never redo a step whose commit already exists.

The handoff format for people is in `../../engineering-practices/references/session-handoff.md`.

## Unattended and scheduled runs

- **Use a real scheduler** (cron, a systemd timer, a CI schedule) that starts a headless agent invocation in a workspace it owns. In-session schedulers end when the session ends. Set an overlap policy: skip a run while the previous one is still going.
- **Least privilege.** A tool allowlist per step (read-only for analysis steps), no blanket permission bypass, credentials scoped to the job and injected by name. Run in an isolated checkout or container without production credentials (`../../agent-safety/references/isolation.md`).
- **Monitor from outside the loop.** A wedged agent cannot report that it is wedged. A separate watchdog reads the state file and logs: last heartbeat, last checkpoint age, steps without a tool result, spend so far. Alert or kill on a stale heartbeat or budget breach.
- **Report every run**, success or not, to a place the owner reads.

## Roll out in stages

1. Run the loop body once by hand. This forces you to state exactly how the judge decides.
2. Run it supervised: the agent loops, a person watches the first few iterations and reads every diff.
3. Only then schedule it, with the budgets, stop conditions and approval gates in force, and keep reading its reports.

The more a loop rewrites its own rules, prompts or memory, the stricter the review it needs, not the looser.

## Write the run plan and check it

Before the first unattended run, write the plan as JSON (template: `../assets/run-plan.example.json`) and run:

```bash
python3 <productcraft>/modules/agent-engineering/scripts/run_plan_check.py run-plan.json
```

It reports a missing time or token-and-money budget, missing stop conditions, no checkpoint state file, consequential actions without an approval gate, approval that times out to "approve", permission bypass, payments without caps and allowlists, and secret-looking values in the plan. It checks the plan, not the running loop: the driver still has to enforce what the plan says.

## Review an existing loop

| Question | A "yes" means |
|---|---|
| Is done-when an adjective or an opinion? | It will spin or guess; make it decidable |
| Does the judge share context with the builder? | Self-grading; make the judge independent and deterministic |
| Is "all tests pass" the only gate? | It can delete tests; add boundaries |
| Does it rely on the agent asking mid-run? | It will not; front-load the questions |
| Is any limit enforced only by the prompt? | Move it into the driver |
| Can it push, merge, deploy, send, pay or delete without a person? | Add an approval gate (`approval-gates.md`) |
| Does it read instruction files or memory nobody maintains? | Stale context errs faster in a loop; review them |

## Done when

- [ ] The goal is decidable, with boundaries and a fallback, and open questions were settled before launch.
- [ ] Time, iteration and token-or-money budgets are enforced by the driver, with a provider-side limit as backstop.
- [ ] No-progress, repeated-failure, boundary-breach and external-stop conditions are implemented and tested once.
- [ ] State, commits and reports make every run resumable and auditable.
- [ ] Consequential actions go through an approval gate; `../scripts/run_plan_check.py` reports no errors.
- [ ] The loop ran by hand and supervised before it was scheduled.
