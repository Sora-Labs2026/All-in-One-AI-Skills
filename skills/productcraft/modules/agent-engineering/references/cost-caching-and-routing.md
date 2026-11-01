# Cost tracking, prompt caching, model routing, and rules before models

Read this when LLM or agent spend needs to be measured, explained or reduced; when you add prompt caching or check why its hit rate is low; when you route work between models or effort levels; and when you decide whether a step needs a model at all. Budgets inside loops are in `autonomous-loops.md`; hard spending caps and payments are in `spending-controls.md`; prompt cost tips for app features are in `../../ml-engineering/references/prompt-design.md`.

Prices, cache rules and model names change often. Read the provider's current pricing and caching pages before using any number, and record the date and source next to every price you use. Facts below are stated as of October 2026.

## Measure first

- **Log usage per call:** model identifier returned by the API, input tokens, output tokens, cache write and cache read tokens, latency, the run, session and step ids, and the route or feature. Never log prompt contents just to count tokens.
- **Know the counter semantics of your API.** Some APIs report ordinary input separately from cache reads and writes (Claude: `input_tokens` is the uncached part, with `cache_creation_input_tokens` and `cache_read_input_tokens` beside it). Others report cached tokens as a subset of the input total (OpenAI: `prompt_tokens_details.cached_tokens` or `input_tokens_details.cached_tokens`). Adding the subset to the total counts it twice.
- **Per-call records versus cumulative snapshots.** Some tools write a running total per session at each checkpoint. Summing every row multiplies the cost; take the latest row per session.
- **Price from a dated table you maintain,** not from constants scattered in code. When a model is missing from the table, report it as unpriced rather than guessing.
- **Judge cost per completed task,** not per request. A cheaper request that needs more turns, retries or human fixes is not cheaper.

Summarize a usage log offline:

```bash
python3 <productcraft>/modules/agent-engineering/scripts/usage_cost.py usage.jsonl --prices prices.json
python3 <productcraft>/modules/agent-engineering/scripts/usage_cost.py costs.jsonl --cumulative --prices prices.json --budget 25 --json
```

It reads JSON Lines usage records in either counter convention, applies your price table (per million tokens, with cache write and read rates), and reports totals by model, session and day, unpriced models, the token cache hit rate, the cost without caching for comparison, and whether a budget was exceeded (exit 1). It never reads prompt text.

## The levers, in order

1. **Free wins:** prompt caching, removing input nobody needs (duplicate instructions, unused tool definitions, oversized tool results; `context-budget-and-compaction.md`), stopping runaway loops, bounding output length, and batch endpoints for work that can wait (commonly about half price, results within a day; check the provider).
2. **Trade-offs, measured on your evaluation:** a lower effort or reasoning setting on the same model, a smaller model for a route, fewer review passes. Each one is accepted only if the quality checks still pass (`agent-evals.md`).
3. **Architecture:** deterministic code instead of a model for the steps that allow it (below).

## Prompt caching

Providers cache the processed prefix of a prompt so repeated requests with the same prefix cost less and start faster. It does not shrink the context window; cached tokens still count toward it.

**Design for a stable prefix:**

- Put content that never changes first and changing content last. For Claude the render order is tools, then system, then messages; a breakpoint on the last system block caches tools and system together.
- Any byte difference invalidates everything after it. Common silent invalidators: a timestamp or request id in the system prompt, JSON serialized with unstable key order, a tool list that varies by request, switching model or certain request settings mid-conversation, editing or deleting earlier turns.
- When requests share a long preamble but end in a unique question, place the cache breakpoint at the end of the shared part, not at the very end; otherwise each request pays to write an entry nobody reads.
- Keep history append-only in multi-turn agents so each turn reuses the previous prefix.
- Caches are per model. Routing one conversation across several models forfeits reuse.

**Claude specifics (October 2026; verify current docs):** explicit `cache_control` breakpoints or top-level automatic caching; at most 4 breakpoints per request; a minimum cacheable prefix that depends on the model (from 512 to 4,096 tokens), below which nothing is cached and no error is raised; a 5-minute default lifetime refreshed on every read, or a 1-hour option. Writes cost about 1.25 times the base input price for the 5-minute lifetime and 2 times for 1 hour; reads cost about 0.1 times base input or less on some newer models. With 5-minute entries, two requests already break even; with 1-hour entries, at least three.

