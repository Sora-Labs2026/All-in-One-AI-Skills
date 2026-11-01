# Low-latency and freshness-critical systems

Read this when tail latency or data freshness is the requirement, not just "fast enough": realtime dashboards and feeds, market-data and order-routing paths, game and voice back ends, request paths with strict p99 or p99.9 targets, streaming pipelines, ingest queues and caches in front of them. The general measure-profile-change loop, caching rules and web performance are in `../../engineering-practices/references/performance.md`; timeouts, retries and bounded queues in `../../engineering-practices/references/resilience.md`; push transports in `realtime-websockets.md`; firmware timing in `embedded.md`. Nothing here authorizes trading, placing orders or giving financial advice.

## Define the target precisely

A latency requirement has five parts; get all five from the user before optimizing:

1. **The span:** from which event to which visible effect (exchange timestamp to rendered price; request received to response sent; sensor reading to alert).
2. **The percentile:** p50, p99, p99.9 or the maximum. Users and downstream systems feel the tail; an average says nothing about it.
3. **The load:** at what request or message rate, and with what burst pattern.
4. **The window:** over what period and which measurement (per minute, per trading session).
5. **Freshness**, where data is involved: the age of the data the user sees (now minus the source timestamp), separate from how fast the request returned. A 5 ms response serving a 30-second-old price is fast and wrong.

Write them as one line: "p99 tick-to-screen under 250 ms and data age under 1 s, at 2,000 updates per second with 5x bursts, measured per minute during market hours."

## Measure the tail correctly

