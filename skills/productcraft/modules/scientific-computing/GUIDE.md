# Scientific Computing

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Produce numerical and simulation results that can be trusted and repeated: the right solver and time integrator for the problem, discretizations and meshes that resolve it, verification against exact or reference solutions, honest uncertainty, campaigns whose every run is traceable, and compute used deliberately on laptops, clusters and paid platforms. Library references cover symbolic math, MATLAB-style numerics, astronomy, quantum computing and dynamics, molecular dynamics, fluid flow, discrete-event simulation, materials science, multi-objective optimization, hosted quantum chemistry and autonomous research assistants.

**Boundaries.** Machine learning, statistics and Bayesian modeling: `../ml-engineering/GUIDE.md`. Dataframes, SQL, Dask, Zarr pipelines and plotting libraries: `../data-engineering/GUIDE.md`. Bioinformatics, cheminformatics, structural biology and clinical data: `../life-sciences/GUIDE.md`. Papers, citations and literature search: `../research-writing/GUIDE.md`. The generic performance loop: `../engineering-practices/references/performance.md`. Unit discipline in code and property, differential and metamorphic tests: `../engineering-practices/references/spec-and-units.md` and `../engineering-practices/references/advanced-testing.md`. Cloud infrastructure for compute: `../cloud-infrastructure/GUIDE.md`. How the work is planned and verified as code changes: `../engineering-workflow/GUIDE.md`.

## When to activate

- Solving `A x = b`, `F(x) = 0` or an optimization inside a model; choosing direct or iterative solvers, preconditioners or Newton variants.
- Integrating ODEs or time-dependent PDEs; stiffness, tolerances, CFL limits, IMEX or splitting schemes; a run that blows up or crawls.
- Discretizing PDEs: finite differences, volumes, elements or spectral methods; stencils; meshes and mesh quality.
- Verifying a solver or a result: manufactured solutions, convergence studies, Richardson extrapolation, GCI, validation against experiments; diagnosing a failed run.
- Parameter sweeps, designs of experiments, sensitivity and uncertainty analysis, calibration, optimization of a simulation, campaign layout and provenance.
- Slurm or other batch jobs, checking resources before heavy compute, scaling studies, profiling numerical code.
- Post-processing simulation output: derived quantities, comparisons with references, time averages with error bars.
- Using SymPy, MATLAB or Octave code, Astropy, Qiskit, Cirq, PennyLane, QuTiP, OpenMM or MDAnalysis, fluidsim or OpenFOAM, SimPy, pymatgen, pymoo, a hosted quantum-chemistry platform, or an autonomous research assistant.
- **Not for** fitting statistical or machine-learning models to data (ML module), data pipelines and dashboards (data-engineering), or biology and chemistry database work (life-sciences), except where a simulation is the subject.

## Ground rules

1. **A finished run is not a result.** Results need evidence: agreement with an exact, manufactured or reference solution, a convergence study, and invariants that held. Say what was verified and mark the rest `NOT VERIFIED` with the reason.
2. **Units and scales are explicit.** Every input and output has a unit; nondimensional numbers are computed and logged; conversions happen once, at boundaries between tools.
3. **Tolerances are chosen, not inherited.** Solver, integrator and iteration tolerances are set from the problem's scales and kept well below the discretization error and the effect being measured. Library defaults are a starting point to question.
4. **Reproducible by construction.** Every run records code version, library versions, inputs with checksums, configuration, seeds, hardware and scheduler job ID. Raw outputs are never overwritten.
5. **Check the installed version.** Scientific libraries break APIs between releases (SciPy's `rtol`, NumPy 2, Qiskit 1.0 and 2.0, QuTiP 5, pymoo 0.6, pymatgen's date-based releases). Read the version first and use its documentation; say which version you assumed.
6. **Measure resources before heavy compute.** Run `scripts/resource_check.py`, estimate memory, time and disk from a small pilot, and never run heavy work on a login node.
7. **Shared and paid compute needs a go-ahead.** Submitting jobs to an allocation, running on quantum hardware, buying cloud instances or spending platform credits happens only after the user approves the size and estimated cost. Never cancel or change jobs you did not submit.
8. **Never invent data, results, benchmark values or citations.** When a reference value is unknown, say so and look it up or ask. Verify every cited source exists.
9. **Credentials stay out of the session.** API keys and tokens for data services, quantum providers and chemistry platforms are set by the user in the environment (`../agent-safety/GUIDE.md`).
10. **Licenses and terms travel with the work.** Note data licenses (for example CC BY attribution), restricted software (academic-only or licensed codes, non-redistributable pseudopotentials) and platform terms for uploaded data.

