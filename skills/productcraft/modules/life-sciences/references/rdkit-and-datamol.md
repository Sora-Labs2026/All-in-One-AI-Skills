# Cheminformatics with RDKit and datamol

Read this when you parse, clean, compare, search, cluster, split or draw molecules: SMILES and SDF handling, standardization, descriptors, fingerprints, similarity, substructure search, scaffolds, reactions and conformers. Filters and alerts are in `medchem-filters.md`; featurization for models in `molecular-ml.md`.

## RDKit or datamol

RDKit is the underlying toolkit and exposes everything. datamol is a thin layer over it with simpler calls, sane defaults and easy parallelism; it returns ordinary RDKit molecules, so mixing the two is fine. Use datamol for routine pipeline work, RDKit directly when you need control.

```bash
python -m pip install rdkit datamol        # conda-forge packages also work
python -c "import rdkit, datamol; print(rdkit.__version__, datamol.__version__)"
```

RDKit versions are date-based (for example 2024.09.x). Record the version: aromaticity perception, descriptor definitions and default fingerprint behavior change between releases, so fingerprints and descriptors are only comparable within one version.

## Parsing: always check for failures

```python
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.info")           # keep warnings and errors visible

mols, failed = [], []
for idx, smi in enumerate(smiles_list):
    m = Chem.MolFromSmiles(smi)             # None on failure, with a message on the log
    (mols if m is not None else failed).append(m if m is not None else (idx, smi))
print(f"parsed {len(mols)}, failed {len(failed)}")
```

- Every `MolFrom*` returns `None` on failure. Count and report failures; never filter them out silently.
- `Chem.MolFromSmiles` sanitizes by default (valence checks, aromaticity, stereochemistry). `sanitize=False` plus `Chem.DetectChemistryProblems(m)` tells you what is wrong with a stubborn structure.
- SD files: `Chem.SDMolSupplier` yields `None` for unparsable records; `ForwardSDMolSupplier` streams (including from a gzip handle) and `MultithreadedSDMolSupplier` parallelizes. Property fields are strings until you convert them.
- Keep the original identifier with every molecule (`m.SetProp("_Name", ...)` or a parallel list); RDKit objects carry no index.

## Standardize before anything else

Two records of the same compound differ by salt, charge, tautomer or isotope. Comparisons, deduplication and models all need one representation.

```python
import datamol as dm

mol = dm.to_mol(smiles, sanitize=True)
mol = dm.fix_mol(mol)
mol = dm.sanitize_mol(mol)
mol = dm.standardize_mol(mol, disconnect_metals=False, normalize=True,
                         reionize=True, uncharge=False, stereo=True)
parent = dm.keep_largest_fragment(mol)     # drop counter-ions
inchikey = dm.to_inchikey(parent)
```

Decide and record each step:
- **Salts and mixtures:** keep the largest organic fragment, or keep the mixture when it matters.
- **Charge:** neutralize, or keep the state relevant at assay pH. Be consistent across the dataset.
- **Tautomers:** canonicalize with RDKit's `rdMolStandardize.TautomerEnumerator` when duplicates matter; note that canonical tautomer choice can change between RDKit releases.
- **Stereochemistry:** keep it unless the assay cannot distinguish isomers. Dropping it merges enantiomers with different activity.
- **Deduplicate** on InChIKey of the standardized parent (the full key for exact matches, the first block to group stereoisomers and tautomer variants). Report how many duplicates were merged and how conflicting measurements were resolved.

## Descriptors

```python
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors

props = {
    "mw": Descriptors.MolWt(mol),
    "clogp": Crippen.MolLogP(mol),
    "tpsa": rdMolDescriptors.CalcTPSA(mol),
    "hbd": rdMolDescriptors.CalcNumHBD(mol),
    "hba": rdMolDescriptors.CalcNumHBA(mol),
    "rotb": rdMolDescriptors.CalcNumRotatableBonds(mol),
    "arom_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
    "fsp3": rdMolDescriptors.CalcFractionCSP3(mol),
}
all_props = Descriptors.CalcMolDescriptors(mol)     # the full set as a dict
```

- Computed logP and TPSA are estimates from fragment models, not measurements; report them as computed values.
- Descriptors depend on the standardization state (charge, salts, explicit hydrogens). Compute them after standardization, always the same way.
- A few descriptors fail or return extreme values on unusual structures; guard the loop and inspect outliers.

## Fingerprints and similarity

```python
from rdkit.Chem import rdFingerprintGenerator
from rdkit import DataStructs

gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)   # ECFP4-like
fps = [gen.GetFingerprint(m) for m in mols]
sims = DataStructs.BulkTanimotoSimilarity(fps[0], fps[1:])
```

