# Java and Spring Boot

Read this before writing or changing Java, especially Spring Boot services: configuration, web layer, transactions, JPA and Hibernate, tests, build files. Kotlin on the same stack is in `kotlin.md`; Spring Security and other Java security traps are in `../../code-security-review/references/language-pitfalls.md#java-and-spring`.

## Orient first

- **Build tool:** always the wrapper (`./mvnw`, `./gradlew`) so the version matches CI. Gradle projects may use a version catalog (`gradle/libs.versions.toml`) and convention plugins in `buildSrc/` or `build-logic/`; add dependencies there, not ad hoc.
- **Java level:** `maven.compiler.release` (or `java.version` with the Boot parent) in Maven, `java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }` in Gradle. Write for that level.
- **Spring Boot generation:**

| Boot | Baseline | What changes for code |
|---|---|---|
| 2.x | Java 8+, `javax.*` | End of open-source support; upgrading is a project of its own |
| 3.0 to 3.5 | Java 17+, Jakarta EE (`jakarta.*`) | `SecurityFilterChain` beans instead of `WebSecurityConfigurerAdapter`; `ProblemDetail`; virtual threads (3.2+); `RestClient` and `JdbcClient` (3.2+); `@ServiceConnection` for Testcontainers (3.1+); `@MockitoBean` replaces `@MockBean` (3.4+) |
| 4.0 (November 2025) | Java 17+, Spring Framework 7, Jakarta EE 11 | JSpecify null-safety annotations, Jackson 3 by default, `@MockBean` removed; read the migration guide before touching dependencies |

- Static analysis and style configured in the build (Checkstyle, PMD, SpotBugs, Error Prone with NullAway, Spotless) run in `verify` or `check`; run those, not a tool of your choice.
- Spring Boot manages versions through its BOM. Do not pin a Boot-managed dependency's version in the build unless there is a security fix to pick up, and say so in a comment.

## Modern Java by version

| Feature | Final in |
|---|---|
| `var` for locals | 10 |
| Text blocks; switch expressions | 15, 14 |
| Records | 16 |
| Sealed classes and interfaces | 17 |
| Pattern matching for `switch`; record patterns; virtual threads; `SequencedCollection` (`getFirst`, `reversed`) | 21 |
| Unnamed variables (`_`) | 22 |
| `synchronized` no longer pins virtual threads | 24 |
| Scoped values; flexible constructor bodies; module import declarations | 25 (LTS, September 2025) |

- Records for DTOs, value objects and configuration properties; sealed interfaces plus pattern-matching `switch` for closed sets of outcomes, so the compiler checks exhaustiveness.
- `Optional` as a return type for "may be absent", never as a field or parameter. Use the project's nullness annotations (JSpecify, or the older `@Nullable` the project already uses).
- `java.time` only (`Instant` for timestamps, `LocalDate` for dates without time zones); `BigDecimal` from strings for money, compared with `compareTo`, not `equals`.

## Spring essentials

- **Constructor injection** with `final` fields; one constructor needs no `@Autowired`. No field injection.
- **Configuration:** bind groups of settings to a `@ConfigurationProperties` record with `@Validated` constraints, instead of scattered `@Value` strings. Profiles for environment differences; secrets from the environment or a secret store, never committed.
- **Errors:** a `@RestControllerAdvice` that maps domain exceptions to `ProblemDetail` (RFC 9457); enable `spring.mvc.problemdetails.enabled` for framework errors. Never return stack traces.
- **Web layer:** request records with Jakarta Bean Validation (`@Valid @RequestBody CreateOrder body`), response records mapped from entities. Never bind requests to or return JPA entities.
- **HTTP clients:** `RestClient` (6.1+) for blocking code, `WebClient` in reactive code; `RestTemplate` is in maintenance. Configure connect and read timeouts explicitly; the defaults can wait indefinitely.

## Transactions

- `@Transactional` works through a proxy, so:
  - a call from one method to another in the same bean (self-invocation) skips the proxy and its transaction;
  - private methods are never transactional.
- By default only unchecked exceptions (`RuntimeException`, `Error`) roll back. A checked exception commits unless you add `rollbackFor`.
- Put transactions on the service layer, around one unit of work. `@Transactional(readOnly = true)` for reads lets Hibernate skip dirty checking.
- Do not call remote services inside a transaction: the database connection stays checked out for the whole remote call. Commit first, then call, or use an outbox (`../../engineering-practices/references/resilience.md`).
- Events that must follow a successful commit use `@TransactionalEventListener(phase = AFTER_COMMIT)`.

## JPA and Hibernate

