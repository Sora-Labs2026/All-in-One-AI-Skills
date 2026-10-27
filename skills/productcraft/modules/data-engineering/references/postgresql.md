# PostgreSQL operations

Read this when the work depends on how a PostgreSQL server behaves: connections and pooling, configuration, vacuum and bloat, locks, `jsonb`, extensions, partitioning, replication, backups, or diagnosing a slow or stuck database. Query writing and plan reading are in `sql-query-tuning.md`; schema migrations in `../../engineering-practices/references/data-and-migrations.md`.

Everything here is for local, staging or explicitly approved systems. Configuration changes, `VACUUM FULL`, `REINDEX`, killing sessions, failovers and restores on production need the user's permission and a rollback note.

## Versions

One major release per year (autumn), each supported for five years. In 2026 the supported majors are 14 to 18; 13 reached end of life in November 2025. Run `SELECT version();` and `SHOW server_version_num;` before relying on a feature, and read the release notes when crossing a major version. Recent features worth knowing, by version: `MERGE` (15), `pg_stat_io` (16), `JSON_TABLE` and incremental `pg_basebackup` (17), asynchronous I/O, B-tree skip scan, `uuidv7()` and virtual generated columns (18). Managed services (Amazon RDS and Aurora, Cloud SQL, Azure Database for PostgreSQL) restrict superuser, extensions and some settings; check their documentation, not only PostgreSQL's.

## Connections and pooling

