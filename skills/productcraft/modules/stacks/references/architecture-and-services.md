# System design and services

Read this when you design a new system or a major component, size it, choose a datastore, decide whether and where to split a monolith, or design how services talk and stay consistent. Neighboring topics live elsewhere: interface and event contracts in `../../engineering-practices/references/api-contracts.md`; timeouts, retries, circuit breakers and the transactional outbox in `../../engineering-practices/references/resilience.md`; telemetry in `../../engineering-practices/references/observability.md`; ADRs and design docs in `../../engineering-practices/references/docs-and-decisions.md`; replacing an existing system in `legacy-modernization.md`; GraphQL servers in `graphql.md`; server push and WebSockets in `realtime-websockets.md`.

## Start from requirements with numbers

Architecture follows from a few quantified requirements. Ask for them, or state assumptions the user can correct; never invent business facts.

| Requirement | Questions that produce a number |
|---|---|
| Load | Requests or events per second on average and at peak; read-to-write ratio; growth expected in 12 months |
| Latency | p50 and p99 targets for the key operations, measured where |
| Availability | Target (99.9% allows about 43 minutes of downtime a month, 99.99% about 4 minutes); which features may degrade instead of failing |
| Data | Volume now and in a year, retention rules, recovery point (how much data may be lost) and recovery time (how long restoring may take) |
| Consistency | Which operations must never show stale or conflicting data (money, inventory, permissions), and which tolerate seconds of delay |
| Constraints | Team size and skills, budget, existing platforms, regulation (data residency, audit, HIPAA or GDPR duties), deadlines |

**Estimate before designing.** One line of arithmetic often settles a debate:

```text
200k daily active users x 30 requests/day = 6M requests/day ~ 70 req/s on average; peak at 5x ~ 350 req/s
-> one well-indexed PostgreSQL primary and a few app instances handle this; sharding is not a question yet.
10M events/day x 1 KB = 10 GB/day ~ 3.6 TB/year before replication and indexes
-> plan partitioning or tiered storage and a retention policy.
```

## Default to a modular monolith

For most products, especially with one team, a single deployable application with strong internal module boundaries is faster to build, cheaper to run and easier to change than services:

- Modules own their data (their own tables or schema), expose a small interface, and do not reach into each other's tables. Enforce boundaries with a check (`../../engineering-practices/references/large-refactors.md#module-boundaries`).
- In-process calls are fast and transactional; refactoring across modules is a single change.
- A module with clean boundaries can be extracted later, when there is a reason.

**Split a service out when at least one of these is real and measured:**

| Reason | Example |
|---|---|
| Independent scaling or resource profile | A CPU-heavy image pipeline next to a latency-sensitive API |
| Independent release cadence or ownership | A separate team that is blocked by the main release train |
| Fault or security isolation | Payment processing in a smaller, audited, separately deployed unit |
| Different technology need | A component that needs a different runtime or datastore |

Services cost network failures, partial consistency, versioned contracts, distributed tracing, more deployments and harder local development. Name the reason in an ADR; "microservices are best practice" is not a reason.

## Drawing boundaries

- **Boundaries follow business capabilities and language,** not technical layers. A "user service" plus an "order service" plus an "email service" called in sequence for every request is a distributed monolith. A boundary is good when most changes stay inside one side.
- **Use change history as evidence:** files and tables that change together in the same commits belong together (`git log` co-change analysis).
- **Single data owner:** each table or collection has exactly one owning module or service. Others read through its API, through events, or through a read model it publishes, never through shared tables.
- **Avoid entity services:** a service per noun (customers, products, orders) with only CRUD operations forces every business operation to coordinate several services. Prefer services around workflows (checkout, fulfillment, billing).
- Sketch the main flows across the proposed boundaries. Count the synchronous hops per user request; more than two or three in a chain multiplies latency and failure probability.

## Communication

| Style | Use for | Watch out for |
|---|---|---|
| Synchronous request/response (HTTP, gRPC) | Queries that need an answer now; commands where the caller must know the result | Chains of calls; every hop needs a timeout budget and a degradation plan |
| Asynchronous commands through a queue | Work that can happen later (emails, exports, provisioning) | Idempotent consumers, retries with backoff, dead-letter queues that someone watches |
| Events (publish/subscribe) | Telling others that something happened, without knowing who listens | Event schemas are contracts; ordering is per key at best; consumers must deduplicate |

- **Event notification** (an ID and a type; consumers call back for details) keeps payloads small but adds calls. **Event-carried state** (the data in the event) lets consumers keep local read models, at the cost of larger, versioned payloads. Choose per event, deliberately.
- Publishing an event and changing the database must not diverge: use the outbox described in `../../engineering-practices/references/resilience.md`, or change data capture.
- Request deadlines propagate across hops (gRPC deadlines, a deadline header), so downstream work stops when the caller has given up.

## Consistency across services

