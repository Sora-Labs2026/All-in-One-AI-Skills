# Company filings (SEC EDGAR, XBRL) and market data

Read this when a task uses SEC filings or XBRL financial data, insider or institutional holdings forms, or prices, fundamentals, FX or crypto quotes from a market-data API, including backtests and technical indicators. Official macroeconomic statistics are in `economic-statistics-apis.md`.

**Guardrail.** Build software and analyses; never give investment, trading or tax advice, recommend securities, or place orders. Backtests are hypothetical and must say so, with their assumptions and costs. Never invent a reported figure, a filing or a date.

## SEC EDGAR

### Access rules

- No API key. The SEC's fair-access policy requires a descriptive `User-Agent` header naming the organization or person and a contact email (for example `Example Research Lab data-team@example.org`), and limits clients to 10 requests per second in total. Exceeding it gets the IP address blocked for a period. Throttle below the limit and cache.
- The user supplies the contact identity; do not invent one, and do not use the user's personal email unless they ask you to.
- For large pulls, download the nightly bulk archives (all company facts, all submissions) instead of making hundreds of thousands of calls.

### Endpoints worth knowing

| Need | Endpoint (on `data.sec.gov` unless noted) |
|---|---|
| Ticker to CIK mapping | `https://www.sec.gov/files/company_tickers.json` |
| A company's filing history and metadata | `/submissions/CIK##########.json` (CIK zero-padded to 10 digits) |
| All XBRL facts for a company | `/api/xbrl/companyfacts/CIK##########.json` |
| One concept over time for a company | `/api/xbrl/companyconcept/CIK##########/us-gaap/Revenues.json` |
| One concept for all companies in a period | `/api/xbrl/frames/us-gaap/Revenues/USD/CY2025.json` (`CY2025Q2` for a quarter, `CY2025Q4I` for an instant) |
| Filing documents | `https://www.sec.gov/Archives/edgar/data/<CIK>/<accession-without-dashes>/` |
| Full-text search of filings (2001 onward) | The EDGAR full-text search service behind the website's search page |

Tickers change and are reused; store the CIK (and accession numbers for filings) as identifiers.

Open-source wrappers such as `edgartools` parse filings, XBRL statements and ownership forms; pin the version and spot-check their output against the raw JSON or the filing itself.

### Forms

- **10-K** annual report and **10-Q** quarterly report (no 10-Q for the fourth quarter); **10-K/A** and **10-Q/A** amendments; **8-K** current events (results, executive changes, material agreements); **20-F** and **40-F** for many foreign issuers; **S-1** registrations; **DEF 14A** proxy statements (executive pay, votes).
- **Form 4** insider transactions, generally due within two business days of the trade; Forms 3 and 5 for initial and annual ownership.
- **13F-HR** quarterly holdings of institutional managers above the reporting threshold, due 45 days after quarter end: long positions in listed securities only (no shorts, most derivatives excluded), so it is a lagged, partial picture.
- **Schedules 13D and 13G** report beneficial ownership above 5%.
- Private-fund **Form PF** filings are confidential; only aggregates are published (through the OFR, see `economic-statistics-apis.md`).

### XBRL financial data traps

- **The same fact appears in many filings.** A 10-K reports the current year and comparatives for prior years, so a company-facts series contains each period several times. Deduplicate on the period (`start`, `end`), the value and the unit, and decide which filing wins: the first filed (point in time) or the latest (as currently restated).
- **`fy` and `fp` describe the filing, not the fact.** A fact for fiscal 2023 inside the fiscal 2025 10-K carries `fy = 2025`. Use `start` and `end` dates to identify the period; the `frame` field (for example `CY2024Q3`) marks the fact the SEC aligned to a calendar period.
- **Durations and instants.** Income-statement and cash-flow items cover a duration; balance-sheet items are instants. A 10-Q reports both three-month and year-to-date durations; select by period length (about 90 days versus 180 or 270).
- **Fourth quarters are derived.** Quarterly series need Q4 = annual value minus the first three quarters, which breaks when one of them was restated; check that the parts sum back to the annual figure.
- **Concepts vary across companies and years.** Revenue may appear as `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet` (older) or a company-specific extension. Map concepts per company and check coverage by year, rather than assuming one tag.
- **Units** are explicit (`USD`, `shares`, `USD/shares`, `pure`); values are already scaled (no "in thousands"). Signs follow the concept's definition, not the presentation in the statement.
- **Fiscal years** end in different months; align on period end dates when comparing companies, and say how.
- Reconcile a few key numbers with the rendered statement in the filing before trusting a parsed series.

