# Molecular machine learning: featurization, models and benchmarks

Read this when you predict properties of molecules (solubility, permeability, toxicity, activity, ADMET), featurize structures for a model, train a graph neural network on molecules or proteins, or benchmark against standard therapeutic datasets. Molecule handling is in `rdkit-and-datamol.md`; filters in `medchem-filters.md`; general evaluation and training in `../../ml-engineering/GUIDE.md`.

## The order that avoids wasted work

1. **Define the endpoint and its unit.** "Soluble" is not an endpoint; logS in log mol/L measured by a stated assay is. Mixing assays or units is the most common silent error in public chemistry datasets.
2. **Clean the data** (`rdkit-and-datamol.md`): standardize, deduplicate on InChIKey, and decide how to resolve duplicate measurements (median for continuous values; drop when replicates disagree beyond the assay's error).
3. **Split by scaffold or cluster**, never at random.
4. **Baseline:** Morgan fingerprints plus gradient boosting, and a descriptor-plus-linear model. Report them.
5. **Only then** try graph networks or pretrained embeddings, and show they beat the baseline on the same split with spread over seeds.

Published comparisons repeatedly find fingerprint-plus-tree baselines competitive with graph neural networks on small and medium molecular datasets. The baseline is not a formality.

## Splits that do not lie

- **Scaffold split:** group by Bemis-Murcko scaffold, assign whole groups to one side. The standard for prospective-like evaluation.
- **Cluster split:** cluster by fingerprint similarity (Butina or sphere exclusion) and split clusters.
- **Time split:** when a date is available (patent, publication, synthesis date), train on earlier compounds and test on later ones; this is closest to real use.
- **Random split:** only to show how much it inflates scores.
- For target-based data (drug-target pairs), also split by target to test generalization to unseen proteins, and report both settings.

```python
import numpy as np
from collections import defaultdict
from rdkit.Chem.Scaffolds import MurckoScaffold

def scaffold_split(smiles, frac_train=0.8, seed=0):
    groups = defaultdict(list)
    for i, smi in enumerate(smiles):
        groups[MurckoScaffold.MurckoScaffoldSmiles(smiles=smi, includeChirality=False)].append(i)
    buckets = sorted(groups.values(), key=len, reverse=True)      # large scaffolds to train first
    n_train, train, test = int(frac_train * len(smiles)), [], []
    for b in buckets:
        (train if len(train) + len(b) <= n_train else test).extend(b)
    return np.array(train), np.array(test)
```

## Featurization

| Representation | Good for | Notes |
|---|---|---|
| Morgan or count fingerprints | Trees, kernels, similarity | Strong baseline; state radius and size |
| Physicochemical descriptors | Linear and tree models, interpretation | Scale them; some fail on odd structures |
| Molecular graphs (atom and bond features) | Graph neural networks | Needs enough data; see `../../ml-engineering/references/graph-neural-networks.md` |
| Pretrained chemical language model embeddings | Transfer on small datasets | Gains over fingerprints are often small; test, do not assume |
| 3D descriptors and conformer-based features | Shape-dependent endpoints | Costly; conformer generation is a modeling choice |

The `molfeat` package (Apache-2.0) exposes many featurizers behind one interface, with scikit-learn-compatible transformers, caching and parallelism:

```python
from molfeat.calc import FPCalculator
from molfeat.trans import MoleculeTransformer

transformer = MoleculeTransformer(FPCalculator("ecfp", radius=2, fpSize=2048), n_jobs=-1)
X = transformer(smiles_list)          # failures come back as None or are dropped, depending on settings
```

Check how the transformer handles molecules it cannot featurize, and keep the index mapping so rows still line up with labels. Pretrained featurizers download weights; record the name, version and license.

## Toolkits

| Toolkit | Use it for | Watch out for |
|---|---|---|
| scikit-learn and gradient boosting | Baselines and most tabular endpoints | Nothing chemistry-specific; pair with fingerprints |
| DeepChem (MIT) | Many featurizers, dataset loaders, model wrappers, standard benchmark loaders | Large dependency surface; APIs vary across releases; its loaders download public datasets |
| PyTorch Geometric | Custom graph models with full control | See the graph reference in the ML module |
| TorchDrug (Apache-2.0) | Molecule, protein and knowledge-graph tasks with a task-and-model structure | Lightly maintained; pin versions and test against a known result before building on it |
| Chemprop | Directed message-passing baselines for property prediction | Well-tested, good default for graph models on this data |

Prefer a small, well-understood stack. A toolkit that bundles everything is convenient and also pins you to its versions of torch and RDKit; check compatibility before adopting it.

## Benchmarks and public datasets

The Therapeutics Data Commons (PyTDC, MIT-licensed code) packages many therapeutic datasets with standard splits and metrics: ADME and toxicity endpoints, drug-target interaction, drug-drug interaction, generation tasks and property oracles.

```python
from tdc.single_pred import ADME
data = ADME(name="Caco2_Wang")
split = data.get_split(method="scaffold", seed=42, frac=[0.7, 0.1, 0.2])
```

- Use the prescribed split and metric when reporting benchmark numbers, and say which seed or seeds; otherwise the numbers are not comparable.
- Record the package version and dataset version: datasets get corrected over time.
- Each underlying dataset has its own source license and citation. Check them before commercial use or redistribution, and cite the original source, not only the collection.
- Benchmark datasets are small and often noisy. A difference of a few hundredths in AUROC between methods, on one split and one seed, is not a result; report spread over seeds and compare paired.
- Property "oracles" used in generation benchmarks are models or simple scoring functions. Optimizing against them measures optimization, not real-world activity; do not report oracle scores as biological outcomes.

## Metrics that match the decision

- Regression: RMSE and MAE in the endpoint's units, plus Spearman correlation when ranking is what matters.
- Classification on imbalanced actives: precision-recall area and enrichment at the fraction you can actually test; plain accuracy and AUROC flatter the model.
- Report performance in chemical space where it will be used (held-out scaffolds, held-out targets), with confidence intervals from bootstrap or repeated splits.

## Applicability domain and calibration

- A model is only trustworthy for compounds similar to its training set. Report a distance measure (for example maximum Tanimoto similarity to training compounds) with every prediction, and show error against that distance on held-out data.
- Calibrate probabilities before using them as decision thresholds; check uncertainty estimates from ensembles against observed errors.
- Say plainly that predictions are hypotheses to be tested in assays, and never present a model score as a measured property or a safety conclusion.

## Checks (done when)

- [ ] Endpoint, assay, units and duplicate resolution documented.
- [ ] Scaffold, cluster or time split used, with random-split numbers only shown as a contrast.
- [ ] Fingerprint-plus-tree and descriptor baselines reported on the same split.
- [ ] Results reported with spread over seeds or repeated splits, and paired comparisons.
- [ ] Applicability domain reported with predictions; dataset, model and weight licenses recorded.
