# Quarkus

Read this before writing or changing a Quarkus service: CDI beans, REST endpoints, Hibernate ORM with Panache, configuration, Dev Services, tests, security and native builds. Modern Java, transactions and JPA behavior that apply to any framework are in `java-spring.md` and `jvm-persistence.md`; this file adds what Quarkus does differently. Java security traps are in `../../code-security-review/references/language-pitfalls.md#java-and-spring`.

## When Quarkus fits

| Fits | Weaker fit |
|---|---|
| Container and Kubernetes services where startup time and memory per pod matter | A team fluent in Spring with a large Spring codebase and no startup or memory problem |
| Scale-to-zero, serverless functions and CLIs built as native executables | Libraries that depend on heavy runtime reflection, bytecode generation or classpath scanning that no Quarkus extension supports |
| Event-driven services (Kafka, AMQP) with a reactive core and imperative code on top | Code that must stay framework-neutral and run in several containers |

Do not migrate a working Spring service to Quarkus as part of a feature. That is its own project, decided with the user and recorded as an ADR.

## Orient first

- **Version:** the `quarkus.platform.version` property (Maven) or the platform BOM in Gradle. Quarkus 3 is the current major (Jakarta EE namespaces, Java 17 minimum since 3.7). LTS releases arrive about every six months (3.20 and 3.27 were the LTS lines as of late 2025); check the support page before assuming a version is maintained.
- **Extensions, not plain libraries:** features come as `quarkus-*` extensions that do work at build time. Add them with `quarkus ext add <name>` or `./mvnw quarkus:add-extension -Dextensions=<name>`. A plain library that needs reflection may work in JVM mode and fail in a native build.
- **Build tool and commands:** `./mvnw quarkus:dev` (or `./gradlew quarkusDev`) for dev mode with live reload and continuous testing (press `r` in the console); `./mvnw verify` for unit and integration tests; `./mvnw package -Dnative` for a native build.
- **Configuration:** `src/main/resources/application.properties` (or YAML with the `quarkus-config-yaml` extension), profiles as prefixes: `%dev.`, `%test.`, `%prod.`.
- **Upgrades:** `quarkus update` (CLI) or `./mvnw quarkus:update` applies recipes for API and configuration renames. Run it on a branch as its own change and read the diff.

## The build-time model

Quarkus does most framework work during the build (augmentation): it indexes classes, wires CDI, generates proxies and records configuration. Consequences that surprise newcomers:

- **Build-time properties are frozen into the artifact.** Properties marked as fixed at build time (the extension guides flag them) are ignored when changed at runtime, with a startup warning. Changing the database kind, enabled extensions or packaging requires a rebuild.
- **Bean discovery uses a Jandex index.** Beans in your own modules are found; beans in a dependency jar are found only if that jar has an index (`META-INF/jandex.idx`, produced by the Jandex Maven or Gradle plugin) or is listed in `quarkus.index-dependency.<name>.group-id` and `artifact-id`.
- **Unused beans are removed.** A bean that nothing injects and that has no observer or lifecycle hook disappears. Programmatic lookup (`CDI.current().select(...)`, `Arc.container().instance(...)`) then fails; inject `Instance<T>` or mark the bean `@Unremovable`.
- **Reflection is the exception.** Field injection into `private` fields works through generated accessors but costs reflection in native builds; Quarkus recommends package-private fields or constructor injection.

## CDI with ArC

- **Scopes:** `@ApplicationScoped` (one instance, lazily created behind a client proxy) is the default choice. `@Singleton` has no client proxy: it is created when first injected and cannot be replaced with `@InjectMock`. `@RequestScoped` for per-request state. `@Dependent` instances share the lifecycle of what injects them.
- **Constructor injection** of `final` fields with a single constructor needs no `@Inject`. Lombok's `@RequiredArgsConstructor` works if the project uses Lombok.
- **Ambiguous or missing beans** fail the build, not runtime: `UnsatisfiedResolutionException` (no bean: missing bean-defining annotation, missing extension, or an unindexed dependency) and `AmbiguousResolutionException` (two candidates: add a qualifier, `@Alternative` with `@Priority`, or `@DefaultBean` on the fallback).
- **Startup work** goes in an observer of `StartupEvent` or a `@Startup` bean. Keep it short: liveness probes wait for it.
- **Interceptors** (`@Transactional`, `@CacheResult`, security annotations) are applied by generated subclasses. Unlike Spring's proxies, ArC also intercepts a call from one method to another in the same bean; `private` methods are never intercepted, so do not put interceptor annotations on them.

## REST endpoints and the threading model

- **Quarkus REST** (`quarkus-rest`, `quarkus-rest-jackson`; named RESTEasy Reactive before 3.9) is the current stack. Do not add the classic `quarkus-resteasy` extensions next to it; pick one stack per application.
- **Where a method runs is inferred from its signature:**

