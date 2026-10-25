# Parallel subagents and worktrees

Read this when the platform can run subagents or create worktrees and the work might be split. Parallel work saves wall-clock time and keeps your own context focused, but every helper rereads code, costs tokens and adds integration work. Use it when the pieces are truly independent.

## Decide whether to split

Split only when all of these hold:

- The pieces share no files and no mutable resources (database schema, ports, caches, global configuration).
- Each piece can be explained in a self-contained brief and verified on its own.
- The time saved outweighs the cost of briefing, checking and integrating.

| Good candidates | Keep together |
|---|---|
| Failing tests in unrelated areas with different error messages | Failures that may share a cause: investigate them together first |
| Read-only investigation of several subsystems | A bug whose cause is still unknown |
| The same mechanical edit across separate packages (one helper can do the whole batch) | Changes to the same files |
| Tests for separate modules with clear interfaces | Steps that depend on each other's interfaces: define the interface first, or run them in sequence |
| A fresh read-only review of a finished change | Small tasks where the brief takes longer than the work |

Never run two writers in the same checkout at the same time.

## Write a self-contained brief

A helper starts with none of your context. Give it exactly what it needs:

- **Goal:** one sentence.
- **Context:** relevant paths, the error output, interfaces and decisions already made. Not your conversation history.
- **Scope:** the files or directories it may change, and the ones it must not.
- **Constraints:** no new dependencies, no destructive git commands, no pushes, no editing tests just to make them pass, and when to stop and report instead of guessing.
- **Done when:** the commands to run and the results expected.
- **Report back:** a status (done, done with doubts, or blocked and why), a short summary, files changed, commands run with their results, and open questions.

Example:

> Fix the two failures in `tests/test_invoice_pdf.py` (output below). Context: PDF rendering moved to `billing/pdf.py` in commit `a1b2c3d`; the font-loading path is the likely suspect. You may change `billing/pdf.py` and `tests/test_invoice_pdf.py` only. Don't change other tests, add dependencies or push. Done when `pytest tests/test_invoice_pdf.py -q` passes and `pytest tests/billing -q` still passes. Report: status, root cause in two sentences, the diff summary, the commands with their output tails, and anything you were unsure about. If the cause is outside these files, stop and report instead of editing.

If the platform lets you choose models, give mechanical, fully specified tasks to a cheaper model, and judgment-heavy tasks and reviews to a stronger one.

## Isolation

- Read-only helpers can share your checkout.
- Writers each need their own worktree on their own branch, or strictly separate file sets worked in turn.
- When tests use shared resources, give each helper its own ports, temporary directories, database names and cache directories (for example `PORT=0`, a per-helper `TMPDIR`, a database-name suffix).

## Worktrees

- **Native tool first.** If the platform has its own worktree feature, use it; it tracks and cleans up what it creates.
- **Already isolated?** If `git rev-parse --git-dir` and `git rev-parse --git-common-dir` resolve to different paths, you are in a linked worktree, unless `git rev-parse --show-superproject-working-tree` prints a path, which means a submodule.
- **Create:** `git worktree add -b <branch> ../<repo>-<topic> <base>`. A sibling directory needs no ignore rule. Put worktrees inside the repository only if the project has that convention and the directory is ignored: `git check-ignore -q .worktrees || echo "not ignored"`.
- **Set up:** install dependencies the way the project documents (ask first if installing needs network access the user hasn't approved), then run a baseline test in the new worktree. Report a failing baseline before starting work.
- **Inspect:** `git worktree list`.
- **Remove** only worktrees you created, after their work is merged or handed over: `git worktree remove <path>`. If git refuses because of modified or untracked files, show them (`git -C <path> status --short`) and ask; never add `--force` on your own. `git worktree prune` clears stale entries.
- Tell the user about new branches and worktrees so they know where work lives, and follow any preference they have stated about where worktrees go.

## Integrate the results

1. **Verify each result yourself.** Read its diff (`git -C <worktree> diff <base>...HEAD`) and rerun its checks. A report is a claim, not evidence.
2. **Check for overlap.** Compare `git diff --name-only <base>...HEAD` across results; overlapping files need careful manual integration.
3. **Bring results in one at a time** (merge or cherry-pick), running the relevant tests after each.
4. **Run the full suite** on the combined tree.
5. **Spot-check for repeated mistakes:** helpers given similar briefs often share the same wrong assumption.
6. **Clean up** the worktrees and branches you created, as described in `finishing-a-branch.md`.

## Long plans, one fresh helper per step

A Deep plan with many dependent steps can be carried out by handing each step to a new helper, one after another. Each helper starts with a clean context, and yours stays free for coordination. It pays only when the platform supports helpers and the plan is long enough to strain a single context; a handful of small steps is cheaper to do yourself.

1. **Strictly in sequence.** One step at a time in the same checkout or worktree; never two implementers at once.
2. **Note the commit before each step** (`git rev-parse HEAD`) and review the step as the range from that commit. A step may leave several commits, so comparing with the previous commit alone misses work.
3. **Brief from a file.** Copy the step from the plan, exact values included, into a brief file. Add only what the step cannot know: interfaces created by earlier steps and how you resolved anything ambiguous. Leave out the story of earlier steps.
4. **Short replies, full reports on disk.** Ask the helper to write its full report (changes, commands and results, doubts) to a file beside the brief, and to keep its reply to a few lines: outcome, commit hashes, test result, open questions. Long replies from every step fill your own context.
5. **Review each step before the next starts.** First compare `git diff <commit>..HEAD` with the brief, not with the helper's summary: everything asked for, nothing extra. Then review it for soundness with the self-review checklist in `verification-and-review.md`, and rerun the step's check yourself.
6. **Limit the fix rounds.** Send findings back to the same helper. If two rounds do not produce a clean step, take it back: fix it yourself, split it, or ask the user whether the step itself is wrong, and note which.
7. **Only you start agents.** A helper that launches its own reviewer duplicates the review you are about to do.
8. **Progress on disk.** Keep the progress note from `clarify-and-plan.md` (step, start and end commits, status, open findings). After a context reset, rely on it and `git log`, and never redo a step whose commits already exist.
9. **One review of the whole branch at the end,** by a fresh reviewer over `git diff <plan base>...HEAD`, briefed with `../assets/review-brief.md`. Problems that span steps are invisible in step-by-step reviews.

## Fresh reviewer

A read-only reviewer with a clean context is one of the most useful helpers: it sees the diff without your assumptions. Brief it with `../assets/review-brief.md` and the diff range. One reviewer per change; the reviewer reports findings and does not edit the code or start other reviewers.
