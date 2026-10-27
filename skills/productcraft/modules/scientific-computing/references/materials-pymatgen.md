# Materials science with pymatgen

Read this when working with crystal structures (CIF, POSCAR and other formats), symmetry, structure comparison, phase diagrams and energies above the convex hull, electronic-structure outputs, or data from the Materials Project.

## Setup and versions

- pymatgen uses date-based versions (for example `2025.x.y`) and from time to time renames or moves functions; check the installed version (`pip show pymatgen`) and its changelog before reusing older examples. Core imports: `from pymatgen.core import Structure, Lattice, Composition, Element`.
- **Materials Project access** goes through the `mp-api` client: `from mp_api.client import MPRester`. It reads the API key from the `MP_API_KEY` environment variable; the user sets it, and it never appears in code, notebooks or chat. The legacy API client in `pymatgen.ext.matproj` is deprecated; use `mp-api`.
- **Data terms:** Materials Project data are released under CC BY 4.0, so attribution is required; cite the database and the specific calculations or entries used, and respect the API rate limits.
- **Neighbors in the ecosystem:** ASE (atoms objects and calculators; convert with `pymatgen.io.ase.AseAtomsAdaptor`), spglib (the symmetry engine under pymatgen's analyzer), phonopy, atomate2 with jobflow (workflows), custodian (error recovery for DFT runs), matminer (descriptors).
- **Licensing:** VASP requires a license, and its POTCAR pseudopotential files may not be redistributed: never commit them to a repository or include them in shared archives.

## Structures

```python
from pymatgen.core import Lattice, Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

rocksalt = Structure.from_spacegroup("Fm-3m", Lattice.cubic(5.64), ["Na", "Cl"],
                                     [[0, 0, 0], [0.5, 0.5, 0.5]])
analyzer = SpacegroupAnalyzer(rocksalt, symprec=0.01)
assert analyzer.get_space_group_number() == 225
primitive = analyzer.get_primitive_standard_structure()
assert len(rocksalt) == 8 and len(primitive) == 2          # conventional versus primitive cell

supercell = rocksalt.copy()
supercell.make_supercell([2, 2, 2])
rocksalt.to(filename="POSCAR")                              # format from the file name
```

- Lengths are in angstrom and energies in eV throughout pymatgen; VASP stresses are reported in kbar. Convert explicitly when combining with other tools.
- **Reading CIFs:** `Structure.from_file("x.cif")` for simple cases; `CifParser("x.cif").parse_structures(primitive=False)` for control. The default for `primitive` changed in 2024; pass it explicitly. Read parser warnings: they flag symmetry fixes and occupancy problems.
- **Disorder:** experimental CIFs often have partial occupancies. DFT needs an ordered model: enumerate orderings (`OrderDisorderedStructureTransformation`, enumlib) or build special quasirandom structures, and report the choice.
- Coordinates are fractional unless stated; neighbors respect periodic images (`structure.get_neighbors(site, r)`).

## Symmetry and comparison

- `SpacegroupAnalyzer(structure, symprec=0.01, angle_tolerance=5)`: the detected space group depends on the tolerance. Relaxed structures with small numerical noise may need `symprec=0.1`; report the tolerance with the result.
- Standardize before comparing or publishing: `get_conventional_standard_structure()` or `get_primitive_standard_structure()`.
- Duplicates and equivalence: `StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5)` with `fit(a, b)` or `group_structures(list)`; tolerances decide what counts as "the same" and belong in the report.

## Thermodynamic stability

```python
from mp_api.client import MPRester
from pymatgen.analysis.phase_diagram import PhaseDiagram

with MPRester() as mpr:                                      # key from MP_API_KEY
    entries = mpr.get_entries_in_chemsys(["Li", "Fe", "O"])
diagram = PhaseDiagram(entries)
for entry in sorted(entries, key=diagram.get_e_above_hull)[:5]:
    print(entry.composition.reduced_formula, round(diagram.get_e_above_hull(entry), 4), "eV/atom")
```

- Energy above the hull (eV/atom) measures thermodynamic stability at 0 K within the DFT model. Zero means on the hull; small positive values mean metastable. Cut-offs for "probably synthesizable" are heuristics used in the literature, not physical laws; state the one you use and why.
- **Compare only compatible energies.** Mixing your own DFT energies with database entries requires the same functional, Hubbard U values, pseudopotentials and cutoffs (the Materials Project input sets) and the same correction scheme (`MaterialsProject2020Compatibility`), or the database's documented mixing scheme for different functionals. Otherwise hull distances are meaningless.
- The 0 K hull ignores finite-temperature entropy, kinetics and synthesis conditions. Say so when the question is about real-world stability.

Querying many materials: `mpr.materials.summary.search(chemsys="Li-Fe-O", energy_above_hull=(0, 0.05), fields=["material_id", "formula_pretty", "energy_above_hull", "band_gap"])` returns only the requested fields, which is faster and lighter on the service.

## Electronic structure and calculation outputs

- Parse with `Vasprun("vasprun.xml")` (check `converged` before using anything), `Outcar`, and the band-structure and density-of-states objects (`get_band_structure()`, `complete_dos`); plot with `BSPlotter` and `DosPlotter`.
- Semilocal functionals (GGA) underestimate band gaps systematically; never present a GGA gap as the experimental gap.
- Converge k-point density and plane-wave cutoff for the property of interest, and report smearing settings.
- Generate inputs from standard sets (`MPRelaxSet`, `MPStaticSet`) when results must be compatible with database entries; record any overrides.

## Checks (done when)

- [ ] Structures load with parser warnings read; disorder handled explicitly; units stated.
- [ ] Symmetry results reported with `symprec` and angle tolerance; comparisons with matcher tolerances.
- [ ] Hull analyses use compatible, consistently corrected energies; thresholds are labeled heuristics.
- [ ] Calculation outputs checked for convergence before use; GGA gaps labeled as such.
- [ ] The API key stayed in the environment; Materials Project data cited under CC BY 4.0; no POTCAR files in shared material.

## Anti-patterns

- Mixing your own DFT energies with database entries computed with different settings.
- Trusting the space group from one tolerance without saying which.
- Running DFT directly on partially occupied CIF sites.
- An API key pasted into a notebook cell.
