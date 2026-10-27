# Mass spectrometry: spectra, features and identifications

Read this when you process LC-MS or LC-MS/MS data in Python: reading mzML, filtering and comparing spectra, matching against spectral libraries (matchms), detecting and aligning features, or handling peptide and protein identifications (pyOpenMS). Molecular structures are in `rdkit-and-datamol.md`.

## Pick the tool

| Job | Tool |
|---|---|
| Spectral library matching, similarity scores, molecular networking input | matchms (Apache-2.0) |
| Full LC-MS processing: centroiding, feature detection, alignment, linking, identification handling, quantification | pyOpenMS (BSD, bindings to OpenMS) |
| Reading raw formats in plain Python | pyteomics (mzML, mzXML, MGF, mzIdentML, pepXML, FASTA) |
| Peptide search engines | Comet, MSFragger, X!Tandem, MS-GF+, or the vendor's own; run them, then handle results in pyOpenMS |
| Untargeted metabolomics pipelines end to end | A complete workflow (for example an OpenMS or XCMS-based pipeline); Python glue around it |

Vendor raw files must be converted first (ProteoWizard `msconvert` to mzML, usually with peak picking to centroid mode). Record the converter version and settings; they change the data.

## Setup

```bash
python -m pip install matchms pyopenms
python -c "import matchms, pyopenms; print(matchms.__version__, pyopenms.__version__)"
```

pyOpenMS wheels bundle the OpenMS libraries; its Python API mirrors the C++ one, so parameters are set through `Param` objects rather than keyword arguments.

## Facts that decide correctness

- **m/z, not mass.** A spectrum's x-axis is mass-to-charge. Convert with the charge and adduct before comparing to a molecular mass; a 2+ peptide appears at roughly half its mass.
- **Tolerances:** parts per million for high-resolution instruments (typically 5 to 20 ppm for precursors), absolute Da for low-resolution or fragment matching (for example 0.01 to 0.05 Da). State both precursor and fragment tolerance with every result.
- **Polarity and adducts:** the same compound gives different precursor m/z values as [M+H]+, [M+Na]+, [M-H]- and so on. Matching across polarities without converting is a common error.
- **Monoisotopic against average mass:** use monoisotopic for high-resolution work; average mass only for large or low-resolution contexts.
- **Retention time is instrument- and method-specific.** It helps within a study and does not transfer between labs without alignment or standards.

## Spectral matching with matchms

```python
from matchms.importing import load_from_mgf
from matchms.filtering import (default_filters, normalize_intensities,
                               select_by_relative_intensity, require_minimum_number_of_peaks,
                               add_precursor_mz)
from matchms import calculate_scores
from matchms.similarity import ModifiedCosine

def clean(s):
    s = default_filters(s)              # harmonizes metadata keys, charge, ion mode
    s = add_precursor_mz(s)
    s = normalize_intensities(s)
    s = select_by_relative_intensity(s, intensity_from=0.01)
    return require_minimum_number_of_peaks(s, n_required=5)

library = [c for c in map(clean, load_from_mgf("library.mgf")) if c is not None]
queries = [c for c in map(clean, load_from_mgf("queries.mgf")) if c is not None]

scores = calculate_scores(library, queries, ModifiedCosine(tolerance=0.01))
best = scores.scores_by_query(queries[0], name="ModifiedCosine_score", sort=True)[:5]
```

- Filters return `None` when a spectrum fails; filter them out and count how many were dropped at each step.
- **Cosine** compares matched fragment peaks; **modified cosine** also matches peaks shifted by the precursor mass difference, which finds analogs; **neutral-loss** similarity compares losses from the precursor. Pick by question and state it.
- A score is not an identification. Report the score, the number of matched peaks (a high cosine on two peaks means nothing), the precursor mass error and the library entry's identifier. Require a minimum matched-peak count.
- Match within the same ion mode and compatible collision energy where the library provides it.
- Confidence levels: a library match of MS/MS plus accurate mass plus retention time against an authentic standard run on the same method is the strongest; a library match without a standard is a putative annotation; a formula or class assignment is weaker still. Say which level each annotation is.
- For molecular networking or large all-against-all comparisons, the number of pairs grows with the square of the spectrum count; filter and chunk.

## LC-MS processing with pyOpenMS

```python
import pyopenms as oms

exp = oms.MSExperiment()
oms.MzMLFile().load("sample.mzML", exp)
print(exp.getNrSpectra(), exp.getSpectra()[0].getMSLevel())

ff = oms.FeatureFinderAlgorithmPicked()        # centroided data
features = oms.FeatureMap()
params = ff.getDefaults()
params.setValue("mass_trace:mz_tolerance", 0.004)
ff.setParameters(params)
ff.run(exp, features, params, oms.FeatureMap())
features.setUniqueIds()
oms.FeatureXMLFile().store("sample.featureXML", features)
```

- Print the algorithm's defaults (`getDefaults()`) and record every value you change; parameter names and defaults differ between OpenMS releases.
- Pipeline shape for untargeted work: convert, (centroid), detect features per sample, align retention times, link features across samples into a consensus map, then annotate adducts and search a database. Keep intermediates (`featureXML`, `consensusXML`) so steps can be rerun.
- `.get_df()` on feature and consensus maps gives pandas DataFrames for downstream analysis.
- Memory: a full profile-mode run can be gigabytes. Centroid during conversion, and process spectra in chunks or on disk where the API allows it.

## Peptide and protein identifications

```python
protein_ids, peptide_ids = [], []
oms.IdXMLFile().load("search_results.idXML", protein_ids, peptide_ids)

fdr = oms.FalseDiscoveryRate()
fdr.apply(peptide_ids)                         # requires target-decoy annotated results
```

- **Target-decoy FDR is mandatory.** Search a database with decoys, control FDR at the peptide-spectrum match level, then separately at the peptide and protein levels; a 1% PSM FDR does not give a 1% protein FDR.
- **Protein inference is ambiguous:** shared peptides mean proteins are reported as groups. Report groups, not a flat list, and state the inference method.
- **Modifications** must match the search settings (fixed, variable, and the enzyme and missed cleavages). Localization of a modification within a peptide needs a site-localization score; report it.
- Record the database (name, version, number of entries, contaminants included), the search engine and version, tolerances and all search parameters.

## Quantification

- **Label-free:** normalize across runs (median or quantile), handle missing values explicitly (missing at random against below detection limit; imputation choice changes results and must be stated), then test with methods for proteomics-style data.
- **Isobaric labels:** correct for isotopic impurities and watch ratio compression from co-isolated precursors; report the isolation window and any interference filter.
- **Targeted (SRM, PRM, DIA):** report transitions, interference checks and the calibration curve; absolute quantification needs internal standards.
- Statistics follow `../../ml-engineering/references/statistical-inference.md`: replicates are samples, not injections; multiple testing across thousands of features needs adjustment.

## Licensing and data

- pyOpenMS and matchms are permissively licensed. Many public spectral libraries are free; some commercial libraries require a license, and redistributing their spectra is usually prohibited. Record which library produced each annotation.
- Public repositories expect depositions (PRIDE for proteomics, MetaboLights or the Metabolomics Workbench for metabolomics); see `data-provenance.md`.

## Checks (done when)

- [ ] Conversion settings, tolerances (precursor and fragment), ion mode and adducts recorded.
- [ ] Spectra dropped by each filter counted; matched-peak counts reported with every match score.
- [ ] Annotations labeled by confidence level, with the library and its version named.
- [ ] Identifications controlled at a stated FDR with a decoy database; protein groups reported, not flat lists.
- [ ] Quantification states normalization, missing-value handling and the replicate structure.
