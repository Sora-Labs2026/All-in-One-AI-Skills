# Physiological signals with NeuroKit2: ECG, PPG, HRV, EDA, respiration, EMG

Read this when code processes electrocardiogram (ECG), photoplethysmogram (PPG), heart rate variability (HRV), electrodermal activity (EDA, skin conductance), respiration (RSP), electromyogram (EMG) or electrooculogram (EOG) recordings, or event-related physiology from an experiment. EEG analysis belongs in MNE-Python; NeuroKit2's EEG helpers are thin. Models trained on signals follow `../../ml-engineering/references/time-series-ml.md`.

**Guardrail.** Features such as RMSSD or skin conductance responses are research measures, not diagnoses. Do not tell a person they have an arrhythmia, stress disorder or any condition. Software that detects or diagnoses a condition can be a regulated medical device (`medical-device-quality.md`). Recordings with timestamps and device IDs are personal health data (`clinical-deidentification.md`).

## Setup

```bash
python -m pip install neurokit2          # 0.2.x; pulls numpy, scipy, pandas, scikit-learn
python -c "import neurokit2 as nk; print(nk.__version__)"
python -m pip install wfdb pyedflib      # optional readers: PhysioNet WFDB and EDF/BDF files
```

Some methods need extra packages (for example the cvxEDA decomposition needs `cvxopt`); the error message names them. Function defaults have changed between 0.2 releases, so pass `method=` explicitly and record the version.

## Know the recording before processing it

- **Sampling rate.** Pass it to every call. Confirm it from timestamps (`np.median(np.diff(t))`) rather than trusting a header or a filename. A wrong rate scales every interval and every HRV value.
- **Units and polarity.** ECG in mV with upright R waves (an inverted lead breaks some detectors; `nk.ecg_invert` can fix it), EDA in microsiemens, respiration in arbitrary belt units.
- **Device and placement.** A 12-lead clinical ECG, a chest strap and a wrist PPG differ in noise, artifacts and validity. Wrist PPG during movement is often unusable.
- **Gaps and clipping.** Find dropouts, flat lines and saturated segments first; interpolating across long gaps fabricates beats.
- **Clock.** Store timestamps in UTC with the device offset; align stimulus logs to the recording with a hardware trigger channel where one exists, not by matching wall clocks.

Typical minimum sampling rates for analysis: ECG 250 Hz or more for R-peak timing in HRV (500 to 1,000 Hz is better), PPG 64 Hz or more, EDA 10 to 32 Hz, respiration 10 Hz or more, surface EMG 1,000 Hz or more.

## ECG and HRV

```python
import neurokit2 as nk

fs = 500
signals, info = nk.ecg_process(ecg, sampling_rate=fs, method="neurokit")   # clean, R peaks, rate, quality
rpeaks = info["ECG_R_Peaks"]
quality = nk.ecg_quality(signals["ECG_Clean"], rpeaks=rpeaks, sampling_rate=fs, method="zhao2018")

artifacts, rpeaks_fixed = nk.signal_fixpeaks(rpeaks, sampling_rate=fs, iterative=True, method="Kubios")
hrv_time = nk.hrv_time(rpeaks_fixed, sampling_rate=fs)        # RMSSD, SDNN, pNN50, ...
hrv_freq = nk.hrv_frequency(rpeaks_fixed, sampling_rate=fs)   # interpolates the RR series before the spectrum
```

- `ecg_process` already filters. Do not band-pass the signal again before calling it, and do not feed it a signal that another tool already cleaned with different settings.
- Look at the result: `nk.ecg_plot(signals, info)` or an overlay of peaks on a few windows, including the noisiest one.
- Count and report corrected beats. Ectopic beats and missed or extra peaks inflate RMSSD and high-frequency power far more than they change mean heart rate. Set a rule in advance (for example, drop windows where more than a few percent of beats were corrected) and report how many windows it removed.
- **Duration rules** (from the 1996 HRV standards of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology): compare short-term measures on 5-minute recordings; HF power needs at least about 1 minute and LF at least about 2 minutes; VLF from recordings of 5 minutes or less is not interpretable; ULF and SDNN over 24 hours need 24-hour recordings. Ultra-short RMSSD (under a minute) is a research topic, not a standard.
- Frequency bands: VLF up to 0.04 Hz, LF 0.04 to 0.15 Hz, HF 0.15 to 0.4 Hz. Slow breathing (under 9 breaths per minute) moves respiratory power into the LF band, so LF/HF is not a clean "sympathovagal balance" index; report it with that caveat or not at all.
- Pulse rate variability from PPG approximates HRV at rest in healthy adults and diverges with movement, arrhythmia and poor perfusion. Name it pulse rate variability.

