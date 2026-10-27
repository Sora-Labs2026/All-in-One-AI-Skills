# Statistical inference: test selection, assumptions, multiple comparisons, effect sizes

Read this when a question is "is this difference real?", "does X relate to Y?", "how many samples do we need?", or when results will be reported with p-values or confidence intervals: A/B tests, experiments, surveys, analyses for papers or decisions. Regression modeling is in `statsmodels-regression.md`; Bayesian analysis in `bayesian-modeling.md`; writing up results for publication in `../../research-writing/GUIDE.md`.

## Before touching data

1. **State the question as a comparison or an estimate.** "Conversion rate of B minus A among new visitors in March" beats "does B work?".
2. **Fix the primary outcome, the analysis and the sample size in advance.** Write them down (a pre-registration or an analysis plan in the repository). Everything else is exploratory and labeled as such.
3. **Identify the unit of analysis.** If users are randomized but you analyze page views, observations are not independent; analyze at the user level or use clustered methods.
4. **Decide the smallest effect worth detecting** and run a power analysis for it.
5. **Decide how missing data, outliers and exclusions are handled** before seeing outcomes.

Changing the outcome, the test, the exclusions or the stopping point after looking at results inflates false positives, even when each choice seems reasonable.

## Choose the test

| Question | Data | Default | Alternatives |
|---|---|---|---|
| Two independent groups differ in mean | Continuous | Welch's t-test (`scipy.stats.ttest_ind(a, b, equal_var=False)`) | Mann-Whitney U for ordinal data or heavy outliers (tests distribution shift, not means); bootstrap CI of the mean difference |
| Same units measured twice | Continuous, paired | Paired t-test (`ttest_rel`) | Wilcoxon signed-rank |
| Three or more groups | Continuous | Welch's ANOVA (pingouin `welch_anova`) or one-way ANOVA if variances are similar | Kruskal-Wallis; follow with corrected pairwise comparisons (Games-Howell, Tukey HSD) |
| Repeated measures, several conditions | Continuous | Mixed-effects model (`statsmodels-regression.md`) | Repeated-measures ANOVA with sphericity correction |
| Two proportions | Binary | Two-proportion z-test or chi-square without correction for large samples; difference with a CI | Fisher's exact test when expected counts are small (below about 5) |
| Paired binary outcomes | Binary, paired | McNemar's test | |
| Association between two categorical variables | Counts | Chi-square test of independence, with Cramer's V | Fisher's exact for 2x2 with small counts |
| Linear association | Two continuous | Pearson correlation with CI | Spearman for monotone or ranked data |
| Effect of several predictors | Any outcome | Regression: OLS, logistic, Poisson or negative binomial, mixed models | |
| Counts or rates | Counts with exposure | Poisson or negative binomial regression with an offset | |
| Time to event | Durations with censoring | Log-rank test, Cox model (`survival-analysis.md`) | |
| Agreement between raters | Ratings | Cohen's kappa (2 raters), Fleiss' kappa, ICC for continuous ratings | Krippendorff's alpha |

When the test choice is unclear, prefer estimating the effect with a confidence interval (from a regression or a bootstrap) over picking a named test.

## Check assumptions the useful way

| Assumption | Check | If violated |
|---|---|---|
| Independence | Design: how were units sampled or randomized? Repeated users, clusters, time order | Aggregate to the independent unit, cluster-robust standard errors, mixed models |
| Normality of residuals or of the sampling distribution | Q-Q plot of residuals; sample size (the central limit theorem covers means for moderate n unless data is extremely skewed) | Transform (log), use a robust or rank-based method, or bootstrap |
| Equal variances | Compare group SDs; Levene's test as a hint | Use Welch's versions by default |
| Linearity (regression) | Residuals versus fitted, partial residual plots | Splines, transformations, or another model |
| No influential outliers | Cook's distance, leverage | Investigate the points; report with and without; robust regression |

Formal normality tests (Shapiro-Wilk) reject trivial departures in large samples and miss real ones in small samples. Use plots, and choose methods that are robust by default (Welch, robust standard errors, bootstrap) rather than gatekeeping with tests.

## Effect sizes and intervals: always

A p-value says how surprising the data would be if there were no effect; it says nothing about size or importance. Report:
- The **estimate in natural units** with a 95% CI (difference in means, difference in proportions, ratio, regression coefficient).
- A **standardized effect** where comparisons across studies matter: Cohen's d or Hedges' g (small samples) for mean differences, odds ratio or risk ratio for binary outcomes, r or R² for associations, eta-squared or omega-squared for ANOVA, Cramer's V for contingency tables.
- **Exact p-values** (p = 0.031, not p < 0.05), and the test used.

