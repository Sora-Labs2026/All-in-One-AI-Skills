# Data modeling and safe migrations

Read this when you design tables or documents, write a schema migration, change a column or index, backfill data, or plan how a schema change ships alongside code.

The data is the one part of a system you cannot fix by redeploying the previous version. Plan schema work so that every step can run while both the old and the new application version are live, and so that a code rollback never needs a schema rollback.

## Modeling choices that age well

- **Put invariants in the database.** `NOT NULL`, `UNIQUE`, foreign keys and `CHECK` constraints hold no matter which code path, script or person writes. Application validation exists to give users good messages; constraints keep the data true.
- **Keys.** Use surrogate primary keys (`bigint` identity or UUID). For UUIDs, time-ordered UUIDv7 (RFC 9562) keeps B-tree inserts local, unlike random v4. Unguessable IDs are not authorization; check ownership on every access (LaunchGuard #7).
- **Time.** Store instants as `timestamptz` (PostgreSQL) or UTC. When local wall-clock time matters (recurring meetings, opening hours), also store the IANA time zone name.
- **Money.** `numeric(precision, scale)` or integer minor units, with a currency column. Never `float` or `double`.
- **Status fields.** A small `text` column with a `CHECK (status IN (...))` constraint, or a lookup table, is easier to evolve than a PostgreSQL enum type, whose values cannot simply be removed. Record state transitions with timestamps when history matters.
- **Case-insensitive uniqueness.** A unique index on `lower(email)` (or a case-insensitive type such as `citext`) rather than application-side checks.
- **Soft delete costs.** A `deleted_at` column affects every query and every unique constraint (use a partial unique index `WHERE deleted_at IS NULL`) and may conflict with deletion obligations for personal data (LaunchGuard gate 2). Consider an archive table instead.
- **Multi-tenant data.** Put `tenant_id` on every tenant-owned row, lead composite indexes with it, include it in foreign keys where possible, and enforce isolation with row-level security or a mandatory query scope (LaunchGuard #4 and #7).
- **JSON columns** suit genuinely variable attributes. Columns you filter, join, constrain or report on belong in real columns.
- **Indexes follow queries.** Index the columns real queries filter, join and sort on, including foreign-key columns (PostgreSQL does not index the referencing side automatically). Every index costs write time and storage; remove unused and duplicate ones.
- **Normalize first.** Denormalize only for a measured read path, with one clearly owned writer that keeps the copies consistent.

## Migration rules

1. **One migration tool, versioned files, applied in order.** Never edit a migration that has run anywhere shared; write a new one.
2. **Schema migrations change schema.** Large data changes run as separate backfills (below).
3. **Additive first, destructive last and alone.** New tables, nullable columns and new indexes can ship any time. Drops, renames and type changes ship in their own later release, after no deployed code depends on the old shape.
4. **Every step is compatible with the running app (N) and the next app (N+1).** Deploy order matters: expand the schema, deploy code, then contract.
5. **Set lock and statement timeouts** so a migration that cannot get its lock fails quickly instead of queueing every other query behind it. PostgreSQL: `SET lock_timeout = '5s'; SET statement_timeout = '15min';` at the top of the migration (adjust to the table), then retry later. MySQL: `SET SESSION lock_wait_timeout = 5;`.
6. **Read the SQL your ORM generates** before applying it: Django `python manage.py sqlmigrate <app> <migration>`, Alembic `alembic upgrade <rev> --sql`, Prisma migration folders already contain `migration.sql`. ORMs readily emit table rewrites and blocking index builds.
7. **Write the down path, or say why there is none.** Reversible steps get a tested down migration. Destructive steps cannot restore data on the way down; state that in the file and make sure a verified backup or the still-present old column covers it.
8. **Never run a migration against production or a shared database without explicit permission.** Prepare it, test it locally, in CI and in staging, then hand over the exact command and the rollback.

## Expand, migrate, contract

Example: replace `users.name` with `users.full_name`.

| Release | Schema | Application | Rollback at this point |
|---|---|---|---|
| 1. Expand | Add `full_name` nullable | No change | Drop the unused column, or leave it |
| 2. Dual-write | none | Write both columns on every insert and update; still read `name` | Redeploy release 1 code |
| 3. Backfill | none | Batched job copies `name` to `full_name` where `full_name IS NULL` | Stop the job; nothing reads `full_name` yet |
| 4. Switch reads | Optionally enforce `NOT NULL` on `full_name` (safe recipe below) | Read `full_name`, still write both | Redeploy release 2 code; both columns are current |
| 5. Stop old writes | none | Stop writing `name`; tell ORMs that cache column lists to ignore it | Redeploy release 4 code |
| 6. Contract | Drop `name` | none | Restore from backup only; this step is the point of no return |

Let each release bake in production long enough to see real traffic before starting the next. The same pattern covers type changes (new column of the new type), splitting a table, and moving data to another store.

## Backfills

- Run them as a separate, resumable job or script, not inside the schema migration or the deploy.
- Walk the primary key in batches, one short transaction per batch:

```sql
-- 1. find the end of the next batch; stop when batch_end is NULL. :last_id starts at 0
SELECT max(id) AS batch_end
FROM (SELECT id FROM users WHERE id > :last_id ORDER BY id LIMIT 1000) AS next_batch;

-- 2. update exactly that range in its own short transaction
UPDATE users
SET full_name = name
WHERE id > :last_id AND id <= :batch_end AND full_name IS NULL;

-- 3. set :last_id = :batch_end, pause, repeat
```

- Make it idempotent (the `IS NULL` condition lets a rerun skip finished rows) and resumable (persist `:last_id`), log progress, and pause between batches. Watch database CPU, lock waits and replication lag, and slow down if they rise.
- Prove completion with a count: `SELECT count(*) FROM users WHERE full_name IS NULL AND name IS NOT NULL;` must return 0 before reads switch.
- Never run one `UPDATE` over a large table: it holds row locks for its whole duration, bloats the table, floods the write-ahead log and stalls replicas.

## PostgreSQL lock-safe recipes

| Goal | Risky form | Safer form |
|---|---|---|
| Add an index | `CREATE INDEX` (blocks writes for the whole build) | `CREATE INDEX CONCURRENTLY`, outside a transaction block. If it fails it leaves an `INVALID` index: `DROP INDEX CONCURRENTLY` it and retry |
| Add a foreign key | `ADD CONSTRAINT ... FOREIGN KEY` (validates while blocking writes on both tables) | `ADD CONSTRAINT ... NOT VALID`, then `VALIDATE CONSTRAINT` in a later migration |
| Add a CHECK | `ADD CONSTRAINT ... CHECK (...)` (scans under an exclusive lock) | `... CHECK (...) NOT VALID`, then `VALIDATE CONSTRAINT` |
| Make a column NOT NULL | `ALTER COLUMN ... SET NOT NULL` (full scan under an exclusive lock) | Add `CHECK (col IS NOT NULL) NOT VALID`, validate it, then `SET NOT NULL` (PostgreSQL 12+ uses the validated check and skips the scan), then drop the check |
| Add UNIQUE or PRIMARY KEY | `ADD CONSTRAINT ... UNIQUE (...)` | `CREATE UNIQUE INDEX CONCURRENTLY idx ...`, then `ADD CONSTRAINT name UNIQUE USING INDEX idx` |
| Add a column with a default | Volatile default (`gen_random_uuid()`, `random()`, `clock_timestamp()`), `serial`, identity or stored generated column: rewrites the table | Constant or stable defaults (including `now()`) are metadata-only since PostgreSQL 11. Otherwise add nullable, set the default for new rows, backfill |
| Change a column type | `ALTER COLUMN ... TYPE` (usually rewrites the table and its indexes) | New column plus expand/contract. Some changes are metadata-only, such as increasing a `varchar` limit or converting `varchar` to `text` |
| Rename | `RENAME COLUMN` (instant, but breaks running code) | Expand/contract, or a view that exposes the new name during transition |

Check what a running migration is waiting on in staging with `SELECT pid, wait_event_type, state, query FROM pg_stat_activity WHERE datname = current_database();` and `pg_locks`.

## MySQL and SQLite notes

- **MySQL (InnoDB)** supports online DDL for many changes. State the expectation explicitly, for example `ALTER TABLE t ADD COLUMN c INT NULL, ALGORITHM=INSTANT;` or `ALGORITHM=INPLACE, LOCK=NONE`, so MySQL errors instead of silently copying the table. For large tables use an online schema change tool (`gh-ost`, `pt-online-schema-change`). Long-running transactions hold metadata locks that block DDL, and waiting DDL then blocks new queries; set `lock_wait_timeout`.
- **SQLite** supports only a few `ALTER TABLE` forms. Other changes need the documented rebuild: create the new table, copy rows, drop the old table, rename the new one, inside one transaction with foreign-key checks handled as the SQLite documentation describes.

## Testing migrations

- CI applies every migration to an empty database and runs the test suite against the result.
- For new migrations, run up, down, up to prove the down path and idempotent re-application.
- Run the previous application version's tests (or at least its main queries) against the migrated schema to prove N-1 compatibility.
- For a large table, time the migration and the backfill on a production-sized, anonymized copy, and watch which locks it takes.
- Run the bundled checker on the new files: `python3 <productcraft>/modules/engineering-practices/scripts/migration_check.py <files>`. Handle each open finding or acknowledge it with a reason.

## Rollback planning

- Write down, before deploying, what rollback means for each step: redeploy the previous code (normal case), run the down migration (reversible steps only), or restore data (destructive steps).
- Take a backup or snapshot before any destructive step, and confirm that restores have been tested, not merely that backups exist.
- Decide in advance whether a problem in a data transformation is fixed forward or rolled back; for large tables forward fixes are usually faster and safer.

## Checks (done when)

- [ ] Each migration step is compatible with both the running and the next application version.
- [ ] No in-place rename, type change or drop of something deployed code still uses.
- [ ] Large data changes are batched, resumable backfills with a completion query.
- [ ] Lock and statement timeouts are set, or the migration tool sets them.
- [ ] Generated SQL was read; `migration_check.py` was run on new files and every open finding is handled.
- [ ] Up, down and up again succeed on a fresh database, or the file states why it is forward-only.
- [ ] The user has the apply command, the expected duration and the rollback for every environment you were not allowed to touch.

## Anti-patterns

- Renaming a column and shipping the code that uses the new name in the same release.
- Adding a `NOT NULL` column without a default to a populated table.
- `CREATE INDEX` without `CONCURRENTLY` on a busy PostgreSQL table.
- A single `UPDATE` across millions of rows inside a migration.
- Editing an already-applied migration file.
- A down migration that was never run.
- Storing money as floats or timestamps without a zone.
- Enforcing uniqueness only in application code.
