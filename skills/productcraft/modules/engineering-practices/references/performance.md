# Performance

Read this when something is slow, a performance target or budget exists, a change touches a hot path or large data, a page's loading or responsiveness is in question, or someone proposes caching, an index or an optimization.

## The loop

1. **Name the metric and the target.** "p95 latency of `GET /search` under 300 ms at 50 requests per second", "LCP under 2.5 s on the product page for mobile visitors", "CI under 10 minutes". A vague goal ("make it faster") cannot be verified.
2. **Measure a baseline** with a command you can repeat: same machine or environment, same data volume, same warm or cold state. Run it several times (five or more for noisy measurements) and record the median and the spread.
3. **Profile to find where the time goes.** Do not guess; the cost is usually somewhere other than where intuition points.
4. **Change one thing,** aimed at the largest measured cost.
5. **Re-measure the same way.** Keep the change only if the improvement is larger than the run-to-run spread and every test still passes. A neutral result means revert: unmeasured complexity is pure cost.
6. **Guard it.** Add a budget, a benchmark or a monitor so the regression cannot return silently.

Record each attempt in the PR description or the project's performance notes, including reverted ones, as `idea | baseline -> result | kept or reverted | why`, so nobody repeats a dead end.

## Where to look first

| Symptom | Usual causes | First measurement |
|---|---|---|
| One endpoint slow | N+1 queries, missing or unusable index, unbounded result, heavy serialization | Query count and duration per request; query plan |
| Every endpoint slow at once | Connection pool exhausted, CPU saturated, a shared dependency slow, long garbage-collection pauses | Pool wait time, CPU, dependency latency |
| Slow only sometimes | Lock contention, cache expiry storms, noisy neighbors, cold starts | Latency percentiles over time; lock waits |
| Memory keeps growing | Unbounded caches or queues, listeners never removed, large payloads held | Heap snapshots compared over time |
| Page loads slowly | Slow server response, render-blocking CSS or JS, large images, too much JavaScript | Field LCP; lab trace and network waterfall |
| Page reacts slowly to input | Long main-thread tasks, expensive re-renders, layout thrashing | Field INP with attribution; Performance panel recording |
| Layout jumps | Media without dimensions, late-injected content, font swaps | Layout shift attribution in the trace |
| A page or endpoint waits on several calls | Independent requests awaited one after another; data fetched only after a parent component rendered | A network panel or trace waterfall that looks like a staircase |

## Measuring and profiling tools

Run these locally or in staging. Load tests and profilers against production or third-party systems need explicit permission.

- **Request timing:** `curl -o /dev/null -s -w 'ttfb=%{time_starttransfer}s total=%{time_total}s\n' http://localhost:3000/api/search?q=a`
- **Load:** `k6 run load.js`, `npx autocannon -c 50 -d 30 http://localhost:3000/api/search`, `wrk -t4 -c50 -d30s <url>`. Report throughput and p50/p95/p99, not averages.
- **CPU profiles:** Node `node --cpu-prof server.js` (open the `.cpuprofile` in browser DevTools) or `node --inspect`; Python `python -m cProfile -o out.prof app.py` and `python -m pstats out.prof`, or `py-spy record -o profile.svg -- python app.py`; Go `go test -bench . -cpuprofile cpu.out` then `go tool pprof cpu.out`; JVM async-profiler or JDK Flight Recorder. Read the flame graph from the widest frames down.
- **Database:** PostgreSQL `EXPLAIN (ANALYZE, BUFFERS) <query>`. It executes the query, so wrap data-changing statements in `BEGIN; ... ROLLBACK;` and use a non-production copy. `pg_stat_statements` ranks queries by total time. MySQL `EXPLAIN ANALYZE` (8.0.18+) and the slow query log.

