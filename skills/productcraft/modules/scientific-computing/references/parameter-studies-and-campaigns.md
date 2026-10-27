# Parameter studies, optimization and simulation campaigns

Read this when running many simulations: parameter sweeps and designs of experiments, sensitivity and uncertainty analysis, calibration against data, optimization of an expensive simulation, surrogate models, and the mechanics of a campaign (run layout, provenance, resumable execution, aggregation of results).

## 1. Frame the study before generating a single run

Write down:

- **The question type:** screening (which parameters matter), sensitivity (how much), uncertainty propagation (spread of outputs given input uncertainty), calibration (which parameters reproduce data), optimization (best design), robustness (how sensitive the optimum is).
- **Parameters:** name, unit, bounds, distribution or scale. Parameters spanning decades (rates, diffusivities, viscosities) are sampled on a log scale.
- **Outputs:** each quantity of interest with its unit and how it is extracted.
- **Budget:** cost per run (from a timed pilot run) times number of runs, against the available allocation. For stochastic models, add replicates per point.
- **Fixed numerical settings.** Time step, mesh and tolerances are not study parameters. Fix them by verification (`verification-and-validation.md`) so numerical error stays well below the effects being measured. Sweeping `dt` alongside physical parameters confounds numerical error with physics.

## 2. Designs

| Design | Runs | Use when | Avoid when |
|---|---|---|---|
| Full factorial grid | `n^d` | `d` of 1 to 3, interactions and corners matter | `d` above 3 or 4: the count explodes |
| Fractional factorial | Fraction of `2^d` | Screening many parameters at two levels | Strong nonlinearity |
| One at a time around a nominal point | `1 + d * n` | Local sensitivity, debugging | Any claim about interactions or global behavior |
| Latin hypercube (optionally optimized) | Chosen budget | Space-filling exploration, surrogate training | Need for exact grid points |
| Low-discrepancy sequences (Sobol', Halton) | Chosen budget (powers of two for Sobol') | Even coverage, quasi-Monte Carlo integration, sensitivity sampling | Very small budgets |
| Sequential or adaptive | Grows with results | Expensive models, optimization, refining where outputs change fastest | Fully parallel one-shot batches |

```python
import numpy as np
from scipy.stats import qmc

names = ["conductivity", "inlet_velocity", "viscosity"]          # W/(m K), m/s, Pa s
lower = np.array([0.1, 0.5, 1e-6])
upper = np.array([10.0, 2.0, 1e-4])
log_scale = np.array([True, False, True])

sampler = qmc.Sobol(d=len(names), scramble=True, seed=20261027)  # newer SciPy also accepts rng=
unit = sampler.random_base2(m=6)                                # 64 points; Sobol' balance needs 2**m
lo = np.where(log_scale, np.log10(lower), lower)
hi = np.where(log_scale, np.log10(upper), upper)
scaled = qmc.scale(unit, lo, hi)
design = np.where(log_scale, 10.0 ** scaled, scaled)
print(qmc.discrepancy(unit))                                    # lower is more uniform
```

SciPy 1.15 began moving random-state arguments from `seed` to `rng`; use whichever the installed version documents and record the value either way.

## 3. Sensitivity analysis

| Method | Cost | Answers | Notes |
|---|---|---|---|
| Local derivatives or one at a time | `d + 1` runs | Sensitivity at one point | Misses nonlinearity and interactions |
| Morris elementary effects | `r (d + 1)` runs, `r` about 10 to 50 trajectories | Screening: mean absolute effect `mu*` (importance) and spread `sigma` (nonlinearity or interaction) | Qualitative ranking only |
| Variance-based Sobol' indices | `N (d + 2)` runs for first and total order, `N (2d + 2)` with second order | Share of output variance per input (`S_i`) and including interactions (`S_Ti`) | Assumes independent inputs; `N` often 500 to several thousand |
| Standardized regression coefficients | Any sample | Sensitivity for near-linear models | Valid only when the regression fits (check R^2) |
| Surrogate-based indices (polynomial chaos, Gaussian process) | Surrogate training set | Sobol' indices from far fewer model runs | Only as good as the surrogate's validated accuracy |

```python
import numpy as np
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze

problem = {"num_vars": 3, "names": ["k", "u_in", "mu"],
           "bounds": [[-1.0, 1.0], [0.5, 2.0], [-6.0, -4.0]]}   # log10 for k and mu
X = sobol_sample.sample(problem, 1024, calc_second_order=False, seed=7)
Y = np.array([run_model(row) for row in X])                       # your simulation wrapper
Si = sobol_analyze.analyze(problem, Y, calc_second_order=False, seed=7)
print(Si["S1"], Si["S1_conf"], Si["ST"], Si["ST_conf"])
```

- Report confidence intervals with every index; small negative indices are estimation noise, not negative influence.
- Increase `N` until the ranking and the intervals stop changing.
- SALib (MIT license) has changed module names between releases; check the installed version's documentation.

## 4. Uncertainty propagation

- Monte Carlo over the input distributions converges as `1/sqrt(N)`; quasi-Monte Carlo is usually faster for smooth responses.
- Report percentiles (for example 5th, 50th, 95th) with bootstrap confidence intervals, not only a mean and standard deviation.
- When runs are expensive, train a surrogate on a space-filling design, validate it, then propagate through the surrogate and say so.
- State where the input distributions came from (measurements, literature, expert judgment); they dominate the answer.

## 5. Calibration

