# Building an agent harness: loop, tools, permissions and context

Read this when you write or restructure the code around a model that calls tools: the loop that sends requests and runs tool calls, the tool set and what tools return, the permission model, and how the context is assembled each turn. Designing an MCP server's tools in detail is in `../../builder-tools/references/mcp-server-design.md`; prompts inside an application's features are in `../../ml-engineering/references/prompt-design.md`.

## Pick the simplest tier that works

| Tier | Who decides the next step | Use when |
|---|---|---|
| Single call | Nobody; one request, one answer | Classification, extraction, summarizing, one-shot drafting |
| Workflow | Your code: fixed steps, branches and retries; the model fills in each step | The path is known in advance (extract, validate, enrich, file) |
| Agent | The model, choosing tools in a loop | The path cannot be specified up front and errors are recoverable |

Move up a tier only when the task is hard to specify step by step, the outcome justifies the extra cost and latency, the model is measurably capable at the task (`agent-evals.md`), and mistakes can be caught and undone (tests, review, rollback). A workflow with one model-driven step is often enough.

Hosted agent runtimes, agent SDKs and tool-runner helpers can supply the loop for you. Use them when they fit; the rules below still apply to whatever you configure.

## The loop controller

- **You own the loop limits.** Maximum turns, a wall-clock deadline, a timeout per tool call and a token or cost ceiling, all enforced in code (`autonomous-loops.md`).
- **Branch on the stop reason** the API returns: tool use (run the tools and continue), end of turn (done), output limit reached (the answer is truncated; do not parse it as complete), refusal or safety stop (handle explicitly), pause (resume as the provider documents). Read it on every response.
- **Return every tool result.** When the model requests several tools at once, run them (concurrently if independent) and return all results together; report a failed call as an error result rather than dropping it.
- **Validate tool inputs before running them.** Parse arguments as JSON, check them against the tool's schema and your own rules (paths inside the workspace, ids that exist, amounts within limits), and return a clear error result when they fail. Do not string-match the serialized input.
- **Stream long responses** and set request timeouts that match the expected generation time; a client timeout with automatic retries can multiply wall-clock time and cost.
- **Retry only transient failures** (rate limits, server errors, connection resets) with exponential backoff and jitter, within the budget. Authentication, permission and validation errors fail fast.

## Tools: the action space

- **Few, task-shaped tools** with distinct names and precise schemas. Overlapping tools cause wrong choices; a catch-all "run anything" tool defeats the permission model.
- **Narrow tools for risky operations.** Deploy, migrate, delete, send and pay get their own tools with tight schemas, so the harness can gate exactly those (`approval-gates.md`). Reads and writes are separate tools.
- **Requirements live in code, not in prompt text.** If a step is mandatory (check the cache before calling the vendor, run the tests before committing, look up the contract before drafting), enforce it in the harness: refuse the later tool until the earlier one ran, or run the step yourself. "You must always call X" in a prompt is a request, not a guarantee.
- **Observations the model can use.** Each tool result states success, warning or error; a one-line summary; the identifiers or paths produced; and, for errors, the likely cause, whether a retry is safe, and when to stop trying. Large outputs are truncated with a note and a way to page or read the rest from a file.
- **Deterministic shapes.** The same tool returns the same structure every time, so the model and your code can rely on it.

## Interpret tool results in layers

A tool call can fail at three levels; check them in order and keep them distinct:

1. **Transport or envelope:** the call itself errored, timed out or returned something malformed. Outcome: tool error or unknown.
2. **Operation status:** the call returned, but the operation reports failure (maintenance, not found, permission denied) in the field the tool documents. An outer "success" flag or a non-empty payload does not prove the operation succeeded. A missing or unrecognized status is unknown, not success.
3. **Payload:** only after confirmed success, validate the shape and compare fields (ids match, totals add up).

Rules that follow:

