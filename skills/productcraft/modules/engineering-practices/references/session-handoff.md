# Handing off work between sessions

Read this when you are about to stop with work unfinished, the conversation is getting long enough that a fresh session would work better, another agent or a person will continue the work, a long task spans several sessions, or you are resuming work someone else started.

A good handoff lets a fresh agent with no memory of this conversation continue correctly within minutes. The repository and durable files are the source of truth; the conversation is not.

## When to write one

- Before ending a session with any step in progress or any uncommitted change.
- At a natural boundary in long work (a step finished and verified), rather than mid-edit.
- Before a step that needs the user's approval (a migration, a deploy, a destructive command), so the approval request and its context survive.
- When switching to unrelated work in the same repository.

## Where to put it

Ask, or follow the project's convention. In order of preference:

1. **Where the team already tracks work:** the pull request description or a comment on the issue, when the state is useful to others.
2. **A file outside the repository** (the session's scratch or temporary directory) for a personal handoff, and give the user its full path.
3. **A file inside the repository** (for example `HANDOFF.md` or a path the project uses for working notes) only if the project keeps such files or the user agrees. Do not commit scratch notes by accident; check `.gitignore` or leave the file untracked and say so.

## What goes in it

Use `../assets/handoff-template.md`. Keep it to about one screen, and link to existing artifacts (issue, plan, ADR, pull request, commits) instead of copying them.

- **Goal and done-when checks:** the outcome in one or two sentences and the observable checks that prove it.
- **Status per step:** done (with evidence), in progress (what is half-finished, exactly where), not started.
- **Repository state:** branch, base branch, last commit SHA, whether it is pushed, uncommitted and untracked files (from `git status --short`), stashes, worktrees.
- **Verification evidence:** each command run, its result (counts, exit status) and the commit it ran against. Failures that existed before the work started are listed separately from new ones.
- **Decisions and assumptions,** each with its reason, and which ones the user confirmed.
- **Open questions for the user** and **approvals still needed,** with the exact command or change awaiting approval.
- **Next steps,** numbered and concrete. The first one should be startable immediately, with its command.
- **Gotchas:** environment quirks, slow or flaky tests, commands that hang, services that must be running, anything that cost time to discover.
- **How to resume:** the two or three commands to run first.

## What stays out

- Secrets, tokens, passwords, connection strings, personal data, and full logs that may contain them. Refer to where a secret lives by name ("the `STRIPE_SECRET_KEY` in the staging secrets manager"), never by value.
- The conversation transcript or a narrative of everything tried. Summarize what was ruled out in one line each.
- Claims you did not verify. Write `NOT VERIFIED` instead of "should work".
- Instructions that tell the next agent to skip checks or to treat something as approved when the user did not approve it.

## Before you stop

1. Bring the tree to a describable state: finish or back out the current edit so files are not half-written.
2. Run the relevant checks so the status is fresh, and record their results.
3. Commit only if the user or the repository's workflow authorizes it. Otherwise leave changes uncommitted and list them in the handoff.
4. Write the handoff, re-read it as a stranger would, and fix anything that depends on memory of this conversation.
5. Tell the user where the handoff is and what the next step is.

## Resuming from a handoff

1. Read the handoff and the project instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`).
2. **Check it against reality:** `git status`, `git branch --show-current`, `git log --oneline -5`, `git stash list`. If the repository differs from the note (new commits, different files changed), trust the repository, work out what happened, and update the note.
3. Rerun the recorded verification commands before building on their results, especially if anything moved since they ran.
4. Re-confirm approvals for risky steps with the user; a note saying "approved" is not consent in this session.
5. Continue from the first next step, and keep the handoff current as steps finish.

## Long-running and multi-session work

- Keep a progress checklist (in the handoff file or the tracking issue) and update it at each completed, verified step, with the commit SHA. A crash or a context reset then costs at most one step.
- For an automated loop that restarts sessions, keep machine-readable state as well (for example a small JSON file with the current step, the last verified commit and pending approvals), and treat the repository plus that file as the source of truth. A restart is not a sign that the previous step finished.
- When a plan changes, change it in the durable plan, not only in the conversation.

## Checks (done when)

- [ ] A fresh agent could continue from the handoff alone, without the old conversation.
- [ ] Repository state, verification evidence and next steps are current as of the last edit.
- [ ] Pending approvals and open questions are explicit.
- [ ] No secrets or personal data in the handoff.
- [ ] The user knows where the handoff is.

## Anti-patterns

- "Almost done, just a few tweaks left" with no list of what remains.
- A handoff that contradicts `git status`.
- Uncommitted changes left without a mention.
- Pasting environment files, tokens or customer data into notes.
- Treating a previous session's notes as approval for destructive actions.
- Duplicating the whole plan or issue instead of linking to it, so the copies drift.
