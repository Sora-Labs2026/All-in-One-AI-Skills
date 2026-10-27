# Bayesian modeling with PyMC and ArviZ

Read this when you need full uncertainty about parameters and predictions, hierarchical (multilevel) models that pool information across groups, small data with real prior knowledge, or a probabilistic model that does not fit a standard regression. Frequentist inference is in `statistical-inference.md` and `statsmodels-regression.md`.

## When Bayesian modeling pays off

- **Hierarchical structure:** many groups with few observations each (stores, schools, clinics, products). Partial pooling gives better estimates for small groups than either one global model or one model per group.
- **Uncertainty that feeds decisions:** posterior predictive distributions for inventory, pricing or risk, where intervals drive actions.
- **Prior information:** measured physical limits, previous studies, expert ranges.
- **Custom generative models:** mixtures, change points, measurement error, missing data modeled jointly.

For a large, simple prediction problem, a gradient-boosted model or a regularized GLM is cheaper and usually as accurate.

## Setup and versions

```bash
python -m pip install pymc arviz          # PyMC 5.x builds on PyTensor
python -c "import pymc, arviz; print(pymc.__version__, arviz.__version__)"
python -m pip install nutpie              # optional: faster NUTS sampler; numpyro or blackjax are alternatives
```

- PyMC 4 and later replaced Theano with Aesara and then PyTensor; code written for PyMC3 (`import pymc3`, `theano.tensor`) needs porting.
- `pm.MutableData` and `pm.ConstantData` were folded into `pm.Data` in PyMC 5.x.
- ArviZ is being reorganized into smaller packages in its 1.x line; check function locations against the installed version.
- Bambi provides a formula interface (`bmb.Model("y ~ x + (1|group)", df)`) on top of PyMC for regression-style models.

## The workflow

1. **Write the generative story:** how the data could have been produced, in plain words.
2. **Code the model with named dimensions.**
3. **Prior predictive check:** simulate data from the priors; it should look plausible (right scale, no impossible values).
4. **Fit with NUTS** and check diagnostics.
5. **Posterior predictive check:** simulated data from the fitted model should resemble the observed data in the features that matter.
6. **Compare models** with LOO cross-validation when there are alternatives.
7. **Report** posteriors as estimates with credible intervals and decisions in the domain's terms.

```python
import arviz as az
import numpy as np
import pymc as pm

coords = {"store": store_names, "obs": np.arange(len(y))}
with pm.Model(coords=coords) as model:
    x = pm.Data("x", x_std, dims="obs")                              # standardized predictor
    store = pm.Data("store", store_idx, dims="obs")
    mu_a = pm.Normal("mu_a", 0.0, 1.0)
    sigma_a = pm.HalfNormal("sigma_a", 1.0)
    z = pm.Normal("z", 0.0, 1.0, dims="store")                       # non-centered parameterization
    a = pm.Deterministic("a", mu_a + sigma_a * z, dims="store")
    b = pm.Normal("b", 0.0, 0.5)
    sigma = pm.HalfNormal("sigma", 1.0)
    pm.Normal("y", mu=a[store] + b * x, sigma=sigma, observed=y_std, dims="obs")

    prior = pm.sample_prior_predictive(random_seed=1)
    idata = pm.sample(draws=1000, tune=1000, chains=4, target_accept=0.9, random_seed=1,
                      idata_kwargs={"log_likelihood": True})
    idata.extend(pm.sample_posterior_predictive(idata, random_seed=1))
```

## Priors

- Standardize predictors and outcomes, then use weakly informative priors on that scale: `Normal(0, 1)` for coefficients, `HalfNormal(1)` or `Exponential(1)` for scales. They rule out absurd values without dominating the data.
- Avoid flat or extremely wide priors (`Normal(0, 1000)`); they are not "uninformative" on transformed scales and they slow sampling.
- Use domain knowledge where it exists, and write down its source.
- Check sensitivity: refit with wider and narrower priors; conclusions that flip are prior-driven and must be reported as such.

## Diagnostics: do not skip

```python
print(az.summary(idata, var_names=["mu_a", "sigma_a", "b", "sigma"]))   # r_hat, ess_bulk, ess_tail
print(int(idata.sample_stats["diverging"].sum()), "divergences")
az.plot_trace(idata, var_names=["mu_a", "sigma_a", "b"])
az.plot_ppc(idata, num_pp_samples=100)
```

