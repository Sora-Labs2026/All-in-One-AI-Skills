# Watching canaries and verifying deploys

Read this when a release is rolling out in stages and someone must decide whether to advance, hold or roll back; when you set up automated canary analysis (Argo Rollouts, Flagger, a mesh or load balancer that splits traffic); or when you verify a deploy right after it lands. The rollout plan template, deploy strategies and feature flags are in `../../engineering-practices/references/ci-and-release.md`; the tools in `kubernetes-delivery.md`; service objectives in `sre-practice.md`.

**Roles.** The agent watches, compares and reports. Advancing, pausing and rolling back are the user's decisions, or automation the user configured and approved in advance. Watching has a budget too: an agreed interval and duration, and stop conditions written before the rollout starts.

## Before traffic moves

- **Per-version signals.** Every metric, log line and error report carries the version (commit, image digest or pod template hash). Without that label the canary cannot be told apart from the stable version, and the comparison is impossible.
- **What to watch,** chosen from the change and the service objective: request error ratio and latency (p50, p95, p99) per version; saturation (CPU, memory, connection pools, queue depth); the traffic share actually reaching the canary; one or two business signals (checkouts, sign-ins, messages sent); new error signatures in logs and the error tracker; client-side errors and failed asset loads for web front ends; load on shared dependencies (database, caches, third-party APIs).
- **Thresholds agreed in advance:** for example "error ratio no more than 0.2 percentage points above stable; p95 no more than 20% above stable; any data-integrity error rolls back". Numbers belong to the owner; write them into the plan.

## Compare against the right baseline

- Compare canary with stable **over the same time window**, not with last week or with a dashboard from before the deploy. Traffic mix, time of day and incidents elsewhere move every metric.
- New pods start cold (empty caches, unwarmed JIT, new connection pools). When the canary is small, a fresh baseline group (the old version, same size, started at the same time) cancels that warm-up effect; some analysis tools do this for you.
- Make sure both groups receive comparable traffic: sticky sessions, header-based routing or a canary limited to internal users skew the comparison.

## Is there enough evidence?

A small canary on a quiet service may see too few events to detect anything. Estimate before trusting a green result:

```
expected bad events in canary = request rate x canary share x window x baseline error ratio
example: 40 req/s x 5% x 30 min (1,800 s) x 0.1% = about 3.6 errors
```

With about four expected errors, even a doubling to eight is hard to tell from chance. Then lengthen the bake time, raise the weight one step, rely on more frequent signals (latency), or report the stage as underpowered rather than as healthy. Check at fixed intervals with a rule such as "two failed checks in a row", not by re-testing every minute until something looks significant.

## Automated analysis

Encode the agreed comparison so the controller pauses or rolls back by itself. With Argo Rollouts, an `AnalysisTemplate` compares canary and stable from Prometheus (label names depend on how your scrape configuration maps pod labels):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: error-ratio-vs-stable
spec:
  args:
    - name: canary-hash
    - name: stable-hash
  metrics:
    - name: error-ratio-increase
      interval: 5m
      count: 6                                  # 30 minutes of evidence per analysis step
      failureLimit: 1
      successCondition: result[0] <= 0.002      # owner's tolerance: +0.2 percentage points
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc:9090
          query: |
            ( (sum(rate(http_requests_total{pod_template_hash="{{args.canary-hash}}",code=~"5.."}[5m])) or vector(0))
              / sum(rate(http_requests_total{pod_template_hash="{{args.canary-hash}}"}[5m])) )
            -
            ( (sum(rate(http_requests_total{pod_template_hash="{{args.stable-hash}}",code=~"5.."}[5m])) or vector(0))
              / sum(rate(http_requests_total{pod_template_hash="{{args.stable-hash}}"}[5m])) )
