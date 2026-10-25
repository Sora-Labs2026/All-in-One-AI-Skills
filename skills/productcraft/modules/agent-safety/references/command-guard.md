# Command guard: an optional pre-tool hook

`scripts/guard_command.py` checks a proposed shell command before it runs and answers with a decision, a rule ID, a reason and a safer alternative. It is a seatbelt: it catches common, recognizable mistakes. It is not a sandbox and does not make an agent session safe on its own.

Wiring it into Claude Code is **opt-in**. The agent offers it, shows the exact settings change and adds it only after the user says yes.

## Decisions

| Decision | Meaning | In hook mode |
|---|---|---|
| `ALLOW` | No rule matched. This is not a safety guarantee | Prints nothing, so Claude Code's normal permission rules and prompts still apply. The guard never approves anything on its own |
| `ASK` | Legitimate in some tasks, but destructive, irreversible or outside the project | Claude Code shows a permission prompt with the guard's reason |
| `DENY` | Catastrophic or almost never the agent's job: deleting `/`, home or `.git`, force-pushing a protected branch, piping a download into a shell, printing private keys, formatting disks | The call is blocked and the reason goes back to the agent, which must stop and tell the user, not look for a way around it |

When several rules match, the strictest wins. Destructive database and cloud findings are raised from `ASK` to `DENY` when the command names a production target (`prod`, `production` or `prd` as a separate word).

## What it reads

The command text, the working directory, `CLAUDE_PROJECT_DIR` (the project boundary; it falls back to the working directory), and `.git/HEAD` to learn the current branch for `git push` without a branch name. It never runs the command and never uses the network.

If the project boundary is `/` or the home folder, there is no meaningful boundary, so every recursive delete or write outside a temp folder is asked about. Temp folders (`/tmp`, `/var/tmp`, `$TMPDIR` and the platform temp directory) count as safe for deleting their subfolders but not themselves.

On a remote host (`ssh HOST 'command'`) the guard does not know the layout, so most denials become questions. Deleting `/` or home, disk writes, remote code, reverse shells, secret uploads, killing every process, mirror pushes and force pushes to protected branches stay denied.

## Try it before wiring it in

```bash
G=<productcraft>/modules/agent-safety/scripts/guard_command.py
python3 "$G" "rm -rf ./build"                            # ALLOW, exit 0
python3 "$G" "git push --force origin feature/login"     # ASK, exit 1
python3 "$G" "rm -rf ~"                                  # DENY, exit 2
python3 "$G" --json --cwd . "cat .env"                   # machine-readable result
echo '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"/tmp"}' | python3 "$G" --hook
```

The last line prints nothing, which means "no objection". Exit codes outside hook mode: 0 allow, 1 ask, 2 deny, 64 usage error. In hook mode the exit code is always 0 and the decision is in the JSON.

## Wire it into Claude Code (opt-in)

1. **Ask first.** Explain that the guard runs before every matching tool call, can block calls, and adds about 0.1 to 0.2 seconds per call (measured at about 0.13 seconds including Python start-up).
2. **Pick the scope.** `.claude/settings.json` is shared with everyone on the project, so the script must be committed too. `.claude/settings.local.json` is personal to this project. `~/.claude/settings.json` applies to every project and needs an absolute script path.
3. **Copy the script** so that updates are deliberate and reviewable:

   ```bash
   mkdir -p .claude/hooks
   cp <productcraft>/modules/agent-safety/scripts/guard_command.py .claude/hooks/
   ```

