# Apache Spark

Read this when code uses PySpark, Spark SQL or Scala Spark, when a Spark job is slow, spills, skews or fails with memory errors, or when designing batch or streaming pipelines on a lakehouse. For data that fits on one machine, `polars.md` or `dask-and-out-of-core.md` is usually faster and cheaper.

## Versions and platforms

Spark 3.5 is still widely deployed; Spark 4.0 (2025) changed defaults that alter results:

- **ANSI SQL mode is on by default in 4.0.** Invalid casts, integer overflow and division by zero raise errors instead of returning NULL or wrapping. Jobs that "worked" on 3.x may now fail, which usually reveals real data problems; fix the data or use `try_cast`, `try_divide` deliberately.
- Spark Connect (a thin client talking to a remote Spark server) is a first-class way to run PySpark; some low-level APIs (`sparkContext`, RDDs) are unavailable through it.
- 4.0 requires Java 17 or 21 and Scala 2.13, and adds a `VARIANT` type for semi-structured data.

Check `spark.version`, and the platform's runtime notes (Databricks Runtime, Amazon EMR, Google Dataproc, Microsoft Fabric), which bundle their own defaults, connectors and table-format versions.

## Ground rules

- Use DataFrames and Spark SQL. RDDs bypass the optimizer and Tungsten's memory format; reserve them for the rare case no DataFrame API covers.
- Declare schemas for production reads. `inferSchema` on CSV or JSON reads the data an extra time and guesses differently as files change.
- Transformations are lazy; actions (`count`, `collect`, `write`, `show`) run the plan. Every action without caching recomputes from the source.
- Never `collect()` or `toPandas()` an unbounded result: it pulls everything into the driver. Aggregate or `limit` first; `spark.driver.maxResultSize` is a safety net, not a plan.

```python
from pyspark.sql import SparkSession, functions as F, types as T

spark = SparkSession.builder.appName("daily-revenue").getOrCreate()

schema = T.StructType([
    T.StructField("order_id", T.LongType(), False),
    T.StructField("customer_id", T.StringType(), False),
    T.StructField("amount", T.DecimalType(18, 2), True),
    T.StructField("created_at", T.TimestampType(), False),
])

orders = spark.read.schema(schema).parquet("s3://lake/raw/orders/")
daily = (
    orders.where(F.col("created_at") >= F.lit("2026-01-01").cast("timestamp"))
          .groupBy(F.to_date("created_at").alias("day"))
          .agg(F.sum("amount").alias("revenue"), F.countDistinct("customer_id").alias("customers"))
)
daily.explain(mode="formatted")   # check pushed filters and the join and aggregate strategy
```

## Reading what Spark did

- `df.explain(mode="formatted")` shows the physical plan: look for `PushedFilters` on the scan, `BroadcastHashJoin` versus `SortMergeJoin`, and `Exchange` nodes (shuffles).
- The Spark UI is the profiler. Per stage, compare the **median and maximum task time**: a maximum far above the median is skew. Check **shuffle read and write** sizes, **spill (memory and disk)** and **GC time**. The SQL tab shows the plan that actually ran, after adaptive changes.
- One slow stage with a few long tasks is nearly always skew or one huge input file; many short tasks with overhead dominating means too many partitions.

## Partitions

- **Input:** file splits follow `spark.sql.files.maxPartitionBytes` (128 MB by default). Thousands of tiny files create thousands of tiny tasks; compact them.
- **Shuffles:** `spark.sql.shuffle.partitions` defaults to 200. Adaptive Query Execution (AQE, on by default since 3.2) coalesces small shuffle partitions after the fact, so set the initial number generously high for large jobs and let AQE reduce it. Target roughly 100-200 MB per shuffle partition.
- **Parallelism:** two to four tasks per executor core keep cores busy without excessive overhead.
- `repartition(n, col)` shuffles to balance or co-locate data; `coalesce(n)` merges partitions without a full shuffle, which is cheaper but can leave uneven, oversized partitions.
- **Writes:** `partitionBy` on low-cardinality columns that queries filter on (date, region). Partitioning by a high-cardinality column (user id) creates millions of tiny files. Control file counts with a `repartition` on the partition columns before writing, or with the table format's compaction.

## Joins and skew

