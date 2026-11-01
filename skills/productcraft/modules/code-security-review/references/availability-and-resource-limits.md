# Resource exhaustion and availability

Read this when untrusted requests, files, messages or tenant data can consume shared CPU, memory, disk, connections, worker slots, queue capacity or money, or can crash or stall a shared process. The [vulnerability classes](vulnerability-classes.md#16-other-classes-to-keep-in-view) cover regular-expression blowup, zip bombs in archives and entity expansion in XML; [AIG-20](ai-generated-code-bugs.md#aig-20-no-limits-on-expensive-endpoints) covers missing limits on expensive endpoints; login throttling belongs to Credential Shield. This file is the method for everything else.

## When it is a finding

Three things are needed. Without them it is a performance note or hardening:

1. **A path from input to cost.** Name the entry, the accepted size or count, and the work or resource it drives.
2. **No effective bound on that path.** Check every layer before saying "unbounded": proxy and framework body limits, parser depth limits, pagination caps, queue and concurrency limits, database constraints and statement timeouts, per-tenant quotas, gateway limits. Bounds outside the repository are `NOT_VERIFIED`, not absent.
3. **Impact beyond the requester.** Other users, a shared service, a safety function, or money the operator pays. Slowing down your own request, or a worker that only serves you, is not a vulnerability.

Weigh four things: attacker effort against service work (one small request causing seconds of CPU differs from sustained volume), whether the effect persists after the request ends, whether it is reachable before authentication, and how the service recovers.

## Never prove it by load

Do not stress, flood or saturate any shared, staging or production system. Prove availability findings by analysis plus small local measurements:

- Derive the complexity from the code: what grows with input size, nesting, count or fan-out.
- Measure three or four small sizes in a local process with hard limits, and show the growth curve: `timeout 10s`, `prlimit --as=1073741824 --cpu=10 <command>`, or `systemd-run --user --scope -p MemoryMax=512M -p CPUQuota=50% <command>`. Stop at the first size that shows the trend.
- For leaks, repeat a bounded number of operations and count what remains: open descriptors (`ls /proc/<pid>/fd | wc -l`), pool connections, temp files.
- Mock paid APIs and message senders. Count calls instead of making them.

## Build an input-to-resource table

| Entry | Earliest size or count limit (where) | Work before authentication | Amplification | What is retained | Shared pool | Cleanup and recovery |
|---|---|---|---|---|---|---|
| `POST /api/import` | 10 MB at the proxy (`nginx.conf:41`) | none | zip, then CSV rows, then one query per row | rows, temp files | DB pool of 20, 4 workers | temp dir cleaned on success only |

The finding is usually one cell: a limit that applies before an expansion step but not after it, cleanup that runs only on success, or a pool shared by every tenant.

## Classes to hunt

**Superlinear work**
- Nesting depth in JSON, XML, YAML, protobuf or GraphQL drives recursion. Deep input exhausts the stack or the time budget in recursive parsers, validators, serializers and resolvers.
- YAML anchors and aliases turn a small document into a huge structure when code walks or copies it. Some libraries cap aliases (SnakeYAML's `maxAliasesForCollections`); others do not.
- Hash tables keyed by attacker strings. Mainstream runtimes randomize string hashing (Python since 3.3) or degrade gracefully (Java's `HashMap` turns long buckets into trees since Java 8). Hand-written C tables and custom hash functions often do neither.
- Sorting, diffing, graph traversal, template expansion and permission evaluation, where cost grows with the square of the input or worse.
- GraphQL depth, aliases and fragments. Set depth and cost limits, and paginate list fields.

**Expansion after the size check**
- Compressed request bodies inflated by middleware: check whether the body limit applies before or after decompression.
- Archives: the expanded total, entry count and nesting.
- Images: pixel dimensions, not file size. Pillow warns above `Image.MAX_IMAGE_PIXELS` (about 89.5 million pixels by default) and raises an error above twice that; other libraries need explicit limits.
- PDFs, office files, SVG and fonts rendered server-side.
- Any limit must be checked again after each stage that can grow the data.

**Unbounded queries and fan-out**
- `limit` or `pageSize` with no maximum.
- `include` and `expand` parameters that pull related records.
- Exports that build the whole result in memory instead of streaming it.
- Wildcard or regex search against large indexes.
- One request that sends a notification to every member of a large group, or calls every configured webhook.
- Fix by capping server-side, using cursor pagination, streaming large results, and moving heavy work to a bounded queue.

**Accumulation**
- In-memory caches keyed by user input without size bounds or eviction.
- Metrics labels holding user IDs, raw paths or error messages: each distinct label set is a new time series, and monitoring falls over.
- Sessions, uploads, pending jobs, open sockets or subscriptions per user, with no cap and no expiry.
- Log volume an anonymous user can drive onto a shared disk.

**Leaks on error and cancellation paths**
- Descriptors, database connections, cursors, subprocesses, timers and temp files acquired before an exception and released only on the success path.
- In garbage-collected languages, look for missing `finally` or `with` or `defer` blocks around pooled resources.

**Work that outlives the request**
- A client disconnect or timeout that does not cancel server work: a Go handler ignoring `r.Context()`, a Node handler with no abort wiring, a database query with no `statement_timeout`, outbound calls with no timeout ([language pitfalls](language-pitfalls.md) covers the client defaults).
- An abandoned request keeps holding a worker and a connection.

**Event loop and pool starvation**
- Synchronous CPU work or synchronous I/O on an event loop (large `JSON.parse`, synchronous hashing or compression, `readFileSync` in a Node handler; blocking calls inside Python `async` code). One request stalls everyone.
- One tenant able to fill a shared worker pool, database pool or queue with no per-tenant concurrency limit.

**Expensive work before authentication**
- Parsing large bodies, decompressing, verifying signatures over large payloads, rendering, or calling external services before the caller is identified and limited.
- Order the cheap checks first: size, then authentication, then rate, then the expensive work. Password hashing on a login endpoint is expected cost; its throttling belongs to Credential Shield.

**Quota scope and accounting**
- Limits keyed on a spoofable `X-Forwarded-For`.
- Per-IP limits that IPv6 users escape by rotating addresses within their /64 (key on the prefix).
- In-memory counters in a service that runs several instances: each instance counts separately.
- Quotas that reset on reconnect, token refresh or account switch.
- Check-then-increment races ([race conditions](vulnerability-classes.md#10-race-conditions)).

**Failure and recovery**
- Crash on input:
  - an uncaught exception or unhandled promise rejection ends the Node process by default since Node 15;
  - a Go panic in a goroutine the handler started ends the whole program (`net/http` recovers panics only in the handler's own goroutine);
  - a Rust panic in a service ([Rust](rust.md#panics)).
- Poison messages retried forever block a queue or partition. An SQS redrive policy with `maxReceiveCount` and a dead-letter queue is the usual remedy; Kafka consumers need explicit skip-and-park logic.
- Retry storms: retries at several layers multiply (three layers of three retries make 27 attempts). Retries without exponential backoff, jitter and a cap amplify an outage.
- Crash loops: startup replays a journal entry or migration step that crashes again on every restart.
- Limiters and fraud checks that fail open when their store is down ([AIG-19](ai-generated-code-bugs.md#aig-19-fail-open-error-handling)).

**Operator spend**
- Model tokens and agent steps ([LLM and agent risks](vulnerability-classes.md#15-llm-and-agent-risks)).
- SMS, voice and email sends.
- Outbound bandwidth.
- Serverless invocations and autoscaling that turn traffic into a bill.
- Look for per-user and global budgets with alerts, and idempotent sends so retries do not double the cost.

## Fixes that hold

- Bound at the earliest point (proxy and framework body limits), again after every expansion step, and in aggregate per request, per tenant and per process. A per-item limit is not an aggregate limit: ten thousand valid small items still exhaust the pool.
- Propagate deadlines end to end: from the client timeout, through every outbound call and query, to cancellation of background work started for the request.
- Use bounded queues with back-pressure: reject early with `429` or `503` and `Retry-After`, rather than accepting work you cannot finish.
- Quarantine poison inputs after a fixed number of attempts. Retry with exponential backoff, jitter and a ceiling, and add circuit breakers around failing dependencies.
- Give each tenant its own concurrency and quota on shared pools, so one tenant degrades only itself.
- Write a regression test with a small oversized input that expects a fast refusal, plus a leak test that repeats an operation and checks the resource count returns to baseline.

## Rating

Use the [severity rules](audit-phases.md#phase-6-rate-severity). The demonstrated result is typically "a component stalled for other users" (`MEDIUM`). It is higher when one unauthenticated request causes a lasting outage of a shared service, or when the operator's spend is unbounded. It is lower when recovery is automatic and fast, or when the requester needs a privileged role. Say in the finding how the service recovers: automatically, by restart, or by manual cleanup.

## Done when

- Every entry that accepts size, count, depth or fan-out has a row in the input-to-resource table, with the limit's location or `NOT_VERIFIED`.
- Each candidate names the input, the work or resource, the missing bound, the shared blast radius and the recovery, and is proven by analysis plus bounded local measurement, never by load.
- Cancellation, timeout, cleanup-on-error and retry behavior are cited for queues, workers and outbound calls.
- Fixes add limits at the earliest point and after each expansion step, with regression tests that expect a fast refusal.
