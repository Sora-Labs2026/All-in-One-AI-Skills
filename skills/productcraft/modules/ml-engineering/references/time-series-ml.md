# Time-series machine learning: classification, regression, clustering, anomalies

Read this when each example is a whole series or window (an ECG beat, a sensor trace from one machine cycle, a gesture, a day of user activity) and you classify, regress, cluster, search or segment it, or when you detect anomalies in a stream. Forecasting future values is in `forecasting.md`.

## Tools

- **aeon** (BSD-3-Clause): scikit-learn compatible classifiers, regressors, clusterers, transformations, distances, anomaly detection, segmentation and similarity search for time series. Its forecasting module is younger than the rest; for forecasting use the tools in `forecasting.md`.
- **sktime**: similar scope with a broad forecasting framework; choose one of the two per project.
- **tsfresh**, **catch22**: feature extraction for use with any tabular model.
- Deep learning (InceptionTime, ResNet, FCN) via aeon's network modules or plain PyTorch, when data is large.

```bash
python -m pip install aeon      # check: python -c "import aeon; print(aeon.__version__)"
```

aeon's collection format is a 3-D array `(n_cases, n_channels, n_timepoints)`; univariate data has one channel. Unequal-length series are passed as a list of 2-D arrays, and only some estimators accept them (check the estimator's capability tags or documentation). Release 1.0 (late 2024) reorganized several modules; follow the installed version's API reference rather than older tutorials.

## Pick the method

| Need | Start with | Then try |
|---|---|---|
| Fast, accurate classification baseline | MiniRocket or MultiRocket (random convolutional kernels + linear classifier) | HIVE-COTE 2 for maximum accuracy when compute allows |
| Very small training sets | 1-nearest neighbor with DTW (elastic distance) | Shapelet or interval methods |
| Interpretable features | catch22 or summary-statistic features + gradient boosting or logistic regression | Shapelet transform (shows discriminative subsequences) |
| Large datasets, GPU available | InceptionTime or ResNet | Ensembles of several seeds |
| Regression from series (predict a value from a whole series) | MiniRocket or MultiRocket regressor, feature-based boosting | Deep regressors |
| Clustering whole series | k-means on z-normalized series (Euclidean), or k-medoids with DTW | Feature-based clustering |
| Find recurring patterns or nearest windows | Matrix profile (stumpy), aeon similarity search | |
| Change points and regimes | Segmentation (ClaSP in aeon, ruptures) | |
| Anomalies in a stream | Forecast residuals with calibrated intervals; matrix-profile discords; isolation forest on window features | |

ROCKET-family models are the practical default: minutes of training, accuracy close to the best published methods on standard benchmarks, no tuning beyond the number of kernels.

```python
from aeon.classification.convolution_based import MiniRocketClassifier
from sklearn.metrics import balanced_accuracy_score

clf = MiniRocketClassifier(random_state=0)        # check the class path in your aeon version
clf.fit(X_train, y_train)                          # X: (cases, channels, timepoints)
print(balanced_accuracy_score(y_test, clf.predict(X_test)))
```

## Preprocessing

- **Z-normalize each series** (per case, per channel) when shape matters more than level. Per-series normalization uses only that series, so it does not leak across the split; dataset-wide scaling must still be fitted on training data only.
- Resample to a common rate and length when estimators require equal length; record the method.
- Impute gaps before methods that cannot handle missing values, and keep a missingness indicator if gaps carry meaning.
- Elastic distances (DTW and relatives) need a warping window constraint for speed and to avoid pathological alignments; 10% of the series length is a common start.

## Splitting and leakage

- **Windows from the same long recording are not independent.** Overlapping windows in train and test leak almost the whole answer. Split by recording, subject, machine or session, and leave a gap in time when windows come from one stream.
- Subject-wise splits matter for physiological and behavioral data: a model that recognizes the person instead of the condition scores well in random splits and fails on new people.
- Public benchmark archives (UCR/UEA) come with fixed train/test splits; use them unchanged when comparing with published results, and report resampled results if you claim a difference.

## Anomaly detection

- Define what an anomaly is with the domain owner (a single spike, a level shift, a changed pattern) and collect labeled incidents for evaluation, even a few dozen.
- Evaluate with event-level precision and recall (was the incident caught, how soon, how many false alarms per day), not only point-wise scores; point-adjusted metrics that credit a whole event for one hit overstate performance.
- Set thresholds from the tolerable false-alarm rate on normal periods, then check detection of known incidents.
- Seasonal data: detect on residuals after removing trend and seasonality, or on forecast errors.

## Performance

- MiniRocket transforms thousands of series per second on a CPU; HIVE-COTE 2 can take hours on large datasets.
- DTW is quadratic in series length; use a warping window, lower bounds, or downsampling.
- Deep models need a GPU and several seeds; report mean and spread.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Overlapping windows from one recording in train and test | Split by recording or subject, with a time gap |
| Wrong array shape (cases, timepoints) passed without the channel axis | Reshape to `(n_cases, 1, n_timepoints)` for univariate data |
| Accuracy on imbalanced classes | Balanced accuracy, per-class recall, confusion matrix |
| DTW without a window on long series | Constrain the window; check run time on a sample first |
| Anomaly scores reported without a false-alarm rate | Alarms per day on normal data next to recall of known incidents |

## Done when

- [ ] Splits are by recording, subject or time, and the leakage risk of windows is addressed.
- [ ] A ROCKET-family or 1-NN DTW baseline is reported next to any complex model.
- [ ] Metrics fit the class balance or the alarm budget, with spread across folds or seeds.
- [ ] The aeon (or sktime) version is recorded, since module paths changed across releases.
