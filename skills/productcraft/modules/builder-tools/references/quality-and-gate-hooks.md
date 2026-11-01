# Gate and quality hooks: patterns that work

Read this after `hook-design.md` (contract, speed, safety, testing) when you want a specific kind of hook: a gate that makes the agent investigate before it edits, format and lint checks at write time, protection for the checks themselves, rule hooks distilled from repeated corrections, or checks before the agent ends its turn. Every pattern here is optional and opt-in: show the user the settings change and the script, and add them only after a yes.

Contents: fact-forcing gates · write-time format and lint · protecting the checks · rule hooks · completion checks · done when.

## 1. Fact-forcing gates before edits

Asking a model "are you sure?" or "did you follow the guidelines?" nearly always gets "yes": self-assessment does not make it look at anything. Asking for specific facts that can only be produced by looking does. "List the files that import this module" makes the agent search; "show the real field names and date format of the data file" makes it open the file. The gathered context then changes the edit.

**Shape:** a `PreToolUse` hook on file-editing tools denies the first edit of each file in a session with a short list of facts to present, and lets the retry through. Track checked files per session in a private state file. On the retry, print nothing rather than `allow`, so the user's permission rules still apply.

**Questions by target, each ending with "quote the user's current instruction verbatim":**

| Target | Ask for |
|---|---|
| Existing code file | Files that import or call it (from a search); public functions or types the change affects; if it reads or writes data, the actual field names, structure and date format (synthetic or redacted values) |
| New code file | Which file and line will call it; confirmation from a search that nothing existing does the same job |
| Test file | The behavior and the function under test; existing tests for that module |
| Documentation | Other documents or code that reference the section; for a new file, why an existing document cannot hold it |
| Configuration | Which program reads it and when; the effect of the change; confirmation that no secret is written in plain text |
| Agent instruction file (`CLAUDE.md`, `AGENTS.md`, skills, rules) | Which host loads it and when; what agent behavior changes; confirmation that no existing instruction already covers it |

**Make it cheap enough to keep:**
- Fit the questions to the change: drop "who imports this" when the edit touches no public name, drop the data question when nothing reads or writes data, and let comment- or whitespace-only edits through without marking the file checked.
- Always gate sensitive targets in full, judged on the real path after resolving symlinks: secret and key files, `auth`, `payments`, `billing`, `migrations`, CI workflow folders. If deciding fails (dangling link, permission error), treat the target as sensitive.
- Credit investigation already done: when the transcript shows a completed search in the current user turn that names the file, allow the edit with a short note. Never credit a search sent in the same batch as the edit (its result was not seen), and remember the transcript is a file the agent can write: credit proves a search ran, not that its result was read.
- Bound the context cost: the full question block for the first few denials in a session, a one-line form after that, and optionally a cap on denials per session.
- Exempt generated, vendored and build folders by explicit, reviewable patterns, and provide an off switch for setup or repair work.

**Parallel batches:** hooks see tool calls one at a time. If the agent sends several edits to an unchecked file in one batch, the first can be denied while the others apply, leaving the file half-changed. The denial message should say so, and tell the agent to re-read the file and send dependent edits one after another.

**Shell commands:** gate destructive commands every time (what will be changed or deleted, a one-line rollback, the quoted instruction), and ordinary commands at most once per session, with read-only commands such as `ls`, `cat`, `git status` and `git diff` exempt.

**Check that it helps.** Run realistic tasks with and without the gate (`skill-evaluation.md`) and count denials and credits. A gate that fires constantly without changing outcomes is friction; loosen or remove it.

## 2. Write-time format and lint

**Shape:** a `PostToolUse` hook on `Edit|Write` for the file just changed.
1. Run the project's formatter on that file in place, silently.
2. Run the linter on that file in machine-readable mode.
3. If violations remain, exit 2 with a short list (`path:line rule message`, capped at a few dozen lines) so the model fixes them now. If clean, print nothing.

Practical points:
- Use the project's own tools and configuration (`ruff`, `eslint` or `biome`, `gofmt`, `rustfmt`, `shellcheck`), at the versions in its lockfile or toolchain file. If a tool is missing, skip with one line on stderr instead of failing every edit.
- A formatter that rewrites the file after the model wrote it makes the model's copy stale, and its next exact-match edit can fail. Either format at `Stop`, or tell the model in the feedback that the file was reformatted.
- One formatter per file type. Two tools that both format TypeScript, for example, undo each other.
- Per-file checks only after each edit; batch heavier ones (type-check, project-wide lint) at `Stop` over the files changed this turn: `git diff --name-only` plus `git ls-files --others --exclude-standard`.
- Skip generated, vendored and lockfile paths.
- Run the same commands in CI. The hook is a fast local loop, not the gate the team relies on.
- Prefer handing remaining violations to the main agent over spawning a hidden fixing agent from the hook. If you do spawn one, give it a budget, a timeout, a recursion guard, and report the diff it made.