- **Database plans in depth:** reading plans, designing indexes and engine-specific tuning for PostgreSQL, MySQL and SQL Server are in `../../data-engineering/references/sql-query-tuning.md`, `../../data-engineering/references/postgresql.md` and `../../data-engineering/references/mysql-and-sql-server.md`.
- **Frontend lab:** `npx lighthouse http://localhost:3000 --output=json --output-path=./lighthouse.json`, browser DevTools Performance panel with CPU throttling (4x to 6x) to approximate mid-range phones, the bundler's analyzer or `npx source-map-explorer 'dist/assets/*.js'`.
- **Frontend field data:** the `web-vitals` library (`onLCP`, `onINP`, `onCLS`, and its attribution build for causes) reporting to your analytics endpoint, plus the Chrome UX Report for public sites.
- **Microbenchmarks** (`pytest-benchmark`, `vitest bench`, Go `testing.B`, JMH) only for code the profile already showed is hot. They mislead easily: warm up, avoid dead-code elimination, use realistic inputs.

- **Numerical, parallel and HPC code** (scaling studies, thread oversubscription, MPI and GPU profilers, Slurm job accounting, memory estimates for large arrays): `../../scientific-computing/references/hpc-and-profiling.md`.

## Backend practices

- **N+1 queries.** One query for the list plus one per row. Detect by counting queries per request (ORM query logging, Django `assertNumQueries`, Rails `strict_loading`, a test helper that fails above N queries). Fix with a join, eager loading (`select_related` / `prefetch_related`, SQLAlchemy `selectinload`, Prisma `include`, ActiveRecord `includes`) or one batched query (`WHERE id = ANY($1)`). In GraphQL, batch with a DataLoader-style loader.
- **Indexes from plans, not hunches.** Read the plan before and after. A sequential scan on a large table, a row estimate off by orders of magnitude (run `ANALYZE` first: statistics may be stale) or a sort above the scan each point to different fixes. Composite index order: equality columns first, then the range or sort column. Functions on columns need expression indexes (`lower(email)`); leading-wildcard search needs trigram or full-text indexes; a rare value of a skewed column suits a partial index. If the plan does not change, drop the index: it still slows every write.
- **Bounded work per request.** Paginate, select only needed columns, cap batch sizes, stream large exports or move them to a background job.
- **Connection pools.** One pool per process. Keep `instances x pool size` below the database's connection limit; with autoscaling or serverless, put a pooler such as PgBouncer or a managed proxy in front instead of raising pool sizes. When the pool runs dry, find what holds connections (long transactions, missing releases) before resizing it.
- **Keep the request path light.** Move slow, non-essential work (emails, thumbnails, webhooks, analytics) to a queue. In Node, never run CPU-heavy synchronous work on the event loop; use worker threads or a separate service.
- **Payloads.** Compress responses (`br` or `gzip`), avoid over-fetching, and prefer one batch call over many small ones across a network hop.

## Caching

Cache only what is expensive to produce, read far more often than it changes, and tolerable when slightly stale.

- **Pick the layer deliberately:** HTTP caching (browser or CDN), a shared cache (for example Redis or Memcached), or in-process memoization. Each layer adds a staleness window and something to invalidate.
- **The key includes every input that changes the result:** tenant, user or role, locale, feature flags, query parameters, API version. A key that omits the viewer serves one user's data to another, which is a security incident, not a performance bug.
- **Choose one invalidation strategy** (time-based TTL, explicit invalidation on write, or versioned keys) and write down the acceptable staleness. Add random jitter to TTLs so entries do not all expire together.
- **Protect hot keys from stampedes** when they expire: let one request recompute while others wait for it or receive the stale value (request coalescing, a short lock, or `stale-while-revalidate`).
- Cache "not found" results with a shorter TTL; never cache errors as if they were answers.
- Bound memory with a size limit and an eviction policy, and measure the hit rate; a cache with a low hit rate is overhead.
- Never cache values whose staleness breaks correctness: balances, permissions, stock at checkout, security decisions.
- **HTTP headers:** content-hashed static assets `Cache-Control: public, max-age=31536000, immutable`; HTML usually `no-cache` (revalidate) with an `ETag`; per-user responses `private`; sensitive responses `no-store`; `stale-while-revalidate` (RFC 5861) where brief staleness is acceptable.

## Web performance and Core Web Vitals

Thresholds for a "good" experience, assessed at the 75th percentile of page visits, separately for mobile and desktop:

| Metric | Measures | Good | Poor |
|---|---|---|---|
| LCP (Largest Contentful Paint) | Loading of the main content | at most 2.5 s | over 4.0 s |
| INP (Interaction to Next Paint) | Responsiveness to input; replaced FID in 2024 | at most 200 ms | over 500 ms |
| CLS (Cumulative Layout Shift) | Visual stability | at most 0.1 | over 0.25 |

Field data from real users decides; lab tools explain causes and catch regressions before release.

- **LCP:** fast server response (caching, CDN, server or static rendering for content pages); find the LCP element and make it discoverable in the initial HTML; give the LCP image `fetchpriority="high"` and never lazy-load it; serve modern formats (AVIF or WebP) at the right size with `srcset` and `sizes`; remove render-blocking CSS and scripts (`defer`, critical CSS); preconnect to required third-party origins.
- **INP:** break long tasks (over 50 ms) into smaller pieces and yield to the main thread between them (`scheduler.yield()` where supported, otherwise `setTimeout`); do the visible update first and defer the rest; ship less JavaScript (code-split by route, lazy-load rarely used features); avoid reading layout right after writing styles in loops; virtualize long lists; move heavy computation to a Web Worker; give input handlers only the work they need.
- **CLS:** set `width` and `height` or `aspect-ratio` on images, video and embeds; reserve space for ads, banners and late content; do not insert content above what the user is reading unless they asked for it; animate `transform` and `opacity`; reduce font-swap shifts with `font-display` and fallback metric overrides (`size-adjust`, `ascent-override`).
- **Request chains:** independent calls awaited one after another add up their latencies, on the server and in the browser. Start independent work together (`Promise.all`, `asyncio.gather`, Go's `errgroup`), start loading data as soon as the route is known (in the router or server loader rather than after the first render), and avoid child components that each fetch only after their parent has rendered. Keep steps that truly depend on each other in order, deliberately.
- **Component re-renders** (React, Vue, Angular): measure first with the framework's devtools profiler (React DevTools Profiler with update highlighting, the Vue Devtools timeline, the Angular DevTools profiler). Usual causes: state held higher than the components that use it; a context or store value rebuilt on every render, so every consumer updates; new object, array or function props on each render that defeat memoization; list items keyed by index, which also mixes up row state when items move. Fix the cause (move state down, split the context, subscribe to narrow store slices, use stable keys), then memoize only components the profile shows are hot. If the project uses a compiler that memoizes automatically, do not add manual memoization on top.
- **General:** HTTP/2 or HTTP/3, compression, long-lived caching of hashed assets, WOFF2 fonts subset to the needed characters, audited third-party scripts loaded `async` or `defer` (or replaced with a lightweight placeholder until the user interacts), and no `unload` handlers so the back/forward cache works.
- UI-level rules for loading states and honest progress are in `../../ui-rules.md` (`FBK` category).

## Budgets and regression guards

- **Set budgets from the current baseline plus a target,** for example: initial JavaScript at most 170 KB compressed on the main route, LCP image at most 150 KB, API p95 at most 300 ms on the reference dataset. The numbers belong to the project; pick them with the user.
- **Gate deterministic metrics in CI** (bundle size with the bundler's budget setting, `size-limit` or a script comparing build output). Gate noisy ones (Lighthouse metrics, latency) with several runs and a tolerance, for example `npx @lhci/cli autorun` with assertions on medians.
- **Monitor the field metric** that motivated the work and alert on a sustained change, not on a single bad day.

## Checks (done when)

- [ ] Metric, target and method are written down; baseline and result come from the same method and both are reported with their spread.
- [ ] The change addresses the cost the profile showed, and the improvement exceeds the noise.
- [ ] Tests still pass; no correctness was traded away (skipped validation, stale data where freshness matters).
- [ ] New indexes are justified by before and after plans; new caches state their key, invalidation and staleness window.
- [ ] A budget, benchmark or monitor now protects the result.

## Anti-patterns

- Optimizing without a profile, or reporting improvement from a single run.
- Comparing a cold baseline with a warm result.
- Several optimizations landed together so none can be attributed.
- Memoizing everything, or adding caches for already fast calls.
- An index added because a column "looks filtered", never checked against a plan.
- Raising the connection pool size to cure exhaustion.
- Lazy-loading the LCP image; images without dimensions.
- Averages instead of percentiles.
