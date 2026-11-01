# JVM persistence: JPA, Hibernate and MyBatis

Read this when JVM data access misbehaves or is about to change: entity mappings, lazy loading errors, N+1 queries, surprising updates, ID generation, locking, pagination over large tables, connection-pool trouble, or MyBatis mappers. The baseline rules (open-session-in-view off, `LAZY` to-one associations, `JOIN FETCH` and entity graphs, DTO projections, `@Version`, no entities across the web boundary, Flyway or Liquibase owning the schema) are in `java-spring.md`; Quarkus specifics in `quarkus.md`; Kotlin's Exposed in `kotlin-server.md`. Schema-change safety is `../../engineering-practices/references/data-and-migrations.md`; query plans and indexes are `../../data-engineering/references/sql-query-tuning.md`.

## Versions that change the advice

| Version | What matters |
|---|---|
| Hibernate 6 (Spring Boot 3, Quarkus 3) | New query engine, stricter JPQL; bind-parameter logging moved to `org.hibernate.orm.jdbc.bind`; pagination combined with collection fetches warns (HHH90003004) |
| Hibernate 7 with Jakarta Persistence 3.2 (arrives with Spring Boot 4) | Removed long-deprecated APIs and settings; read the migration guide before upgrading, as its own change |
| Spring Data 3.1+ | Keyset scrolling with `Window<T>` and `ScrollPosition` |
| MyBatis 3.5 and MyBatis-Spring 3 (Spring 6, Jakarta) | `@Mapper` or `@MapperScan` registration; Spring-managed `SqlSession` |

## How the persistence context bites

The `EntityManager` (Hibernate `Session`) keeps every loaded entity managed until the transaction or session ends, and compares it to a snapshot at flush time.

- **Unintended updates.** Changing a managed entity's field, even in code meant only to format a response, writes an `UPDATE` at commit. Map to DTOs before transforming, and load read-only data with `@Transactional(readOnly = true)` or DTO queries.
- **Memory growth in batch jobs.** A loop that loads 100,000 entities in one transaction keeps all of them. Process in chunks and call `flush()` and `clear()` every chunk, or use Hibernate's `StatelessSession` for bulk work (no dirty checking, no cascades).
- **Detached entities.** An entity loaded in one transaction and changed in another needs `merge()`, which copies its state onto a managed copy and returns that copy; keep using the returned object.
- **Spring Data `save()` on new entities with assigned IDs** (UUIDs set in the constructor, natural keys) cannot tell new from existing, so it calls `merge()`, which issues a `SELECT` before every `INSERT`. Implement `Persistable<ID>` with an `isNew()` flag, or add a `@Version` field that is null until the first persist.
- **Bulk JPQL or native updates** skip the persistence context and optimistic locking. Use `@Modifying(clearAutomatically = true, flushAutomatically = true)` so stale managed copies do not overwrite the bulk change.

## Lazy loading without surprises

`LazyInitializationException` ("could not initialize proxy - no Session") means something touched an unloaded association after the session closed. Fix the query, not the session:

- Fetch what the use case needs inside the transaction: `JOIN FETCH`, `@EntityGraph(attributePaths = ...)`, or a DTO projection.
- Do not turn on `hibernate.enable_lazy_load_no_trans` or re-enable open-session-in-view to make the error go away; both hide N+1 queries and open extra connections.
- `Hibernate.isInitialized(order.getLines())` tells a serializer or mapper whether data is present.
- `toString`, `equals`, `hashCode` and logging statements that touch associations trigger loads (or the exception). Keep them to identifier fields.

## Collections and associations

- **Two `List` collections fetched in one query** fail with `MultipleBagFetchException`. Use `Set` for collections that are fetch-joined together, or fetch the second collection in a separate query over the same parents (the persistence context stitches them together).
- **`@ManyToMany` mapped as a `List`** deletes every join row and reinserts the rest when one element is removed. Map it as a `Set`, or model the join table as an entity when it carries data such as a role or a timestamp.
- **Bidirectional associations** need both sides kept in sync. Give the parent `addLine(line)` and `removeLine(line)` methods that set both ends; the side with `mappedBy` is ignored when Hibernate writes.
- **Unidirectional `@OneToMany` without `@JoinColumn`** creates a join table and extra statements. Prefer the bidirectional mapping with the foreign key on the child, or `@JoinColumn` on the parent.
- `orphanRemoval = true` deletes children removed from the collection; replacing the collection object (`setLines(newList)`) instead of mutating it fails or deletes everything. Mutate the managed collection.

