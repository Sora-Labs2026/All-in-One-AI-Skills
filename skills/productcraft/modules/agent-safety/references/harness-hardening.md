# Hardening the agent harness

Reference for the `agent-safety` module. Read this when setting up a coding agent for a person or a team, before running one with broad auto-approval or unattended, when it will read content other people wrote (issues, pull requests, email, web pages, attachments) while holding credentials, or when building the runtime that turns model output into actions. The command guard, the stop-check and isolation (`command-guard.md`, `isolation.md`) are parts of this; this file is the whole picture and the minimum bar.

Contents: the design assumption · repository trust · identities and credentials · permissions and approval boundaries · untrusted content · memory · logging · unattended runs and kill paths · building the runtime · minimum bar · done when.

## The design assumption

Sooner or later the agent will read hostile text while holding something valuable. Text in a README, an issue, a web page, a PDF, a tool result or an MCP tool description can carry instructions, and no prompt wording reliably stops a model from acting on them. So design for the case where the model loses that argument, and make the loss survivable:

- **Break the dangerous combination.** Private data, untrusted content and a way to send data out (network tools, email, chat, auto-loaded image links, pushes to public places) must not all be present in one session. Remove at least one: no outbound channel, no secrets, or no untrusted input.
- **Put the boundary between the model and the action,** in permission rules, hooks, sandboxes and server-side authorization. Instruction-file text such as "never reveal secrets" or a list of "prompt defense" phrases is advice to the model, not a control; keep it short if you keep it at all.
- **Keep the blast radius small:** what a compromised session can reach is what you gave it.

## Repository trust: what loads when a folder is opened

Opening a project can load configuration written by whoever controls that repository:

| File | What it can do |
|---|---|
| `.claude/settings.json` and similar agent settings | Hooks that run shell commands on events, permission allow-lists, environment variables for the session (an API base URL or proxy pointing elsewhere sends your traffic and key there), helper commands that run to fetch credentials |
| `.mcp.json` and editor MCP files | Start programs or connect to remote servers, possibly with auto-approved tools |
| `CLAUDE.md`, `AGENTS.md`, rule and skill folders | Instructions the agent reads at session start |
| `.devcontainer/`, `.vscode/tasks.json`, `.envrc`, Git hooks and config | Commands run by the editor, the shell or Git on the host |

Before trusting a folder you did not write, list and read these:

```bash
git ls-files | grep -E '(^|/)(\.claude/|\.mcp\.json$|\.vscode/|\.devcontainer/|CLAUDE\.md$|AGENTS\.md$|\.envrc$|\.husky/)'
grep -rnE '"(hooks|env|apiKeyHelper|enableAllProjectMcpServers|permissions)"|BASE_URL|_PROXY' .claude .mcp.json .vscode 2>/dev/null
python3 <productcraft>/modules/agent-safety/scripts/scan_skill.py .                  # hooks, permissions, hidden text, remote code
python3 <productcraft>/modules/agent-safety/scripts/audit_mcp_config.py .            # MCP declarations
```

Accept the host's trust prompt only after that review, and treat the files like an extension (`vetting-extensions.md`). Keep the agent host updated: hosts have shipped fixes for flaws where project files ran code or redirected API traffic before the trust prompt was answered, and an outdated host keeps those flaws. For code you do not trust at all, open it only inside a sandbox (`isolation.md`).

## Identities and credentials

If the agent uses your accounts, a compromised agent is you.

- **Give the agent its own identities:** a bot or machine user for the Git host, a separate mailbox or chat bot instead of your own, a separate cloud role. Each can be revoked without touching yours.
- **Short-lived and narrow:** fine-grained tokens limited to one repository and the permissions the task needs, expiring in days rather than never; test-mode payment keys; read-only database roles.
- **Spending limits** on model API keys and any paid service the agent can call, set at the provider, not only in the agent.
- **Nothing ambient:** no production credentials in the shell profile the agent inherits, no cloud CLI logged in with an admin role, no SSH agent forwarding unless the task needs it (`secrets.md`).

## Permissions and approval boundaries

Grant the least agency the task needs, and make the host ask, or refuse, before these:

- shell commands outside the sandbox, and anything in the risk classes of `destructive-commands.md`;
- network access to destinations the task did not name;
- reading secret-bearing paths (`secrets.md` has deny rules for the file tools);
- writes outside the project;
- dispatching CI workflows, deploying, publishing, sending email or messages, spending money.

Practical settings:
- Use the host's permission rules and modes rather than a blanket bypass. Run with permission checks skipped only inside a sandbox with no production credentials and a closed or allow-listed network.
- Deny rules that match shell command text are best effort: wrappers, aliases and scripts get around them. Pair them with the command guard and a sandbox.
- In unattended runs nobody answers a prompt, so "ask" must become "deny" (`command-guard.md`, `--ask-as-deny`).
- Review allow-lists periodically; entries granted once for an experiment accumulate (`../../builder-tools/references/workspace-config-audit.md`).

## Untrusted content

- **Separate reading from acting.** For workflows that process outside content (email, tickets, attachments, scraped pages), let one step with no tools and no credentials extract the facts into a fixed structure, validate that structure in code, and give only the validated result to the agent that can act. The acting agent never sees the raw text.
- **Strip what humans cannot see** before a privileged agent reads it: HTML comments, hidden elements, document metadata, zero-width and direction-control characters. A quick check:

  ```bash
  rg -nP '[\x{200B}-\x{200F}\x{202A}-\x{202E}\x{2060}-\x{2064}\x{2066}-\x{2069}\x{FEFF}]|<!--' PATH
  ```