## Market data

### Providers and terms

Prices and fundamentals come from exchanges, licensed commercial vendors (many with free tiers), brokers' APIs, and central banks for official FX reference rates (the ECB's euro reference rates, the Federal Reserve's H.10 series through FRED). Before building on any of them:

- **License and use:** exchange-sourced data usually may not be redistributed or displayed to others without a license; free tiers are typically for personal, non-commercial use. Storing and republishing vendor data in a product needs the vendor's written permission. Security identifiers such as CUSIP are themselves licensed.
- **Limits:** free tiers commonly allow only a handful of calls per minute and a few dozen to a few hundred per day; plan batch downloads and caching around the documented quota.
- **Errors inside successful responses:** several vendors return HTTP 200 with an error or "rate limit" message in the JSON body instead of data. Check the body for the expected keys and fail loudly; do not parse an error message as an empty series.
- **Unofficial scrapers** of consumer finance websites break without notice and may violate those sites' terms; do not build pipelines on them.
- **Credentials and sandboxes:** keys in the environment, never in chat or code; use a provider's paper-trading or sandbox environment for anything that touches orders, and never place real orders (see the guardrail above).

### Data traps

- **Adjusted versus unadjusted prices.** Splits and dividends change history: an adjusted close is restated whenever a new dividend or split occurs, so saved adjusted series go stale. Store raw prices plus corporate actions, and compute adjustments yourself, or record the adjustment date.
- **Survivorship bias.** A universe built from today's listings omits delisted, merged and bankrupt companies, inflating historical returns. Use a point-in-time constituent list and include delisted securities.
- **Look-ahead bias.** Fundamentals are known from the filing date, not the period end; index membership from the announcement date. Join on availability dates.
- **Time and calendars.** Exchanges trade in local time with holidays, half days and daylight-saving shifts; a daily bar's date and an intraday bar's timestamp (start or end of the interval) follow the vendor's convention. Use an exchange calendar library (`exchange_calendars` or `pandas_market_calendars`) and keep timestamps tz-aware.
- **Identifiers.** Tickers change and get reused; map to stable identifiers (CIK, FIGI, ISIN where licensed) with validity date ranges.
- **Crypto** trades around the clock across many venues with different prices; state the venue or index used, and expect gaps and outliers from thin markets.
- **Currency:** convert with a stated rate source and fixing time; do not mix close prices from different time zones with one FX rate unknowingly.

### Indicators: compute and test them yourself

Common indicators are a few lines of pandas; computing them locally avoids one API call per indicator and makes the definition explicit.

```python
import pandas as pd

def sma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n, min_periods=n).mean()

def ema(close: pd.Series, n: int) -> pd.Series:
    return close.ewm(span=n, adjust=False, min_periods=n).mean()

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()   # Wilder smoothing
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + gain / loss)
```

Definitions vary (seeding of the first average, simple versus Wilder smoothing), so test against a published worked example or the vendor's values for a few dates and document which definition you implemented.

### Backtests

- Use only information available at each decision time; lag signals by one bar where the trade happens at the next open.
- Include transaction costs, spreads, slippage and borrowing costs; report results with and without them.
- Separate the period used to design the strategy from the period used to evaluate it, and report how many variants were tried (multiple testing inflates the best result).
- Present outputs as hypothetical, with the data source, period, universe, assumptions and known biases.

## Checks (done when)

- [ ] EDGAR requests carry a real, user-approved `User-Agent` and stay under 10 per second; bulk files used for large pulls.
- [ ] XBRL facts deduplicated by period; durations and instants separated; derived quarters reconcile with annual totals; key values match the filed statements.
- [ ] Market-data license, quota and redistribution terms recorded; responses checked for in-body errors.
- [ ] Prices stored raw with corporate actions; universes point-in-time; joins on availability dates; exchange calendars and time zones explicit.
- [ ] Indicators tested against reference values; backtests labeled hypothetical with costs and biases stated; no advice given.
