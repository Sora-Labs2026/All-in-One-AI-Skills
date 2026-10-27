# Kotlin

Read this before writing or changing Kotlin: server code with Spring or Ktor, libraries, coroutines and Flow, Gradle builds, and the shared or Android parts of multiplatform apps. Spring itself (transactions, JPA, tests) is in `java-spring.md`, and everything there applies to Kotlin too; this file adds what is different.

## Orient first

- **Kotlin version:** the `kotlin("jvm")`, `kotlin("multiplatform")` or `kotlin("android")` plugin version in `build.gradle.kts` or the version catalog. Kotlin 2.0 (May 2024) switched to the K2 compiler; most code is unaffected, but compiler plugins and some smart-cast edge cases changed.
- **JVM target:** `kotlin { jvmToolchain(21) }` or `compilerOptions.jvmTarget`. Match the Java level of the rest of the build.
- **Coroutines version:** `org.jetbrains.kotlinx:kotlinx-coroutines-*` in the catalog. Use APIs that exist in it.
- **Style and static analysis:** ktlint (often through Spotless or the ktlint Gradle plugin) and detekt (`detekt.yml`). Run the tasks the build defines, for example `./gradlew ktlintCheck detekt`.
- Libraries may enable explicit API mode (`kotlin { explicitApi() }`), which requires visibility modifiers and return types on public declarations.

## Idioms that matter

- `val` by default; `var` only for state that really changes. Read-only collection interfaces (`List`, `Map`) in signatures, mutable ones inside implementations.
- Data classes for values and DTOs; sealed interfaces with data classes or objects for closed sets of outcomes, consumed with an exhaustive `when` (no `else` branch, so adding a case breaks compilation where it must be handled).
- Value classes (`@JvmInline value class OrderId(val value: UUID)`) for identifiers and units, at no allocation cost in most uses.
- Null safety: `?.`, `?:` and smart casts. `!!` only where a null is a broken invariant, and then prefer `requireNotNull(x) { "why" }` or `checkNotNull` for a useful message. `lateinit` only for fields injected by a framework or set in test setup.
- Preconditions: `require` (bad argument, `IllegalArgumentException`), `check` (bad state, `IllegalStateException`), `error("message")`.
- Scope functions (`let`, `apply`, `also`, `run`, `with`) are for short, obvious uses; nested chains of them are harder to read than a local variable.
- `use { }` closes `Closeable` resources, like Java's try-with-resources.
- Extension functions for small, discoverable helpers on types you do not own; not as a way to scatter a class's core behavior across files.
- `Sequence` for long transformation chains over large collections, to avoid intermediate lists; plain collection operators for small ones.

## Coroutines

