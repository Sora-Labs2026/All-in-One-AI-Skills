# Destructive and irreversible commands

Read the section for the class you are about to touch. Each one lists how to recognize the command, why it is dangerous, what to do instead and what can still be recovered. The guard rule IDs refer to `scripts/guard_command.py` (see `command-guard.md`).

Dangerous forms appear only inside tables and inline code here. Every fenced block shows a safe workflow.

## General traps that turn a safe command into a destructive one

- **An empty variable.** With `DIR` unset, `rm -rf "$DIR/"` becomes `rm -rf /`. In scripts use `set -u`, and write `"${DIR:?}"` so the shell aborts when the variable is empty.
- **A failed `cd` in a chain.** With `cd build; rm -rf *`, if `cd` fails the delete runs in the current directory. Chain with `&&`, or use `cd build || exit 1`.
- **Globs in the wrong place.** `*` expands relative to the current directory, which may not be the one you think. Print `pwd` first.
- **Symlinks.** A path inside the project can point elsewhere. Check with `ls -la` before recursive deletes or permission changes.
- **Confirmation-silencing flags.** `-y`, `--yes`, `--force`, `--quiet`, `--auto-approve`, `--accept-data-loss` and `--no-verify` remove the last check. Add them only when the user asked for that exact command.

## 1. Deleting files

| Recognize | Guard rules |
|---|---|
| `rm -r`, `rm -rf`, `rimraf`, `find ... -delete`, `find ... -exec rm`, `xargs rm`, `shred`, `rsync --delete`, `mv` of system or home folders | `DEL-ROOT-HOME`, `DEL-SYSTEM`, `DEL-CREDENTIALS`, `DEL-GIT-HISTORY`, `DEL-PROJECT-ROOT`, `DEL-PROJECT-CONTENTS`, `DEL-OUTSIDE`, `DEL-UNVERIFIED`, `DEL-KEY-FILE`, `DEL-GIT-INTERNAL`, `DEL-UNRECOVERABLE`, `DEL-SYNC` |

**Risk.** `rm` has no trash. Untracked files and anything outside git are gone, and disk-level recovery is unreliable. Deleting `.git` destroys every unpushed commit, branch and stash.

**Safe workflow.**

```bash
pwd && realpath build && ls -la build      # confirm the exact target
git status --short                          # make sure nothing unsaved lives there
find . -name '*.log' -print | head -50      # preview a pattern delete
mkdir -p /tmp/agent-trash-$(date +%Y%m%d) && mv build /tmp/agent-trash-$(date +%Y%m%d)/   # reversible "delete"
```

Delete named folders inside the project (`build`, `dist`, `node_modules`, `.cache`) rather than `*` or `.`. Use `git clean -n` to see untracked files git would remove.

**Recovery.** Tracked files can be restored with `git restore PATH` only if they were committed. Untracked files cannot be restored by git.

## 2. Discarding uncommitted work

| Recognize | Guard rules |
|---|---|
| `git reset --hard`, `git reset --merge`, `git clean -f` (worst with `-x`), `git checkout -- PATH`, `git checkout .`, `git restore PATH`, `git switch --discard-changes`, `git stash drop`, `git stash clear`, `git branch -D`, `git worktree remove --force`, `git rm -f` | `GIT-DISCARD`, `GIT-BRANCH-DELETE` |

**Risk.** These overwrite or delete changes that were never committed. `git clean -x` also removes ignored files such as `.env`, local databases and editor settings.

**Safe workflow.**

```bash
git status --short && git stash list
git stash push --include-untracked -m "before reset"   # or:
git branch backup/before-reset                          # keeps the current commit reachable
git diff > /tmp/before-reset.patch                      # plain-text copy of unstaged changes
git clean -n                                            # list what clean would delete
git branch -d old-feature                               # refuses to delete unmerged work
```