There is no shared transaction across services. Two-phase commit across independent services is fragile and rarely available; design for it not to be needed.

- **Saga:** a sequence of local transactions, each followed by an event or command that triggers the next, with a **compensating action** for each step that must be undone when a later one fails (refund the charge, release the reservation).
  - *Orchestration:* one coordinator tells each participant what to do and tracks state. Easier to follow, test and monitor; the coordinator must be durable (a workflow engine or a state table).
  - *Choreography:* each service reacts to the previous service's events. Fewer moving parts for two or three steps, hard to follow beyond that.
- Make intermediate states explicit and visible (`PENDING_PAYMENT`, `RESERVED`), with timeouts that trigger compensation, so users and support can see where a process stands.
- Compensations are business operations, not database rollbacks; some effects (a sent email) can only be followed up, not undone. Agree them with the user.
- Every consumer and step is idempotent, because messages are delivered at least once.

## CQRS and event sourcing

- **Separate read models** (CQRS in its simple form) help when reads need a very different shape or scale than writes: a search index, a reporting table, a denormalized view fed by events. It adds lag between write and read; show users their own writes immediately.
- **Event sourcing** (the event log is the source of truth, state is derived) fits domains that need a full audit trail or reconstruction of past states (ledgers, some regulated workflows). It costs schema evolution of stored events forever, snapshotting, projections to rebuild and a steep learning curve. Never adopt it by default.

## Choosing datastores

| Need | Usual choice |
|---|---|
| General application data, transactions, relations, reporting | A relational database (PostgreSQL by default unless the organization standardizes on another) |
| Flexible documents with simple access patterns | A relational database's JSON columns first; a document store when the access patterns are known and fit it |
| Cache, rate limits, ephemeral counters, simple queues | An in-memory key-value store (Redis or a compatible one), never as the only copy of important data |
| Massive key-based access with predictable patterns | A wide-column or managed key-value store, with the access patterns designed up front |
| Full-text search, relevance, facets | A search engine fed from the primary store |
| Metrics and time-stamped events at volume | A time-series database or columnar analytics store |
| Large files and blobs | Object storage, with metadata in the database |

Every additional datastore adds operations, backup, security and consistency work. Add one only with a requirement it uniquely meets, and record it in an ADR.

## Caching

- Cache-aside (read through the cache, fill on miss, set a TTL) is the default. Decide per item who invalidates and when; a TTL is the fallback, not the plan.
- Protect against stampedes on popular keys expiring together: request coalescing, early refresh with jitter, or a lock per key.
- Never cache per-user or permission-dependent data under a shared key.
- Measure the hit rate; a cache with a low hit rate adds latency and inconsistency for nothing.

## Multi-tenancy

| Model | Isolation | Cost and operations |
|---|---|---|
| Shared tables with a `tenant_id` column | Logical; one missed filter leaks data. Add database row-level security as a second layer where available | Cheapest; one schema to migrate |
| Schema per tenant | Stronger; per-tenant backups possible | Migrations run per schema; connection and catalog overhead at high tenant counts |
| Database per tenant | Strongest; per-tenant residency and restore | Highest cost; fleet management for migrations and monitoring |

Whatever the model, the tenant comes from the authenticated session, never from a request parameter, and every query path is tested for cross-tenant access.

## Deployment and operations

- Each service has its own pipeline, health and readiness checks, configuration, dashboards and owner. A service that cannot be deployed alone is not independent; consumer contract tests catch breaking changes before release.
- Start with the platform's built-in service discovery and load balancing; add a service mesh only for a concrete need (mutual TLS at scale, traffic shifting) the team can operate.
- Trace every request across services with propagated context, and correlate logs by trace ID.

## Write it down

A design is reviewable when it has: the requirements with numbers (or marked assumptions), the estimate, a context diagram and a container diagram (C4-style levels, as text such as Mermaid), the main flows across boundaries, a failure-mode table (each dependency: what happens when it is slow, down or returns garbage), the data ownership map, and ADRs for each costly-to-reverse choice. Draft; the user decides.

## Anti-patterns

- Splitting into services before the domain and the load are understood.
- A shared database written by several services.
- Synchronous call chains across many services for one user request.
- A service per entity with CRUD endpoints, forcing every workflow to coordinate several of them.
- Event sourcing, a service mesh or a new datastore adopted because they are fashionable.
- Designing for a scale that is orders of magnitude beyond the estimate, or ignoring an estimate that says the current design will not last a year.

## Done when

- [ ] Requirements are quantified or listed as assumptions for the user, with a capacity estimate.
- [ ] Each boundary has a named reason, a single data owner per data set, and its main flows sketched with the number of synchronous hops.
- [ ] Cross-boundary writes have an explicit consistency mechanism (local transaction, outbox, saga with compensations) and idempotent consumers.
- [ ] Each dependency has a failure mode and degradation plan; each costly choice has an ADR draft.
