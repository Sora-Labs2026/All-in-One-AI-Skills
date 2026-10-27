# Linting agent configuration: instruction files, hooks, MCP and plugins

Read this when checking the files that configure a coding agent rather than a skill's own package: agent instruction files (`CLAUDE.md`, `AGENTS.md`), hook definitions in `settings.json`, MCP server declarations (`.mcp.json` and settings), and plugin or marketplace manifests. `scripts/lint_skill.py` checks a *skill folder* (frontmatter, body size, links, stray files). This reference covers everything around the skill: the configuration that decides what loads, what runs automatically and with what permissions.

Two concerns run through all of it: **correctness** (will the host parse and apply this as intended?) and **safety** (does anything run automatically or with more power than its job needs?). Correctness is this module's job; the safety checks hand off to `../../agent-safety/GUIDE.md`, which owns vetting and the `scan_skill.py` scanner.

## Check the host and its version first

These formats are defined by the agent host and change between versions: event names, settings keys, permission-rule syntax and manifest fields are not universal. Before editing, read the installed host's current documentation and look at a working example in the same project. Do not apply a rule from memory; state which host and version you assumed. A config that is valid for one tool can be silently ignored by another.

## Agent instruction files (`CLAUDE.md`, `AGENTS.md`)

These load at the start of every session, so every line costs attention on every task. Lint for value, not just syntax:

- **No generic filler.** "Be helpful", "write clean code", "follow best practices" match everything and change nothing. Remove them; the agent already does this.
- **Concrete and project-specific.** Keep the build, test, lint and run commands; conventions not obvious from the code; and boundaries (what never to touch, what to ask about first).
- **Point, don't paste.** Link a deeper document with a line saying when to read it ("Before changing the billing schema, read `docs/billing.md`"), instead of inlining it.
- **True and current.** A command or convention that has changed is worse than none. Update it in the same change that changes the behavior.
- **No secrets.** Tokens, keys or connection strings never belong here (`../../agent-safety/references/secrets.md`).
- **Right scope.** Project-wide rules in the shared file; personal preferences in a user-level file, not committed for the whole team.

Flag instructions that restate the host's defaults, contradict each other, or tell the agent to skip confirmations or safety steps. The last is a safety finding, not a style one.

## Hooks in `settings.json`

A hook runs a shell command automatically on an agent event, with the user's permissions and no prompt. That makes hooks the highest-risk configuration, so check both that they work and that they are safe:

- **Event name and matcher are valid** for the installed host (events such as before/after a tool runs, on a prompt, on session start, on stop vary by host and version). A misspelled event silently never fires.
- **The command exists and is deterministic.** It reads its input from where the host provides it (usually a JSON payload on stdin), exits with the codes the host expects (commonly 0 for allow and a specific non-zero to block), and does not hang. Parsing the payload needs the tool it assumes (for example `jq`) to be present.
- **It does only what its purpose needs.** A formatting hook has no reason to reach the network, read credentials or edit settings. A hook that runs on every prompt and calls out to a server is a red flag (hand it to agent-safety).
- **Paths are portable.** Use the host's project-directory variable rather than a machine-specific absolute path, and quote paths that may contain spaces.
- **It fails safe.** A hook meant to block an unsafe action must deny when its own check errors, not fall open.

## MCP server declarations (`.mcp.json`, settings)

- **Transport and launch are valid:** the command and arguments resolve, or the URL is reachable for a remote server, in the shape the host expects.
- **Pinned, not floating.** A server launched with a package runner and no version (`@latest`, a tag, no digest) can fetch new code on every start. Pin a version or digest.
- **Least privilege.** Auto-approval of a server's tools, broad tool allow-lists, and write scopes for a read-only purpose are findings. A local (stdio) server runs as the user; a remote one receives whatever its tools are sent, and its tool names and descriptions become model input, so they can carry instructions.
- **Secrets by reference.** Credentials come from the environment or a secret store, never written into the committed config.

Designing an MCP server's own tool surface is `mcp-server-design.md`; this is about the declaration that wires an existing server into the agent.

## Plugin and marketplace manifests

- **Required fields present and well-typed** for the host: name, version, and the entry points it declares (skills, commands, hooks, agents, MCP servers). A name should match its folder and the host's naming rule (usually lowercase and hyphens).
- **Every referenced file exists.** A manifest that lists a command, hook script or skill that is not in the package is broken.
- **Version is real and bumped** when the content changes, so consumers can tell releases apart.
- **The declared capabilities match the contents.** A plugin that claims to add one command but also installs a session hook and an MCP server is under-declaring what it does; that is both a correctness gap and a safety signal.

## How this relates to the bundled scanners

- `scripts/lint_skill.py` (this module): the skill package itself.
- `../../agent-safety/scripts/scan_skill.py`: a safety scan of a third-party extension folder before installing it. It already flags auto-running hooks, broad permission lists, unpinned launchers and install-time scripts in these same config files. Run it for the safety verdict; use this reference for the correctness pass and for configs you are authoring yourself.

A host-specific linter, where one exists and is installed, can check many of these rules mechanically. Run it if the project uses one, read its findings as leads, and still apply judgment: a rule that is right for one host may not fit another, and a passing lint does not mean the configuration is safe.

## Done when

- Each config was checked against the installed host's current format, with the host and version stated.
- Instruction files carry only concrete, true, project-specific guidance with no secrets and no filler.
- Every hook has a valid event, a working deterministic command, fail-safe behavior and no capability beyond its purpose.
- MCP and plugin declarations are pinned, least-privilege, reference only files that exist, and keep secrets out of the committed file.
- Anything that runs automatically or asks for broad power was sent through `../../agent-safety/GUIDE.md` for a safety verdict before being enabled.
