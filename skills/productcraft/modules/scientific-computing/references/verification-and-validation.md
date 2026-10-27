# Verification, validation and run health

Read this before trusting any simulation result: proving a solver computes what it claims (code verification), estimating the numerical error of a specific result (solution verification), comparing with experiments (validation), and checking a run before, during and after it executes. Also read it when a run crashed, produced NaN, or "looks wrong".

## Three questions, three activities

| Question | Activity | Evidence |
|---|---|---|
| Are the equations solved correctly? | Code verification | Observed order of accuracy matches the formal order on an exact or manufactured solution |
| How large is the numerical error in this result? | Solution verification | Iterative, time-step and grid convergence; Richardson extrapolation; grid convergence index (GCI) |
| Are these the right equations for reality? | Validation | Comparison with experimental data, with numerical, input and measurement uncertainty |

The vocabulary follows common engineering practice (the ASME V&V 10 and V&V 20 standards, and the code and solution verification literature). Never skip to validation: agreement with an experiment from an unverified code can be two errors cancelling.

## 1. Code verification

**Exact solutions** where they exist: Fourier modes of the heat equation, Couette and Poiseuille flow, the 2D Taylor-Green vortex, the Sod shock tube (exact Riemann solution), the harmonic oscillator, Kepler orbits (energy and angular momentum), Rabi oscillations.

**Method of manufactured solutions (MMS)** when they do not:

1. Pick a smooth function that exercises every term (all derivatives used by the equations are non-zero), stays in the physically admissible range (positive densities and temperatures) and has order-one magnitudes. Avoid symmetries that make terms vanish.
2. Apply the continuous operator to it symbolically to get a source term.
3. Add the source to the solver, impose boundary and initial conditions from the manufactured function, and solve on at least three or four systematically refined grids.
4. Compute error norms against the manufactured function and the observed order.

```python
import sympy as sp

x, t, a, nu = sp.symbols("x t a nu", real=True)
u = sp.sin(sp.pi * x) * sp.exp(-t) + sp.Rational(1, 4) * sp.cos(2 * sp.pi * x) * (1 + t)  # manufactured
source = sp.diff(u, t) + a * sp.diff(u, x) - nu * sp.diff(u, x, 2)   # for u_t + a u_x - nu u_xx = s
s_func = sp.lambdify((x, t, a, nu), sp.simplify(source), modules="numpy")
u_exact = sp.lambdify((x, t), u, modules="numpy")
```

- **Separate space and time.** For the spatial order, take time steps small enough that time error is negligible (or refine `dt` with `dx` at the ratio that keeps the expected error balance); for the temporal order, use a fine grid and refine `dt`.
- **Use proper norms:** discrete L2 weighted by cell size, `sqrt(sum(e_i^2 * dV_i) / V)`, and L-infinity. A lower order in L-infinity than in L2 points at boundaries or singular points.
- **Run the order check.** For a scalar quantity with a known exact value: `python3 <productcraft>/modules/scientific-computing/scripts/convergence_order.py --h 0.1,0.05,0.025,0.0125 --values <computed values> --exact <exact value> --expected-order 2`. For a field, pass the error norms themselves: `--values <L2 errors> --errors --expected-order 2`.
- Observed order matching the formal order on every term is the evidence. An order that is too low points at a bug, a boundary closure, insufficient smoothness, or a pre-asymptotic grid; one that is too high usually means error cancellation in a symmetric test.

Keep the MMS case as a regression test in the project's suite, with a tolerance on the observed order, so it runs on every change.

## 2. Solution verification

Order of operations: iterative error first, then time, then space.

1. **Iterative convergence.** Tighten nonlinear and linear tolerances until the quantity of interest stops changing; keep iteration error at least two orders below the discretization error.
2. **Time-step convergence.** Three or more step sizes with the same grid.
3. **Grid convergence.** Three or more systematically refined grids, refinement ratio at least 1.3 (`discretization-and-meshes.md`).

`../scripts/convergence_order.py` computes, for each triplet of levels, the convergence type, the observed order (with non-constant refinement ratios), the Richardson extrapolated value, relative errors and the GCI with its asymptotic-range ratio:

```bash
python3 <productcraft>/modules/scientific-computing/scripts/convergence_order.py \
  --h 0.04,0.02,0.01 --values 1.0128,1.0032,1.0008 --expected-order 2
python3 <productcraft>/modules/scientific-computing/scripts/convergence_order.py \
  --cells 12000,96000,768000 --dim 3 --values 0.3215,0.3242,0.3249 --json
```

| Result | Meaning | Action |
|---|---|---|
| Monotone, observed order near formal, asymptotic ratio near 1 | In the asymptotic range | Report the fine-grid value with the GCI band |
| Monotone, order well below formal | Pre-asymptotic, singularity, low-order boundary or bug | Refine further; check the code verification case |
| Order well above formal | Error cancellation or a lucky pre-asymptotic triple | Add a level; do not report a tiny GCI from it |
| Oscillatory | Changes alternate sign | The band is indicative only; refine, or report the spread of the levels |
| Divergent | Changes grow with refinement | Something is wrong: resolution of a singularity, instability, a mesh artifact |

- The default safety factor is 1.25 for three or more grids with an observed order, 3.0 for two grids with an assumed order.
- Report the GCI as an uncertainty band on the fine-grid value: `value +/- GCI * abs(value)`.
- Statistical outputs (turbulence, molecular dynamics, Monte Carlo) also carry sampling error; estimate it separately (`post-processing.md`) and keep it well below the effect being studied.

## 3. Validation

