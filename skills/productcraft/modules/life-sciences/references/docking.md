# Protein-ligand docking

Read this when you predict how a small molecule binds a protein, run a structure-based virtual screen, or triage docking output. Ligand preparation and chemistry are in `rdkit-and-datamol.md`; protein models and embeddings in `protein-language-models.md`; molecular dynamics and free-energy methods in `../../scientific-computing/GUIDE.md`.

## What docking gives you, and what it does not

- **Pose prediction** (where and how a ligand sits) is the reliable part when the binding site is known and the protein conformation is close to the bound form.
- **Affinity prediction** is not. Docking scores and diffusion-model confidence values correlate weakly with measured binding; they rank poses, not compounds. Never report a docking score as an affinity, a Kd or a probability of activity.
- Everything is a hypothesis for an assay. Say so in the report.

## Choose a method

| Situation | Method |
|---|---|
| Known site, standard drug-like ligand, need a baseline | Classical docking with a search and a scoring function (AutoDock Vina, smina, GNINA) |
| Site unknown or whole-protein search, want a learned prior over poses | Diffusion-based docking (DiffDock and successors) |
| Rescoring poses | A different scoring function than the one that generated them (for example a neural scorer, or MM/GBSA after minimization) |
| Quantitative affinity differences in a congeneric series | Free-energy perturbation, with the cost and expertise it requires |
| Covalent binders, metal coordination, large peptides | Specialized protocols; general docking handles them poorly |

Running one classical and one learned method and comparing poses is usually more informative than tuning one.

## Prepare the inputs (this decides the result)

**Protein**
- Pick the structure deliberately: resolution, the bound ligand it was solved with (conformations are biased toward it), missing loops, mutations and construct tags. Predicted structures are usable but less reliable for side-chain placement in the site; check per-residue confidence at the site.
- Keep or remove waters and cofactors by design: structural waters bridging the site and catalytic metals often matter. Record what you kept.
- Add hydrogens and assign protonation at the intended pH (for example with PDBFixer, `pdb2pqr` or the docking suite's own preparation), check histidine tautomers in the site, and fix missing side chains.

**Ligand**
- Standardize, choose the dominant protonation state at assay pH, enumerate unspecified stereocenters and relevant tautomers, and generate a reasonable 3D conformer (`rdkit-and-datamol.md`). Docking cannot fix a wrong protonation or a missing stereocenter.

**Site**
- Classical docking needs a box or center. Derive it from a known ligand, a conserved pocket or a pocket-detection tool, and record the coordinates and size. An oversized box wastes sampling and lowers accuracy.

## Classical docking

```bash
# Vina-style run, box derived from a reference ligand
vina --receptor protein.pdbqt --ligand ligand.pdbqt \
     --center_x 12.4 --center_y -3.1 --center_z 25.8 \
     --size_x 22 --size_y 22 --size_z 22 \
     --exhaustiveness 16 --num_modes 9 --seed 42 --out poses.pdbqt
```

- Raise `exhaustiveness` for flexible ligands; results vary run to run, so set and record the seed and repeat a few times.
- Scores are in kcal/mol by convention but are empirical fits; treat them as a ranking within one target and one protocol.

## Diffusion-based docking

Diffusion models (DiffDock and its successors) sample poses directly, without a user-defined box, and return a confidence value per pose.

- **Inputs:** a protein structure (or a sequence, which is folded first) and ligand SMILES or structure files. Batch jobs take a table of complexes.
- **Sampling:** generate several poses per complex (tens for hard cases), then cluster them. Agreement among top poses is a better signal than any single confidence value.
- **Confidence is not affinity.** It expresses the model's certainty about the pose. It drops for large ligands, multi-chain systems and targets unlike the training data (which is largely crystallographic protein-ligand complexes).
- **Compute:** a GPU is effectively required; the first run precomputes lookup tables. Precompute protein embeddings once when screening many ligands against one target.
- The field moves fast and public benchmarks have repeatedly shown that pose-prediction methods can produce physically invalid poses that still score well. Check physical validity explicitly (below).

## Validate before believing

1. **Redock a known ligand.** Take a complex solved with a ligand, remove it, dock it back, and measure symmetry-corrected RMSD to the crystal pose. Under 2 Angstrom is the usual success criterion. If your protocol fails this on the target's own structure, it will not do better on new ligands.
2. **Check physical validity** of every pose you keep: no clashes with protein or internal atoms, sensible bond lengths and angles, correct stereochemistry preserved, ligand inside the pocket rather than on the surface. Tools such as PoseBusters run these checks; do not skip them for learned methods.
3. **Inspect interactions:** hydrogen bonds, salt bridges and hydrophobic contacts with residues known to matter for the target. A pose that ignores the key anchor residue is suspect even with a good score.
4. **Decoy test for screening:** include known actives and property-matched decoys, and report enrichment (for example enrichment factor at 1% and BEDROC) rather than a hit list alone. A protocol that does not enrich actives will not find new ones.

## Virtual screening

- Filter the library first (`medchem-filters.md`): remove reactive and interfering compounds, apply property ranges, deduplicate by InChIKey.
- Prepare ligands in bulk, record the protocol, and keep the mapping from each pose back to its input molecule.
- Expect the score distribution to be dominated by molecular size; normalize or compare within size bins, and look at ligand efficiency.
- Review the top compounds by eye and by chemistry before any purchase or synthesis, and send a diverse selection rather than one scaffold.
- Report: library size, filters, protocol, number of poses, validity check results, enrichment on the control set, and the selection rule.

## Reporting rules

- Always state: structure (PDB ID or model with its source), preparation choices, site definition, method and version, sampling settings, seeds and validation results.
- Never write that a compound "binds", "is active" or "has an affinity of" based on docking. Write that it is a predicted pose with the evidence that supports it, and name the assay that would test it.

## Checks (done when)

- [ ] Protein and ligand preparation choices (waters, cofactors, protonation, stereochemistry, tautomers) recorded.
- [ ] Redocking a known ligand reached sub-2-Angstrom RMSD, or the limitation is reported.
- [ ] Kept poses passed explicit physical-validity checks and interaction inspection.
- [ ] Screening reports enrichment against actives and matched decoys, not only a ranked list.
- [ ] No score or confidence value is presented as an affinity or a probability of activity.
