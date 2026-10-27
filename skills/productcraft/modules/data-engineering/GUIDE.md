# Data Engineering

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Get correct numbers out of data and keep them correct: SQL that returns the right rows and runs fast on PostgreSQL, MySQL and SQL Server; safe, read-only access to real databases; dataframes from pandas and Polars up to Dask and Spark; storage formats from CSV and Parquet to Zarr; exploratory analysis and data-quality checks; charts and publication figures; geospatial and graph data; MATLAB and Octave interop; Kaggle workflows; and public economic, filing and market-data APIs with their terms and limits. Each topic has one focused reference. Read only the ones the task touches.

This module covers data work up to understanding, validating, transforming and visualizing data. Statistical modeling, machine learning and forecasting live in `../ml-engineering/GUIDE.md`. Schema design and migrations stay in `../engineering-practices/references/data-and-migrations.md`; charts inside a product's interface in `../data-and-product-surfaces.md`.

## When to activate

- A query is wrong, slow or about to be written for reporting, analytics or a data pipeline; someone proposes an index; a database is misbehaving (locks, bloat, replication lag, connection limits).
- The agent is about to connect to a database that holds real data.
- Code reads, cleans, joins, reshapes or aggregates tabular data with pandas, Polars, DuckDB, Dask or Spark, or the data has outgrown memory.
- A dataset arrives and the user asks what is in it, whether it is usable, or what it shows; a pipeline needs data-quality checks.
- Charts for analysis or reports, or figures for a paper, thesis or poster.
- Locations, maps, rasters or coordinate systems; networks of entities; `.m` or `.mat` files; Kaggle datasets, notebooks or competitions.
- Pulling official statistics (FRED, BLS, BEA, Census, Treasury, OFR, World Bank, IMF, OECD, Eurostat, ECB, Data Commons), SEC filings or market data.
- **Not for** model training, statistical inference or forecasting (`../ml-engineering/GUIDE.md`), schema migrations (`../engineering-practices/`), spreadsheets as deliverables (`../documents/GUIDE.md`), or dashboards and tables in a product UI (`../data-and-product-surfaces.md`).

## Ground rules

1. **Correct before fast, and both proven.** Check row counts, keys and a total computed a second, independent way before tuning anything. A fast query or pipeline that returns wrong numbers is a regression.
2. **Look at the data before trusting it.** Profile first (`scripts/csv_profile.py`, metadata reads, size estimates), then decide types, null tokens, keys and the tool. Never assume a column's meaning, unit or grain; ask the owner.
3. **Real data is read-only and private by default.** Use a copy or replica where possible, a read-only account enforced by privileges, bounded queries and timeouts. Never paste personal data into the conversation, reports or commits; aggregate instead. Follow `references/live-database-access.md`.
4. **Hands off production and shared systems.** No writes, DDL, `EXPLAIN ANALYZE` of data-changing statements, configuration changes, session kills, failovers, cluster creation or cloud spend without explicit permission. Prepare the exact commands and hand them over (`../engineering-practices/GUIDE.md`, ground rule 6; `../agent-safety/GUIDE.md`).
5. **Check versions.** pandas 3, Polars 1.x, Spark 4, zarr-python 3, GeoPandas 1 and others changed defaults that alter results. Read the installed version from the environment or lockfile and say which version an answer assumes.
6. **Keys and tokens by name only.** API keys, database passwords and Kaggle tokens live in environment variables or the client's credential files, set by the user (`../agent-safety/references/secrets.md`, `../agent-safety/references/guided-setup.md`).
7. **Respect terms and limits.** Every external source has a license, attribution rule and rate limit. Read them, throttle, cache, and record them next to the data. No scraping where an API exists.
8. **Every number comes from code that ran.** Never estimate, round up or invent figures, citations, releases or revisions. Mark anything not computed or not verified as `NOT VERIFIED` with the reason.
9. **No advice dressed as analysis.** Financial and economic work produces data and analysis, never investment, trading or policy recommendations; backtests are labeled hypothetical.

