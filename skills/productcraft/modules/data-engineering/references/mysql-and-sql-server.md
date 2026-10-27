# MySQL and SQL Server operations

Read this when the database is MySQL (or MariaDB) or Microsoft SQL Server (including Azure SQL) and the question is about how that engine behaves: plans, indexes, locking, configuration, monitoring or replication. Engine-neutral query and index guidance is in `sql-query-tuning.md`; online schema changes in `../../engineering-practices/references/data-and-migrations.md`.

As with PostgreSQL, configuration changes, killing sessions, index rebuilds and failovers on shared or production servers need the user's permission.

## MySQL

### Versions

MySQL 8.0 reached end of life in April 2026; 8.4 is the long-term support line and 9.x are short-lived innovation releases. MariaDB forked long ago and differs in optimizer, JSON, replication and system tables; do not assume MySQL documentation applies to it. Check with `SELECT VERSION();`.

### InnoDB essentials

- **The primary key is the table.** Rows are stored in primary-key order and every secondary index stores the primary key. Keep it short and monotonically increasing (`BIGINT AUTO_INCREMENT` or a time-ordered UUID stored as `BINARY(16)`); random UUID primary keys scatter inserts across pages and inflate every index.
- **Buffer pool:** `innodb_buffer_pool_size` is the main memory setting, often 50-75% of RAM on a dedicated server. Check the hit rate and `Innodb_buffer_pool_reads` (reads that missed the pool) over time, not once.
- **Redo log:** size it with `innodb_redo_log_capacity` (8.0.30+) so checkpoints are not constantly forced on write-heavy systems.
- The query cache was removed in 8.0. Caching belongs in the application (`../../engineering-practices/references/performance.md`).

### Character sets, collations and SQL mode

- Use `utf8mb4` everywhere. `utf8` is an alias for the deprecated three-byte `utf8mb3`, which cannot store emoji or some CJK characters.
- The 8.0 default collation `utf8mb4_0900_ai_ci` compares case- and accent-insensitively: `'resume' = 'Résumé'` is true, and a unique index rejects both. Choose a `_as_cs` or `_bin` collation per column where that matters.
- Keep strict SQL mode (`STRICT_TRANS_TABLES`, `ONLY_FULL_GROUP_BY`, the 8.0 default). Without it MySQL truncates oversized values and coerces bad dates with only a warning.

### Reading plans

- `EXPLAIN` columns: `type` from worst to best is roughly `ALL` (full scan), `index` (full index scan), `range`, `ref`, `eq_ref`, `const`; `key` is the chosen index; `rows` times `filtered` estimates rows passed on; `Extra` flags `Using filesort`, `Using temporary` (a temporary table for grouping or sorting) and `Using index` (covering, no row lookup).
- `EXPLAIN ANALYZE` (8.0.18+) runs the query and shows actual times and rows per iterator; `EXPLAIN FORMAT=TREE` shows the iterator plan without running it.
- Optimizer statistics: `ANALYZE TABLE t;` refreshes index statistics; histograms (`ANALYZE TABLE t UPDATE HISTOGRAM ON col WITH 64 BUCKETS;`) help with skewed, unindexed filter columns.

### Finding problems

- **Slow query log:** `slow_query_log = ON`, `long_query_time = 0.5` (or lower briefly in staging); summarize with `pt-query-digest` or `mysqldumpslow`.
- **Performance Schema** (on by default): `performance_schema.events_statements_summary_by_digest` ranks normalized statements by total time; the `sys` schema wraps it in readable views such as `sys.statements_with_full_table_scans`, `sys.statement_analysis`, `sys.schema_unused_indexes` and `sys.schema_redundant_indexes`.
- **Current activity:** `SHOW FULL PROCESSLIST;` or `sys.session`; locks in `performance_schema.data_locks` and `data_lock_waits`.
- **Deadlocks:** `SHOW ENGINE INNODB STATUS\G` shows the latest one. Under the default `REPEATABLE READ`, range scans take gap and next-key locks, so two transactions inserting into the same range can deadlock. Keep transactions short, touch rows in a consistent order, index the columns in `WHERE` clauses of updates (an unindexed update locks far more rows), and retry deadlock errors (1213) in the application.
- **Testing an index drop:** `ALTER TABLE t ALTER INDEX idx INVISIBLE;` hides it from the optimizer while it is still maintained; make it `VISIBLE` again if plans regress.

### Replication

- Row-based binary logging with GTIDs is the modern default; check `SHOW REPLICA STATUS\G` (8.0.22+ naming). `Seconds_Behind_Source` only measures how far the applier is behind the relay log: it can read 0 while the replica is still fetching a backlog, and it is NULL when replication has stopped. Check that both replication threads are running and compare executed GTID sets for a real answer.
- Replicas can lag behind under long transactions and big batch updates; route read-your-writes to the source.
- Group Replication and InnoDB Cluster give automatic failover; managed services wrap their own. Never trigger a failover or reset replication without the user.