```python
import numpy as np
from scipy import stats

def hedges_g(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return (a.mean() - b.mean()) / sp * (1 - 3 / (4 * (na + nb) - 9))

res = stats.ttest_ind(a, b, equal_var=False)
ci = res.confidence_interval(confidence_level=0.95)     # SciPy 1.11+; CI of mean(a) - mean(b)
print(f"diff={np.mean(a) - np.mean(b):.3f}, 95% CI [{ci.low:.3f}, {ci.high:.3f}], p={res.pvalue:.3g}, g={hedges_g(a, b):.2f}")
```

The labels "small, medium, large" for d of 0.2, 0.5 and 0.8 are generic conventions; judge size against the domain (a 0.5% conversion lift can be large for a business).

## Multiple comparisons

Every extra test (metrics, segments, time windows, variants, model specifications) raises the chance of a false positive. With 20 independent tests at alpha = 0.05, the chance of at least one false positive is about 64%.

- **Plan one primary outcome.** Secondary outcomes are reported with adjustment or labeled exploratory.
- **Family-wise error (any false positive is costly):** Holm, which is uniformly more powerful than Bonferroni.
- **False discovery rate (screening many hypotheses, such as features or genes):** Benjamini-Hochberg.
- Count all comparisons you looked at, including those not reported. Searching many segments and reporting the one that "worked" is the same as not correcting.
- Tools: `statsmodels.stats.multitest.multipletests(pvals, method="holm" | "fdr_bh")`, or `python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py adjust --p 0.01,0.04,0.03`.

## Power and sample size

```python
from statsmodels.stats.power import TTestIndPower, NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

n_per_group = TTestIndPower().solve_power(effect_size=0.3, alpha=0.05, power=0.8, alternative="two-sided")
h = proportion_effectsize(0.055, 0.050)                     # detect 5.0% -> 5.5%
n_props = NormalIndPower().solve_power(effect_size=h, alpha=0.05, power=0.8)
```

- Power analysis is for planning. "Observed power" computed after the fact from the observed effect adds nothing beyond the p-value; report the CI instead, and a sensitivity analysis (the smallest effect the study could have detected).
- An underpowered study that finds a "significant" effect usually overestimates it.
- Non-significant results are not evidence of no effect. For "no meaningful difference" claims, use an equivalence test (two one-sided tests, TOST) against a pre-set margin.

## Online experiments (A/B tests)

- Randomize at the unit you analyze (user, account, session) and keep assignment stable.
- **Sample ratio mismatch:** check that the observed split matches the planned split (chi-square test on assignment counts). A mismatch means a bug in assignment or logging; do not trust the results until it is explained.
- **Peeking:** checking significance repeatedly and stopping when p < 0.05 inflates false positives greatly. Fix the sample size, or use a sequential method designed for repeated looks (group sequential boundaries, always-valid inference).
- **Variance reduction:** adjusting for a pre-experiment covariate (CUPED-style regression adjustment) shrinks intervals without bias when the covariate is measured before assignment.
- **Guardrail metrics** (errors, latency, unsubscribes, refunds) are checked alongside the primary metric.
- Ratio metrics (revenue per session when sessions per user vary) need the delta method or bootstrap by user.
- Novelty and seasonality: run full weekly cycles; long-term effects may differ from the first weeks.

## Correlation, causation and observational data

- Observational associations are confounded by default. Causal claims need randomization, or a design that addresses confounding (matching or weighting on measured confounders, difference-in-differences, regression discontinuity, instrumental variables) with its assumptions stated.
- Draw the assumed causal graph before choosing adjustment variables; adjusting for a mediator or a collider introduces bias.
- Simpson's paradox: an aggregate trend can reverse within groups. Check key strata.

## Reporting checklist

State: the question and pre-specified plan (and any deviations), sample sizes per group after exclusions with reasons, descriptive statistics, the test or model with its assumptions and how they were checked, effect estimates with 95% CIs, exact p-values, the number of comparisons and the correction used, and which results are exploratory. Share code and, where allowed, data.

Never invent or adjust numbers to fit a narrative. If an analysis was not run, say so.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Student's t-test with unequal variances | Welch's t-test by default |
| Page views analyzed when users were randomized | Analyze per user or use cluster-robust methods |
| Many segments tested, the best one reported | Pre-register; adjust; label exploratory |
| Peeking and stopping at significance | Fixed horizon or sequential design |
| p > 0.05 reported as "no effect" | CI and, for equivalence claims, TOST |
| Only p-values reported | Effect size with CI |
| `scipy.stats.binom_test` in old code | Removed in SciPy 1.12; use `scipy.stats.binomtest` |

## Done when

- [ ] Outcome, analysis, unit and sample size were fixed before looking at results (or deviations are listed).
- [ ] The test matches the data and design; assumptions were checked with plots and robust defaults.
- [ ] Every result has an effect size with a CI and an exact p-value.
- [ ] Multiple comparisons are counted and adjusted.
- [ ] Causal language is used only with a design that supports it.
