# Querying a real database safely

Read this before the agent connects to any database that holds real data: to answer an analytical question, to debug production behavior, to profile tables, or to build a dataset. It covers credentials, read-only enforcement, bounding queries and handling personal data. Changes to schema or data follow `../../engineering-practices/references/data-and-migrations.md` and the stop-check in `../../agent-safety/GUIDE.md`.

## Before connecting

1. **Ask which system and why.** Prefer, in order: a local or CI database, a staging copy, an anonymized snapshot, a read replica, and only then the primary. State which one you will use.
2. **Get a read-only account** created by the owner for this purpose. Do not borrow the application's account or an administrator's.
3. **Keep credentials out of the conversation.** The user puts them where the client reads them; you refer to them by name. See `../../agent-safety/references/secrets.md` and, for values the user must type, `../../agent-safety/references/guided-setup.md`.

| Engine | Where credentials live | Notes |
|---|---|---|
| PostgreSQL | `PGHOST`, `PGUSER`, `PGDATABASE` environment variables plus `~/.pgpass` (mode 0600), or a named service in `~/.pg_service.conf` used as `psql service=analytics` | `libpq` reads these automatically; never put the password in the connection string on the command line, where process listings and shell history expose it |
| MySQL | `~/.my.cnf` (mode 0600) with a `[client]` section, or an encrypted login path from `mysql_config_editor set --login-path=analytics` | `mysql --login-path=analytics` |
| SQL Server | Integrated (Kerberos or Windows) authentication or Microsoft Entra ID where available; otherwise environment variables read by the script | Avoid storing SQL logins in project files |

Committed config files hold only names and placeholders (`connections.example.json`, `.env.example`); the real file is git-ignored and readable only by the user.

## Enforce read-only on the server, not in the client

A client-side check that rejects statements containing `INSERT` or `DELETE` is a convenience, not a boundary: comments, `WITH x AS (DELETE ... RETURNING ...)` in PostgreSQL, functions with side effects and stored procedures all get past keyword filters. The guarantee must come from privileges.

**PostgreSQL**

```sql
-- run by the owner, once
CREATE ROLE analyst LOGIN;
GRANT CONNECT ON DATABASE app TO analyst;
GRANT USAGE ON SCHEMA public TO analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyst;   -- or only the tables needed
ALTER ROLE analyst SET default_transaction_read_only = on;
ALTER ROLE analyst SET statement_timeout = '60s';
ALTER ROLE analyst SET idle_in_transaction_session_timeout = '2min';
```

PostgreSQL 14+ also offers the predefined `pg_read_all_data` role; it is broad, so prefer table grants. Per session, `BEGIN READ ONLY;` or `SET default_transaction_read_only = on;` adds a second layer.

**MySQL**

```sql
CREATE USER 'analyst'@'10.%' IDENTIFIED BY '<set by the owner>' REQUIRE SSL;
GRANT SELECT ON app.* TO 'analyst'@'10.%';
-- per session
SET SESSION TRANSACTION READ ONLY;
SET SESSION max_execution_time = 60000;   -- milliseconds, SELECT statements only
```

**SQL Server**

```sql
CREATE USER analyst FOR LOGIN analyst_login;
ALTER ROLE db_datareader ADD MEMBER analyst;
-- per session
SET LOCK_TIMEOUT 5000;
```

In an availability group, `ApplicationIntent=ReadOnly` in the connection string routes to a readable secondary when read-only routing is configured. Set a command timeout in the driver as well.

## Bound every query

- **Look before you pull.** Check sizes first: `SELECT reltuples::bigint FROM pg_class WHERE relname = 't';` (PostgreSQL estimate), `information_schema.TABLES.TABLE_ROWS` (MySQL estimate), `sys.dm_db_partition_stats` (SQL Server). Then `EXPLAIN` anything that joins or aggregates large tables.
- **Limit rows** while exploring (`LIMIT`, `TOP`), select only needed columns, and aggregate in the database instead of transferring raw rows.
- **Sample** with `TABLESAMPLE SYSTEM (1)` (PostgreSQL; `TABLESAMPLE (1 PERCENT)` in SQL Server; block-level, fast, but rows arrive in clumps) or `TABLESAMPLE BERNOULLI (1)` (PostgreSQL; row-level, slower, closer to random). Add `REPEATABLE (42)` in PostgreSQL for the same sample twice, or filter on a stable key (`WHERE id % 100 = 0` for well-distributed integer keys).
- **Timeouts at both ends:** a server-side statement timeout and a client timeout. A runaway query on a primary competes with real users.
- **Avoid long transactions.** An open transaction, even a read-only one, holds back vacuum in PostgreSQL and keeps undo history alive in MySQL. Use autocommit for ad hoc reads.
- **Exports:** stream with server-side cursors (`psycopg` named cursors, `COPY (SELECT ...) TO STDOUT` in PostgreSQL) instead of fetching everything into memory.

## Personal and sensitive data

- Query the minimum: aggregates, counts and distributions answer most analytical questions without reading individual records.
- Do not paste rows containing personal data (names, emails, addresses, identifiers, health or financial details) into the chat, reports, tickets or commits. Show schemas, counts and masked or synthetic examples instead.
- Suppress small groups in shared outputs (for example counts under 10) when the data is sensitive, because small cells can identify people.
- Extracts are copies with the same obligations as the source: keep them out of the repository, delete them when done, and tell the user where they are. Retention, purpose limits and data subject rights are covered in `../../legal-ready/GUIDE.md`.

## When a write is needed

Stop and hand over. Write the statement as a script that runs in a transaction, prints the number of affected rows, verifies the result with a query, and rolls back unless an explicit flag is passed. Include the backup or restore point to use. Run it only after the user approves, against the environment they named.

## Report

- Which database and role were used, and how read-only was enforced.
- Every query that ran (or a summary for many), with row counts and run times.
- Where any extract was written and whether it contains personal data.

## Checks (done when)

- [ ] The user named the environment; a replica or copy was used where possible.
- [ ] Credentials were never shown in the conversation, the command line or committed files.
- [ ] Read-only enforced by privileges, plus session settings and timeouts.
- [ ] Queries bounded (columns, rows, timeouts) and checked with `EXPLAIN` when heavy.
- [ ] No personal data copied into outputs; extracts accounted for.
