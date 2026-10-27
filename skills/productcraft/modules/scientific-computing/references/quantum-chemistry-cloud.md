# Quantum chemistry on cloud platforms

Read this when computational chemistry runs on a hosted platform through an API (geometry optimization, conformer search, single-point energies and frequencies, pKa or redox predictions, descriptors, docking or structure prediction workflows), or when deciding between such a platform and local open-source codes. Cheminformatics libraries and molecular databases are in `../../life-sciences/GUIDE.md`; classical molecular dynamics in `molecular-dynamics.md`.

## What a hosted platform changes

Hosted chemistry platforms wrap standard methods (force fields, semiempirical tight-binding such as GFN2-xTB, density functional theory, neural-network potentials, docking) behind job submission, credits and a results store. They remove cluster setup; they add data transfer to a third party, cost per job, and less visibility into exact settings and versions.

| Fits | Does not fit |
|---|---|
| No local cluster; many small, standard calculations | Confidential structures under obligations that forbid third-party processing |
| Standard workflows with documented defaults | Work that needs full control of every keyword |
| Fast turnaround for screening | Results that must be reproducible years later with exact versions, unless the platform exposes them |
| Pilots before investing in local infrastructure | Large campaigns where per-job pricing exceeds local compute cost |

## Ground rules

1. **Keys and accounts.** API keys live in an environment variable or secrets manager that the user sets; never in code, notebooks, logs or chat (`../../agent-safety/GUIDE.md`, `../../integrations/GUIDE.md` for general API practice).
2. **Confidentiality.** Read the platform's terms on data retention, reuse of submitted structures, and processing location. Get the user's explicit OK before uploading proprietary or unpublished compounds.
3. **Cost control.** Estimate credits per job type times the number of molecules; run a pilot on one to three molecules; agree a spending cap with the user before any batch; cancel orphaned jobs.
4. **Reliable submission.** Store job IDs as you submit, skip molecules already submitted (idempotent batches), poll with backoff, honor rate limits, retry only transient failures.
5. **Record** for every result: method (functional, dispersion correction, basis set or method family), solvent model, charge and multiplicity, input geometry (with checksum), conformer-search settings, software and version as reported by the platform, and the job ID. If the platform does not report versions or exact settings, say so in the results.

## Method choice and honest expectations

| Method class | Good for | Limits |
|---|---|---|
| Force fields (MMFF94, GAFF, OpenFF) | Conformer generation, quick geometries | No bond breaking; energies only meaningful within the force field |
| Semiempirical tight-binding (GFN2-xTB) | Geometries, conformer pre-screening, large systems | Energies rough; errors of several kcal/mol are common |
| Neural-network potentials | Near-DFT energies and geometries at low cost within their training domain | Unreliable outside it: check element coverage, charge and spin support, and unusual bonding |
| DFT (dispersion-corrected hybrids, efficient composite methods such as r2SCAN-3c) | Reaction energies, geometries, frequencies, properties | Errors of a few kcal/mol depending on functional and property; check benchmark studies (for example the GMTKN55 collection) for the property type |
| Coupled cluster (for example DLPNO-CCSD(T)) | Reference energies for small sets | Expensive; basis-set convergence matters |
| Predicted pKa and redox potentials | Ranking within a chemical series | Absolute errors can reach one pKa unit or more; validate on close analogs with known experimental values |

Never present a computed property as an experimental value, and give the method with every number.

## Workflow

1. **Validate inputs locally.** Parse SMILES with RDKit and sanitize; set stereochemistry explicitly; enumerate relevant tautomers and protonation states; check total charge and spin multiplicity.
2. **Conformers.** Properties of flexible molecules depend on the ensemble. Generate conformers, refine the low-energy ones at a better level, and Boltzmann-weight at the stated temperature.
3. **Optimize and verify stationary points.** Frequencies confirm a minimum (no imaginary frequencies) or a transition state (exactly one, along the expected motion).
4. **Solvation.** Implicit models (CPCM, SMD) capture bulk effects but miss specific interactions such as strong hydrogen bonding to solvent; add explicit solvent molecules when they matter and say so.
5. **Pilot against a known reference.** Compute a property with a published experimental or high-level value for a test molecule before the batch, and compare.
6. **Batch** with idempotent submission, then download raw outputs as well as parsed results and archive them with the inputs.
7. **Validate outputs:** convergence flags, SCF convergence, imaginary frequencies, geometry sanity (bond lengths, no fragmentation), consistency of charge and multiplicity.

### Input validation and idempotent submission

```python
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

def validate(smiles: str) -> dict:
    """Parse and sanity-check one input before any credits are spent."""
    mol = Chem.MolFromSmiles(smiles)                     # None when parsing or sanitization fails
    if mol is None:
        raise ValueError(f"unparseable SMILES: {smiles!r}")
    centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)
    unpaired = sum(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms())
    return {"canonical_smiles": Chem.MolToSmiles(mol), "formula": rdMolDescriptors.CalcMolFormula(mol),
            "charge": Chem.GetFormalCharge(mol), "unassigned_stereocenters": [i for i, c in centers if c == "?"],
            "multiplicity_if_high_spin": unpaired + 1}
```

```python
import json
from pathlib import Path

def submit_batch(molecules: dict, submit, ledger_path: str, method: dict) -> dict:
    """submit(smiles, method) wraps the platform SDK call and returns a job ID; names differ per platform."""
    path = Path(ledger_path)
    ledger = json.loads(path.read_text()) if path.exists() else {}
    for key, smiles in molecules.items():
        if key in ledger:                                 # submitted before: never pay twice
            continue
        ledger[key] = {"job_id": submit(smiles, method), "smiles": smiles, "method": method}
        write_json_atomic(ledger_path, ledger)            # from parameter-studies-and-campaigns.md
    return ledger
```

Stop the batch on the first authentication, quota or validation error instead of retrying it for every molecule.

## Local open-source alternatives and cross-checks

- **xtb** and **CREST** (tight-binding and conformer search), **PySCF** (Python, Apache-2.0; GPU acceleration through its GPU extension), **Psi4** (LGPL), **NWChem**, **CP2K** (GPL).
- **ORCA** is free for academic use under its license agreement, not for commercial use without a separate license; Gaussian and Q-Chem are commercial. Check the license before using any of them for commercial work.
- Recompute a sample of platform results locally with the same method to confirm settings were what you assumed.

## Checks (done when)

- [ ] The user approved uploading the structures and the spending cap; keys stayed out of code and output.
- [ ] Inputs validated locally (charge, multiplicity, stereochemistry, protonation states).
- [ ] A pilot reproduced a known reference within the method's expected error.
- [ ] Every result carries method, solvent model, versions (or a note that they are unavailable) and job ID.
- [ ] Outputs checked for convergence and correct stationary points before use.

## Anti-patterns

- Bulk-submitting a library before a single pilot.
- Comparing energies computed with different methods, solvent models or conformer treatments.
- Treating a neural-network potential as reliable for elements or charges it was not trained on.
- Uploading confidential compounds without checking the platform's terms.
