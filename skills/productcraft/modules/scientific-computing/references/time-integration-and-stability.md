# Time integration, stiffness and stability

Read this when a model evolves in time: choosing an ODE integrator or a time-stepping scheme for a PDE, setting `rtol` and `atol`, diagnosing a run that blows up or crawls with tiny steps, splitting stiff and non-stiff terms, checking CFL-type limits, or planning output and checkpoint cadence for a long run.

## 1. Classify the problem

| Question | Why it matters |
|---|---|
| Is it stiff? | Explicit methods are limited by the fastest decaying mode, not by accuracy |
| Is it a DAE (algebraic constraints, mass matrix)? | Needs a DAE solver; `solve_ivp` does not handle mass matrices |
| Does it conserve something (energy, symplectic structure, mass)? | Long runs need a structure-preserving or conservative scheme |
| Are there discontinuities in time (switched inputs, events)? | Integrate piecewise between them, or use event detection |
| How large is the system, and is the Jacobian sparse? | Implicit methods need a linear solve per step; supply sparsity or a Jacobian |

**Stiffness in practice:** the eigenvalues of the Jacobian span many orders of magnitude and the fast modes decay. The symptom is an explicit adaptive solver taking steps far smaller than the solution's visible time scale. The direct test: run an explicit method (RK45) and an implicit one (Radau or BDF) with the same tolerances and compare function evaluations and wall time. If the implicit run is much cheaper at the same accuracy, the problem is stiff.

## 2. Choosing an integrator

| Problem | Method | Where |
|---|---|---|
| Non-stiff, moderate accuracy | Dormand-Prince 5(4) | `solve_ivp(method="RK45")` |
| Non-stiff, tight tolerances, smooth | DOP853 (order 8) | `solve_ivp(method="DOP853")` |
| Stiff, any eigenvalues | Radau IIA (order 5, L-stable) | `solve_ivp(method="Radau")` |
| Stiff, eigenvalues near the negative real axis, large systems | BDF orders 1 to 5 | `solve_ivp(method="BDF")`, SUNDIALS CVODE |
| Stiffness unknown or changing | Automatic switching | `solve_ivp(method="LSODA")` |
| Very large stiff systems (method of lines) | BDF with Newton-Krylov | SUNDIALS CVODE (through scikits-odes or Assimulo), PETSc TS |
| DAEs | IDA (SUNDIALS), Radau with mass matrix | Assimulo, PETSc TS, Julia's DifferentialEquations.jl |
| Hamiltonian, long-time orbits or molecular dynamics | Symplectic, fixed step (velocity Verlet, leapfrog) | Write it, or use the domain code |

BDF above order 2 is not A-stable: lightly damped oscillatory stiff modes (eigenvalues close to the imaginary axis) can degrade it, so prefer Radau there. Adaptive step sizes destroy the long-time benefit of symplectic schemes.

For method-of-lines PDEs, pass the Jacobian sparsity (`jac_sparsity=`) or an analytic sparse Jacobian to Radau, BDF or LSODA; dense finite-difference Jacobians make large systems impossibly slow.

```python
import numpy as np
from scipy.integrate import solve_ivp

def robertson(t, y):          # classic stiff chemical kinetics test; y1 + y2 + y3 = 1 is conserved
    y1, y2, y3 = y
    return [-0.04 * y1 + 1e4 * y2 * y3,
            0.04 * y1 - 1e4 * y2 * y3 - 3e7 * y2 ** 2,
            3e7 * y2 ** 2]

def jacobian(t, y):
    y1, y2, y3 = y
    return [[-0.04, 1e4 * y3, 1e4 * y2],
            [0.04, -1e4 * y3 - 6e7 * y2, -1e4 * y2],
            [0.0, 6e7 * y2, 0.0]]

sol = solve_ivp(robertson, (0.0, 1e5), [1.0, 0.0, 0.0], method="Radau", jac=jacobian,
                rtol=1e-8, atol=[1e-10, 1e-14, 1e-10])   # y2 stays near 1e-5: it needs its own floor
assert sol.success, sol.message
drift = np.max(np.abs(sol.y.sum(axis=0) - 1.0))           # invariant check
print(sol.nfev, sol.njev, sol.nlu, drift)
```