**Recovery.** Commits moved away by `reset` stay in `git reflog` (by default reachable entries are kept 90 days, unreachable ones 30). Uncommitted edits discarded by `reset --hard` or `checkout --` are not in the reflog. Content that had been staged may survive as dangling blobs (`git fsck --lost-found`). A dropped stash is a dangling commit that `git fsck --no-reflog` can list until garbage collection removes it.

## 3. Rewriting shared history

| Recognize | Guard rules |
|---|---|
| `git push --force`, `git push -f`, a `+branch` refspec, `--mirror`, `--delete` or `:branch`, `--prune`, `git filter-branch`, `git filter-repo`, history-rewriting tools such as BFG, force-pushing after `rebase` or `commit --amend` on pushed commits, `git reflog expire`, `git gc --prune=now` | `GIT-FORCE-PROTECTED`, `GIT-FORCE-PUSH`, `GIT-MIRROR-PUSH`, `GIT-REMOTE-DELETE`, `GIT-HISTORY-REWRITE` |

**Risk.** A plain force push overwrites commits other people pushed. Rewriting `main` or a release branch breaks every clone and open pull request. `--mirror` makes the remote match your clone exactly, deleting branches and tags you do not have.

**Safe workflow.** Work on your own branch and force-push only that branch, with a lease:

```bash
git fetch origin
git push --force-with-lease --force-if-includes origin my-feature
```

`--force-with-lease` refuses when the remote branch moved since your last fetch. A background fetch (for example by an editor) can update your remote-tracking ref and defeat that check; `--force-if-includes` (Git 2.30 and later) also requires that the remote tip is already part of your local history. The real control is the hosting service's branch protection; suggest it if `main` is unprotected.

To remove a secret from history: rotate it first (LaunchGuard, `../../launchguard/references/safe-operations.md`), back up with `git clone --mirror`, agree the plan with the user, and tell collaborators to re-clone afterwards.

## 4. Destroying data

| Recognize | Guard rules |
|---|---|
| SQL `DROP DATABASE`, `DROP SCHEMA`, `DROP TABLE`, `TRUNCATE`, `DELETE` or `UPDATE` without `WHERE`, `ALTER TABLE ... DROP`; Redis `FLUSHALL` and `FLUSHDB`; MongoDB `dropDatabase()` and `deleteMany({})`; `dropdb`, `mysqladmin drop`; `prisma migrate reset`, `prisma db push --accept-data-loss`, `rails db:drop`, `rails db:reset`, `manage.py flush`, `artisan migrate:fresh`, `alembic downgrade base`, `supabase db reset`; `docker volume rm`, `docker volume prune`, `docker system prune`, `docker compose down -v` | `DB-DESTRUCTIVE`, `DATA-DELETE` (denied when the command names a production target) |

**Risk.** Data deleted without a backup is gone. Framework "reset" commands drop and recreate the whole database. Docker volumes often hold the only copy of a local database.

**Safe workflow.**

```bash
psql -c "SELECT current_database(), inet_server_addr();"      # which database is this?
pg_dump -Fc -f before-change.dump app_dev                       # PostgreSQL backup
mysqldump --single-transaction app_dev > before-change.sql      # MySQL backup
sqlite3 app.db ".backup before-change.db"                       # SQLite backup
psql -c "SELECT count(*) FROM sessions WHERE expires_at < now();"   # count before deleting
docker system df && docker volume ls                            # see what a prune would remove
```

Run row changes inside a transaction and check the count before committing (`BEGIN; DELETE ... WHERE ...; SELECT count(*) ...;` then `COMMIT` or `ROLLBACK`). PostgreSQL and SQLite can roll back DDL such as `DROP TABLE`; MySQL commits DDL immediately, so a transaction does not protect it. Never run destructive statements against production from an agent session without the user's explicit approval for that statement; prefer a reviewed migration.

## 5. Mass permission and ownership changes