| Diagnostic | Target | If not met |
|---|---|---|
| R-hat | At most 1.01 for every parameter | Run longer, reparameterize, check for multimodality |
| Effective sample size (bulk and tail) | At least about 400 per quantity you report | More draws; reparameterize correlated parameters |
| Divergent transitions | Zero, or a handful that disappear with higher `target_accept` | Non-centered parameterization; tighter priors on scales; raise `target_accept` to 0.95 or 0.99 |
| Tree depth saturation | Rare | Reparameterize; rescale variables |
| Posterior predictive check | Observed data looks typical among simulations | Change the likelihood (heavier tails, overdispersion, zero inflation) or add structure |

Divergences mean the sampler could not explore part of the posterior; results with unexplained divergences are not reliable, even if the summaries look reasonable.

## Hierarchical models and parameterization

- Centered (`a ~ Normal(mu_a, sigma_a)`) works with lots of data per group; non-centered (`a = mu_a + sigma_a * z`, `z ~ Normal(0, 1)`) works when groups have little data. Divergences in a hierarchical model usually mean you need the non-centered form.
- Index variables (`a[store]`) are cleaner and faster than one-hot design matrices.
- Report the group-level spread (`sigma_a`) as a finding: it says how much groups really differ.

## Model comparison

```python
cmp = az.compare({"pooled": idata_pooled, "hierarchical": idata_hier}, ic="loo")
print(cmp)                 # elpd_loo, standard errors, weights
az.loo(idata_hier, pointwise=True)   # check Pareto k diagnostics
```

- Pareto k above 0.7 for some points means the LOO estimate is unreliable for them; refit leaving them out (exact LOO) or use K-fold cross-validation.
- A difference in `elpd_loo` smaller than about two of its standard errors is weak evidence.
- Bayes factors are sensitive to priors and hard to compute well; prefer predictive comparison unless a Bayes factor is specifically required.

## Predictions for new data

```python
with model:
    pm.set_data({"x": x_new_std, "store": store_idx_new}, coords={"obs": np.arange(len(x_new_std))})
    pred = pm.sample_posterior_predictive(idata, var_names=["y"], predictions=True, random_seed=2)
```

Transform predictions back to the original scale, and report intervals from the posterior predictive (which include observation noise), not from the mean parameter alone.

## Reporting

- Posterior median or mean with a 94% or 95% highest-density or equal-tailed interval; state which.
- Probability statements answer business questions directly: "probability that variant B's conversion exceeds A's by at least 0.5 points is 0.87".
- Region of practical equivalence (ROPE): the share of the posterior inside a range of negligible effect, for "no meaningful difference" claims.
- Report priors, likelihood, sampler settings, diagnostics and posterior predictive checks. Archive the `InferenceData` (`idata.to_netcdf("fit.nc")`).

## Performance

- NUTS cost grows with data size and model complexity; models with thousands of parameters and hundreds of thousands of rows are feasible, slower with dense covariance structures.
- Alternative samplers (nutpie, numpyro, blackjax via `pm.sample(nuts_sampler=...)`) are often several times faster; JAX-based samplers can use GPUs.
- Variational inference (`pm.fit`, ADVI) is fast but underestimates uncertainty; use it for exploration or very large data, and validate against NUTS on a subset.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Ignoring divergences or R-hat above 1.01 | Reparameterize and refit; never report until clean |
| Unstandardized predictors with default priors | Standardize, or set priors on the real scale |
| No prior predictive check | Simulate from priors before fitting |
| Credible intervals from the mean parameter used as prediction intervals | Posterior predictive sampling |
| Comparing models by in-sample fit | LOO with Pareto k checks |
| PyMC3 code pasted into PyMC 5 | Port imports and APIs; check the installed version |

## Done when

- [ ] The generative story, priors and their sources are written down; the prior predictive check looks plausible.
- [ ] R-hat at most 1.01, adequate ESS, no unexplained divergences.
- [ ] Posterior predictive checks reproduce the features of the data that matter.
- [ ] Results are reported on the original scale with intervals, priors and diagnostics, and sensitivity to priors is known.