## 3. Tolerances

- `rtol` sets the relative digits kept; `atol` is the size below which a component no longer matters. Set `atol` per component, in that component's units.
- SciPy's defaults (`rtol=1e-3`, `atol=1e-6`) are loose for most science. A concentration of order `1e-9` with `atol=1e-6` is effectively uncontrolled.
- The tolerance controls local error per step. Global error accumulates and can exceed it. Verify by repeating the run with tolerances ten times tighter and comparing the quantity of interest; the difference estimates the integration error.
- In double precision, `rtol` below about `1e-13` buys nothing.
- Nondimensionalize, or at least scale variables, so that one `rtol` and a sensible `atol` vector fit all components.

## 4. Steps, events and discontinuities

- Library integrators use embedded error estimates and a step controller. Write your own controller only when you write your own integrator; then use a weighted RMS error norm `sqrt(mean((e_i / (atol_i + rtol * |y_i|))^2))`, accept when it is at most 1, and limit the step change per step (for example to between 0.2x and 5x).
- **Discontinuities:** do not integrate across a known jump in a forcing term or parameter. Split the interval at the break times and restart the integrator; dense output and `t_eval` do not fix the error introduced by stepping over a jump.
- **State-dependent events:** use `events=` with `terminal=True` and `direction` set; check that the event time converged by tightening tolerances.
- **Short pulses:** set `max_step` below the pulse width, or the controller may step over it entirely.
- Read `sol.status`, `sol.message`, `nfev`, `njev` and `nlu`. A stiff solver with `nlu` close to the step count is refactoring every step, which often means a poor Jacobian.

## 5. IMEX and operator splitting

When stiff and non-stiff terms coexist (diffusion plus advection or reaction), treat the stiff part implicitly and the rest explicitly.

| Approach | Order | Use when | Watch |
|---|---|---|---|
| IMEX Runge-Kutta (additive RK, for example the Kennedy-Carpenter ARK family) | 2 to 5 | Terms tightly coupled; one method for everything | Needs the split written into the right-hand side |
| IMEX multistep (SBDF2, Crank-Nicolson with Adams-Bashforth) | 2 | Spectral and finite-difference PDE codes; cheap per step | Startup steps; stability of the explicit part still limits the step |
| Lie-Trotter splitting (`A` then `B`) | 1 | Quick prototypes | First order regardless of the substep solvers |
| Strang splitting (`A` half, `B` full, `A` half) | 2 | Separate solvers per physics, reaction-diffusion | Order reduction with stiff terms or time-dependent boundary conditions |

- Splitting error comes from the non-commuting operators. Tightening the tolerances of the substep solvers does not reduce it; only a smaller split step does. Verify the observed order of the whole split scheme with a time-step refinement study (`verification-and-validation.md`).
- Stiff pointwise reactions in a split scheme: integrate each cell's ODE with an implicit solver, vectorized over cells where possible.

## 6. Stability limits for explicit PDE schemes

Use the actual maximum speeds and coefficients of the current state; recompute every step or every few steps, since velocities grow during a run.

| Physics | Number | Typical explicit limit | Notes |
|---|---|---|---|
| Advection | Courant `C = abs(u) dt / dx` | `C <= 1` for first-order upwind in 1D | Unsplit multidimensional upwind needs `sum(abs(u_i) dt / dx_i) <= 1`; for Runge-Kutta stages the limit comes from the stability region (RK4 with central differences reaches about 2.8 on the imaginary axis) |
| Diffusion | Fourier `Fo = nu dt / dx^2` | `Fo <= 1/2` in 1D (FTCS) | In d dimensions on a uniform grid, `sum(nu dt / dx_i^2) <= 1/2`, so `1/(2d)` with equal spacing |
| Linear decay or reaction | `k dt` | Forward Euler stable for `k dt <= 2`, free of sign flips for `k dt <= 1` | Positivity usually matters before stability does |
| Waves | `c dt / dx` | `<= 1` for the standard leapfrog scheme | Use the fastest wave speed in the system (sound, gravity waves) |
| Advection-diffusion with FTCS | Both | Requires `C^2 <= 2 Fo <= 1` | Centered advection without diffusion is unconditionally unstable |

