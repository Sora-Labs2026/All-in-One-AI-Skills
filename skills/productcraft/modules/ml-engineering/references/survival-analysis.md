# Survival and time-to-event analysis

Read this when the outcome is the time until an event (churn, failure, default, relapse, conversion) and some subjects have not had the event yet. If those subjects are dropped or treated as "no event", the analysis is wrong; this reference is about doing it right.

Clinical and health data: this is engineering and analysis practice, not medical advice. Work on de-identified data, never fabricate patient records, and keep HIPAA or GDPR duties (minimum necessary data, access control, audit) in view. Clinical conclusions need review by qualified clinicians and statisticians.

## The data shape

Every subject needs: a start time (time zero), a follow-up time, and an event indicator (1 = event observed, 0 = censored: still event-free when observation ended). Define time zero the same way for everyone (signup date, diagnosis date, install date) and make sure every feature is measured at or before it.

```python
import numpy as np
from sksurv.util import Surv
y = Surv.from_arrays(event=df["event"].astype(bool), time=df["duration_days"])   # scikit-survival format
# lifelines and statsmodels take the duration and event columns directly
```

Common data errors:
- Durations of zero or negative: fix the date logic, do not clip silently.
- Event indicator inverted (1 = censored in some exports): check the event rate against domain expectation.
- **Immortal time bias:** classifying subjects by something that happens after time zero (for example "received treatment at any point") guarantees that group survived long enough to receive it. Use time-varying covariates or a landmark design.
- Censoring that depends on the outcome (people leave the study because they are getting worse) violates the independent-censoring assumption behind every method here. Flag it; it needs domain judgment.

## Pick the library

| Library | Use for | License |
|---|---|---|
| lifelines | Kaplan-Meier, Nelson-Aalen, Cox with diagnostics, parametric (Weibull, log-normal) and accelerated failure time models, Aalen-Johansen cumulative incidence | MIT |
| scikit-survival | scikit-learn compatible models (penalized Cox, random survival forests, gradient-boosted survival, survival SVMs) and proper survival metrics | GPL-3.0 |
| statsmodels `PHReg` | Cox regression inside a statsmodels workflow, stratification, robust standard errors | BSD |
| R `survival`, `cmprsk`, `tidycmprsk` | Fine-Gray competing-risks regression and the widest set of validated methods | GPL |

**License check:** scikit-survival is GPL-3.0. Using it in internal analysis is fine; shipping it inside distributed proprietary software creates copyleft obligations. Ask the owner before adding it to a product dependency list (see `../../legal-ready/GUIDE.md`).

## Workflow

1. **Describe:** Kaplan-Meier curves overall and by key groups, with confidence bands and numbers at risk. Report median survival only where the curve crosses 0.5.
2. **Compare groups:** log-rank test for a planned comparison (it is most sensitive when hazards are proportional).
3. **Model:** Cox proportional hazards for interpretable hazard ratios; penalized Cox or tree ensembles when prediction is the goal.
4. **Check assumptions:** proportional hazards, functional form of continuous covariates, influential observations.
5. **Evaluate prediction:** concordance, time-dependent AUC, integrated Brier score on held-out data.

```python
from lifelines import KaplanMeierFitter, CoxPHFitter

kmf = KaplanMeierFitter().fit(df["duration_days"], df["event"], label="all")
ax = kmf.plot_survival_function(at_risk_counts=True)

cph = CoxPHFitter(penalizer=0.01)
cph.fit(df[["duration_days", "event", "age", "plan_tier", "usage_z"]],
        duration_col="duration_days", event_col="event")
cph.print_summary()                        # hazard ratios exp(coef) with 95% CIs
cph.check_assumptions(df, p_value_threshold=0.01, show_plots=False)   # Schoenfeld-residual based
```

## Cox model essentials

- A hazard ratio of 1.3 means a 30% higher instantaneous event rate at any time, holding other covariates fixed, **if** hazards are proportional. It is not a 30% higher probability of the event.
- Proportional hazards violated for a covariate: stratify on it (`strata=`), add an interaction with time, or switch to a time-varying coefficient or an accelerated failure time model. Do not ignore the diagnostic.
- Continuous covariates: check linearity (splines or martingale residuals); log-transform skewed ones.
- Ties in event times: lifelines uses Efron's method; state it when matching another tool.
- With many covariates relative to events (a common rule of thumb is at least 10 to 20 events per covariate), use penalization (`CoxnetSurvivalAnalysis` in scikit-survival, `penalizer` in lifelines) and expect unstable individual coefficients.

