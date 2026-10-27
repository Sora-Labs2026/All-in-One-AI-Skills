# Symbolic math (SymPy) and MATLAB-style numerics

Read this when deriving formulas, Jacobians, series, stencils or manufactured solutions with SymPy; generating numerical code from symbolic expressions; or running, reading or translating MATLAB and GNU Octave code and `.mat` files.

## Part 1: SymPy

### When to use it

- **Good for:** derivations that are error-prone by hand (Jacobians, linearizations, Taylor series, stencil weights, manufactured-solution source terms), exact checks of algebra, closed-form solutions of small systems, and generating code for the result.
- **Not for:** heavy numerics. Derive symbolically, then convert to NumPy, C or Fortran and run numerically.
- Versions: SymPy 1.13 (2024) and 1.14 (2025) are current at the time of writing; check `sympy.__version__`. `symengine` offers a faster core for large expression manipulation.

### Idioms that prevent wrong answers

- **Declare assumptions.** `x = sp.symbols("x", positive=True)` lets `sqrt(x**2)` simplify to `x`; without it, SymPy correctly refuses. Use `real=True`, `integer=True`, `nonnegative=True` as the mathematics demands.
- **Keep numbers exact.** Python's `1/3` is already a float before SymPy sees it. Write `sp.Rational(1, 3)` or `sp.S(1) / 3`; recover exact forms with `sp.nsimplify` when a float slipped in.
- **Simplify on purpose.** `simplify` is a heuristic that can be slow and returns forms you did not ask for. Prefer targeted functions: `expand`, `factor`, `cancel`, `together`, `apart`, `trigsimp`, `powsimp`, `logcombine` (needs assumptions).
- **Equality.** `==` tests structural identity. Test mathematical equality with `(a - b).equals(0)` or `sp.simplify(a - b) == 0`, plus a numeric spot check, because neither proves equality in every case. `sp.Eq(lhs, rhs)` builds an equation object.
- **Solving.** `solve` returns lists or dicts and can miss solutions; `solveset` returns sets over a declared domain (and a `ConditionSet` when it cannot decide); `linsolve` and `nonlinsolve` for systems; `nsolve` for a numeric root from a start point; `dsolve` for ODEs, checked with `checkodesol`. Substitute every solution back, and check domain conditions (division by zero, branch cuts).
- **Calculus.** `diff`, `integrate` (an unevaluated `Integral` or a `Piecewise` with conditions means read carefully), `limit`, `series(expr, x, 0, n).removeO()`.
- **Matrices.** `Matrix.jacobian`, `det`, `LUsolve`. Avoid symbolic inverses of anything beyond small matrices: expression swell makes them unusable.
- **Substitution.** `subs` substitutes mathematically (and may evaluate); `xreplace` replaces exact subtrees. Pass a dict for simultaneous substitution.

### From symbols to fast numbers

```python
import numpy as np
import sympy as sp

x, y, k = sp.symbols("x y k", real=True)
F = sp.Matrix([x**2 + k * sp.sin(y) - 1, sp.exp(x) * y - 2])
J = F.jacobian([x, y])

F_num = sp.lambdify((x, y, k), F, modules="numpy", cse=True)
J_num = sp.lambdify((x, y, k), J, modules="numpy", cse=True)

# Verify the generated Jacobian against central differences at a random point
rng = np.random.default_rng(0)
x0, y0, k0, h = *rng.uniform(0.2, 1.0, 2), 0.7, 1e-6
fd = np.column_stack([
    (np.ravel(F_num(x0 + h, y0, k0)) - np.ravel(F_num(x0 - h, y0, k0))) / (2 * h),
    (np.ravel(F_num(x0, y0 + h, k0)) - np.ravel(F_num(x0, y0 - h, k0))) / (2 * h),
])
assert np.allclose(np.array(J_num(x0, y0, k0), dtype=float), fd, rtol=1e-6, atol=1e-8)
```

- `lambdify(..., modules="scipy")` maps special functions to SciPy; `cse=True` (or `sp.cse`) removes repeated subexpressions.
- Code printers: `sp.ccode`, `sp.fcode`, `sp.pycode`, and `sympy.utilities.codegen` for whole routines; `autowrap` and `ufuncify` compile with a local compiler.
- `sp.latex(expr)` produces LaTeX for reports; render it and read it, since printed forms can hide assumptions.
- `sympy.physics.mechanics` (Kane's and Lagrange's methods) derives equations of motion for multibody systems; `sympy.physics.units` exists, but for numerical work with units `pint` or `astropy.units` are the better fit.

### Security

`sp.sympify(string)` and `parse_expr` evaluate Python code (they use `eval`). Never pass them text from users, web requests or files you did not write. Build expressions from parsed, validated tokens instead, or restrict the input grammar first.

### Verify every derivation

