# Finishing a branch

Read this when the work is implemented and you are about to open a pull request, merge, or hand the branch back. Integration is the user's decision; your job is to leave the branch in a state where any choice is safe.

## Checks on the final tree

Run these on exactly the tree you are about to integrate. An earlier green run proves only the tree it ran on.

- [ ] `git status --short` shows only intended changes; untracked files are either added or deliberately left out.
- [ ] Full test suite, lint, type check and build, with commands and results recorded.
- [ ] `python3 <productcraft>/modules/engineering-workflow/scripts/diff_scope.py --git <base>...HEAD`: every WARN resolved or explained.
- [ ] No debug output, focused or skipped tests, commented-out code or local configuration in the diff.
- [ ] Docs, changelog and version updated where the project keeps them.
- [ ] Commits are logical and their messages explain why. Squash fixup commits only if the branch isn't shared and the user or project wants a tidy history.

If anything fails, fix it, or stop and report. Integration options come after a green tree.

## Confirm the base and bring it up to date

- **Find the base** from the plan, the user, or the branch's upstream: `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}`, or compare candidates with `git merge-base <candidate> HEAD`. If it is still unclear, ask; merging into the wrong base is expensive to undo.
- **Update** with `git fetch`, then merge or rebase following the project's convention. Rebase only branches nobody else uses, or with permission. Resolve conflicts by understanding both sides, never by taking one side wholesale, and rerun the checks afterwards.

## Choose how to integrate

If the user hasn't already said, offer:

1. **Open a pull request** (the usual choice for shared repositories).
2. **Merge locally into the base** (solo repositories, or when the user asks).
3. **Leave the branch** for the user to handle.

Throwing work away happens only on an explicit request. Before doing it, list exactly what will be lost (the branch, its commits, worktree files that exist nowhere else) and wait for a clear confirmation.

## Pull request

- Use the repository's template if it has one (`.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/`).
- Body: what changed and why; how it was verified (commands and results); risks, rollout and rollback; what is `NOT VERIFIED`; follow-ups; the linked issue.
- Push with `git push -u origin <branch>`, then open it with the host's CLI (for example `gh pr create --base <base> --title "<title>" --body-file <file>`) or its web page. Give the user the URL.
- Keep the branch and worktree until the pull request is merged; review fixes happen there.

## Local merge

```bash
git switch <base>
git pull --ff-only
git merge --no-ff <branch>        # or the project's merge style
<full test command>               # on the merged result, before deleting anything
git branch -d <branch>            # lowercase -d refuses to delete unmerged work
```

If the merged result fails, stop with the branch intact and investigate; nothing has been pushed yet.

## Never without explicit permission

| Action | Risk | Safer alternative |
|---|---|---|
| `git push --force` or `--force-with-lease` to a shared branch | Overwrites other people's work | `git fetch`, inspect, merge or rebase, then ask |
| Pushing directly to `main`, a release or a protected branch | Skips review | A pull request |
| `git branch -D` | Deletes unmerged commits | `git branch -d`, or ask |
| `git worktree remove --force` | Deletes files that exist only in that worktree | Show `git -C <path> status --short` and ask |
| `git reset --hard`, `git clean -fdx`, `git checkout -- .` | Destroys local work | `git stash push -u -m "<note>"`, then ask |
| Rewriting pushed history (amend, rebase, filter tools) | Breaks collaborators' clones | A new commit |
| Deploying, publishing a package, pushing release tags | Production impact | Hand the user the exact steps |

**Push rejected?** The remote moved. Run `git fetch`, look at what arrived (`git log HEAD..origin/<branch>`), integrate it and rerun the checks. Do not force-push by default.

## Clean up

After the merge, or once the pull request is merged: delete the local branch with `git branch -d`, remove worktrees you created (`git worktree remove <path>`, then `git worktree prune`), and delete the remote branch only if the project expects it and the user agrees. Leave alone anything you did not create.

## Hand-off summary

```text
Branch / PR: <name or URL>    Base: <branch>
What changed: <2-4 lines>
Verification:
  <command> -> <result>
Not verified: <check - why - how to confirm>
Decisions made for you: <decision - reason - impact if wrong>
Known limits and follow-ups: <...>
Where the work lives: <worktree path, if any>
```