- **Compare like with like:** the same quantity, location, averaging and filtering as the measurement.
- **Combine uncertainties.** With comparison error `E = S - D` (simulation minus data), a validation uncertainty `u_val = sqrt(u_num^2 + u_input^2 + u_D^2)` collects numerical, input-parameter and measurement uncertainty. If `abs(E)` is within about `u_val`, the model error cannot be distinguished from the noise; if larger, `E` estimates the model error. This is the structure of the ASME V&V 20 approach.
- **Keep calibration and validation data separate.** Parameters tuned on a dataset cannot be validated against it.
- **State the validated domain.** Agreement at the tested conditions does not extend to other regimes; flag extrapolation.
- **Use published benchmarks and cite them** (for example lid-driven cavity centerline data, flow-past-cylinder benchmarks, standard test suites of a field). Never invent benchmark values; when the reference value is not at hand, say so and look it up or ask, and verify the citation exists (`../../research-writing/GUIDE.md`).

## 4. Run health: before, during, after

### Before (preflight)

- [ ] Configuration parses; every required parameter is present, with units; values are in physically sensible ranges.
- [ ] Nondimensional numbers computed and printed (Courant, Fourier, Reynolds, Peclet, and so on) and every stability limit respected (`time-integration-and-stability.md`).
- [ ] Resources checked: `python3 <productcraft>/modules/scientific-computing/scripts/resource_check.py --need-mem-gb <estimate> --need-disk-gb <output estimate> --path <output dir>`; output volume estimated as fields times points times bytes times outputs.
- [ ] A smoke run (coarse grid, a few steps) finishes and its output can be read back by the post-processing script.
- [ ] Versions, seeds, inputs and configuration recorded (`parameter-studies-and-campaigns.md`); the output directory is new or explicitly reused, never silently overwritten.

### During (runtime monitors)

```python
import numpy as np

def check_state(step, t, fields, invariants, reference, tolerance):
    """Stop early with a clear message instead of computing garbage for hours."""
    for name, array in fields.items():
        if not np.isfinite(array).all():
            first = np.argwhere(~np.isfinite(array))[0]
            raise FloatingPointError(f"step {step}, t={t:g}: non-finite {name} first at index {tuple(first)}")
    for name, value in invariants.items():
        drift = abs(value - reference[name]) / max(abs(reference[name]), 1e-300)
        if drift > tolerance[name]:
            raise RuntimeError(f"step {step}, t={t:g}: {name} drifted by {drift:.2e} (limit {tolerance[name]:.1e})")
```

Watch also: residual histories of each solve, the adaptive `dt` (a collapsing step means stiffness or an emerging instability), bounds (negative densities, volume fractions outside [0, 1]), wall time per step (a growing trend often means growing iteration counts) and memory growth. Write a final state dump when a monitor stops the run, so the failure can be inspected.

### After (postflight)

- [ ] The run reached its end time or converged, by the code's own status, not by the absence of an error message.
- [ ] No non-finite values in outputs; bounds and invariants within tolerance over the whole run.
- [ ] Symmetries of the problem are present in the solution where the setup is symmetric.
- [ ] Output files are complete: expected count, non-zero sizes, readable.
- [ ] Log warnings reviewed (solver not converged at some steps, clipped values, fallbacks).
- [ ] Results compared with the exact, reference or previous verified solution.

## 5. Diagnosing failures

| Evidence | Likely cause | First check |
|---|---|---|
| Exit status 137, "Killed", Slurm state `OUT_OF_MEMORY` | Memory limit hit (SIGKILL is signal 9; 128 + 9) | Peak memory (`sacct ... MaxRSS`); memory estimate; container limit |
| Exit status 139, "Segmentation fault" | Out-of-bounds access, stack overflow, library ABI mismatch | Rebuild with debug symbols and bounds checks or sanitizers; `ulimit -s` for large stack arrays |
| Slurm state `TIMEOUT` | Wall time exceeded | Time per step times steps; checkpoint and resubmit |
| NaN after some steps | Stability limit violated, invalid initial condition, division by zero, `log` or `sqrt` of a negative, uninitialized memory | First step and location of the NaN; nondimensional numbers at that step |
| Solver "did not converge" followed by odd values | Return status ignored | Check every status flag; reduce the step; better initial guess |
| MPI run hangs | Mismatched collectives, deadlock in point-to-point messages, one rank failed | Per-rank logs; run with fewer ranks; a debugger or `py-spy dump` on a stuck rank |
| Different results run to run | Unseeded randomness, parallel reduction order, GPU atomics, uninitialized memory | Seeds; single-thread run; deterministic flags where the library has them |
| Results change with the number of processes beyond roundoff | Partition-dependent bug (halo exchange, boundary handling) | Compare 1, 2 and 4 processes on a small case |

Read the first error in the log, not the last; later errors are usually consequences.

## 6. Reporting

State, for each reported quantity: the value with its numerical uncertainty (GCI band or tolerance study), grids and time steps used, observed versus formal order, iterative tolerances, sampling uncertainty where relevant, the validation comparison with uncertainties, the conditions it applies to, the code and library versions, and what was not verified (mark it `NOT VERIFIED` with the reason).

## Checks (done when)

- [ ] Code verified on an exact or manufactured solution, with the observed order on record and kept as a regression test.
- [ ] Iterative, time-step and grid convergence shown for the reported quantities, with the convergence type and GCI.
- [ ] Validation compares like with like and combines numerical, input and measurement uncertainty; calibration data were not reused.
- [ ] Preflight, runtime and postflight checks ran; failures were diagnosed from the first error.

## Anti-patterns

- "The run finished, so the result is right."
- Two grids and a GCI from an assumed order presented as verification.
- Tuning model parameters until a plot matches, then calling it validation.
- Error bars with no statement of what they contain.
- Benchmark numbers quoted from memory.