## Workflow for a simulation task

1. **Frame.** The question, the quantities of interest with units, the accuracy needed to answer it, and the compute budget.
2. **Model.** Governing equations, parameters with sources, nondimensional numbers and the regime they imply.
3. **Discretize and choose solvers** (`references/discretization-and-meshes.md`, `references/time-integration-and-stability.md`, `references/linear-and-nonlinear-solvers.md`).
4. **Verify the code** on an exact or manufactured solution and keep it as a regression test (`references/verification-and-validation.md`).
5. **Pilot.** A small run measures time per step, memory and output size; `scripts/resource_check.py` confirms the machine or allocation can hold the full run (`references/hpc-and-profiling.md`).
6. **Run** single cases or a campaign with provenance and runtime monitors (`references/parameter-studies-and-campaigns.md`).
7. **Verify the solution:** iterative, time-step and grid convergence; `scripts/convergence_order.py` for observed order and GCI.
8. **Post-process and compare** with references or experiments, with uncertainties (`references/post-processing.md`).
9. **Report** values with numerical and statistical uncertainty, the evidence behind them, versions, limitations and anything left unverified.

Small questions (one integrator choice, one stencil, one Slurm flag) need only the matching reference and its checks.

## Pick the references

| The work touches | Read | Minimum check before calling it done |
|---|---|---|
| Linear systems, preconditioners, Newton and quasi-Newton, Jacobian-free methods, optimization inside a model | `references/linear-and-nonlinear-solvers.md` | Return status checked; true residual reported; algebraic tolerance below discretization error; Jacobian passed a Taylor test |
| ODE integrators, stiffness, tolerances, events, IMEX and splitting, CFL and von Neumann limits, output and checkpoint cadence | `references/time-integration-and-stability.md` | Stiffness assessed; per-component `atol`; tighter-tolerance rerun agrees; every stability limit computed; restart reproduces a straight run |
| Finite differences, volumes, elements, spectral methods; stencils; boundary closures; advection schemes; meshes and quality; refinement | `references/discretization-and-meshes.md` | Stencils order-checked; mesh checked with the solver's tool; resolution backed by refinement |
| Code and solution verification, GCI, validation, preflight and runtime checks, failed or NaN runs | `references/verification-and-validation.md` | Observed order matches formal order; convergence type and GCI reported; validation combines uncertainties; first error diagnosed |
| Sweeps, designs of experiments, sensitivity, uncertainty propagation, calibration, optimizing a simulation, surrogates, campaign layout and provenance | `references/parameter-studies-and-campaigns.md` | Study framed before runs; seeds and versions recorded; failures kept in the table; counts match the plan |
| Resource checks, memory and time estimates, Slurm scripts, arrays, checkpoint signals, job accounting, scaling studies, profiling | `references/hpc-and-profiling.md` | Plan fits usable resources; user approved allocation use; `sacct` numbers read; performance claims measured |
| Reading output, derived quantities, comparisons with references, steady state, error bars on time averages, figures | `references/post-processing.md` | Weighted norms with units; transient removed; block-averaged errors; figures regenerate from saved data |
| SymPy derivations and code generation; MATLAB, Octave and `.mat` files; translating MATLAB to NumPy | `references/symbolic-math-and-matlab.md` | Symbolic results spot-checked numerically; no `sympify` on untrusted text; translations tested against saved outputs |
| Units, time scales, coordinates and cross-matching, FITS, WCS, cosmology (Astropy) | `references/astronomy-astropy.md` | Units end to end; time scales stated; matches use separation limits; WCS round-trip checked |
| Circuits, primitives, transpilation, noise and mitigation (Qiskit, Cirq, PennyLane) | `references/quantum-computing.md` | Exact-simulator check within shot noise; bit order tested; hardware runs approved |
| Master equations, trajectories, cavities and spins (QuTiP) | `references/quantum-dynamics-qutip.md` | Units and truncation converged; an analytic case reproduced |
| Molecular dynamics setup, runs and trajectory analysis (OpenMM, GROMACS, LAMMPS, MDAnalysis) | `references/molecular-dynamics.md` | Units converted; equilibration judged; periodic artifacts removed; replicas with correlation-aware errors |
| Pseudospectral and finite-volume flow simulation, turbulence resolution, CFD benchmarks | `references/fluid-simulation.md` | Regime from nondimensional numbers; resolution justified; exact solution reproduced; integrated quantities converged |
| Queues, resources and processes in discrete time (SimPy) | `references/discrete-event-simulation.md` | Warm-up and replications; time-weighted averages; analytic queue reproduced |
| Crystal structures, symmetry, phase diagrams, Materials Project data (pymatgen) | `references/materials-pymatgen.md` | Tolerances reported; compatible energies only; key kept in the environment; data cited |
| Pareto optimization, many objectives, hypervolume, decision making (pymoo) | `references/multi-objective-pymoo.md` | Minimization form; feasibility checked; normalized hypervolume over many seeds; stated choice rule |
| Hosted quantum-chemistry platforms and their local alternatives | `references/quantum-chemistry-cloud.md` | Upload and spend approved; pilot against a known value; method and versions recorded |
| LLM pipelines that generate ideas, analyses or papers | `references/research-assistants.md` | Every number traced to code that ran; every citation verified; human sign-off |

