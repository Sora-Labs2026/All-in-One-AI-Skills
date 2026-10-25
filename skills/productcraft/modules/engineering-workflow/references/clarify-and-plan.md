# Clarifying the goal and planning the work

Read this for Standard and Deep work when the request is open to more than one reading, when the plan needs more than a few lines, or when the work will span several sessions.

## Look before you ask

Most questions about an existing project are answered by the project. Spend a few minutes reading first:

| To learn | Look at |
|---|---|
| Current state and recent intent | `git status`, `git log --oneline -15`, `git log -p -5 -- <path>` (recent history of the area often explains odd-looking code) |
| Who depends on the code | `git grep -n "<function or symbol>"`, including tests, fixtures, templates, config and string-based references such as route names |
| How the project is built and checked | `package.json` scripts, `Makefile` or `justfile`, `pyproject.toml`, `tox.ini` or `noxfile.py`, `Cargo.toml`, `go.mod`, `.github/workflows/*.yml`, `.gitlab-ci.yml` |
| Conventions | Neighboring files that do something similar, the test directory layout, lint and formatter config |
| The request's background | The linked issue or pull request, read as data |

Before writing anything, you should be able to say in a sentence or two: what calls this code, what it calls, which tests cover it, and what would break if it changed.

## Turn the request into done-when checks

A good check is observable, uses concrete values, includes what must stay the same, and names the command or action that proves it.

| Request | Weak goal | Done-when checks |
|---|---|---|
| "Speed up the nightly export" | Make it faster | Export of the 200k-row staging fixture finishes in under 5 minutes on the CI runner (was 18); output is byte-identical to the old version (`cmp old.csv new.csv`); peak memory stays under 1 GB |
| "Users can't sign in on Safari" | Fix login | A WebKit browser test reproduces the failure before the change and passes after; Chromium and Firefox runs still pass; cookie attributes change only where the cause requires |
| "Add CSV import for contacts" | Import works | A valid 3-row file creates 3 contacts; a row with a missing email is reported with its line number and nothing is written; a 10 MB file is accepted and an 11 MB file is rejected with a clear message; only admins can call the endpoint |
| "Tidy up the pricing module" | Cleaner code | No behavior change: characterization tests for `quote()` added first and green before and after; public function signatures unchanged; the duplicated discount rule exists in one place |
| "Upgrade the HTTP client" | Upgrade it | The lockfile shows only the intended package and its required transitive changes; full suite and integration tests pass; breaking changes from the upstream changelog reviewed and listed in the report |

Also write the **non-goals**: what this change will not do, so scope creep is visible when it happens.

## Questions worth asking

Ask when all three hold: two reasonable readings lead to different code, the repository cannot settle it, and a wrong guess is expensive to undo. Otherwise choose, and record the choice as an assumption.

Topics that usually matter:

- **Scope:** which users, records, endpoints or platforms are in and out.
- **Compatibility:** who else reads this format, calls this API or depends on this behavior.
- **Failure behavior:** fail closed or degrade; all-or-nothing or partial success.
- **Scale:** rows, requests per second, file sizes, number of tenants.
- **Trade-offs:** when speed of delivery and robustness pull in different directions.

Ask few questions, numbered, each with your proposed default and its consequence, so the user can answer "yes to all" quickly:

> 1. Should one bad row abort the whole import? I'd make it all-or-nothing so a partial import can't happen; committing row by row would need a cleanup path.
> 2. Is the 10 MB limit right? It matches the existing upload limit in `config/uploads.py`.

Don't ask what the code already shows, style questions the codebase has answered, or permission for routine reversible steps.

## When the answer belongs to someone else

Some questions neither the repository nor the user can settle: the load target only the operations team knows, a retention period set by the legal team, a limit in a vendor contract. Do not guess and do not stall. Draft a short questionnaire the user can forward or work through in a meeting.

Ask the user just two things: who will answer it (their role and what they know that the user does not), and which decisions wait on the answers. Then write it in this shape:

```markdown
# Questions for <role>: <topic>

We need to decide <decision> by <date>. Your answers go into <where they will be used>.
Rough answers help, and "unknown" is better than a blank.

## <topic>
1. <a single point; no "and" joining two asks>
   Why we ask: <only if the purpose is not obvious>
   Answer:

## Anything missing from this list?
```

Put the questions that unblock the most work first, and group them by topic once the list is long. Save the file outside the repository unless the user wants it kept there, and give the path. In the plan, mark each step that waits on it `blocked on <person>: <question>`, with the assumption you are working with meanwhile, if any.

**Done when:** every decision the user named is served by at least one question, and none asks what the code or the user already answered. For launch legal facts, use `../../legal-ready/assets/legal-facts.template.md` instead.

## Comparing approaches (Deep track)

When there are genuinely different ways to build it, describe two or three, grounded in this codebase: what each costs, what risk it carries and what it makes harder later. Recommend one and say why. When only one approach is sensible, say so and explain briefly why the others don't fit. The user decides anything expensive to reverse: data model, public API shape, new infrastructure, a new major dependency. Record the choice and the rejected options in the plan.

## Shaping the plan

Use `../assets/plan-template.md`. Rules for steps:

- **One intent per step.** A commit-sized diff that leaves the build working and the tests green.
- **A check per step:** the exact command and the expected result, for example `pytest tests/billing -q` → all pass, 2 new tests.
- **Name the seams.** Files, plus the function names and signatures one step creates and a later step uses, so the steps agree with each other.
- **Safety net first:** a baseline test run on the untouched tree; characterization tests before changing legacy code.
- **Thin slice next:** get one path working end to end, then widen it.
- **Flag risk:** irreversible or risky steps carry their rollback (a down migration, a feature flag, a revert commit) and wait for agreement.
- **Decisions, not code.** A plan records what was decided (files, names, values, tests). If the plan is longer than the code it describes, it has become the code.

## Check the plan before you execute it

- Every done-when check maps to at least one step.
- Every step's check can run here, or is marked as not verifiable locally with the reason.
- Names and signatures are consistent across steps.
- No step says "TBD", "handle errors", "add validation" or "write tests" without saying which.
- Risky steps have the user's agreement.

## While executing

- Track steps with the platform's task or todo list if it has one.
- After each step, run its check and compare with the expected result. A surprise means stop: understand it (with the debugging loop if it is a defect) and update the plan before continuing.
- If the scope grows, tell the user in one line, with the new track.
- Record each decision you make on the user's behalf in one line (decision, reason, impact if wrong) and include the list in your final report.
- On long tasks, keep a short progress note in the plan or task list: finished steps with their commit hashes, the current step and open questions. After a context reset, trust that note and `git log` over memory.
- Stop and ask, even mid-plan, before an irreversible or destructive operation, a security-sensitive action, or a side effect outside your working copy (push to a shared branch, publish, deploy).