4. **Merge this into the chosen settings file.** Keep any existing `hooks` and `permissions` entries.

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash|Read|Edit|Write|MultiEdit|Grep",
           "hooks": [
             {
               "type": "command",
               "command": "python3 -I \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard_command.py\" --hook",
               "timeout": 10
             }
           ]
         }
       ]
     }
   }
   ```

   `-I` runs Python in isolated mode, so environment variables and files next to the script cannot change which modules it imports. To protect more branch names, append `--protected-branch NAME` (repeatable). The default list is `main`, `master`, `trunk`, `develop`, `development`, `production`, `prod`, `staging`, `stable`, `release`, `live`, `gh-pages`, plus `release/*`, `release-*` and `hotfix/*`.

5. **Reload.** Restart the session or review the change in the `/hooks` menu, since Claude Code reads hook settings at start-up.
6. **Verify with a harmless command.** Ask the agent to run `git status` (no objection expected), then `kill -0 -1`. The second should be denied with `PROC-KILL-ALL`; if the hook were not active it would still do nothing, because signal 0 only checks that processes exist.

Remove the guard by deleting its entry from the settings file.

## Unattended sessions

An `ASK` only helps if a person sees the prompt. When the payload says the session runs in `bypassPermissions` or `dontAsk` mode, the guard turns every `ASK` into `DENY` by itself. For headless or CI runs, add `--ask-as-deny` to the hook command to get the same behavior regardless of mode.

## Rules

| Family | Rule IDs | Default |
|---|---|---|
| Deleting | `DEL-ROOT-HOME`, `DEL-SYSTEM`, `DEL-CREDENTIALS`, `DEL-GIT-HISTORY`, `DEL-PROJECT-ROOT` | Deny |
| | `DEL-PROJECT-CONTENTS`, `DEL-OUTSIDE`, `DEL-UNVERIFIED`, `DEL-KEY-FILE`, `DEL-GIT-INTERNAL`, `DEL-UNRECOVERABLE`, `DEL-SYNC` | Ask |
| Git | `GIT-FORCE-PROTECTED`, `GIT-MIRROR-PUSH`; `GIT-REMOTE-DELETE` on a protected branch | Deny |
| | `GIT-FORCE-PUSH`, `GIT-REMOTE-DELETE`, `GIT-DISCARD`, `GIT-BRANCH-DELETE`, `GIT-HISTORY-REWRITE`, `GIT-GLOBAL-CONFIG` | Ask |
| Data | `DB-DESTRUCTIVE`, `DATA-DELETE` | Ask; deny for production |
| Permissions | `PERM-CATASTROPHIC` | Deny |
| | `PERM-OUTSIDE`, `PERM-WORLD-WRITABLE`, `PERM-UNVERIFIED` | Ask |
| Remote code and network | `REMOTE-EXEC`, `NET-REVERSE-SHELL`, `SECRET-EXFIL` | Deny |
| | `REMOTE-EXEC-FILE`, `DATA-UPLOAD`, `INLINE-DESTRUCTIVE`, `AWK-EXEC` | Ask |
| Processes | `PROC-KILL-ALL`, `PROC-POWER`, `PROC-FORK-BOMB` | Deny |
| | `PROC-KILL`, `PROC-SERVICE` | Ask |
| Cloud and release | `CLOUD-DELETE` | Ask; deny for production |
| | `DEPLOY`, `PUBLISH`, `ACCOUNT-EXPOSURE`, `ACCOUNT-CHANGE` | Ask |
| Secrets | `SECRET-READ` for private keys and credential stores | Deny |
| | `SECRET-READ` for `.env`-style files, `SECRET-PRINT`, `SECRET-ENV-DUMP`, `SECRET-COPY`, `SECRET-COMMIT`, `SECRET-WRITE` | Ask |
| Configuration | `CFG-PERSISTENCE` for `crontab -r` | Deny |
| | `CFG-CHANGE`, `CFG-PERSISTENCE`, `WRITE-OUTSIDE` | Ask |
| Disk | `DISK-DESTROY` | Deny |
| Other | `PRIV-ESCALATION`, `CMD-DYNAMIC`, `PARSE-UNCLEAR`, `PARSE-LIMIT`, `GUARD-ERROR` | Ask |

For the file tools, `Read` and `Grep` on private keys or credential stores are denied, and on `.env`-style files asked. `Edit` and `Write` are asked for key material and for agent, shell, SSH and git-hook configuration.

What each class covers and the safer alternatives: `destructive-commands.md`.

## How the parsing works, briefly

The guard splits the command into simple commands on `;`, `&&`, `||`, `|` and newlines, and keeps quoting, redirects, heredocs and substitutions. It looks through wrappers (`sudo`, `env`, `xargs`, `timeout`, `nohup`, `npx`) and analyzes the inner command. It recursively checks `bash -c`, `sh -c`, `eval`, `$(...)`, backticks, process substitution, heredocs fed to a shell and the command part of `ssh HOST CMD`, plus commands written literally inside awk `system()` calls and command pipes, and GNU `parallel` command templates, whose inputs count as values known only at runtime (so `parallel rm -rf ::: ...` is asked about, like `xargs rm -rf`). It tracks `cd` within a command line. A heredoc written to a file stays data. Unbalanced quotes or nesting deeper than four levels produce `ASK`.

## Limits

- **It sees only the command text.** It cannot see inside scripts, `Makefile` targets, package scripts, shell aliases or functions, or whatever the command starts. `bash cleanup.sh` is allowed even if `cleanup.sh` deletes the home folder.
- **Computed values.** When a recursive delete target comes from a variable or command output it asks, but other computed names and arguments may pass unchecked.
- **Paths are lexical.** Symlinks are not followed, so a link inside the project that points elsewhere looks like a project path.
- **Inline interpreter code** (`python -c`, `node -e`) is checked with heuristics only. An awk program read from a file (`awk -f`) is not checked, and an awk `system()` call whose command is built at runtime is asked about (`AWK-EXEC`).
- **Other channels are not covered:** MCP tools, network traffic, the content of files written by `Edit` or `Write` (only sensitive locations are checked), and any tool not in the matcher.
- **POSIX shells only.** PowerShell and `cmd` syntax is not parsed, apart from one download-and-run pattern.
- **It fails open outside its own code.** If `python3` is missing, the hook times out or the process cannot start, Claude Code treats that as a non-blocking error and the call proceeds. Errors inside the script produce `ASK` (`DENY` with `--ask-as-deny`).
- **Allow is not approval.** Many harmful commands match no rule.

For real isolation use a devcontainer, container or VM, a separate OS account, environments without production credentials, short-lived narrowly scoped tokens, and the agent's own permission rules and sandboxing where available. How to set it up and check it: `isolation.md`.

## Troubleshooting

- **Nothing happens:** check that `/hooks` lists the entry, that the matcher spells tool names exactly (matchers are case-sensitive), that the script path is right and that `python3` is on `PATH`. Then run the stdin example above by hand.
- **Too many prompts:** every reason starts with a rule ID. Reproduce the decision with `python3 guard_command.py --json --cwd DIR "COMMAND"`. If a rule is wrong for this project, change the copied script deliberately and run the module tests (`python3 -m unittest discover -s modules/agent-safety/tests -v`). The agent must not weaken the guard on its own; edits under `.claude/` are themselves asked about.