## SQL Server

### Versions and compatibility level

SQL Server 2019 and 2022 are the common on-premises versions in 2026, with SQL Server 2025 released in late 2025; Azure SQL Database is versionless. Optimizer behavior follows the database **compatibility level** (`SELECT compatibility_level FROM sys.databases`), not only the engine version, so check both (`SELECT @@VERSION;`) before applying version-specific advice.

### Plans and measurement

- Compare actual execution plans (with actual row counts), not estimated ones. `SET STATISTICS IO, TIME ON;` reports logical reads per table and CPU time: logical reads are the most stable before and after measure.
- Classic findings:
  - **Implicit conversion:** a `varchar` column compared with an `nvarchar` parameter (the default for many drivers' strings) turns a seek into a scan, flagged by a warning on the plan's root operator. Match parameter types to column types, or declare parameters explicitly.
  - **Key lookups** repeated for many rows: add `INCLUDE` columns to the nonclustered index, or accept the lookup when few rows qualify.
  - **Spills and memory grant warnings:** row estimates are wrong; refresh statistics (`UPDATE STATISTICS dbo.t WITH FULLSCAN;` after large loads) and fix non-sargable predicates.
  - **Parallelism:** `cost threshold for parallelism` defaults to 5, which is low for modern hardware; many teams raise it (for example to 30-50) after measuring. `MAXDOP` defaults are set by setup in recent versions.
- **Missing-index suggestions** in plans and `sys.dm_db_missing_index_details` are hints, not designs: they ignore existing indexes and write costs and often duplicate each other. Consolidate them by hand.

### Query Store

- Enabled by default on new databases since SQL Server 2022 (and in Azure SQL). It keeps query texts, plans and runtime statistics over time.
- Use it to find regressed queries (a new plan slower than an old one) and, as a deliberate, documented decision, force the good plan. Remove forced plans once the root cause is fixed.

### Parameter sniffing

A cached plan compiled for the first parameter values is reused for all later ones. Diagnose by comparing the plan's compiled values with the slow call's values (Query Store or the plan XML). Remedies, roughly in order: fix estimates (statistics, sargable predicates), `OPTION (RECOMPILE)` for queries that run rarely, `OPTIMIZE FOR (@p UNKNOWN)` or a specific value, splitting the procedure by parameter range, and compatibility level 160's parameter-sensitive plan optimization.

### Indexes

- One clustered index per table defines row order; a narrow, ever-increasing key avoids page splits. Nonclustered indexes carry the clustered key.
- Filtered indexes (`WHERE status = 'open'`) are small and fast, but queries must match the filter and connections need the required `SET` options (the drivers' defaults are fine).
- Columnstore indexes suit large analytic scans and aggregates; a nonclustered columnstore on an OLTP table supports real-time reporting at some write cost.
- Usage: `sys.dm_db_index_usage_stats` (seeks, scans, lookups versus updates) since the last restart; a restart resets it, so judge over a full business cycle.

### Waits, blocking and isolation

- What the server waits on: `sys.dm_os_wait_stats` (cumulative) and `sys.dm_exec_requests` with `blocking_session_id` for the current blocking chain; `sys.dm_exec_query_stats` joined to `sys.dm_exec_sql_text` ranks cached queries by total CPU or reads.
- The default `READ COMMITTED` takes shared locks, so readers and writers block each other. `READ_COMMITTED_SNAPSHOT ON` (the Azure SQL default) gives readers row versions from tempdb instead; enabling it on an existing database is a deliberate change to test, because it alters read semantics.
- `WITH (NOLOCK)` / `READ UNCOMMITTED` reads uncommitted data and can skip or double-count rows during page splits. It is not a performance fix for anything that must be correct.
- Deadlocks: the `system_health` Extended Events session captures deadlock graphs by default; fix access order and indexing, and retry error 1205.

### Practical details

- Prefer `datetime2` and `datetimeoffset` over `datetime`; use `SYSUTCDATETIME()` for UTC.
- Unicode text needs `nvarchar` and `N'...'` literals; a string literal without `N` loses characters outside the code page.
- Microsoft's ODBC Driver 18 encrypts connections by default; a connection that fails after a driver upgrade usually needs the server's certificate trusted properly, not `TrustServerCertificate=yes` in production.
- tempdb is shared by every database on the instance; heavy temp tables, sorts that spill and row versioning all compete there.

## Checks (done when)

- [ ] Engine, version (and for SQL Server, compatibility level) read from the server.
- [ ] Each diagnosis names the evidence: plan operator, digest or Query Store entry, wait type or lock view, with numbers.
- [ ] Changes measured before and after with the same parameters (logical reads or rows examined, not only elapsed time).
- [ ] No session killed, plan forced, setting changed or failover triggered on shared systems without permission; forced plans and setting changes are documented with how to undo them.
