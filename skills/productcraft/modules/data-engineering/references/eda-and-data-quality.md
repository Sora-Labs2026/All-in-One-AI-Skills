# Exploratory data analysis and data quality

Read this when someone hands you a dataset and asks what is in it, whether it can be trusted, or what it shows; before any modeling; and when building checks that keep a pipeline's data trustworthy. Statistical modeling, hypothesis tests and machine learning are in `../../ml-engineering/GUIDE.md`; this reference stops at understanding and validating the data.

EDA is a sequence of questions, not a gallery of every possible chart. Each step produces a short written finding with the evidence (a count, a table, a figure) that supports it.

## 1. Frame it before opening the file

- **The question.** What decision or claim will this data inform? Write it down; it decides which columns and checks matter.
- **Provenance.** Who produced the data, how (system export, survey, sensor, scrape, third-party vendor), when, with what filters, and under what license or terms. Ask the user rather than guessing.
- **The grain.** One row equals one what (order, order line, customer per day, sensor reading)? Most wrong numbers come from misreading the grain.
- **Sensitivity.** Personal, health, financial or confidential data changes how you look at it: profile with aggregates, do not print raw records into the conversation, and keep extracts out of the repository (`live-database-access.md` covers the same rules for databases).

## 2. First look without exposing values

- For delimited files, run the bundled profiler; it prints structure and statistics but no cell values unless asked:

  ```bash
  python3 <productcraft>/modules/data-engineering/scripts/csv_profile.py data/orders.csv
  python3 <productcraft>/modules/data-engineering/scripts/csv_profile.py data/orders.csv --json > profile.json
  ```
- For Parquet, read the metadata (row count, schema, row groups) before the data; for HDF5, NetCDF and Zarr, print the structure (`h5ls -r`, `ncdump -h`, `xr.open_dataset(...)` without computing). See `storage-formats-and-zarr.md`.
- For databases, row-count estimates and `information_schema` before any `SELECT *`.
- Record the basics in the notes: rows, columns, file size, date range, encoding, and anything the profiler flagged.

## 3. Structure and keys

- Confirm the key that defines the grain is unique (`df.duplicated(subset=key).sum() == 0`, or the profiler's "possible keys"). If no key is unique, find out why before aggregating anything.
- Check types against meaning: identifiers as text, codes with leading zeros intact, dates parsed with an explicit format, units known for every measure. A column named `amount` without a currency or unit is a question for the owner.
- Look up coded values (status codes, country codes, categories) in a dictionary from the source; do not infer meanings from frequencies.
- For several tables, check referential integrity: child keys without parents, parents without children, and the cardinality of each relationship.

## 4. Completeness

- Missingness per column, and its pattern: by time (a field added mid-year), by source or segment (one region never fills it), together with other columns (whole blocks missing). `df.isna().groupby(df["source"]).mean()` and a missingness heatmap over time answer this quickly.
- Think about why values are missing: at random, related to other observed variables, or related to the missing value itself (high earners skip the income question). The answer decides whether any later analysis is biased; record it, do not fix it here.
- Watch disguised missing values: sentinel codes (`-999`, `9999`, `1900-01-01`, `0` where zero is impossible), placeholder text (`unknown`, `n/a`, `TBD`), and empty strings. The profiler flags common ones.

## 5. Validity and consistency

- Ranges and domains: negative ages, quantities, prices; percentages above 100; dates in the future or before the business existed; coordinates outside the region.
- Cross-field rules: `end >= start`, `total == sum(lines)`, `shipped_at` only when `status = 'shipped'`.
- Duplicates: exact duplicate rows, and near duplicates after normalizing case, whitespace, punctuation and formatting of names, emails and addresses.
- Consistency over time: a definition change shows up as a step in a series, a new category, or a unit change (grams to kilograms). Plot the main measures by month before trusting any trend.

## 6. Distributions

- Numeric columns: histogram (or ECDF, which needs no bin choice) on a log scale when values span orders of magnitude; summary statistics with quantiles, not only mean and standard deviation.
- Look for: heavy tails, zero inflation, several modes (mixed populations), heaping at round numbers (self-reported values), truncation at a limit (a system cap), and impossible precision.
- Categorical columns: frequency tables sorted by count, with the long tail summarized; spelling variants of the same category.
- **Outliers are questions, not deletions.** For each extreme value decide: data error (fix or exclude, with a record), legitimate but rare (keep; consider robust statistics), or a different population (analyze separately). Never drop outliers silently or by a blanket rule.

## 7. Relationships

- Scatter plots (hexbin or 2-D histograms for many points) for pairs of measures; grouped box or violin plots for a measure across categories; cross-tabulations with row percentages for two categories.
- Correlation coefficients summarize only linear (Pearson) or monotonic (Spearman) association, are distorted by outliers and say nothing about cause. Always look at the plot behind a coefficient.
- Stratify before concluding: an association that reverses within every subgroup (Simpson's paradox) is common in operational data with a confounding segment, such as region, channel or cohort.

## 8. Time

- Gaps, duplicated timestamps, time zone mixing, daylight-saving jumps, irregular sampling.
- Seasonality and calendar effects (weekday, month end, holidays) before reading anything into a single change.
- Revisions and late-arriving data: the most recent periods are often incomplete or provisional. Economic and financial series are revised (see `economic-statistics-apis.md`).

## 9. Representativeness and leakage

- Who or what is missing from the data entirely (survivorship: only customers who stayed, only funds still trading; selection: only users who opted in)? No amount of analysis of the rows you have recovers what was never collected.
- If the data will train or evaluate a model: columns that are recorded after the outcome, or derived from it, leak the answer; rows from the same entity across training and test sets inflate scores. Flag these for the modeling work in `../../ml-engineering/references/evaluation-and-leakage.md`.

## Report the findings

Structure: the question; the data (source, grain, size, period); quality issues found, each with a count and its likely effect; the main findings, each with the figure or table that shows it; caveats and open questions for the data owner; suggested next steps. Every number in the report comes from code that ran in this session; never estimate or invent figures. Keep the notebook or script so the report can be regenerated.

## Data quality checks in pipelines

Turn the findings into automated checks so the same problems are caught next time:

- **Schema:** column presence, types, nullability, allowed values, uniqueness of keys.
- **Volume and freshness:** row counts within an expected band, latest timestamp recent enough.
- **Content:** ranges, cross-field rules, referential integrity, distribution shifts against a reference period.
- **Tools:** Pandera (pandas and Polars schemas in Python), Great Expectations, dbt tests (`unique`, `not_null`, `accepted_values`, `relationships`) for SQL pipelines, Soda; or plain SQL assertions that return offending rows. Choose what the project already uses.
- Fail loudly on contract violations, quarantine bad rows with a reason column instead of dropping them, and alert the data owner. Record row counts in and out of every step so silent loss is visible.

## Reproducibility

- Raw data is read-only; every derived file is produced by code.
- Notebooks run top to bottom on a fresh kernel; random seeds are fixed and stated; library versions are pinned.
- Sampling for speed is fine during exploration; final numbers come from the full data, or the report says otherwise.

## Checks (done when)

- [ ] Question, provenance, grain and sensitivity written down.
- [ ] Key uniqueness, types, units and coded values confirmed.
- [ ] Missingness, validity, duplicates and outliers measured and described, with counts.
- [ ] Each finding backed by a figure or table produced by code that ran; caveats stated.
- [ ] No personal data printed into the conversation or committed; recurring problems turned into pipeline checks where a pipeline exists.
