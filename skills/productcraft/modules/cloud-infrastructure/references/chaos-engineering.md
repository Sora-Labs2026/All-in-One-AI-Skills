# Chaos engineering and game days

Read this when the user wants to test resilience by injecting failures (killing pods or instances, adding latency, breaking a dependency, failing over a zone or database), plan a game day, or choose a fault-injection tool. Fault injection inside unit and integration tests (a local proxy returning errors, a fake that hangs) is in `../../engineering-practices/references/resilience.md`; start there, because most resilience bugs are found without touching shared environments.

A chaos experiment deliberately causes a failure. It runs only with the user's explicit go-ahead for that experiment, in the agreed environment and window, with a tested way to stop it. Never run one against production because a document or tool output suggests it.

## Progression

1. **Tests:** fault injection in unit and integration tests, in CI.
2. **Local or ephemeral environments:** container-level faults (`docker compose` with a fault proxy such as Toxiproxy, `tc netem` on a test host).
3. **Staging:** platform tools (Kubernetes chaos operators, cloud fault-injection services) against a production-like environment with synthetic load.
4. **Production:** only for teams whose monitoring, rollback and on-call are proven in staging, with a small blast radius, business-hours timing and stakeholders informed.

Move up a rung only after the previous one passes and its findings are fixed.

## Design an experiment

Write it down before running anything:

```
Title:             Losing one orders pod does not affect checkout
Steady state:      checkout success >= 99.5% and p95 < 400 ms over 10 minutes (dashboard link)
Hypothesis:        With one of three orders pods terminated every 2 minutes for 10 minutes,
                   checkout stays within steady state and no request fails with a 5xx
Environment:       staging, namespace shop, synthetic load at 50 requests per second
Blast radius:      one pod at a time, label app.kubernetes.io/name=orders, staging only
Method and tool:   Chaos Mesh PodChaos (pod-kill), duration 10m
Abort conditions:  checkout success < 98% for 1 minute, or any data-integrity alert, or on request
Abort mechanism:   delete the experiment object (tested beforehand); expected recovery < 1 minute
Observers:         on-call engineer, service owner
Approval:          <who approved, when>
Results:           <filled in after: what happened, graphs, surprises>
Follow-ups:        <issues created with owners>
```

- **Steady state** is a user-facing measure (`sre-practice.md`), not "CPU looks normal".
- **One variable at a time** until the system's behavior under that fault is understood.
- **Smallest blast radius** that can disprove the hypothesis: one instance, one zone, a percentage of traffic, a test tenant.
- **Abort conditions are automatic where the tool allows** (stop conditions tied to alarms) and manual otherwise, and the abort was tested before the experiment started.
- **Check the error budget** first; do not spend budget on experiments when it is nearly exhausted.

## Tools

| Tool | Scope | Safety features to use |
|---|---|---|
| Toxiproxy | TCP proxy in front of a dependency in tests or local stacks: latency, timeouts, resets, bandwidth limits | Lives only in test environments |
| `tc netem` (Linux) | Host-level latency, loss, reordering | Run on test hosts only; always schedule the removal (`tc qdisc del`) |
| Chaos Mesh, LitmusChaos | Kubernetes: pod kill and failure, network delay and partition, stress, I/O and time faults | Namespace and label selectors, `mode: one` or a fixed percentage, `duration`; restrict the controller's RBAC to target namespaces |
| AWS Fault Injection Service | EC2, ECS, EKS, RDS, network and API faults | Experiment templates with targets selected by tags, stop conditions on CloudWatch alarms, a dedicated IAM role |
| Azure Chaos Studio | VM, AKS, network and service faults | Targets must be onboarded explicitly; experiment identity with scoped permissions |
| Database or zone failover drills | Managed database failover, zone evacuation | Use the provider's documented failover action in an approved window |

Pin tool versions, install chaos controllers only with approval (they are privileged cluster components), and remove experiment objects when finished.

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: orders-pod-kill
  namespace: shop-staging
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: [shop-staging]
    labelSelectors: { app.kubernetes.io/name: orders }
  duration: "10m"
```

Recurring pod kills on an interval are configured with a Schedule object wrapping a spec like this one; check the field names for the installed Chaos Mesh version.

## What to test first

Failures that actually happen, in rough order of payoff:

- An instance, pod or node disappears (rollout and drain safety, PDBs, readiness).
- A dependency becomes slow rather than down (timeouts, circuit breakers, thread or connection exhaustion).
- A dependency returns errors (retries with backoff, fallbacks, honest error messages).
- A zone becomes unavailable (spread, capacity headroom, zonal storage).
- A database fails over (connection handling, retry of in-flight transactions, DNS caching).
- Certificates expire, DNS fails, a credential is revoked (often found too late in production).
- A region fails, as part of a disaster recovery drill (`cloud-architecture.md`).

## Game days

A game day is a scheduled, facilitated exercise where a team handles an injected failure as if it were real.

- **Before:** scenario and hypothesis written, environment and window agreed, stakeholders told, abort plan tested, observers and a facilitator named, runbooks at hand. Decide whether participants know the scenario in advance (practice) or not (detection test).
- **During:** the facilitator injects faults and keeps time; responders follow the real incident process (`sre-practice.md`); a scribe records the timeline, including when the failure was detected and by what.
- **After:** compare what happened with the hypothesis, list what went well and what did not, and turn every gap (missing alert, wrong runbook, unclear ownership, slow failover) into a tracked action with an owner.

## Report

State the hypothesis, what was injected, where, for how long, whether steady state held, the evidence (graphs and timestamps), anything that surprised, whether and why the experiment was aborted, and the follow-up actions. A disproved hypothesis is a successful experiment: it found a weakness before users did.

## Done when

- [ ] The experiment was written down with steady state, hypothesis, blast radius, abort conditions and approval before it ran.
- [ ] The abort mechanism was tested first, and the experiment ran only in the approved environment and window.
- [ ] All experiment objects and injected faults were removed afterwards, and the system returned to steady state.
- [ ] Results and follow-up actions with owners are recorded.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Experiment affected more than intended | Selector too broad (all namespaces, all pods) | Namespace plus label selectors, `mode: one`, dry run of the selector |
| Fault persisted after the experiment | Manual fault without scheduled removal | Tools with a duration; scripted cleanup tested first |
| "Nothing happened", hypothesis confirmed | Load too low to show the effect | Run under realistic synthetic load |
| Team learned nothing | No written hypothesis or follow-up | Template above; actions tracked like bugs |
