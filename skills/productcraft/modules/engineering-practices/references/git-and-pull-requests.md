# Git and pull request hygiene

Read this when you commit, branch, open or update a pull request, resolve a conflict, tag a release or write release notes. When to integrate a finished branch, and how, is covered in phase 9 of `../../engineering-workflow/GUIDE.md`; parallel worktrees in its phase 8.

## History safety

These need the user's explicit permission every time: `git push --force` (use `--force-with-lease` even then, and only on your own branch), rewriting pushed history, `git reset --hard`, `git clean -fdx`, `git checkout -- .` or `git restore .` over uncommitted work, deleting branches, pushing to protected branches, creating or moving tags, publishing packages.

- Undo merged work with `git revert <sha>`, which adds a commit instead of rewriting history.
- Recover lost commits with `git reflog` before concluding they are gone.
- Before any operation that could discard work, check `git status` and `git stash list`, and tell the user what would be lost.

## Branches

- Branch from an up-to-date default branch (`git fetch origin && git switch -c <name> origin/main`).
- Keep branches short-lived and focused on one change; prefer feature flags to long-running branches for unfinished work.
- Follow the project's naming convention; if there is none, `<type>/<short-description>` (`fix/invoice-rounding`) is common and readable.
- Keep up with the base branch: rebase your own unshared branch; on a shared branch, merge the base in instead of rewriting others' history.

## Commits

- **One logical change per commit,** and each commit builds and passes tests, so `git bisect` and `git revert` work on it.
- **Separate kinds of change:** formatting, mechanical renames, refactors, dependency updates and behavior changes in separate commits (ideally separate pull requests for large ones).
- **Stage deliberately.** Use `git add -p` or explicit paths, then read `git diff --staged` before every commit. Look for debug output, unrelated files, generated files and secrets.
- **Never commit** secrets or `.env` files, build output, dependency folders, large binaries (use Git LFS if the project does), or editor settings the team does not share. Commit generated files only if the project does (lockfiles, some migration files, checked-in generated clients).
- **Messages explain why.** A subject line in the imperative mood, about 50 characters and at most 72, no trailing period; a blank line; then a body wrapped at about 72 characters explaining the reason, notable consequences and anything a reviewer would otherwise ask. Reference the issue.

```
Round invoice totals per line before summing

Totals were rounded once at the end, so invoices with many discounted
lines could differ by a cent from the PDF, which rounds per line.
Rounding per line matches the PDF and the accounting export.

Fixes #482
```

- If the project uses a commit convention (Conventional Commits prefixes such as `fix:` and `feat:`, a ticket prefix, sign-off lines), check `git log --oneline -20` and follow it. Add attribution or trailers only as the project or the user requires.

## Hooks

- Pre-commit hooks should take seconds: format and lint only staged files (for example husky with lint-staged, the `pre-commit` framework, lefthook). Slow checks such as the full test suite belong in a pre-push hook or CI.
- CI remains the real gate; hooks are a convenience for fast feedback.
- Never bypass hooks with `--no-verify` without the user's agreement. If a hook fails, fix the cause.

## Pull requests

- **Size:** small enough to review carefully in one sitting, typically a few hundred lines of hand-written change. Split larger work into a sequence: preparatory refactors, then the feature behind a flag, then cleanup; or stacked pull requests, each reviewable on its own.
- **Open early as a draft** when direction matters, so problems surface before the work is large.
- **Self-review the diff in the review tool** before requesting review; you will spot leftovers you missed locally.
- **Description template:**

```markdown
## What and why
<the user-visible or system change, and the reason; link the issue>

## How
<approach and key decisions; alternatives rejected and why; where to start reading>

## Evidence
<commands run and their results; tests added; screenshots or recordings for UI; before/after numbers for performance>

## Risk and rollback
<what could break and for whom; one-way or reversible; migrations and their order; flags; how to roll back>

## Out of scope / follow-ups
<what this deliberately does not do>
```

- Keep the description true as the pull request changes; reviewers read it first.
- **Respond to every review comment:** fix it, or explain with evidence why not. Push follow-up commits during review rather than rewriting the branch, so reviewers can see what changed; tidy the history before merge only if the project wants that, or let squash-merge do it.
- **Merge strategy** follows the repository's setting. With squash merges, the pull request title and description become the commit message, so write them as one.
- Use `CODEOWNERS` (or the platform's equivalent) for review routing on sensitive paths when the project maintains it.

## Resolving conflicts

- Understand both sides before editing: `git log --merge -p -- <file>` shows the commits that touched the file on each side; read their messages and linked pull requests.
- Show the common ancestor in conflict markers (`git config merge.conflictStyle zdiff3`, Git 2.35+) to see what each side changed.
- Keep both intents where they are compatible. Where they truly conflict, choose the one matching the goal of the merge, state what was dropped and why, and ask the user if the choice affects behavior.
- Regenerate lockfiles and generated files with their tools instead of merging them by hand.
- Search for leftover markers (`git diff --check`, `git grep -n '^<<<<<<<\|^>>>>>>>'`), then run the full checks before completing the merge or rebase. A conflict resolution can compile and still break both sides' tests.
- If you are unsure, it is acceptable to stop and ask; `git merge --abort` or `git rebase --abort` returns to the previous state, but tell the user before discarding resolution work.

## Versions, tags and changelogs

- Anything with consumers carries a version. Libraries and APIs follow Semantic Versioning 2.0.0: MAJOR for incompatible changes, MINOR for compatible additions, PATCH for compatible fixes. If consumers could observe a behavior change, treat it as breaking.
- Keep one source of truth for the version (the tag or the manifest, not both edited by hand) and let the release process derive the rest.
- Mark releases with annotated tags (`git tag -a v1.4.0 -m "Release 1.4.0"`). Tags are created and pushed only with the user's permission, normally by the release pipeline.
- Update the changelog in the same pull request as the change (see `docs-and-decisions.md`).

## Repository hygiene files

- `.gitignore` covers dependencies, build output, environment files, logs, coverage and OS files for the stack.
- `.gitattributes` normalizes line endings (`* text=auto`) and can mark generated files (`linguist-generated=true`) so reviews collapse them.
- A pull request template in `.github/pull_request_template.md` (or the platform's equivalent) when the team wants consistent descriptions.
- Branch and worktree cleanup, issue and pull request triage, labels, issue forms and `CODEOWNERS`: `repository-hygiene.md`. Before a first public release: `open-sourcing.md`.

## Checks (done when)

- [ ] Every commit is one logical change, builds, and has a message that explains why.
- [ ] `git diff --staged` was reviewed before each commit; no secrets, debug output or unrelated files.
- [ ] The pull request description covers what, why, evidence, risk and rollback, and matches the final diff.
- [ ] Conflicts were resolved by intent and the full checks ran afterwards.
- [ ] No history rewrite, force-push, tag or branch deletion happened without explicit permission.

## Anti-patterns

- "WIP", "fix", "updates" as commit messages; one commit mixing a refactor, a feature and formatting.
- A 3,000-line pull request with a one-line description.
- Resolving conflicts by taking "ours" or "theirs" wholesale without reading either side.
- Force-pushing over a shared branch or over review history without telling anyone.
- Committing `.env` files or build artifacts.
- A breaking change released as a patch version.
