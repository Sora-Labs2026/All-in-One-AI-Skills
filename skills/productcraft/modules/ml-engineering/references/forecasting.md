# Forecasting: baselines, classical models, ML and foundation models

Read this when you predict future values of one or many time series (demand, load, traffic, sensor readings, revenue), need prediction intervals, or are asked to try a pretrained forecasting model. Time-series classification, clustering and anomaly detection on whole series are in `time-series-ml.md`.

## Frame the problem first

Write these down before choosing a model; most forecasting failures are framing failures.
- **Horizon and cadence:** what is forecast (daily units, hourly kWh), how far ahead, how often it is refreshed, and when the forecast must be ready.
- **Decision and loss:** what the forecast drives (orders, staffing, alerts) and whether under- and over-forecasting cost the same. Asymmetric costs call for a quantile, not the mean.
- **Information available at forecast time:** which covariates are known in advance (calendar, planned prices, promotions, weather forecasts) and which are only known afterwards (actual weather, competitor prices). Only the first kind may enter the forecast.
- **Granularity and hierarchy:** item, store, region totals; whether forecasts must add up.
- **Data quality:** gaps, outages, stockouts (sales of zero because nothing was on the shelf are censored demand, not low demand), level shifts, changes in definition.

## Baselines are mandatory

| Baseline | Forecast | Beat it before anything else |
|---|---|---|
| Naive | Last observed value | Random-walk-like series (prices, many metrics) |
| Seasonal naive | Value one season ago | Anything with weekly or yearly patterns |
| Moving average or drift | Recent mean, or last value plus average change | Smooth trends |

Report every model's error relative to seasonal naive (MASE does this). A sophisticated model that cannot beat seasonal naive in backtests is not ready.

## Backtesting (time-series cross-validation)

Evaluate with a rolling or expanding origin: fit on data up to time T, forecast T+1 to T+h, move T forward, repeat. Score every window at the horizons the business uses.

```python
import numpy as np
import pandas as pd

def backtest(series: pd.Series, fit_predict, horizon: int, n_windows: int, step: int, min_train: int):
    """Expanding-window backtest; fit_predict(train_series, horizon) -> array of length horizon."""
    rows = []
    last_origin = len(series) - horizon
    origins = range(last_origin - (n_windows - 1) * step, last_origin + 1, step)
    for origin in origins:
        if origin < min_train:
            continue
        train, actual = series.iloc[:origin], series.iloc[origin:origin + horizon]
        pred = np.asarray(fit_predict(train, horizon))
        rows.append(pd.DataFrame({"origin": series.index[origin], "h": np.arange(1, horizon + 1),
                                  "actual": actual.values, "pred": pred}))
    return pd.concat(rows, ignore_index=True)
```

- Never shuffle. Never let a feature, scaler or fitted parameter see data after the forecast origin.
- Use at least 5 windows that cover different seasons or regimes; one holdout window is one data point.
- Add a gap between the training end and the first forecast step when data arrives late in production.
- With many series, pool errors across series and also show the distribution; a good average can hide series that are badly wrong.

## Metrics

| Metric | Use | Watch out |
|---|---|---|
| MASE (scaled by in-sample seasonal naive MAE) | Default comparison across series of different scales | Needs enough history for the scaling term |
| MAE, RMSE | Errors in units for one series or a single scale | Not comparable across series of different size |
| WAPE (sum of absolute errors over sum of actuals) | Business reporting for volumes | Dominated by large series |
| MAPE, sMAPE | Only when actuals are far from zero | Explodes or misbehaves near zero; asymmetric |
| Pinball (quantile) loss, CRPS | Probabilistic forecasts | Needs quantiles or samples |
| Interval coverage and width | Prediction intervals | An 80% interval should contain about 80% of actuals in backtests, per horizon |

Report error by horizon step; error grows with the horizon, and a single averaged number hides it.

## Model families

| Family | Tools | Good for | Limits |
|---|---|---|---|
| Exponential smoothing (ETS), Theta | statsmodels `ExponentialSmoothing`/`ETSModel`, statsforecast `AutoETS`, `AutoTheta` | Many short business series; strong, fast, intervals included | Single seasonality; no covariates (ETS) |
| ARIMA, SARIMAX | statsmodels `SARIMAX`, statsforecast `AutoARIMA` | Autocorrelated series, known exogenous drivers | Slow to tune per series at scale; multiple seasonalities need Fourier terms |
| Regression with ARIMA errors / dynamic regression | `SARIMAX(exog=...)` | Effects of price, promotions, holidays | Future exogenous values must be known or forecast |
| Gradient boosting on lag features | LightGBM, XGBoost with lags, rolling means, calendar features | Many related series with covariates; global models | Recursive multi-step error accumulation; feature leakage risk |
| Deep models | N-BEATS, N-HiTS, TFT, PatchTST (neuralforecast, darts, PyTorch Forecasting) | Large collections of related series | Data-hungry, tuning-heavy; must beat boosting and ETS |
| Pretrained foundation models | TimesFM, Chronos and Chronos-Bolt, Moirai, and similar | Zero-shot forecasts, cold-start series, quick baselines | See below |
| Intermittent demand | Croston, SBA, TSB (statsforecast) | Many zeros, sporadic sales | Evaluate with scaled or quantile metrics, not MAPE |

Libraries that wrap many of these with one interface: statsforecast and neuralforecast, sktime, darts. Pick one per project.