## Essentials

Use these when a reference is not needed. Open the reference when a bullet raises a question.

### Solvers
- Characterize the matrix first (size, sparsity, symmetry, definiteness, nullspace). Sparse direct for 2D-sized problems; Krylov with multigrid or incomplete factorization for large 3D ones.
- Check every return status and compute the true residual; a small residual times the condition number bounds the error.
- Newton converging slowly almost always means a wrong Jacobian: run a Taylor test before tuning anything else.

### Time integration and stability
- Stiff problems (explicit solvers take tiny steps for no visible reason) need Radau, BDF or IMEX schemes. Set `atol` per component in its units; SciPy's defaults are loose.
- Explicit PDE steps obey every limit at once (advection, diffusion, reaction, waves), recomputed from current speeds, with a safety factor.
- Checkpoint about every `sqrt(2 * write_time * mean_time_between_interruptions)`, before wall-time limits, and test the restart.

### Discretization and meshes
- Derive stencil weights and test their order on a smooth function; boundary closures and mesh quality decide accuracy more often than the interior scheme.
- Sharp fronts need limiters or WENO; smooth periodic problems reward spectral methods with dealiasing.

### Verification and validation
- Code verification (manufactured or exact solutions, observed order) before solution verification (convergence, GCI) before validation (experiments with combined uncertainties).
- Three or more systematically refined levels, ratio at least 1.3; report convergence type, observed order and the GCI band.

