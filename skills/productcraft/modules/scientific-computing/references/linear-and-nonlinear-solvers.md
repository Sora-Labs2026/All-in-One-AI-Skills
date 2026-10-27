# Linear and nonlinear solvers

Read this when a simulation, fit or implicit time step has to solve `A x = b`, `F(x) = 0` or `min f(x)`, when a solver is slow, stalls or returns a suspicious answer, or when choosing between direct and iterative methods, preconditioners, Newton variants and globalization.

## 1. Characterize the problem before choosing

Write these down; every choice below depends on them.

| Property | How to find out |
|---|---|
| Size `n`, nonzeros, structure (banded, block, saddle point) | `A.shape`, `A.nnz`; plot the pattern once with `matplotlib.pyplot.spy` on a small case |
| Symmetry | `abs(A - A.T).max()` relative to `abs(A).max()`; symmetric physics plus nonsymmetric boundary rows is common |
| Definiteness | Physics (diffusion and elasticity are SPD after boundary conditions; Stokes and constrained systems are indefinite); `eigsh(A, k=1, which="SA")` on a small instance |
| Conditioning | `np.linalg.cond` for small dense; `scipy.sparse.linalg.onenormest` of `A` and of `A^-1` (via a factorization) for sparse |
| Right-hand sides | One, many with the same matrix (factor once), or a sequence of slowly changing matrices (reuse the preconditioner) |
| Nullspace | Pure Neumann, periodic or floating structures have one; the system is singular by construction |

A matrix that "should" be symmetric but is not usually means a boundary condition was imposed by overwriting rows. Symmetric elimination of the boundary rows and columns keeps CG usable.

## 2. Direct or iterative

| Situation | Start with | Why |
|---|---|---|
| Dense, `n` up to about 10^4 | LAPACK through `scipy.linalg` (`cho_factor` for SPD, `lu_factor` otherwise) | Robust, predictable; memory is `8 n^2` bytes (20,000 unknowns is 3.2 GB) |
| Sparse, 1D and 2D problems up to roughly 10^6 unknowns | Sparse direct: `scipy.sparse.linalg.splu`, or MUMPS, PARDISO, CHOLMOD through PETSc or wrappers | Fill-in stays moderate in 2D; no tuning; exact to roundoff |
| Sparse 3D, or anything that does not fit after factorization | Krylov method with a preconditioner | Fill-in in 3D grows much faster than `nnz` |
| Same matrix, many right-hand sides | Factor once, solve many | Factorization dominates the cost |
| Rectangular, least squares | `scipy.linalg.lstsq`, or LSQR or LSMR for sparse | Normal equations square the condition number |

These are starting points, not thresholds. Time both options on a representative size before committing; measure memory too.

## 3. Krylov methods and preconditioners

| Matrix | Method | Notes |
|---|---|---|
| SPD | CG | Needs an SPD preconditioner too; on a nonsymmetric matrix it can wander without warning |
| Symmetric indefinite | MINRES | Preconditioner must be SPD |
| Nonsymmetric | GMRES(m), BiCGStab, TFQMR | GMRES minimizes the residual but needs `m` stored vectors; BiCGStab has short recurrences but erratic convergence |
| Least squares | LSQR, LSMR | Work on `A` and `A^T` without forming `A^T A` |

| Preconditioner | Good for | Watch |
|---|---|---|
| Jacobi (diagonal) | Cheap first try, strongly diagonally dominant systems | Weak; iteration count grows with refinement |
| Incomplete LU or Cholesky (ILU(0), ILUT) | General sparse, moderate size | Can break down on indefinite systems; tune drop tolerance and fill |
| Algebraic multigrid (PyAMG; hypre BoomerAMG; PETSc GAMG) | Elliptic and parabolic operators: Poisson, diffusion, elasticity (give it the rigid-body near-nullspace) | Iteration count should stay nearly constant as the mesh is refined; if it does not, the problem is not AMG-friendly or the setup is wrong |
| Block Jacobi or additive Schwarz | Parallel runs | Weakens as the number of blocks grows; combine with a coarse level |
| Physics-based block preconditioners | Saddle points (Stokes, mixed formulations, constraints) | Approximate the Schur complement, for example with a pressure mass matrix for Stokes |

