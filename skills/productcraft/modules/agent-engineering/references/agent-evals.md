# Evaluating agents and harness changes

Read this before you claim that an agent, model, prompt, tool set, skill or harness change "works better", when choosing between coding agents or models for a team, and when setting up regression checks for an agent system. Evaluating single-call LLM features (RAG answers, extraction, judges) is in `../../ml-engineering/references/llm-evaluation.md`; evaluating an Agent Skill's triggering and value is in `../../builder-tools/references/skill-evaluation.md`. This reference adds what is specific to multi-step agents: tasks with environments, repeated trials, reliability metrics and cost per success.

## Evaluate first, then change

1. Write the capability checks (what the change should make possible) and the regression checks (what must keep working) before touching the harness.
2. Run the current setup to get a baseline and its failure signatures.
3. Make one change.
4. Re-run the same tasks with the same settings and compare paired results.

A change without a baseline is an anecdote.

## Build the task suite

- **Source tasks from real work:** closed issues with the commit that fixed them, bugs reproduced as failing tests, recurring chores, past incidents. Add synthetic tasks only to fill gaps, and label them.
- **Each task is self-contained:** a pinned base commit or snapshot, the prompt exactly as a user would write it, the environment (dependencies, services, fixtures), and the checks.
- **Checks decide pass or fail without the agent's opinion:** a test command, a build, a schema validation, a diff against expected output, a query result. Add boundary checks: no deleted or skipped tests, no edits outside the allowed paths, no changes to the checker.
- **Cover the space:** easy, typical and hard tasks; tasks that should end in "cannot do this safely" or a question; tasks with misleading context; at least one long-horizon task if the agent will run long.
- **Size:** 20 to 50 tasks find gross differences. Small differences need many more tasks and repeats (see below). Keep a held-out split you do not tune against.
- **Prefer private tasks.** Public benchmarks may appear in training data; a high public score says little about your codebase.
- **Version the suite with the code** and record which version produced each score.

## Run conditions

- **Fresh isolated environment per trial:** a new worktree or container from the pinned commit, reset databases and caches, no leftover memory or files from earlier trials (`../../agent-safety/references/isolation.md`).
- **Same limits for every variant:** turn limit, wall-clock limit, token or cost limit, tool set, network policy. A variant that wins because it was allowed to run longer has not won.
- **Record versions:** the model identifier the API actually returned, harness commit, tool and SDK versions, prompt and skill versions.
- **Separate infrastructure failures** (timeouts of the harness itself, provider outages, rate limits, environment setup failures) from agent failures. Log them in their own column, re-run them, and never score them as wrong or silently drop them.
- **Keep full traces** per trial: prompts, tool calls and results, final diff, check output, usage. A surprising score must be explainable without re-running.
- **Get approval for paid runs.** Agent evaluations spend real money on every trial; estimate the cost from a pilot (`cost-caching-and-routing.md`) before a large run.

## Graders

1. **Code checks first:** tests, builds, linters, type checks, schema and diff checks. Deterministic and cheap.
2. **Model-based grading** only for properties code cannot check (quality of an explanation, adherence to a style guide), with a rubric of atomic pass or fail criteria, calibrated against human labels as described in `../../ml-engineering/references/llm-evaluation.md`. A model grader never replaces a failing test.
3. **Human review** of a sample of transcripts and diffs, especially passes: an agent can pass the checks in ways you would not accept (special-casing the test input, weakening an assertion, hard-coding output).

## Trials and reliability metrics

Agents are not deterministic. Run each task several times (at least 3; more for close comparisons) and report what the repeats show.

- **pass@k:** the probability that at least one of k attempts succeeds. From n trials with c successes, the unbiased estimate is `1 - C(n-c, k) / C(n, k)`. Use it when a person or a reliable checker will pick a passing attempt, and retries are cheap.
- **pass^k:** the probability that all k attempts succeed, estimated as `C(c, k) / C(n, k)`. Use it for unattended work, where every run has to be right. It falls quickly: a task that passes 70% of the time passes three runs in a row only about a third of the time.
- **Per-task consistency** (c out of n) shows which tasks are flaky; average pass rates hide them.
- **Cost per successful task:** total spend on the task (including failed trials and retries) divided by successes. Also wall-clock time, turns, tool errors, and how often a person had to intervene.
- **Regressions:** list tasks that passed before and fail now, by name. A higher average with new failures on important tasks is not an improvement.

## Comparing variants

- **Paired:** same tasks, same number of trials, same limits. Compare per task.
- **Test the difference.** For pass or fail per task, use an exact McNemar test on paired outcomes; for scores, cost or time, a paired bootstrap:

```bash
python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py mcnemar --csv outcomes.csv --a-col baseline_pass --b-col candidate_pass
python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py bootstrap --csv per_task.csv --a-col cost_a --b-col cost_b --lower-is-better
```

- **Expect wide intervals.** With 30 tasks, a difference of two or three tasks is usually noise. Say so instead of declaring a winner.
- **Report both sides:** what got better, what got worse, by task type, plus cost and time. A variant that solves one more task at three times the cost may not be the right choice; that is the owner's call, with the numbers in front of them.
- When many variants are tried, confirm the winner on the held-out split before adopting it.

## Regression checks for harness changes

- A fast smoke subset (the most important 10 to 20 tasks, code checks only) runs on every change to prompts, instruction files, tools, skills, model or routing.
- The full suite runs before a release and on a schedule, because hosted models can change behavior under the same name. Pin model versions where the provider allows it, and note the drift risk where it does not.
- Thresholds live in configuration: fail when a required task fails, or when the pass rate drops more than the noise band below the last accepted run.
- Re-check harness components when the model changes: run with and without each scaffold (planner, context resets, separate judge) and keep only what still helps.

## Reading failures

Group failed trials by cause before changing anything:

| Failure class | Typical fix location |
|---|---|
| Wrong or missing tool call | Tool descriptions, tool set, a step enforced in code |
| Looped or gave up | Stop conditions, observations, error messages that say what to change |
| Misread the task | The task prompt or the agent's instruction files |
| Passed by gaming the check | Boundary checks, the checker itself |
| Ran out of budget | Context bloat, missing tools, a task too large for one run |
| Claimed success that the checks deny | Verification step in the harness; never trust the final message |

Fix the largest group's cause, re-run, and check that other groups did not grow.

## Done when

- [ ] A versioned suite of real tasks with deterministic and boundary checks, and a held-out split, exists.
- [ ] Trials run in fresh isolated environments with equal limits; infrastructure failures are separated.
- [ ] Results report per-task consistency, pass@k or pass^k as appropriate, cost per success, time and regressions.
- [ ] Comparisons are paired and tested, with intervals, and the report says when a difference is within noise.
- [ ] A smoke subset gates harness changes; the full suite runs before release.
