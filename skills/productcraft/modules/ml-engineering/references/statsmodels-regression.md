# Regression and econometric modeling with statsmodels

Read this when the goal is to estimate and interpret relationships (coefficients, odds ratios, rate ratios, marginal effects) with valid standard errors, rather than only to predict: linear models, GLMs, logistic and count models, mixed effects, and classical time-series models. Test selection and reporting rules are in `statistical-inference.md`.

## statsmodels or scikit-learn?

- **statsmodels:** inference. Standard errors, confidence intervals, hypothesis tests, diagnostics, robust and clustered covariance, formula interface, marginal effects.
- **scikit-learn:** prediction. Pipelines, cross-validation, regularization paths, many model families. Its `LogisticRegression` is penalized by default, so its coefficients are shrunk and come without standard errors.

Use both when needed: interpret with statsmodels, validate predictive performance with scikit-learn-style cross-validation.

```bash
python -m pip install statsmodels pandas patsy   # check: python -c "import statsmodels; print(statsmodels.__version__)"
```

## The formula interface

```python
import numpy as np
import statsmodels.formula.api as smf

m = smf.ols("np.log(revenue) ~ price + C(region, Treatment('north')) + tenure * plan", data=df).fit(cov_type="HC3")
print(m.summary())
m.params, m.conf_int(), m.pvalues
```

- The formula API adds the intercept; the array API (`sm.OLS(y, X)`) does not, so call `sm.add_constant(X)` there. Forgetting it is the most common statsmodels bug.
- `C(var)` for categorical variables, with an explicit reference level via `Treatment(...)`.
- `a * b` expands to `a + b + a:b`. Center continuous variables in interactions so main effects are interpretable at a meaningful value.
- Transformations inside the formula (`np.log(x)`, `I(x**2)`) are re-applied at prediction time with `m.predict(new_df)`.
- Rows with missing values in any formula variable are dropped silently; check `m.nobs` against your row count.

## Standard errors are a modeling choice

| Situation | Covariance |
|---|---|
| Heteroskedastic residuals (most real data) | `fit(cov_type="HC3")` (or HC1 for large samples) |
| Observations clustered (users, schools, stores) | `fit(cov_type="cluster", cov_kwds={"groups": df["store_id"]})` |
| Time series with autocorrelated errors | `fit(cov_type="HAC", cov_kwds={"maxlags": L})` |
| Few clusters (under about 30 to 50) | Cluster-robust SEs are unreliable; use a wild cluster bootstrap or mixed models and say so |

Default OLS standard errors assume independent, constant-variance errors; they are often too small.

## Generalized linear models

| Outcome | Family and link | Coefficient meaning (exponentiated) |
|---|---|---|
| Binary | `smf.logit` or `smf.glm(..., family=sm.families.Binomial())` | Odds ratio |
| Counts | `smf.poisson` or GLM Poisson, log link | Rate ratio |
| Overdispersed counts | `smf.negativebinomial` or GLM NegativeBinomial | Rate ratio |
| Rates with exposure (events per time or per user) | Poisson or NB with `offset=np.log(exposure)` | Rate ratio |
| Positive skewed continuous (costs, durations) | GLM Gamma, log link | Multiplicative effect on the mean |
| Many zeros plus continuous positive values (insurance, spend) | Tweedie (power between 1 and 2) | Multiplicative effect on the mean |
| Proportions from counts | Binomial with successes and failures | Odds ratio |
| Ordered categories | `statsmodels.miscmodels.ordinal_model.OrderedModel` | Cumulative odds ratio |
| Unordered categories | `smf.mnlogit` | Relative risk ratio versus the reference |

```python
import statsmodels.api as sm
pois = smf.glm("tickets ~ plan + np.log(seats)", data=df, family=sm.families.Poisson(),
               offset=np.log(df["months_active"])).fit()
print(pois.pearson_chi2 / pois.df_resid)        # well above 1 means overdispersion -> negative binomial
np.exp(pois.params), np.exp(pois.conf_int())
```

- Odds ratios are not risk ratios; when the outcome is common (over about 10%), they differ a lot. For communication, report predicted probabilities or average marginal effects: `logit_res.get_margeff(at="overall").summary()`.
- Perfect separation in logistic regression (a predictor perfectly predicts the outcome) produces huge coefficients or errors; it is often a leakage signal. Investigate before applying penalization (Firth-type or L2).
- Pseudo R² values are not comparable with OLS R²; compare models with likelihood-ratio tests (nested) or AIC/BIC.