## Pick the references

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Writing or reviewing SQL; slow queries; plans; index design | `references/sql-query-tuning.md` | Result checked against a simple version; NULL, join-cardinality and window-frame traps reviewed; before and after plans on realistic data |
| PostgreSQL behavior: pooling, settings, vacuum and bloat, locks, `jsonb`, extensions, partitions, replication, backups | `references/postgresql.md` | Version and settings read from the server; diagnosis cites views and numbers; nothing blocking or destructive run without permission |
| MySQL, MariaDB or SQL Server behavior: plans, collations, deadlocks, Query Store, parameter sniffing, replication | `references/mysql-and-sql-server.md` | Engine, version and compatibility level known; evidence named for each diagnosis; changes measured and reversible |
| Connecting to any database with real data | `references/live-database-access.md` | Environment named by the user; read-only by privileges; queries bounded; no credentials or personal data in outputs |
| pandas code: reading, types, joins, group-bys, time series, memory | `references/pandas.md` | Types set on read; joins validated with row counts; missing values measured; one total cross-checked |
| Polars, DuckDB, or replacing slow pandas on one machine | `references/polars.md` | Lazy plan inspected; schemas pinned; no Python UDFs on hot paths; results compared with a reference |
| Data larger than memory; Dask; Vaex; choosing between single-node and distributed | `references/dask-and-out-of-core.md` | Simplest adequate tool chosen; partitions sized; no `compute()` in loops; sample run matches a reference |
| PySpark or Spark SQL jobs, skew, spills, streaming | `references/spark.md` | Version defaults known; plan and UI checked for skew and spill; writes idempotent; output reconciled with input |
| Choosing or reading formats; Parquet datasets; Zarr, HDF5, NetCDF arrays | `references/storage-formats-and-zarr.md` | Format fits the access pattern; schemas consistent; chunking measured; conversions verified with a second reader |
| "What is in this data?", EDA, data quality, pipeline checks | `references/eda-and-data-quality.md` | Grain, keys, missingness, validity and outliers measured with counts; each finding backed by output that ran |
| Charts in notebooks, reports or shared HTML | `references/plotting.md` | Form fits the question; units and error bars explained; the saved file opened and spot-checked |
| Figures for papers, theses, posters or submissions | `references/publication-figures.md` | Venue rules recorded and met; built at final size; fonts embedded; colorblind-safe; regenerates from data |
| Locations, maps, rasters, coordinate systems, spatial joins | `references/geospatial.md` | CRS checked at every step; measurements in a suitable projection; join matches counted; licenses recorded |
| Networks: paths, centrality, communities, graph files | `references/networkx-graphs.md` | Counts reconcile with source; weights mean costs for paths; seeds fixed; algorithm checked on a toy graph |
| `.m` or `.mat` files, running MATLAB or Octave, porting to NumPy | `references/matlab-octave.md` | Availability and license checked; batch runs fail loudly; ports match golden outputs within stated tolerance |
| Kaggle datasets, notebooks, competitions, submissions | `references/kaggle.md` | Token set by the user; rules summarized; metric reproduced locally; submission validated against the sample |
| Official statistics APIs (FRED, BLS, BEA, Census, Treasury, OFR, World Bank, IMF, OECD, Eurostat, ECB, Data Commons) | `references/economic-statistics-apis.md` | Each series' units, adjustment, frequency and vintage recorded; limits respected; values checked against the agency |
| SEC filings, XBRL facts, insider and 13F data; market prices, FX, crypto, indicators, backtests | `references/filings-and-market-data.md` | EDGAR fair-access rules followed; XBRL facts deduplicated and reconciled; vendor terms recorded; biases controlled |

Several references often apply together. A question about a production table's trend typically needs `live-database-access`, `sql-query-tuning`, `eda-and-data-quality` and `plotting`, read in that order.

## Working method

