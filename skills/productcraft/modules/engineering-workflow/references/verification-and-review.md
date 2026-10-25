# Verification, self-review and code review

Read this before you report work as done, when you review your own diff, when you ask someone else to review it, and when review feedback arrives.

## Find the commands that count

CI defines what "passing" means for the project, so start there and mirror its steps locally where that is safe (never its deploy, publish or release steps).

- `grep -nE "run:|script:" .github/workflows/*.yml .gitlab-ci.yml 2>/dev/null` lists the commands CI runs.
- Then package scripts (`npm run`), `Makefile` targets, `tox`/`nox` sessions, `cargo` and `go` commands, and anything `CONTRIBUTING.md` says to run.
- Note required services (database, cache, queue). Use the project's own local setup (a compose file, test containers) when it exists and the user allows it.

## Claims and the evidence they need

| Claim | Evidence required | Not enough |
|---|---|---|
| Tests pass | The suite command, run after your last edit: exit 0 and counts ("212 passed, 0 failed, 3 skipped, all skips pre-existing") | An earlier run, one file's run, "should pass" |
| Bug fixed | The original reproduction now behaves correctly, and a regression test seen red without the fix and green with it | The code changed where the bug seemed to be |
| It builds | The build command exits 0 | Lint passing; no errors shown in an editor |
| Types and lint clean | The project's type-check and lint commands report zero errors | Checking only the files you edited, unless that is how the project runs them |
| Feature works | Each done-when check confirmed: a test, a script, a screenshot, or a request against a local server | Unit tests green while the feature path never ran |
| UI looks right | Screenshots of the affected states at the target widths (see UI Distiller) | The CSS compiled |
| Faster | Before and after numbers for the same input on the same machine, repeated | "Should be faster" |
| Migration is safe | Applied and rolled back on a local or test copy, with data checks | The migration file exists |
| A helper finished its task | You read its diff and reran its checks | Its report says "done" |

Read the output, not just the last line:

- Zero tests collected is a failure, not a pass.
- More skipped tests than before needs an explanation.
- New warnings and deprecations belong in the report.
- Pipes can hide a failing exit code: use `set -o pipefail`, or check `${PIPESTATUS[0]}`, when you pipe test output through `tail` or `tee`.

## Baselines and failures you didn't cause

For Standard and Deep work, run the suite once on the untouched tree (or the base branch) before changing anything and note what already fails. Afterwards, compare. Report pre-existing failures by name and leave them alone unless asked. Never write "all tests pass" while any test fails, whoever caused it.

## When you can't verify

Write it in this form: `NOT VERIFIED: <check> - <why it couldn't run here> - confirm with <exact command>`. Typical reasons are missing credentials, external services, hardware, an unavailable platform or a job too long to run. A mock standing in for the real dependency doesn't turn the check into a verified one; say what the mock covered and what it didn't.

## Self-review checklist

Read `git diff <base>...HEAD`, plus any untracked files you are adding, from top to bottom as if a colleague wrote it.

- **Scope:** does it do what the done-when list says, and nothing else?
- **Edge inputs:** empty, one, many, maximum size, zero and negative numbers, null or missing fields, duplicates, non-ASCII text, time zones and daylight-saving changes, two requests at once, a retried request (is the operation idempotent?).
- **Failure paths:** what happens when a dependency fails or times out? Are errors reported with useful messages? Is anything swallowed?
- **Callers:** did a signature, return value or raised error change? Are all callers updated?
- **Data:** are writes ordered safely, inside a transaction where needed? Is the migration reversible? Can a failure halfway lose or corrupt data?
- **Security touch points:** input validation, authorization on new endpoints, secrets, personal data in logs. Run the matching LaunchGuard baseline controls.
- **Tests:** would they fail if the code were wrong? Use the mutation check in `test-first.md`.
- **Hygiene:** `diff_scope.py` WARNs resolved or explained; no leftover debugging; clear names.
- **Docs:** README, changelog, configuration examples and API descriptions updated where the project keeps them.

The author's own review misses things the author cannot see. On Deep work, add a fresh reviewer.

## Requesting a review

**When:** Deep work; risky Standard changes (money, auth, data deletion, concurrency, public interfaces); after a hard bug fix; before merging into a shared branch.

**Who:** a human, or a fresh subagent if the platform supports one. One reviewer per change is usually enough; a reviewer should not start further reviewers.

**What to send:** the brief in `../assets/review-brief.md`: the goal and done-when checks, the base and head commits (`git merge-base origin/main HEAD`, `git rev-parse HEAD`), a few lines on what changed and why, the risky areas and what you are unsure about, what you verified with which commands and what you didn't, and constraints such as behavior that must not change. Hand over the diff range or a diff file, not your conversation history; the reviewer should judge the work, not your reasoning about it.

**What to ask for:** a read-only review (inspect with `git show`, `git diff` and `git log`, and run code only in a separate worktree or copy); for each finding, the file and line, a concrete situation where it goes wrong, the severity and the smallest fix; a list of what the reviewer could not check; and a verdict.

**Severity scale:**

- **Blocker:** wrong results, a crash, data loss, a security hole, a broken caller, failing tests, an unmet done-when check.
- **Should fix:** risky logic without a test, an unhandled failure path, misleading names, duplication that must change in lockstep, a real performance problem at the expected load.
- **Optional:** style, naming preferences, small simplifications.

## Handling review feedback

1. Read all of it before changing anything. Restate any item you are unsure about in your own words.
2. If an item is unclear, ask before touching anything related to it; items often depend on each other.
3. Check each claim against the code. Does that caller exist? Can the value really be null there? Is the path reachable? Reviewers lack context too.
4. Decide per item: fix it, defer it with a tracked note, or decline it with evidence (a test, a pointer to code, a compatibility constraint, or a `git grep` showing that nothing uses the feature being requested). Disagreements about product or architecture choices go to the user.
5. Fix blockers first, then quick fixes, then larger changes. Every behavior fix gets a test; rerun the suite after the batch.
6. Reply per item with what changed and where, or why not. Keep it factual; skip flattery and blanket agreement.
7. On a code host, answer each comment in its own thread when the platform supports that (`gh pr view <number> --comments` reads them), rather than in one top-level comment.
