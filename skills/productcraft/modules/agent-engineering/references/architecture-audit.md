# Auditing and debugging an agent system

Read this when an agent or LLM feature misbehaves and nobody knows which part is at fault, when "the model got worse" after a change to the surrounding code, when the same model works in a direct API call but not inside the product, or before an agent system ships. It also covers debugging one failing run and smoke-testing an agent runtime end to end. An audit changes no code until its findings are reported; fixes follow the normal workflow in `../../engineering-workflow/GUIDE.md`.

## Map the layers first

Every agent system wraps the model in layers, and any of them can corrupt a correct answer. List the ones this system has, with the file or service that implements each:

| Layer | What goes wrong |
|---|---|
| Request intake and routing | Wrong agent or route chosen; request text altered before the model sees it |
| Instruction assembly (system prompt, rule files, injected context) | Conflicting or stale instructions; the same rule in three places with three wordings |
| Conversation history | Old turns leak into new tasks; truncation drops the turn that mattered |
| Long-term memory and retrieval | Facts from another user, project or topic; the agent's own guesses stored as facts; corrections overwritten by older entries |
| Summaries and compaction | Lossy summaries re-enter as authoritative facts |
| Tool selection | Required tool skipped; wrong tool for the job; tools overlap |
| Tool execution | The model says it called a tool that never ran; arguments not validated |
| Tool result interpretation | Errors read as data; a failed operation read as "not found"; truncated output treated as complete |
| Secondary model passes | Hidden repair, rewrite, guard or summarizer calls change the answer without a contract |
| Output shaping and parsing | Format repair mangles content; schema coercion drops fields |
| Delivery and rendering | Streaming, Markdown or UI code corrupts a correct answer; terminal and UI disagree |
| Persistence and caches | Expired state or cached outputs served as live evidence |

## Collect evidence before theorizing

1. **Reproduce** the symptom with a fixed input, and record the exact request the model received: the fully assembled prompt, tool definitions, model id and settings. Without the assembled prompt you are guessing.
2. **Run the wrapper test.** Send the same task straight to the model with only the essential instructions. If the direct call is right and the product is wrong, the fault is in the layers, not the model. Then add layers back one at a time (memory, retrieval, history, post-processing) until the failure returns.
3. **Diff a good run against a bad one:** assembled prompts, tool call sequences, memory entries retrieved, post-processing steps applied.
4. **Check claims against execution records.** For every tool call the transcript mentions, find the matching execution log entry. A claimed call without a record is a tool-discipline failure.
5. **Search the code** for patterns that hide layers, then read each hit:

```bash
rg -n "messages\.create|chat\.completions|responses\.create|generate_content|\.invoke\(" --type py --type ts   # every model call site
rg -n -i "retry|fallback|repair|re-?prompt|rewrite|self[-_ ]?correct" --type py --type ts   # second passes
rg -n -i "must (always )?(call|use)|always use the .* tool|never answer without" -g '*.md' -g '*.txt' -g '*.py' -g '*.ts'   # requirements stated only in prompts
rg -n -i "memory|remember|persist|save_fact|upsert" --type py --type ts   # memory admission paths
```

Adapt the patterns to the codebase's language and SDKs. A hit is a lead to read, not a finding.

## Failure mechanisms to look for

- **Wrapper regression:** each added layer was reasonable, together they bury or contradict the instruction that mattered. Evidence: the direct call passes, the full stack fails, removing one layer fixes it.
- **Memory contamination:** content from another session, project or user appears; the agent's own unverified statements were stored as facts; a user's correction did not stick because an older memory outranks it. Check the admission path: who may write, what is stored, how conflicts are resolved (`memory-and-learning.md`).
- **Tool discipline failure:** a required lookup is mandated only in prompt text and skipped under pressure; results are hallucinated. Fix by enforcing the step in code (`harness-construction.md`).
- **Hidden second passes:** a repair or rewrite call runs on failures or always, without logging, and replaces the answer. Make every model call visible in traces, with a stated contract, or remove it.
- **Delivery corruption:** the logged answer is right, the user sees something else. Compare the final model output with what the transport sent.
- **Stale persistence:** cached tool results, summaries or state files from an earlier run are read as current. Look for missing expiry or version checks.

Do not blame the model before ruling out the layers, and do not blame memory without showing the path by which the wrong content got in. A clean state today does not erase a documented failure yesterday; find out how it happened.

## Write findings

