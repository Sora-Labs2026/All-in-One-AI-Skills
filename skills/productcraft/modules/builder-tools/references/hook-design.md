# Designing agent hooks that are correct, safe and fast

Read this when writing, reviewing or debugging a hook: a command the agent host runs automatically on an event such as "before a tool call" or "when the agent is about to stop". `agent-config-linting.md` checks a hook declaration someone already wrote; this file is how to design one. Ready-made patterns (fact-forcing gates, write-time format and lint, protecting check configs, rule hooks, completion checks) are in `quality-and-gate-hooks.md`. The command guard in `../../agent-safety/references/command-guard.md` is a complete worked example.

Contents: hook or something else · the host contract · write it as a small program · fail-open or fail-closed · speed · safety of the hooks themselves · testing · done when.

## Hook, instruction, permission rule or CI check?

| The behavior | Best home | Why |
|---|---|---|
| Allow or deny a tool by name, path or command prefix | The host's permission rules | Enforced by the host, no process to start, nothing to maintain |
| Must happen on every matching call, and a script can decide it from the tool input | Hook | Runs whether or not the model remembers |
| Needs judgment or context ("prefer small commits") | Instruction file line or skill | A script cannot judge it; a hook would guess |
| Must hold for every contributor and every change | CI check, optionally mirrored by a hook | Hooks run only in the sessions of people who installed them |

A hook that only reminds the model of something the instruction file already says is usually noise. A hook earns its cost when it observes something concrete (this command, this path, this diff) and either blocks it or tells the model a fact it would not otherwise see.

## Know the contract of the installed host

Event names, payload fields, exit-code meaning and JSON output differ between hosts and change between versions. Read the installed version's hook documentation before writing one, and state the host and version you targeted. For Claude Code (2.x, late 2026), the points that most often go wrong:

- **Events** include `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`, `PreCompact` and `Notification`; newer versions add more.
- **Matchers match tool names only** (a case-sensitive regular expression: `Bash`, `Edit|Write`, `mcp__github__.*`). They cannot look at arguments, so filter on the command or path inside the script. A matcher written like an expression (`Bash && command contains "npm"`) is just a tool-name pattern that matches nothing, and the hook silently never runs.
- **Input** arrives as JSON on stdin: session id, transcript path, working directory, event name, and for tool events the tool name and input; post-tool events also carry the tool's response.
- **Exit codes:** 0 means no objection. 2 blocks, and stderr goes back to the model: for `PreToolUse` the call does not run; for `PostToolUse` the tool already ran, so it is feedback only. Other non-zero codes are non-blocking errors shown to the user. Text on stderr with exit 0 does not reach the model in most events.
- **JSON on stdout** gives finer control: for `PreToolUse` a permission decision of `allow`, `deny` or `ask` with a reason; for post-tool, prompt and stop events a `block` decision with a reason, or extra context for the model. **Returning `allow` skips the user's permission prompt.** A gate should never return `allow`; it should print nothing when it has no objection, so the normal permission rules still apply.
- **Stop hooks:** blocking a stop makes the agent continue. The payload has a flag (`stop_hook_active`) that is true when the agent is already continuing because of a stop hook; ignore it and a hook that always blocks loops forever.
- **Runtime:** all matching hooks run in parallel, so one cannot depend on another's result; each has a timeout (60 seconds by default; set a much lower one); settings are read at session start, so changes need a reload or a review in `/hooks`. `$CLAUDE_PROJECT_DIR` points at the project root.

Porting a hook to another host means re-checking every item above, not renaming the event.

## Write the hook as a small program

- **Logic in a script file,** committed next to the settings (`.claude/hooks/check_edit.py`), referenced by a short command. Avoid inline one-liners with layers of escaped quotes, and never a command that searches caches or plugin folders for code to load: whoever reads the settings must see exactly what runs.
- **Isolated interpreter:** `python3 -I "$CLAUDE_PROJECT_DIR/.claude/hooks/check_edit.py"`, so files in the working directory cannot replace imported modules.
- **Defensive parsing:** missing keys, wrong types, empty or non-JSON input. Decide per purpose what happens then (next section).
- **Bounded input:** read at most a fixed number of bytes; a `Write` payload can carry a whole file. When input is over the cap, a safety hook asks or denies, a convenience hook skips.
- **stdout is for the decision only.** Diagnostics go to stderr or a log file. Never echo the payload back: it contains file contents and commands, sometimes secrets.
- **Deterministic and local:** no network calls and no model calls by default. A hook that spawns a model or agent (for example to auto-fix lint) needs a budget, a timeout, a guard against recursion (the spawned agent triggers hooks too) and a visible report of what it changed.

A minimal `PreToolUse` gate in Python:

```python
#!/usr/bin/env python3
"""Deny writes into vendor/ and generated/ folders; say nothing otherwise."""
import json, sys

MAX_INPUT = 1_000_000
BLOCKED = ("vendor/", "generated/")

def main() -> int:
    raw = sys.stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        return decide("ask", "Input too large to inspect; please confirm this edit.")
    try:
        payload = json.loads(raw)
        path = str(payload.get("tool_input", {}).get("file_path", ""))
    except (ValueError, AttributeError):
        return decide("ask", "Could not read the hook input; please confirm this edit.")
    if any(f"/{part}" in f"/{path}" for part in BLOCKED):
        return decide("deny", f"{path} is generated or vendored. Change the generator or the upstream package instead.")
    return 0  # no output: normal permission rules apply

def decide(decision: str, reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                      "permissionDecision": decision, "permissionDecisionReason": reason}}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Fail-open or fail-closed

| Hook purpose | When the hook itself fails or cannot inspect the input | Why |
|---|---|---|
| Safety gate (destructive commands, secrets, protected paths) | `ask`, or `deny` in unattended runs | An error must never turn into permission |
| Quality feedback (format, lint, reminders) | Allow, and write one diagnostic line to stderr | A broken formatter must not stop all work |
| Observation (logging, metrics) | Allow silently, log the failure locally | Recording is never worth blocking work |

Many hosts treat a hook that crashes, cannot start or times out as a non-blocking error, so the call proceeds. A gate that must hold therefore needs a backstop that does not depend on the hook process: a permission deny rule, a sandbox, or a server-side check.

## Keep hooks fast

A `PreToolUse` hook runs before every matching call, so tens of milliseconds add up over a session.

- **Measure.** Run the hook twenty times with a representative payload and report the median, interpreter start-up included: `for i in $(seq 20); do ( TIMEFORMAT=%R; time python3 -I hook.py < payload.json > /dev/null ); done 2>&1 | sort -n | sed -n 10p` (bash; seconds).
- **Narrow matchers, early exits.** Match only the tools you inspect and return at once for paths or commands you do not care about.
- **Consolidate.** One dispatcher process per event that runs several checks costs one interpreter start instead of many.
- **Move heavy work later.** Format and type-check the files edited this turn once at `Stop` rather than after every edit; leave full test suites to CI.
- **Background only for side work.** Where the host can run a hook in the background, that hook cannot block or give feedback; use it for logging, not for checks.
- **Cache per session** in a private state directory keyed by session id, with an expiry.
- **Regular expressions:** anchor them, compile once, cap the input length, and avoid nested quantifiers such as `(a+)+`, which can take exponential time on crafted input.

## Safety of the hooks themselves

- A hook runs with the user's permissions and no prompt. Treat third-party hooks as code to vet (`../../agent-safety/references/vetting-extensions.md`).
- Hook settings and rule files committed to a repository activate for anyone who opens it. A hook framework that loads rule files from the project should ignore tracked rule files until the user opts in, and should label rule text as untrusted when passing it to the model.
- The agent must not edit hook settings or hook scripts to get past a block. Protect `.claude/` and the scripts (the command guard asks on these writes) and say so in the block message.
- State files live in a private directory (`0700`), stay small, expire, and never record secret values or full file contents.
- Hooks that record every tool call or the transcript collect sensitive data: local by default, opt-in, with a retention period, and readable and deletable by the user.
- Give every hook a stable id and a documented way to switch it off for repair work (a settings entry or an environment variable naming the id), so nobody has to delete a safety hook to get unstuck.

## Test hooks like code

- Keep one payload fixture per case: allowed, blocked, ask, malformed JSON, oversized input, a tool the hook should ignore.
- Unit-test by running the script with each fixture on stdin and asserting the exit code and the parsed stdout JSON.
- After wiring it in, trigger one harmless and one blocked case in a real session and confirm the result in the transcript (the pattern in `../../agent-safety/references/command-guard.md`, step 6).
- Re-run the latency measurement after every change.

```python
import json, subprocess, unittest

def run(payload: dict) -> tuple[int, dict | None]:
    p = subprocess.run(["python3", "-I", ".claude/hooks/check_edit.py"], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=10)
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None)

class GateTests(unittest.TestCase):
    def test_vendor_write_denied(self):
        code, out = run({"tool_name": "Write", "tool_input": {"file_path": "vendor/x.js"}})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_ordinary_write_is_silent(self):
        self.assertEqual(run({"tool_name": "Write", "tool_input": {"file_path": "src/x.js"}}), (0, None))
```

## Done when

- The behavior could not be handled more simply by a permission rule, an instruction line or CI.
- The hook targets a named host version; its matcher, event, payload fields and output follow that version's documentation.
- It lives in a reviewed script file, reads bounded input, prints only its decision, never returns `allow` as a gate, and fails open or closed according to its purpose.
- Its tests cover allowed, blocked, malformed and oversized input; its median latency was measured and reported; it was confirmed in a live session.
- It has an id, a documented off switch, and a backstop if it guards something that must hold.
