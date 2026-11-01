# Auditing and cleaning the agent workspace configuration

Read this when someone asks what their agent setup can actually do, which automations are live, broken or redundant, why sessions start slowly or feel noisy, or to clean up a configuration that has grown by accretion. Also run it after installing a large skill or plugin pack and as a periodic review. Agent configuration only ever grows: skills, hooks, permission entries, MCP servers, memory notes and scheduled jobs get added and almost never removed, and the leftovers cost context, speed and review effort.

Contents: ground rules · inventory · live state · problems per channel · decisions · cleaning up safely · report · done when.

## Ground rules

- **Read first, change later.** The audit produces an inventory and recommendations. Changes happen only after the user decides, item by item.
- **Names, never values.** Report that `.env` defines `STRIPE_SECRET_KEY`, never its value (`../../agent-safety/references/secrets.md`).
- **Stay in scope:** the agent's own configuration folders (user-level and project-level) and the automation surfaces the user named. Never touch source code under the banner of a config cleanup.
- **Configured is not working.** Every claim about a surface cites proof: a file path and line, a command's output, a recent run, a log entry. If the state cannot be established, say so.

## 1. Inventory

| Surface | Where to look | How |
|---|---|---|
| Instruction files | User and project `CLAUDE.md`, `AGENTS.md`, rule folders, imported files | Line counts, last change (`git log -1 --format=%cs -- FILE`) |
| Skills | Every loaded skill root | `skill-inventory-and-portability.md`, section 1 |
| Hooks | `hooks` in each settings scope, plugin hook files, scripts on disk | Snippet below |
| Permissions | `permissions.allow`, `ask`, `deny` in each settings scope | Snippet below |
| MCP servers | Project and user declarations; the host's live list | `../../agent-safety/scripts/audit_mcp_config.py`; in Claude Code `claude mcp list` or `/mcp` |
| Plugins and extensions | The host's plugin list | What each one adds: skills, hooks, servers |
| Services implied by environment | Variable names in `.env*` files | `for f in .env*; do [ -f "$f" ] && echo "$f: $(grep -v '^#' "$f" | cut -d= -f1 | tr '\n' ' ')"; done` |
| Scheduled and CI automation | crontab, user timers, CI workflows | `crontab -l`, `systemctl --user list-timers`, `grep -l 'schedule:' .github/workflows/*.y*ml` |
| Caches and session history | The host's config folder | `du -sh ~/.claude/*/ 2>/dev/null \| sort -h` |

Hooks and permission entries across the three Claude Code settings scopes (adapt the file list for other hosts):

```bash
python3 -I - <<'EOF'
import collections, json, pathlib, re
home = pathlib.Path.home()
files = [home / ".claude/settings.json", pathlib.Path(".claude/settings.json"), pathlib.Path(".claude/settings.local.json")]
rules, commands = collections.defaultdict(list), []
for f in files:
    if not f.is_file():
        print("absent:", f); continue
    data = json.loads(f.read_text())
    for kind in ("allow", "ask", "deny"):
        for rule in data.get("permissions", {}).get(kind, []):
            rules[(kind, rule)].append(str(f))
    for entries in data.get("hooks", {}).values():
        for entry in entries:
            commands += [h.get("command", "") for h in entry.get("hooks", [])]
for (kind, rule), where in sorted(rules.items()):
    if len(where) > 1:
        print(f"duplicate {kind}: {rule}  ({', '.join(where)})")
allowed = {r for k, r in rules if k == "allow"}
for rule in sorted(allowed & {r for k, r in rules if k == "deny"}):
    print("both allowed and denied:", rule)
wide = {r.split("(")[0] for r in allowed if "(" not in r or r.endswith("(*)")}
for rule in sorted(allowed):
    if "(" in rule and not rule.endswith("(*)") and rule.split("(")[0] in wide:
        print("shadowed by a tool-wide allow:", rule)
joined = "\n".join(commands)
for d in (home / ".claude/hooks", pathlib.Path(".claude/hooks")):
    for script in sorted(d.iterdir()) if d.is_dir() else []:
        if script.is_file() and script.name not in joined:
            print("orphan script (no hook entry runs it):", script)
for path in re.findall(r"[\w${}~./-]*\.claude/hooks/[\w.-]+", joined):
    local = re.sub(r"^\$\{?CLAUDE_PROJECT_DIR\}?/", "", path).replace("~", str(home), 1)
    if not pathlib.Path(local).exists():
        print("dangling entry (script missing):", path)
EOF
```