## Classical models in statsmodels

```python
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller, kpss

model = SARIMAX(y_train, order=(1, 1, 1), seasonal_order=(0, 1, 1, 7),
                exog=X_train_known, enforce_stationarity=True, enforce_invertibility=True)
res = model.fit(disp=False)
fc = res.get_forecast(steps=h, exog=X_future_known)
mean, ci = fc.predicted_mean, fc.conf_int(alpha=0.2)       # 80% interval
res.plot_diagnostics()                                      # residuals should look like white noise
```

- Choose orders with information criteria plus residual diagnostics (Ljung-Box), or let `AutoARIMA` search; confirm with the backtest, not in-sample fit.
- Stationarity tests (ADF, KPSS) guide differencing; seasonal differencing for strong seasonality. Tests disagree often; the backtest decides.
- Log or Box-Cox transform for multiplicative seasonality and positive data; back-transform intervals, and remember the back-transformed mean is biased low (bias adjustment exists).
- More on statsmodels idioms: `statsmodels-regression.md`.

## Machine-learning forecasting

- **Global models:** one model across many series, with series identifiers and static attributes as features, usually beats per-series models when series are related.
- **Features as of the origin:** lags at least `h` steps back for direct strategies, rolling statistics computed only from past values (`shift` before `rolling`), calendar features, known future covariates.
- **Multi-step strategy:** recursive (feed predictions back) accumulates error; direct (one model per horizon, or horizon as a feature) avoids it at more training cost. Test both.
- **Target scaling per series** (divide by the series' recent mean) lets one model learn across scales; invert after prediction.
- **Intervals:** quantile objectives (`objective="quantile"` in LightGBM) or conformal prediction on backtest residuals; check coverage per horizon.

## Foundation forecasting models

Pretrained models forecast series they have never seen, without training. Use them as strong baselines, for cold-start series with little history, or when maintaining many per-series models is costly.

As of 2025 releases (check the installed package):
- **TimesFM** (Google, Apache-2.0): decoder-only model; version 2.5 has about 200M parameters, long contexts (up to 16k points), a quantile head, and covariate support through an extra regression add-on. Its Python API changed between 1.x/2.0 and 2.5, so read the installed version's README instead of older examples. The quantile output contains the mean followed by the 10th to 90th percentiles; verify the index layout by checking that the median slice equals the point forecast.
- **Chronos and Chronos-Bolt** (Amazon, Apache-2.0): T5-based models from tiny to large; Bolt variants are much faster and return quantiles directly.
- **Moirai** (Salesforce) and others: check each model's weight license; some research releases are non-commercial.

```python
import numpy as np
# Pattern only; class and argument names differ by package and version.
context = [s.dropna().to_numpy(dtype=np.float32) for s in series_list]   # list of 1-D arrays
point, quantiles = model.forecast(horizon=h, inputs=context)            # TimesFM-style call
```

Rules for using them honestly:
- **Backtest them like any model** with the same windows and metrics, against seasonal naive and a tuned ETS or boosting model. Zero-shot does not mean evaluation-free.
- **Leakage through pretraining:** public benchmark series (M4, electricity, traffic, weather) may be in the training corpus, so published zero-shot scores on them can be optimistic. Your private data does not have this problem; evaluate on it.
- **Hardware:** small models run on CPU; larger ones need a GPU for batch throughput. Check memory before loading and start with small batches. Weights download from a model hub on first use (hundreds of MB to GBs); ask before downloading in restricted environments.
- **Inputs:** one-dimensional float arrays per series, gaps filled or handled as the model expects, no future values in the context. Positive-only clamping options must be off for series that can go negative.
- **Covariates:** only values known for the whole horizon can be used as future covariates.
- **Intervals:** check coverage in backtests; pretrained quantiles are not automatically calibrated for your data.

## Anomaly flags from forecasts

A forecast with intervals gives a simple anomaly detector: flag actuals outside the interval. Calibrate the interval level on backtests so the false-alarm rate is acceptable (an 80% interval flags about 20% of normal points). Detrend and deseasonalize before using z-scores on history. More detectors are in `time-series-ml.md`.

## Hierarchies

When forecasts must add up (item to store to region), forecast all levels and reconcile (bottom-up, top-down, or optimal reconciliation such as MinT in hierarchicalforecast). Evaluate at every level the business reads.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Random K-fold on time series | Rolling-origin backtest |
| Rolling features that include the current or future value | `shift(1)` (or more) before `rolling` |
| Actual weather or actual prices used as "future" covariates | Use forecasts of them, or values known at the origin |
| Stockout zeros treated as zero demand | Mark censored periods; exclude or model them |
| MAPE on series with zeros | MASE, WAPE or pinball loss |
| Point forecast used where costs are asymmetric | Forecast the quantile that matches the cost ratio |
| Foundation model scores copied from a paper | Backtest on the user's own series |
| Intervals never checked | Coverage per horizon in the backtest |

## Done when

- [ ] Horizon, cadence, decision, loss and known-in-advance covariates are written down.
- [ ] Rolling-origin backtests over several windows compare every candidate against naive and seasonal naive.
- [ ] Errors are reported by horizon with a scale-free metric, plus interval coverage when intervals are used.
- [ ] No feature or covariate uses information after the forecast origin.
- [ ] Model licenses (including pretrained weights) fit the intended use.