- Each connection is a server process with its own memory. Hundreds of mostly idle connections waste memory and slow snapshots; thousands cause outages.
- Size application pools so that `instances x pool size` stays well under `max_connections`, keeping a reserve for administration and migrations.
- Put PgBouncer (or the provider's proxy) in front when many processes, serverless functions or autoscaling clients connect. In transaction pooling mode, session state does not survive between transactions: no session-level `SET`, advisory locks held across transactions, `LISTEN`, or temporary tables. Protocol-level prepared statements work in transaction mode from PgBouncer 1.21 with `max_prepared_statements` set.
- Set `idle_in_transaction_session_timeout` (for example `'5min'`) so a forgotten open transaction cannot block vacuum and DDL indefinitely, and `statement_timeout` per role or per application.

## Configuration starting points

Tune from measurements, change one setting at a time, and record why. Common starting points for a dedicated server:

| Setting | Starting point | Notes |
|---|---|---|
| `shared_buffers` | About 25% of RAM | Higher rarely helps; the OS cache does the rest |
| `effective_cache_size` | 50-75% of RAM | Planner hint only; allocates nothing |
| `work_mem` | 4-64 MB | Per sort or hash node, per query, per parallel worker; a complex query can use many multiples. Raise per session or per role for reports rather than globally |
| `maintenance_work_mem` | 256 MB to 1-2 GB | Speeds index builds and vacuum |
| `random_page_cost` | 1.1-1.5 on SSD or NVMe | The default 4 assumes spinning disks and steers the planner away from indexes |
| `max_wal_size`, `checkpoint_timeout` | Larger than defaults on write-heavy systems | Fewer, smoother checkpoints; check `pg_stat_checkpointer` (17+) or `pg_stat_bgwriter` |

`ALTER SYSTEM` plus `SELECT pg_reload_conf();` applies most settings; some (such as `shared_buffers`, `shared_preload_libraries`) need a restart. `SELECT name, setting, source FROM pg_settings WHERE source <> 'default';` shows what has been changed.

## MVCC, vacuum and bloat

Updates and deletes leave dead row versions. Autovacuum reclaims them for reuse and refreshes planner statistics; it does not shrink files.

- **Never disable autovacuum.** For large, busy tables lower the thresholds per table instead of globally:

  ```sql
  ALTER TABLE events SET (autovacuum_vacuum_scale_factor = 0.02, autovacuum_analyze_scale_factor = 0.01);
  ```
- **What blocks vacuum:** long-running transactions (including idle-in-transaction sessions and long reports on a hot standby with `hot_standby_feedback` on), abandoned replication slots, and prepared transactions. Check `pg_stat_activity` for the oldest `xact_start`, and `pg_replication_slots` for inactive slots.
- **Watch:** `pg_stat_user_tables` (`n_dead_tup`, `last_autovacuum`, `last_autoanalyze`) and `pg_stat_progress_vacuum` for running vacuums.
- **Transaction ID wraparound** forces an emergency anti-wraparound vacuum, and in the worst case stops writes. Monitor `SELECT datname, age(datfrozenxid) FROM pg_database ORDER BY 2 DESC;` and alert when the age passes `autovacuum_freeze_max_age` (200 million by default) and keeps climbing; the hard stop is near 2 billion, and the usual cause is something blocking vacuum (above).
- **Removing bloat:** `VACUUM FULL` and `CLUSTER` rewrite the table under an `ACCESS EXCLUSIVE` lock that blocks reads and writes for the whole run. On live tables use the `pg_repack` extension (if installed and approved) instead. Bloated indexes can be rebuilt with `REINDEX INDEX CONCURRENTLY` (12+).
- Run `ANALYZE` after bulk loads and large deletes so plans reflect the new data.

## Locks and blocking

- Find blockers: `SELECT pid, pg_blocking_pids(pid) AS blocked_by, wait_event_type, state, left(query, 80) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0;`
- A DDL statement waiting for an `ACCESS EXCLUSIVE` lock blocks every later query on that table, even plain reads. Always set `lock_timeout` before DDL on live tables (see the migration reference).
- `pg_cancel_backend(pid)` cancels a query; `pg_terminate_backend(pid)` ends the session and rolls back its transaction. Both affect someone else's work: confirm with the user first.
- Deadlocks are reported in the server log with both statements. Fix by taking locks in a consistent order, keeping transactions short, and retrying the losing transaction in application code.

## jsonb

- Use `jsonb` (not `json`) for documents you query; `json` keeps the original text and re-parses it on each access.
- Operators: `->` returns `jsonb`, `->>` returns text, `#>>'{a,b}'` follows a path, `@>` tests containment, `?` tests key existence, `@?` and `@@` evaluate SQL/JSON path expressions.
- Indexing: a GIN index with the default `jsonb_ops` supports `@>`, `?`, `?|`, `?&` and path operators; `jsonb_path_ops` is smaller and faster but supports only containment and path operators. For one frequently filtered key, a B-tree expression index is smaller still: `CREATE INDEX ON events ((payload->>'user_id'));` (the query must use the same expression and type).
- Columns you filter, join, sort, constrain or report on regularly belong in real columns. Large documents updated in place are rewritten whole (TOAST), which multiplies write volume.
- PostgreSQL 16-17 add SQL-standard JSON constructors, `IS JSON` predicates and `JSON_TABLE`; prefer them on new code when the version allows.

## Extensions

Install only extensions the user approves; on managed services only those on the provider's list. An extension runs inside the server with high privilege, so treat a new one like a new dependency (`../../engineering-practices/references/dependencies.md`).

| Extension | Use |
|---|---|
| `pg_stat_statements` | Query statistics; needs `shared_preload_libraries` and a restart; reset with `pg_stat_statements_reset()` before a measurement window |
| `auto_explain` | Logs plans of statements slower than a threshold; set `auto_explain.log_analyze` only briefly, it adds overhead |
| `pg_trgm` | Trigram GIN or GiST indexes for `LIKE '%term%'`, `ILIKE` and similarity search |
| `citext` | Case-insensitive text type |
| `postgis` | Geometry and geography types and spatial indexes; see `geospatial.md` |
| `pgvector` | Vector similarity search; index and recall trade-offs belong with the retrieval design in `../../ml-engineering/references/rag-systems.md` |
| `postgres_fdw` | Query another PostgreSQL server; watch for pulling whole remote tables across the network |
| `pg_partman` | Automates creating and retiring time-based partitions |
| `pgcrypto` | Hashing and encryption functions; `gen_random_uuid()` is built in since 13 and `uuidv7()` since 18 |

TimescaleDB is popular for time series; parts of it are under a source-available license rather than an open-source one, so check the license against the user's use (especially offering it as a service).

## Partitioning

- Declarative partitioning by `RANGE` (time), `LIST` (tenant or region) or `HASH`. Queries must filter on the partition key for pruning to help; check the plan for `Partitions removed` or only the expected partitions scanned.
- Retention becomes cheap: `ALTER TABLE events DETACH PARTITION events_2024_01 CONCURRENTLY;` (14+) then drop or archive it, instead of a giant `DELETE`.
- Unique constraints and primary keys must include the partition key. Thousands of partitions slow planning; keep the count moderate.

## Replication and high availability

- **Streaming (physical) replication** copies the whole cluster byte for byte; standbys serve read-only queries. Monitor lag on the primary with `SELECT application_name, state, write_lag, flush_lag, replay_lag FROM pg_stat_replication;`.
- **Logical replication** publishes chosen tables, works across major versions and is used for upgrades and selective copies. It does not replicate DDL or sequence values; plan for both.
- Reads from a replica can be stale; a user who just wrote data may not see it. Route read-your-own-writes to the primary.
- A replication slot retains WAL until its consumer catches up. An abandoned slot fills the primary's disk; alert on `pg_replication_slots` where `active` is false and retained WAL grows.
- Failover is handled by tooling (Patroni and similar) or by the managed service. Never promote a standby or rewire replication without the user.

## Backups and restores

- `pg_dump` / `pg_restore` give logical, per-database backups: portable across versions, slow to restore for large databases, and a point-in-time snapshot only.
- Physical base backups plus continuous WAL archiving (pgBackRest, Barman or the provider's automated backups) allow point-in-time recovery.
- A backup counts only once a restore has been tested and timed. Before any destructive operation, confirm a recent restorable backup exists (`../../agent-safety/GUIDE.md`).

## Security notes

- Least-privilege roles: the application role owns nothing it does not need, cannot create objects in shared schemas, and reads only its tables. Since PostgreSQL 15, ordinary users can no longer create objects in the `public` schema by default; older databases still allow it unless revoked.
- Row-level security (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY` plus policies) enforces tenant isolation in the database; table owners and roles with `BYPASSRLS` skip it unless `FORCE ROW LEVEL SECURITY` is set.
- Connect with TLS and verify the server (`sslmode=verify-full` with the CA certificate). Credentials stay out of code and chat (`live-database-access.md`).

## Checks (done when)

- [ ] Server version and relevant settings read from the running server, not assumed.
- [ ] Diagnoses cite the view and the numbers that support them (`pg_stat_activity`, `pg_stat_statements`, `pg_stat_user_tables`, plans).
- [ ] Any configuration change has a before and after measurement and a rollback value.
- [ ] Nothing that blocks, rewrites, cancels, promotes or restores ran on a shared or production system without the user's go-ahead.
