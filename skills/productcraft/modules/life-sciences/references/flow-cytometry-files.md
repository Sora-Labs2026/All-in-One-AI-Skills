# Flow cytometry files and event data

Read this when you read or write FCS files, pull events and channel metadata into Python, apply compensation and transforms, or build a pipeline around cytometry data. Statistics and clustering follow `../../ml-engineering/GUIDE.md`.

## The format

An FCS file holds a HEADER, a TEXT segment of keyword-value pairs, a DATA segment of events by parameters, and an optional ANALYSIS segment. Versions 2.0, 3.0 and 3.1 are common; 3.2 adds more. Key keywords:

| Keyword | Meaning |
|---|---|
| `$PAR` | Number of parameters (channels) |
| `$TOT` | Number of events |
| `$PnN` | Short channel name (`FSC-A`, `BV421-A`) |
| `$PnS` | Stain or marker name (`CD3`), often empty |
| `$PnR`, `$PnE`, `$PnG` | Range, logarithmic amplification, gain |
| `$DATATYPE`, `$BYTEORD` | Numeric type and byte order |
| `$SPILLOVER` (or `SPILL`) | Spillover matrix, when the instrument wrote one |
| `$CYT`, `$DATE`, `$BTIM` | Instrument, acquisition date and time |

Files from different instruments vary in how they use these, and some write offsets that disagree between HEADER and TEXT. A robust reader needs options for that.

## Libraries

| Library | Use |
|---|---|
| FlowIO (BSD) | Minimal, dependency-light reading and writing of FCS; events as arrays, full TEXT access |
| FlowKit (BSD) | Higher level: samples, compensation, transforms, gating, GatingML and FlowJo workspace import |
| FlowCal, cytoflow | Alternative analysis-oriented libraries |

Reading the file is the easy part; compensation, transforms and gating are where results are decided.

```bash
python -m pip install flowio flowkit
python -c "import flowio; print(flowio.__version__)"
```

## Reading

```python
import flowio
import numpy as np

fd = flowio.FlowData("sample.fcs")
print(fd.version, fd.event_count, fd.channel_count)
events = np.reshape(fd.events, (-1, fd.channel_count))        # events x channels

names = [fd.channels[str(i)]["PnN"] for i in range(1, fd.channel_count + 1)]
stains = [fd.channels[str(i)].get("PnS", "") for i in range(1, fd.channel_count + 1)]
```

- Read metadata only (`only_text=True` in recent releases) when scanning many files; it avoids loading events.
- Some files need tolerance options for offset discrepancies; use them deliberately and record that you did, because they mean the file is malformed.
- Multi-dataset files exist (several acquisitions in one file); check for them rather than assuming one.
- Raw values are instrument units. Whether preprocessing (gain, log amplification) has been applied depends on the reader's options; check the keyword values and state what you used.

## Compensation

Spectral spillover between detectors must be removed before any marker is interpreted.

```python
import flowkit as fk

sample = fk.Sample("sample.fcs")
if sample.compensation is None:                 # no embedded $SPILLOVER
    comp = fk.Matrix(spill_csv_text, detectors=detector_names)
    sample.apply_compensation(comp)
else:
    sample.apply_compensation(sample.compensation)
```

- The matrix must come from single-stain controls acquired with the same instrument settings as the samples. A matrix from another day or another configuration is wrong.
- Record the matrix source (embedded, separate file, acquisition software) in the report.
- Spectral cytometers use unmixing rather than classical compensation; use the instrument's unmixed output or a method built for it, and say which.
- Over- or under-compensation shows as populations bending away from the axes on two-parameter plots. Look at the plots.

## Transforms

Fluorescence spans orders of magnitude and includes negative values after compensation, so plain log fails.

```python
xform = fk.transforms.LogicleTransform(param_t=262144, param_w=0.5, param_m=4.5, param_a=0.0)
sample.apply_transform(xform)
```

- Logicle (or biexponential) for fluorescence; arcsinh with a cofactor is the usual choice for mass cytometry (a cofactor near 5 is a common starting point) and for analysis pipelines.
- Transform parameters change where populations appear. Use one setting across every sample in a study and record it; comparing samples transformed differently is meaningless.
- Scatter channels (FSC, SSC) are usually left linear.

## A sound pipeline

1. Quality control per file: event count, acquisition time trace (flow instabilities show as gaps or jumps), fraction of events outside the measurable range.
2. Compensation or unmixing with controls from the same run.
3. Transform with one shared setting.
4. Clean-up gating: remove debris (scatter), doublets (height against area), and dead cells (viability dye).
5. Analysis: manual gates for defined populations, and unsupervised methods (clustering such as FlowSOM-style approaches, with dimensionality reduction for display) for discovery.
6. Report **both** the percentage of a parent population and the absolute count where counting beads or a volumetric instrument allow it.

Gating is a modeling choice. Record the gate definitions (export GatingML or the workspace), the gating order, and the events remaining after each step. Batch effects between acquisition days are real; include controls across batches and check them before comparing.

## Writing files

```python
flowio.create_fcs(open("out.fcs", "wb"), events.flatten().tolist(), channel_names=names,
                  opt_channel_names=stains, metadata_dict={"$SRC": "reprocessed"})
```

Writers typically emit FCS 3.1 with float data; original integer resolution and some vendor keywords are not preserved. Keep the original file, and document any transform already applied to written values so a later reader does not apply it twice.

## Privacy

Clinical cytometry files carry patient identifiers in TEXT keywords (sample names, patient IDs, dates, operator). Strip or replace them with coded IDs before sharing, and check the keyword dump rather than assuming; the duties in the clinical section of `../GUIDE.md` apply.

## Checks (done when)

- [ ] File version, event count and channel names and stains reported; malformed-file options recorded if used.
- [ ] Compensation or unmixing applied, with the matrix source named, and plots inspected.
- [ ] One transform with recorded parameters used across all samples.
- [ ] Clean-up gating documented with events remaining at each step; batch controls checked.
- [ ] Identifying keywords removed before any file is shared.
