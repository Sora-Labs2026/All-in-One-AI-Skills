# UI Distiller: Building dashboards

Read this when building or rebuilding a dashboard: an analytics or operations screen inside a product, or a monitoring board in an observability tool. It covers the questions a dashboard must answer, specifying each panel, layout, data states, time and refresh, building it as code, and verification. Screen-level rules are `SCR-01`, `CMP-17` (KPI tiles), `CMP-18` (charts) and `CMP-19` (operational tables) in `../../../references/ui-rules/`; chart choice is in `../../data-and-product-surfaces.md`; 21 worked dashboards are in `../../../examples/` (`dashboard-v1.html` to `dashboard-v21.html`, listed in `../../../examples/README.md`). Monitoring-stack specifics (Prometheus, Grafana provisioning, alerts) are in `../../cloud-infrastructure/references/monitoring-stack.md` and `../../engineering-practices/references/observability.md`.

## 1. Questions before panels

Write down who uses the dashboard, how often, and the three to seven questions they bring to it, each paired with the decision it supports. A question with no decision behind it is cut.

| Who and when | Question | Decision it supports |
|---|---|---|
| On-call engineer, during an alert | Is checkout failing for users right now, and since when? | Page the owning team, roll back the last deploy |
| On-call engineer | Which dependency is slow? | Fail over, open an incident with the vendor |
| Operations lead, each morning | Which orders will miss today's dispatch window? | Re-assign pickers, notify customers |
| Finance, weekly | Is cash in on track against the forecast? | Chase overdue invoices |

Operational boards follow established frames: rate, errors and duration for request-driven services; utilization, saturation and errors for resources; then each dependency. Product dashboards lead with the user's decision (`SCR-01`), not a row of equal tiles.

## 2. Specify every panel

Fill one row per panel before building. It forces the definitions that dashboards usually leave implicit.

| Field | Example |
|---|---|
| Question | Is checkout failing for users? |
| Measure (exact definition) | Failed checkout requests ÷ all checkout requests, excluding health checks; failure = HTTP 5xx or payment timeout |
| Unit and format | Percent, one decimal |
| Aggregation and window | Ratio of rates over 5 minutes |
| Comparison | Objective of 0.5%; same hour last week as a faint line |
| Threshold and its basis | Warn at 0.5% (service objective), critical at 2% (incident policy) |
| Form | Line over time with the objective marked; current value as the title figure |
| Drill-down | Link to failed requests filtered to the same window; runbook link |
| Owner | Payments team |

Definitions that go wrong most often:
- **Averages hide the tail.** Show latency percentiles computed from histograms; percentiles cannot be averaged across instances or time buckets, so aggregate the histogram first.
- **Counters are not rates.** Show rates or increases per interval, never a raw ever-growing counter.
- **Ratios need their denominator** visible on hover or in a caption, or a 50% failure rate on two requests looks like an outage.
- **Partial periods.** Today and this month are incomplete; mark them and never compare a partial period with a full one.
- **Time zones.** Store in UTC; display in the viewer's or the business's zone, and say which on the dashboard.
- **Totals must add up** with their parts and with the system of record (`COP-05`).
- **Thresholds need a source:** an objective, a contract, a capacity limit or a historical percentile. A round number chosen by eye produces alerts nobody trusts.

## 3. Layout

1. **Top:** the answer to "is it OK?": exceptions, the status in words and color (`COL-07`), the one figure that matters with its comparison (`CMP-17`).
2. **Then** the main trend against its target or objective, with deploy or change markers.
3. **Then** breakdowns that explain the trend: by region, dependency, endpoint, product line.
4. **Last** detail tables built for triage (`CMP-19`) and links out.

Group related panels in titled sections; collapse rarely used sections. Keep a fixed panel order across environments and services so people know where to look. Scope controls (environment, region, tenant, period) sit at the top, are visible at all times (`SCR-27`), and are kept in the URL so links reproduce the view.

## 4. Data states

Design each state explicitly; the generic "loading forever" or blank panel is the most common dashboard defect.

