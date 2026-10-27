# Discrete-event simulation with SimPy

Read this when modeling systems whose state changes at discrete events: queues and service systems, manufacturing and logistics, networks, computing clusters, call centers or hospital operations (as operations models, never as medical advice). Continuous dynamics belong in `time-integration-and-stability.md`.

## When it fits, and alternatives

- SimPy (MIT license, 4.x) models processes as Python generators that wait on events: timeouts, resource requests, other processes. It is small, readable and pure Python.
- Pure Python sets the speed limit: models with millions of events take seconds to minutes. Profile before scaling up, and run replications in parallel processes rather than making one run bigger.
- Alternatives: Ciw for queueing networks, Mesa for agent-based models with spatial interaction, salabim for animation-heavy models.

## Model structure

- `env = simpy.Environment()`; processes are generator functions started with `env.process(...)`; `env.run(until=T)` advances simulated time.
- **Time is unitless.** Pick one unit (minutes, hours), write it down, and convert every rate and duration to it.
- **Resources:** `Resource(env, capacity)` (servers), `PriorityResource`, `PreemptiveResource` (higher priority interrupts the current user), `Container(env, capacity, init)` for continuous amounts (fuel, inventory levels), `Store`, `FilterStore` and `PriorityStore` for discrete items.
- Request resources with `with resource.request() as req: yield req`, so they are released even when the process is interrupted.
- **Reneging and timeouts:** `result = yield req | env.timeout(patience)`, then check `req in result`.
- **Interrupts:** `process.interrupt(cause)` raises `simpy.Interrupt` inside the target process; handle it there.
- `simpy.rt.RealtimeEnvironment` ties simulated time to wall time for hardware-in-the-loop tests and demonstrations, not for analysis.

## A model with its analytic check

```python
import math
import random
import statistics
import simpy

ARRIVAL_RATE, SERVICE_RATE = 0.8, 1.0      # customers per minute
HORIZON, WARMUP = 50_000.0, 5_000.0        # minutes

def customer(env, server, service_time, waits):
    arrived = env.now
    with server.request() as request:
        yield request
        if arrived >= WARMUP:              # discard the initial transient
            waits.append(env.now - arrived)
        yield env.timeout(service_time)

def arrivals(env, server, arrival_rng, service_rng, waits):
    while True:
        yield env.timeout(arrival_rng.expovariate(ARRIVAL_RATE))
        service_time = service_rng.expovariate(SERVICE_RATE)   # drawn at arrival: same customer, same time
        env.process(customer(env, server, service_time, waits))

def replicate(seed, servers=1):
    arrival_rng, service_rng = random.Random(seed), random.Random(seed + 1_000_003)  # separate streams
    env = simpy.Environment()
    server = simpy.Resource(env, capacity=servers)
    waits = []
    env.process(arrivals(env, server, arrival_rng, service_rng, waits))
    env.run(until=HORIZON)
    return statistics.fmean(waits)

means = [replicate(seed) for seed in range(20)]
mean = statistics.fmean(means)
half_width = 2.093 * statistics.stdev(means) / math.sqrt(len(means))   # t quantile, 19 degrees of freedom
analytic = ARRIVAL_RATE / (SERVICE_RATE * (SERVICE_RATE - ARRIVAL_RATE))  # M/M/1 mean wait in queue: 4.0 min
print(f"simulated {mean:.3f} +/- {half_width:.3f}, analytic {analytic:.3f}")
```

If the analytic value falls outside the interval, look for a modeling error before blaming chance; then extend the model (more servers, other distributions, priorities) and keep this configuration as a regression test.

## Statistics that hold up

- **Terminating or steady state?** A terminating simulation (one business day) needs replications of the full period. A steady-state question needs warm-up deletion: inspect the running output (Welch's moving-average plot) or use a truncation rule such as MSER, and record the warm-up length.
- **Replications:** independent seeds per replication; confidence intervals from the t distribution across replication means. For one long run, use batch means with batches longer than the correlation time.
- **Time-weighted averages** for state variables such as queue length and utilization: integrate over time (sum of value times duration) instead of averaging over events.
- **Consistency checks:** Little's law `L = lambda W` must hold for long-run averages; entities that entered equal those that left plus those still inside.
- **Comparing designs:** common random numbers (the same streams for arrivals and for each service step across designs) and paired differences give much tighter comparisons than independent runs. Keep a separate stream per random element and draw each entity's attributes when it is created, as the example does for service times, so the same customer gets the same draws in every design.
- **Input modeling:** fit distributions to observed data (`scipy.stats` fitting with goodness-of-fit checks), use empirical distributions when nothing fits, and run sensitivity checks on the distribution choice. Exponential times are a modeling assumption, not a default.

## Monitoring

- Record events as tuples (time, entity, event, value) in lists and analyze them after the run; avoid printing inside the event loop.
- Utilization: busy time over elapsed time, from recorded start and end times of service; queue length over time from request and release events.
- For many runs, write per-replication summaries to the campaign table (`parameter-studies-and-campaigns.md`).

## Verification and validation

- Deterministic test cases (fixed interarrival and service times) with hand-computed answers.
- Analytic queueing results for simple configurations: M/M/1, M/M/c (Erlang C), M/D/1 and M/G/1 (Pollaczek-Khinchine mean wait).
- Trace a handful of entities through the model and check each step by hand.
- Face validation with people who run the real system, and comparison with historical data when it exists, on measures that were not used to tune the model.

## Checks (done when)

- [ ] Time unit stated; all rates and durations converted to it.
- [ ] Resources acquired with context managers; interrupts handled where they can occur.
- [ ] Warm-up handled for steady-state measures; replications or batch means give confidence intervals.
- [ ] State averages are time-weighted; Little's law and entity conservation checked.
- [ ] A configuration with an analytic answer reproduces it within the confidence interval.
- [ ] Design comparisons use common random numbers and paired differences.

## Anti-patterns

- A generator that never yields, or a process function called directly instead of passed to `env.process`.
- `time.sleep` inside a model.
- A single replication reported as the answer.
- Queue length averaged per event instead of over time.
- One shared random generator for everything, so a small model change reshuffles every random draw.
