# Fluid simulation

Read this when simulating fluid flow: choosing between pseudospectral, finite-volume and finite-element codes; setting up a case from its nondimensional numbers; resolving turbulence; running periodic-box simulations (for example with fluidsim or Dedalus) or engineering cases (for example with OpenFOAM); and checking results against exact solutions and benchmarks.

## 1. Choose the tool by the problem

| Problem | Approach | Examples |
|---|---|---|
| Periodic-box turbulence, idealized geophysical flows (2D and 3D Navier-Stokes, shallow water, stratified or rotating flows) | Pseudospectral | fluidsim, Dedalus, custom FFT codes with `mpi4py-fft` |
| Engineering geometries, RANS and LES, compressible flow | Finite volume | OpenFOAM (two distributions with different release numbering), SU2 |
| Coupled multiphysics, complex geometry, adjoints | Finite element | FEniCSx, Firedrake, deal.II |
| Complex boundaries at moderate Reynolds number, porous media | Lattice Boltzmann | Palabos, waLBerla |
| Violent free surfaces, splashing | Smoothed particle hydrodynamics | DualSPHysics |

Licenses differ (for example fluidsim is CeCILL, which is GPL-compatible; Dedalus and OpenFOAM are GPL; SU2 is LGPL); check each code's license file. Copyleft codes are fine to use; distributing modified versions or linking them into closed software carries obligations (`../../legal-ready/GUIDE.md` covers license questions).

## 2. Start from nondimensional numbers

- Compute the numbers that set the regime: Reynolds `Re = U L / nu`, Mach, Froude, Rossby, Peclet, Richardson, Prandtl or Schmidt. Print them in every run log.
- Choose the model from the regime: laminar or transitional flows can be resolved directly; turbulent flows need DNS (all scales), LES (resolve large eddies, model small ones) or RANS (model all turbulence).
- **DNS cost.** The Kolmogorov scale is `eta = (nu^3 / epsilon)^(1/4)`. Pseudospectral DNS commonly requires `k_max * eta` of at least about 1 (about 1.5 or more for small-scale statistics). The number of grid points in 3D grows roughly as `Re^(9/4)`, so doubling Re costs far more than double. Estimate before promising a resolution.
- **Time step.** Advective CFL from the current maximum velocity; explicit viscous limits unless viscosity is treated implicitly or by an integrating factor (`time-integration-and-stability.md`).

## 3. Pseudospectral specifics

- **Dealiasing:** quadratic nonlinearities alias onto resolved modes; truncate with the 2/3 rule or pad by 3/2. Record which one (fluidsim exposes a dealiasing coefficient on the operator parameters).
- **Resolution check:** the energy spectrum near `k_max` should fall several decades below its peak. A spectrum that turns up at the highest wavenumbers means under-resolution or aliasing.
- **Dissipation choices** (hyperviscosity, its order and coefficient) shape the inertial range; report them with the forcing scheme, its wavenumber band and injection rate, and the random seed for stochastic forcing.
- **Energy budget:** for forced turbulence, `dE/dt = P - epsilon` (injection minus dissipation) must close; a residual comparable to either term indicates a bug or under-resolution. Track energy, enstrophy, injection and dissipation as time series.

```python
import numpy as np
from fluidsim.solvers.ns2d.solver import Simul

params = Simul.create_default_params()
params.oper.nx = params.oper.ny = 256
params.oper.Lx = params.oper.Ly = 2 * np.pi
params.nu_2 = 1e-3                           # viscosity (Laplacian order 2)
params.time_stepping.t_end = 20.0
params.init_fields.type = "noise"
params.output.periods_save.spatial_means = 0.1
params.output.periods_save.spectra = 0.5
params.output.sub_directory = "ns2d-decay-256"
sim = Simul(params)
sim.time_stepping.start()
```

Print `params` to see the full parameter tree for the installed version. Reload finished runs for analysis with `fluidsim.load_sim_for_plot(path)`; restarts start from saved state files. fluidsim needs an FFT backend (installed through its extras) and MPI for parallel runs.

