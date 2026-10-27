# Storage formats, Parquet and Zarr

Read this when choosing how to store or exchange data, when reading a file format you have not seen in this project, when Parquet datasets are slow or inconsistent, or when working with chunked N-dimensional arrays in Zarr, HDF5 or NetCDF. Spreadsheets are in `../../documents/references/excel-xlsx.md`; domain formats (sequencing, imaging, spectra) in `../../life-sciences/GUIDE.md`.

## Choosing a format

| Format | Strengths | Weaknesses | Use for |
|---|---|---|---|
| CSV / TSV | Universal, human-readable | No types, no nulls, encoding and delimiter ambiguity, slow | Exchange with people and legacy tools |
| JSON Lines | Nested records, append-friendly | Verbose, slow to scan, types loose | Logs, API dumps, semi-structured events |
| Parquet | Columnar, typed, compressed, statistics for skipping | Not appendable in place; small files hurt | Analytical tables of any size |
| Arrow IPC (Feather v2) | Very fast, memory-mappable, zero-copy to Arrow tools | Larger than Parquet, less universal | Intermediate files between steps, caches |
| Avro | Row-based with embedded schema and evolution rules | Poor for column scans | Streaming messages, Kafka payloads |
| HDF5 | Mature N-D arrays with hierarchy and attributes | One writer at a time, awkward on object storage | Local scientific arrays, instrument output |
| NetCDF-4 | HDF5 plus climate and forecast (CF) conventions | Same as HDF5 | Gridded geoscience data |
| Zarr | Chunked N-D arrays, each chunk a separate object, parallel and cloud-native | Many objects; needs a chunking plan | Large arrays on object storage, parallel writes |
| SQLite / DuckDB file | Queryable single file with SQL | Concurrent writers limited | Small apps, portable analytical bundles |

## CSV you hand to someone else

UTF-8, a header row, one delimiter, standard quoting (RFC 4180 style), ISO 8601 dates and timestamps with offsets, `.` as the decimal mark, no thousands separators or currency symbols, and a documented null representation. Include a short data dictionary (column, type, unit, meaning). Run `../scripts/csv_profile.py` on what you produce as well as what you receive. When the recipient opens files in a spreadsheet, see the formula-injection guard in `../../documents/references/excel-xlsx.md`.

## Parquet

- **Layout:** a file holds row groups; each row group holds one column chunk per column, divided into pages, with min, max and null-count statistics. Readers skip row groups whose statistics cannot match a filter, and read only requested columns.
- **Row groups** of roughly 64 MB to 1 GB (compressed) balance skipping against overhead; writers default to sensible values. Sorting by a commonly filtered column before writing makes statistics far more selective.
- **Compression:** Zstandard gives good ratio and speed; Snappy is the long-standing default in many writers. Dictionary encoding happens automatically for low-cardinality columns.
- **Datasets:** many files in a directory, often hive-partitioned (`year=2026/month=03/part-0.parquet`). Partition only by low-cardinality columns that queries filter on. Aim for files of tens to hundreds of MB; thousands of kilobyte-sized files make every engine slow.
- **Schema consistency:** every file in a dataset should share column names and types. A column that is `int64` in one file and `double` or `string` in another breaks readers or forces casts; enforce a schema at write time.
- **Types to watch:** timestamps carry a unit (ms, us, ns) and an "adjusted to UTC" flag; the legacy `INT96` timestamp from older Hive and Spark writers is deprecated. Decimals keep exact precision; use them for money. Unsigned integers and nanosecond timestamps are not supported by every reader.
- **Inspect without loading:**

  ```python
  import pyarrow.parquet as pq
  meta = pq.ParquetFile("orders.parquet").metadata
  print(meta.num_rows, meta.num_row_groups, meta.schema)
  print(meta.row_group(0).column(0).statistics)
  ```
- Table formats (Delta Lake, Apache Iceberg) layer transactions, schema evolution and compaction over Parquet; see `spark.md`.

## Zarr

Zarr stores an N-dimensional array as a grid of chunks, each compressed and saved as its own object, plus JSON metadata. Many processes can read and write different chunks at once, which makes it the usual choice for large arrays on object storage, often through Xarray and Dask.