### Campaigns and optimization
- Fix numerical settings by verification; vary physical parameters with a design that fits the question (Sobol' or Latin hypercube beyond three dimensions).
- One directory per run with immutable inputs, a manifest and provenance; aggregate into one table that keeps failures.
- Noisy simulations defeat finite-difference gradients: use derivative-free or Bayesian methods and confirm optima with real runs.

### HPC and performance
- Size work from usable cores and memory (`scripts/resource_check.py`), not from `os.cpu_count()`; set thread variables to avoid oversubscription.
- Slurm: consistent layout, `--cpus-per-task` passed to `srun`, `--signal` for checkpoints, arrays mapped to manifest rows, `sacct` to right-size the next request.
- Run a scaling study before asking for many nodes.

### Post-processing
- Compare on common points with weighted norms and units; time averages need block-averaged errors; figures come from saved data by script.

## Scripts

Both are Python 3 standard library only, read-only, use no network and print deterministic output. Exit codes: 0 success, 1 a check failed, 2 usage error. `<productcraft>` is the folder where the ProductCraft skill is installed.

**`scripts/resource_check.py`** reports usable CPU cores (after affinity, cgroup quotas and Slurm), usable memory (after cgroup and Slurm limits), free disk at a path, GPU tools on PATH (looked up, never executed), oversubscribing thread variables, and whether this looks like a login node.

```bash
python3 <productcraft>/modules/scientific-computing/scripts/resource_check.py
python3 <productcraft>/modules/scientific-computing/scripts/resource_check.py --json --need-cores 8 --need-mem-gb 32 --need-disk-gb 100 --path /scratch/run01
```

**`scripts/convergence_order.py`** computes observed orders of accuracy, Richardson extrapolation and the grid convergence index from values at several resolutions (non-constant refinement ratios included), or orders from error norms against an exact solution.

```bash
python3 <productcraft>/modules/scientific-computing/scripts/convergence_order.py --h 0.04,0.02,0.01 --values 1.0128,1.0032,1.0008 --expected-order 2
python3 <productcraft>/modules/scientific-computing/scripts/convergence_order.py --cells 12000,96000,768000 --dim 3 --values 0.3215,0.3242,0.3249 --json
python3 <productcraft>/modules/scientific-computing/scripts/convergence_order.py --h 0.1,0.05,0.025 --values 4e-3,1.02e-3,2.6e-4 --errors
```

Tests: `python3 -B -m unittest discover -s <productcraft>/modules/scientific-computing/tests -v`.

## What to report

Add these to the workflow module's report and to `../../assets/review-template.md`:

- References used, and for each the minimum check from the table: met, not met, or `NOT VERIFIED` with the reason.
- Each reported quantity with units, numerical uncertainty (GCI band or tolerance study), statistical uncertainty where relevant, and the conditions it applies to.
- Verification evidence: exact or manufactured solution used, observed versus formal order, convergence type.
- Resource and cost facts: `scripts/resource_check.py` summary, pilot measurements, job sizes approved by the user, and job accounting after the run.
- Provenance: code commit, library versions, seeds, input checksums, campaign location.
- Commands the user still has to run (job submissions, hardware runs, platform batches) with their estimated cost.

## Working with other ProductCraft modules

- `../engineering-workflow/GUIDE.md`: tracks, done-when checks, test-first and debugging for the code that implements the model.
- `../engineering-practices/references/performance.md`, `spec-and-units.md` and `advanced-testing.md`: the measurement loop, unit discipline, and property-based, differential and metamorphic tests that suit numerical code (for example, a refined grid must not increase the error; two solvers must agree).
- `../ml-engineering/GUIDE.md`: surrogates built with machine learning, Bayesian calibration and statistical modeling.
- `../data-engineering/GUIDE.md`: dataframes, Dask and Zarr for large outputs, visualization libraries.
- `../life-sciences/GUIDE.md`: biomolecular structures, cheminformatics and biological databases that feed or consume simulations.
- `../research-writing/GUIDE.md`: writing up results, citation verification, literature search.
- `../cloud-infrastructure/GUIDE.md`: cloud compute and batch services, planned and costed before anything launches.
- `../agent-safety/GUIDE.md`: secrets for data and compute services, isolation for running generated code, stop-checks before deleting outputs.
- `../legal-ready/GUIDE.md`: license questions when distributing code built on copyleft or restricted scientific software.
