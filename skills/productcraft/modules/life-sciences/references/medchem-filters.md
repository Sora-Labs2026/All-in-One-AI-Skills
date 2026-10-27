# Medicinal-chemistry filters and compound triage

Read this when you filter a compound library, flag problematic structures, apply drug-likeness or lead-likeness rules, or decide which hits deserve follow-up. Molecule handling is in `rdkit-and-datamol.md`; docking in `docking.md`.

## How to use filters at all

Filters are **prioritization aids with a context**, not verdicts. Every widely used rule has well-known exceptions: approved drugs break the Rule of Five routinely (natural products, macrocycles, kinase inhibitors, antibiotics), and alert sets flag substructures present in marketed drugs. Treat a failed filter as a reason to look, not as a reason to delete.

Practical rules:
1. **Never silently drop molecules.** Annotate every compound with which filters it failed and why, then decide.
2. **State the context.** Oral small molecules, fragments, CNS targets, covalent inhibitors, PROTACs and peptides have different expectations.
3. **Sanity-check the filter set** on known drugs or known actives for the target class. If the set rejects half of them, it is the wrong set for this project.
4. **Report counts per filter**, not only a final number.

## Libraries

```bash
python -m pip install rdkit datamol medchem
```

- RDKit ships a `FilterCatalog` with published alert sets (PAINS A/B/C, BRENK, NIH, ZINC and others) and property descriptors for rules.
- The `medchem` package (Apache-2.0) bundles rule implementations, structural alert collections, chemical-group queries and a demerit-style scoring interface behind one API, with parallel evaluation. Some of its filters shell out to external tools that must be installed separately; check what is available in the environment.
- Keep a project-owned list of custom SMARTS alongside, versioned with the project.

## Property rules

| Rule | Typical bounds | Intended for |
|---|---|---|
| Rule of Five | MW <= 500, cLogP <= 5, HBD <= 5, HBA <= 10 | Oral absorption of small molecules; a trend across datasets, not a per-compound test |
| Veber | Rotatable bonds <= 10, TPSA <= 140 | Oral bioavailability |
| Rule of Three | MW < 300, cLogP <= 3, HBD <= 3, HBA <= 3, rotatable bonds <= 3 | Fragment screening |
| Lead-like | MW roughly 200 to 350, cLogP roughly -1 to 3.5 | Starting points with room to grow |
| CNS-oriented ranges | Lower MW and TPSA, fewer HBD | Brain penetration; a guideline, not a predictor |
| Ligand efficiency | Potency per heavy atom (and lipophilic efficiency) | Comparing hits of different size; needs measured potency |

With RDKit alone:

```python
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors as rdmd

def rule_of_five(mol):
    violations = sum([
        Descriptors.MolWt(mol) > 500,
        Crippen.MolLogP(mol) > 5,
        rdmd.CalcNumHBD(mol) > 5,
        rdmd.CalcNumHBA(mol) > 10,
    ])
    return violations      # the original formulation allows one violation
```

Compute properties on the standardized parent structure, consistently (`rdkit-and-datamol.md`).

## Structural alerts

```python
from rdkit import Chem
from rdkit.Chem import FilterCatalog

params = FilterCatalog.FilterCatalogParams()
params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.BRENK)
catalog = FilterCatalog.FilterCatalog(params)

entry = catalog.GetFirstMatch(mol)                     # None when nothing matches
names = [e.GetDescription() for e in catalog.GetMatches(mol)]
```

What the main families mean:
- **PAINS:** substructures enriched among frequent hitters in a particular set of assay panels. They flag a risk of assay interference (aggregation, redox activity, covalent reaction, fluorescence), not inactivity. Several PAINS classes appear in approved drugs. A PAINS flag means "confirm with orthogonal assays", not "discard".
- **Reactive and unstable groups** (acyl halides, Michael acceptors, epoxides, aldehydes): a liability for a reversible-binder program, the point of the molecule for a covalent program.
- **Promiscuity and toxicophore lists** (for example in-house medicinal-chemistry demerit systems): useful aggregate judgment, best used as a score with reasons rather than a hard cut.
- **Aggregation:** many false positives come from colloidal aggregation, which structure alone predicts poorly. Detergent-sensitivity controls in the assay are the real test.

## A triage pipeline

```python
import datamol as dm

records = []
for smi in library:
    mol = dm.to_mol(smi)
    if mol is None:
        records.append({"smiles": smi, "status": "unparsable"}); continue
    parent = dm.keep_largest_fragment(dm.standardize_mol(mol))
    records.append({
        "smiles": smi,
        "inchikey": dm.to_inchikey(parent),
        "mw": Descriptors.MolWt(parent),
        "clogp": Crippen.MolLogP(parent),
        "ro5_violations": rule_of_five(parent),
        "alerts": ";".join(e.GetDescription() for e in catalog.GetMatches(parent)),
    })
```

Then decide in a documented order: unparsable, out of property range, alerts for this project, duplicates, and finally diversity selection. Report how many compounds each step removed, and keep the annotated table so decisions can be revisited.

## Elements, size and practicality

- Reject or flag compounds with elements outside the project's scope (metals, unusual halogens, isotopes) and those far outside the property ranges.
- Check availability and cost if compounds will be purchased, and synthetic accessibility (for example an SA-score style estimate) if they will be made. Both are estimates; a chemist's judgment decides.

## What filters cannot tell you

- Potency, selectivity and cellular activity.
- Metabolic stability, toxicity or safety: these need measured or modeled ADMET endpoints, and models need honest evaluation (`molecular-ml.md`).
- Whether a hit is real: that needs dose-response, orthogonal assays and, where possible, biophysical confirmation.

## Checks (done when)

- [ ] Every compound carries its filter annotations; nothing was removed without a record.
- [ ] The filter set and thresholds are stated with their versions, and justified for the modality and target class.
- [ ] A control set of known drugs or actives was run through the same filters, with the pass rate reported.
- [ ] Counts removed per step are reported, and the annotated table is kept.
- [ ] Alerts are described as interference or liability risks, never as proof of inactivity or toxicity.