1. **Frame.** Write the question, the decision it informs, the data's grain (what one row is) and its sensitivity. Ask the owner for anything you would otherwise guess: units, codes, filters, time zone.
2. **Look safely.** Profile files with `scripts/csv_profile.py`; read metadata for Parquet, HDF5, NetCDF and Zarr; estimate table sizes before querying. Note encoding, delimiter, types, nulls, keys and flagged values.
3. **Pick the tool by size and shape.** In memory: pandas or Polars. Larger than memory on one machine: Polars streaming or DuckDB. Python parallelism or chunked arrays: Dask with Zarr. Multi-terabyte or an existing lakehouse: Spark. Data already in a database: push filters and aggregates into SQL.
4. **Transform with checks.** Explicit types on read, validated joins, row counts after every filter and join, and no silent filling or dropping of values. Write transformations as functions with small tests that include nulls, duplicates and edge dates.
5. **Show it.** Choose each chart from the question, label units, explain uncertainty, and open the saved file to check it.
6. **Verify and report.** Cross-check key numbers independently (SQL against dataframe, a manual subset, the source's published table) and report what ran, what it showed and what remains unverified.

## CSV profiler helper

`scripts/csv_profile.py` is a read-only, standard-library profiler for CSV, TSV and other delimited files (optionally gzip-compressed). It never uses the network, never writes files and never prints cell values unless `--show-values` is given.

It sniffs the encoding (byte-order marks, UTF-8, Windows-1252 and Latin-1 fallbacks, counting undecodable bytes) and the delimiter; infers each column's type (integer, float, decimal-comma float, boolean, date, datetime, string, mixed); and reports row counts, ragged rows with line numbers, blank and duplicate rows, nulls including null-like tokens such as `N/A`, distinct counts, numeric summaries (mean, standard deviation, quantiles, zeros, negatives, outliers beyond 1.5 IQR), date ranges, and possible single-column and two-column keys. Findings flag mixed types, numbers stored with formatting, leading zeros, scientific notation in integer columns, integers beyond 2^53, sentinel values and dates, ambiguous or mixed day/month order, mixed time zones, spreadsheet formula prefixes, encoding damage, control characters, whitespace and case variants.

```bash
python3 <productcraft>/modules/data-engineering/scripts/csv_profile.py data/orders.csv
python3 <productcraft>/modules/data-engineering/scripts/csv_profile.py data/export.txt --delimiter ';' --encoding cp1252 --json
python3 <productcraft>/modules/data-engineering/scripts/csv_profile.py big.csv.gz --max-rows 500000 --strict
python3 <productcraft>/modules/data-engineering/scripts/csv_profile.py survey.csv --null-token "not asked" --show-values --top 3
```

`<productcraft>` is the folder where the ProductCraft skill is installed. Exit codes: 0 when the profile completes, 1 with `--strict` when WARN findings exist, 2 for usage errors or unreadable input. Column names and aggregate statistics (including the minimum and maximum of numeric and date columns) are printed; use `--show-values` only when the user agrees that values may appear in the conversation. Exact distinct counts are tracked up to `--distinct-cap` values per column; quantiles come from a deterministic sample above `--sample-size` values; two-column keys are checked for files up to 200,000 rows. Findings are prompts to investigate, not verdicts. Speed is roughly 25,000-30,000 rows per second for an eight-column file; use `--max-rows` for a first look at very large files.

## Topic essentials

Use these when the reference is not needed; open the reference when a bullet raises a question.

- **SQL:** `NOT EXISTS` instead of `NOT IN` with nullable subqueries; aggregate before joining one-to-many; unique tiebreakers in every `ORDER BY` used for pagination or ranking; keyset pagination instead of large offsets; bind parameters always.
- **Indexes:** from plans, not hunches; equality columns first, then range or sort; check estimated versus actual rows before blaming the index; count the write cost.
- **Databases:** never disable autovacuum; set `lock_timeout` before DDL; long transactions block vacuum and replication cleanup; read replicas lag.
- **pandas:** IDs as text, explicit date formats, `validate=` on merges, `.loc` assignment, no `iterrows` on hot paths, nullable dtypes for integers with gaps.
- **Polars:** lazy scans, expressions instead of `map_elements`, explicit schemas and null counts around non-strict casts.
- **Scale:** try column pruning, Parquet and SQL pushdown before a cluster; Dask partitions around 100 MB; Spark shuffle partitions around 100-200 MB with AQE on; never `collect()` unbounded results.
- **Formats:** Parquet for tables, Zarr for chunked arrays on object storage, CSV only for exchange, with a data dictionary.
- **EDA:** grain and keys first; missingness patterns; sentinel values; outliers are questions; stratify before concluding.
- **Charts:** form from the question, units on axes, error bars defined, colorblind-safe palettes, saved file opened and checked.
- **Geospatial:** print the CRS at every step; measure in projected or geodesic terms; count join matches; OSM attribution.
- **External data:** precise series definitions, vintages, rate limits, caching, attribution, and no advice.

## What to report

Add these to the engineering workflow's report and `../../assets/review-template.md`:

- References used and, for each, the minimum check from the table: met, not met or `NOT VERIFIED` with the reason.
- Data sources: system or file, environment, version or vintage, retrieval date, license or terms, and how read-only access was enforced.
- Profiler summary (rows, columns, WARN findings and how each was handled) for files received or produced.
- Row counts through the pipeline, and the independent cross-check of the main numbers.
- For performance work: baseline and after (plan, logical reads or run time, same parameters, run-to-run spread).
- Commands the user still has to run (index builds, writes, cluster or cloud changes, credential setup), with their rollback.
- Caveats: missing data, revisions, sampling, biases, and anything assumed rather than confirmed by the data owner.

## Working with other ProductCraft modules

- `../engineering-workflow/GUIDE.md`: tracks, done-when checks, test-first and verification for the code around the data.
- `../engineering-practices/references/data-and-migrations.md` and `../engineering-practices/scripts/migration_check.py`: schema changes, backfills and lock-safe index builds; run the checker on any migration this module's advice leads to.
- `../engineering-practices/references/performance.md`: the general measure-change-measure loop, caching and application-side N+1 queries.
- `../engineering-practices/references/resilience.md`: timeouts, retries, backoff and idempotency for API clients.
- `../ml-engineering/GUIDE.md`: statistical modeling, hypothesis testing, machine learning, forecasting and retrieval systems built on the data prepared here.
- `../data-and-product-surfaces.md` and `../ui-rules.md`: tables, dashboards and charts inside a product.
- `../documents/GUIDE.md`: Excel, Word, PowerPoint and PDF inputs and deliverables, including CSV for spreadsheets.
- `../launchguard/references/security-baseline.md`: parameterized queries, data exposure and access control when data code ships in an application.
- `../agent-safety/GUIDE.md`: stop-check before destructive database commands; secrets by name; guided setup scripts for credentials.
- `../legal-ready/GUIDE.md`: personal data, retention and data rights when datasets contain information about people.
- `../cloud-infrastructure/GUIDE.md`: provisioning clusters and storage for Dask or Spark, with plan-first and cost guardrails.
- `../scientific-computing/GUIDE.md`, `../life-sciences/GUIDE.md` and `../research-writing/GUIDE.md`: numerical methods, domain data formats, and the papers that publication figures go into.
