# Benchmarking methodology: timings you can defend

Read this when someone claims a change made code, a query, a model or a pipeline faster or slower; when you compare libraries, configurations, hardware or model variants on speed, throughput or memory; when you set up performance regression checks in CI; or when timing numbers go into a report. The measure-profile-change loop and web performance live in `../../engineering-practices/references/performance.md`; scaling studies and HPC profilers in `../../scientific-computing/references/hpc-and-profiling.md`; model quality comparisons in `evaluation-and-leakage.md`.

## Decide what you are measuring

- **The question,** in one sentence: "Is the new parser at least 10% faster on our invoice corpus?" A benchmark without a question produces numbers nobody can act on.
- **The metric:** latency distribution (p50, p95, p99) for request paths; throughput at a stated latency target for services; CPU time for compute-bound code; peak memory or allocations for memory-bound code; cost per unit (per thousand predictions, per gigabyte processed) when money decides.
- **Cold or warm:** first-call latency (serverless, command-line tools, model loading) and steady-state latency are different questions. Measure the one that matters and say which.
- **The practical threshold:** the smallest change worth acting on, agreed before measuring. It turns "statistically significant 0.3%" into "irrelevant" and protects against chasing noise.

## Control the conditions

- Same machine type, operating system, runtime and library versions, build mode (release builds, the same compiler flags) and input data for both sides. Record them with the commit hashes.
- A quiet machine: no other benchmarks or heavy jobs, a laptop on mains power, nothing syncing. CPU frequency scaling, turbo and thermal throttling move results by more than many optimizations; on dedicated hosts consider a fixed performance governor, and on laptops expect drift.
- Cloud machines share hardware with others. Run both versions on the same instance, interleaved, rather than on two instances.
- Realistic inputs: the size and distribution of production data (not sorted when production is random, not tiny enough to fit in a CPU cache when production does not).

## Warm-up and repetition

- Warm-up effects: just-in-time compilers (JVM, V8, .NET, PyPy), CPU and operating-system caches, database buffer pools, connection pools, lazy initialization, GPU context creation, kernel autotuning and `torch.compile` compilation. Discard warm-up iterations, and check that the remaining values do not still trend downward.
- Repeat many times. Timings are right-skewed (occasional pauses from garbage collection, scheduling and interrupts), so look at the distribution, not only the mean. Report the median with its spread, or a ratio of geometric means with a confidence interval.
- **Interleave** the two variants (A, B, A, B or a shuffled order) so slow drift affects both equally. Running all of A, then all of B, confounds the change with whatever drifted in between.
- Multimodal results (two clusters of timings) mean something else is going on: frequency changes, a cache that sometimes misses, garbage collection in some runs. Investigate before comparing.

## Compare with statistics, not eyeballs

Two independent samples of timings, one per variant:

- **Welch's t-test on log timings** gives the ratio of geometric means (candidate / baseline) with a confidence interval. Logs suit timings because effects are multiplicative and the distribution is skewed.
- **Mann-Whitney U** is a rank test that tolerates outliers; use it as a cross-check.
- **Bootstrap interval of the ratio of medians** makes few assumptions and reads naturally ("median about 11% lower, 95% interval 9% to 13%").
- **Verdicts:** an improvement or regression only when the whole interval lies on one side of 1 (and beyond the practical threshold, if one was set). "No significant difference" is not "equal": equivalence needs the whole interval inside the threshold band. Many benchmarks compared at once need the multiplicity caution in `statistical-inference.md`.
- Paired measurements (the same input timed under both variants) can use the paired tools in `../scripts/compare_scores.py` on per-input differences.

The bundled helper does the unpaired comparison:

```bash
# Two files with one timing per line (seconds or milliseconds, the same unit in both)
python3 <productcraft>/modules/ml-engineering/scripts/bench_compare.py base.txt new.txt --drop-first 3 --threshold 2

# hyperfine export with two commands; fail the job on a regression beyond 5%
hyperfine --warmup 5 --runs 40 --export-json bench.json 'old/bin/tool in.dat' 'new/bin/tool in.dat'
python3 <productcraft>/modules/ml-engineering/scripts/bench_compare.py bench.json bench.json --select-a 0 --select-b 1 --threshold 5 --fail-on-regression

# Throughput (higher is better), JSON for CI
python3 <productcraft>/modules/ml-engineering/scripts/bench_compare.py --a-values 912,905,931,899 --b-values 980,1002,975,990 --higher-is-better --json
```