## Identifiers and batching

- `GenerationType.IDENTITY` makes Hibernate insert each row at once to learn its ID, which disables JDBC insert batching. Prefer a database sequence with a pooled optimizer.
- A sequence's `allocationSize` (default 50) must equal the sequence's `INCREMENT BY`, or IDs collide or jump; set both explicitly in the mapping and the migration.
- Random UUIDs (version 4) as primary keys scatter inserts across a B-tree index; time-ordered UUIDs (version 7) keep inserts local. Check what the database and the generator in use produce.
- Batch writes need `hibernate.jdbc.batch_size` (for example 50), `hibernate.order_inserts` and `hibernate.order_updates`. Turn on the driver's rewrite option where it exists (`reWriteBatchedInserts=true` for PostgreSQL, `rewriteBatchedStatements=true` for MySQL) and measure.

## Locking and concurrency

- **Optimistic (`@Version`):** the losing transaction gets `OptimisticLockException` (Spring wraps it as `ObjectOptimisticLockingFailureException`). Decide per use case whether to retry the whole unit of work (a fresh transaction re-reading the data), or return 409 Conflict to the client. Never retry inside the failed transaction.
- **Pessimistic:** `@Lock(LockModeType.PESSIMISTIC_WRITE)` issues `SELECT ... FOR UPDATE`. Set a lock timeout (`jakarta.persistence.lock.timeout`), lock rows in a consistent order to avoid deadlocks, and keep the transaction short.
- **Work queues in a table:** `FOR UPDATE SKIP LOCKED` (PostgreSQL, MySQL 8, Oracle) lets several workers claim different rows. Hibernate exposes it through the `-2` lock timeout hint (`LockOptions.SKIP_LOCKED`) or a native query.
- **`REQUIRES_NEW` holds a second connection** while the outer transaction keeps its own. Under load, with a pool of N connections and N requests each waiting for a second one, the pool deadlocks until timeouts fire. Use it sparingly, and never in a loop.

## Pagination and large reads

- Offset pagination gets slower with depth because the database still reads the skipped rows. For deep or infinite scrolling use keyset pagination: `WHERE (created_at, id) < (:lastCreatedAt, :lastId) ORDER BY created_at DESC, id DESC`, with an index on the same columns. Spring Data's `Window` and `KeysetScrollPosition` implement it for derived queries.
- Every page has a stable total order; add the primary key as the tie-breaker.
- `Page<T>` runs a `COUNT` query on every call. Use `Slice<T>` or a window when the UI needs only "is there more", and write a cheaper count query when the default one repeats expensive joins.
- Exports: a repository method returning `Stream<T>` must run inside a transaction and be closed (try-with-resources); set a fetch size (`@QueryHints(@QueryHint(name = "org.hibernate.fetchSize", value = "500"))`). The PostgreSQL driver streams only with auto-commit off and a fetch size set; otherwise it loads the whole result.

## Connection pool (HikariCP)

- Pool size comes from the database's connection limit divided by the number of application instances, not from thread counts. Small pools with short transactions outperform large ones.
- `maxLifetime` must be shorter (by at least several seconds) than any timeout that closes idle connections in the database, a proxy or a firewall; otherwise the pool hands out dead connections.
- `connectionTimeout` is how long a request waits for a connection; when it expires, find what holds connections (long transactions, remote calls inside transactions, `REQUIRES_NEW`, unclosed streams) before raising the pool size. `leakDetectionThreshold` logs where a connection was borrowed and not returned.

## Second-level and query caches

Enable them only for read-mostly reference data, with a cache provider whose eviction and cluster behavior you understand. Every node needs invalidation, bulk updates bypass the cache, and stale permission or price data is a correctness bug. Measure the hit rate before keeping it.

## Seeing and asserting SQL