- An operation failure is not a data mismatch; report it as what it is, with the request id and the original response (secrets and private data redacted).
- A failed or ambiguous **read** never proves that a **write** failed. If a write timed out, reconcile through a documented status or read-back before any retry, and never overwrite on the basis of a failed read.
- A classification authorizes nothing: a "transient" label does not by itself permit a retry of a write, and one authorization error does not prove a service-wide outage. Follow the tool's documented recovery policy; stop a batch on a confirmed service-wide failure rather than repeating the call for every row.

## Permissions

- **Allowlist per phase.** Analysis phases get read-only tools; implementation phases get edit tools inside the workspace; outward actions get gated tools. Never start an unattended agent with a blanket permission bypass.
- **Bind actions to tools.** Record which tool may read, write or publish for each kind of operation. If the bound tool cannot do something, report the gap and hold that operation; do not silently route the write through another tool that happens to be able to. Only the owner can change a binding, and the change is logged.
- **Bind the entity scope.** The account, project, workspace, period and exclusions the run may touch are part of its inputs, separate from search filters. Apply the scope to discovery, batch preparation and remaining-work reports, not only to writes. An ambiguous scope holds that group of work.
- **The agent cannot change its own permissions, budgets or policy.** Those are set by the operator before delegation and enforced outside the model.
- **Secrets by name.** Credentials are injected at the tool boundary (environment of the tool process, a vault the runtime substitutes at egress), never placed in prompts, context, logs or memory. Pass a subprocess only the environment variables it needs (`../../agent-safety/references/secrets.md`).
- **Validate at the action boundary.** Identifiers, paths, URLs and irreversible operations are checked in code immediately before each side effect; the hardening checklist is in `../../agent-safety/references/harness-hardening.md`.
- **Untrusted content is data.** Tool results, fetched pages, files, issues and messages can contain instructions. Keep them in tool-result or clearly delimited data positions, never interpolate them into trusted instructions, and do not let them trigger privileged tools without a gate. Run agents that read untrusted content in isolation (`../../agent-safety/references/isolation.md`).

## Context assembly

- **Small, stable system prompt.** Identity, rules that apply to every turn, and how to find more. Keep it byte-identical across requests so provider prompt caching works (`cost-caching-and-routing.md`).
- **Load guidance on demand.** Long instructions live in files, skills or references the agent opens when the task needs them. Point to files instead of inlining documents.
- **One source per fact.** The same rule repeated in the system prompt, memory and history wastes context and drifts out of sync; when the copies disagree the model picks one at random.
- **Typed hand-offs between components.** Planner to builder, builder to judge, tool to tool: pass JSON with a schema (status, artifacts, evidence, open questions), not free prose that the next step must re-interpret.
- **Budget the window.** Measure what the instruction files, tool definitions and typical tool results cost before adding more (`context-budget-and-compaction.md`).

## Observability

- Trace every model request and tool call with a run id and step id: model identifier actually returned, stop reason, token usage (including cache reads and writes), latency, cost, tool name, arguments (redacted), outcome class.
- Keep traces long enough to explain a surprising run, and short enough to respect the data's retention rules. Redact secrets and personal data before storage.
- Count per run: turns, tool errors by class, retries, budget spent, stop condition. These numbers find harness bugs faster than reading transcripts one by one.

## Re-test harness assumptions

Every component (a planner, context resets, a separate judge, retry wrappers, forced step order) exists because the model once needed it. When the model, the provider or the task mix changes, run the evaluation suite with and without each component and remove what no longer helps (`agent-evals.md`).

## Done when

- [ ] The tier is justified, and the loop enforces turn, time, token and cost limits in code.
- [ ] Stop reasons, truncation, refusals and parallel tool results are handled; tool inputs are validated.
- [ ] Mandatory steps and risky actions are enforced by the harness, not by prompt wording.
- [ ] Tool results are interpreted in three layers; unknown write outcomes are reconciled, never blindly retried.
- [ ] Permissions, action-to-tool bindings and entity scope are explicit; secrets never enter the context.
- [ ] Traces record model, tokens, cost, latency and outcome per step.