**Other providers:** many cache automatically above a minimum prefix length and report cached tokens in the usage block; some offer explicit cache objects billed for storage time as well. Read the endpoint's own rules and counters before estimating.

**Measure, do not assume:**

- Token hit rate = cache reads divided by all input tokens (ordinary plus writes plus reads); also report the share of requests with any cache read. State the period and denominator.
- If reads stay at zero across requests that should share a prefix, look for an invalidator by diffing two consecutive request payloads.
- Counterfactual savings = cost of all input at the ordinary rate, minus actual cost of ordinary, write and read tokens (plus any storage charge). Output cost is unchanged by caching; never apply a cache discount to the whole bill. A prefix written once and never read costs more than no caching.

**Boundaries:** check authorization before content is assembled into a prompt. A cache key or cache handle is not an access-control mechanism, and provider-side isolation does not replace the application's own checks. Do not share cached material across users or workspaces unless it was approved for that scope.

## Model and effort routing

- **Start from the evaluation, not a size chart.** Run the route's task set on the candidate models and settings, and pick the cheapest one whose quality and failure rate meet the bar (`agent-evals.md`).
- **Try lower effort on the strong model before building a cascade.** On current models, a lower reasoning or effort setting often holds quality on routine work at a fraction of the cost, keeps one cache namespace, and avoids routing bugs.
- **Route on observable features of the request** (task type, input size, required tools, risk) with thresholds tuned from logged outcomes, not on the model's own claim that a task is easy.
- **Escalate on evidence:** move a task up a tier when the cheaper attempt fails a check, not by default. Log every routing decision with its reason so thresholds can be tuned.
- **Keep model names in configuration,** never scattered through code, and re-run the evaluation when a model is retired or replaced.
- **Review and security work** go to the stronger setting by default; a missed vulnerability costs more than the tokens saved.

## Retries without waste

- Retry only transient failures: rate limits (honor the `retry-after` header), server errors, connection resets, timeouts on idempotent calls.
- Fail fast on authentication, permission, validation and malformed-request errors; retrying them burns money for the same answer.
- Use exponential backoff with jitter and a retry budget per run. SDK default retries plus your own wrapper can multiply attempts; know both.
- A write that timed out is not retried until its outcome is reconciled (`harness-construction.md`).

## Rules and code before models

Use deterministic code for anything with a stable structure, and a model only where judgment or messy language is needed.

| Use code (regex, parsers, schemas, lookups) | Use a model |
|---|---|
| Consistent formats: generated reports, logs, forms, invoices from one system, CSV and JSON | Free-form or highly variable text |
| Exact matching, routing on known keywords, validation | Meaning, intent, tone, summarization |
| Arithmetic, totals, dates, units | Reconciling ambiguous references |

A hybrid pipeline that works:

1. Parse with code first; write tests for the known formats and edge cases (encodings, missing fields, multi-line values).
2. Validate each record: required fields present, values in range, totals add up. Flag records that fail validation with the reasons.
3. Send only the flagged records to a model, with the original text and the failed checks, and require structured output against a schema.
4. Validate the model's output with the same checks; records that still fail go to a person.
5. Measure on a labeled sample: parser accuracy, model accuracy on flagged records, and cost. Do not quote coverage figures you have not measured on your own data.

## Done when

- [ ] Usage is logged per call with model, tokens by category, latency and ids; prices come from a dated table.
- [ ] Reports use the right counter convention and deduplicate cumulative snapshots; unpriced models are reported, not guessed.
- [ ] Caching was verified with usage counters, with hit rate and counterfactual savings stated for a named period.
- [ ] Every routing or effort change was accepted on the evaluation, with cost per completed task reported.
- [ ] Retries are limited to transient errors within a budget.
- [ ] Deterministic steps are handled by tested code, and model output is validated before use.
