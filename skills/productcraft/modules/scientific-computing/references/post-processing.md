# Post-processing simulation output

Read this when turning raw simulation output into numbers and figures: reading large output files, extracting fields, profiles and probes, computing derived quantities, comparing with analytic, reference or experimental data, judging steady state, putting error bars on time averages, and producing figures and reports that can be regenerated.

Dataframes, SQL, Dask and general plotting libraries are covered in `../../data-engineering/GUIDE.md`; this file covers what is specific to simulation data.

## 1. Read output safely and efficiently

| Format | Read with | Notes |
|---|---|---|
| HDF5 | `h5py`, PyTables, xarray (`h5netcdf` engine) | Slice datasets instead of loading them whole; store units and metadata as attributes |
| NetCDF | xarray with netCDF4 or h5netcdf | Follow the CF conventions for units and coordinates |
| Zarr | xarray, `zarr` | Chunked, parallel and object-store friendly |
| VTK, VTU, XDMF, Exodus | PyVista, meshio | Distinguish point data from cell data |
| `.npy`, `.npz` | `np.load` (keeps `allow_pickle=False`, the default) | Simple, but no units or metadata |
| CSV | pandas, the `csv` module | Scalars and time histories only |
| MATLAB `.mat` | `scipy.io.loadmat`; version 7.3 files are HDF5 (`h5py`) | See `symbolic-math-and-matlab.md` |

- Open large datasets lazily (`xarray.open_dataset(..., chunks={})` with Dask, or `h5py` slicing) and reduce before loading.
- **Never unpickle untrusted files.** Pickle (and `np.load(..., allow_pickle=True)`) executes code while loading. Prefer self-describing formats for anything shared.
- Treat raw output as read-only. Write derived data to a separate folder, together with the script and the version that produced it.

## 2. Fields, profiles and probes

- **Know where values live.** Cell-centered, node-based and face-based (staggered) values differ in location; interpolating cell data to nodes smooths it. State which one a plot shows.
- **Line profiles:** on structured grids, `scipy.interpolate.RegularGridInterpolator` (linear by default) or exact grid lines when the profile follows one; on unstructured meshes, PyVista `sample_over_line` or `probe`.
- Interpolation across a discontinuity (shock, interface) invents intermediate values. Sample on either side, or report the jump.
- Check the axis order: `meshgrid` indexing (`"ij"` versus `"xy"`), and the memory order of arrays written by Fortran or MATLAB codes (column-major).

## 3. Derived quantities

- **Derivatives:** `np.gradient(f, x, edge_order=2)` handles nonuniform coordinates when you pass the coordinate array. Differentiation amplifies noise; for noisy data, fit or filter first and say so. Use an order at least as high as the solver's to avoid post-processing error dominating.
- **Integrals:** for finite-volume data, `sum(value * cell_volume)` is exactly the discrete conserved quantity. For sampled functions use `np.trapezoid` (NumPy 2.0 renamed `trapz`) or `scipy.integrate.simpson` (SciPy removed the old `simps` in 1.14).
- **Coefficients and dimensionless numbers** (drag coefficient, Nusselt number, Strouhal number): write down the reference area, length, velocity and property values used. Different normalizations make results from different sources incomparable.
- Attach units to every derived column, with `pint` or `astropy.units`, or at least in the column name (`drag_force_n`). See `../../engineering-practices/references/spec-and-units.md` for unit discipline in code.

## 4. Comparing with a reference

- **Common points:** interpolate the finer or analytic solution onto the coarser points, not the other way around, so the comparison does not reward interpolation smoothing.
- **Norms:** volume-weighted discrete norms, reported with their units and, for relative norms, the reference norm:

```python
import numpy as np

def relative_l2(u, reference, weights):
    """Volume-weighted relative L2 error; weights are cell volumes (or quadrature weights)."""
    return np.sqrt(np.sum(weights * (u - reference) ** 2) / np.sum(weights * reference ** 2))

def linf(u, reference):
    return np.max(np.abs(u - reference))
```

- **Phase and position errors:** a wave or front shifted by one cell gives a large pointwise error even when shape and amplitude are right. Report the shift (cross-correlation peak, front position) separately from the shape error when that is the physics question.
- **Experimental data:** compare in the experiment's terms (probe volume, time averaging, filtering), include measurement uncertainty, and record the data source and version. Validation logic is in `verification-and-validation.md`.

## 5. Time series: transients, steady state and uncertainty

**Initial transient.** Discard it before computing statistics. Inspect the series, then confirm with a stationarity check: the mean over the first and second halves of the retained window agree within their uncertainties. Truncation heuristics such as MSER help automate the choice; record the cut time.

**Steady state of an iterative solver.** Require both: residuals below tolerance and the quantity of interest changing by less than its tolerance over a window of iterations. Residuals alone can plateau while an integral quantity still drifts.

**Uncertainty of a time average.** Successive samples are correlated, so the naive standard error `std / sqrt(N)` is too small, often by a large factor. Use block averaging: the standard error of block means rises with block size and plateaus once blocks are longer than the correlation time; the plateau is the honest error.

```python
import numpy as np

def block_standard_errors(x, min_blocks=16):
    """Rows of (block size, number of blocks, standard error); read the plateau, ignore the noisy tail."""
    x = np.asarray(x, dtype=float)
    rows, size = [], 1
    while len(x) // size >= min_blocks:
        n = len(x) // size
        means = x[: n * size].reshape(n, size).mean(axis=1)
        rows.append((size, n, means.std(ddof=1) / np.sqrt(n)))
        size *= 2
    return rows
```

Equivalently, estimate the integrated autocorrelation time `tau = 1 + 2 * sum(rho_k)` (in samples, summing the autocorrelation `rho_k` up to a cutoff where it becomes noise) and use `N_eff = N / tau`. If no plateau appears, the run is too short to quote an error; say so instead of quoting the naive one.

**Spectra.** Use Welch's method (`scipy.signal.welch`) with a window; sample at least twice the highest frequency of interest; resample to uniform time first when outputs came from adaptive steps (or use a Lomb-Scargle periodogram for uneven sampling). Report frequency resolution, window and averaging.

## 6. Figures and reports

- Every axis has a quantity and a unit. Captions state resolution, parameters and what error bars mean (standard error, standard deviation, a confidence interval and its level).
- Show the reference or analytic solution on the same axes. Convergence plots are log-log with a reference slope line for the expected order.
- Produce figures from saved data by a script kept beside them, so any figure can be regenerated; record the commit of that script.
- Scientific figure design and plotting libraries: `../../data-engineering/GUIDE.md`.

## Checks (done when)

- [ ] Raw outputs untouched; derived data stored with the producing script and version.
- [ ] Every derived quantity has a written definition, units and normalization.
- [ ] Reference comparisons use common points, weighted norms and stated units.
- [ ] Time averages exclude the transient and carry a block-averaged or autocorrelation-corrected error.
- [ ] Figures regenerate from saved data; captions say what the error bars are.

## Anti-patterns

- Naive standard errors on correlated time series.
- Declaring steady state from residuals alone.
- Comparing values normalized with different reference quantities.
- Interpolating across shocks and plotting the result as data.
- Loading untrusted pickles.
