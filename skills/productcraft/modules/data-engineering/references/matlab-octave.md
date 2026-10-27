# MATLAB and GNU Octave

Read this when a project contains `.m` files, `.mat` data or Simulink models; when MATLAB or Octave code must run non-interactively; when data moves between MATLAB and Python; or when code is ported from MATLAB to NumPy and SciPy. Numerical methods themselves (solvers, integration, stability) are in `../../scientific-computing/GUIDE.md`.

## Licensing and availability

- **MATLAB** is commercial. Each user or machine needs a license, and toolboxes (Statistics and Machine Learning, Signal Processing, Optimization and others) are licensed separately. Never assume MATLAB or a toolbox is installed: check with `matlab -batch "ver"` and `license('test', 'Statistics_Toolbox')`.
- **GNU Octave** is free software under the GPL version 3. Running your own scripts in Octave does not put them under the GPL; distributing software that links Octave's libraries can. Octave packages (`pkg install -forge ...`, now often from their own repositories) have their own licenses.
- Running MATLAB in CI needs a license arrangement that allows it; check with the user before wiring MATLAB into a pipeline.

## Running non-interactively

```bash
# MATLAB R2019a and later: no desktop, runs the statement, exits nonzero on an uncaught error
matlab -batch "addpath('src'); results = run_analysis('data/input.csv'); disp(results)"

# GNU Octave
octave --no-gui --no-window-system --eval "addpath('src'); run_analysis('data/input.csv')"
octave-cli --eval "run_analysis('data/input.csv')"
```

- Older MATLAB releases use `matlab -nodisplay -nosplash -r "try, run_analysis(); catch e, disp(getReport(e)); exit(1); end; exit(0)"`; without the explicit `exit`, the process waits forever.
- Write functions, not scripts that rely on workspace state, so each run starts clean and takes explicit inputs.
- Figures in headless runs: create them invisible (`figure('Visible', 'off')`) and save with `exportgraphics(fig, 'out.pdf', 'ContentType', 'vector')` (MATLAB R2020a+) or `print -dpdf` (both); in Octave set a non-interactive graphics toolkit (`graphics_toolkit gnuplot` or use `--no-window-system`).
- Tests: MATLAB's unit test framework (`runtests('tests')`, `matlab.unittest`) works in batch mode; in Octave, `test` blocks inside function files (`%!test`) run with `test function_name`.

## Writing code that runs in both

Octave accepts syntax MATLAB rejects. For portability avoid: `#` comments (use `%`), `!=` (use `~=`), `++` and `+=`, double-quoted strings with backslash escapes, `endif`/`endfor`/`endwhile` (use `end`), `printf` (use `fprintf`), `unwind_protect` (use `try`/`catch` or `onCleanup`), and `do ... until`.

MATLAB features with missing or partial Octave support: the `string` class and its functions, `table` and `timetable`, many toolbox functions, parts of `classdef`, App Designer and GUIDE apps, Simulink, and live scripts (`.mlx`, a zipped format). Detect the runtime when needed:

```matlab
isOctave = exist('OCTAVE_VERSION', 'builtin') ~= 0;
```

Test in both environments when both are targets; "runs in MATLAB" is not evidence for Octave.

## Exchanging data with Python

- **MAT files version 5 to 7.2**: `scipy.io.loadmat("data.mat", squeeze_me=True, simplify_cells=True)` returns NumPy arrays and nested dicts; `scipy.io.savemat` writes them. Structs, cell arrays and MATLAB objects come back as nested arrays or are not supported, so inspect the result.
- **MAT version 7.3** files are HDF5. `loadmat` refuses them; read with `h5py` (or a helper package for 7.3 files). Arrays appear transposed, because MATLAB is column-major; strings are stored as `uint16` codes; cell arrays are HDF5 object references.
- For pipelines, prefer neutral formats with explicit layout: CSV with a header (`writetable`/`readtable` in MATLAB), Parquet (`parquetwrite`/`parquetread`, MATLAB R2019a+), or HDF5 with documented dimension order.
- **Calling MATLAB from Python:** the MATLAB Engine API for Python (`pip install matlabengine`, with a version matching the installed MATLAB release) starts a MATLAB session; `eng.my_function(matlab.double([[1.0, 2.0]]), nargout=1)`. It needs a licensed local MATLAB.
- **Calling Python from MATLAB:** `pyenv` selects the interpreter; `py.numpy.array(...)` and `py.module.function(...)` call Python; conversions of nested types need care.