- Log statements with `org.hibernate.SQL` at debug and bind values with `org.hibernate.orm.jdbc.bind` at trace, only locally and never with production data (bind values contain personal data and secrets).
- In tests, assert query counts for list endpoints: Hibernate `Statistics` (`hibernate.generate_statistics=true`, then `getPrepareStatementCount()`), or a datasource proxy that counts statements. A regression test for each fixed N+1 keeps it fixed.

## MyBatis

MyBatis maps hand-written SQL to objects. It fits teams that want full control of SQL, legacy schemas and reporting queries; it does no dirty checking, lazy loading by default, or cascading.

- **Registration:** `@MapperScan("com.example.persistence")` once, or `@Mapper` on each interface, not both. The XML `namespace` equals the mapper interface's fully qualified name, and statement IDs match method names.
- **`#{}` binds a parameter; `${}` pastes text into the SQL.** `${}` is acceptable only for identifiers chosen from a closed map in Java code (a sort column, a direction), never for request values:

```java
private static final Map<String, String> SORTS = Map.of("name", "display_name", "created", "created_at");
String column = SORTS.getOrDefault(request.sort(), "created_at");   // only this reaches ${sortColumn}
String direction = request.descending() ? "DESC" : "ASC";
```

- **Dynamic SQL:** use `<where>`, `<set>`, `<trim>`, `<choose>` and `<foreach>` instead of string building. An empty collection in `<foreach>` either produces invalid `IN ()` or, when wrapped in an `<if>` that skips it, silently removes the filter and widens the query. Decide empty-list behavior in the service (return no rows without calling the mapper) before the mapper runs.
- **`LIKE` searches:** build the pattern in Java, escape `%`, `_` and the escape character in user input, and bind it with `#{}`.
- **Result mapping:** `resultType` with column aliases for flat rows; `resultMap` with an `<id>` element for joins and nested objects (the `<id>` lets MyBatis group joined rows correctly). A nested `select` inside a `resultMap` runs one query per parent row, which is N+1; use a join or a second batched query over the parent IDs.
- **Paging:** `RowBounds` skips rows in the result set after the database has produced them; it is not SQL `LIMIT`. Write `LIMIT`/`OFFSET` or keyset predicates in the statement.
- **Transactions:** put `@Transactional` on the service method that calls several mappers. MyBatis-Spring's `SqlSessionTemplate` is thread-safe and joins Spring transactions; never call `commit()`, `rollback()` or `close()` on it, and never inject a raw `DefaultSqlSession` (not thread-safe).
- **Writes:** `useGeneratedKeys="true" keyProperty="id"` returns generated keys. For bulk inserts, use `ExecutorType.BATCH` with chunked `flushStatements()`, or a multi-row insert sized below the driver's parameter limit. Check affected-row counts for updates that must hit exactly one row (stale or missing data otherwise passes silently).
- **Nulls:** some drivers need `jdbcType` on nullable parameters (`#{middleName,jdbcType=VARCHAR}`).
- **Second-level cache** is per namespace; a statement in another namespace that changes the same table leaves it stale. Keep it off unless the data is truly read-only.
- **Tests:** `@MybatisTest` (from the MyBatis Spring Boot test starter) loads only mappers; run it against the real database engine in a container, covering each dynamic branch, empty collections, null parameters and result-map joins.

## Review checklist

- [ ] No entity is modified outside the use case that owns it; read paths use DTOs or read-only transactions.
- [ ] No `LazyInitializationException` workaround (`enable_lazy_load_no_trans`, open-session-in-view, `EAGER` everywhere).
- [ ] Collections fetched together are `Set`s or fetched separately; `@ManyToMany` is not a `List`.
- [ ] ID strategy allows batching where bulk inserts matter; sequence increments match.
- [ ] Optimistic-lock failures have a decided behavior (retry the unit of work, or 409).
- [ ] Deep pagination uses keyset; exports stream with a fetch size inside a transaction.
- [ ] MyBatis: every `${}` is backed by an allowlist; empty-list behavior is decided in the service.

## Done when

- [ ] Repository and mapper tests ran against the real database engine (Testcontainers or the framework's equivalent).
- [ ] List and detail endpoints have query-count assertions or inspected SQL showing no N+1.
- [ ] Locking and retry behavior has a test with two concurrent transactions where it matters.
- [ ] Pool settings were checked against the database's connection limit and network idle timeouts.
