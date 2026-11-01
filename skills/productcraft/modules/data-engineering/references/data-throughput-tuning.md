# Data throughput: backfills, loads and pipelines that keep up

Read this when moving data is too slow: a backfill that will take days, an ingestion job falling behind, an export or warehouse load that misses its window, a sync between tables that never catches up. The goal is correct data in the right place sooner, with proof. Query tuning is in `sql-query-tuning.md`; large-data engines in `dask-and-out-of-core.md` and `spark.md`; batched backfills inside an application database in `../../engineering-practices/references/data-and-migrations.md`.

## First, find out what "slow" means

Split the pipeline into stages and measure each one separately: **extract** (reading the source), **transfer** (network and object storage), **transform**, **load** (writing the target), **publish** (derived and serving tables), and the **live tail** (new data arriving while the job runs).

- Record per stage: rows and bytes in and out, wall time, and what the stage waits on (CPU, disk, network, locks, a remote rate limit).
- Measure the arrival rate as well as the processing rate. Time to catch up is roughly `backlog / (processing rate - arrival rate)`: with 50 million rows behind, 20,000 rows per second processed and 5,000 arriving, that is about 3,300 seconds. If processing is not faster than arrival, the job never catches up, however long it runs.
- Report backfill progress and live-tail freshness separately. A finished backfill with a lagging tail is still behind.

The slowest stage sets the pace; speeding up any other stage changes nothing. Find it before changing anything.

## Levers by stage

| Stage | Usually helps | Watch out for |
|---|---|---|
| Extract from a database | Keyset ranges on the primary key read in parallel; only needed columns; bulk export (`COPY ... TO STDOUT`, the engine's export tool); a replica or snapshot | Load on the production primary; `OFFSET` paging; inconsistent reads across ranges when a consistent snapshot is required |
| Extract from an API | Incremental pulls (`updated_since` with an overlap window), cursor pagination, bounded concurrency under the documented limit | Terms and quotas; missed records at page boundaries |
| Transfer | Compression, columnar files (Parquet), fewer and larger files, same region as the compute | Egress charges; thousands of tiny files |
| Transform | Columnar engines (Polars, DuckDB, Spark) or SQL in the warehouse where the data already is | Row-by-row Python, ORM objects per row, Python UDFs on hot paths |
| Load | The bulk path: PostgreSQL `COPY`, MySQL `LOAD DATA`, large ClickHouse inserts (`clickhouse.md`), warehouse bulk loads from files in object storage | Row-at-a-time inserts; per-row commits; streaming inserts billed per row |
| Load into a new table | Load first, then build indexes and constraints; swap the table in when complete | Doing this to a live table: it needs the user's go-ahead and a rollback |
| Publish | Rebuild only affected partitions; incremental models | Full refresh of large derived tables on every run |

- **Batch size:** too small wastes round trips and commits; too large holds locks and memory for long and makes each retry expensive. Measure two or three sizes.
- **Concurrency:** add workers while throughput rises; stop where the curve flattens or the target starts showing lock waits, CPU saturation or throttling. More workers past that point only add contention.
- **Move compute to the data.** Pulling a billion rows into a script to aggregate them is slower and costlier than one query in the warehouse.

## Correctness is the gate

A faster path that drops, duplicates or reorders data is a regression.

- **Idempotent writes.** Load into a staging table, then merge or upsert by the natural key, or replace whole partitions atomically. A rerun after a crash must not duplicate rows.
- **Manifest of work units.** For files: name, size, checksum, row count, status and run id. For ranges: bounds and status. The job skips completed units and retries failed ones; nothing is skipped silently.
- **Checkpoints** after each unit so a stopped job resumes where it left off.
- **Rejected rows** go to a quarantine table with the reason and are counted; they are never dropped quietly.
- **Incremental extracts by timestamp** need an overlap window (`updated_at > last_watermark - overlap`) plus deduplication, because of clock skew, rows sharing a timestamp and transactions that commit late. When completeness matters, use log-based change data capture instead of timestamps.
- **Reconcile** source and target per partition or day: row counts, distinct keys, sums of a measure column, minimum and maximum timestamps, and a hash comparison on a sample of rows.

## Benchmark variants, then codify

1. Pick a representative slice (one day, one partition, one file group), and record its source counts.
2. Run the current path and each variant (batch size, worker count, file grouping, warehouse SQL instead of client code) on the same slice under the same conditions, several times each; compare as in `../../ml-engineering/references/benchmarking-methodology.md`.
3. Keep only variants that pass reconciliation on the slice.
4. Codify the winner as the job, script or workflow that runs from now on, with its parameters in config.
5. Run it, then reconcile again on the full result.

## The accounting block

End every throughput task with numbers that add up, for example:

```text
Throughput result (run 2026-10-14T02:10Z, job orders_backfill v4)
Work units:      1,440 files discovered, 1,440 processed, 0 failed, 0 skipped
Rows:            source 812,400,118 = loaded 812,399,950 + quarantined 168
Derived table:   daily_orders rebuilt for 2024-01-01..2026-10-13 (1,017 partitions)
Freshness:       target max(event_time) 2026-10-14T02:05Z, live tail lag 6 min
Runtime:         3 h 12 min (was 19 h 40 min on the previous path)
Reconciliation:  counts, distinct order_id and sum(amount) match per day; sample hash check 10,000/10,000
Not verified:    late-arriving rows after 02:05Z (next incremental run)
```

## Guardrails

- Heavy reads on production sources, bulk loads into shared targets, index drops and table swaps need the user's permission, a time window and a rollback (`live-database-access.md`, `../../agent-safety/GUIDE.md`).
- Estimate warehouse compute, egress and storage costs before large runs (`../../cloud-infrastructure/references/cloud-cost.md`).
- Never delete raw or source data to make a backlog look smaller, and never mark a job complete before the manifest and the target agree.
- For financial, health, regulated or customer-facing data, keep the manifest, the reconciliation output and the ability to replay a unit.

## Checks (done when)

- [ ] Per-stage measurements identify the bottleneck; arrival and processing rates are both known.
- [ ] Writes are idempotent; a manifest and checkpoints make the job resumable; rejected rows are counted.
- [ ] The chosen variant beat the old path on the same slice by more than run-to-run spread, and passed reconciliation.
- [ ] The path is codified with parameters in config, and the accounting block reconciles for the full run.
- [ ] Backfill completion and live-tail freshness are reported separately.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Tuning the transform while the load is the bottleneck | Measure each stage first |
| More workers, same throughput, more lock waits | Find the knee; fix the contended resource |
| Duplicates after a retried batch | Staging plus merge, or atomic partition replace |
| Rows missed by a timestamp watermark | Overlap window and deduplication, or change data capture |
| "Done" while the tail grows | Report freshness separately |
| Faster job, quietly fewer rows | Reconciliation as a required gate |