**Versions.** zarr-python 3.0 (January 2025) implements the Zarr v3 format by default, adds sharding and an asynchronous core, and changes the API and store classes from 2.x; it requires Python 3.11 or newer. It still reads and writes the v2 format (`zarr_format=2`), which some other tools only understand. Check `zarr.__version__`, and check the format of existing stores before writing to them.

```python
import numpy as np
import zarr

z = zarr.create_array(
    store="data/temperature.zarr",
    shape=(3650, 720, 1440),            # time, lat, lon
    chunks=(30, 180, 360),              # about 7.8 MB per float32 chunk
    shards=(90, 360, 720),              # optional: 12 chunks per object; a multiple of the chunk shape
    dtype="float32",
    fill_value=np.nan,
    dimension_names=("time", "lat", "lon"),
)
z[0:30] = np.random.default_rng(0).random((30, 720, 1440), dtype="float32")
r = zarr.open_array("data/temperature.zarr", mode="r")   # read-only handle
print(r.info)
```

**Chunking decides performance.**
- Match chunk shape to the dominant read pattern: whole maps per time step want chunks spanning lat and lon; long time series at points want chunks long in time. Mixed access needs a compromise, or two copies with different chunking.
- Keep each chunk at least about 1 MB uncompressed; on object storage, where every chunk is a request, tens of MB is better. Very large chunks force reading far more than needed.
- **Sharding** (v3) stores many small chunks inside one object (a shard), so you can keep fine-grained chunks for access without millions of objects. A shard is the unit of writing: concurrent writers must not share a shard.
- **Parallel writes** are safe when each writer writes whole chunks (or whole shards) that no other writer touches. Writes that cover part of a chunk read, modify and rewrite it; two writers doing that to the same chunk lose data. Align regions to chunk boundaries (Xarray `to_zarr(region=...)` enforces alignment).

**Codecs.** The default compression is reasonable; Blosc with Zstandard and byte or bit shuffle usually compresses numeric data well. Measure ratio and read speed on a sample of the real data before tuning.

**Stores.** Local directories, ZIP files (read-mostly), memory, and object storage through fsspec (`s3://`, `gs://`, `az://`) with credentials from the environment or the provider's standard chain. Listing many keys on object storage is slow; consolidated metadata (one document describing all arrays in a hierarchy) lets readers open a group with one request, and Xarray writes it by default.

**With Xarray and Dask.**

```python
import xarray as xr
ds = xr.open_zarr("s3://bucket/climate.zarr", chunks={})   # lazy, Dask chunks follow the Zarr chunks
monthly = ds["t2m"].resample(time="1MS").mean()
monthly.to_dataset().to_zarr("monthly.zarr", mode="w")
```

Keep Dask chunks equal to, or whole multiples of, the Zarr chunks; misaligned chunks force reads of overlapping chunks and break safe parallel writes.

## HDF5 and NetCDF

- Read with `h5py` (raw HDF5) or Xarray (`xr.open_dataset("file.nc")`); `xr.open_mfdataset` combines many files lazily with Dask.
- HDF5 files allow one writer at a time (SWMR mode allows one writer with concurrent readers); concurrent writers need parallel HDF5 with MPI. A crash during writing can corrupt the file; write to a temporary name and rename.
- Chunking and compression are set per dataset at creation, with the same trade-offs as Zarr.
- NetCDF files following the CF conventions carry units, calendars, coordinates and fill values in attributes. Read them before computing: scale factors and offsets, `_FillValue`, and non-standard calendars (360-day, no-leap) are common sources of wrong numbers. Xarray decodes them by default; check the result.
- On object storage, reading HDF5 or NetCDF directly is slow; converting to Zarr, or using a reference layer that maps HDF5 chunks to byte ranges, works better for repeated access.

## Verification after converting or writing

- Row counts (or array shapes) equal; column names, types and units preserved.
- Aggregates match within a stated tolerance: sums, min and max, null counts per column, a checksum over a sorted key column.
- A handful of individual records or array slices compared field by field.
- The file opens in a second, independent reader (for example DuckDB for Parquet, Xarray for Zarr).

## Checks (done when)

- [ ] Format chosen for how the data will be read, by whom and where.
- [ ] Parquet datasets have consistent schemas, sensible file and row-group sizes, and partition columns that match query filters.
- [ ] Zarr chunk shapes match access patterns, sizes measured, and parallel writes aligned to chunk or shard boundaries.
- [ ] Conversions verified with counts, aggregates and a second reader.