- **Do not auto-follow links** from untrusted text in a session that holds credentials. A skill or rule that tells the agent to fetch a URL whose content can change is a standing injection channel: inline the content you need, or pin it to a reviewed version.
- **Review bots and pull requests:** an agent that reviews outside contributions should not hold write tokens or secrets, and outsider comments should not reach it as instructions (`../../code-security-review/references/ci-agent-workflows.md`).

## Memory

Anything stored in agent memory or instruction files that load automatically is read again in later sessions, so an injected instruction can wait and act later.

- Store memory only with the user's knowledge; keep it reviewable (plain files the user can read) and erasable.
- No secrets, tokens or personal data in memory files.
- Keep project memory separate from user-wide memory, so one repository's content cannot steer work in another.
- After a session that processed untrusted content, review what was written to memory, or discard it. For high-risk workflows, turn long-lived memory off.

## Logging

You cannot investigate what you did not record. For agent sessions that matter, keep a local, structured log of: session or task id, tool name, a redacted input summary, files touched, approval decisions (allowed, asked, denied), and network destinations attempted.

- Redact before writing: never log secret values, full environment dumps or whole file contents.
- Session transcripts and tool logs are sensitive data: restrict access, set a retention period, and delete on schedule. Sending them to a hosted service needs the user's explicit opt-in.
- Baseline normal sessions so odd calls stand out: a documentation task that suddenly reads `~/.aws` or posts to an unknown host.

## Unattended runs and kill paths

Every autonomous or long-running agent loop needs, before it starts:
- **a budget:** wall-clock time, tokens or turns, and money, enforced outside the model;
- **stop conditions:** done criteria, a maximum number of attempts per subtask, and stop on repeated identical failures;
- **checkpoints:** commits or snapshots the user can roll back to;
- **an approval gate** for anything consequential (merges, deploys, external messages, spending), even when everything else runs alone.

A stop path that relies on the agent agreeing to stop is not a stop path. Run the agent under a supervisor that can end it:

```bash
set -m                                   # job control: each background job gets its own process group
agent-command --args > run.log 2>&1 &
pgid=$!                                  # the group id equals the job's first PID
kill -TERM -- "-$pgid"; sleep 10; kill -KILL -- "-$pgid" 2>/dev/null   # whole group: polite, then forced
```

```python
import os, signal, subprocess
proc = subprocess.Popen(cmd, start_new_session=True)        # own process group
os.killpg(proc.pid, signal.SIGTERM)                          # then SIGKILL after a grace period
```

Kill the process group, not only the parent; children (dev servers, test runners, browsers) otherwise keep running and holding ports and memory. For long runs, add a heartbeat: the worker updates a file or endpoint at a fixed interval, and the supervisor kills the group when it goes stale for longer than the task can justify. Keep a stalled run's logs and workspace for review instead of retrying it blindly.

## Building the runtime: checks at the action boundary

When you write the code that executes model decisions (a tool gateway, an agent framework, an MCP server), validate in code immediately before each side effect, even if a schema or prompt validated earlier:

- **Identifiers** that become file names, keys or command arguments: allow-list characters and length; pass them as separate argv entries after `--`, never inside a shell string.
- **Paths:** reject absolute paths and `..`, resolve both root and candidate, check containment by path components (not string prefix: `/work/app` vs `/work/application`), and handle symlinks; for portability also reject Windows device names (`CON`, `NUL`, `COM1`), trailing dots or spaces, and `:` stream syntax.
- **URLs:** allowed schemes only, no embedded credentials, block private and link-local destinations, re-check every redirect, and drop credentials when the origin changes (`../../code-security-review/references/vulnerability-classes.md`, SSRF).
- **Irreversible operations:** check that the authenticated principal may perform this operation on this resource, then require confirmation or a scoped pre-approval. Missing evidence means no action.
- **Tool output:** read with a byte limit, strip terminal control sequences, mark truncation explicitly with the original size, and return a typed error for malformed output instead of an empty success.
- **Temporary files and secrets:** owner-only permissions (`0600` files, `0700` directories), created atomically with unpredictable names, removed in `finally`; secrets kept out of arguments, logs, traces, exceptions and model context.
- **Limits** come from the requirement or deployment config; when none is defined, record it as an open decision and reject unbounded configuration rather than inventing a number.

Test each through the real entry point with a hostile input and assert the side effect did not happen. Mocks do not prove OS permissions, symlink handling or network egress rules.

## Minimum bar

- Agent identities separate from personal accounts; short-lived, narrow credentials; spending limits.
- Project configuration reviewed before a folder is trusted; host kept updated.
- Untrusted work runs in a container or VM; network closed or allow-listed by default (`isolation.md`).
- Reads of secret-bearing paths denied; approvals required for egress, off-project writes, deploys and external messages.
- Untrusted content cleaned or quarantined before a privileged agent sees it; no auto-followed links.
- Tool calls, approvals and network attempts logged locally, redacted, with retention.
- Unattended runs have budgets, stop conditions, checkpoints, a supervisor with a process-group kill, and a heartbeat.
- Memory narrow, reviewable, erasable and free of secrets.
- Skills, hooks, MCP declarations and agent definitions vetted like any other supply-chain artifact (`vetting-extensions.md`).

## Done when

- The user has seen which items of the minimum bar are met, which are not, and the concrete change for each gap, and approved any change to settings, sandbox or credentials before it was made.
- Repository configuration in the session's scope was reviewed, with findings reported.
- For unattended setups, the kill path was tested (start a harmless long command under the supervisor, stop it, confirm nothing of the group still runs: `ps -eo pid,pgid,stat,command | awk -v g=<pgid> '$2 == g'` should list nothing, or only entries in state `Z`, which have exited and wait to be reaped).
- The report lists what was verified by running a check and what was only read.
