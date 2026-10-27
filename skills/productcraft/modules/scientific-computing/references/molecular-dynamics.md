# Molecular dynamics

Read this when setting up, running or analyzing molecular dynamics (MD): biomolecules in water, materials with interatomic potentials, trajectory analysis (RMSD, RMSF, contacts, hydrogen bonds, radial distribution functions), sampling statistics and free-energy estimates. Protein structure, docking and cheminformatics tooling live in `../../life-sciences/GUIDE.md`; quantum-chemistry calculations in `quantum-chemistry-cloud.md`.

## 1. Choose the engine and analysis tools

| Engine | Strengths |
|---|---|
| OpenMM | Python API, fast on GPUs, custom forces, easy scripting of protocols |
| GROMACS | Very fast biomolecular MD on CPUs and GPUs, mature tooling |
| LAMMPS | Materials and soft matter, very wide range of interatomic potentials, including machine-learned ones |
| AMBER (pmemd) and AmberTools | Biomolecular force fields and setup; pmemd needs a license, AmberTools is free |
| CP2K | Ab initio and hybrid MD |

Analysis: MDAnalysis and MDTraj (Python), `gmx` tools, VMD. Setup: PDBFixer (missing atoms, protonation), the OpenFF toolkit and GAFF tools (small-molecule parameters), PACKMOL (initial packing). Check each tool's license before redistributing anything built on it.

## 2. Units differ by package

| Package | Length | Time | Energy |
|---|---|---|---|
| OpenMM | nm | ps | kJ/mol (with explicit `openmm.unit` quantities) |
| GROMACS | nm | ps | kJ/mol |
| MDAnalysis | angstrom | ps | kJ/mol |
| LAMMPS `units real` | angstrom | fs | kcal/mol |
| LAMMPS `units metal` | angstrom | ps | eV |

Convert explicitly at every boundary between tools, and name variables with units. A factor-of-10 length error between nm and angstrom produces plausible-looking nonsense.

## 3. Protocol skeleton

1. **Prepare the structure.** Fix missing atoms and residues, choose alternate locations, assign protonation states at the target pH (PROPKA or a similar tool, then inspect histidines and active sites), and decide on disulfides and cofactors. Write down every choice.
2. **Choose a force field and a matching water model.** For example Amber ff14SB with TIP3P, Amber ff19SB with OPC, CHARMM36m with CHARMM-modified TIP3P; small molecules with GAFF2 or OpenFF. Mixing families or water models outside their parameterization invalidates the model.
3. **Solvate and neutralize.** Add counter-ions and salt to the target ionic strength; use box padding of at least about 1 nm, so the solute stays farther than the cutoff from its own periodic images; the box must also be longer than twice the cutoff in every direction (minimum image convention).
4. **Minimize energy.**
5. **Equilibrate.** NVT with positional restraints on solute heavy atoms, then NPT, releasing restraints in stages. Watch temperature, pressure, density and box volume until they fluctuate around stable values.
6. **Production.** Time step 2 fs with bonds to hydrogen constrained (about 4 fs with hydrogen mass repartitioning); PME electrostatics; the cutoff the force field was parameterized with; a Langevin or Nose-Hoover thermostat or stochastic velocity rescaling; a Monte Carlo or Parrinello-Rahman barostat. The Berendsen thermostat and barostat do not sample the correct ensemble: use them, if at all, only during early equilibration.
7. **Save** trajectory frames at the interval the analysis needs (often 10 to 100 ps) and checkpoints for restarts.

```python
from openmm import app, unit, LangevinMiddleIntegrator, MonteCarloBarostat

pdb = app.PDBFile("prepared_solvated.pdb")           # protonated, solvated, neutralized
forcefield = app.ForceField("amber14-all.xml", "amber14/tip3pfb.xml")
system = forcefield.createSystem(pdb.topology, nonbondedMethod=app.PME,
                                 nonbondedCutoff=1.0 * unit.nanometer, constraints=app.HBonds)
system.addForce(MonteCarloBarostat(1.0 * unit.bar, 300 * unit.kelvin))
integrator = LangevinMiddleIntegrator(300 * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds)
integrator.setRandomNumberSeed(2026)

simulation = app.Simulation(pdb.topology, system, integrator)
simulation.context.setPositions(pdb.positions)
simulation.minimizeEnergy()
simulation.context.setVelocitiesToTemperature(300 * unit.kelvin, 2026)
simulation.reporters.append(app.DCDReporter("traj.dcd", 5000))                 # every 10 ps
simulation.reporters.append(app.StateDataReporter("state.csv", 5000, step=True, temperature=True,
                                                  potentialEnergy=True, density=True, speed=True))
simulation.reporters.append(app.CheckpointReporter("state.chk", 50000))
simulation.step(500_000)                                                         # 1 ns
```