- Spark broadcasts the smaller side automatically below `spark.sql.autoBroadcastJoinThreshold` (10 MB by default) and AQE can switch to a broadcast at runtime. An explicit `F.broadcast(dim)` hint helps when statistics are missing; keep broadcast tables small enough for driver and executor memory (tens to a few hundred MB at most).
- **Skew:** AQE splits skewed partitions in sort-merge joins automatically (`spark.sql.adaptive.skewJoin.enabled`, default on). If one key still dominates, look at that key first: NULL or placeholder keys (`''`, `0`, `'unknown'`) often account for the hot spot and can be filtered or handled separately. Salting (appending a random suffix to the hot key on the large side and replicating the small side across suffixes) is the manual last resort.
- Filter and project before joins; push filters into the scan by filtering on partition columns and columns with Parquet statistics.

## Caching

- Cache only DataFrames reused by several actions, after the expensive part of their lineage. `cache()` is lazy: the first action fills it. Check the Storage tab for the fraction actually cached, and `unpersist()` when done.
- For very long lineages (iterative algorithms), `checkpoint()` to reliable storage truncates the plan.
- Caching a DataFrame that is read once only adds cost.

## Python UDFs

- Built-in functions in `pyspark.sql.functions` run in the JVM and are optimizable; prefer them.
- Row-at-a-time Python UDFs serialize every row to a Python worker and back. When Python is unavoidable, use vectorized pandas UDFs (`@F.pandas_udf`) or `mapInPandas` / `applyInPandas`, which move Arrow batches, or Arrow-optimized Python UDFs (`useArrow=True`, 3.5+).
- A UDF is a black box to the optimizer: filters do not push through it.

## Writing reliably

- Table formats (Delta Lake, Apache Iceberg, Apache Hudi) add ACID commits, schema enforcement and evolution, time travel and compaction on object storage. Prefer them over raw Parquet folders for tables others read while you write.
- Make batch writes idempotent: overwrite whole partitions (`spark.sql.sources.partitionOverwriteMode=dynamic` for raw Parquet, or `MERGE` / `replaceWhere` in table formats) so a rerun after failure does not duplicate data.
- Writes, `MERGE` and `VACUUM` / snapshot expiry on shared production tables need the user's approval; expiring snapshots removes the ability to time travel back.

## Structured Streaming

- Each query needs its own durable **checkpoint location**; never share it between queries or delete it to "fix" a job, which loses progress and can duplicate or drop data.
- **Watermarks** (`withWatermark("event_time", "10 minutes")`) bound how late data may arrive and how much state aggregations and joins keep. Without them, state grows forever.
- Output modes: append for finalized rows, update for changing aggregates, complete for small result tables.
- End-to-end exactly-once needs a replayable source, the checkpoint, and an idempotent or transactional sink. With `foreachBatch`, use the `batch_id` to make writes idempotent.
- `trigger(availableNow=True)` processes everything available and stops: incremental batch processing with streaming bookkeeping.
- Monitor `query.lastProgress` (input rows per second versus processed rows per second, batch duration, state size).

## Testing

- Unit-test transformations as functions from DataFrame to DataFrame with a local `SparkSession` (`master("local[2]")`) and tiny hand-built inputs including nulls and duplicate keys. `pyspark.testing.assertDataFrameEqual` (3.5+) compares results and schemas.
- Test on a realistic sample before the full run; record input size, run time and cost.

## Cost and clusters

Executors, autoscaling and spot instances are infrastructure decisions with a bill attached. Propose cluster sizes with an estimate and get approval before creating or resizing clusters (`../../cloud-infrastructure/GUIDE.md`). Turn on auto-termination for interactive clusters.

## Checks (done when)

- [ ] Spark version and platform defaults known (especially ANSI mode).
- [ ] Explicit schemas on production reads; no unbounded `collect` or `toPandas`.
- [ ] Physical plan checked for pushed filters, join strategies and the number of shuffles.
- [ ] Spark UI checked for skew, spill and GC on a realistic run; partition sizes in a sensible range; output file sizes reasonable.
- [ ] Writes idempotent on rerun; streaming queries have their own checkpoints and watermarks.
- [ ] Output reconciled with the input (row counts, sums of key measures) and with a small independent computation.
