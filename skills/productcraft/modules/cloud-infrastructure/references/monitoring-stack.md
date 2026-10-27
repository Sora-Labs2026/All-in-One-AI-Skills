# Running the monitoring stack: Prometheus, Alertmanager, Grafana, OpenTelemetry Collector and cloud monitors

Read this when you write or review Prometheus scrape configs, recording or alerting rules, PromQL, Alertmanager routing, Grafana dashboards, OpenTelemetry Collector pipelines, CloudWatch or Azure Monitor alarms, synthetic checks, or when monitoring costs or cardinality grow. What to instrument and which alerts to have is in `../../engineering-practices/references/observability.md`; objectives and error budgets are in `sre-practice.md`.

Monitoring configuration is code: keep it in the repository, validate it offline, and change shared production monitoring only through the project's normal review and deployment path.

## Prometheus

- **Scraping:** in Kubernetes, discover targets with ServiceMonitor or PodMonitor objects (Prometheus Operator) or `kubernetes_sd_configs`; elsewhere, file or cloud service discovery. Scrape every 15 to 60 seconds; shorter intervals multiply storage.
- **Labels:** relabel at scrape time to drop high-cardinality or useless labels. Every unique label combination is a new series; user IDs, request IDs, full URLs and error messages never become labels.
- **Check cardinality** in the TSDB status page (`/api/v1/status/tsdb`) or with `topk(10, count by (__name__)({__name__=~".+"}))` on a small instance; the latter is expensive on large ones.
- Prometheus 3 (late 2024) brought UTF-8 metric and label names and a new UI; check the version before copying older configuration.
- Long-term storage and global views come from remote write to a compatible backend (Thanos, Mimir, Cortex or a managed service). Size retention to what operations need.

### PromQL idioms

```promql
# Rate of a counter: always rate() or increase() over a range of at least four scrape intervals
sum by (service) (rate(http_requests_total{code=~"5.."}[5m]))
  / sum by (service) (rate(http_requests_total[5m]))

# Latency percentile from a histogram: aggregate buckets, keep le, then compute the quantile
histogram_quantile(0.95, sum by (le, service) (rate(http_request_duration_seconds_bucket[5m])))

# SLI as a ratio of good to valid requests under a latency threshold
sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
  / sum(rate(http_request_duration_seconds_count[5m]))

# Alert when a metric disappears entirely
absent_over_time(up{job="orders"}[10m])
```

- Never average percentiles across instances; aggregate the histogram buckets first.
- `rate()` handles counter resets; never apply it to gauges. Use `deriv()` or `delta()` for gauges.
- A latency threshold used in an SLI must be a bucket boundary, or the result is interpolated.
- Missing series make expressions return nothing, which looks like "fine". Pair important alerts with an `absent` alert, or use `or vector(0)` deliberately.

### Recording and alerting rules

```yaml
groups:
  - name: orders-slo
    rules:
      - record: service:http_requests:error_ratio_rate5m
        expr: |
          sum by (service) (rate(http_requests_total{code=~"5.."}[5m]))
            / sum by (service) (rate(http_requests_total[5m]))
      - alert: OrdersHighErrorBudgetBurn
        expr: service:http_requests:error_ratio_rate5m{service="orders"} > (14.4 * 0.001)
          and on (service) service:http_requests:error_ratio_rate1h{service="orders"} > (14.4 * 0.001)
        for: 2m
        labels: { severity: page, team: shop }
        annotations:
          summary: "orders is burning its 99.9% error budget about 14x too fast"
          runbook_url: "https://git.example.com/shop/docs/runbooks/orders-error-budget.md"
```

- Name recorded series `level:metric:operation` and precompute anything dashboards and alerts query often (the 1-hour rule above is recorded the same way).
- `for:` suppresses brief blips; `keep_firing_for:` (Prometheus 2.42+) stops alerts flapping on recovery.
- Every alert carries a severity label that routing understands, a summary a human can read at 3 a.m., and a runbook link.
- Validate and unit-test rules offline:

```bash
promtool check config prometheus.yml
promtool check rules rules/*.yml
promtool test rules tests/orders-slo.test.yml    # feed synthetic series, assert which alerts fire
```

## Alertmanager

- One routing tree: group by `alertname`, `service` and `cluster`; route `severity: page` to the paging integration and everything else to tickets or chat.
- Tune `group_wait` (first notification delay), `group_interval` (updates to a group) and `repeat_interval` (reminders) so one incident produces one page, not fifty.
- Inhibition rules mute symptoms of a known cause (cluster unreachable silences every alert from that cluster).
- Silences are for planned maintenance and known incidents, always with an end time and a comment. Creating or extending a silence on production alerts needs the user's go-ahead; an open-ended silence hides the next outage.
- Validate with `amtool check-config alertmanager.yml`, and test routes with `amtool config routes test --config.file=alertmanager.yml severity=page service=orders`.
- Receivers' webhook URLs and API keys are secrets; keep them in the secret store, not in the committed file.