## 2. Label the live state

For each automation, record one of: **configured** (declared), **authenticated** (credentials present and accepted), **recently verified** (seen working, with the proof), **stale or broken** (failing, pointing at something missing, or not run when expected), **missing** (needed but absent). Then name the problem type: active breakage, authentication failure, stale status, overlap, or missing capability. Fix the most important broken path before tidying redundancy.

## 3. Problems to look for, per channel

| Channel | Signals |
|---|---|
| Instruction files | Long always-loaded files; catalogs (lists of every agent, command or skill) that belong in on-demand files; commands that no longer exist; rules that contradict each other or repeat a skill; fixed numeric targets nobody checks |
| Skills | Overlap, stale tool names or flags, broken links or scripts, never loaded where usage is measured (`skill-inventory-and-portability.md`) |
| Hooks | Orphan scripts, entries pointing at missing scripts, two hooks doing the same job (two formatters on one file type), slow hooks (measure, `hook-design.md`), hooks for tools the project no longer uses |
| Permissions | Duplicates across scopes, entries shadowed by a tool-wide allow, one-off grants from past experiments, rules both allowed and denied, unrestricted shell allows (`Bash` or `Bash(*)`) |
| MCP servers | Servers that fail to connect, duplicates across scopes, servers nobody uses (each adds tool definitions to every session), mutable package references |
| Memory notes | Contradicting entries, dates that have passed, fragments that should merge, anything secret |
| Scheduled jobs | Jobs whose target script is gone, one-time jobs that already ran, schedules nobody owns |
| Caches and history | Large, old folders. Session history may be wanted; it also holds sensitive content, so prefer a retention setting (in Claude Code, `cleanupPeriodDays`) over ad-hoc deletion |

## 4. Decide: keep, merge, cut or fix next

Give each suspect item one call with its evidence. For a capability the user needs but does not have, pick the right shape:

| Gap | Shape |
|---|---|
| A short convention that applies to most tasks | One line in the instruction file |
| A repeatable multi-step workflow | Skill (`skill-authoring.md`) |
| Must happen automatically on an event, decidable by a script | Hook (`hook-design.md`) |
| A specialized role with its own tools and context | Subagent definition |
| Access to an external system | Existing MCP server or connector, reviewed (`../../agent-safety/references/mcp-config-review.md`), or a new one (`mcp-server-design.md`) |
| Must hold for every contributor | CI check |

Prefer a thin skill over an existing tool to a new subsystem, and recommend at most a few next moves, ordered by impact.

## 5. Clean up safely

1. **Rank and cap.** Present at most about twenty candidates per run, highest confidence first (broken and orphaned before merely old).
2. **One decision per item.** Show the evidence and ask yes, no or skip for each. No "apply all".
3. **Reversible first.**
   - Skills: move the folder to a dated archive outside the loaded roots (`~/.claude-archive/2026-11-01/`). Renaming a folder inside a skill root usually does not stop the host from loading it.
   - Hook scripts: move to the archive; remove the settings entry.
   - JSON settings (hooks, permissions, MCP entries): copy the file to a dated backup, record each removed entry verbatim in the log, edit with a JSON-aware tool, then check the file still parses (`python3 -m json.tool FILE > /dev/null`).
   - Delete for good only when the user asks.
4. **Age is a signal, not a verdict.** A skill untouched for months may be seasonal. Merging memory or instruction notes means reading both and keeping the current truth, not keeping the longer one.
5. **Log every run** in a small file next to the configuration: date, item, reason, where it went, how to undo.
6. **Verify afterwards:** the host starts cleanly, `/hooks` (or the host's equivalent) lists what you expect, MCP servers that should connect do, and a quick task still works.

Changes to permissions, hooks and MCP declarations are agent-configuration changes: follow the confirmation rules in `../../agent-safety/GUIDE.md`.

## 6. Report

```text
CURRENT SURFACE    item | source | live state | proof
FINDINGS           breakage | auth failures | stale | overlap | missing
DECISIONS          item | keep / merge / cut / fix next | evidence
NEXT MOVES         at most 3 to 5, ordered by impact
CHANGES MADE       item | action | backup or archive location | undo
NOT CHECKED        surfaces outside scope or without access
```

## Done when

- Every in-scope surface is listed with a live-state label backed by proof, and secret values never appeared.
- Each suspect item has a keep, merge, cut or fix-next call with evidence; gaps have a recommended shape.
- Every change was confirmed individually, made reversibly, logged with an undo path, and followed by a verification that the host still starts and works.
