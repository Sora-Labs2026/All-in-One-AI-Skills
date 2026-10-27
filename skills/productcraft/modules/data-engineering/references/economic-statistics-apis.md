# Official economic statistics through APIs

Read this when a task pulls macroeconomic, fiscal, labor, demographic or financial-stability statistics from a public agency's API: FRED and ALFRED, the U.S. Bureau of Labor Statistics, Bureau of Economic Analysis, Census Bureau and Treasury Fiscal Data, the Office of Financial Research, the World Bank, the IMF, OECD, Eurostat, the ECB, or Data Commons. Company filings and market prices are in `filings-and-market-data.md`. General integration rules (keys, retries, pagination) are in `../../engineering-practices/references/resilience.md` and `../../agent-safety/references/secrets.md`.

This is data engineering and analysis, not investment or policy advice. Report what the data says, with its caveats; never invent a figure, a release date or a revision.

## Identify a series precisely

Two series with the same name can differ in every way that matters. Record for each one:

| Attribute | Examples of what differs |
|---|---|
| Identifier and source agency | FRED `UNRATE` is the BLS unemployment rate; `CPIAUCSL` is CPI-U, seasonally adjusted |
| Units | Levels, index (and base period), percent, percent change, annualized rate, per capita, millions versus billions |
| Seasonal adjustment | Seasonally adjusted, not adjusted, or adjusted at annual rates (U.S. GDP levels are SAAR) |
| Frequency and aggregation | Monthly average versus end of period versus sum; fiscal versus calendar years |
| Price basis | Nominal (current prices) versus real (chained or constant prices of a stated year) |
| Vintage | The value as first published versus as revised today |
| Observation date convention | FRED dates a monthly or quarterly observation by the first day of the period |