- **Turn off open-session-in-view** (`spring.jpa.open-in-view=false`; Boot logs a warning while it is on by default). With it on, lazy loads run silently from controllers and serializers; with it off, missing fetches fail loudly in tests, where they belong.
- **Fetching:**
  - `@ManyToOne` and `@OneToOne` default to EAGER; set `fetch = FetchType.LAZY` explicitly.
  - Fix N+1 with `JOIN FETCH`, `@EntityGraph(attributePaths = ...)` or `hibernate.default_batch_fetch_size`.
  - Read-only views use DTO projections (`select new ...Summary(...)` or interface projections).
- **Pagination plus collection fetch** makes Hibernate paginate in memory (warning HHH90003004 in Hibernate 6). Page over IDs first, then fetch the collections for that page; set `hibernate.query.fail_on_pagination_over_collection_fetch=true` to catch it.
- **Entity equality:** no Lombok `@Data` or `@EqualsAndHashCode` on entities (they touch lazy collections and change hash codes after persist). Use the ID with a null check and a constant `hashCode`, or a natural business key.
- **Writes:**
  - Optimistic locking with a `@Version` column on aggregates edited concurrently.
  - Batch inserts need `hibernate.jdbc.batch_size` and an ID strategy other than `IDENTITY` (a sequence).
  - Bulk JPQL `update`/`delete` bypasses the persistence context; clear it afterwards.
- **Schema:** Flyway or Liquibase owns it; `spring.jpa.hibernate.ddl-auto` is `validate` or `none` outside throwaway local setups. Migration safety: `../../engineering-practices/references/data-and-migrations.md`.
- Cascades: `CascadeType.REMOVE` and `orphanRemoval` delete data; add them only on true parent-child aggregates.
- See the SQL: `spring.jpa.show-sql` only locally; better, a datasource proxy or Hibernate statistics in tests to assert query counts.

## Concurrency: virtual threads or reactive

- On Java 21+, `spring.threads.virtual.enabled=true` (Boot 3.2+) runs request handling on virtual threads. Blocking code (JDBC, `RestClient`) then scales to many concurrent requests without a reactive rewrite.
- The connection pool and downstream limits still cap throughput; size HikariCP (`maximumPoolSize`) from the database's limits, not the thread count.
- Before Java 24, blocking inside `synchronized` pins the carrier thread. Prefer `ReentrantLock` around blocking calls on 21 to 23.
- WebFlux pays off only when the whole path is non-blocking. A single `block()` or JDBC call inside a reactive chain stalls an event-loop thread. Do not convert an MVC service to WebFlux as part of a feature.

## Testing

| Need | Use |
|---|---|
| Controller mapping, validation, error bodies | `@WebMvcTest(OrderController.class)` with `MockMvc` (or `MockMvcTester` on 6.2+) and `@MockitoBean` services |
| Repository queries and mappings against a real database | `@DataJpaTest` plus Testcontainers and `@ServiceConnection`; turn off the embedded replacement with `@AutoConfigureTestDatabase(replace = NONE)` |
| Full wiring, security filters, serialization | `@SpringBootTest(webEnvironment = RANDOM_PORT)`, sparingly |
| Pure domain logic | Plain JUnit 5 and AssertJ, no Spring context |

- Spring caches application contexts between tests with identical configuration. Every distinct set of `@MockitoBean`s or properties creates a new context and slows the suite; share a base configuration.
- An H2 database does not behave like PostgreSQL or MySQL (locking, JSON, constraint names, SQL dialect). Use Testcontainers when queries matter.
- Architecture rules (layering, no cycles) can be tested with ArchUnit if the project uses it.
- `./mvnw -Dtest=OrderServiceTest test` or `./gradlew test --tests '*OrderServiceTest'` for the fast loop.

## Operations

- Actuator: expose `health` (with liveness and readiness groups for Kubernetes) and `info`; everything else stays internal and protected.
- Metrics through Micrometer; traces through Micrometer Tracing with an OpenTelemetry bridge, propagated over every client call (`../../engineering-practices/references/observability.md`).
- JVM in containers: the JVM reads container memory limits; set heap as a percentage (`-XX:MaxRAMPercentage=75`) rather than a fixed `-Xmx` copied from a VM.
- Profile with Java Flight Recorder (`jcmd <pid> JFR.start`) before tuning. GraalVM native images and CDS or AOT caches trade build complexity for startup time; adopt them only for a measured need.

## Done when

- [ ] The wrapper's `verify` or `check` passed, including the static analysis plugins the build configures.
- [ ] No entity crosses the web boundary; requests are validated records.
- [ ] Transactions sit on service methods reached through the proxy, roll back on the intended exceptions and contain no remote calls.
- [ ] Repository changes have tests against the real database engine; list queries have no N+1 (query count asserted or SQL inspected).
- [ ] Code compiles at the project's Java release and uses the Spring APIs of the installed Boot generation.