| Signature | Runs on | Blocking calls allowed |
|---|---|---|
| Returns a plain type or `Response` | A worker thread | Yes (JDBC, blocking clients) |
| Returns `Uni<T>` or `Multi<T>`, or is a Kotlin `suspend` function | The Vert.x event loop | No |
| Annotated `@Blocking` / `@NonBlocking` | Forced worker / forced event loop | Follows the annotation |
| Annotated `@RunOnVirtualThread` (Java 21+) | A virtual thread | Yes; the connection pool still caps concurrency |

- Blocking on the event loop raises `BlockingOperationNotAllowedException` or logs "blocked thread" warnings and stalls every request on that loop. Fix the signature or the annotation, or switch to the reactive client; never raise the blocked-thread warning interval to hide it.
- **Request and response bodies** are records with Jakarta Bean Validation (`@Valid` on the parameter). Map entities to DTOs; never return Panache entities directly, for the same reasons as in `java-spring.md`.
- **Errors:** `@ServerExceptionMapper` methods (or `ExceptionMapper` providers) map domain exceptions to one error shape. A catch-all mapper logs the exception with a request ID and returns a generic message; it never echoes exception text or stack traces.
- **Outbound HTTP:** the REST Client (`quarkus-rest-client-jackson`) with an interface per remote API, `@RegisterRestClient(configKey = "billing")`, and `quarkus.rest-client.billing.url`, `connect-timeout` and `read-timeout` set explicitly. Add SmallRye Fault Tolerance (`@Timeout`, `@Retry` for idempotent calls, `@CircuitBreaker`) as `../../engineering-practices/references/resilience.md` describes.

## Data with Hibernate ORM and Panache

- **Two styles; choose one per bounded context:** active record (`extends PanacheEntity`, static `Order.find(...)`) or repositories (`implements PanacheRepository<Order>`). Repositories are easier to fake in unit tests.
- Panache query strings are parameterized (`find("status = ?1 and customerId = :c", ...)` with `Parameters.with`). Building them by concatenation is as injectable as JPQL; the rules in `jvm-persistence.md` apply.
- **Transactions:** `@Transactional` on service methods (worker threads). `QuarkusTransaction.requiringNew().run(...)` for programmatic boundaries. Keep remote calls outside.
- **Schema:** `quarkus.hibernate-orm.database.generation` is `none` or `validate` outside dev; Flyway or Liquibase extensions own the schema. `quarkus.flyway.migrate-at-start=true` runs migrations on every instance start; with several replicas, prefer a migration job the user runs (`../../engineering-practices/references/data-and-migrations.md`).
- **Hibernate Reactive** (with `quarkus-hibernate-reactive-panache`) is a different API: sessions are bound to the Vert.x context, `@Transactional` does not apply (use `@WithTransaction` or `Panache.withTransaction`), and blocking JDBC must not be mixed in. Use it only when the whole path is reactive.
- **Mutiny:** a `Uni` does nothing until subscribed; building one and never returning or subscribing it silently skips the work. Do not call `await().indefinitely()` on the event loop.

## Configuration

- Group settings in a `@ConfigMapping(prefix = "billing")` interface with validation annotations; use `@ConfigProperty` for one-off values. Required values without defaults fail startup, which is what you want.
- Secrets come from environment variables (`BILLING_API_KEY` maps to `billing.api-key`), a `.env` file in dev only (git-ignored), or a secret-store config source. No secret in `application.properties`.
- Profiles: `%dev.` and `%test.` settings never reach production builds, but `%prod.` values must not depend on dev defaults. Custom profiles are selected with `quarkus.profile` or `QUARKUS_PROFILE` at runtime, unless the property is build-time fixed.
- **Proxies:** behind a load balancer, enable `quarkus.http.proxy.proxy-address-forwarding=true` together with `quarkus.http.proxy.trusted-proxies`; otherwise forwarded headers are either ignored or spoofable. Never read `X-Forwarded-For` by hand for rate limiting or audit.

## Dev Services and dev mode

- With a container runtime available, Dev Services start databases, Kafka, Keycloak and others automatically in dev and test when no URL is configured. Pin their images (`quarkus.datasource.devservices.image-name`) to the production major version; the default image changes between Quarkus releases.
- Dev Services never run in production builds. CI needs Docker or Podman access, or explicit test resources.
- The Dev UI (`/q/dev-ui`) exists only in dev mode. Dev mode listens on localhost by default; do not expose it.

## Testing

