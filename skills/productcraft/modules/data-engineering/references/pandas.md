# pandas

Read this when code reads, cleans, joins, reshapes or aggregates tabular data with pandas, when pandas code is slow or memory-hungry, or when results look subtly wrong (row counts, types, missing values). For data that outgrows memory, see `polars.md` and `dask-and-out-of-core.md`; for Excel files, `../../documents/references/excel-xlsx.md`.

## Versions

Check `python -c "import pandas; print(pandas.__version__)"` and the lockfile before writing code. pandas 2.x (2023-2025) and 3.0 (released early 2026) differ in ways that change results:

- **Copy-on-Write** is the only behavior in 3.0 (opt-in in 2.x via `pd.options.mode.copy_on_write = True`). Any derived DataFrame or Series behaves as a copy, so chained assignment such as `df[df.a > 0]["b"] = 1` never modifies `df`. Assign in one step with `.loc`.
- **Strings** are inferred as a dedicated `str` dtype in 3.0 (backed by PyArrow when installed) instead of `object`. Code that checks `dtype == object` or relies on mixed Python objects in a text column needs updating.
- Deprecated APIs from 2.x are removed in 3.0. Run the test suite under the 2.x version with warnings turned into errors (`python -W error::FutureWarning -m pytest`) before upgrading.

Install `pyarrow` alongside pandas: it provides the fast CSV and Parquet readers and Arrow-backed types.

## Reading data so the types are right

```python
import pandas as pd

df = pd.read_csv(
    "orders.csv",
    dtype={"order_id": "int64", "customer_id": "string", "zip": "string"},  # IDs and codes stay text
    usecols=["order_id", "customer_id", "zip", "amount", "created_at"],
    na_values=["", "N/A", "-"], keep_default_na=False,                   # say exactly what means missing
    parse_dates=["created_at"], date_format="%Y-%m-%d %H:%M:%S",
    engine="pyarrow",                                                     # faster; drop it if an option is unsupported
)
```

- Profile an unfamiliar CSV first with `../scripts/csv_profile.py`; it reports delimiter, encoding, leading zeros, null tokens and ambiguous dates that decide these arguments.
- Identifiers, postcodes, phone numbers and account numbers are text. Reading them as numbers drops leading zeros and turns long IDs into floats.
- `keep_default_na=True` (the default) turns the strings `"NA"`, `"null"`, `"None"` and others into missing values, including a real person named "NA" or the country code for Namibia. Decide deliberately.
- Parse dates with an explicit `date_format` (or `format=` in `pd.to_datetime`). Without one, pandas infers a format from the first value, and day-first data can be silently read month-first.
- Prefer Parquet over CSV for anything you write and read again: types, nulls and time zones survive, and reading is much faster (`storage-formats-and-zarr.md`).
- For files larger than memory, read in chunks (`chunksize=`) and aggregate each chunk, or switch tools.

## Dtypes

| Data | Use | Avoid |
|---|---|---|
| Integers with missing values | `"Int64"` (nullable) | `float64`, which silently turns IDs into `1.0` and loses precision above 2^53 |
| Booleans with missing values | `"boolean"` | `object` columns of `True`/`False`/`None` |
| Text | `"string"` (2.x) or the default `str` (3.0) | `object` |
| Low-cardinality labels | `"category"`, after checking that categories match across frames you combine | `category` for high-cardinality or ever-growing values |
| Instants | `datetime64[ns, UTC]` (tz-aware) | Naive timestamps whose zone nobody remembers |
| Money | Integer minor units, or `decimal.Decimal` in `object` when exact decimal arithmetic matters | `float64` sums for reconciliation |

`df.dtypes`, `df.info(memory_usage="deep")` and `df.isna().sum()` are the first three things to print after loading. `dtype_backend="pyarrow"` on readers gives Arrow-backed columns throughout; check that downstream libraries accept them.

## Selecting and assigning

```python
# one-step conditional assignment (works the same before and after Copy-on-Write)
df.loc[df["status"] == "refunded", "amount"] = 0

# derive columns without mutating the input; returns a new frame
out = df.assign(
    net=lambda d: d["amount"] - d["fee"],
    month=lambda d: d["created_at"].dt.to_period("M"),
)

# vectorized conditionals instead of apply(axis=1)
import numpy as np
df["band"] = np.select(
    [df["amount"] < 10, df["amount"] < 100],
    ["small", "medium"],
    default="large",
)
```

- `iterrows`, `itertuples` and `apply(axis=1)` run Python per row and are typically 10-1000 times slower than column operations. Use arithmetic on columns, `np.where`/`np.select`, `.str` and `.dt` accessors, `.map(dict)` for lookups, and `merge` instead of lookups in a loop.
- `inplace=True` rarely saves memory and does not chain; prefer reassignment.