## Grafana dashboards

- Provision dashboards and data sources from files or IaC (JSON in Git, Grafonnet, or the Grafana Terraform provider) so they are reviewed and reproducible. Hand-built dashboards drift and vanish.
- One overview per service in a fixed order: traffic, errors, latency against the objective, saturation, dependencies, with deploy annotations. Use template variables for environment and instance instead of copies per environment.
- Show rates and ratios, not raw counters; show percentiles from histograms; label units on every panel.

## OpenTelemetry Collector

```yaml
receivers:
  otlp:
    protocols: { grpc: {}, http: {} }
processors:
  memory_limiter: { check_interval: 1s, limit_percentage: 80, spike_limit_percentage: 20 }
  attributes/scrub:
    actions:
      - { key: http.request.header.authorization, action: delete }
      - { key: user.email, action: delete }
  batch: {}
exporters:
  otlphttp:
    endpoint: https://otel.example.com
    headers: { authorization: "${env:OTEL_EXPORTER_TOKEN}" }
service:
  pipelines:
    traces:  { receivers: [otlp], processors: [memory_limiter, attributes/scrub, batch], exporters: [otlphttp] }
    metrics: { receivers: [otlp], processors: [memory_limiter, batch], exporters: [otlphttp] }
    logs:    { receivers: [otlp], processors: [memory_limiter, attributes/scrub, batch], exporters: [otlphttp] }
```

- `memory_limiter` first, `batch` last, in every pipeline. Scrub personal data and credentials in a processor before export.
- Run agents per node or as sidecars for collection, and a gateway tier for tail sampling (keep all errors and slow traces), routing and credentials.
- Validate with `otelcol validate --config=collector.yaml` (or the distribution's binary name) and watch the Collector's own metrics for dropped or refused data.
- Collector component names and stability levels change between releases; pin the distribution version.

## Cloud-native monitors

- **CloudWatch:** alarms on metric math (error ratio = errors divided by requests) rather than raw counts; set `TreatMissingData` deliberately (`notBreaching` for sparse error metrics, `breaching` for heartbeats); composite alarms to page once per service; set retention on every log group (the default keeps logs forever); Logs Insights for investigation.
- **Azure Monitor:** metric alerts with dynamic or static thresholds, log search alerts in KQL, action groups for routing; diagnostic settings send resource logs to a Log Analytics workspace whose retention and ingestion cost need sizing.
- **Google Cloud Monitoring:** alerting policies with PromQL or MQL conditions, uptime checks, and log-based metrics; SLO monitoring built in for supported services.
- Manage these as IaC alongside the resources they watch.

## Synthetic checks

Probe user journeys from outside: HTTP checks with expected status and content (Prometheus blackbox exporter, cloud uptime checks), TLS certificate expiry, DNS resolution. Synthetic checks catch failures that produce no server-side errors (DNS, CDN, expired certificates). Point them at production only with the owner's agreement and at a modest rate.

## Cost and retention

Monitoring bills grow with series count, log volume and retention. Drop unused metrics at scrape time, sample high-volume success logs and traces, keep error data, and match retention to operational and policy needs (`cloud-cost.md`).

## Done when

- [ ] `promtool check`, `promtool test rules`, `amtool check-config` and the Collector validation ran on changed files, or are marked `NOT VERIFIED` with the reason.
- [ ] New alerts have severity, summary and runbook link, and were test-fired in a non-production setup.
- [ ] No high-cardinality labels were added; personal data and credentials are scrubbed before export.
- [ ] Dashboards and alarms are provisioned as code; no production silence or routing change happened without approval.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Alert never fires during an outage | Series missing, expression returns nothing | `absent_over_time` companion alert; test with promtool |
| p95 looks wrong across instances | Averaged per-instance percentiles | `histogram_quantile` over summed buckets |
| Prometheus memory keeps climbing | Cardinality explosion from a new label | Relabel to drop it; fix the instrumentation |
| Fifty pages for one incident | Grouping too fine, no inhibition | Group by service and alertname; inhibit dependents |
| Collector drops data under load | No memory limiter or batch tuning | `memory_limiter` first, `batch` last, scale the gateway |
| Log bill doubled | Debug logging in production, no retention | Restore levels; sampling; retention per log group |
