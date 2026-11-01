# Context budgets, compaction and subagent context

Read this when a session or an agent you are building runs short of context, when answers degrade late in long sessions, when an installation of skills, tools and instruction files feels heavy, or when you plan how a long task will survive compaction or a session restart. Token cost and caching are in `cost-caching-and-routing.md`; handing work between sessions is in `../../engineering-practices/references/session-handoff.md`.

## Measure before trimming

- **Live usage:** use the agent tool's own context or usage command, or, for your own API calls, the usage block returned with every response and the provider's token-counting endpoint (for Claude, `POST /v1/messages/count_tokens`). Do not replace a native meter with an estimate.
- **Estimates are estimates.** Characters divided by about four, or words times about 1.3, are rough for English prose and wrong for code, other languages and images. Say "estimated" whenever you report them, and never present an estimate as provider-reported usage or as realized savings.
- **Tokenizers differ between model families,** and a newer tokenizer can count the same text differently. Re-measure after a model change.

## What fills the window

| Source | Loaded | Typical fix |
|---|---|---|
| Always-loaded instruction files (`CLAUDE.md`, `AGENTS.md`, rule folders) | Every request | Keep them short and true; move detail into files read on demand |
| Tool definitions from tool servers and plugins | Every request, unless the platform defers them | Enable per project only what the work needs; use deferred loading or tool search where supported |
| Skill, agent and command descriptions | Usually every request (names and descriptions only) | Remove unused ones; keep descriptions specific and short |
| Conversation history | Grows each turn | Phase boundaries, compaction, fresh sessions |
| Tool results: file reads, logs, search output, web pages | When called | Read ranges, search before reading, truncate and page, summarize to a file |
| Images and documents | When attached | Crop, downscale, extract the relevant pages |

Full skill bodies and reference files usually load only when used; count them separately from the always-loaded baseline.

### Always-loaded instructions that earn their place

Keep in them:

- the build, test, lint and run commands, exactly as they work;
- conventions the code does not make obvious, and the boundaries (files not to touch, actions that need approval);
- where to find more: paths to design docs, runbooks and references to open on demand.

Keep out: tutorials, long examples, rules already enforced by linters or hooks, history, and anything repeated from another always-loaded file. When user-level and project-level instruction files disagree, the agent follows one at random; resolve the conflict in the files. Review them when the project changes, because a stale command in an always-loaded file misleads every session. Linting these files for correctness is in `../../builder-tools/references/agent-config-linting.md`.

### A bounded installation audit

When asked to audit what an installation costs, stay read-only and bounded: inspect only the named configuration roots, never the whole home directory, transcripts or caches; do not start tool servers or provider CLIs just to count tools; cap long inventories and summarize the rest. Report what was inspected, estimated always-loaded overhead by component type, the heaviest entries, and at most a few concrete removals. Point back to the native meter for live usage.

### Tool servers versus command-line tools

Each tool server adds its schemas to every request while enabled. For services with a good command-line client (version control hosting, cloud CLIs, database clients), an occasional operation through the shell, wrapped in a small documented command or skill, can cost less context than a permanently loaded server. The trade-offs: shell output must be parsed, the permission model is the shell's, and secrets must still stay out of the command line. Decide per project, and prefer platform features that load tool definitions on demand when available.

## Keep tool results small

- Search first (`rg -n`), then read the relevant range, not whole files.
- Pipe long command output through `tail`, `head` or `grep`, or write it to a file and read the part that matters.
- Tools you build return summaries with identifiers and paths, page large results, and truncate with a note (`harness-construction.md`).
- Do not paste the same log, plan or file twice. Refer to the earlier copy or the file path.

## Subagents protect the main context

Delegate reading-heavy work (exploring a subsystem, scanning many files, researching documentation) to a subagent that returns conclusions with file paths and line references, not raw content. Rules for splitting and briefing are in `../../engineering-workflow/references/parallel-work.md`. Two additions for context:

- **Pass the purpose, not just the query.** A subagent asked "find the auth middleware" without knowing you need to add rate limiting returns the wrong level of detail. State the objective, what you already know, and what form the answer should take.
- **Refine in a few rounds.** Check what comes back, ask targeted follow-up questions about the gaps (terms the codebase uses, related files the first pass missed), and stop after two or three rounds; then proceed with what you have and say what is still unknown.

## Compaction at the right moment

Compaction (manual or automatic) replaces the history with a summary. What survives is whatever is written down; nuance that lived only in the conversation is lost.

| Persists | Lost unless written down |
|---|---|
| Files on disk, git history and branches | Reasoning and alternatives considered |
| Always-loaded instruction files | Contents of files read earlier |
| Notes, plans and state files you wrote | Preferences the user stated in passing |
| Task lists only if the tool keeps them outside the context | Exact error messages and partial results |

- **Write state first.** Before compacting or restarting, save the plan, decisions with reasons, what is done (with evidence), what failed and why, and the next concrete step to a file (`../../engineering-practices/assets/handoff-template.md`). Do not rely on a task-list feature to survive; it may not exist on every version or model.
- **Compact at phase boundaries:** after research and before implementation, after a finished milestone, after a failed approach (to drop the dead end), when switching to unrelated work.
- **Do not compact mid-edit** or mid-debugging, when variable names, paths and partial state are all in play.
- **Steer the summary** when the tool allows it ("keep the migration plan and the failing test names").
- **Prefer a fresh session** for a large phase change; start it from the written handoff, not from memory of the old one.
- **Signs you waited too long:** the agent repeats steps, forgets stated constraints, contradicts earlier decisions or re-reads files it already read. Stop, write state, compact or restart.

## Long-running agents you build

- **Clear before you summarize.** Old tool results that were already acted on can often be dropped or replaced by a short note; this is cheaper and more exact than summarizing everything. Several provider APIs offer context editing (clearing old tool results) and server-side compaction; when you use compaction, keep the compaction blocks the API returns in the history exactly as returned.
- **Append, do not rewrite.** Editing or reordering earlier turns breaks prompt caching from that point and, on some current models, invalidates earlier reasoning blocks. Add corrections as new messages.
- **Keep exact data out of summaries.** Ids, amounts, paths and decisions go into structured state files, not into prose that a summarizer may paraphrase.
- **Memory is not context.** A memory store the agent reads on demand keeps the window small, but what it returns is evidence to check, not truth (`memory-and-learning.md`).

## Done when

- [ ] Usage was measured with the native meter or the provider's counter, and estimates are labeled.
- [ ] Always-loaded instructions and enabled tools are limited to what the project uses.
- [ ] Large outputs are searched, ranged, paged or written to files instead of pasted.
- [ ] State was written to a file before any compaction or restart, at a phase boundary.
- [ ] For agents you build: old tool results are cleared or compacted by a documented mechanism, and history stays append-only.