## 3. Protect the checks from being weakened

Under pressure, agents make a failing check pass by changing the check: disabling a lint rule, raising a threshold, adding suppression comments, skipping tests or committing with `--no-verify`. Two layers stop most of this:

**Block edits to existing check configuration** (`PreToolUse` on file-editing tools). Compare the file's base name case-insensitively against a list such as `.eslintrc*`, `eslint.config.*`, `.prettierrc*`, `prettier.config.*`, `biome.json`, `biome.jsonc`, `ruff.toml`, `.ruff.toml`, `.flake8`, `mypy.ini`, `.golangci.yml`, `.shellcheckrc`, `.markdownlint*`, `.stylelintrc*`, `.pre-commit-config.yaml`. Count a dangling symlink with a protected name as existing. Allow creating a config in a project that has none.

```python
import json, os, sys

PROTECTED = {".eslintrc.json", "eslint.config.js", "eslint.config.mjs", ".prettierrc", "biome.json",
             "ruff.toml", ".ruff.toml", ".flake8", "mypy.ini", ".golangci.yml", ".pre-commit-config.yaml"}
try:
    path = json.loads(sys.stdin.read(1_000_000))["tool_input"]["file_path"]
except (ValueError, KeyError, TypeError):
    sys.exit(0)  # convenience-level guard: fail open, and the Stop check below still reports changes
if os.path.basename(str(path)).lower() in PROTECTED and os.path.lexists(path):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": f"{os.path.basename(path)} configures a project check. Fix the code so the check "
                                    "passes; if the rule itself is wrong, ask the user to change it."}}))
```

**Report changes at `Stop`.** Files such as `pyproject.toml`, `package.json`, `tsconfig.json`, test-runner configs and CI workflows hold much more than check settings, so blocking them outright is too strict. Instead, at `Stop`, compare this turn's diff for changes to lint, type-check, coverage or test sections, and for newly added suppressions (`# noqa`, `# type: ignore`, `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `//nolint`, `.skip(`, `@pytest.mark.skip`), and tell the model and the user.

**Ratchets for existing debt.** When turning on a rule the codebase already breaks (complexity, file length, coverage), measure today's worst value and set the enforced limit there, then lower it as hotspots are fixed. Starting from a textbook default fails the build on day one and invites blanket suppressions. A global ceiling does not stop a function from growing up to it, so keep reviewing the largest offenders.

## 4. Rule hooks from repeated corrections

When `rules-from-corrections.md` concludes that a correction needs mechanical enforcement, express it as a small declarative rule that one generic hook evaluates, instead of writing a new script per rule:

```yaml
name: warn-console-log-in-src
enabled: true
event: file            # shell | file | prompt | stop
action: warn           # warn adds context and lets the call run; block denies it
conditions:
  - field: file_path
    operator: regex_match
    pattern: ^src/.*\.(ts|tsx|js)$
  - field: new_text
    operator: contains
    pattern: console.log(
message: Use the project logger (src/lib/log.ts) instead of console.log in application code.
```

- **Patterns:** too broad matches innocent text (`log` matches `login` and `dialog`); too narrow misses variants (`rm -rf /tmp` instead of `rm\s+-[a-zA-Z]*r`). Escape `.` and `(`; remember that YAML double-quoted strings need doubled backslashes; test each pattern against examples that must match and examples that must not.
- **Evaluation limits:** reject nested quantifiers, cap input length and evaluation time, and skip a malformed or oversized rule file with a diagnostic so one bad rule does not disable the others.
- **Trust:** keep rule files local and ignored by Git by default. Rules committed to a repository should stay inactive until the user enables them, and their message text reaches the model labeled as rule text, not as user instructions.
- **Lifecycle:** list rules with their state, disable without deleting, and review them with the rest of the configuration (`workspace-config-audit.md`).

## 5. Completion checks at Stop

A `Stop` hook can hold the agent to the facts it must establish before ending its turn:
- tests were run after the last edit (compare the transcript's last test command with the last edit);
- no debug output (`console.log`, `print(` in non-script code, `debugger`) or new `TODO` markers were added in changed files;
- formatting and type-checks pass for files changed this turn.

Block with a specific reason only when the agent can fix the problem in this turn. Read `stop_hook_active`: on the second pass, let the agent stop and report the unmet check to the user instead of blocking again. Keep the check to files changed this turn.

## Done when

- Each hook in use matches a pattern above or has a written reason; it was offered to the user and installed only with their OK.
- Gates print nothing on the allowed path, gate sensitive targets fully, and their benefit was checked against runs without them.
- Format and lint hooks use the project's own tools and configuration, stay per-file after edits and batch heavy checks at `Stop`, and CI runs the same checks.
- Check configurations are protected, and suppressions or config changes made during a turn are reported.
- Rule hooks have tested patterns, local or opt-in rule files, and an off switch; stop hooks cannot loop.