```

The rollout passes `valueFrom: {podTemplateHashValue: Latest}` and `{podTemplateHashValue: Stable}` as the two arguments in its analysis step. Flagger expresses the same idea with metric thresholds, step weights and a failed-check limit on its `Canary` resource.

- Test the analysis in staging with a deliberately broken build and confirm it rolls back. An analysis that has never failed has not been tested.
- Keep weights, pauses and thresholds in Git with the rest of the delivery configuration.
- Changing analysis or rollout settings on production is itself a change: prepare the diff and ask.

## Verify every deploy

Whether or not there is a canary, run read-only checks as soon as a version is live:

```bash
curl -fsS https://app.example.com/version                     # expected commit or digest
curl -fsS -o /dev/null -w '%{http_code} %{time_total}s\n' https://app.example.com/healthz
curl -sSI https://app.example.com/assets/app.3f9c2e.js | grep -iE '^(HTTP|content-type|cache-control)'
curl -sSN --max-time 15 -H 'Accept: text/event-stream' https://app.example.com/events | head -n 5   # first event or heartbeat
```

- **Version:** the running version is the one you meant to ship, on every instance or region.
- **Critical paths:** a scripted journey through the few flows that matter, with a dedicated test account and test-mode payments, never a real customer's account.
- **Static assets:** hashed files return 200 with the right `Content-Type` and long-lived caching; HTML is not cached long. Keep the previous build's assets available during and after the rollout, because browsers holding the old HTML still request old chunk names; removing them causes "failed to load chunk" errors that look like a broken release.
- **Streaming endpoints:** server-sent events and WebSockets connect and deliver a first event or heartbeat. Long-lived connections stay on old instances until drained; give them a drain period and expect reconnect spikes.
- **Edges:** TLS certificate and chain valid, redirects intact, security headers and content security policy not blocking the new build's resources.
- **Errors:** the error tracker shows the new release with no new issue types; client-side error counts per release are flat.

## A watch loop that stays safe

- Interval, duration and checks agreed up front (for example every 5 minutes for 2 hours, or until the final stage completes). Stop when the window ends, when a rollback trigger fires, or when the user says so.
- Read-only checks at normal request volume; no load tests against production without explicit permission (`../../engineering-practices/references/performance.md`).
- On a rollback trigger: report immediately with the evidence, and roll back only if the user pre-approved that action or the controller does it automatically. Then keep the dashboards and logs for the review.

## Report

```text
Release:   web 2026.10.14-2 (sha 3f9c2e1), stage 25%, bake 40 min of 60
Signal            Stable     Canary     Delta        Threshold          Verdict
Error ratio       0.11%      0.13%      +0.02 pp     <= +0.2 pp         ok
p95 latency       182 ms     190 ms     +4%          <= +20%            ok
Checkouts/min     41.0       40.2       -2%          >= -5%             ok
New error types   -          0          -            0                  ok
Evidence:   canary served 62,000 requests; about 70 errors expected at baseline, enough to detect a doubling
Smoke:      version, health, assets, SSE heartbeat, checkout journey (test account): pass
Not verified: mobile app clients (no per-release metrics yet)
Recommendation: advance to 50% at 15:10 if the next two checks pass
```

## Checks (done when)

- [ ] Metrics, logs and errors carry the version; thresholds and the watch window were agreed before traffic moved.
- [ ] Canary compared with stable over the same window; the evidence was large enough, or the stage was reported as underpowered.
- [ ] Automated analysis, where used, was shown to roll back a bad build in staging.
- [ ] Post-deploy smoke checks covered version, health, critical paths, assets, streaming endpoints and edges.
- [ ] Every advance or rollback on production was the user's decision or pre-approved automation, and the report lists what was not verified.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Comparing the canary with yesterday | Same-window comparison with stable |
| "No errors" from a canary that saw 200 requests | Expected-events estimate; longer bake or higher weight |
| One dashboard for all versions | Version label on every signal |
| Chunk-load errors after deploy | Keep previous assets; long cache only on hashed files |
| Analysis never tested | Fail a deliberately broken build in staging |
| Checking significance every minute | Fixed intervals and consecutive-failure rules |
