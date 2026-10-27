# Multi-objective optimization with pymoo

Read this when a design or calibration has two or more conflicting objectives (cost and performance, mass and stiffness, accuracy and runtime), when a Pareto front is the deliverable, or when comparing evolutionary algorithms. Single-objective and calibration problems are in `parameter-studies-and-campaigns.md` and `linear-and-nonlinear-solvers.md`.

## When pymoo fits

- pymoo (Apache-2.0, 0.6.x at the time of writing) provides genetic and evolutionary multi-objective algorithms, constraint handling, performance indicators, visualization and decision-making helpers behind one `minimize` interface. Version 0.6 reorganized imports; examples written for 0.5 do not run unchanged. Check the installed version.
- Evolutionary algorithms need thousands of evaluations (population 100 for 200 generations is 20,000). For expensive simulations, consider multi-objective Bayesian optimization (for example BoTorch with expected hypervolume improvement) or a validated surrogate first.
- With a single objective, SciPy's optimizers are often simpler and faster.

## Defining a problem

- **Everything is minimized.** Negate objectives you want to maximize, and negate them back when reporting.
- **Constraints:** inequality constraints are `G <= 0` and equality constraints `H = 0` (handled with a tolerance). Rewrite `g(x) >= b` as `b - g(x) <= 0`. Scale constraints so violations are comparable in size.
- `ElementwiseProblem` evaluates one design at a time (easy for wrapping simulations); `Problem` evaluates a whole population as arrays (fast for vectorized models). Parallel evaluation: pass an `elementwise_runner` such as `StarmapParallelization` with a process pool, or dispatch through the campaign machinery.
- Mixed variables (integers, choices, booleans) use `pymoo.core.variable` types with the mixed-variable genetic algorithm.
- Use variables of similar scale (for example log-transform a parameter spanning decades).

```python
import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.termination import get_termination

class Cantilever(ElementwiseProblem):
    """Rectangular steel cantilever: minimize mass and tip deflection under a stress limit (SI units)."""
    LENGTH, LOAD, MODULUS, DENSITY, STRESS_MAX = 2.0, 1_000.0, 200e9, 7_850.0, 150e6

    def __init__(self):
        super().__init__(n_var=2, n_obj=2, n_ieq_constr=1,
                         xl=np.array([0.01, 0.01]), xu=np.array([0.10, 0.30]))   # width b, height h in m

    def _evaluate(self, x, out, *args, **kwargs):
        b, h = x
        inertia = b * h**3 / 12.0
        mass = self.DENSITY * b * h * self.LENGTH                                   # kg
        deflection = self.LOAD * self.LENGTH**3 / (3.0 * self.MODULUS * inertia)  # m
        stress = self.LOAD * self.LENGTH * (h / 2.0) / inertia                     # Pa, at the root
        out["F"] = [mass, deflection]
        out["G"] = [(stress - self.STRESS_MAX) / self.STRESS_MAX]                  # scaled, feasible <= 0

result = minimize(Cantilever(), NSGA2(pop_size=100), get_termination("n_gen", 200), seed=1, verbose=False)
if result.F is None:
    raise RuntimeError("no feasible design found: check the constraints and bounds")
```

`result.X` holds the non-dominated designs, `result.F` their objectives, `result.G` and `result.CV` the constraints and violations. `result.F` is `None` when no feasible design was found.

## Choosing an algorithm

| Objectives | Algorithms | Notes |
|---|---|---|
| 2 or 3 | NSGA-II (robust default), SMS-EMOA (hypervolume-driven, better spread, costlier per generation), MOEA/D (decomposition) | Start with NSGA-II and a population of about 100 |
| 4 or more ("many-objective") | NSGA-III, MOEA/D, AGE-MOEA | NSGA-III needs reference directions: `get_reference_directions("das-dennis", n_obj, n_partitions=p)` grows combinatorially with `n_obj`; the `"energy"` method gives an arbitrary count |
| With a preferred region | R-NSGA-II, reference-point variants | Focuses evaluations near the decision maker's aspiration point |

- Defaults for real variables (simulated binary crossover and polynomial mutation) are sensible; tune their distribution indices only with evidence.
- Termination: a fixed number of generations or evaluations makes comparisons fair; the default tolerance-based termination stops when the front stops improving.
- Always pass `seed` and record it.

## Measuring quality

```python
import numpy as np
from pymoo.indicators.hv import HV

F = result.F
ideal, nadir = F.min(axis=0), F.max(axis=0)
F_normalized = (F - ideal) / (nadir - ideal)
hypervolume = HV(ref_point=np.array([1.1, 1.1]))(F_normalized)
```

- **Hypervolume** needs a reference point slightly worse than the nadir in normalized space. When comparing algorithms, normalize all fronts with the same ideal and nadir (taken over all runs), or the numbers are not comparable.
- **IGD and IGD+** need a known true front, so they suit benchmark problems, not real designs.
- **Compare algorithms honestly:** the same evaluation budget, many independent seeds (for example 20 to 31), median and interquartile range of the indicator, and a nonparametric test (Wilcoxon rank-sum) for differences.
- Track the indicator against evaluations with a callback; `save_history=True` stores every generation and costs memory.
- Visualize 2 or 3 objectives with scatter plots, more with parallel coordinates or petal diagrams (`pymoo.visualization`).

## Decision making

- The Pareto set is the result. Choosing one design needs the decision maker's preferences; present the trade-off and let them choose, or apply an explicit, reported rule.
- Helpers: achievement scalarization with weights (`pymoo.decomposition.asf.ASF`), pseudo-weights (`pymoo.mcdm.pseudo_weights.PseudoWeights`), knee-point detection. Normalize objectives first.
- Re-evaluate the chosen designs with perturbed inputs: designs on the constraint boundary are sensitive to model error.

## Expensive simulations

- Cache evaluations (keyed by rounded decision variables) and log every evaluation, including failures, to the campaign table (`parameter-studies-and-campaigns.md`).
- Parallelize evaluation through a process pool or scheduler job arrays; seed stochastic simulations per evaluation and average replicates when noise matters.
- Confirm any front obtained on a surrogate with real simulations of selected designs.

## Checks (done when)

- [ ] Objectives in minimization form with units; constraints written as `G <= 0` and scaled.
- [ ] Algorithm matches the number of objectives; seed and termination recorded.
- [ ] Feasibility checked (`result.F` not `None`, violations zero for reported designs).
- [ ] Quality reported with a correctly normalized hypervolume; algorithm comparisons use equal budgets, many seeds and a statistical test.
- [ ] The chosen design follows a stated preference rule or the decision maker's explicit choice, and passed a robustness check.

## Anti-patterns

- Maximizing by accident (forgetting to negate).
- Hypervolumes computed with different normalizations or reference points, then compared.
- One seed per algorithm, then a ranking.
- Picking the "best" compromise silently.
