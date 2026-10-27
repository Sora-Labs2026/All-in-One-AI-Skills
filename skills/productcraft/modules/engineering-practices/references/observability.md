# Observability

Read this when a change adds an endpoint, job, queue consumer, external call or retry path that will run in production; when you add logging, metrics, tracing, dashboards or alerts; or when an incident took too long to understand.

Instrumentation is part of the feature, written and verified with it, like tests.

## Start from questions

Before adding any signal, write two to four questions an on-call engineer will ask about this feature, for example:

- Are imports succeeding, and how long do they take at p95?
- When an import fails, is it bad input, our parser, or the storage provider?
- Is the storage provider slower or failing more than usual?

Each signal you add should help answer one of them. Rough split: **metrics** say *that* something changed, **traces** show *where* time or errors arise across components, **logs** explain *why* for a specific case.

## Structured logs

- Emit one JSON object per event with a stable event name and typed fields, through the project's logger (for example pino, structlog, zap, slog, Logback with a JSON encoder). Not interpolated strings.

```json
{"ts":"2026-10-25T09:31:02.118Z","level":"warn","event":"import.row_rejected","importId":"imp_81f","row":1204,"reason":"invalid_date","requestId":"01JB7Q3W5K6X","traceId":"4bf92f3577b34da6a3ce929d0e0e4736"}
```

- **Levels with consistent meaning:** `error` means an operation failed and someone may need to act; `warn` means degraded but handled (retry succeeded, fallback used); `info` means a significant business or lifecycle event; `debug` is diagnostic detail, off in production by default.
- **Correlation on every line:** accept or create a request ID at the edge, return it in a response header, put it and the trace ID on every log line (a child logger per request or log context), and pass them on outbound calls and in queue message metadata.
- **Name the entry point** when the same code runs from several places (HTTP request, scheduled job, replay tool, CLI): include a field such as `trigger` set where the run starts.
- **Never log secrets, tokens, passwords, session cookies, full card numbers or unnecessary personal data.** Log allowlisted fields, not whole request or response bodies; redact at the logger (for example redaction paths in the logger configuration). This is also a LaunchGuard gate 2 requirement.
- Log external calls with metadata only: target, operation, status, duration, attempt number.
- Control volume: sample high-frequency success events, keep all errors, and set retention to what operations and the privacy policy need.

## Metrics

- **For request-driven work, measure rate, errors and duration** for every endpoint, job type and outbound dependency. **For resources** (pools, queues, disks, worker threads) measure utilization, saturation (queue length, wait time) and errors.
- **Latency as histograms,** read as p50, p95 and p99. Averages hide the slow tail that users notice.
- **Bounded labels only.** Every distinct label combination is a separate time series. Use route templates (`/orders/:id`), status classes (`5xx`), dependency names and job types. Never user IDs, emails, raw URLs, request IDs or error message text; those belong in logs and traces.
- Follow the backend's naming conventions, with units in the name: Prometheus style `http_server_request_duration_seconds`, `jobs_failed_total`.
- Queues and jobs: depth, age of the oldest message, processing duration, failures, dead-letter count, time since last successful run of each scheduled job.
- Business signals that reveal silent failure: orders per minute, sign-ups, successful payments. A drop to zero is often the first sign of a broken path that raises no errors.

## Traces

- Use OpenTelemetry: initialize the SDK before other imports, enable automatic instrumentation for the HTTP server and client, database and messaging libraries, and export with OTLP to the project's backend.
- Propagate W3C Trace Context (`traceparent`, `tracestate`) across every HTTP and gRPC hop and in queue message attributes; a trace that stops at a queue cannot explain the slow half of the request.
- Add manual spans only around meaningful internal steps (`pricing.apply_discounts`, `storage.upload`), with attributes on-call will filter by. Follow the OpenTelemetry semantic conventions for attribute names. No secrets or personal data in attributes.
- Sample deliberately: a low head-based rate by default, and, where the backend supports tail-based sampling, keep all error and slow traces.

## Error tracking

- Report unhandled exceptions and failed jobs to the project's error tracker with the release version, environment and request or trace ID.
- Upload frontend source maps to the tracker privately rather than serving them publicly.
- Group noise deliberately, but never mute a new error type without looking at it.

## Objectives and alerts

- **Define service level indicators** from the user's point of view: the share of requests that succeed, the share served under a latency threshold, the share of jobs finished within their window.
- **Set objectives** with the user or owner, for example 99.9% of checkout requests succeed over 30 days. The remaining 0.1% is the error budget.
- **Page on symptoms, not causes.** Elevated error rate, latency over the objective, queue age beyond the promise, a business signal at zero. CPU at 85% or a restarted pod belongs on a dashboard or a ticket unless users are affected.
- **Alert on budget burn rate** rather than raw thresholds where the backend allows it. A widely used setup for a 30-day objective pages when the budget burns about 14 times faster than sustainable over both the last hour and the last five minutes, pages again at about 6 times over six hours (with a 30-minute short window), and opens a ticket for slow burns over days. The two windows keep alerts fast and stop them firing after recovery.
- **Every alert is actionable and links to a runbook.** Use two severities: page (users are affected now) and ticket (fix within days). An alert that is routinely acknowledged and ignored should be fixed or deleted.
- **Runbook minimum:** what the alert means, the first query or dashboard to check, common causes with their fix or mitigation, and who to escalate to. Keep runbooks next to the code (for example `docs/runbooks/<alert-name>.md`) and update them after every incident that used them.

- Choosing SLIs and objectives with the owner, error budget policies, incident response and postmortems are in `../../cloud-infrastructure/references/sre-practice.md`. Prometheus rules, Alertmanager routing, OpenTelemetry Collector pipelines and cloud alarms are in `../../cloud-infrastructure/references/monitoring-stack.md`.

## Dashboards

- One overview per service: traffic, error rate, latency percentiles, saturation, and each dependency's error rate and latency, with deploy markers.
- Lay it out to answer the on-call questions from the top of this file, not to show every metric available.

## Verify the telemetry

Instrumentation is code and can be wrong. Before calling it done, in local or staging:

- Trigger a failure and find it by request ID; confirm the fields are structured (not `[object Object]`) and that nothing sensitive appears.
- Send test traffic and check that metric series appear with the expected labels and plausible values.
- Follow one request through every component in the trace view without gaps.
- Fire each new alert once (temporarily lower the threshold in a non-production setup) and confirm it reaches the right channel with a working runbook link.

## Checks (done when)

- [ ] The on-call questions are written down and each new signal maps to one.
- [ ] Logs are structured, carry request and trace IDs, and were spot-checked for secrets and personal data.
- [ ] Rate, errors and latency histograms exist for each new endpoint, job and dependency, with bounded labels.
- [ ] Trace context crosses every hop, including queues.
- [ ] New alerts are symptom-based, tied to an objective, have a runbook and were test-fired.
- [ ] Verification steps above were run, or are marked `NOT VERIFIED` with the reason.

## Anti-patterns

- A feature with retries, queues or external calls and no new telemetry.
- `console.log` or `print` as production logging; prose log lines.
- Logging full request bodies, headers or tokens.
- User IDs or URLs as metric labels.
- Averages without percentiles.
- Paging on CPU, memory or disk while user-facing errors go unmonitored.
- Alerts without runbooks; alerts everyone has learned to ignore.
