# Production readiness review

Read this when the user asks whether a service is ready for production, what will break once real traffic arrives, or what to fix before a launch, a large migration or a move to a new platform; or when a merged change needs a risk pass before it ships. This review covers operations: deploys, configuration, health, dependencies, data safety, observability, capacity and failure handling. Security controls have their own review in `../../launchguard/GUIDE.md`; run both before a public launch. Objectives and incident practice are in `sre-practice.md`.

## How to run it

- **Evidence only.** Each item is `PASS` (evidence named), `FAIL`, `NEEDS_REVIEW`, `NOT_APPLICABLE` (with the reason) or `NOT_VERIFIED` (with the reason). A checklist ticked from memory is not a review.
- **Local first.** Read the repository, CI configuration, deploy manifests, migrations, environment documentation and runbooks. Check a deployed environment only with read-only requests, and only one the user named. Do not upload code or configuration to outside scanners or services, or run unpinned remote tools, without the user's approval of that exact tool and data flow.
- **No composite score.** A number such as 76/100 hides the one blocker that matters. Give a verdict (`READY`, `READY WITH ACCEPTED RISKS`, `NOT READY`), the blockers, and the risks someone must accept by name.

Start with cheap facts:

```bash
git status --short --branch
git log --oneline -15
git diff --stat origin/main...HEAD          # what is about to ship
ls .github/workflows deploy k8s helm 2>/dev/null
grep -rnE "process\.env\.|os\.environ|getenv\(" --include=*.{ts,js,py,go} src | head -50   # config actually read
```

## What to check

| Area | Questions | Typical evidence |
|---|---|---|
| Ownership | Who owns it, who is on call, where the runbook is | Service catalog entry, rota, runbook links in alerts |
| Build and deploy | One immutable artifact promoted through environments? Reproducible from a clean checkout? Deploy automated? | CI workflow, image digests, deploy job |
| Rollback | Fastest lever known and rehearsed? Rollback without a schema rollback? | Rollback command in the plan; expand and contract migrations |
| Configuration | Required settings validated at startup? No secret or production fallbacks in code? Test and live keys separated? | Startup schema validation, `.env.example`, secret store references |
| Health and lifecycle | Liveness, readiness and startup checks correct? Graceful shutdown on `SIGTERM`? | Probe configuration, signal handling, drain time |
| Dependencies | Timeouts on every call? Retries only for idempotent calls, with backoff and jitter? Defined behavior when a dependency is down? | Client configuration, circuit breakers, fallbacks |
| Data | Backups exist and a restore was tested and timed? Migrations tested on production-sized data? Recovery objectives agreed? | Restore drill record, migration timings, RPO and RTO |
| Async work | Jobs, queues and webhooks idempotent? Dead-letter handling? Duplicate and out-of-order delivery handled? Scheduled jobs locked and time-limited? | Idempotency keys, DLQ alarms, job locks |
| Observability | Request rate, errors and latency per endpoint; saturation; structured logs with request ids and no secrets or personal data; traces across services | Dashboards, log samples, alert rules |
| Alerting | Alerts on user-facing symptoms tied to objectives, each with a runbook and an owner | Alert rules, runbook links, paging policy |
| Capacity | Load tested at expected peak with headroom? Autoscaling limits? Connection pool totals below database limits? Cloud quotas? | Load test report, HPA settings, quota checks |
| Cost | Estimate at expected and peak load; budgets and alerts | Cost estimate (`cloud-cost.md`) |
| User-facing failure | Clear error and loading states; status page and communication plan; support path | UI states, incident comms template |
| Security and privacy | LaunchGuard run and its blockers handled | LaunchGuard report |

## Health checks that help instead of hurt

- **Liveness** answers "is this process stuck?" It checks the process itself only. A liveness check that queries the database turns a brief database blip into every instance restarting at once.
- **Readiness** answers "should this instance get traffic now?" It may check critical dependencies, with short timeouts, so a degraded instance drops out of the load balancer instead of failing requests.
- **Startup** checks give slow-starting applications time before liveness applies (`kubernetes-workloads.md`).
- A detailed status endpoint (dependency states, version, build time) is for operators: keep it internal or authenticated, and never include secrets or connection strings.
- On `SIGTERM`, stop accepting new work, finish in-flight requests and jobs within the grace period, then exit. Test it: a deploy should not produce a burst of 502s.

## Configuration that fails fast

Validate configuration once at startup and refuse to start when something required is missing or malformed, naming the setting but never printing its value:

```python
import os, sys

REQUIRED = ["DATABASE_URL", "PAYMENT_WEBHOOK_SECRET", "APP_ENV"]
missing = [name for name in REQUIRED if not os.environ.get(name)]
if missing:
    sys.exit(f"missing required settings: {', '.join(missing)}")
if os.environ["APP_ENV"] == "production" and os.environ.get("PAYMENT_MODE") != "live":
    sys.exit("production must use live payment mode")
```

No defaults for secrets, no "if unset, use the staging URL", and no debug switches that can be turned on in production by an unvalidated variable.

## Blockers

Treat any of these as `NOT READY` unless the owner explicitly accepts the risk in writing:

- No rollback path for a high-impact release, or a rollback that needs a schema rollback.
- Migrations that cannot run safely on the production data size (`../../engineering-practices/references/data-and-migrations.md`).
- Payment, fulfillment or other money-moving handlers that are not idempotent.
- Backups that have never been restored.
- No alert on the main user journey failing, or alerts without an owner.
- Health checks that would restart or remove the whole fleet when a dependency degrades.
- Secrets in code, images, client bundles or logs (LaunchGuard decides the details).
- Green CI treated as proof of readiness while the critical user path has never run end to end.

## Report

```text
Production readiness: NOT READY (2 blockers), reviewed 2026-10-14 at sha 9b1d0e2
Blockers:
  1. Webhook handler for order.paid is not idempotent (src/webhooks/orders.ts:41): duplicate deliveries ship twice.
  2. Migration 0042 adds a NOT NULL column with a volatile default on orders (48M rows): rewrites the table under lock.
Accepted risks (owner: name):
  - No load test above 2x current peak; launch traffic forecast is 1.5x.
High-value fixes:
  - Liveness probe calls the database; move the check to readiness.
Evidence checked: CI run 1823 (green), deploy/k8s/*.yaml, migrations 0040-0042, runbook.md, staging /version and /healthz
Not verified: restore time for the production backup (no drill record); third-party rate limits for the SMS provider
Next action: make order.paid idempotent with the provider event id as the key, then re-review.
```

## Checks (done when)

- [ ] Every area has a status with named evidence or a reason; nothing was marked `PASS` from assumption.
- [ ] Blockers are listed with file and line or system evidence and a concrete fix; accepted risks carry an owner's name.
- [ ] Health checks, graceful shutdown, fail-fast configuration, idempotent async work and rollback were checked specifically.
- [ ] LaunchGuard was run, or its absence is stated, for anything public-facing.
- [ ] Only read-only actions touched deployed environments.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Numeric readiness score | Verdict, blockers and named accepted risks |
| "CI is green, ship it" | Critical paths end to end; operations areas above |
| Liveness checks dependencies | Liveness for the process; readiness for dependencies |
| Backup exists, restore unknown | Timed restore drill |
| Review findings with no evidence | File, line, command output or dashboard for each |