## Joins that do not silently change row counts

```python
before = len(orders)
merged = orders.merge(
    customers, on="customer_id", how="left",
    validate="many_to_one",   # raises if customer_id repeats in customers
    indicator=True,
)
assert len(merged) == before, "join changed the row count"
unmatched = (merged["_merge"] == "left_only").sum()
```

- Key dtypes must match exactly. An `int64` key joined to a `string` key raises or matches nothing; `"00123"` and `123` never match. Normalize keys (type, case, whitespace) on both sides first.
- Duplicate keys on both sides multiply rows. `validate=` turns that into an error instead of a wrong total.
- Report unmatched counts in both directions; they are often the most important finding.
- For "the latest value at or before this time", use `pd.merge_asof(left, right, on="ts", by="id", direction="backward", tolerance=pd.Timedelta("1D"))`, with both sides sorted by `ts`.

## Grouping and reshaping

```python
summary = (
    df.groupby(["region", "channel"], observed=True, dropna=False)
      .agg(orders=("order_id", "nunique"), revenue=("amount", "sum"), avg=("amount", "mean"))
      .reset_index()
)
df["share_of_region"] = df["amount"] / df.groupby("region")["amount"].transform("sum")
```

- Pass `observed=True` for categorical keys (otherwise every combination of categories appears, empty ones included; the default changes across versions, so set it explicitly) and `dropna=False` if rows with a missing key must not disappear.
- `size()` counts rows, `count()` counts non-null values per column.
- `pivot` fails on duplicate index-column pairs; `pivot_table` aggregates them (with `aggfunc="mean"` by default, which may not be what you want: set it). `melt` goes from wide to long, which is what plotting and modeling libraries usually expect.

## Time series

- Make timestamps tz-aware once (`dt.tz_localize("Europe/Berlin")` for local wall-clock data, then `dt.tz_convert("UTC")`), and decide how nonexistent and ambiguous daylight-saving times are handled (`nonexistent=`, `ambiguous=`).
- `resample("D")` needs a `DatetimeIndex` or `on=`; state `label` and `closed` for weekly or monthly bins, because defaults differ by frequency. Missing periods appear as NaN after `mean` and as 0 after `sum`; know which you want.
- Time-based rolling windows (`rolling("7D", on="ts")`) handle irregular sampling; count-based ones (`rolling(7)`) do not.

## Missing values

- `NaN` (float), `NaT` (datetime) and `pd.NA` (nullable dtypes) behave differently in comparisons: `pd.NA == 1` is `NA`, not `False`. Use `isna()`.
- During exploration, measure and describe missingness; do not fill it. Filling with the mean, median or mode changes distributions and correlations and should be a documented modeling decision (`../../ml-engineering/GUIDE.md`).
- `dropna()` without `subset=` drops rows missing any column, which can remove most of a wide table. Count before and after.

## Numbers

- Floating-point sums are not exact; compare with `np.isclose` or round at the reporting edge, and reconcile money in integer units.
- `Series.round()` rounds half to even (NumPy behavior): `round(2.5)` is 2. Financial rounding rules usually need `decimal` with `ROUND_HALF_UP`.

## Memory and speed

- Measure: `df.memory_usage(deep=True).sum() / 2**20` (MiB). Text columns dominate; Arrow-backed strings and categories cut them sharply.
- Read only needed columns and rows; downcast numeric types where ranges allow (`pd.to_numeric(s, downcast="integer")`).
- Profile slow code with `%timeit` or `cProfile` before rewriting it; the cost is often a single `apply` or a join on mismatched types.
- When data is several times larger than RAM, or a pipeline is dominated by joins and group-bys, Polars, DuckDB or Dask are usually better choices than tuning pandas further.

## Testing transformations

- `pd.testing.assert_frame_equal(result, expected, check_dtype=True)` in unit tests with small, hand-built frames that include nulls, duplicates and edge dates.
- Validate inputs and outputs at pipeline boundaries with a schema library such as Pandera (column types, ranges, uniqueness, nullability), so bad data fails loudly instead of flowing on.
- Log row counts after every filter and join; a silent drop of 5% of rows is the most common pandas bug in practice.

## Checks (done when)

- [ ] pandas version known; code avoids chained assignment and relies on no `object` dtype assumptions.
- [ ] Types set explicitly on read for IDs, dates and nullable integers; null tokens decided deliberately.
- [ ] Every join validated (`validate=`, row counts, unmatched counts reported).
- [ ] Missing values measured and any filling documented as a decision.
- [ ] Results cross-checked: one total or count computed a second, independent way (SQL, a spreadsheet, a manual subset).