## Mixed-effects models

Use when observations are grouped (repeated measures per user, students in schools) and you want population-level effects plus group-level variation.

```python
mixed = smf.mixedlm("score ~ week * treatment", data=df, groups=df["user_id"], re_formula="~week").fit(reml=True)
print(mixed.summary())
```

- `groups` is the clustering unit; `re_formula="~week"` adds random slopes.
- Convergence warnings are common: rescale predictors, simplify the random-effects structure, try another optimizer (`method=["lbfgs"]`).
- statsmodels `MixedLM` covers linear mixed models; for generalized mixed models (binary or count outcomes with random effects), use the Bayesian route (`bayesian-modeling.md`, Bambi) or R's lme4 and glmmTMB, and say which.
- Compare fixed-effect structures with ML (`reml=False`), and report variance components.

## Diagnostics

```python
from statsmodels.stats.diagnostic import het_breuschpagan, acorr_ljungbox
from statsmodels.stats.outliers_influence import variance_inflation_factor

infl = m.get_influence(); cooks = infl.cooks_distance[0]            # influential points
bp = het_breuschpagan(m.resid, m.model.exog)                         # heteroskedasticity hint
vif = [variance_inflation_factor(m.model.exog, i) for i in range(1, m.model.exog.shape[1])]
```

- Plot residuals versus fitted and a Q-Q plot first; tests second.
- High VIF (above about 5 to 10) inflates standard errors and makes coefficients unstable; it does not bias predictions. Combine or drop redundant predictors if interpretation matters.
- Influential points: refit without them and report both if conclusions change.
- Specification: test non-linearity with splines (`bs(x, df=4)` in formulas) rather than assuming linear effects.

## Time-series models in statsmodels

- `SARIMAX`, `ExponentialSmoothing` and `ETSModel`, `UnobservedComponents`, `VAR` and `VECM`, `AutoReg`, `MarkovRegression`. Forecasting workflow, backtesting and metrics are in `forecasting.md`.
- Spurious regression: regressing one trending series on another produces high R² and tiny p-values with no relationship. Difference the series, include trends, or test for cointegration.
- Granger causality (`grangercausalitytests`) tests whether past values of X improve predictions of Y; it is not causation.
- Use HAC standard errors or model the error autocorrelation explicitly when residuals are autocorrelated (Ljung-Box test, ACF plot).

## Prediction with uncertainty

```python
pred = m.get_prediction(new_df).summary_frame(alpha=0.05)
# mean_ci_*: uncertainty of the average outcome; obs_ci_*: interval for a new individual observation
```

Prediction intervals for individual outcomes are much wider than confidence intervals for the mean. Say which one you report.

## Interpreting coefficients honestly

- A coefficient is the expected difference in the outcome per unit difference in the predictor, holding the other predictors fixed, under the model. It is causal only under a design that supports causation.
- Log outcome: `100 * (exp(b) - 1)` percent change per unit. Log predictor: b / 100 change in outcome per 1% change in the predictor.
- Do not compare raw coefficient sizes across predictors with different units; standardize or compare effects over realistic ranges.
- Stepwise selection by p-values gives biased coefficients and invalid p-values. Choose variables from the question and domain knowledge, or use penalization for prediction.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `sm.OLS(y, X)` without a constant | `sm.add_constant(X)` or the formula API |
| Default standard errors on clustered or heteroskedastic data | HC3, cluster-robust or HAC covariance |
| Poisson on overdispersed counts | Check dispersion; negative binomial |
| Odds ratios reported as "times more likely" | Report risk differences or marginal effects for common outcomes |
| Silent dropping of rows with missing values | Compare `nobs` with the data; handle missingness explicitly |
| Trending series regressed on each other | Differencing, trends, cointegration tests |
| Coefficients read as causal effects | State the design; use causal language only when justified |

## Done when

- [ ] The model family matches the outcome type, with the intercept, reference levels and offsets set deliberately.
- [ ] The covariance type matches the data's dependence structure.
- [ ] Residual and influence diagnostics were reviewed, and any refit without influential points is reported.
- [ ] Effects are reported in interpretable units (ratios, marginal effects, predicted values) with CIs.
- [ ] Row counts after missing-value handling are stated.