| Need | Use |
|---|---|
| Pure logic | Plain JUnit 5 and AssertJ, no Quarkus boot |
| Endpoint, CDI wiring, serialization, security | `@QuarkusTest` with REST Assured (`given().when().get("/orders/1").then().statusCode(200)`) |
| Replace a bean | `@InjectMock` (from `quarkus-junit5-mockito`) for normal-scoped beans; `@Singleton` beans cannot be mocked this way. A `@Mock`-annotated alternative bean in the test sources replaces it for all tests |
| Different configuration | `@TestProfile(SomeProfile.class)`; each distinct profile restarts the application, so keep their number small |
| The packaged artifact (JAR, native executable or container) | `@QuarkusIntegrationTest`; no injection, black-box over HTTP only |
| Authenticated calls | `@TestSecurity(user = "alice", roles = "admin")` from `quarkus-test-security`, plus one real token test for the authentication wiring |

- `@QuarkusTest` starts the application once and reuses it across test classes with the same profile. Tests that mutate shared state (database rows, static fields) must clean up or use unique data.
- `@TestTransaction` rolls back the test's transaction; it does not cover work done by the application in its own transactions during an HTTP call.
- Database tests run against the real engine through Dev Services or a Testcontainers-backed `QuarkusTestResourceLifecycleManager`, not H2 standing in for PostgreSQL.

## Security

- **Authentication:** `quarkus-oidc` for tokens from an identity provider (bearer tokens for services, the authorization code flow for web apps); `quarkus-smallrye-jwt` to verify JWTs signed with a known key. Configure issuer and audience checks (`mp.jwt.verify.issuer`, `mp.jwt.verify.audiences`, or the OIDC equivalents).
- **Authorization:** `@RolesAllowed`, `@Authenticated`, `@PermitAll` on resources, or path-based policies in `quarkus.http.auth.permission.<name>.paths` and `.policy`. Set `quarkus.security.jaxrs.deny-unannotated-endpoints=true` so a new endpoint without an annotation is denied, not public.
- **Object-level checks:** roles do not answer "may this user see order 42". Check ownership in the service with the `SecurityIdentity` principal, and test the denial path.
- **CORS:** enable the filter (`quarkus.http.cors.enabled=true` on current 3.x; older releases used `quarkus.http.cors=true`) and list exact origins; never a wildcard together with credentials.
- **Passwords:** `BcryptUtil` from the Elytron security extensions, or delegate to the identity provider.
- **Management endpoints:** health is at `/q/health/live`, `/q/health/ready` and `/q/health/started`; metrics at `/q/metrics`. Move them to a separate management port (`quarkus.management.enabled=true`, port 9000 by default) that is not exposed publicly.

## Native executables

- Build with GraalVM or Mandrel: `./mvnw package -Dnative`, or `-Dquarkus.native.container-build=true` to build inside a builder image without a local GraalVM. Native builds take minutes and several gigabytes of memory; run them in CI, not in the inner loop.
- **What breaks:** reflection on classes Quarkus did not see (polymorphic JSON, libraries that load classes by name), resources read from the classpath, and static initializers that capture build-time state (random seeds, time, open connections).
- **Fixes:** `@RegisterForReflection(targets = {...})` for DTOs and third-party classes; `quarkus.native.resources.includes=templates/**` for resources; `quarkus.native.additional-build-args=--initialize-at-run-time=<class>` for classes that must initialize at runtime. Prefer a Quarkus extension for the library over hand-written reflection configuration.
- Run the integration tests against the native executable (`@QuarkusIntegrationTest` with `-Dnative`); JVM-mode tests do not prove the native build works.
- Native trades peak throughput and build time for startup time and memory. Choose it for a measured need (scale to zero, CLIs, dense pods), not by default.

## Messaging and scheduling

- SmallRye Reactive Messaging connects `@Incoming` and `@Outgoing` channels to Kafka or AMQP. Decide the acknowledgment strategy and the failure strategy (`dead-letter-queue`, `ignore`, `fail`) per channel; make consumers idempotent, since redelivery happens.
- `@Scheduled(every = "1m", concurrentExecution = SKIP)` prevents overlapping runs in one instance. With several replicas every instance runs the job; use the Quartz extension with a clustered job store, or a lock, when a job must run once.

## Review checklist

- [ ] No blocking call on the event loop; reactive and imperative styles are not mixed within one call path.
- [ ] `@ApplicationScoped` unless there is a reason for `@Singleton`; no programmatic lookup of beans that may be removed.
- [ ] Only one REST stack and one Panache style per context; entities never cross the HTTP boundary.
- [ ] Unannotated endpoints are denied; object-level authorization is checked and tested.
- [ ] Build-time properties are not expected to change at deploy time; secrets come from the environment.
- [ ] Dev Services images are pinned to the production major version.

## Done when

- [ ] `./mvnw verify` (or `./gradlew build`) passed, including the static analysis the build configures.
- [ ] Endpoint changes have `@QuarkusTest` coverage, including validation errors and authorization denials.
- [ ] Data changes ran against the real database engine; migrations were reviewed as SQL.
- [ ] If the service ships natively, the native build and `@QuarkusIntegrationTest` suite passed, or the report marks them `NOT VERIFIED` with the reason.
- [ ] Health endpoints respond, on the management port where one is configured.
