# Dask and other ways past the memory limit

Read this when data does not fit in memory, when a single-machine job needs more cores, when array computations need chunking, or when code already uses Dask or Vaex. Spark is in `spark.md`; storage formats that make all of these fast are in `storage-formats-and-zarr.md`.

## Pick the smallest tool that works

| Situation | First choice | Why |
|---|---|---|
| Fits in memory (with room for 2-5x working copies) | pandas or Polars | Simplest; no scheduler to debug |
| Larger than memory, one machine, tabular | Polars streaming or DuckDB | Optimized engines, spill to disk, no cluster |
| Python code or pandas APIs to parallelize, one machine or a few | Dask DataFrame or `dask.delayed` | Familiar APIs, scales from a laptop to a cluster |
| N-dimensional arrays larger than memory (climate grids, imaging stacks) | Dask Array with Xarray and Zarr | Chunked, lazy, parallel I/O |
| Many terabytes, shared cluster, SQL users, existing lakehouse | Spark | Mature distributed SQL, table formats, fault tolerance |

Before scaling out, try the cheap wins: read only needed columns, switch CSV to Parquet, fix dtypes, push work into SQL, or sample for development. These often remove the need for a cluster.

## Dask essentials

**Versions.** Dask releases on a calendar version scheme (for example `2025.x`). Since 2024 Dask DataFrame uses a query optimizer (originally the `dask-expr` package) by default, and the legacy implementation has since been removed; old examples that touch internals may not apply. Check `dask.__version__` and keep `dask`, `distributed` and any plugins at matching versions.

**Collections:** `dask.dataframe` (partitioned pandas frames), `dask.array` (chunked NumPy), `dask.bag` (sequences of Python objects, for messy semi-structured input), `dask.delayed` (lazy function calls building a custom task graph) and futures from `distributed` (eager, real-time task submission).

**Schedulers:**
- Threads (default for arrays and dataframes) work well when the work releases the GIL (NumPy, pandas, Arrow).
- Processes help pure-Python, GIL-bound work (text parsing, Python objects), at the cost of serialization.
- `dask.config.set(scheduler="synchronous")` runs everything in one thread so tracebacks and `pdb` work. Debug there first.
- `from dask.distributed import Client; client = Client()` starts a local cluster with a dashboard (the link is in `client.dashboard_link`), and works for one machine too. It adds memory management, spilling and diagnostics.

```python
import dask
import dask.dataframe as dd

ddf = dd.read_parquet(
    "data/events/",                      # a directory of Parquet files
    columns=["user_id", "ts", "kind", "value"],
    filters=[("ts", ">=", "2026-01-01")],  # row-group pruning
)
daily = ddf.assign(day=ddf.ts.dt.floor("D")).groupby(["day", "kind"]).value.sum()
users = ddf.user_id.nunique()

daily_result, users_result = dask.compute(daily, users)   # one pass over the data for both
```

## Partitions and chunks

- Aim for partitions of roughly 100 MB in memory and tasks that each take at least around 100 ms. Every task has scheduling overhead (on the order of a millisecond), so a million tiny tasks spend more time scheduling than computing.
- Too-large partitions run out of worker memory: a worker typically holds several partitions per thread at once, plus intermediate copies.
- `ddf.npartitions` and `ddf.map_partitions(len).compute()` show the layout; `ddf.repartition(partition_size="100MB")` evens it out after heavy filtering.
- Arrays: choose chunks that match how you read (whole images, whole time series) and that are large enough (tens to hundreds of MB). `chunks="auto"` is a reasonable default; rechunking a large array is expensive, so get it right at load time, and align with the chunks of the Zarr or HDF5 file underneath.

## Idioms and pitfalls

- **Load with Dask, not before it.** `dd.from_pandas(pd.read_csv(big))` first loads everything into one process; use `dd.read_csv` or `dd.read_parquet` so each worker reads its own piece.
- **Compute once.** Calling `.compute()` inside a loop re-reads and recomputes the inputs every time. Build all results lazily and pass them together to `dask.compute(...)`.
- **Persist what is reused.** `ddf = ddf.persist()` keeps an expensive intermediate in distributed memory for several later computations; release it when done.
- **`len(ddf)`, `ddf.shape[0].compute()` and `head()` cost real work.** `head()` reads only the first partition by default, which may be empty after a filter (`npartitions=-1` searches all).
- **Shuffles are expensive.** `set_index`, `sort_values`, joins on non-index columns and `groupby().apply()` move data between workers. Prefer group-by aggregations with built-in reductions; set an index only when many later joins or lookups use it, and do it once.
- **`map_partitions(func, meta=...)`** applies pandas code to each partition. Give `meta` (an empty frame with the output schema) so Dask does not run `func` on fake data to guess it.
- **Large objects in closures** are serialized into every task. Scatter them once (`client.scatter(obj, broadcast=True)`) or load them inside the task.
- **Unsupported pandas APIs** raise or behave differently (row positions, `iloc` on rows, some reshape operations). Keep Dask code to operations that are naturally partition-wise or tree reductions.

## Reading the dashboard

- **Task stream** shows what each thread is doing over time: long white gaps mean scheduling or communication overhead; red bars are data transfer between workers.
- **Worker memory** shows managed, unmanaged and spilled memory. Steady growth to the limit followed by pauses and restarts means partitions are too big or too much is persisted.
- Memory thresholds (`distributed.worker.memory.target`, `spill`, `pause`, `terminate`) control when workers spill to disk, stop accepting work and restart. Change them only with evidence.

## Clusters

- Local: `LocalCluster(n_workers=4, threads_per_worker=2, memory_limit="8GB")`.
- HPC schedulers (Slurm, PBS): the `dask-jobqueue` package submits workers as batch jobs.
- Kubernetes and cloud: Dask's Kubernetes operator or a managed service. Provisioning cloud workers costs money and touches shared infrastructure: plan and ask first, following `../../cloud-infrastructure/GUIDE.md`.

## Vaex

Vaex memory-maps HDF5 and Arrow files, evaluates virtual columns lazily and computes binned statistics over billions of rows very quickly. Its development has been quiet for a long time, with releases lagging new Python and NumPy versions, so check recent release activity and compatibility with the project's Python version before adopting it. For new work, Polars streaming or DuckDB cover the same ground with active maintenance. For existing Vaex code: keep it pinned, test it under the Python version in use, and when migrating, export to Parquet (`df.export_parquet(...)`) and port expressions one by one with a comparison test.

## DuckDB for larger-than-memory SQL

DuckDB runs in-process, reads Parquet and CSV in place (including globs and hive partitions), and spills to a temporary directory when queries exceed memory. Set limits on shared machines:

```python
import duckdb
con = duckdb.connect()
con.execute("SET memory_limit = '8GB'; SET threads = 4; SET temp_directory = '/tmp/duck_spill'")
con.execute("COPY (SELECT kind, date_trunc('day', ts) AS day, sum(value) AS total "
            "FROM 'data/events/*.parquet' GROUP BY ALL) TO 'daily.parquet' (FORMAT parquet)")
```

## Checks (done when)

- [ ] The choice of tool is justified by data size and workload, and simpler options were tried first.
- [ ] Partition or chunk sizes checked (count, size per partition) and aligned with the storage layout.
- [ ] No `.compute()` in loops; reused intermediates persisted and released.
- [ ] A small run on a sample matches a pandas or SQL reference result exactly (or within a stated tolerance).
- [ ] Peak memory and run time recorded from the dashboard or system metrics; no cloud resources created without approval.