## 4. Finite-volume engineering cases (OpenFOAM pattern)

- A case has `0/` (initial and boundary fields), `constant/` (mesh, physical properties, turbulence model) and `system/` (`controlDict`, `fvSchemes`, `fvSolution`, decomposition).
- Mesh with `blockMesh` or `snappyHexMesh`, then run `checkMesh` and fix failed checks before solving (`discretization-and-meshes.md`).
- Steady incompressible RANS commonly uses `simpleFoam`, transient flows `pimpleFoam`; recent releases of one OpenFOAM distribution moved to a single `foamRun` driver with selectable solver modules. Check which distribution and version is installed before copying tutorials.
- **Convergence means quantities, not only residuals.** Monitor integrated outputs (forces, pressure drop, mass flow imbalance, heat flux) until they stop changing, in addition to residuals.
- Wall treatment must match the first-cell `y+` (about 1 for wall-resolved, about 30 to 300 for wall functions, depending on the model); report the turbulence model and inlet turbulence quantities.
- Parallel runs: `decomposePar`, the solver with `-parallel` under the MPI launcher, `reconstructPar`.

## 5. Verify and validate

**Exact solutions:**

- 2D Taylor-Green vortex: `u = U sin(kx) cos(ky) F(t)`, `v = -U cos(kx) sin(ky) F(t)` with `F(t) = exp(-2 nu k^2 t)`; kinetic energy decays as `F(t)^2`. Checks advection and diffusion operators and the time integrator together.
- Couette and Poiseuille flows (steady, viscous; check the profile and wall shear).
- Decaying single Fourier modes for linear diffusion; inviscid conservation of energy and enstrophy in 2D spectral codes with viscosity set to zero over short times.

**Benchmarks** with published reference data: lid-driven cavity centerline velocities, laminar flow past a cylinder (Strouhal number and force coefficients at fixed Reynolds number, including the Schafer-Turek cylinder-in-channel benchmark), backward-facing step reattachment length, turbulent channel DNS databases. Cite the source of every reference value used and never quote one from memory without checking it (`verification-and-validation.md`).

**Statistics of turbulent flows:** discard the transient, average over many large-eddy turnover times, and give uncertainties from block averaging (`post-processing.md`). Check that statistics are stationary before reporting them.

## 6. Common failures

| Symptom | Likely cause | First step |
|---|---|---|
| Blow-up after some steps | CFL exceeded as velocities grew; poor mesh; incompatible boundary conditions (for example velocity and pressure both fixed at an outlet); unbounded convection scheme | Recompute CFL from the last good step; `checkMesh`; review boundary pairs; start with a bounded first-order scheme, then raise the order |
| Spectrum rises at high wavenumbers | Under-resolution or aliasing | Higher resolution, dealiasing, or stronger small-scale dissipation (reported) |
| Mean flow drifts in a periodic box | Forcing or numerical injection of the zero mode | Remove the mean mode; check forcing |
| Statistics depend on the averaging window | Not stationary or too short | Longer run; stationarity check; block-averaged error |
| Results change with the number of MPI ranks | Decomposition-dependent bug or reductions | Compare 1, 2 and 4 ranks on a small case |

## Checks (done when)

- [ ] Nondimensional numbers computed and logged; the modeling approach (DNS, LES, RANS) follows from them.
- [ ] Resolution justified by `k_max * eta`, spectra, `y+` or a grid study, as appropriate.
- [ ] At least one exact solution reproduced at the expected order before production runs.
- [ ] Integrated quantities converged, not only residuals; energy budgets close for forced turbulence.
- [ ] Turbulence statistics come with stationarity evidence and uncertainties.
- [ ] Benchmark comparisons cite verified sources.

## Anti-patterns

- Declaring convergence from residual plots alone.
- DNS claims without a resolution check of the smallest scales.
- Copying tutorials from a different OpenFOAM distribution or version.
- Reporting turbulence statistics from a few eddy turnover times.