- **Record full distributions,** not averages: histograms with fixed precision (HdrHistogram and its ports, or the metrics library's native histograms). Percentiles cannot be averaged across hosts or intervals; merge the histograms, then read the percentile.
- **Coordinated omission:** a closed-loop load generator (each virtual user waits for its response before sending the next) sends less when the system stalls, so the stall barely shows in the results. Use open-loop, constant-arrival-rate load (wrk2, k6's `constant-arrival-rate` executor, Gatling's open models) and measure latency from the intended send time.
- **Clocks:** durations come from monotonic clocks (`System.nanoTime`, `time.monotonic_ns`, `std::chrono::steady_clock`, Rust `Instant`, Go `time.Since`). Cross-host spans (freshness, one-way latency) need synchronized wall clocks: chrony or NTP for millisecond accuracy, PTP with hardware timestamping for microseconds. Record the clock-sync error alongside the numbers.
- **Per-hop timing:** stamp each message at every stage (received, decoded, enqueued, dequeued, processed, sent) so you can see where the time goes. Queue wait is usually the largest and least visible part.
- **Benchmark like production:** same instance types, CPU governor, kernel settings, payload sizes and data volume; warm-up excluded and reported separately; several runs with the spread shown.

## Map the hot path and its budget

Draw the path from source to effect and give each hop a share of the budget:

```text
source -> network ingress -> decode -> validate -> queue -> process -> state/cache -> fan-out -> client render
```

- Measure each hop; optimize the largest measured one first.
- **Fan-out amplifies the tail.** If a request waits on 50 backends that each exceed their p99 one time in a hundred, about four requests in ten wait on at least one slow call. Reduce fan-out, set per-call deadlines, or use hedged requests: after the backend's p95 has elapsed, send a second copy to another replica and take the first answer. Hedge only idempotent reads, cap the extra load, and cancel the loser.
- **Little's law** (items in the system = arrival rate x time in the system) connects queue depth to latency: a queue holding 10,000 messages at 2,000 per second adds five seconds. Watch queue depth and age, not only throughput.
- **Deadlines propagate:** each hop receives the remaining budget and gives up when it is spent, instead of every hop applying its own fixed timeout.

## Design techniques, in order of usual payoff

1. **Remove work from the hot path:** round trips, synchronous logging, validation that can move to the edge once, serialization formats heavier than needed. Move non-urgent work (audit writes, analytics, notifications) behind an asynchronous boundary.
2. **Keep hot data local:** in-process state or cache with explicit freshness metadata (source timestamp, version) instead of a network call per request. Stale data must be detectable and flagged, never served silently as current.
3. **Batch with a time limit:** batching raises throughput but adds waiting. Flush on size or a short deadline, whichever comes first, and tune the deadline against the latency budget.
4. **Bound every queue and apply backpressure:** when full, shed load (drop the oldest market-data update in favor of the newest, reject with 503 and `Retry-After`) rather than growing memory and latency. For "latest value wins" data, conflate: keep only the newest update per key.
5. **Split hot and cold paths:** separate thread pools, processes or services so a slow report or export cannot occupy the threads that serve the hot path.
6. **Single writer per piece of state:** one thread or actor owns each mutable structure and others send it messages; this removes lock contention and makes ordering explicit.
7. **Push instead of poll** where freshness matters and clients can hold connections (`realtime-websockets.md`).

## Runtime and language specifics

- **JVM:** allocation drives garbage-collection pauses. Generational ZGC (default ZGC mode since JDK 23; the non-generational mode was removed in JDK 24) and Shenandoah keep pauses in the low milliseconds or below on suitable heaps; measure with GC logs (`-Xlog:gc*`) under production load. Warm up JIT-compiled paths before taking traffic, or use AOT caches (JDK 24 and later) or a native image after measuring their effect on peak throughput. Avoid `synchronized` hot spots and contended `ConcurrentHashMap` keys; JFR shows allocation and lock profiles.
- **Go:** reduce allocations on hot paths (`go test -bench -benchmem`, escape analysis with `-gcflags=-m`); `GOMEMLIMIT` with a tuned `GOGC` bounds GC work; check scheduler latency and GC pauses in execution traces (`go tool trace`). Go 1.25 sets `GOMAXPROCS` from the container's CPU limit.
- **.NET:** Server GC for throughput; measure pause times with `dotnet-counters` and traces; `GCSettings.LatencyMode = SustainedLowLatency` only around measured critical windows; `ArrayPool<T>` and `Span<T>` to cut allocations.
- **C++ and Rust:** no allocation, locking, logging formatting or system calls on the hot path; preallocate buffers and pools at startup; single-producer single-consumer ring buffers between threads; pad shared atomics to separate cache lines (`alignas(std::hardware_destructive_interference_size)`, `crossbeam_utils::CachePadded`) to avoid false sharing; keep data contiguous for the cache.
- **Python and Node.js:** a single event loop or interpreter lock serializes work; keep CPU-heavy steps out of the loop (worker processes, native extensions) and measure event-loop lag directly.

## Operating system and network

These settings affect the whole host. Propose them with measurements and apply them only with the owner's approval, on dedicated machines, never as a side effect of a code change.

- **CPU placement:** pin hot threads to isolated cores (`taskset`, `isolcpus` and `nohz_full` kernel parameters), keep interrupt handling for the network card on other cores, and respect NUMA locality (`numactl`) so threads use memory attached to their socket.
- **Power management:** CPU frequency scaling and deep C-states add wake-up latency; latency-critical hosts usually run the `performance` governor.
- **Memory:** disable swapping for the process (or the host); transparent huge pages in `always` mode can cause pauses during compaction, so prefer `madvise`; lock critical memory (`mlockall`) where the platform allows.
- **Network:** set `TCP_NODELAY` on request-response sockets (Nagle's algorithm delays small writes); reuse connections and TLS sessions; keep payloads small; prefer one region and availability zone for chatty components; UDP multicast for exchange-style market data where the network supports it. Kernel-bypass networking and busy polling cut microseconds at the cost of dedicated cores and operational complexity.
- **Virtualized and shared hosts** add jitter (noisy neighbors, steal time); measure `steal` before blaming the code.

## Correctness guardrails

- **Never trade correctness for speed silently.** Validation, authorization, risk checks and idempotency stay on the path; if a check moves (to the edge, to a precomputed table), its coverage must be equal and tested.
- **Freshness is visible:** every value shown or acted on carries its age; consumers reject or flag data older than its limit; dashboards show "stale" rather than a last-good value with no indication.
- **Kill switches and degraded modes:** a way to stop automated actions immediately and a defined behavior when a provider is late or down (stop quoting, show stale state clearly), tested regularly.
- **Execution-adjacent paths** (order routing, payments, control systems) run against simulators, paper trading or sandboxes during development. Live orders, production deploys and changes to risk limits require the owner's explicit approval.
- Benchmarks and logs contain no secrets, account identifiers or customer data.

## Verify

- Load test with open-loop traffic at the target rate and at burst rate; report p50, p99, p99.9 and maximum per hop and end to end, plus freshness, queue depth and error rates.
- Add a regression guard: a repeatable benchmark in CI with a tolerance, or a production alert on the percentile and on data age.
- After deployment, compare field measurements with the test results; a gap usually means the test environment or traffic shape differs.
- For stale-data and degraded-provider handling, inject the fault (delay the feed, stop a provider) and confirm the system flags it and the kill switch works.

## Done when

- [ ] The target names span, percentile, load, window and freshness limit, agreed with the user.
- [ ] Measurements use histograms, open-loop load and monotonic clocks, with clock-sync error stated for cross-host spans.
- [ ] Each change addressed the largest measured hop and was kept only if the tail improved beyond run-to-run spread.
- [ ] Queues are bounded with a defined overflow behavior; stale data is detectable and visibly flagged.
- [ ] Host-level tuning, live trading and production changes happened only with the owner's approval.