For each finding record:

- **Symptom:** what the user saw.
- **Mechanism:** how the layer produced it.
- **Layer** from the map above.
- **Root cause:** the deepest cause you can show.
- **Evidence:** `file:line`, trace or request ids, and the minimal reproduction.
- **Confidence:** high, medium or low, with the reason (reproduced and ablated; reproduced only; inferred from code).
- **Fix:** the smallest change that removes the cause.

| Severity | Meaning | When to fix |
|---|---|---|
| Critical | The agent can confidently take wrong actions or give wrong operational answers | Before the next release |
| High | Correctness or stability degrades often | This cycle |
| Medium | Usually correct, but fragile or wasteful | Planned |
| Low | Maintainability or cosmetic | Backlog |

Report findings by severity, then the diagnosis (which layer corrupted what), then an ordered fix plan. Lead with the problems; no preamble.

## Fix order: code before prompts

1. Enforce required steps and risky-action gates in code.
2. Remove or narrow hidden second passes; give any that remain an explicit contract and a trace.
3. Remove duplicated context so each fact has one source.
4. Tighten memory admission: user corrections outrank agent assertions; nothing the agent merely said becomes a stored fact without evidence.
5. Stop compressing what must stay exact (ids, amounts, decisions).
6. Make delivery pass the answer through unchanged.
7. Replace prose hand-offs between components with typed envelopes.
8. Only then tune prompt wording, and measure each change (`agent-evals.md`).

## Debugging one failing run

When a single run loops, stalls or burns tokens without progress, stop retrying and diagnose.

1. **Capture:** goal, last successful step, the failing tool call or command, the error text, the repeated pattern, and the environment assumptions (working directory, branch, services, files expected).
2. **Classify:** logic (wrong hypothesis), state (files, branch or data not as believed), environment (service down, wrong port, quota), or policy (permission denied, blocked action). Decide whether it is deterministic or transient.

| Pattern | Likely cause | First check |
|---|---|---|
| Same command repeated | No exit path, or the observation never changes | Last N tool calls; what new information each produced |
| Quality drops late in a long run | Context bloat: pasted logs, repeated plans | What fills the context; summarize to goal, evidence, blockers |
| Connection refused or timeout | Service not running, wrong host or port | Health endpoint, the configured URL |
| HTTP 429 or quota errors | Retry storm, missing backoff | Call count and spacing |
| File missing right after a write | Wrong directory, branch or worktree | `pwd`, `git status`, the absolute path |
| Tests still failing after the "fix" | Wrong hypothesis | Run the single failing test; re-derive the cause (`../../engineering-workflow/references/debugging.md`) |

3. **Run one discriminating check** that would prove the diagnosis wrong, then take the smallest reversible action. Never claim a recovery action ("reset state", "updated the config") that did not actually run.
4. **Report:** failure, root cause, action taken, evidence that it worked or that it is still blocked, tokens and time spent, and a preventive change worth encoding (a harness check, a stop condition).

## Smoke-testing an agent runtime end to end

When a remote sandbox or hosted agent calls back into a local or staging API through a gateway or tunnel:

- Use an isolated test agent, test data and a non-production copy of the app; get the owner's agreement before exposing a local service through a tunnel, and scope the tunnel to the one authenticated route.
- **Install cleanup first:** record the original API target of the app, and restore it on success, failure, timeout or interruption. Track only processes and resources the test created.
- Start the API and tunnel; check the API's health; probe the gateway route anonymously and expect the documented 401 or 403, and confirm the probe appears in the local API log (an edge response alone proves nothing).
- Switch the app to the test target only after both checks pass; confirm a request reaches the local API.
- Run one tool-free task with an exact expected answer. A queued or running task is not a pass; the task must reach a terminal state with the matching answer and an observed callback.
- Restore the original target, verify it works, then stop the test processes. If restoration fails, report it at once.
- Report: API healthy, probe status and log confirmation, callback observed, task status and answer match, route restored, open blocker. Keep tunnel URLs, credentials and private logs out of the report. Test connected tools separately, with test accounts and no writes to real accounts.

## Done when

- [ ] The layer map exists with an owner file or service per layer.
- [ ] Each finding has mechanism, layer, evidence, confidence and fix, and critical findings were reproduced.
- [ ] The fix plan is ordered code-first and each fix has a check that shows it worked.
- [ ] Nothing was changed during the audit without the owner's go-ahead.