```python
import numpy as np
import scipy.sparse.linalg as spla

A = A.tocsc()                                   # spilu expects CSC
ilu = spla.spilu(A, drop_tol=1e-4, fill_factor=10)
M = spla.LinearOperator(A.shape, ilu.solve)
history = []
x, info = spla.gmres(A, b, M=M, rtol=1e-8, restart=50, maxiter=40,   # maxiter counts restart cycles
                     callback=history.append, callback_type="pr_norm")
if info != 0:
    raise RuntimeError(f"GMRES stopped without converging (info={info}, {len(history)} iterations)")
true_relative = np.linalg.norm(b - A @ x) / np.linalg.norm(b)
```

SciPy renamed the iterative solvers' `tol` argument to `rtol` in 1.12 and removed `tol` in 1.14; older code passes `tol`. SciPy's iterative solvers return the last iterate with `info > 0` when they fail, so an unchecked call returns a wrong answer silently.

```python
import pyamg
ml = pyamg.smoothed_aggregation_solver(A.tocsr())
x, info = spla.cg(A, b, M=ml.aspreconditioner(cycle="V"), rtol=1e-10, maxiter=500)
```

For large or parallel problems use PETSc (`petsc4py`), Trilinos or hypre instead of SciPy. PETSc options make experiments cheap: `-ksp_type gmres -pc_type gamg -ksp_monitor_true_residual -ksp_converged_reason`, and `-ksp_view` prints what actually ran.

## 4. Scaling, tolerances and what a residual means

- **Nondimensionalize first.** A system mixing pascals and meters per second has rows that differ by 10^5 for no physical reason. Scale unknowns and equations to order one, or equilibrate (row and column scaling; `D^-1/2 A D^-1/2` keeps symmetry).
- **A small residual is not a small error.** The relative error is bounded by the condition number times the relative residual. With `cond(A) = 1e8`, a residual of `1e-10` only promises about two correct digits.
- **Match the tolerance to the discretization error.** Solving to `1e-12` when the discretization error is `1e-4` wastes time; solving to `1e-3` when it is `1e-6` pollutes the convergence study. Keep the algebraic error at least two orders below the discretization error.
- **Use an absolute floor** (`atol`) when `b` can be near zero, or the relative test can never be met.
- **Preconditioned and true residuals differ.** Left-preconditioned GMRES monitors `M^-1 r`. Always compute the true residual at the end, in the original units, and report which norm you used.
- **Singular systems.** For a nullspace (pure Neumann, periodic), make the right-hand side compatible (for a constant nullspace, `sum(b) = 0` up to roundoff), then pin one value or project the nullspace out; tell the Krylov solver about the nullspace where the library supports it.

## 5. Reading a linear solver's convergence

| Symptom | Likely cause | Next step |
|---|---|---|
| Restarted GMRES plateaus | Restart too short; poor preconditioner | Larger restart; stronger preconditioner; deflation |
| CG residual erratic or rising | Matrix or preconditioner not SPD | Check symmetry and the sign of pivots; switch to MINRES or GMRES |
| BiCGStab spikes or breaks down | Near-breakdown of the recurrence | GMRES or BiCGStab(l) |
| Iterations grow with each mesh refinement | Preconditioner does not scale | Multigrid or domain decomposition with a coarse space |
| Converges, answer wrong | Singular or nearly singular system; wrong boundary conditions | Check nullspace, compatibility and boundary rows |
| Direct solver reports a singular matrix | Missing boundary condition, duplicated degrees of freedom, unit mismatch | Inspect zero rows and columns; count constraints |

## 6. Nonlinear systems `F(x) = 0`

| Situation | Method | SciPy or library entry point |
|---|---|---|
| Small to medium, Jacobian available | Newton with line search or trust region | `scipy.optimize.root(method="hybr")` (MINPACK), `method="lm"` |
| Large, Jacobian too costly to form | Jacobian-free Newton-Krylov | `scipy.optimize.newton_krylov`; PETSc SNES with `-snes_mf` |
| Jacobian expensive, moderate size | Broyden (quasi-Newton) | `root(method="broyden1")` |
| Coupled multiphysics solved by fixed point | Picard iteration with Anderson acceleration | `scipy.optimize.anderson`; PETSc `-snes_type anderson` |
| No good initial guess | Continuation (step a parameter from an easy case), pseudo-transient continuation | Write the outer loop yourself; reuse each solution as the next guess |
| Bound-constrained least squares | Trust-region reflective | `scipy.optimize.least_squares(method="trf", bounds=...)` |