- **Structured concurrency:** every coroutine starts in a scope that owns it: a framework scope (Spring's request handling, Ktor's call, Android's `viewModelScope`), or a `coroutineScope { }` / `supervisorScope { }` block. Never `GlobalScope`; a class that launches background work takes a `CoroutineScope` and cancels it on shutdown.
- `coroutineScope` fails all children when one fails; `supervisorScope` lets siblings continue. Choose deliberately.
- **Dispatchers:** `withContext(Dispatchers.IO)` around blocking calls (JDBC, file I/O, blocking SDKs); `Dispatchers.Default` for CPU work. `Dispatchers.IO.limitedParallelism(n)` caps concurrency toward one resource such as a small connection pool.
- `runBlocking` belongs in `main` functions and tests only. Inside a coroutine or a request thread it blocks a thread and can deadlock.
- **Cancellation is cooperative and travels as `CancellationException`.**
  - Never swallow it. `catch (e: Exception)` around suspending calls, and `runCatching { }`, catch it too, so rethrow it or catch narrower types.
  - Long CPU loops call `ensureActive()` or `yield()`.
  - Cleanup that must suspend runs in `withContext(NonCancellable)`.
- `withTimeout` throws `TimeoutCancellationException`; `withTimeoutOrNull` returns null. Every outbound call still needs a client-level timeout.
- Exceptions in `launch` go to the scope's `CoroutineExceptionHandler` or fail the parent; exceptions in `async` surface at `await()`. An `async` that is never awaited loses its error until the scope fails.

## Flow

- `flow { }` is cold: each collector runs it again. `StateFlow` holds a current value and conflates updates (UI state, configuration); `SharedFlow` broadcasts events. Convert with `stateIn` or `shareIn` in an owning scope, with an explicit `SharingStarted` policy.
- `flowOn(Dispatchers.IO)` changes the context upstream of it only. The `catch` operator handles upstream errors only; errors in `collect` are the collector's.
- Do not expose `MutableStateFlow` publicly; expose `StateFlow` via `asStateFlow()`.
- Back-pressure: `buffer`, `conflate` and `collectLatest` each drop or delay differently; pick the one that matches the meaning of the data.

## Interop with Java

- Java types without nullness annotations arrive as platform types (`String!`): the compiler does not check them. Treat values from Java APIs as nullable unless the API is annotated (JSpecify, JetBrains, or Jakarta annotations that Kotlin understands) or documented as non-null.
- For Java callers of Kotlin code: `@JvmStatic` on companion members, `@JvmOverloads` for default arguments, `@Throws` for checked exceptions Java code should catch, `@JvmName` to avoid clashes.
- Kotlin has no checked exceptions; document what a function throws in KDoc.

## Kotlin with Spring

- Apply `kotlin("plugin.spring")` (opens classes annotated for proxies, which `@Transactional` and `@Configuration` need) and, with JPA, `kotlin("plugin.jpa")` (adds the no-argument constructors JPA requires). Without them, proxies silently fail or entities cannot be instantiated.
- JPA entities are regular classes, not data classes: data-class `equals`, `hashCode` and `toString` touch every property, including lazy associations. Use mutable properties with a nullable or generated ID and the equality rules in `java-spring.md`.
- Add `jackson-module-kotlin` so Jackson can construct data classes and respects default values and nullability.
- `@ConfigurationProperties` works with constructor-bound data classes and validation.
- Suspend functions in controllers run on Spring's coroutine support (WebFlux, and Spring MVC with the coroutine and Reactor bridge on the classpath); do not mix them into a blocking MVC service without checking how the project wires them.

## Ktor

- Install features as plugins: `ContentNegotiation` with kotlinx.serialization, `StatusPages` mapping exceptions to the API's error shape, `Authentication`, `CallLogging` with a call ID, request size limits.
- Organize routes in extension functions per area (`fun Route.orderRoutes(service: OrderService)`), with dependencies passed in.
- Ktor 3 (October 2024) changed I/O internals to kotlinx-io; check the major version before copying examples.
- Test with `testApplication { }` and its client; no real port needed.
- Blocking database libraries (Exposed with JDBC, plain JDBC) run inside `withContext(Dispatchers.IO)` or the library's suspended transaction helper.

## Testing

- JUnit 5 or Kotest, whichever the project uses; MockK for mocks (`coEvery`/`coVerify` for suspend functions). Prefer fakes for your own interfaces.
- `kotlinx-coroutines-test`: `runTest { }` runs with virtual time, so `delay` is instant; inject dispatchers so tests can pass a `StandardTestDispatcher`, and use `advanceUntilIdle()` to drain work. Never `Thread.sleep` in coroutine tests.
- Test flows with Turbine (`flow.test { assertEquals(x, awaitItem()) }`) if available.
- Backtick test names (`` fun `rejects expired coupons`() ``) are idiomatic on the JVM.

## Multiplatform and Android pointers

- Kotlin Multiplatform: shared code in `commonMain` uses only multiplatform libraries (kotlinx.serialization, kotlinx.datetime, the Ktor client, SQLDelight); platform specifics go behind `expect`/`actual` declarations or interfaces injected from each platform. Run each target's tests (`./gradlew allTests` or the per-target tasks).
- Android with Jetpack Compose: state lives in a `ViewModel` exposed as `StateFlow`, collected with `collectAsStateWithLifecycle()`; composables receive state and callbacks (state hoisting) and stay free of side effects except through `LaunchedEffect` and friends. Run `./gradlew lint` and the unit tests; instrumented tests need an emulator or device the user provides. App-store releases are the user's step. Concerns every mobile app shares (configuration, offline sync, deep links, push, store releases) are in `mobile-cross-platform.md`.

## Done when

- [ ] The build's Kotlin and coroutine versions support every API used; ktlint and detekt tasks pass where configured.
- [ ] Every coroutine has an owning scope; no `GlobalScope`, no `runBlocking` outside `main` and tests; `CancellationException` is never swallowed.
- [ ] Blocking calls run on `Dispatchers.IO` (or a limited view of it), and outbound calls have timeouts.
- [ ] Spring and JPA projects apply the Kotlin compiler plugins, and entities are not data classes.
- [ ] Tests ran with `./gradlew test` (or the project's task), using virtual time for coroutine code.