- Use the generator API (`rdFingerprintGenerator`); the old `AllChem.GetMorganFingerprintAsBitVect` helpers are deprecated.
- Radius 2 with 2048 bits is the common default; `GetCountFingerprint` keeps counts; feature-based variants (FCFP-like) generalize across scaffolds.
- **Tanimoto values are not absolute.** Similarity depends on fingerprint type, radius and size, so thresholds (the often-quoted 0.85) do not transfer between settings. Calibrate on your own data, and always state the fingerprint.
- MACCS keys (166 bits) are fast and coarse; atom-pair and topological-torsion fingerprints capture different relationships; 3D descriptors need conformers and alignment.
- For large libraries, use a bulk similarity call, `rdSubstructLibrary` or a chemical cartridge instead of Python loops.

## Substructure search and SMARTS

```python
patt = Chem.MolFromSmarts("[CX3](=O)[OX2H1]")     # carboxylic acid
hits = mol.GetSubstructMatches(patt)
```

- SMARTS is not SMILES: `[nH]` differs from `N`, and aromatic and aliphatic atoms do not cross-match. Test every pattern against molecules that must match and molecules that must not.
- `useChirality=True` makes matching stereo-aware when needed.
- Query a large library through `rdSubstructLibrary` with a pattern fingerprint screen-out; a naive loop over a million molecules is orders of magnitude slower.

## Scaffolds and splits

```python
from rdkit.Chem.Scaffolds import MurckoScaffold
scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
```

- Bemis-Murcko scaffolds group series. The generic (atom-type-stripped) form groups more aggressively; pick one and say which.
- **Random splits leak** in chemistry: analogs end up on both sides and scores look far better than they are. Split by scaffold or by fingerprint clusters (`molecular-ml.md`, `../../ml-engineering/references/evaluation-and-leakage.md`).

## Clustering and diversity

```python
from rdkit.ML.Cluster import Butina

dists = []
for i in range(1, len(fps)):
    dists.extend(1 - s for s in DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i]))
clusters = Butina.ClusterData(dists, len(fps), distThresh=0.35, isDistData=True)
```

The distance list grows with the square of the number of molecules: 20,000 molecules is about 200 million distances. Above a few thousand, use sphere exclusion or MaxMin picking (`rdkit.SimDivFilters`) or cluster in a reduced space.

## Reactions

```python
from rdkit.Chem import AllChem
rxn = AllChem.ReactionFromSmarts("[C:1](=[O:2])[OH].[N:3]>>[C:1](=[O:2])[N:3]")
products = rxn.RunReactants((acid, amine))
for (p,) in products:
    Chem.SanitizeMol(p)          # products come back unsanitized
```

Atom maps carry atoms across; unmapped atoms are dropped. A reaction can produce several product sets (one per match), including duplicates: deduplicate on canonical SMILES.

## Conformers

```python
from rdkit.Chem import AllChem
mh = Chem.AddHs(mol)
cids = AllChem.EmbedMultipleConfs(mh, numConfs=50, randomSeed=0xC0FFEE,
                                  pruneRmsThresh=0.5, useSmallRingTorsions=True)
AllChem.MMFFOptimizeMoleculeConfs(mh, maxIters=500)
```

- Add explicit hydrogens before embedding and keep them for any 3D use.
- The number of conformers needed grows with rotatable bonds: tens for rigid molecules, hundreds for flexible ones.
- Set `randomSeed` for reproducibility; embedding is stochastic.
- MMFF or UFF minimization is a crude gas-phase model: it gives reasonable geometries, not conformer populations or bioactive conformations.

## Drawing

```python
from rdkit.Chem.Draw import rdMolDraw2D
AllChem.Compute2DCoords(mol)
d = rdMolDraw2D.MolDraw2DSVG(350, 300)
rdMolDraw2D.PrepareAndDrawMolecule(d, mol, highlightAtoms=[a for match in hits for a in match])
d.FinishDrawing(); svg = d.GetDrawingText()
```

Use a common template (`AllChem.GenerateDepictionMatching2DStructure`) so a series is drawn in the same orientation.

## Parallel work

```python
import datamol as dm
results = dm.parallelized(process_one, mols, n_jobs=-1, progress=True)
```

RDKit molecules do not always pickle with all properties; pass SMILES to workers and rebuild, or use `dm.parallelized` which handles the common cases.

## Checks (done when)

- [ ] Parse failures counted and reported; identifiers preserved through the pipeline.
- [ ] Standardization choices (salts, charge, tautomers, stereo) recorded and applied uniformly.
- [ ] Duplicates resolved on standardized InChIKey, with conflicts explained.
- [ ] Fingerprint type, radius and size stated with every similarity number; thresholds calibrated, not assumed.
- [ ] SMARTS patterns tested on positive and negative examples.
- [ ] RDKit version recorded wherever descriptors or fingerprints are compared across runs.