Revisions are routine: GDP, payrolls and many others are revised for months or years, and benchmark revisions rewrite whole histories. For "what was known at the time" (backtests, forecast evaluation), use vintage data (ALFRED's real-time periods, or archived releases), not today's series.

## Hygiene for every source

- **Keys** stay in environment variables (`FRED_API_KEY`, `BLS_API_KEY`, ...) set by the user, never in code, notebooks or chat. Several sources need no key at all.
- **Throttle and cache.** Respect the published limits below, back off on HTTP 429 and 5xx, and cache raw responses on disk with the retrieval date so reruns do not refetch and the analysis can be reproduced.
- **Save raw, parse separately.** Keep the response (JSON, CSV) as fetched; parse into a typed table in a second step with tests on saved fixtures.
- **Missing-value encodings differ:** FRED observations use `"."`; Treasury Fiscal Data uses the string `"null"`; SDMX sources use empty observations or status flags. Map them explicitly.
- **Attribution and terms:** cite the agency and series in outputs as each source asks; check redistribution terms before republishing data (see the FRED note below).
- **Verify a few values** against the agency's own release table or website for the same period and vintage.

```python
import os, time, requests

def get_json(url, params, *, tries=5, timeout=30):
    """GET with a timeout and capped exponential backoff on 429 and 5xx responses."""
    for attempt in range(tries):
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(60, 2 ** attempt))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"giving up after {tries} attempts: {url}")

obs = get_json("https://api.stlouisfed.org/fred/series/observations", {
    "series_id": "UNRATE", "api_key": os.environ["FRED_API_KEY"], "file_type": "json",
    "observation_start": "2015-01-01",
})["observations"]
values = [(o["date"], None if o["value"] == "." else float(o["value"])) for o in obs]
```

## Sources

Limits and policies below are as published around 2026; read the provider's current documentation before relying on them.

### FRED and ALFRED (Federal Reserve Bank of St. Louis)

- Hundreds of thousands of U.S. and international series aggregated from many agencies. Free API key; JSON with `file_type=json`; a per-key request limit applies (commonly cited as about 120 requests per minute), with HTTP 429 when exceeded.
- Core endpoints: `fred/series` (metadata: units, frequency, seasonal adjustment, last updated, notes), `fred/series/observations`, `fred/series/search`, `fred/release/dates`, `fred/category/children`, `fred/tags/series`.
- Server-side transformations with `units=` (`chg`, `ch1`, `pch`, `pc1`, `pca`, `log` and others) and frequency conversion with `frequency=` plus `aggregation_method=` (`avg`, `sum`, `eop`). Doing transformations yourself keeps them visible and testable; if you use the server's, record the parameters.
- Vintages: `realtime_start` and `realtime_end` (or `vintage_dates=`) return values as they were known on given dates; `output_type` controls the layout.
- **Terms:** FRED republishes data owned by other organizations. Some series carry their owners' copyright and restrict redistribution or commercial use; read the series notes and FRED's terms before republishing. The API key belongs to the person who registered it.

### U.S. Bureau of Labor Statistics (BLS)

- Public Data API version 2 with a free registration key: daily query limits (on the order of 500 queries per day, 50 series per query, 20 years per query); version 1 without a key allows far less. Series IDs encode survey, area, item and adjustment (for example CPI, employment, wages).
- Data is POSTed as JSON (`seriesid`, `startyear`, `endyear`); responses mark preliminary values with footnotes. Handle `"-"` and footnote codes.

### U.S. Bureau of Economic Analysis (BEA)

- National accounts (NIPA tables), regional, industry and international data. Free `UserID` key. Published throttling: roughly 100 requests, 100 MB and 30 errors per minute; exceeding them locks the key out for an hour.
- Tables are identified by dataset, table name, frequency and year; line numbers within NIPA tables can change across comprehensive revisions, so key on series codes and line descriptions, not positions.

### U.S. Census Bureau

- APIs for the American Community Survey, decennial census, economic surveys and more. A free key is required beyond a small number of queries per day per IP address (500 at the time of writing); up to 50 variables per call.
- ACS estimates come with **margins of error**; carry them through, and do not compare estimates whose intervals overlap as if they differed. Geographies and variable codes change between vintages; pin the vintage in the URL.

### U.S. Treasury Fiscal Data

- Debt, revenue, spending, interest rates and exchange rates from the Bureau of the Fiscal Service. No key. Base `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/` plus a versioned endpoint such as `v2/accounting/od/debt_to_penny`.
- Query parameters: `fields=`, `filter=record_date:gte:2025-01-01` (operators `eq`, `lt`, `lte`, `gt`, `gte`, `in`), `sort=-record_date`, `format=json|csv|xml`, `page[number]` and `page[size]`. Omitting fields can trigger automatic aggregation of the remaining numeric columns; select fields deliberately.
- Every value arrives as a string, including numbers and dates, and nulls arrive as the string `"null"`. Use `meta.dataTypes` in the response to cast, and loop over `meta.total-pages` for complete results.

### Office of Financial Research (OFR)

- The Hedge Fund Monitor API (`https://data.financialresearch.gov/hf/v1`) serves aggregated statistics, with no key: SEC Form PF aggregates (size, leverage, liquidity), CFTC Traders in Financial Futures positioning, sponsored repo volumes, and the Federal Reserve's dealer financing survey. Series are named by mnemonics (`/metadata/search?query=...` to find them; `/series/timeseries?mnemonic=...` returns date and value pairs).
- Data is aggregated and lagged (quarterly Form PF statistics appear months after the quarter); some subseries mask values for confidentiality. Individual fund filings are confidential and not available.

### International sources

| Source | Access | Notes |
|---|---|---|
| World Bank Indicators API (v2) | No key; `https://api.worldbank.org/v2/country/<codes>/indicator/<id>?format=json&per_page=...` | The response is a two-element list (paging metadata, rows). Country lists include regional and income aggregates; filter them before cross-country statistics. Most data under CC BY 4.0 |
| IMF | SDMX-based API | The IMF moved to a new data portal and SDMX API in 2025; older JSON endpoints in examples may no longer work. Check current documentation |
| OECD | SDMX API of the OECD Data Explorer | Replaced the older OECD.Stat interface in 2024; dataflows are versioned; anonymous use has rate limits |
| Eurostat | JSON-stat and SDMX APIs | Reuse under CC BY 4.0 with attribution; flags mark provisional, estimated and break-in-series values |
| European Central Bank | ECB Data Portal SDMX API (`data-api.ecb.europa.eu`) | Exchange rates, interest rates, monetary statistics; series keys such as `EXR/D.USD.EUR.SP00.A` |
| Bank for International Settlements | SDMX API of the BIS data portal | Credit, property prices, effective exchange rates |

An SDMX client library (for example `sdmx1` in Python) handles dataflow discovery, dimension codes and keys across these sources. Codes for countries and units differ between providers; map them with a documented table (ISO 3166 alpha-3 is the usual common key).

### Data Commons

- Data Commons (a Google-run knowledge graph) aggregates statistics from census bureaus, health, labor and environmental agencies under common variable names (`Count_Person`, `UnemploymentRate_Person`) and entity IDs (`country/USA`, `geoId/06` for California). The `datacommons-client` Python package wraps the v2 API; an API key is required for the public instance.
- Each value can come from several sources ("facets") with different methods and dates. Pin the facet (source, measurement method, observation period) for a consistent series, and cite the underlying source; its license applies, not only Data Commons' terms.
- Resolve place names to IDs with the resolve endpoints and check ambiguous matches (several places share names).

## Checks (done when)

- [ ] Every series recorded with ID, source, units, seasonal adjustment, frequency, price basis, vintage and retrieval date.
- [ ] Keys read from the environment; limits respected with throttling, backoff and a local cache.
- [ ] Missing-value encodings and string-typed fields converted explicitly; parsers tested on saved responses.
- [ ] A few values checked against the agency's published tables for the same vintage.
- [ ] Attribution included and redistribution terms checked for anything published; no advice presented as a conclusion from the data.
