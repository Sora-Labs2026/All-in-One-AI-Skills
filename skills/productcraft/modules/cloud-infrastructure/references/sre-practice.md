# SRE practice: objectives, error budgets, incidents, toil and capacity

Read this when you define or revise SLIs and SLOs, write an error budget policy, respond to or write up an incident, set up on-call, reduce operational toil, or plan capacity. How to instrument services and the standard burn-rate alert setup are in `../../engineering-practices/references/observability.md`; this file covers the decisions and practices around them. Alert and dashboard mechanics are in `monitoring-stack.md`.

Objectives and policies are agreements between engineering and the product owner. The agent drafts them with real data and marks every number the owner has not confirmed.

## Choosing SLIs

An SLI is the ratio of good events to valid events, measured as close to the user as possible.

| Service kind | Typical SLIs |
|---|---|
| Request and response (API, web) | Availability: share of requests not failing with a server error; latency: share served faster than a threshold (for example 300 ms) |
| Data processing (pipelines, queues) | Freshness: share of data processed within N minutes; correctness: share of outputs passing validation |
| Scheduled jobs | Share of runs that complete successfully within their window |
| Storage | Durability and share of reads returning the latest write |

- Measure at the load balancer or edge (or with synthetic probes) rather than inside the service, so failures that never reach the service still count.
- Decide what counts as valid: exclude health checks, and decide explicitly whether client errors (4xx) count. Rate limiting the user caused is usually not a failure; a 429 because the service is overloaded is.
- Use thresholds rather than percentiles for latency SLIs ("share under 300 ms"); they aggregate correctly and turn directly into an error budget.

## Choosing SLOs

- Start from what users notice and from history: if the service delivered 99.95 percent last quarter and nobody complained at 99.9 percent, an objective of 99.9 percent leaves room to ship.
- Never promise 100 percent. Every extra nine costs roughly an order of magnitude more effort and blocks change.
- Dependencies cap you: a service cannot be more available than the critical dependencies it calls in series, unless it degrades gracefully without them.
- Use a rolling window (28 or 30 days) for operational decisions; calendar periods suit reporting. An SLA (a contractual promise with penalties) should be looser than the internal SLO.
- Write the SLO document: SLI definition with the exact query, objective, window, owner, data source, exclusions, and the date it will be reviewed.

### Error budget arithmetic

Error budget = 1 minus the objective. Over a 30-day window:

| Objective | Allowed bad share | Equivalent full outage per 30 days |
|---|---|---|
| 99% | 1% | about 7.2 hours |
| 99.5% | 0.5% | about 3.6 hours |
| 99.9% | 0.1% | about 43 minutes |
| 99.95% | 0.05% | about 22 minutes |
| 99.99% | 0.01% | about 4.3 minutes |

Burn rate is the observed bad share divided by the allowed bad share; a burn rate of 1 spends the budget exactly over the window. The multi-window burn-rate alerts in the observability reference page on fast burns and ticket slow ones. A 99.99 percent objective leaves too little budget for humans to respond before it is gone; it needs automated mitigation.

## Error budget policy

A short written agreement on what happens as budget is spent, signed off by the product owner. It typically covers:

- **Budget healthy:** normal release pace.
- **Budget mostly spent:** riskier changes need extra review or a slower rollout; reliability work moves up.
- **Budget exhausted:** releases limited to fixes and reliability work until the window recovers, with named exceptions (security fixes, legal deadlines) and who may grant them.
- **One incident consuming a large share** (for example over 20 percent) triggers a postmortem with tracked actions.
- **Budget consistently unspent:** the objective may be too loose, or the team can take more release risk.

The policy is only real if it was agreed before it is needed. Do not invent thresholds or approvers; propose them as a draft.

## Incident response

Mitigate first, diagnose second. Restoring service (rollback, feature flag off, failover, shedding load) comes before finding the root cause.