It reads plain number lists, CSV columns, hyperfine exports and pytest-benchmark exports saved with their raw data, and reports both samples' statistics, the three comparisons, a verdict and hints (drift across run order, outliers, noisy samples). Exit codes: 0 computed, 1 when `--fail-on-regression` or `--require-improvement` trips, 2 bad input.

## Tools that already do the hard parts

| Ecosystem | Tool | Notes |
|---|---|---|
| Any command | `hyperfine --warmup N --runs M --export-json` | Interleave by listing both commands; `--prepare` to reset caches between runs when cold runs matter |
| Python | `pyperf`, `pytest-benchmark` (`--benchmark-save-data` keeps raw timings), `timeit` | `pyperf system tune` reduces noise on dedicated machines |
| Go | `go test -bench . -count 10` plus `benchstat old.txt new.txt` | `benchstat` does the statistics |
| Rust | `criterion` | Warm-up, outliers and comparisons built in |
| Java and JVM | JMH | Forks, warm-up iterations and `Blackhole` against dead-code elimination |
| .NET | BenchmarkDotNet | |
| C and C++ | Google Benchmark; `perf stat -r 10` | |
| PyTorch | `torch.utils.benchmark.Timer` | Handles CUDA synchronization and warm-up |

## Microbenchmark traps

- **Dead code and constant folding:** compilers delete work whose result is unused or computable at build time. Consume the result (a black hole, a checksum printed at the end).
- **Asynchronous work:** GPU kernels and many I/O calls return before the work finishes. Synchronize (`torch.cuda.synchronize()`, awaiting futures) before stopping the clock, or time with device events.
- **Caching between runs:** the second read of a file comes from the page cache; the second query hits the buffer pool. Decide whether that is the scenario you mean.
- **Timer and harness overhead:** use a monotonic, high-resolution clock (`time.perf_counter_ns`), and batch very short operations so one measurement covers many calls.
- Microbenchmarks only for code a profile showed is hot; a 3x faster function that takes 1% of the request changes nothing.

## Load tests and latency percentiles

- A closed-loop load generator (each virtual user waits for its response before sending the next) sends less when the server stalls, so it misses exactly the slow periods ("coordinated omission"). For latency under load, use a constant arrival rate (k6's arrival-rate executors, wrk2) and record full latency histograms.
- Percentiles do not average: combine histograms, then take the percentile. Never average p99s across instances or intervals.
- Exclude ramp-up from the measurement window; check that the load generator itself is not saturated; run against an environment sized like production. Load tests against shared, production or third-party systems need explicit permission and a cost check.

## Regression checks in CI

- Shared CI runners are noisy. Build both the base and the candidate in the same job, run them interleaved on the same machine, and gate on the interval plus a threshold, not on one run against a stored number.
- For CPU-bound code, instruction counts (from `perf stat -e instructions` or a Valgrind-based counter) are far less noisy than wall time and catch most algorithmic regressions; confirm big changes with wall time.
- Keep a history and look for step changes over many commits; one-off alerts on single runs train people to ignore them.

## Report

```text
Question:    Does the streaming parser cut p50 parse time on the 2026-09 invoice sample (n=500 files)?
Setup:       c7i.2xlarge, Ubuntu 24.04, Python 3.12.6, release build; base 4e1a9c0, candidate 9b2f113; interleaved; 3 warm-up runs dropped
Samples:     40 runs each; base median 812 ms (IQR 798-830), candidate median 701 ms (IQR 690-716)
Comparison:  ratio of geometric means 0.864, 95% CI [0.851, 0.877]; Mann-Whitney p < 1e-10
Verdict:     improvement beyond the agreed 5% threshold (about 13.6% faster)
Caveats:     single instance type; cold-start time not measured
Raw data:    bench/2026-10-14/*.json
```

## Checks (done when)

- [ ] Question, metric, cold or warm, and practical threshold written down before measuring.
- [ ] Both variants ran on the same machine and inputs, interleaved, with warm-up discarded and the environment recorded.
- [ ] Results reported as distributions with intervals; the verdict follows the interval and the threshold.
- [ ] Traps checked: dead code, asynchronous work, caching, harness overhead, coordinated omission.
- [ ] Raw timings saved so someone else can recompute the comparison.

## Pitfalls

| Pitfall | Fix |
|---|---|
| One run each, "B is 4% faster" | Many interleaved runs; interval and threshold |
| Cold baseline versus warm candidate | Same warm-up for both, or measure both cold |
| All A runs, then all B runs | Interleave |
| Averaging p99 across servers | Merge histograms |
| Closed-loop load test under stall | Constant arrival rate |
| CI gate on a stored number from another machine | Base and candidate in the same job |
