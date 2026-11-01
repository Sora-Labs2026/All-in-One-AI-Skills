# Terminal sessions: running commands and opening programs safely

Read this when the work is hands-on terminal execution: running commands in a repository and reporting exactly what happened, debugging a failing build step by step, opening an interactive program (an SSH session, a REPL, a container or pod shell, a dev server) in a visible terminal window for the user, or keeping a long-running process alive. Destructive commands and their stop-check are in `../../agent-safety/references/destructive-commands.md`; the general debugging loop in `../../engineering-workflow/references/debugging.md`.

## Say exactly what state things are in

Use one of these words for each piece of work, and only when it is true:

| State | Means |
|---|---|
| inspected | Read or ran read-only commands; nothing changed |
| changed locally | Files edited in the working tree; not yet proven |
| verified locally | The proving command (test, build, lint) was rerun after the change and passed; name it |
| committed | In a local commit; give the hash |
| pushed | The remote branch moved; give the remote, branch and hash, checked with `git status -sb` or `git log origin/<branch> -1` |
| deployed | Running in the named environment, checked there |
| blocked | Cannot proceed; say on what |

"Fixed" without a rerun proving command is not a state. Neither is "pushed" without checking the remote.

## Before the first command

- Confirm the repository path, the branch and the working-tree state (`git status --short --branch`). Note the user's uncommitted work and never overwrite, stash or discard it without asking.
- Confirm the mode the user asked for: inspect only, fix, verify, or push. An audit request stays read-only.
- Prefer the project's own entry points (`make test`, `npm run build`, `./gradlew check`, scripts in the repository) over improvised command chains.
- Use logs and output the user already provided before rerunning expensive commands.

## Narrow loops

- Run the smallest command that reproduces the failure (one test, one package), fix the dominant error, rerun that command, then widen to the full suite.
- When the same command fails with the same signature twice after changes, stop retrying. Narrow the scope, read more, or report `blocked` with the evidence.
- Avoid hanging on prompts and pagers: `GIT_PAGER=cat`, `git --no-pager`, `PAGER=cat`, `GIT_TERMINAL_PROMPT=0`, `CI=1` for tools that respect it, and a timeout on anything that might wait for input. Never add auto-confirm flags (`--yes`, `-f`, `--force`) to destructive commands to get past a prompt.

## Arguments as arrays, not strings

A command built by pasting strings together is a shell program, and every space, quote, `$`, `;` or newline in a file name or user input changes what it does.

```python
import subprocess
subprocess.run(["git", "log", "--oneline", "--", path], check=True, timeout=60)   # no shell involved
```

```js
import { execFile } from "node:child_process";
execFile("git", ["log", "--oneline", "--", path], { timeout: 60_000 }, callback);   // shell defaults to false
```

- Put `--` before positional arguments that could start with `-`, so a file named `-rf` is not read as options.
- Some interfaces always go through a shell: `ssh host command` (the remote side joins the arguments and runs them in a shell), `bash -c`, AppleScript's `do script`, many CI `run:` steps. There, quote each argument with the platform's quoting function (`shlex.join` or `shlex.quote` for POSIX shells) and never concatenate raw input. Windows `cmd.exe` has different, fragile rules; avoid it and call programs directly.
- Never put secrets on a command line: other users can see arguments in the process list and shells keep history. Pass them through the environment, standard input or a file readable only by the user.

## Opening a program in a visible terminal

Sometimes the user needs to interact with a program themselves: type a password into SSH, watch a dev server, use a REPL. Hand it to them in a new terminal window, built from an argument array:

| Terminal | Argument form (program and its arguments stay separate) |
|---|---|
| GNOME Terminal | `gnome-terminal --working-directory=DIR -- PROG ARG...` |
| Konsole | `konsole --workdir DIR -e PROG ARG...` (`-e` takes everything after it) |
| kitty | `kitty --directory DIR PROG ARG...` |
| WezTerm | `wezterm start --cwd DIR -- PROG ARG...` |
| Alacritty | `alacritty --working-directory DIR -e PROG ARG...` |
| xterm | `xterm -e PROG ARG...` (`-e` must come last; starts in the current directory) |
| Windows Terminal | `wt.exe -d DIR PROG ARG...` (a `;` in any argument separates commands; escape it as `\;`) |
| macOS Terminal, iTerm2 | No argument-array interface; AppleScript `do script` takes a shell string, so quote it with `shlex.join` |

```python
import shlex, shutil, sys

def applescript_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

def open_in_terminal_argv(prog_argv, cwd):
    if shutil.which("gnome-terminal"):
        return ["gnome-terminal", f"--working-directory={cwd}", "--", *prog_argv]
    if shutil.which("konsole"):
        return ["konsole", "--workdir", cwd, "-e", *prog_argv]
    if shutil.which("wezterm"):
        return ["wezterm", "start", "--cwd", cwd, "--", *prog_argv]
    if sys.platform == "darwin":
        command = f"cd {shlex.quote(cwd)} && {shlex.join(prog_argv)}"
        return ["osascript", "-e", f'tell application "Terminal" to do script {applescript_string(command)}']
    raise RuntimeError("no supported terminal found; ask the user which one they use")

plan = open_in_terminal_argv(["ssh", "-t", "build-01.example.internal"], "/srv/work/project")
print(plan)   # show the plan first; launch with subprocess.Popen(plan, start_new_session=True) only when asked
```

- **Plan, then launch.** Show the exact program, arguments, working directory and terminal first. Open the window only when the user asked for one and the command was reviewed.
- **It is a hand-off.** The agent cannot see what happens in that window. Commands whose output you need, run yourself and read.
- **The new process inherits your environment,** including any tokens in it. For anything you do not fully trust, launch with a minimal environment (`env -i PATH=/usr/bin:/bin HOME="$HOME" ...` or an explicit `env=` mapping) rather than everything the agent's shell holds.
- If the requested terminal is not installed, say so and offer the ones that are; do not install a terminal emulator without asking.

## Interactive sessions on other systems

- `ssh -t host` forces a terminal for interactive programs; check the host key on first connection rather than disabling checking.
- `kubectl exec -it`, `docker exec -it` and debug containers on production are changes in effect (`../GUIDE.md`, commands at a glance): ask first, prefer read-only commands, and record what was run.
- Confirm the target before typing anything (`kubectl config current-context`, the SSH host name in the prompt).

## Long-running processes

- Start dev servers and watchers in the background with output to a log file, record the PID and port, and check that they answer before saying they run.
- For sessions that must survive a disconnect, use tmux or screen, and name the session so the user can attach to it.
- Stop what you started at the end of the task, or tell the user exactly what is still running and how to stop it.

## Report

```text
Repo:      ~/src/orders (branch fix/total-rounding, 2 files changed locally)
Evidence:  npm test -- src/total.test.ts failed: expected 10.01, received 10.009999
Action:    round in minor units in src/total.ts
State:     verified locally (npm test -- src/total.test.ts passes; full suite 412 passed); not committed
Running:   nothing left running
```

## Checks (done when)

- [ ] Every claim uses a state word that is true, with the proving command or remote check named.
- [ ] Commands were built from argument arrays; any unavoidable shell string was quoted with a quoting function.
- [ ] No secrets on command lines; launched programs got only the environment they need.
- [ ] Terminal windows were opened only on request, after showing the plan.
- [ ] Background processes were stopped or listed with how to stop them.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `subprocess.run(f"git log {path}", shell=True)` | Argument list, no shell |
| File name starting with `-` read as an option | `--` before positional arguments |
| `ssh host rm {dir}` with spaces in the path | `shlex.join` for the remote command |
| Hang on a pager or credential prompt | `--no-pager`, `GIT_TERMINAL_PROMPT=0`, timeouts |
| "Pushed" when the push was rejected | Check the remote branch after pushing |
| Dev server left running after the task | Stop it or report it |