## Machine-learning survival models

```python
from sksurv.ensemble import RandomSurvivalForest
from sksurv.metrics import concordance_index_ipcw, integrated_brier_score, cumulative_dynamic_auc

rsf = RandomSurvivalForest(n_estimators=500, min_samples_leaf=15, n_jobs=-1, random_state=0)
rsf.fit(X_train, y_train)
risk = rsf.predict(X_test)                                   # higher = earlier event
tau = np.percentile(y_train["time"], 80)                     # evaluate where follow-up is adequate
c_uno = concordance_index_ipcw(y_train, y_test, risk, tau=tau)[0]
times = np.percentile(y_test["time"], [25, 50, 75])
auc_t, mean_auc = cumulative_dynamic_auc(y_train, y_test, risk, times)
surv_fns = rsf.predict_survival_function(X_test)
probs = np.vstack([[fn(t) for t in times] for fn in surv_fns])
ibs = integrated_brier_score(y_train, y_test, probs, times)
```

- Random survival forests and gradient-boosted survival models capture non-linearity and interactions; compare them against penalized Cox on the same folds. They often do not win on small clinical datasets.
- Deep survival models (DeepSurv-style, discrete-time neural models via pycox) need large datasets; justify them against the simpler baselines.
- Discrete-time alternative: expand each subject into person-period rows and fit a classifier for the event in each interval. Simple, flexible, and works with any classifier; group the rows by subject when splitting.

## Metrics

| Metric | Measures | Notes |
|---|---|---|
| Harrell's C-index | Ranking: does the model give higher risk to subjects who fail earlier? | Optimistic under heavy censoring; easy to compute (`concordance_index_censored`) |
| Uno's C-index | Same, with inverse-probability-of-censoring weights | Preferred under heavy censoring; needs a truncation time `tau` within the follow-up of the training data |
| Time-dependent AUC | Discrimination at chosen horizons (30, 90, 365 days) | Report at horizons that match decisions |
| Brier score at t, integrated Brier score | Calibration plus discrimination of predicted survival probabilities | Compare with the Kaplan-Meier (no covariates) baseline |
| Calibration at horizon | Predicted versus observed event probability by risk decile | Needed whenever predicted probabilities drive decisions |

A model with a good C-index can still be badly calibrated. Report both when probabilities are used.

## Competing risks

When another event prevents the one of interest (death before relapse, churn by account closure before upgrade):
- Do **not** use 1 minus Kaplan-Meier treating competing events as censored; it overestimates the cumulative incidence.
- Estimate cumulative incidence with Aalen-Johansen (`lifelines.AalenJohansenFitter`; recent scikit-survival versions also provide a competing-risks cumulative incidence estimator; check the installed version).
- Cause-specific Cox models (competing events treated as censored) answer etiologic questions about the event rate; the Fine-Gray subdistribution model answers questions about cumulative incidence. Name which question you answer. Fine-Gray regression is best supported in R (`cmprsk`, `tidycmprsk`).

## Splitting and leakage

- Split by subject. Repeated episodes of one customer or patient go in the same fold.
- Features must be known at time zero. Anything measured later goes in a time-varying covariate model (`CoxTimeVaryingFitter`) or a landmark analysis, never as a baseline feature.
- Use stratified folds on the event indicator so each fold has events; with few events, prefer repeated cross-validation to one split.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Censored subjects dropped or labeled "no event" | Survival methods that use censored follow-up |
| Median survival reported when the curve never reaches 0.5 | Report "not reached" and the survival at fixed horizons |
| Proportional hazards never checked | `check_assumptions`, Schoenfeld residuals; stratify or model time-varying effects |
| Harrell's C under 60%+ censoring treated as precise | Uno's C with a stated `tau`, plus time-dependent AUC |
| Competing events censored | Cumulative incidence (Aalen-Johansen), and choose cause-specific or Fine-Gray deliberately |
| Post-baseline information used as baseline features | Time-varying covariates or landmarking |

## Done when

- [ ] Time zero, event definition and censoring rules are written down and checked on the data.
- [ ] Kaplan-Meier description with numbers at risk is included.
- [ ] Model assumptions were checked and violations handled.
- [ ] Prediction metrics come from held-out subjects, include a no-covariate baseline, and cover both ranking and calibration when probabilities are used.
- [ ] Competing risks are handled or explicitly ruled out.
- [ ] License of each survival library is acceptable for the intended use.
