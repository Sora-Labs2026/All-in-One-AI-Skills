# Constraint-based metabolic modeling with COBRApy

Read this when you work with genome-scale metabolic models: flux balance analysis, flux variability, gene and reaction knockouts, media design, production envelopes or flux sampling. Dynamic kinetic simulation (ODEs) belongs to `../../scientific-computing/GUIDE.md`.

## What the method assumes

Flux balance analysis solves a linear program: find fluxes that satisfy mass balance at steady state and the bounds on each reaction, while maximizing an objective (usually a biomass reaction). Therefore:
- It predicts **flux distributions at steady state**, not concentrations, not dynamics, not regulation.
- The optimum is usually **not unique**: many flux distributions give the same objective value. A single `optimize()` result is one point in a space; use flux variability or sampling before interpreting individual fluxes.
- Predictions depend heavily on the **biomass reaction** and the **medium**, both of which are modeling choices.
- Gene essentiality predictions are often qualitatively useful; quantitative yields are only as good as the model's curation.

## Setup

```bash
python -m pip install cobra            # bundled GLPK solver
python -c "import cobra; print(cobra.__version__)"
```

COBRApy is GPL-2.0-licensed: that matters when it is distributed inside a product. For larger models or many optimizations, install a faster solver (for example HiGHS, or an academic license for a commercial solver) and set `model.solver`.

## Load and inspect

```python
import cobra
from cobra.io import read_sbml_model

model = read_sbml_model("iML1515.xml")           # SBML with FBC is the portable format
print(len(model.reactions), len(model.metabolites), len(model.genes))
print(model.objective.expression)
print(model.medium)                               # exchange reactions and their uptake bounds
```

- Check where the model came from and its version (model repositories publish curated models with identifiers); record it.
- Validate before trusting: mass and charge balance of reactions, blocked reactions, reactions able to carry flux with no inputs (energy-generating cycles). The MEMOTE test suite reports these systematically; run it on unfamiliar or hand-edited models.
- Identifier namespaces differ between model sources (BiGG, MetaNetX, KEGG, ModelSEED). Map deliberately when combining models or mapping omics data.

## Simulate

```python
solution = model.optimize()
print(solution.status, solution.objective_value)          # always check the status
```

- `status` must be `optimal`. `infeasible` means the constraints contradict each other (often a medium with no carbon source or a wrongly fixed bound); `unbounded` means a missing constraint lets flux grow without limit.
- `model.slim_optimize()` returns only the objective value and is much faster in loops.
- Parsimonious FBA (`cobra.flux_analysis.pfba`) picks the solution with the smallest total flux among the optima, which is more interpretable than an arbitrary optimum.

```python
with model:                                   # context manager: all changes revert on exit
    model.reactions.EX_o2_e.lower_bound = 0   # anaerobic
    anaerobic_growth = model.slim_optimize()
```

Use the context manager for every temporary change; silently mutated models are the main source of irreproducible results here.

## Media

```python
medium = model.medium                          # a dict of exchange reaction IDs to uptake limits
medium["EX_glc__D_e"] = 10.0                   # mmol / gDW / h, by convention
medium["EX_o2_e"] = 20.0
model.medium = medium                          # must be assigned back
```

- Exchange reaction sign conventions matter: in most models, uptake is a negative flux and the medium dict holds positive uptake limits. Check one known reaction before changing many.
- Units are millimoles per gram dry weight per hour unless the model says otherwise; a nonsensical uptake rate produces nonsensical growth.
- `cobra.medium.minimal_medium` finds minimal media; with `minimize_components=True` it solves a mixed-integer program, which is far slower.

## Variability, knockouts, sampling

```python
from cobra.flux_analysis import flux_variability_analysis, single_gene_deletion

fva = flux_variability_analysis(model, fraction_of_optimum=0.9, loopless=True)
ko = single_gene_deletion(model)                  # growth after each single-gene knockout
```

- FVA gives the range each flux can take while the objective stays within a fraction of the optimum. Report ranges, not point fluxes.
- `loopless=True` removes thermodynamically infeasible internal cycles; it is slower and usually worth it.
- Gene knockouts use the gene-protein-reaction rules; check that your genes exist in the model and that the rules reflect isozymes correctly.
- Double deletions scale with the square of the gene count; parallelize (`processes=`) and expect long runs.

```python
from cobra.sampling import sample
samples = sample(model, n=5000, method="optgp", processes=4, seed=0)
```

- Sampling explores the flux space when the optimum is degenerate. Check convergence and mixing (the sampler's validate method flags invalid samples); report the number of samples, the method and the seed.

## Omics and strain design

- Methods that integrate expression data into bounds (for example GIMME, iMAT, E-Flux families) each make different assumptions and give different answers; state the method and its threshold choices, and treat the output as one hypothesis.
- Strain-design algorithms (OptKnock-style) need mixed-integer solvers and realistic constraints; their proposals are starting points for experiments, not engineering plans.
- Any prediction about a strain or a therapeutic target is a hypothesis. Growth predictions, essentiality and yields must be confirmed experimentally.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Model mutated for the rest of the session | Use `with model:` |
| Solution status never checked | Assert `optimal` before reading values |
| Single optimum interpreted as "the" flux state | pFBA, FVA or sampling |
| Medium dict edited without reassigning | `model.medium = medium` |
| Infeasible after edits | Bisect the changes; check exchange bounds and the objective |
| Slow mixed-integer runs with the default solver | Install a faster solver; reduce the problem |

## Checks (done when)

- [ ] Model source, version and any curation changes recorded; validation (balances, blocked reactions, energy cycles) run on unfamiliar models.
- [ ] Solver, version and solution status reported for every result.
- [ ] Medium and objective stated explicitly with units.
- [ ] Degeneracy addressed with pFBA, FVA or sampling, with seeds recorded.
- [ ] Predictions reported as hypotheses, with a known growth or essentiality result used as a control.