- Apply a safety factor (0.5 to 0.9) and take the minimum over all limits.
- **Implicit is stable, not accurate.** Backward Euler and BDF2 tolerate large steps; accuracy still needs a convergence check. Crank-Nicolson is A-stable but not L-stable: stiff components with large steps ring. Use BDF2, or start with a few backward Euler steps (Rannacher startup) when initial data are rough.

## 7. Von Neumann and eigenvalue checks

For a linear, constant-coefficient scheme on a periodic grid, substitute `u_j^n = G^n exp(i theta j)` and require `abs(G(theta)) <= 1` for all `theta`. Scanning the amplification factor numerically avoids algebra mistakes:

```python
import numpy as np

def max_amplification(fourier_number, n=721):
    """FTCS diffusion: G = 1 - 4 Fo sin^2(theta / 2). Stable while max |G| <= 1."""
    theta = np.linspace(-np.pi, np.pi, n)
    return np.max(np.abs(1 - 4 * fourier_number * np.sin(theta / 2) ** 2))

assert max_amplification(0.5) <= 1 + 1e-12 and max_amplification(0.51) > 1
```

Von Neumann analysis ignores boundaries, variable coefficients and nonlinearity. For the full semi-discrete operator `L` (method of lines), compute its extreme eigenvalues on a small grid (`scipy.sparse.linalg.eigs`) and check that `dt * lambda` lies inside the time integrator's stability region. Non-normal operators (strong advection, boundary closures) can grow transiently even when all eigenvalues are stable; a short run with random initial data reveals it.

## 8. Planning a long run

**Time step.** `dt = safety * min(all stability limits, accuracy-driven limit)`, and align with required output times. Re-plan when parameters change.

**Startup.** Abrupt initial or boundary conditions create transients that force tiny steps or shocks. Ramp forcing smoothly (for example `0.5 * (1 - cos(pi * t / t_ramp))` over the ramp time), or start with a small `dt` and let an adaptive controller grow it. Record the ramp as part of the model, since it changes early-time results.

**Output cadence.** Sample at least 10 to 20 outputs per shortest time scale you need to see in the output; two per period is the Nyquist minimum, not a working rate. Hit output times exactly (step to them or use dense output) rather than taking the nearest step. Estimate output volume first: fields times grid points times bytes times outputs.

**Checkpoint cadence.** To first order, the interval that minimizes lost work is `sqrt(2 * C * M)`, where `C` is the time to write a checkpoint and `M` the mean time between interruptions (failures, preemptions or the wall-time limit). Example: `C = 60 s`, `M = 24 h` gives about 54 minutes. Always also checkpoint shortly before a scheduler wall-time limit (`hpc-and-profiling.md`).

**Checkpoint contents.** Full state, time, step number, current `dt`, multistep history (or restart at lower order), random generator state, configuration hash and code version. **Test the restart:** run `2N` steps straight, then `N` steps plus restart plus `N` steps, and compare. Bitwise equality is the goal for deterministic codes; otherwise agreement to the integration tolerance.

**Invariant monitors.** Log conserved or bounded quantities every output: mass, energy, momentum, positivity, maximum principle bounds. Drift in a scheme that should conserve them indicates a bug or loose tolerances.

## Checks (done when)

- [ ] Stiffness assessed (eigenvalue spread or the explicit-versus-implicit test) and the method justified by it.
- [ ] `rtol` and per-component `atol` chosen in the components' units; a run with tolerances ten times tighter changes the quantity of interest by less than the accuracy needed.
- [ ] Every explicit stability limit computed from current maximum speeds and coefficients, with the safety factor stated.
- [ ] Splitting or IMEX schemes show their expected order in a time-step refinement study.
- [ ] Known discontinuities handled by restarting; events converged.
- [ ] Long runs: checkpoint interval derived from write cost and interruption rate; a restart reproduces a straight run.

## Anti-patterns

- Accepting `solve_ivp` default tolerances for small-magnitude components.
- Shrinking `dt` until a blow-up disappears, without finding which limit was violated.
- Calling an implicit scheme "unconditionally accurate".
- Stepping across a forcing discontinuity with an adaptive method.
- Checkpoints that have never been restarted from.