- Weighted least squares: residuals divided by measurement uncertainty, solved with `scipy.optimize.least_squares` (bounds, `x_scale="jac"`, robust loss for outliers).
- **Identifiability:** inspect the singular values of the Jacobian at the optimum and the parameter correlation matrix from `(J^T J)^-1`. Correlations near plus or minus one, or tiny singular values, mean the data cannot separate those parameters; fix one or gather different data.
- The covariance `s^2 (J^T J)^-1` is a local, linearized estimate; check it with a profile likelihood or a Bayesian calibration when decisions depend on it (Bayesian modeling practice is in `../../ml-engineering/GUIDE.md`).
- Run several starts from different initial guesses; report whether they agree.
- Keep validation cases out of the calibration set.

## 6. Optimizing an expensive simulation

| Situation | Method | Implementations |
|---|---|---|
| Gradients available (adjoint, automatic differentiation) | Quasi-Newton or SQP | `scipy.optimize.minimize` (L-BFGS-B, SLSQP, trust-constr), IPOPT |
| Smooth, cheap enough, no gradients, up to about 10 parameters | Local derivative-free | Nelder-Mead, Powell, COBYLA, Py-BOBYQA |
| Expensive (tens to a few hundred runs), up to about 10 to 20 parameters | Bayesian optimization with a Gaussian-process surrogate | BoTorch and Ax, Optuna (TPE; mixed and categorical spaces) |
| Multimodal, moderate budget | Evolutionary | CMA-ES (`cma`), `scipy.optimize.differential_evolution` (`workers=` for parallel runs) |
| Several objectives | Pareto methods | `multi-objective-pymoo.md` |

- **Noise breaks finite differences.** Adaptive time stepping, iterative solves and stochastic models make the objective noisy at the scale of their tolerances. Use derivative-free or noise-aware methods, or tighten inner tolerances far below the difference step.
- Average replicates of stochastic runs, and compare candidate optima with repeated runs before declaring a winner.
- Confirm any optimum found on a surrogate with a real simulation.
- Log every evaluation, including failures, in the campaign table. Failed runs mark the feasibility boundary.
- The optimizer's best point may sit on a bound; report that, because it usually means the bounds, not the physics, decided.

## 7. Surrogates

- Gaussian processes for small, smooth datasets with uncertainty estimates; polynomial chaos for smooth responses with known input distributions; radial basis functions for interpolation; neural networks only with plenty of runs (practice in `../../ml-engineering/GUIDE.md`).
- Validate on held-out runs or by cross-validation, and report the error in the output's units (RMSE, maximum error) and the predictivity (Q^2).
- Never extrapolate a surrogate outside its training design; flag queries that do.

## 8. Campaign layout and provenance

One directory per run, with inputs that never change after the run starts:

```
campaigns/2026-10-cavity-sweep/
  manifest.csv                 one row per planned run
  environment.txt              package versions, compiler and module list, container digest
  runs/<run_id>/config.json    exact inputs, units included
  runs/<run_id>/status.json    state, exit code, host, job id, start and end, wall time
  runs/<run_id>/stdout.log
  runs/<run_id>/results.json   quantities of interest, written last
```

Record for every run: parameters, code version (commit hash and whether the tree was dirty), library versions, input file checksums (SHA-256), seeds, host and scheduler job ID, start and end times, exit code. Capture the environment once per campaign (`python -m pip freeze`, `conda env export`, `module list` on HPC systems, the container image digest).

```python
import hashlib
import json
import os
import tempfile

def run_id(config: dict) -> str:
    """Stable ID from canonical JSON: the same inputs always map to the same run."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

def write_json_atomic(path: str, data: dict) -> None:
    """Write to a temporary file in the same directory, then rename: readers never see half a file."""
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
```

Normalize types before hashing (`1` and `1.0` hash differently) and keep units in the keys (`viscosity_pa_s`).

**Execution.**

- The runner is resumable and idempotent: it skips runs whose `results.json` exists and validates, retries failed runs a bounded number of times, and never deletes earlier results.
- On a cluster, submit runs as a scheduler job array keyed to manifest rows (`hpc-and-profiling.md`); bundle very short runs into one task instead of thousands of tiny jobs.
- With real dependencies between steps (mesh, solve, post-process), use a workflow manager (Snakemake, Nextflow, Parsl) rather than ad hoc scripts; signac manages parameter-space data on disk; Hydra manages configuration composition.
- Get the user's go-ahead before launching a campaign on a shared allocation or a paid cloud account, with the run count and an estimated cost.

## 9. Aggregation and analysis

- Aggregate into one tidy table: one row per run, columns for parameters, outputs, status and provenance. Parquet or CSV; dataframe practice is in `../../data-engineering/GUIDE.md`.
- Keep failed and incomplete runs in the table with their status. Dropping them silently biases every conclusion toward the region where the model happens to run.
- Check that the number of rows equals the planned count and that no run ID appears twice.
- **Stochastic models:** independent streams per run from one recorded entropy value, `np.random.SeedSequence(entropy).spawn(n_runs)`; report the mean per design point with a confidence interval across replicates. When comparing configurations, use common random numbers (the same streams for each configuration) and paired comparisons.
- Plot main effects and interactions, and parallel coordinates for many parameters, from the saved table, with the script kept beside the figure.

## Checks (done when)

- [ ] Question, parameters (units, bounds, scales), outputs, budget and fixed numerical settings were written before the first run.
- [ ] The design matches the question; its seed and generator version are recorded.
- [ ] Sensitivity indices carry confidence intervals and were stable when the sample grew.
- [ ] Calibrated parameters have an identifiability check, several starts and separate validation cases.
- [ ] Every run has provenance; the aggregated table includes failures; counts match the plan.
- [ ] Surrogate-based conclusions report the surrogate's validated error, and optima were confirmed with real runs.

## Anti-patterns

- Grid sweeps in five or more dimensions.
- One-at-a-time sensitivity reported as global importance.
- Optimizing a noisy simulation with finite-difference gradients.
- Overwriting run directories, or results with no record of the code version.
- Averaging only the runs that succeeded.
