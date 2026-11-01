# Kotlin on the server: Ktor, Exposed and coroutines

Read this before building or changing a Kotlin back end without Spring: Ktor servers and clients, the Exposed SQL library, coroutine structure on the server, and Kotlin test tooling. Language idioms, coroutine and Flow basics, Kotlin with Spring and Java interop are in `kotlin.md`; JPA and connection-pool behavior in `jvm-persistence.md`; Android and multiplatform apps in `android.md`.

## Versions that change the advice

| Version | What matters |
|---|---|
| Ktor 3.0 (October 2024) | I/O rebuilt on kotlinx-io; engine and `testApplication` configuration changed; examples written for 2.x often no longer compile |
| Ktor 3.2 (2025) | An optional built-in dependency-injection plugin; Koin and manual wiring remain common |
| Exposed 0.46 (January 2024) | `select { }` deprecated in favor of `selectAll().where { }` |
| Exposed 1.0 (betas from mid-2025) | Packages moved to `org.jetbrains.exposed.v1.*`; R2DBC support added; read the migration guide before upgrading |
| kotlinx.coroutines 1.7+ | `Dispatchers.IO` also on Kotlin/Native; `limitedParallelism` stable |

Read the versions from `gradle/libs.versions.toml` and write for them.

## Ktor server

- **Structure:** an `Application.module()` that installs plugins and calls `configureRouting()`, `configureSecurity()` and similar extension functions; routes grouped per area in `fun Route.orderRoutes(service: OrderService)`. Pass dependencies in as parameters or through the chosen DI container; do not create services inside route lambdas.
- **Thin handlers:** parse and validate, call a service, map the result to a response. Business rules live in services that tests call without HTTP.
- **Serialization:** `ContentNegotiation` with kotlinx.serialization. Configure `Json { ignoreUnknownKeys = true }` deliberately (tolerant readers for external APIs) and keep `explicitNulls` and `encodeDefaults` consistent with the API contract. Request and response types are `@Serializable` data classes separate from database rows.
- **Validation:** `RequestValidation` plugin or explicit checks in the handler, turned into 400 responses with field errors. `call.receive<T>()` fails on malformed JSON; map that to 400, not 500.
- **Errors:** `StatusPages` maps domain exceptions to the API's error shape. For unexpected exceptions, log with the call ID and return a generic body; never echo `cause.message` from an arbitrary exception, which can contain SQL, paths or secrets.
- **Request IDs and logs:** `CallId` (generate or accept an `X-Request-Id`) plus `CallLogging` with `callIdMdc("requestId")` so every log line carries it.
- **Limits:** `RateLimit` plugin per route group for expensive or authentication endpoints; cap request body sizes at the reverse proxy and check `Content-Length` for uploads; set the engine's timeouts.
- **CORS:** `install(CORS)` with explicit `allowHost(...)` entries and methods; `anyHost()` is for local development only and never combined with `allowCredentials = true`.
- **Shutdown:** configure the engine's grace period and timeout so in-flight calls finish on `SIGTERM`; do not install the shutdown-URL plugin in production.

## Authentication in Ktor

- `install(Authentication) { jwt("api") { ... } }`, then wrap protected routes in `authenticate("api") { }`. Routes outside every `authenticate` block are public; review new routes for that.
- Verify signature, issuer, audience and expiry. With an identity provider, verify RS256 or ES256 tokens against its JWKS endpoint (cached) rather than sharing an HMAC secret across services. In `validate { }`, return a principal only when required claims are present.
- Read the principal with `call.principal<JWTPrincipal>()` inside the authenticated block; turn a missing claim into 401, not a 500.
- Object-level authorization ("may this user read order 42") happens in the service, with a test for the denial.
- Session cookies (`Sessions` plugin) need signing or encryption keys from the environment, `httpOnly`, `secure` and a `SameSite` policy, plus CSRF protection for state-changing form posts.

## Ktor client

- One `HttpClient` per remote service, created once and closed at shutdown; a client per request leaks connections and threads.
- Install `HttpTimeout` (request, connect and socket timeouts); the defaults can wait far too long. Add `HttpRequestRetry` only for idempotent requests, with exponential backoff and jitter.
- `expectSuccess = true` turns non-2xx responses into exceptions; otherwise check `response.status` before reading the body.
- Test with `MockEngine`, which returns canned responses per request without a network.

## Coroutines on the server

- Each call runs in a coroutine scoped to the request; cancelled when the client disconnects or the server stops. Child work started with `coroutineScope { async { } }` is cancelled with it. Background jobs that must outlive a request run in an application-owned scope (`CoroutineScope(SupervisorJob() + Dispatchers.Default)`) that is cancelled on `ApplicationStopping`.
- **Fan-out with a bound:** `async` per item over thousands of items floods downstream services. Bound it with a `Semaphore`, `Dispatchers.IO.limitedParallelism(n)`, or chunking:

```kotlin
suspend fun refreshAll(ids: List<OrderId>) = coroutineScope {
    val permits = Semaphore(8)
    ids.map { id -> async { permits.withPermit { refresh(id) } } }.awaitAll()
}
```

- **Blocking libraries** (JDBC, blocking SDKs, file I/O) run under `withContext(Dispatchers.IO)`; size any custom dispatcher for the downstream pool, not for the request rate.
- **Mutual exclusion:** `kotlinx.coroutines.sync.Mutex` around state shared between coroutines. It is not reentrant; locking it again from inside the locked block deadlocks.
- **Timeouts:** `withTimeout` cancels the block at the next suspension point; blocking calls inside it do not stop, so they also need their own driver or client timeouts.
- **Errors:** `runCatching` and `catch (e: Exception)` around suspending calls also catch `CancellationException`; rethrow it, or catch specific types.

## Exposed

Exposed offers a typed SQL DSL and a lighter DAO layer over JDBC (and R2DBC from 1.0).

- **Tables** are `object`s (`object Orders : UUIDTable("orders")`) that mirror migrations; they do not own the schema. Flyway or Liquibase create and change tables; `SchemaUtils.create` is for tests and prototypes.
- **Transactions are thread-bound.** The blocking `transaction { }` stores its connection in a thread-local; calling suspending code that switches threads inside it breaks. In coroutines, use the suspended-transaction helper with `Dispatchers.IO` (named `newSuspendedTransaction` before 1.0; check the installed version's API), and keep the whole database unit of work inside that one block.
- **Every database call happens inside a transaction**, including reads. Accessing a DAO entity's lazy reference after the block ends throws; load what you need inside it.
- **N+1 with the DAO:** iterating entities and touching `order.customer` loads one customer per order. Eager-load with `.with(Order::customer)` or `load()`, or query with a DSL join and map rows to DTOs.
- **Conditions are parameterized** when written with the DSL (`Orders.status eq status`). Raw SQL through `exec()` must bind arguments, never interpolate them. Escape `%` and `_` in user input before building `like` patterns.
- **Batch inserts:** `batchInsert(items, shouldReturnGeneratedValues = false)` with the driver's batch rewrite option enabled; chunk very large lists.
- **Isolation and retries:** pass the isolation level when a use case needs it. Exposed can repeat a transaction block when certain SQL exceptions occur (configured through the transaction's attempts setting); make blocks safe to repeat, with no side effects such as sending email inside them.
- **Mapping:** convert `ResultRow`s to domain or DTO data classes at the repository boundary; do not let `ResultRow` or DAO entities escape into routes.
- **Pool:** HikariCP with sizes from the database's limits and `maxLifetime` below network idle timeouts, as in `jvm-persistence.md`.

## Testing

- **Routes:** `testApplication { application { module(testDependencies) }; client.get("/orders/1") }` runs the real pipeline without a port. Configure the client with `ContentNegotiation` to send and read JSON, and test 400, 401, 403 and 404 paths, not only the happy one.
- **Repositories:** run against the production database engine in a container (Testcontainers); H2 in compatibility mode differs in types, locking and SQL. Apply the real migrations before the tests.
- **Coroutines:** `runTest` with virtual time; inject dispatchers so tests can substitute a `StandardTestDispatcher`.
- **Kotest** (if the project uses it): pick one spec style per project; property tests with `checkAll(Arb...)` for parsers, mappers and money arithmetic; `withData` for tables of cases.
- **MockK:** `coEvery` and `coVerify` for suspend functions. Avoid `relaxed = true` on collaborators whose return values matter (it hides missing stubs); `mockkObject` and `mockkStatic` change global state, so pair them with `unmockkAll()` in teardown, and prefer injecting a dependency over mocking a static.
- **Coverage:** Kover (`./gradlew koverHtmlReport`, `koverVerify`) if the project has it; treat coverage as a map of untested branches, not a target.

## Review checklist

- [ ] Every new route sits inside the intended `authenticate` block, and object-level checks are tested.
- [ ] `StatusPages` never returns raw exception messages for unexpected errors.
- [ ] Clients are shared, have timeouts, and retry only idempotent calls.
- [ ] No `GlobalScope`; background work has an owning scope cancelled at shutdown; fan-out is bounded.
- [ ] Exposed work runs inside one suspended transaction per unit of work; no DAO entity or `ResultRow` leaves the repository.
- [ ] Schema changes are migrations, not `SchemaUtils` calls in production code.

## Done when

- [ ] `./gradlew build` (tests plus ktlint and detekt where configured) passed.
- [ ] Route changes have `testApplication` tests covering validation, authentication and authorization failures.
- [ ] Repository changes ran against the real database engine with the real migrations.
- [ ] The Ktor and Exposed APIs used exist in the versions pinned in the catalog.
