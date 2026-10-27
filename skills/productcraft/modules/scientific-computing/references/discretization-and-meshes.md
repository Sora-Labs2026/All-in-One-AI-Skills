# Discretization schemes and meshes

Read this when turning a PDE into a discrete model: choosing finite differences, finite volumes, finite elements or spectral methods; deriving stencils and boundary closures; handling advection without wiggles or smearing; choosing resolution; generating meshes and judging their quality; and refining meshes for a convergence study.

## 1. Choose the family

| Family | Strengths | Weaknesses | Typical tools |
|---|---|---|---|
| Finite differences | Simple, high order is cheap on structured grids | Complex geometry and boundary closures are awkward | Hand-written NumPy, Numba, JAX; PETSc DMDA |
| Finite volumes | Discrete conservation, shocks, unstructured meshes | High order is hard on unstructured meshes | OpenFOAM, SU2, Clawpack, PyClaw |
| Finite elements | Complex geometry, natural boundary conditions, error theory, multiphysics | Assembly and solver setup are more work | FEniCSx, Firedrake, deal.II, MFEM, scikit-fem |
| Spectral and pseudospectral | Exponential convergence for smooth solutions in simple domains | Gibbs oscillations at discontinuities; aliasing; geometry limits | Dedalus, fluidsim, hand-written FFT codes |
| Discontinuous Galerkin | High order with conservation and shock handling | Many degrees of freedom; tight explicit time steps | deal.II, MFEM, Trixi.jl |

Choose by what must hold exactly (conservation, positivity), by geometry, and by solution smoothness. Changing family later is expensive; write the reason down.

## 2. Finite-difference stencils

Derive weights instead of copying tables. For offsets `s_j` (in units of `h`) and derivative order `m`, the weights solve `sum_j c_j s_j^k / k! = delta(k, m)` for `k = 0 .. len(s) - 1`:

```python
import numpy as np
from math import factorial

def fd_weights(offsets, derivative):
    """Weights c_j so that sum c_j f(x + s_j h) / h**derivative approximates the derivative."""
    s = np.asarray(offsets, dtype=float)
    k = np.arange(len(s))
    V = s[None, :] ** k[:, None] / np.array([factorial(int(i)) for i in k])[:, None]
    rhs = np.zeros(len(s))
    rhs[derivative] = 1.0
    return np.linalg.solve(V, rhs)

fd_weights([-1, 0, 1], 1)           # [-1/2, 0, 1/2]
fd_weights([-2, -1, 0, 1, 2], 2)    # [-1, 16, -30, 16, -1] / 12
fd_weights([0, 1, 2], 1)            # [-3/2, 2, -1/2]: second-order one-sided
```

The Vandermonde system becomes ill-conditioned beyond about seven points. For exact rationals use `sympy.finite_diff_weights(m, offsets, 0)`; for arbitrary point sets Fornberg's algorithm is the standard stable recurrence.

- **Check every stencil numerically:** apply it to `sin(x)` at `h, h/2, h/4` and confirm the error ratio is `2^p` (4 for second order, 16 for fourth).
- **Leading error term:** the central first derivative has error `-(h^2 / 6) f'''`; knowing it tells you which features (steep gradients, high curvature) the scheme handles poorly.
- **Nonuniform grids:** compute weights for the actual offsets at each point, or map to a uniform computational coordinate and carry the metric terms. Abrupt spacing changes lower the effective order; keep neighbor ratios modest (about 1.2 or less).

## 3. Boundaries

- **Ghost cells** carry Dirichlet or Neumann conditions into the interior stencil. Neumann on a cell-centered grid, with `g` the outward normal derivative at the boundary face: `u_ghost = u_0 + h * g` (second order at the face). Check the sign on both ends of the domain with a linear exact solution.
- **One-sided closures** keep the stencil inside the domain. A boundary closure one order lower than the interior often still delivers the interior's global order for many hyperbolic and parabolic problems, but this is a property to verify, not assume.
- **Provable stability** for high-order schemes on bounded domains comes from summation-by-parts operators with weak (SAT) boundary terms. Ad hoc high-order closures can be unstable even when the interior is fine; test with long runs and random data.
- Boundary errors often dominate the L-infinity norm. Report L2 and L-infinity separately, and look at where the maximum error sits.

## 4. Advection: dispersion and dissipation

| Scheme | Behavior | When |
|---|---|---|
| Central differences | No numerical dissipation, dispersive: wiggles behind sharp fronts, odd-even decoupling | Smooth, well-resolved flows; DNS with fine grids |
| First-order upwind | Monotone, strongly diffusive (numerical diffusion about `u dx (1 - C) / 2`) | Robust startup, positivity-critical fields |
| MUSCL with a TVD limiter (minmod, van Leer, superbee) | Second order in smooth regions, no new extrema | Shocks and fronts in finite-volume codes |
| WENO5 | High order in smooth regions, non-oscillatory near shocks | Compressible flow, sharp interfaces |

