# Prisma ORM: queries, transactions and migrations

Read this when a TypeScript or JavaScript project uses Prisma: writing or reviewing queries, transactions, raw SQL or the schema, setting up the client for serverless, or creating, editing, deploying or repairing Prisma migrations. Lock-safe schema changes in general are in `../../engineering-practices/references/data-and-migrations.md`; database behavior in `postgresql.md` and `mysql-and-sql-server.md`.

## Versions

Run `npx prisma --version` and keep `prisma` and the client package on the same version. Majors changed setup a lot: Prisma ORM 7 (late 2025) moved the connection URL out of `schema.prisma` into `prisma.config.ts`, uses driver adapters (for example `@prisma/adapter-pg`) and a TypeScript query engine instead of the Rust binary by default, generates the client into an explicit output path, and stopped some CLI side effects. Projects on 5.x and 6.x still read `url = env("DATABASE_URL")` from the schema. Write for the installed major, and read the official upgrade guide before crossing one. Command flags below can differ between majors; confirm with `--help`.

## The client

- One client per process. Each instance opens its own pool. In development with hot reload, keep the instance on `globalThis` so reloads do not open new pools.
- Serverless and autoscaled functions: a small pool per instance (often one connection) in front of an external pooler (PgBouncer or the provider's), and a direct, unpooled connection for migrations. With PgBouncer in transaction mode and older Prisma versions, add `pgbouncer=true` to the pooled URL. With driver adapters, pool size is set on the driver's pool, not in the URL.
- Credentials come from the environment or secret store by name (`../../agent-safety/references/secrets.md`). Enable query logging only in development: it prints parameter values.

## Reading data

- `select` lists the fields you need; `include` returns every scalar field plus relations. On hot paths and wide tables, `select`.
- Map results to response objects. Returning a model straight from an API handler leaks every column, including password hashes and internal flags.
- N+1: a query inside a loop over results. Use `include`, or fetch the children once with `where: { parentId: { in: ids } }` and group in code. Where the version offers `relationLoadStrategy`, compare `"join"` (one query) with `"query"` (one per relation) on real data; joins can multiply rows for large one-to-many relations.
- Cursor pagination: order by the sort column plus a unique tiebreaker (`[{ createdAt: "desc" }, { id: "desc" }]`), `take: limit + 1` to detect the next page, `cursor` with `skip: 1`. Offset pagination only for small admin lists.
- `findUnique` accepts only unique fields. For soft-deleted data use `findFirst({ where: { id, deletedAt: null } })`; `findUnique({ where: { id } })` happily returns a soft-deleted row.

## Writing data

- `updateMany` and `deleteMany` return `{ count }`, never rows. Newer versions offer `createManyAndReturn` and `updateManyAndReturn` on some databases; otherwise select the ids first and re-read the affected rows.
- `deleteMany()` and `updateMany()` without `where` touch every row. Review every bulk call for its filter.
- `upsert` needs a unique constraint on its `where` fields. Two concurrent upserts can still collide and raise P2002; retry once.
- `@updatedAt` is set by Prisma Client, not the database. Raw SQL, other services and database jobs leave it stale; use a database default or trigger if other writers exist.
- Optimistic concurrency: a `version` column, `updateMany({ where: { id, version }, data: { ..., version: { increment: 1 } } })`, and treat `count === 0` as a conflict.

## Transactions

```ts
// Independent writes: array form, one round trip, all or nothing
await prisma.$transaction([
  prisma.account.update({ where: { id: from }, data: { balance: { decrement: amount } } }),
  prisma.account.update({ where: { id: to }, data: { balance: { increment: amount } } }),
]);

// Dependent steps: interactive form; use tx everywhere inside, never the outer client
await prisma.$transaction(async (tx) => {
  const order = await tx.order.findUniqueOrThrow({ where: { id } });
  if (order.status !== "PENDING") throw new Error("Order is not pending");
  await tx.order.update({ where: { id }, data: { status: "PAID" } });
}, { timeout: 10_000, isolationLevel: "Serializable" });
```

- Interactive transactions time out after 5 seconds by default (and wait at most 2 seconds to start). Never call email, payment or other HTTP APIs inside one: the transaction holds locks and a pooled connection while it waits. Do the external call before or after, with an idempotency key.
- Under `Serializable`, conflicts surface as errors; retry the whole transaction a bounded number of times.

## Raw SQL

- `prisma.$queryRaw` and `$executeRaw` used as tagged templates turn `${value}` into bind parameters. Build dynamic parts with `Prisma.sql` and `Prisma.join`.
- `$queryRawUnsafe`, `$executeRawUnsafe` and `Prisma.raw` with interpolated input are SQL injection. Allow them only with constant strings or values checked against an allow-list (for example a sort column name).
- Typed SQL files (`prisma generate --sql`) give typed results for hand-written queries where the version supports them.

## Errors and types

- Catch `Prisma.PrismaClientKnownRequestError` at the service boundary and map codes to domain errors: P2002 unique violation (the `meta` names the fields), P2025 record not found, P2003 foreign-key violation. Never send raw Prisma messages to clients.
- `BigInt` fields break `JSON.stringify`; convert to strings at the boundary. `Decimal` fields are decimal objects; do arithmetic with their methods, not JavaScript numbers. `DateTime` values are UTC `Date` objects.

## Migrations

| Command | Use | Never |
|---|---|---|
| `prisma migrate dev` | Local development: creates a migration from the schema, applies it, uses a shadow database | On shared, staging or production databases: on drift it offers to reset, which drops all data |
| `prisma migrate dev --create-only` | Generate the SQL without applying it, to edit it first | |
| `prisma migrate deploy` | CI/CD and every shared environment: applies pending migrations in order | |
| `prisma migrate status`, `prisma migrate diff` | What is pending; the SQL between two states; drift checks | |
| `prisma migrate resolve --applied` or `--rolled-back` | Mark a migration in the history table after a failure was fixed by hand | Expecting it to undo anything: it changes only the history |
| `prisma db push` | Prototypes without migration history | Anything with data you keep; with `--accept-data-loss` it drops columns |
| `prisma migrate reset` | Rebuild a local database | Anywhere else |

Running any of these against a shared database is a production change: prepare the command and hand it over (`../../agent-safety/GUIDE.md`).

### Traps in generated SQL

Read every `migration.sql` before it runs anywhere, and run `python3 <productcraft>/modules/engineering-practices/scripts/migration_check.py prisma/migrations/*/migration.sql` on new ones.

- **Renames become data loss.** Prisma does not detect renames: renaming a field generates `DROP COLUMN` plus `ADD COLUMN`. To rename only in code, keep the column with `@map("old_name")` (and `@@map` for tables). To rename in the database, generate with `--create-only`, change the SQL to `ALTER TABLE ... RENAME COLUMN`, and still follow expand and contract for the running application.
- **Required columns on populated tables:** add the column as optional, backfill in batches (not one `updateMany` over millions of rows), then make it required in a later migration.
- **Indexes on large PostgreSQL tables:** generated SQL uses plain `CREATE INDEX`, which blocks writes. Generate with `--create-only`, change it to `CREATE INDEX CONCURRENTLY`, and keep that statement alone in its own migration: a multi-statement script runs as one implicit transaction on PostgreSQL, where `CONCURRENTLY` fails. Rehearse it in staging.
- **Never edit an applied migration.** The history then disagrees with the database and `migrate dev` wants to reset. Write a new migration.
- **Failed migration in production:** `migrate deploy` refuses to continue (P3009). Inspect what partially applied, fix forward with SQL the user approves, then mark it with `migrate resolve`.
- **Existing database, no history:** create a baseline migration from the current schema with `migrate diff`, then mark it applied with `migrate resolve --applied` on each environment.

## Checks (done when)

- [ ] Prisma version known; client created once per process; migrations use a direct connection.
- [ ] API responses use mapped objects; no `include` of sensitive relations by default.
- [ ] Every bulk write has a reviewed `where`; counts, not rows, are expected from bulk calls.
- [ ] No external calls inside interactive transactions; conflicts and P2002 retried where expected.
- [ ] No `*Unsafe` raw SQL with interpolated input.
- [ ] Each new `migration.sql` was read and checked; renames, required columns and indexes follow the safe recipes; `migrate deploy` (not `dev`) is the command handed over for shared environments.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Column data gone after a "rename" | Generated drop and add | `@map`, or hand-edited `RENAME COLUMN` |
| "Transaction already closed" | External call or slow loop inside an interactive transaction | Move it out; raise `timeout` only for genuine bulk work |
| Connection limit reached on serverless | A pool per instance with many instances | External pooler, tiny per-instance pool |
| Soft-deleted record returned | `findUnique` by id | `findFirst` with `deletedAt: null` |
| `TypeError` serializing a response | `BigInt` field | Convert to string at the boundary |
| `migrate deploy` blocked | Earlier migration failed (P3009) | Fix forward, then `migrate resolve` |