## PPG, EDA, respiration, EMG

- **PPG:** `nk.ppg_process(ppg, sampling_rate=fs)`. Check peak detection on motion segments; use the device's motion channel to mask them when available.
- **EDA:** `nk.eda_process(eda, sampling_rate=fs)` separates tonic (skin conductance level) and phasic (responses) parts and finds skin conductance responses (SCRs). Choose the decomposition (`method="highpass"`, `"smoothmedian"` or `"cvxeda"` in `nk.eda_phasic`) and the SCR amplitude threshold (often 0.01 to 0.05 microsiemens) before looking at results. Levels differ greatly between people and with temperature; compare within person or normalize per participant, and expect some non-responders.
- **Respiration:** `nk.rsp_process(rsp, sampling_rate=fs)` gives rate, amplitude and phase; belt and thermistor signals need different cleaning. Respiration volume per time is used to model breathing effects in fMRI.
- **EMG:** `nk.emg_process(emg, sampling_rate=fs)` gives the amplitude envelope and activation onsets. Activation thresholds depend on the baseline noise of each recording; state the method.
- **EOG:** blink detection with `nk.eog_process`; vertical EOG electrodes are needed for blinks.

## Event-related designs

```python
events = nk.events_find(trigger, threshold=0.5, threshold_keep="above")
epochs = nk.epochs_create(signals, events, sampling_rate=fs, epochs_start=-1, epochs_end=6)
features = nk.ecg_analyze(epochs, sampling_rate=fs, method="event-related")
```

- Pass `method="event-related"` or `method="interval-related"` explicitly. With `"auto"`, the choice depends on the epoch length (short epochs count as event-related), which can surprise you.
- Use a pre-stimulus baseline and make the epoch long enough for slow responses: SCRs peak several seconds after a stimulus, and heart rate responses evolve over several seconds.
- One participant contributes many epochs; aggregate per participant before group statistics.

## Filtering pitfalls

- Offline analysis uses zero-phase filters (forward and backward) to keep peak timing; real-time code needs causal filters and must accept their delay.
- Remove powerline interference (50 or 60 Hz) with a notch only when it is present; filter before downsampling, never after.
- Edge effects distort the first and last seconds of every filtered segment. Filter the continuous recording, then cut epochs.
- Long recordings (24 hours at 500 Hz is 43 million samples per channel) should be processed in overlapping windows with numpy arrays; the per-sample DataFrames NeuroKit2 returns are memory-heavy.

## Test with simulated signals, validate on annotated data

```python
ecg = nk.ecg_simulate(duration=300, sampling_rate=500, heart_rate=65, random_state=7)   # synthetic, for tests only
```

- Simulators (`ecg_simulate`, `ppg_simulate`, `eda_simulate`, `rsp_simulate`) make pipeline tests deterministic. Label their output synthetic; never present it as a participant's data.
- Validate detectors against expert-annotated recordings, for example the MIT-BIH Arrhythmia Database on PhysioNet (open license; downloading it needs network access and the user's go-ahead). Match detected and annotated beats within a tolerance window (150 ms is the window used in common QRS benchmarks) and report sensitivity and positive predictive value.

## Checks (done when)

- Sampling rate verified from timestamps; NeuroKit2 version and every `method=` choice recorded.
- Peaks were inspected on plots, including the worst-quality window; corrected-beat counts and exclusion rules are reported.
- HRV measures respect the duration rules; LF/HF is either omitted or caveated.
- Event-related analyses state baseline, epoch window and aggregation per participant.
- The detector was validated on annotated data or the report says `NOT VERIFIED` for detection accuracy.
- No diagnostic language appears in outputs meant for participants or users.
