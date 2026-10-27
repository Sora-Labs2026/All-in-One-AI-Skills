# SQL that is correct first, then fast

Read this when you write or review a non-trivial query (joins, aggregates, windows, recursion, pagination), when a query is slow, or when someone proposes an index. Engine-specific operations live in `postgresql.md` and `mysql-and-sql-server.md`; schema changes and migrations in `../../engineering-practices/references/data-and-migrations.md`; the general measure-change-measure loop in `../../engineering-practices/references/performance.md`.

## Correctness traps that survive review

| Trap | What goes wrong | Write instead |
|---|---|---|
| `NOT IN (subquery)` where the subquery can return NULL | Returns no rows at all, because `x NOT IN (1, NULL)` is unknown | `NOT EXISTS (SELECT 1 FROM ... WHERE ...)` |
| `WHERE col = NULL` or `col <> 'x'` expecting NULL rows | NULL never compares equal or unequal | `col IS NULL`; `col IS DISTINCT FROM 'x'` (PostgreSQL, SQL Server 2022+), `NOT (col <=> 'x')` (MySQL) |
| `COUNT(col)` read as a row count | Skips NULLs | `COUNT(*)` for rows, `COUNT(col)` for non-null values, and say which |
| Joining a one-to-many table, then summing a column of the "one" side | Each parent row is repeated once per child, inflating totals | Aggregate the child table in a subquery or CTE first, then join one row per key |
| `SELECT DISTINCT` added to make duplicates go away | Hides a join on the wrong or incomplete key | Find the key that makes the join one-to-one; assert it with a count |
| Integer division (`7 / 2` gives 3 in PostgreSQL and SQL Server) | Silent truncation in ratios and percentages | Cast one side: `7::numeric / 2`, `CAST(7 AS decimal(18,4)) / 2` |
| `LAST_VALUE(x) OVER (ORDER BY t)` | The default frame ends at the current row (and its peers), so it returns the current value | Add `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`, or use `FIRST_VALUE` with a reversed order |
| Running total with `SUM(x) OVER (ORDER BY day)` when days repeat | The default `RANGE` frame adds all rows sharing that day at once | `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` and a unique tiebreaker in `ORDER BY` |
| `ORDER BY` without a unique tiebreaker in paginated or "top N" queries | Rows move between pages or runs | Append the primary key to every `ORDER BY` that feeds pagination or ranking |
| Comparing a timestamp column to a date literal (`created_at = '2026-03-01'`) | Matches only midnight | Half-open range: `created_at >= '2026-03-01' AND created_at < '2026-03-02'` |
| Time zones | `timestamp` without zone compared with `now()` in another zone | Store instants as `timestamptz` or UTC; convert at the edges |
| Building SQL with string concatenation | Injection, broken quoting, plan cache pollution | Bind parameters (LaunchGuard control #13 in `../../launchguard/references/security-baseline.md`) |

Set-based statements beat loops. A cursor or a per-row loop in application code that issues one query per row is almost always replaceable by one statement with a join, a window function or `INSERT ... SELECT`.

## Patterns worth knowing

```sql
-- Latest row per group: a window function works in all three engines
SELECT *
FROM (
  SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC, id DESC) AS rn
  FROM orders o
) ranked
WHERE rn = 1;

-- PostgreSQL shortcut for the same thing
SELECT DISTINCT ON (customer_id) *
FROM orders
ORDER BY customer_id, created_at DESC, id DESC;

-- Top 3 per group that can use an index on orders(customer_id, created_at):
-- LATERAL in PostgreSQL and MySQL 8.0.14+, CROSS APPLY in SQL Server
SELECT c.id, o.id AS order_id, o.created_at
FROM customers c
CROSS JOIN LATERAL (
  SELECT id, created_at FROM orders
  WHERE orders.customer_id = c.id
  ORDER BY created_at DESC, id DESC
  LIMIT 3
) o;

-- Keyset pagination: constant cost per page, unlike OFFSET which reads and discards
SELECT id, created_at, total
FROM orders
WHERE (created_at, id) < (:last_created_at, :last_id)   -- row comparison: PostgreSQL, MySQL
ORDER BY created_at DESC, id DESC
LIMIT 50;

-- Recursive walk with a depth guard against cycles
WITH RECURSIVE tree AS (
  SELECT id, parent_id, 1 AS depth FROM categories WHERE id = :root
  UNION ALL
  SELECT c.id, c.parent_id, t.depth + 1
  FROM categories c JOIN tree t ON c.parent_id = t.id
  WHERE t.depth < 50
)
SELECT * FROM tree;
```

SQL Server spells the recursive CTE `WITH tree AS (...)` (no `RECURSIVE`), uses `TOP (n)` or `OFFSET ... FETCH NEXT n ROWS ONLY`, and has no row-value comparison, so expand keyset predicates to `created_at < @c OR (created_at = @c AND id < @id)`.

**CTEs and materialization.** PostgreSQL 12+ inlines a non-recursive CTE that is referenced once and has no side effects; add `MATERIALIZED` to force a separate evaluation, `NOT MATERIALIZED` to force inlining. Before 12 every CTE was an optimization fence. SQL Server always inlines CTEs (a CTE referenced twice runs twice; use a temp table to compute once). MySQL 8.0 may materialize or merge derived tables and CTEs; check the plan.

## Dialect differences that bite during ports

| Topic | PostgreSQL | MySQL 8 | SQL Server |
|---|---|---|---|
| Row limit | `LIMIT n OFFSET m` | `LIMIT m, n` or `LIMIT n OFFSET m` | `TOP (n)`; `OFFSET m ROWS FETCH NEXT n ROWS ONLY` (needs `ORDER BY`) |
| Upsert | `INSERT ... ON CONFLICT (key) DO UPDATE` | `INSERT ... ON DUPLICATE KEY UPDATE` | `MERGE` (has known concurrency pitfalls; use `UPDATE` then `INSERT` with `HOLDLOCK`, or a unique constraint plus retry) |
| String concatenation | `||` (NULL-propagating), `concat()` | `CONCAT()` (`||` is OR unless `PIPES_AS_CONCAT`) | `+` (NULL-propagating), `CONCAT()` |
| Case sensitivity of `=` on text | Case-sensitive (use `citext`, `ILIKE` or `lower()`) | Depends on collation; the default `utf8mb4_0900_ai_ci` ignores case and accents | Depends on collation; defaults are usually case-insensitive |
| Booleans | `boolean` | `TINYINT(1)` alias | `bit` |
| Auto keys | `GENERATED ALWAYS AS IDENTITY` | `AUTO_INCREMENT` | `IDENTITY(1,1)` |
| Current UTC instant | `now()` (transaction start, `timestamptz`) | `UTC_TIMESTAMP()` | `SYSUTCDATETIME()` |
| Empty string vs NULL | Distinct | Distinct | Distinct (Oracle is the one that treats `''` as NULL) |

## Tuning loop for one query

1. **Find the queries that matter.** Rank by total time (calls times mean), not by the single slowest call: PostgreSQL `pg_stat_statements`, MySQL `performance_schema.events_statements_summary_by_digest` or the `sys` schema views, SQL Server Query Store (on by default for new databases since SQL Server 2022). Slow query logs show individual examples with real parameters.
2. **Get the actual plan on a realistic copy.** Plans depend on data volume, distribution and statistics; a plan from a 1,000-row dev table says little.
   - PostgreSQL: `EXPLAIN (ANALYZE, BUFFERS, SETTINGS) <query>;` (PostgreSQL 18 includes buffers by default with `ANALYZE`).
   - MySQL 8.0.18+: `EXPLAIN ANALYZE <query>;` or `EXPLAIN FORMAT=TREE` for the estimate only.
   - SQL Server: include the actual execution plan, and `SET STATISTICS IO, TIME ON;` for logical reads and CPU time.

   `ANALYZE` variants **execute** the statement. Wrap data-changing statements in `BEGIN; ... ROLLBACK;` and never run them against production without permission (`../../engineering-practices/GUIDE.md`, ground rule 6).
3. **Read the plan from the most expensive node down** (below).
4. **Change one thing**: refresh statistics, rewrite the query, add or change one index.
5. **Re-measure with the same parameters and cache state** (run each version several times; compare the median and the buffer or logical-read counts, which are less noisy than milliseconds).

## Reading a plan

- **Estimated vs actual rows.** A large mismatch (10x or more) at a node is the usual root cause of a bad join order or algorithm. Fix in this order: refresh statistics (`ANALYZE t;`, `ANALYZE TABLE t;`, `UPDATE STATISTICS t;`); add statistics for correlated columns (PostgreSQL `CREATE STATISTICS ... (dependencies, ndistinct, mcv) ON a, b FROM t;`, MySQL histograms with `ANALYZE TABLE t UPDATE HISTOGRAM ON col`); then rewrite predicates the planner cannot estimate (functions on columns, `OR` across tables).
- **Loops multiply.** In PostgreSQL output, a node's actual time and rows are per loop; a nested-loop inner side with `loops=50000` costs 50,000 times what it shows.
- **Scans.** A sequential or full scan is right when the query reads a large fraction of the table. It is a problem when a selective filter discards most rows (`Rows Removed by Filter` is large).
- **Sorts and hashes that spill.** PostgreSQL `Sort Method: external merge` or hash batches above 1 mean `work_mem` was too small for that node; SQL Server shows spill warnings and memory grant warnings. Prefer an index that delivers rows already ordered, or a smaller input, over raising memory globally.
- **Index-only scans with many heap fetches** (PostgreSQL) mean the visibility map is stale: the table needs vacuuming.
- **Key lookups** (SQL Server) or bookmark lookups repeated many times mean the index lacks columns the query needs: include them, or accept the lookup if few rows qualify.
- **Implicit conversions** (comparing a `varchar` column to an `nvarchar` parameter, or a string column to a number) prevent index seeks. Match parameter types to column types.

## Index design

- **Order composite keys by use:** equality columns first, then the one range or sort column. An index on `(customer_id, created_at)` serves `WHERE customer_id = ? ORDER BY created_at DESC` with no sort; `(created_at, customer_id)` does not.
- **Leftmost prefix.** A B-tree on `(a, b, c)` helps filters on `a`, `a, b` and `a, b, c`. PostgreSQL 18 can skip-scan a leading column with few distinct values, but do not design around it.
- **Covering indexes** avoid table lookups: `INCLUDE (...)` in PostgreSQL 11+ and SQL Server; in MySQL InnoDB every secondary index already carries the primary key, and you add columns to the key itself.
- **Partial or filtered indexes** for a small, hot subset: `CREATE INDEX ... WHERE status = 'pending'` (PostgreSQL), `WHERE` filtered indexes (SQL Server). MySQL has none; use a generated column if needed.
- **Expressions:** an index on `lower(email)` (PostgreSQL), a functional key part `((lower(email)))` (MySQL 8.0.13+), or an indexed computed column (SQL Server). The query must use the same expression.
- **Non-sargable predicates** cannot use a plain index: `WHERE date(created_at) = ...`, `WHERE amount + 0 > 10`, `LIKE '%term'`, mismatched types. Rewrite as ranges on the bare column, or index the expression. Substring search needs trigram (PostgreSQL `pg_trgm` with GIN) or full-text indexes.
- **Other index types (PostgreSQL):** GIN for `jsonb` containment, arrays and full text; GiST for ranges, geometry and nearest-neighbor; BRIN for very large tables whose rows arrive in the order of the indexed column (timestamps in append-only logs), at a tiny fraction of B-tree size.
- **Cost.** Every index slows inserts and updates, uses memory and disk, and competes for cache. Before adding one, check for an existing index it duplicates or that could be extended.
- **Find dead weight** after a full business cycle of statistics: PostgreSQL `pg_stat_user_indexes` with `idx_scan = 0`, MySQL `sys.schema_unused_indexes` and `sys.schema_redundant_indexes`, SQL Server `sys.dm_db_index_usage_stats`. Check replicas too; an index unused on the primary may serve reports on a replica. MySQL 8 can make an index `INVISIBLE` to test its removal reversibly.
- **Build indexes online** on live tables: see the lock-safe recipes in `../../engineering-practices/references/data-and-migrations.md` and run `migration_check.py` on the migration.

## Rewrites that usually pay off

| Slow shape | Rewrite |
|---|---|
| Correlated subquery in the select list, executed per row | Aggregate once in a derived table and join, or `LATERAL` / `CROSS APPLY` with an index |
| `OR` across different columns or tables | `UNION ALL` of two indexed queries (deduplicate deliberately if needed) |
| `OFFSET 100000` | Keyset pagination |
| `COUNT(*) > 0` to test existence | `EXISTS (...)`, which stops at the first row |
| A huge `IN (...)` list from the application | Join to a `VALUES` list, a temporary table, or `= ANY($1::bigint[])` in PostgreSQL |
| `SELECT *` from a wide table | Name the columns; enables covering indexes and smaller transfers |
| The same expensive aggregate recomputed on every dashboard load | A summary table refreshed on a schedule or incrementally, or a materialized view (PostgreSQL `REFRESH MATERIALIZED VIEW CONCURRENTLY` needs a unique index); state its staleness |

**Parameter-sensitive plans.** A plan compiled for a rare value can be terrible for a common one. SQL Server caches the first compiled plan ("parameter sniffing"): diagnose with Query Store, then use `OPTION (RECOMPILE)` for infrequent queries, `OPTIMIZE FOR`, or the parameter-sensitive plan feature of compatibility level 160 (SQL Server 2022). PostgreSQL may switch a prepared statement to a cached generic plan after its first five executions; setting `plan_cache_mode = force_custom_plan` for the session tests whether that is the problem.

**Partitioning** is a data-management tool (dropping old data instantly, pruning large scans by date). It rarely fixes a slow point lookup and adds planning overhead; reach for it only when the plan shows partition pruning would remove most of the work.

## Checks (done when)

- [ ] Result correctness checked first: row count and a few totals compared with a simple, obviously correct version of the query on the same data.
- [ ] NULL handling, join cardinality and window frames reviewed against the traps table.
- [ ] Baseline and after plans captured on realistic data with the same parameters; the change is explained by the plan, not by a single timing.
- [ ] New indexes justified by a before and after plan, checked for duplicates, built online, and their write cost acknowledged.
- [ ] Nothing ran with `ANALYZE` or data changes against production or shared databases without permission.