- Godunov's theorem: a linear monotone scheme is at most first order. Sharp fronts without oscillations need nonlinear limiting.
- Pair TVD and WENO spatial schemes with strong-stability-preserving Runge-Kutta (SSPRK3) time stepping so the time integrator does not reintroduce oscillations.
- **Resolution from phase error.** The modified wavenumber of the second-order central first derivative is `sin(kh)/h`, a relative phase-speed error of about `(kh)^2 / 6`: 1% error needs about 26 points per wavelength. The fourth-order central stencil errs by about `(kh)^4 / 30`: 1% needs about 8.5 points per wavelength. Pick points per wavelength from the error you can accept over the propagation distance, not from a fixed rule.

## 5. Spectral methods

- Exponential convergence holds only for smooth (analytic) solutions with periodic or Chebyshev-suitable boundaries. Check that the spectrum's tail falls to near roundoff; a flat tail means under-resolution.
- Quadratic nonlinearities alias: zero the top third of modes (the 2/3 rule) or pad by 3/2 before transforming. Report which.
- Discontinuities produce Gibbs oscillations that resolution does not remove; filter, or use another method near shocks.
- FFT conventions (normalization, frequency ordering) differ between libraries. Test a derivative of `sin(kx)` on the grid before trusting the operator.

## 6. Resolution from physics

Rules of thumb seed a convergence study; they never replace one.

| Feature | Starting resolution |
|---|---|
| Diffuse interface (phase field) of width `w` | About 5 to 10 cells across `w` |
| Wall-bounded turbulence, wall-resolved LES or DNS | First cell at `y+` of about 1; with wall functions, `y+` of about 30 to 300 depending on the model |
| Waves | From the phase-error analysis above |
| Diffusion layer over time `t` | Several cells across `sqrt(D t)` |
| DNS of turbulence | `k_max * eta` of at least about 1 (Kolmogorov scale `eta`); see `fluid-simulation.md` |

## 7. Meshes

### Quality

| Metric | Meaning | Rough concern level |
|---|---|---|
| Inverted elements (negative Jacobian) | Element is turned inside out | Always fatal |
| Scaled Jacobian, minimum angle | Element distortion | Very small values hurt accuracy and conditioning |
| Aspect ratio | Elongation | Harmless when aligned with a boundary layer or anisotropic solution, harmful when not |
| Skewness, non-orthogonality (finite volumes) | Face misalignment | High values need correction terms and degrade accuracy; OpenFOAM users watch non-orthogonality above about 70 degrees |
| Growth ratio between neighbors | Abrupt size changes | Keep it modest, about 1.2 to 1.3 near walls |

Thresholds depend on the solver and the physics, and metric definitions differ between tools (skewness in particular). Use the solver's own checker and compare meshes with the same metric: OpenFOAM `checkMesh`, Gmsh element quality statistics (`gmsh.model.mesh.getElementQualities`), PyVista cell quality filters.

### Tools and licenses

- **Gmsh** (GPL, Python API) for 2D and 3D unstructured meshes; `meshio` converts between formats (MSH, VTU, XDMF); **Netgen** (LGPL); OpenFOAM `blockMesh` and `snappyHexMesh`.
- **TetGen** is AGPL or commercial, and **CGAL** is GPL or commercial: check the license before shipping them inside a product.
- Structured grids: `np.meshgrid(x, y, indexing="ij")` gives `[i, j]` ordering; the default `"xy"` swaps the first two axes, a frequent source of transposed fields.

### Adaptive refinement

- AMR frameworks: AMReX, p4est, deal.II, libMesh, Basilisk. Refine on an error indicator (gradient or curvature indicators, Kelly or Zienkiewicz-Zhu estimators) rather than on the solution value.
- With explicit time stepping, the finest level sets the CFL step; use subcycling where the framework supports it.
- Conservative interpolation at coarse-fine interfaces matters for conservation laws; check total mass before and after regridding.

## 8. Refining for a convergence study

- Refine systematically: same topology and stretching, a constant refinement ratio of at least 1.3 (2 is common for structured grids).
- For unstructured meshes, use a representative spacing `h = (V / N)^(1/d)` and generate each level with the same sizing field scaled, not with independent meshing choices.
- Keep the geometry representation fixed across levels. Re-sampling a curved boundary differently per level mixes geometric error into the study.
- Compute the observed order and GCI with `../scripts/convergence_order.py` (see `verification-and-validation.md`).

## Checks (done when)

- [ ] The discretization family and its reason are written down.
- [ ] Every hand-written stencil passed a numerical order check on a smooth function.
- [ ] Boundary closures were exercised by a convergence study that includes the boundary region.
- [ ] Advection of sharp features was tested for both overshoots and smearing against an exact profile.
- [ ] Mesh quality was checked with the solver's own tool; no inverted elements; outliers explained.
- [ ] Resolution claims rest on a refinement study, not on a rule of thumb.

## Anti-patterns

- Stencil coefficients copied from memory or a table and never tested.
- Central differences on under-resolved fronts, then filtering the wiggles away in post-processing.
- Treating aspect ratio as bad everywhere instead of judging alignment.
- Comparing grids whose geometry or topology differs and calling it a refinement study.
- `meshgrid` with default indexing feeding code that assumes `[i, j]`.
