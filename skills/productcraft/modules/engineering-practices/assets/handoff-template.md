# Handoff: <short task name>

Written: <date and time, time zone> · Author: <agent or person> · For: <who continues, or "next session">

## Goal
<One or two sentences: the outcome.>

Done when:
- [ ] <observable check 1, with the command that proves it>
- [ ] <observable check 2>

Links: <issue> · <plan> · <pull request> · <relevant ADR>

## Status
| Step | State | Evidence or exact position |
|---|---|---|
| 1. <step> | done | <commit SHA, test command and result> |
| 2. <step> | in progress | <file and function; what is finished, what is not> |
| 3. <step> | not started | |

## Repository state
- Branch: `<branch>` (base `<base>`), last commit `<sha>`, pushed: <yes/no>
- Uncommitted or untracked: <paths from `git status --short`, or "none">
- Stashes and worktrees: <list, or "none">

## Verification
| Command | Result | Ran against |
|---|---|---|
| `<command>` | <passed 212, failed 0 / exit 0> | <sha or "working tree"> |

Failures that existed before this work: <list, or "none">
Not verified, and why: <list>

## Decisions and assumptions
- <decision> because <reason>. Confirmed by user: <yes/no>
- Assumed <assumption>; if wrong, <what changes>.

## Needs the user
- Question: <question, with the default that will be used if unanswered>
- Approval: <exact command or change, its risk, and its rollback>

## Next steps
1. <first concrete step, startable now> — `<command>`
2. <next step>
3. <next step>

## Gotchas
- <environment quirk, flaky test, slow command, required local service>

## Resume with
```bash
git status && git log --oneline -5
<the main test command>
```
