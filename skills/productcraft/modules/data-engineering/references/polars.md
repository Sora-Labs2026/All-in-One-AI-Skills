# Polars

Read this when code uses Polars, when a pandas pipeline is too slow or too memory-hungry on one machine, or when a dataset is larger than memory but a cluster would be overkill. Distributed options are in `dask-and-out-of-core.md` and `spark.md`.

## When to choose it

- **Good fit:** single-machine ETL and analysis from megabytes to hundreds of gigabytes; pipelines dominated by filters, joins, group-bys and window functions; reading many Parquet files; data larger than RAM through the streaming engine.
- **Poor fit:** tiny frames where pandas is already instant and the surrounding libraries (statsmodels, many plotting and ML APIs) expect pandas; row-by-row Python logic that cannot be expressed as expressions; multi-machine scale.
- Converting at the boundary is cheap: `pl.from_pandas(df)`, `df.to_pandas()` (zero-copy for many types through Arrow), `df.to_arrow()`.

## Versions

Polars reached 1.0 in July 2024 and releases often; check `python -c "import polars; print(polars.__version__)"`. Names that changed before or around 1.0 and still appear in old examples: `groupby` became `group_by`, `apply`/`map` on expressions became `map_elements`/`map_batches`, `melt` became `unpivot`, `pivot(columns=...)` became `pivot(on=...)`, and `collect(streaming=True)` gave way to `collect(engine="streaming")`. Read the changelog when upgrading across minor versions; behavior changes are announced there.

## Mental model

An **expression** (`pl.col("amount") * 1.2`, `pl.len()`) describes a computation; a **context** runs it: `select`, `with_columns`, `filter`, `group_by(...).agg(...)`. Expressions in one context run in parallel and must not depend on each other; chain another `with_columns` when one does.

**Lazy** queries (`pl.scan_parquet`, `pl.scan_csv`, `df.lazy()`) build a plan that the optimizer rewrites (projection and predicate pushdown into the file reader, common-subexpression elimination) and run on `.collect()`. Use lazy by default for files; `explain()` shows the optimized plan.

```python
import polars as pl

orders = (
    pl.scan_parquet("data/orders/*.parquet")
      .filter(pl.col("created_at") >= pl.datetime(2026, 1, 1, time_zone="UTC"))
      .with_columns(
          net=pl.col("amount") - pl.col("fee"),
          month=pl.col("created_at").dt.truncate("1mo"),
      )
      .group_by("customer_id", "month")
      .agg(
          orders=pl.len(),
          revenue=pl.col("net").sum(),
          largest=pl.col("net").max(),
      )
      .sort("customer_id", "month")
)
print(orders.explain())        # check that the filter and column selection reached the scan
result = orders.collect()
```

## Idioms

```python
# conditional column
df = df.with_columns(
    band=pl.when(pl.col("amount") < 10).then(pl.lit("small"))
           .when(pl.col("amount") < 100).then(pl.lit("medium"))
           .otherwise(pl.lit("large"))
)

# group statistic on every row (window), no join needed
df = df.with_columns(share=pl.col("amount") / pl.col("amount").sum().over("region"))

# validated join; coalesce the key columns explicitly
joined = orders.join(customers, on="customer_id", how="left", validate="m:1", coalesce=True)

# time-aligned join: latest quote at or before each trade, per symbol (both sides sorted by ts)
aligned = trades.sort("ts").join_asof(quotes.sort("ts"), on="ts", by="symbol", strategy="backward",
                                      tolerance="5m")

# rolling and calendar windows
daily = df.sort("ts").group_by_dynamic("ts", every="1d", group_by="sensor").agg(pl.col("value").mean())
```

- `pl.len()` counts rows; `pl.col(c).count()` counts non-null values.
- `group_by` does not preserve input order; pass `maintain_order=True` or sort afterwards when order matters (tests, reports).
- Selectors (`import polars.selectors as cs`; `cs.numeric()`, `cs.ends_with("_id")`) keep wide-table code short.

## Types, nulls and parsing

