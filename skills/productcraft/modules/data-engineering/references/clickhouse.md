# ClickHouse for analytics

Read this when you design ClickHouse tables, choose a MergeTree engine or sort key, build materialized views, load data into ClickHouse, or a ClickHouse query is slow, wrong or uses too much memory. Engine-neutral SQL correctness is in `sql-query-tuning.md`; safe access to a live server in `live-database-access.md`.

## Versions and when to use it

- ClickHouse is Apache-2.0 licensed. It ships monthly releases and two long-term support releases a year (the `.3` and `.8` versions). Read `SELECT version();` before relying on a feature: lightweight updates, the newer `JSON` type, refreshable materialized views and automatic join reordering arrived in 2024-2025 releases and changed status quickly. ClickHouse Cloud uses its own replicated engine variant and enables some settings by default; check its documentation as well.
- **Good fit:** append-mostly event, log, metric and clickstream data; aggregations over hundreds of millions of rows; dashboards that scan few columns of many rows.
- **Poor fit:** the system of record for transactional data, frequent single-row updates or deletes, multi-statement transactions, high-concurrency key lookups that must see their own writes. Keep PostgreSQL or MySQL as the source of truth and copy into ClickHouse for analysis.

## Table design

The `ORDER BY` clause is the most important decision. It sets the on-disk sort order and the sparse primary index: one index mark per granule (8,192 rows by default), not one entry per row. It does not enforce uniqueness.

```sql
CREATE TABLE events
(
    event_date   Date,
    event_time   DateTime64(3, 'UTC'),
    tenant_id    UInt32,
    event_type   LowCardinality(String),
    user_id      UInt64,
    country      LowCardinality(String),
    amount_cents Int64,
    payload      String CODEC(ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (tenant_id, event_type, event_date, user_id)
TTL event_date + INTERVAL 400 DAY DELETE;
```

- **Sort key:** lead with the columns most queries filter on with equality, roughly from lower to higher cardinality, then the time column (often truncated to a date), then a high-cardinality column if queries look it up. Low-cardinality columns first keep long runs of equal values, which compress well and let the index skip whole granules. Put a unique identifier first only if most queries filter by it.
- **Primary key prefix:** `PRIMARY KEY` may be a prefix of `ORDER BY` to keep the index small while sorting further for compression.
- **Partitioning is for data lifecycle,** not speed: dropping, moving or expiring whole months or days. Keep the number of partitions modest (monthly is the usual choice; daily only with large daily volumes). Never partition by a high-cardinality column such as a user id; it creates huge numbers of small parts.
- **Types:** the smallest integer that fits; `LowCardinality(String)` for repeated strings (the documentation suggests it for up to roughly ten thousand distinct values); `DateTime64` with an explicit time zone; `Decimal` or integer minor units for money. Avoid `Nullable` unless "unknown" differs from a default value; it adds a hidden column and slows queries. `Enum` types break when a new value appears; prefer `LowCardinality(String)` for evolving categories.
- **Codecs:** `Delta` or `DoubleDelta` for monotonic timestamps and counters, `Gorilla` for slowly changing floats, `ZSTD` for text. Measure with `system.columns` (`data_compressed_bytes`, `data_uncompressed_bytes`) before and after.

## Choosing the engine

| Engine | Use for | Remember |
|---|---|---|
| `MergeTree` | Immutable facts | The default |
| `ReplacingMergeTree(ver[, is_deleted])` | Latest version of a row, deduplicated by the sort key | Deduplication happens at merge time, eventually; queries must use `FINAL` or `argMax`-style grouping to be correct |
| `AggregatingMergeTree` | Pre-aggregated rollups fed by materialized views | Store `-State` values, read with `-Merge` and `GROUP BY` |
| `SummingMergeTree` | Simple sums per key | Same "merge eventually" rule; still `GROUP BY` when reading |
| `CollapsingMergeTree`, `VersionedCollapsingMergeTree` | Cancel and replace rows with sign columns | The writer must emit exact cancel rows |
| `Replicated*` variants | Self-managed clusters with ClickHouse Keeper | Plan shards and replicas before data volume forces it |

A query on `ReplacingMergeTree` without `FINAL` or explicit deduplication returns duplicates whenever parts have not merged yet. That is a correctness bug, not a performance detail.

```sql
SELECT order_id, argMax(status, ver) AS status
FROM orders_latest
WHERE tenant_id = 42
GROUP BY order_id;
```

## Ingestion

- **Insert in batches.** Each insert creates a part on disk that background merges must combine. The documentation recommends at least 1,000 rows per insert and ideally 10,000 to 100,000. Many tiny inserts end in "too many parts" errors and rejected writes.
- **Many small producers:** use asynchronous inserts (`async_insert = 1`) and keep `wait_for_async_insert = 1` so errors reach the client; with waiting off, failures are silent.
- **Retries:** resend exactly the same batch. Replicated tables (and Cloud) deduplicate identical inserted blocks; plain `MergeTree` needs `non_replicated_deduplication_window` or an explicit `insert_deduplication_token`. A retry with re-batched rows is not deduplicated.
- **Streams:** a `Kafka` (or similar) engine table read by a materialized view into a MergeTree table, or a connector that batches. Files: `INSERT INTO t SELECT * FROM s3(...)` for Parquet or CSV in object storage, checked with a row count afterwards.
- **Change data capture from an OLTP database:** log-based replication tools, written into `ReplacingMergeTree` with a version column. Triggers, polling or notification channels that insert one row at a time do not scale and miss events.

## Materialized views