This skips the restrained equilibration stages for brevity; production protocols include them. Record the OpenMM version, the platform (CUDA, OpenCL, CPU) and its precision mode.

## 4. Trajectory analysis (MDAnalysis 2.x)

```python
import MDAnalysis as mda
from MDAnalysis import transformations as trans
from MDAnalysis.analysis import align, rms

u = mda.Universe("topology.pdb", "traj.dcd")
protein = u.select_atoms("protein")
u.trajectory.add_transformations(
    trans.unwrap(u.atoms),                        # make molecules whole across periodic boundaries
    trans.center_in_box(protein, center="mass"),
    trans.wrap(u.select_atoms("not protein"), compound="residues"),
)
rmsd = rms.RMSD(u, select="backbone").run()
print(rmsd.results.rmsd[:5])                      # columns: frame, time (ps), RMSD (angstrom)

average = align.AverageStructure(u, select="protein and name CA", ref_frame=0).run()
align.AlignTraj(u, average.results.universe, select="protein and name CA", in_memory=True).run()
rmsf = rms.RMSF(protein.select_atoms("name CA")).run()
```

- **Periodic boundaries** break molecules and complexes across the box. Make them whole and center them before RMSD, RMSF, distances or visualization; unwrapping needs bond information in the topology.
- **Align before fluctuation analysis**, and say which atoms defined the alignment.
- Other standard analyses: hydrogen bonds (`MDAnalysis.analysis.hydrogenbonds`), radial distribution functions (`analysis.rdf.InterRDF`), contacts, dihedral distributions, principal components.
- Large trajectories: iterate with a stride, analyze in chunks, or split frames across processes.

## 5. Sampling and statistics

- One trajectory is one sample of the ensemble. Run several independent replicas (different initial velocities, ideally different starting structures) and report the mean with its standard error across replicas.
- Frames are correlated: estimate uncertainty with block averaging or the autocorrelation time (`post-processing.md`), not with the number of frames.
- An RMSD plateau shows the structure stopped drifting, not that the ensemble is sampled.
- Rare events (binding, folding, large conformational change) need enhanced sampling (umbrella sampling, metadynamics with PLUMED, replica exchange) or much longer runs.
- **Free energies:** use established methods and tools (MBAR or WHAM via `pymbar`, alchemical free-energy workflows such as openmmtools and OpenFE). Check overlap between neighboring states and convergence by comparing forward and reverse halves of the data.

## 6. Checks that catch broken simulations

- **NVE energy drift:** a short constant-energy run from an equilibrated state should conserve total energy well; noticeable drift points at too large a time step, missing constraints or a cutoff problem.
- **Ensemble checks:** temperature fluctuations consistent with the canonical ensemble for the system size; density close to the published value for the chosen water model at that temperature and pressure.
- **Physical sanity:** no atoms flying apart, no unexpected unfolding of a stable fold in the first nanoseconds, ions not stuck to one residue throughout.
- **Experiment:** compare with measurable observables where available (NMR order parameters and couplings, SAXS profiles, crystallographic B-factors with care).

## 7. Reproducibility

Record engine and version, force field and water model with versions, every preparation choice (protonation, missing residues, ions), complete input files (OpenMM XML or scripts, GROMACS `.mdp`, LAMMPS input), seeds, platform and precision, and hardware. GPU runs are usually not bitwise reproducible, and long MD trajectories diverge chaotically anyway; reproducibility means statistically consistent results across replicas, not identical frames. OpenMM's CUDA platform offers a deterministic-forces property when bitwise repeatability of a short run matters for debugging.

## Checks (done when)

- [ ] Units converted explicitly at every tool boundary.
- [ ] Preparation choices, force field, water model and protocol written down with versions.
- [ ] Equilibration judged by stable temperature, pressure, density and volume, not by a fixed length alone.
- [ ] Periodic artifacts removed and alignment done before structural analysis.
- [ ] Results reported across independent replicas with correlation-aware uncertainties.
- [ ] Free energies come from an established estimator with overlap and convergence checks.

## Anti-patterns

- Berendsen coupling in production runs.
- RMSD computed on trajectories with molecules split across the box.
- One long trajectory reported as "the" behavior, with frame-count error bars.
- Force fields and water models mixed outside their parameterization.
- A 4 fs time step without hydrogen mass repartitioning.
