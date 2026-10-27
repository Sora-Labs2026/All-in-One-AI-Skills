# Error handling and resilience

Read this when code calls a database, another service, a queue or a third-party API; when you write retry, fallback or error-handling logic; or when a dependency outage should not take the whole product down.

Every remote call has three outcomes: it worked, it failed, or you do not know. Design for the third one explicitly.

## Classify failures before handling them

| Kind | Examples | Handling |
|---|---|---|
| Expected business outcome | Insufficient balance, email already used, item out of stock | Return a typed result or a 4xx with a stable code; not an exception and not an error log |
| Invalid input | Schema violation, unknown ID | Reject at the boundary with a clear message; never retry |
| Transient infrastructure | Connection reset, timeout, 502/503/504, 429, gRPC `UNAVAILABLE`, deadlock or serialization failure | Retry with backoff if the operation is idempotent; otherwise surface "unknown outcome" |
| Permanent infrastructure | Authentication to a dependency failed, missing table, misconfiguration | Fail fast, alert, do not retry in a loop |
| Bug or broken invariant | Null where impossible, unreachable branch reached | Fail loudly, log with context, let the supervisor restart the worker; do not continue on corrupt state |

## Error handling in code

- **Handle an error where something useful can be done:** retry, fall back, translate it for the caller or the user, or clean up. Otherwise let it propagate.
- **Never swallow.** An empty `catch`, `except: pass` or `.catch(() => {})` hides failures until data is wrong. If ignoring an error really is correct, say why in a comment and record a metric.
- **Keep the cause.** JavaScript: `throw new Error("Charging order failed", { cause: err })`. Python: `raise PaymentError("charging order failed") from err`. Go: `fmt.Errorf("charge order %s: %w", id, err)`.
- **Log once, at the boundary** that handles the error (request handler, job runner), with the request ID and relevant identifiers. Logging and rethrowing at every layer produces the same failure five times.
- **Separate what the user sees from what operators see.** Users get a clear message and a request ID; logs get the details; responses never carry stack traces or internal names.
- **Fail fast at startup.** Validate required configuration and environment variables when the process starts and refuse to start without them, rather than failing on the first request.
- **Clean up deterministically:** `finally`, Python context managers (`with`), Go `defer`, and closing pools on shutdown, so errors do not leak connections, locks or temporary files.
- **Global safety nets** (`process.on("unhandledRejection")`, a framework error middleware, an error boundary in the UI) log and report; they are not a substitute for handling errors where they occur.

## Timeouts and deadlines

- **Every network call gets an explicit timeout.** Many clients default to none or to minutes: Python `requests` waits indefinitely unless you pass `timeout=`, and `fetch` has no per-request timeout unless you pass a signal.

```python
resp = session.get(url, timeout=(3.05, 10))   # (connect, read) seconds
```

```ts
const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
```