A ClickHouse materialized view is an insert trigger: it runs its `SELECT` over each block inserted into the source table and writes the result into a target table.

```sql
CREATE TABLE revenue_hourly
(
    hour DateTime, tenant_id UInt32,
    revenue AggregateFunction(sum, Int64),
    buyers  AggregateFunction(uniq, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (tenant_id, hour);

CREATE MATERIALIZED VIEW revenue_hourly_mv TO revenue_hourly AS
SELECT toStartOfHour(event_time) AS hour, tenant_id,
       sumState(amount_cents) AS revenue, uniqState(user_id) AS buyers
FROM events
WHERE event_type = 'purchase'
GROUP BY hour, tenant_id;

SELECT hour, sumMerge(revenue) AS revenue_cents, uniqMerge(buyers) AS buyers
FROM revenue_hourly
WHERE tenant_id = 42 AND hour >= now() - INTERVAL 1 DAY
GROUP BY hour ORDER BY hour;
```

- It sees only new inserts: existing rows need a one-off backfill (`INSERT INTO target SELECT ...` in time-bounded chunks), and it never sees mutations or deletes on the source.
- A join inside the view fires only on inserts into the left-hand table; changes to the joined table do not update past results.
- Always write `TO target` and create the target yourself. Avoid `POPULATE`: rows inserted while it runs are lost.
- Partial aggregates stay partial until merged; always aggregate again when reading.
- For results that must be recomputed from scratch on a schedule, use a refreshable materialized view (`REFRESH EVERY ...`) where the version supports it.

## Queries

- Filter on a prefix of the sort key and check the effect: `EXPLAIN indexes = 1 SELECT ...` shows how many parts and granules were selected.
- Select only needed columns; in a column store `SELECT *` reads every column.
- **Approximate by default:** `uniq` and `quantile` are approximate (`quantile` samples); `uniqExact`, `quantileExact` and `quantileTDigest` trade speed for accuracy. `count(DISTINCT x)` maps to `uniqExact` unless the setting changed. State which you used when numbers go into a report.
- **Joins:** older planners build an in-memory hash table from the right-hand table, so put the smaller table on the right unless your version reorders joins. Prefer dictionaries (`dictGet`) for dimension lookups and denormalize at ingest for hot paths.
- `LIMIT n BY col` returns the top n rows per group cheaply.
- Guard ad hoc queries with `max_execution_time`, `max_memory_usage` and `max_result_rows` in a settings profile.

## Updates, deletes and retention

- `ALTER TABLE ... UPDATE` and `ALTER TABLE ... DELETE` are mutations: asynchronous rewrites of every affected part. Watch `system.mutations`, and never run them in a loop.
- `DELETE FROM t WHERE ...` (lightweight delete) marks rows and hides them at once; disk space returns after merges. Newer releases add a lightweight `UPDATE`; check its status in your version.
- Prefer designs that avoid mutations: `ReplacingMergeTree` for changing rows, `TTL` for retention, `ALTER TABLE ... DROP PARTITION` for bulk removal.
- Plan erasure requests for personal data before launch: deletes keyed by user are far cheaper when the user id is near the front of the sort key or in a separate table.

## Operations

```sql
-- Slow or heavy queries in the last hour
SELECT query_duration_ms, read_rows, formatReadableSize(read_bytes) AS read, formatReadableSize(memory_usage) AS mem, left(query, 120)
FROM system.query_log
WHERE type = 'QueryFinish' AND event_time > now() - INTERVAL 1 HOUR
ORDER BY query_duration_ms DESC LIMIT 20;

-- Active parts per partition: thousands of small parts means inserts are too small
SELECT table, partition, count() AS parts, sum(rows) AS rows
FROM system.parts WHERE active GROUP BY table, partition ORDER BY parts DESC LIMIT 20;
```

Also watch `system.merges`, `system.mutations`, `system.replication_queue` and free disk space: merges need room to write new parts before deleting old ones.

## Security

- Separate users for ingestion, dashboards and administration; dashboards get a profile with `readonly = 1`, quotas and row policies for tenant isolation.
- On self-managed servers, make sure the `default` user has a password or is disabled, require TLS, and never expose the HTTP (8123) or native (9000) ports to the internet.
- Agents query real servers under `live-database-access.md`: read-only, bounded, no personal data in outputs.

## Checks (done when)

- [ ] Server version read; engine and sort key chosen from the real query patterns, with `EXPLAIN indexes = 1` showing granule skipping.
- [ ] Inserts are batched or asynchronous with waiting on; retries resend identical batches.
- [ ] Every query on a replacing or aggregating engine deduplicates or merges at read time.
- [ ] Materialized views write `TO` an explicit table, and backfills are counted against the source.
- [ ] Approximate functions are labeled as approximate wherever their results are reported.
- [ ] No mutation, `OPTIMIZE ... FINAL`, partition drop or setting change ran on a shared server without the user's go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| "Too many parts", rejected inserts | One row or a few rows per insert | Batch, or async inserts with waiting |
| Duplicate rows in results | `ReplacingMergeTree` read without deduplication | `FINAL` or `argMax` grouping |
| Rollup totals too high or too low | Reading `-State` columns without `-Merge`, or no `GROUP BY` | Merge and group on read |
| Materialized view missing history | Created after data existed; `POPULATE` race | Explicit backfill in chunks, counted |
| Query reads the whole table | Filter not on the sort-key prefix | Redesign the sort key, a projection, or a skip index measured with `EXPLAIN` |
| Disk fills during merges | Little free space; huge mutations | Alert on free space; avoid mutations |