- Polars distinguishes **null** (missing, any type) from **NaN** (a floating-point value). `is_null`/`fill_null` and `is_nan`/`fill_nan` are different operations. `pl.from_pandas` turns pandas NaN into null by default (`nan_to_null=True`), but NaN produced later by arithmetic such as `0 / 0` stays NaN and is not caught by `is_null()`.
- `pl.col("x") == None` is not a null test; use `is_null()`.
- CSV schema inference looks at the first rows only (`infer_schema_length`, 100 by default). Pass `schema_overrides={"zip": pl.String, "amount": pl.Float64}` for columns that must not be guessed, or `infer_schema=False` to read everything as text and cast deliberately.
- Casting is strict by default and raises on bad values. `cast(..., strict=False)` turns failures into nulls silently: count nulls before and after, and report the difference.
- Parse dates with an explicit format: `pl.col("d").str.to_date("%d/%m/%Y")`. Time zones: `dt.replace_time_zone` declares the zone of naive values; `dt.convert_time_zone` converts aware values.
- `pl.Enum([...])` fixes a category set up front and is safer than `pl.Categorical` when frames are combined.

## Performance

- Stay inside expressions. `map_elements` calls Python per value, disables parallelism and is the most common cause of a slow Polars pipeline; almost every case has a native expression (`str`, `dt`, `list`, `struct` namespaces, `replace`, `when/then`).
- Scan, do not read: `scan_parquet` with filters reads only the needed row groups and columns. Hive-partitioned folders (`year=2026/month=03/`) are pruned automatically.
- Larger than memory: `lf.collect(engine="streaming")` processes in batches, and `lf.sink_parquet("out.parquet")` writes without materializing the result. Not every operation streams; operations that cannot fall back to in-memory execution.
- Write partitioned datasets for later pruning with `pl.PartitionByKey` or `write_parquet(..., partition_by=...)` (check which your version supports).
- Cloud storage: `scan_parquet("s3://bucket/path/*.parquet", storage_options={...})`; credentials come from the environment or the provider's standard chain, not from code.
- A GPU engine (`collect(engine="gpu")`) exists for NVIDIA hardware with the optional cuDF-based package; treat it as an optimization to measure, with CPU fallback.
- Threads: Polars uses all cores by default; inside a process pool or a busy server, cap with the `POLARS_MAX_THREADS` environment variable set before import.

## DuckDB as a companion

DuckDB is an in-process SQL engine that reads Parquet, CSV and Polars or pandas frames directly, and spills to disk for larger-than-memory work. It is often the quickest way to answer an exploratory question or run a SQL join on files:

```python
import duckdb
top = duckdb.sql("""
    SELECT customer_id, sum(amount) AS revenue
    FROM 'data/orders/*.parquet'
    WHERE created_at >= TIMESTAMP '2026-01-01'
    GROUP BY customer_id ORDER BY revenue DESC LIMIT 20
""").pl()     # to a Polars DataFrame
```

## Migrating from pandas

| pandas | Polars |
|---|---|
| `df["c"] = expr` | `df = df.with_columns(c=expr)` |
| `df[df.a > 0]` | `df.filter(pl.col("a") > 0)` |
| `df.groupby("k").agg(...)` | `df.group_by("k").agg(...)` |
| `df.groupby("k")["x"].transform("sum")` | `pl.col("x").sum().over("k")` |
| `df.merge(o, on="k", how="left", validate="m:1")` | `df.join(o, on="k", how="left", validate="m:1")` |
| `pd.merge_asof` | `join_asof` |
| Index-based alignment | No index: joins and sorts are explicit |
| `df.apply(f, axis=1)` | An expression; `map_elements` only as a last resort |

Port with a test: run both versions on the same input and compare with `polars.testing.assert_frame_equal` after converting, sorting and aligning types. Expect differences in null handling, group order and float summation order.

## Checks (done when)

- [ ] Polars version known; no pre-1.0 method names.
- [ ] Lazy plan inspected with `explain()` for large inputs; filters and projections reach the scan.
- [ ] Schemas set for columns that must not be inferred; non-strict casts accompanied by null counts.
- [ ] No `map_elements` on hot paths, or a measured reason for it.
- [ ] Results compared with an independent computation (DuckDB SQL or the old pandas code) on the same input.