| State | Show |
|---|---|
| Loading | Skeleton in the panel's final shape; the shell stays put (`FBK-14`) |
| No data | "No data for this period" with the reason if known; never draw it as 0 |
| A real zero | 0 with its unit; zero is a value |
| Stale | "Updated 14 min ago" next to the figure; a warning when older than the expected interval |
| Partial | Which sources or regions are missing, and that totals exclude them |
| Error | What failed (query, permission, timeout) and a retry |
| No permission | What the viewer cannot see and whom to ask |

In observability tools, set each panel's handling of null and missing values deliberately so gaps are not drawn as drops to zero or bridged as flat lines.

## 5. Time range and refresh

- Default the time range to the decision: the last hour for incident boards, month to date for finance, the last 24 hours for daily operations.
- Refresh no faster than the data changes and the scrape or ingestion interval; heavy queries on a short auto-refresh load the database for every open tab. Pause refresh when the tab is hidden.
- Show the time range and the last update in the panel area, not only in a picker.

## 6. Build it

**In the product:** compose from the design system's components and tokens (see [design-system-construction.md](design-system-construction.md)); charts follow `CMP-18` (title, one-line summary, labeled axes, exact values on hover and focus, a table alternative); figures use tabular numerals; actions sit next to the data they act on. Read the closest example page in `../../../examples/` first and take its structure and states, not its sample data or brand.

**In an observability tool:** keep dashboards as code in the repository (JSON model, provisioning files, or a generator such as Grafonnet or the tool's Terraform provider), reviewed like any change. Use template variables for environment, region and instance instead of copies per environment; set units on every panel; put the question and the measure definition in each panel's description; link panels to runbooks and to filtered logs or traces; add deploy annotations. Validate the JSON and import it into a non-production instance before merging.

**Starter questions for common systems** (adapt them; they are not complete lists):
- **API or ingress:** request rate, error ratio by status class, latency percentiles against the objective, saturation (connections, worker utilization), top failing routes.
- **Message broker:** consumer lag expressed as time behind as well as messages, under-replicated or offline partitions, produce and consume rates, broker availability, disk headroom.
- **Search cluster:** cluster status and unassigned shards, query and indexing latency, rejected requests, heap and garbage-collection pressure, disk watermarks.
- **Relational database:** connections against the limit, replication lag, slow queries, lock waits, cache hit ratio, storage growth and headroom.
- **Job queue and workers:** age of the oldest waiting job, throughput, failure and retry rates, dead-letter size, worker saturation.

## 7. Verify

- **Reconcile:** pick a past period and check every figure against the system of record or a direct query; check that parts sum to totals.
- **Thresholds:** feed known values (a replayed incident, a synthetic spike in a test environment) and confirm colors and alerts change where the specification says.
- **States:** force each state from section 4 (empty period, failing data source, revoked permission, stale data) and look at the result.
- **Render:** at the sizes it will be used (a wall display, a laptop, a phone for on-call), in light and dark; keyboard and screen reader for product dashboards (`../../responsive-accessibility.md`).
- **Cost:** load the dashboard with its longest allowed time range and measure query time; fix slow panels with pre-aggregation or recording rules.
- **Exposure:** no secrets, personal data or customer identifiers in panel titles, labels or shared snapshots; sharing and embedding permissions set on purpose.

## Anti-patterns

Vanity tiles that support no decision; gauges and dials (`../../data-and-product-surfaces.md`); pies with many slices; dual y-axes; every available metric "just in case"; units missing; colors without a legend or a meaning; thresholds without a basis; percentiles averaged across hosts; per-environment copies that drift; auto-refresh every few seconds on expensive queries.

## Done when

- Every panel maps to a written question and decision, and its specification row is complete.
- Figures reconcile with the system of record for a test period, and totals add up.
- Loading, no data, zero, stale, partial, error and no-permission states were each seen working.
- The dashboard is stored as code or built from the design system's components, reviewed, and renders at its real display sizes.