| Recognize | Guard rules |
|---|---|
| `chmod -R`, `chown -R`, `chgrp -R`, `chmod 777` or `666`, `o+w`, any of these on `/`, `~`, `/usr/local` or `~/.ssh` | `PERM-CATASTROPHIC`, `PERM-OUTSIDE`, `PERM-WORLD-WRITABLE`, `PERM-UNVERIFIED` |

**Risk.** Recursive ownership changes on home or system folders can break login, `sudo` and SSH. SSH refuses private keys that other users can read. World-writable files let any local process change your code.

**Safe workflow.**

```bash
stat -c '%a %U:%G %n' scripts/*.sh          # Linux: record current modes
stat -f '%Lp %Su:%Sg %N' scripts/*.sh       # macOS equivalent
getfacl -R dir > before.acl                 # Linux: full backup; restore with setfacl --restore=before.acl
find dir -type d -exec chmod 755 {} +
find dir -type f -exec chmod 644 {} +
chmod 700 ~/.ssh && chmod 600 ~/.ssh/config # correct, narrow fixes
```

## 6. Running remote code

| Recognize | Guard rules |
|---|---|
| A downloader piped into a shell or interpreter (`curl URL \| sh`, `wget -qO- URL \| bash`), `bash <(curl URL)`, `sh -c "$(curl URL)"`, `eval "$(curl URL)"`, PowerShell `iex (irm URL)`, downloading a script and running it in the same command | `REMOTE-EXEC`, `REMOTE-EXEC-FILE`, `INLINE-DESTRUCTIVE` |

**Risk.** Nobody reads the code before it runs with the user's permissions. A server can send different content to a script than to a browser, and a dropped connection can run a truncated script.

**Safe workflow.** Prefer the package manager (`brew`, `apt`, `winget`, `npm` or `pip` with a lockfile). Otherwise:

```bash
curl -fsSLo install.sh "$INSTALLER_URL"
less install.sh                                  # read it; look for sudo, rm, curl and eval
shasum -a 256 install.sh                         # compare with the checksum the publisher lists
sh install.sh                                    # only after the user agrees
```

Verify a signature too when the publisher offers one (GPG, minisign, Sigstore).

## 7. Stopping processes or the machine

| Recognize | Guard rules |
|---|---|
| `kill PID`, `kill -9`, `pkill`, `killall`, `kill -9 -1`, `kill 1`, `shutdown`, `reboot`, `halt`, `systemctl poweroff`, `systemctl stop` or `disable`, `launchctl bootout`, fork bombs | `PROC-KILL`, `PROC-KILL-ALL`, `PROC-POWER`, `PROC-SERVICE`, `PROC-FORK-BOMB` |

**Risk.** `pkill -f PATTERN` matches whole command lines and can stop the user's editor, another project or the agent itself. `kill -9 -1` signals every process the user can signal. `SIGKILL` gives a process no chance to save state.

**Safe workflow.** Track what you start and stop only that:

```bash
npm run dev > /tmp/dev.log 2>&1 & echo $! > .dev.pid
kill "$(cat .dev.pid)"                        # SIGTERM first
lsof -ti :3000                                # who holds the port?
ps -p 12345 -o pid,ppid,user,command          # confirm before stopping anything you did not start
```

Never shut down or restart the machine from an agent session.

## 8. Cloud and infrastructure deletion

| Recognize | Guard rules |
|---|---|
| `terraform destroy`, `terraform apply -destroy`, `terraform state rm`, `pulumi destroy`, `kubectl delete`, `helm uninstall`, `aws ... delete-*`, `aws s3 rm --recursive`, `aws s3 rb`, `aws ec2 terminate-instances`, `gcloud ... delete`, `az group delete`, `fly apps destroy`, `heroku apps:destroy`, `gh repo delete` | `CLOUD-DELETE` (denied when the command names a production target), `ACCOUNT-EXPOSURE`, `ACCOUNT-CHANGE` |