- Spot-check the symbolic result numerically at random points against finite differences, numerical integration (`mpmath.quad`) or the original definition.
- Differentiate an antiderivative back; substitute solutions into the equations; compare a lambdified function with `expr.evalf(30, subs=...)` at high precision.
- Keep the derivation as a script or notebook in the project, with these checks as asserts.

## Part 2: MATLAB, Octave and translation to Python

### Options

| Option | Use when | Notes |
|---|---|---|
| MATLAB | The code depends on toolboxes or Simulink | Commercial license; the MATLAB Engine API for Python needs a licensed local MATLAB |
| GNU Octave | Running core MATLAB-language scripts without a license | GPL; mostly compatible core language; toolbox equivalents (Octave packages) differ |
| NumPy and SciPy | Long-term maintenance, integration with Python tooling | Translation needed; verify against the original |
| Julia | Performance with MATLAB-like syntax | 1-based, column-major like MATLAB |

Run a script with Octave from the shell: `octave-cli --eval "run('analysis.m')"`. Read data files with `scipy.io.loadmat` (formats up to version 7.2) and with `h5py` for version 7.3, which is HDF5; arrays read through `h5py` appear transposed because MATLAB stores column-major. `scipy.io.savemat` writes files MATLAB can read.

### Translation pitfalls

| MATLAB | NumPy | Trap |
|---|---|---|
| `a(1)`, `a(end)` | `a[0]`, `a[-1]` | 1-based versus 0-based; `find` returns 1-based indices, `np.flatnonzero` 0-based |
| `a(2:5)` | `a[1:5]` | MATLAB ranges include the end, Python slices do not |
| `1:n` | `np.arange(1, n + 1)` | `linspace` includes both ends in both languages |
| `A * B`, `A .* B` | `A @ B`, `A * B` | `*` means different things |
| `A'`, `A.'` | `A.conj().T`, `A.T` | `'` conjugates complex data |
| `A \ b` | `np.linalg.solve`, `scipy.linalg.solve(A, b, assume_a="pos")`, `np.linalg.lstsq` for rectangular, `scipy.sparse.linalg.spsolve` | Backslash silently picks Cholesky, LU or least squares; choose explicitly |
| Row and column vectors | 1-D arrays have no orientation | Broadcasting surprises; use `x[:, None]` or `reshape(-1, 1)` deliberately |
| `reshape(A, m, n)` | `A.reshape(m, n, order="F")` | Column-major versus row-major |
| `mean(A)`, `sum(A)` | `A.mean(axis=0)`, `A.sum(axis=0)` | MATLAB reduces columns by default |
| `std(x)`, `var(x)` | `np.std(x, ddof=1)` | MATLAB normalizes by `N - 1`, NumPy by `N` |
| `max(x)` with NaN | `np.nanmax(x)` | MATLAB ignores NaN by default; `np.max` returns NaN |
| `[m, i] = max(x)` | `x.max()`, `x.argmax()` | Index base differs |
| `round(2.5)` is 3 | `np.round(2.5)` is 2.0 | Half away from zero versus half to even |
| `int8(200)` is 127 | Wraps or raises | MATLAB integer arithmetic saturates |
| `interp1(x, y, xi)` | `np.interp(xi, x, y)` | Argument order differs; MATLAB returns NaN outside the range, `np.interp` clamps to end values |
| `ode45(@f, tspan, y0)` | `solve_ivp(f, tspan, y0, method="RK45")` | Same `f(t, y)` order and default tolerances (`1e-3`, `1e-6`); `sol.y` has states in rows, MATLAB's `y` in columns |
| `ode15s` | `solve_ivp(method="BDF")` or `"Radau"` | Different implementations: compare at tight tolerances |
| `rng(42); rand(3)` | `np.random.default_rng(42).random((3, 3))` | Different generators: never expect identical random numbers |
| `filter(b, a, x)` | `scipy.signal.lfilter(b, a, x)` | `filtfilt` exists under the same name |
| `ndgrid` | `np.meshgrid(..., indexing="ij")` | `meshgrid` defaults match (`"xy"`) |

### Verify a translation

1. Save inputs and outputs from the original (MATLAB or Octave) to a `.mat` file for a few representative cases, including edge cases (empty arrays, NaN, single elements).
2. Write a Python test that loads them and compares with `np.testing.assert_allclose` at a stated tolerance.
3. Expect bitwise differences from different BLAS libraries and summation orders; differences beyond roundoff are translation bugs until shown otherwise.

## Checks (done when)

- [ ] Symbols carry the assumptions the derivation relies on; no stray floats in exact work.
- [ ] Every symbolic result was checked numerically at random points; generated code was compared with the symbolic expression.
- [ ] No `sympify` or `parse_expr` on untrusted text.
- [ ] Translated MATLAB code passes tests against saved outputs of the original, with indexing, orientation, normalization and NaN behavior checked.

## Anti-patterns

- Calling `simplify` on everything and trusting whatever comes back.
- Symbolic matrix inverses of large systems.
- Translating `A \ b` to `inv(A) @ b`.
- Assuming `np.std` matches MATLAB's `std`.