- Set database statement timeouts and connection-acquire timeouts on the pool, so a slow query or an exhausted pool fails within a bounded time.
- **Budget from the outside in.** If the edge gives a request 10 seconds, the handler cannot wait 10 seconds on each of three dependencies. Pass a deadline down (gRPC deadlines, a context or `AbortSignal`) and give each call what remains, minus a margin.
- Choose timeout values from observed latency (for example a little above the dependency's p99), not from round numbers.

## Retries

- **Retry only transient failures, and only operations that are idempotent** or carry an idempotency key (see `api-contracts.md`). Never blindly retry a payment, an email send or a non-idempotent `POST`.
- **Capped exponential backoff with jitter.** Without jitter, every client retries at the same instant and hits the recovering service together. A common form is "full jitter": wait a random time between 0 and `min(cap, base * 2^attempt)`.
- **Bound the attempts and the total time** (for example 3 attempts within the caller's deadline). Honor `Retry-After` when the server sends it.
- **Retry at one layer.** Three layers that each retry three times multiply load on a struggling dependency by up to 27. Decide which layer owns retries (usually the one closest to the failing call) and turn the rest off.
- **Limit retry volume.** A retry budget (for example retries may add at most 10% to normal traffic) or a circuit breaker stops retries from turning a slowdown into an outage.
- Prefer the project's existing retry helper or the client library's built-in retry, configured explicitly. If you must write one:

```ts
async function withRetry<T>(
  op: (signal: AbortSignal) => Promise<T>,
  isTransient: (err: unknown) => boolean,
  { attempts = 3, baseMs = 100, capMs = 2_000, perTryMs = 3_000 } = {},
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await op(AbortSignal.timeout(perTryMs));
    } catch (err) {
      if (attempt + 1 >= attempts || !isTransient(err)) throw err;
      const ceiling = Math.min(capMs, baseMs * 2 ** attempt);
      await new Promise((resolve) => setTimeout(resolve, Math.random() * ceiling));
    }
  }
}
```

## Circuit breakers, bulkheads and load shedding

- **Circuit breaker per dependency.** Closed: calls pass and failures are counted over a rolling window. Open: once the failure rate passes a threshold (with a minimum number of calls), calls fail immediately for a cool-down period. Half-open: a few trial calls decide whether to close again. Export the state as a metric and log transitions. Established libraries exist for most stacks (for example resilience4j, Polly, opossum, pybreaker); use one rather than writing your own.
- **Bulkheads.** Give each dependency its own connection pool or concurrency limit, so one slow dependency cannot consume every worker or connection.
- **Bounded queues everywhere.** An unbounded in-memory queue turns overload into memory exhaustion and huge latency. When full, reject with 503 and `Retry-After`, or apply backpressure upstream.
- **Shed load early.** Rejecting excess requests at the edge is cheaper than accepting them and timing out after doing most of the work.

## Graceful degradation

- For each dependency, decide in advance what the product does when it is down: serve cached or stale data marked as such, hide a non-essential panel, queue the action for later, or fail the request with a clear message.
- **Never fake success.** If a payment, booking, deletion or permission change did not complete, the user must not be told it did. Show pending or failed, consistent with `../../interaction-feedback.md`.
- Keep operational kill switches (flags) for expensive or risky features so they can be turned off without a deploy (see `ci-and-release.md`).
- Test each fallback: a fallback that has never run is a second, untested failure path.

## Queues, jobs and messages

- Assume at-least-once delivery. Make consumers idempotent: deduplicate by message or event ID, or make the effect naturally idempotent (upsert, set state).
- Set the visibility timeout or acknowledgement deadline longer than the slowest normal processing time, and acknowledge only after the effect is durable.
- Cap redeliveries and move poison messages to a dead-letter queue that is monitored, with a documented replay procedure.
- **Database plus event consistency.** Writing to the database and then publishing to a broker can lose or duplicate events if the process dies between the two. Use a transactional outbox: write the event to an outbox table in the same transaction as the data change, and let a relay publish and mark it sent.
- Scheduled jobs: prevent overlap (a lock or a single-instance scheduler), make reruns safe, and record last success so missed runs are visible.

## Health checks and shutdown

- **Liveness** answers "is this process stuck?" and should not check dependencies, or an outage of the database makes the orchestrator restart every healthy instance.
- **Readiness** answers "can this instance serve now?" and may check critical dependencies with short timeouts and caching.
- **Graceful shutdown:** on `SIGTERM`, stop accepting new work, finish in-flight requests and jobs within the platform's grace period, then close pools and flush telemetry.

## Testing failure paths

- Unit-test classification: which errors are transient, which are retried, how many times, and that non-idempotent calls are not retried.
- Use a fake dependency (or a local proxy that injects faults) to return 503, hang past the timeout, reset connections and return malformed data. Assert the timeout fires, retries stop at the cap, the breaker opens and the fallback runs.
- Run fault-injection experiments only in local, CI or staging environments, and in shared environments only with the owner's approval.

- Planned chaos experiments and game days (hypothesis, blast radius, abort conditions, tools) are in `../../cloud-infrastructure/references/chaos-engineering.md`.

## Checks (done when)

- [ ] Every outbound call in the change has an explicit timeout, and nested timeouts fit inside the caller's deadline.
- [ ] Retries apply only to transient errors on idempotent (or keyed) operations, with capped backoff and jitter, at one layer.
- [ ] Each new dependency has a decided degraded behavior, and no failure path reports success.
- [ ] Errors keep their cause, are logged once with the request ID and expose no internals to users.
- [ ] Consumers are idempotent and poison messages end in a monitored dead-letter queue.
- [ ] At least one test exercises the timeout or failure path of each new dependency.

## Anti-patterns

- Calls without timeouts, or one generous timeout copied everywhere.
- Retrying everything, including 400s and non-idempotent writes; retrying in a tight loop without backoff.
- Retries at the client, the SDK, the service mesh and the job runner all at once.
- `catch (e) { return null }` that turns an outage into missing data.
- A liveness probe that fails when the database is down.
- Publishing an event and updating the database as two independent steps.
- Showing "Saved" before the server confirmed the save.