**Risk.** Most cloud deletions take effect immediately and cannot be undone: an S3 object without versioning, a database deleted without a final snapshot, every resource inside a deleted Kubernetes namespace. Changing a repository's visibility to public exposes its whole history.

**Safe workflow.**

```bash
aws sts get-caller-identity && kubectl config current-context && terraform workspace show
terraform plan -destroy -target=aws_instance.preview
kubectl delete deployment preview-api --dry-run=server
aws s3 rm s3://bucket/tmp/ --recursive --dryrun
aws rds create-db-snapshot --db-instance-identifier app-dev --db-snapshot-identifier app-dev-before-change
```

Scope deletions to one named resource. Suggest the platform's own guards where they are missing: Terraform `lifecycle { prevent_destroy = true }`, database deletion protection, S3 versioning.


Before asking about a Terraform or OpenTofu apply or destroy, run `python3 <productcraft>/modules/cloud-infrastructure/scripts/plan_review.py plan.json` on the JSON plan (`terraform show -json tfplan > plan.json`) and include its deletions, replacements and IAM findings in the confirmation. The full plan-and-diff workflow is in `../../cloud-infrastructure/GUIDE.md`.

## 9. Publishing and deploying

| Recognize | Guard rules |
|---|---|
| `npm publish`, `npm unpublish`, `cargo publish`, `twine upload`, `gem push`, `docker push`, `gh release create`, `terraform apply`, `pulumi up`, `kubectl apply`, `helm install` or `upgrade`, `vercel --prod`, `netlify deploy`, `firebase deploy`, `fly deploy`, `wrangler deploy` | `PUBLISH`, `DEPLOY` |

**Risk.** Other people and production systems receive the change at once. A published package version number can never be reused, even after removal; npm allows unpublishing only under limited conditions, and `cargo yank` only hides a version from new resolutions.

**Safe workflow.** Run `npm publish --dry-run`, `cargo publish --dry-run`, `terraform plan` or the platform's preview deploy, show the result, and publish or deploy only when the user asked for this release.

## 10. Secrets

See `secrets.md`. Guard rules: `SECRET-READ`, `SECRET-PRINT`, `SECRET-ENV-DUMP`, `SECRET-COPY`, `SECRET-COMMIT`, `SECRET-EXFIL`, `SECRET-WRITE`, `DATA-UPLOAD`.

## 11. Agent, shell and startup configuration

| Recognize | Guard rules |
|---|---|
| Writing `.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/`, `.mcp.json`, shell startup files (`~/.bashrc`, `~/.zshrc`, `~/.profile`), `~/.ssh/authorized_keys`, `~/.ssh/config`, `.git/hooks/`, `git config core.hooksPath`, `git config --global`, crontab, launch agents, systemd user units, desktop autostart | `CFG-CHANGE`, `CFG-PERSISTENCE`, `GIT-GLOBAL-CONFIG`, `WRITE-OUTSIDE` |

**Risk.** These files decide what runs automatically and what the agent may do without asking. Changing them quietly can widen the agent's own permissions, disable a guard or leave code that runs at every login.

**Safe workflow.** Show the exact diff first and keep a dated copy:

```bash
cp ~/.zshrc ~/.zshrc.bak-$(date +%Y%m%d)
crontab -l > crontab.backup-$(date +%Y%m%d)
git config --show-origin --get-all core.hooksPath
```

## 12. Disk devices and privilege

| Recognize | Guard rules |
|---|---|
| `dd of=/dev/...`, `mkfs`, `wipefs`, `fdisk`, `parted`, `sgdisk`, `diskutil eraseDisk`, output redirected onto a block device | `DISK-DESTROY` |
| `sudo`, `doas`, `su`, `pkexec` | `PRIV-ESCALATION` |

Never write to block devices from an agent session. For privilege, prefer user-level installs (`pipx`, `uv tool install`, a user npm prefix, Homebrew) and ask before any command needs `sudo`.