**Globalization.** Pure Newton converges quadratically only near the root. Use a backtracking (Armijo) line search or a trust region. A trust-region step with predicted-to-actual reduction ratio below about 0.25 should shrink the region; above about 0.75 at the boundary, grow it.

**Inexact Newton.** Solve each linear system only as tightly as the outer iteration needs (Eisenstat-Walker forcing terms). Tight inner tolerances early in Newton waste time; loose ones near convergence destroy the quadratic rate.

**Check the Jacobian before blaming the solver.** Most "Newton converges slowly" reports are a wrong Jacobian. A Taylor test makes it visible:

```python
import numpy as np

def taylor_test(F, J, x, seed=0, steps=6):
    """Remainder |F(x+e v) - F(x) - e J v| must fall by about 4x per halving of e (second order)."""
    v = np.random.default_rng(seed).standard_normal(x.shape)
    F0, Jv = F(x), J(x) @ v
    eps, previous = 1e-2, None
    for _ in range(steps):
        r = np.linalg.norm(F(x + eps * v) - F0 - eps * Jv)
        print(f"eps={eps:.1e} remainder={r:.3e}" + (f" ratio={previous / r:.2f}" if previous else ""))
        previous, eps = r, eps / 2
```

A ratio near 2 means the Jacobian is wrong (first-order remainder). Ratios that collapse at tiny `eps` are roundoff, not a bug. PETSc offers `-snes_test_jacobian` for the same check.

For Jacobian-free products choose the differencing step relative to the state, roughly `sqrt(machine epsilon) * (1 + norm(x)) / norm(v)`; a fixed `1e-8` fails when `x` is of order 10^6.

## 7. Reading a nonlinear convergence history

| Pattern in `norm(F)` per iteration | Meaning | Action |
|---|---|---|
| Exponent doubles (1e-2, 1e-4, 1e-8) | Quadratic: Newton working | None |
| Constant ratio, for example 0.5 per iteration | Linear: wrong or lagged Jacobian, or inner solves too loose | Taylor test; tighten forcing terms |
| Stalls at a level well above roundoff | Non-smooth residual (`abs`, `max`, table lookups, `if` branches), inconsistent residual evaluation, or a tolerance below the attainable accuracy | Smooth the model or accept the floor with a stated reason |
| Grows or oscillates | No globalization, poor initial guess, step too long | Line search or trust region; continuation |

Estimate the order from the last three residuals: `q = log(r[k+1] / r[k]) / log(r[k] / r[k-1])`. Values near 2 confirm Newton; near 1 point to a Jacobian or inner-solve problem.

## 8. Optimization problems

- **Smooth with gradients** (analytic, adjoint or automatic differentiation): L-BFGS-B for bounds, SLSQP or `trust-constr` for general constraints, IPOPT (through `cyipopt`) for large constrained problems.
- **Least squares** (fits, calibration): `least_squares` with `x_scale="jac"`, and a robust loss (`soft_l1`, `huber`) when outliers exist. Weight residuals by measurement uncertainty.
- **Derivative-free, few parameters:** Nelder-Mead, Powell, COBYLA (constraints), BOBYQA (`Py-BOBYQA`).
- **Multimodal:** `differential_evolution`, CMA-ES (`cma`), multistart local search. Calibration and expensive objectives are covered in `parameter-studies-and-campaigns.md`; several objectives in `multi-objective-pymoo.md`.
- Finite-difference gradients of a simulation that uses adaptive steps or iterative solves are noisy at the scale of the solver tolerance. Either tighten the inner tolerances well below the difference step or use a derivative-free method.

## Checks (done when)

- [ ] Matrix properties (size, sparsity, symmetry, definiteness, nullspace) recorded and the solver choice follows from them.
- [ ] Every solver call checks its return status; the true residual is computed in original units and reported with the norm used.
- [ ] Algebraic tolerance sits at least two orders below the discretization error of the quantity of interest.
- [ ] For iterative methods, iteration counts at two or more mesh sizes show whether the preconditioner scales.
- [ ] For Newton, the Jacobian passed a Taylor test and the observed convergence order matches the method.

## Anti-patterns

- Ignoring `info` or a `success` flag and using whatever came back.
- Copying a tolerance (`1e-6`, `1e-12`) without relating it to the problem's scale or discretization error.
- Inverting a matrix (`inv(A) @ b`) instead of solving or factoring.
- Using CG on a matrix made nonsymmetric by boundary handling.
- Forming normal equations for ill-conditioned least squares.
- Blaming the nonlinear solver before testing the Jacobian.
