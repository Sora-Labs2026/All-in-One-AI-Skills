# Spike sorting high-density probes: SpikeInterface, Kilosort and quality metrics

Read this when the data are extracellular recordings from high-density probes (Neuropixels 1.0 or 2.0, or other silicon probes) acquired with SpikeGLX, Open Ephys or stored as NWB, and the task is preprocessing, drift correction, spike sorting, quality metrics, curation, or export for analysis and sharing.

**Guardrail.** Animal work follows the approved protocol; recordings from human participants (intraoperative or epilepsy monitoring) are clinical data and need de-identification and access control (`clinical-deidentification.md`). Automated and model-assisted curation is advisory; a person decides which units are reported.

## Tools and versions

- **SpikeInterface** wraps readers, preprocessing, sorters, postprocessing, metrics, comparison and export behind one API. Its API changed substantially in recent releases: the `SortingAnalyzer` replaced `WaveformExtractor` in 0.100, and motion functions were reorganized in 0.101. Check `si.__version__` and use that version's docs.
- **Kilosort 4** (`pip install kilosort`, PyTorch) is the common default sorter for Neuropixels. It wants an NVIDIA GPU; on CPU it is very slow. Kilosort 2.5 and 3 need MATLAB; run them through SpikeInterface's container support (`docker_image=True` or Singularity) instead of installing MATLAB toolchains by hand.
- CPU-capable alternatives: SpykingCircus2, Tridesclous2, Mountainsort5. Comparing two sorters is a useful sanity check.
- Manual review: Phy (`si.export_to_phy`) or SpikeInterface's GUI. Sharing: NWB via NeuroConv, published to the DANDI archive; validate files with `nwbinspector`.

```bash
python -m pip install "spikeinterface[full]" kilosort
python -c "import spikeinterface as si, kilosort; print(si.__version__)"
```

## Load and inspect

```python
import spikeinterface.full as si

print(si.get_neo_streams("spikeglx", "data/run_g0"))                 # for example imec0.ap, imec0.lf, nidq
rec = si.read_spikeglx("data/run_g0", stream_id="imec0.ap")
print(rec.get_num_channels(), rec.get_sampling_frequency(), rec.get_total_duration())
print(rec.get_probe())                                               # geometry must be attached; sorting needs it
test = rec.frame_slice(0, int(120 * rec.get_sampling_frequency()))   # develop on two minutes, then run the full file
job_kwargs = dict(n_jobs=8, chunk_duration="1s", progress_bar=True)
```

- Neuropixels 1.0 has separate AP (30 kHz) and LFP (2.5 kHz) streams; 2.0 records one wide-band stream at 30 kHz. Sort the AP band.
- Keep the probe geometry and channel map attached through every step; a missing or wrong map ruins template matching without an error.
- Data rate is about 23 MB per second for 384 channels at 30 kHz in int16, about 83 GB per hour per probe. Plan disk, preferably fast SSD, for raw, preprocessed and sorter output (several times the raw size).

## Preprocess

```python
rec = si.highpass_filter(rec, freq_min=300.0)
rec = si.phase_shift(rec)                         # align channels sampled at different times by a multiplexed ADC
bad_ids, labels = si.detect_bad_channels(rec)     # dead, noisy and outside-brain channels
rec = rec.remove_channels(bad_ids)                # or interpolate them with si.interpolate_bad_channels
rec = si.common_reference(rec, operator="median", reference="global")
rec = rec.save(folder="preprocessed", format="binary", **job_kwargs)   # sorters and metrics then read a plain binary
```

- Apply `phase_shift` before any spatial operation (common reference, destriping). It uses the inter-sample shift that the SpikeGLX and Open Ephys readers set for Neuropixels probes; if the property is missing, find out why before skipping it.
- Common median reference removes shared noise; a spatial high-pass filter (IBL-style destriping) is an alternative for strong stripes.
- Record the bad-channel list and its reason labels in the run notes.

## Drift

Brain tissue moves relative to the probe, and uncorrected drift splits and merges units.

- Estimate motion and look at the drift raster (spike depth over time) before and after correction. SpikeInterface's `correct_motion` takes presets (names vary by version; check `si.correct_motion` docs for the current list, such as rigid, non-rigid and DREDge-based presets).
- Kilosort 4 corrects drift itself (controlled by its `nblocks` parameter). Correct once: either let Kilosort do it, or correct in SpikeInterface and turn Kilosort's correction off. Correcting twice degrades results.
- Large or abrupt shifts (probe settling early in a session) may need the first minutes excluded rather than corrected.

## Sort and postprocess

```python
params = si.get_default_sorter_params("kilosort4")
sorting = si.run_sorter("kilosort4", rec, folder="ks4_out", **params)
sorting = si.remove_excess_spikes(sorting, rec)

analyzer = si.create_sorting_analyzer(sorting, rec, sparse=True, format="binary_folder", folder="analyzer")
analyzer.compute(["random_spikes", "waveforms", "templates", "noise_levels", "spike_amplitudes",
                  "unit_locations", "correlograms", "template_similarity"], **job_kwargs)
metrics = si.compute_quality_metrics(analyzer)    # pandas DataFrame, one row per unit
metrics.to_csv("quality_metrics.csv")
```

- Save the sorter name, version, full parameter set, the SpikeInterface version and the preprocessing chain with the outputs. Many sorters have stochastic steps; record seeds where they exist and expect small differences between runs.
- GPU memory errors usually come from batch size or very long recordings; reduce the batch, do not silently switch sorters.

## Quality metrics and curation

Common metrics: firing rate, presence ratio (fraction of the session with spikes), ISI violation ratio and refractory-period contamination, amplitude cutoff (estimated missed spikes), median amplitude, signal-to-noise ratio, and PCA-based isolation measures (isolation distance, L-ratio, d-prime, nearest-neighbor isolation; these need the principal components extension).

- Thresholds are choices, not facts. A widely used starting set is presence ratio above 0.9, ISI violation ratio below 0.5 and amplitude cutoff below 0.1; other groups use different sets. Write the thresholds down before looking at results, apply them as code, and report how many units pass each one.
- Check a sample of units by eye: waveform across neighboring channels, autocorrelogram with a refractory dip, amplitude stable over time, and drift-consistent location. Include borderline units and units on bad-channel boundaries in the sample.
- Automated classifiers and image-based model judgments speed up triage. Treat their labels as suggestions and keep the human decision in the record.
- Report unit counts by label (good, multi-unit, noise) and say which ones the analysis uses.

## Validate the pipeline

- Run the same pipeline on a synthetic recording with known ground truth (`si.generate_ground_truth_recording`, or hybrid recordings that inject known units into real noise) and score it with `si.compare_sorter_to_ground_truth` (accuracy, recall, precision per unit).
- Compare two sorters on a real session (`si.compare_two_sorters`); low agreement on units you planned to report is a warning.
- Stability check: rerun on a subset with a different seed and compare the units kept.

## Checks (done when)

- Probe geometry attached, sampling rate and channel count confirmed, bad channels listed with reasons.
- Drift raster reviewed before and after correction, with correction applied exactly once.
- Sorter, versions, parameters and preprocessing chain saved with the outputs; quality metrics saved as a table.
- Curation thresholds written before results, applied in code, with counts per threshold, plus a visually checked sample.
- The pipeline was validated on ground-truth or hybrid data, or the report marks sorting accuracy `NOT VERIFIED`.
- NWB exports pass `nwbinspector` before sharing.