1. **Declare** when user impact is likely, even if unsure. Assign an incident commander who coordinates and does not debug; add an operations lead, a communications lead and a scribe for larger incidents.
2. **Set severity by user impact**, with definitions agreed in advance (for example SEV1: many users cannot use a core function; SEV2: degraded or a subset affected; SEV3: minor, with a workaround).
3. **Communicate on a rhythm** (for example every 30 minutes for SEV1) to stakeholders and, where applicable, a status page: what is affected, what is being done, next update time. Say what you know, not what you hope.
4. **Keep a timeline** with timestamps in UTC: detection, actions taken, their effect, mitigation, resolution.
5. **Preserve evidence**: dashboards, logs, the deploy and config change history around the start time. Do not delete or rotate logs during the incident.
6. **Resolve** when the SLI is back within objective and stable, then schedule the postmortem.

The agent's role in a live incident: gather evidence read-only, propose mitigations with their risk and rollback, and run a mitigation only when the incident commander or the user approves that specific action. Security incidents follow a separate path (containment, evidence preservation, legal and notification duties); escalate them to the security owner immediately.

## Postmortems

- Blameless: describe what people knew and why their actions made sense at the time. The question is how the system allowed the failure, not who caused it.
- Contents: summary, impact (duration, users or requests affected, error budget consumed), timeline, contributing factors (usually several), what went well, where we got lucky, and action items.
- Action items are specific, owned, dated and tracked in the normal backlog, and they favor prevention and detection improvements over "be more careful". Review completion in a later meeting.
- Write facts from the timeline and evidence. Do not invent quotes, numbers or causes; mark open questions as open.

## On-call health

- Every page is actionable, linked to a runbook, and tied to user impact. Track pages per shift; a sustained rate above a couple of incidents per shift burns people out and degrades response.
- Review alerts regularly: delete or demote alerts that were ignored, and add the missing alert for every incident users reported first.
- Hand over with a written summary of open issues. Give on-call engineers the access they need in advance, through break-glass procedures that are logged.

## Toil

Toil is manual, repetitive, automatable work that scales with the service and leaves nothing lasting behind: restarting a stuck worker, resizing a volume by hand, rotating a certificate manually.

- Measure it (log tickets and interrupts for two weeks) before fixing it, and rank by time spent times frequency.
- Automate the top items with the same discipline as product code: tests, review, idempotency, dry-run modes, logging, and a kill switch.
- Self-healing automation (automatic restarts, failovers, scaling) must have rate limits and escalate to a person after a few attempts; automation that loops can turn a small fault into a large one. Record every automated action where on-call can see it.
- Fix the cause when possible; automation that hides a recurring fault is still a fault.

## Capacity planning

- Know the current headroom: peak utilization of the binding resource (CPU, memory, connections, queue throughput, quotas) against what triggers degradation, not against 100 percent.
- Forecast demand from business drivers the owner provides (launches, seasonality, growth) plus trend. Little's law helps size concurrency: in-flight work = arrival rate times time in system.
- Load-test to find the breaking point and the first resource to saturate, in a non-production environment with approval (`../../engineering-practices/references/performance.md`).
- Check cloud quotas and limits (instances per region, IP addresses, API rate limits, GPU availability) well before launches and in the disaster recovery region; raising them can take days.
- Keep N+1 (or zone-loss) capacity for production: losing one zone or node must not breach the objective.

## Done when

- [ ] Each objective has an SLI query, a window, an owner, exclusions and the owner's agreement, with unconfirmed numbers marked.
- [ ] The error budget policy is a draft or an agreed document, never invented thresholds presented as policy.
- [ ] Incident actions taken by the agent were approved individually, and the timeline is factual.
- [ ] Postmortem action items are owned, dated and tracked; capacity numbers cite their measurement.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| SLO always green while users complain | SLI measured inside the service, or excludes the failing path | Measure at the edge or with probes; include the path |
| Teams ignore the budget | Policy never agreed with the product owner | Agree it before the next incident |
| Pager fatigue | Cause-based alerts and duplicates | Symptom-based burn-rate alerts; prune regularly |
| Postmortem with "human error" as root cause | Blame framing | Ask what made the error easy and the impact large |
| Automation made the outage worse | No rate limit or escalation | Cap attempts, add a kill switch, alert a person |