## Performance in MATLAB and Octave

- Measure first: `profile on; run_analysis(); profile viewer` (MATLAB) or `profile on; ...; profshow` (Octave), and `timeit` for small functions.
- Preallocate arrays (`zeros(n, 1)`) instead of growing them inside loops; growth copies the array each iteration.
- Vectorize element-wise work and use logical indexing. Modern MATLAB compiles loops well, so a clear loop can beat a convoluted vectorization; Octave's interpreter is much slower on loops, which matters when code must run in both.
- Large data: `datastore` and `tall` arrays in MATLAB process files in chunks; `matfile` reads parts of a version 7.3 MAT file without loading it all.

## Tables and dates across the boundary

- MATLAB `table` and `timetable` map naturally to pandas DataFrames, but MAT files cannot carry them to Python in a readable form. Export with `writetable(T, "out.csv")` or `parquetwrite("out.parquet", T)` and read with pandas or Polars.
- MATLAB `datetime` values without a `TimeZone` are naive; set it before export. Older code stores dates as serial day numbers (`datenum`, days from year 0), which differ from Excel serials and Unix time: convert with `datetime(x, "ConvertFrom", "datenum")` in MATLAB, or subtract 719529 to get days since 1970-01-01 in Python.
- Categorical arrays export as text; restore the category order explicitly on the Python side when it carries meaning.

## Porting MATLAB to NumPy and SciPy

| MATLAB | NumPy / SciPy | Trap |
|---|---|---|
| Indexing from 1; `a(end)` | Indexing from 0; `a[-1]` | Off-by-one in every loop and slice |
| `a(2:5)` includes both ends | `a[1:5]` excludes the end | Range lengths differ |
| Column-major storage | Row-major by default | `reshape` gives different layouts; use `order="F"` to match MATLAB |
| `A * B` is matrix product; `A .* B` elementwise | `A @ B` matrix product; `A * B` elementwise | Silent wrong results when shapes allow both |
| `A \ b` | `np.linalg.solve(A, b)` for square systems; `np.linalg.lstsq` or `scipy.linalg.lstsq` otherwise | MATLAB picks a solver by matrix structure and warns on near-singular matrices; NumPy does not warn |
| `std(x)`, `var(x)` normalize by N-1 | `np.std(x)`, `np.var(x)` normalize by N (`ddof=0`) | Pass `ddof=1` to match MATLAB; pandas already uses `ddof=1` |
| `round(2.5)` is 3 (half away from zero) | `np.round(2.5)` is 2.0 (half to even) | Different results on exact halves |
| `max`, `min`, `sum` with `'omitnan'`; `max`/`min` ignore NaN by default | `np.max` returns NaN if any value is NaN | Use `np.nanmax`, `np.nanmin`, `np.nansum` deliberately |
| Integer types saturate (`uint8(250) + 10` is 255) | NumPy integers wrap around (250 + 10 becomes 4 in `uint8`) | Cast to a wider type before arithmetic |
| `mod(-1, 3)` is 2; `rem(-1, 3)` is -1 | `np.mod(-1, 3)` is 2; `np.fmod(-1, 3)` is -1 | Map `rem` to `fmod`, not `%` |
| `size(x)` of a vector is `[1 n]` or `[n 1]` | 1-D arrays have shape `(n,)` | Row versus column vectors disappear; broadcasting can then produce an n-by-n matrix |
| `rand`, `randn` with `rng(seed)` | `np.random.default_rng(seed)` | Random streams differ; a port cannot reproduce MATLAB's random numbers exactly |
| `interp1` default linear; `unique` returns sorted values | `np.interp` (linear, clamps outside the range); `np.unique` sorted | Extrapolation behavior differs: MATLAB returns NaN outside the range by default |

Verify a port by running the original on fixed inputs, saving outputs (MAT or CSV), and comparing in Python with `np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)`, adjusting tolerances only with a reason (different BLAS libraries and summation orders change the last digits). Compare shapes and orientation as well as values.

## Checks (done when)

- [ ] MATLAB and toolbox availability, or Octave version, checked rather than assumed; licensing implications stated for CI or redistribution.
- [ ] Batch runs exit nonzero on failure and produce their outputs without a display.
- [ ] Code meant for both runtimes avoids Octave-only syntax and was run in both.
- [ ] MAT version identified before choosing a reader; dimension order verified on a known array.
- [ ] Ports verified against golden outputs from the original with stated tolerances.
