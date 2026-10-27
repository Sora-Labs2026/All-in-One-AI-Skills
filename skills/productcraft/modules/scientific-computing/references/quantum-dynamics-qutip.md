# Quantum dynamics with QuTiP

Read this when simulating the time evolution of quantum systems in continuous time: closed dynamics with the Schrodinger equation, open systems with Lindblad master equations, quantum trajectories, steady states, correlation functions and spectra, or periodically driven systems. Gate-level circuits belong in `quantum-computing.md`.

## When it fits

- Cavities, spins, qubits with drives and decoherence, optomechanics, quantum optics and small many-body models.
- Hilbert spaces up to roughly 10^4 to 10^5 states for pure-state (sparse) evolution. Density matrices scale with the square of the dimension, so master equations reach their limit much sooner; quantum trajectories (`mcsolve`) trade that memory for many runs.
- Larger many-body problems need other tools (tensor networks, for example).

## Versions

QuTiP 5 (2024) changed the API in ways that break older examples:

- Solver options are a plain dictionary (`options={"atol": 1e-10, "nsteps": 10000}`); the `Options` class is gone.
- Data layers let operators be dense or sparse (`Qobj.to("dense")`, `"csr"`, `"dia"`).
- Time-dependent operators are `QobjEvo` objects; list format (`[H0, [H1, coeff]]`) still works.
- Solver classes (`SESolver`, `MESolver`, `MCSolver`) sit beside the functions; options such as `"store_states"` and `"progress_bar"` moved into the options dictionary.
- Circuit and control features live in separate packages (`qutip-qip`, `qutip-qoc` and others).

Check `qutip.__version__` and use that version's documentation.

## Building a model

- States and operators: `basis(N, n)`, `fock_dm`, `coherent(N, alpha)`, `destroy(N)`, `qeye`, `sigmax()`, `sigmaz()`; composite systems with `tensor(a, b)` (the order of factors fixes the order of subsystems everywhere after); `ptrace` for reduced states; `expect(op, state)`.
- **Units:** set hbar to 1 and pick one time unit. Frequencies then must be angular frequencies in inverse time units: a 5 GHz qubit with time in nanoseconds has `omega = 2 * pi * 5` rad/ns. Mixing GHz and rad/ns is the most common silent error.
- **Truncation:** a Fock cutoff `N` must exceed every significantly populated level. Increase `N` until the observables of interest change by less than the tolerance, and check that the top level's population (`expect(fock_dm(N, N - 1), rho)`) stays negligible over the whole run.
- **Collapse operators** carry rates under a square root: decay at rate `gamma` is `sqrt(gamma) * a`; at thermal occupation `n_th`, use `sqrt(gamma * (n_th + 1)) * a` and `sqrt(gamma * n_th) * a.dag()`; pure dephasing at rate `gamma_phi` is commonly `sqrt(gamma_phi / 2) * sigmaz()` (conventions differ by a factor of 2: state the one you use).

## Solvers

| Need | Function |
|---|---|
| Closed system, pure state | `sesolve` |
| Open system, Lindblad (Markovian) | `mesolve` |
| Open system via quantum trajectories | `mcsolve` (set the number of trajectories and seeds) |
| Weak coupling to a structured bath | `brmesolve` (Bloch-Redfield) |
| Steady state | `steadystate` (several methods; check the residual) |
| Periodic driving | Floquet solvers |
| Strong coupling, non-Markovian baths | Hierarchical equations of motion (HEOM) |

- **Time dependence:** `H = [H0, [H1, coeff]]`, where `coeff` is a function `coeff(t, args)`, a string expression or an array sampled on the time grid. String and array coefficients avoid Python callbacks in the inner loop.
- **Outputs:** pass `e_ops` to get expectation values in `result.expect`; states are kept only when needed (`options={"store_states": True}`), which keeps memory under control.
- **Tolerances:** tighten `atol`, `rtol` and raise `nsteps` for long or fast-oscillating evolutions; verify by halving the tolerances and comparing.
- **Rotating frames:** moving to a frame rotating with the drive and dropping fast terms (rotating-wave approximation) speeds runs enormously, but it is a physical approximation; check it on a short window against the full model when drive strength is not much smaller than the frequencies involved.
- **Trajectories:** statistical error falls as `1/sqrt(ntraj)`; parallelize with `options={"map": "parallel"}`; record seeds.

## Verify against what is known

```python
import numpy as np
import qutip as qt

N, gamma, n0 = 15, 0.2, 3                  # Fock cutoff, decay rate (per time unit), initial photons
a = qt.destroy(N)
H = 1.0 * a.dag() * a                      # hbar = 1, omega = 1 rad per time unit
times = np.linspace(0.0, 20.0, 201)
result = qt.mesolve(H, qt.fock_dm(N, n0), times, c_ops=[np.sqrt(gamma) * a],
                    e_ops=[a.dag() * a], options={"atol": 1e-10, "rtol": 1e-8})
n_t = result.expect[0]
assert np.max(np.abs(n_t - n0 * np.exp(-gamma * times))) < 1e-6   # zero-temperature decay law
```

Other analytic anchors:

- Rabi oscillation with Rabi frequency `Omega` and detuning `Delta`: excited population `(Omega^2 / W^2) * sin^2(W t / 2)` with `W = sqrt(Omega^2 + Delta^2)`.
- Spontaneous emission of a two-level system: excited population `exp(-gamma t)`.
- A thermally damped oscillator relaxes to mean occupation `n_th`.
- For a small system, the mean of `mcsolve` trajectories converges to the `mesolve` result within statistical error.

Physical consistency checks on any density matrix: trace 1, Hermitian, eigenvalues not below about minus the tolerance, purity at most 1.

## Visualization

`qt.Bloch()` for qubit trajectories, `qt.wigner(rho, xvec, yvec)` and `qt.plot_wigner` for phase-space pictures, `qt.plot_fock_distribution` for occupation numbers. Plot from saved results; matplotlib is required.

## Checks (done when)

- [ ] Units chosen and stated; frequencies are angular and consistent with the time unit.
- [ ] Truncation converged (observables stable with larger cutoff; top-level population negligible).
- [ ] Collapse operators carry the square roots of rates, with conventions stated.
- [ ] At least one analytic or limiting case reproduced; tolerances halved without changing results.
- [ ] Rotating-wave or other approximations checked against the full model on a short window.

## Anti-patterns

- QuTiP 4 `Options` objects in QuTiP 5 code, or the reverse.
- Frequencies in GHz with time in nanoseconds, missing the factor `2 * pi`.
- Storing every state of a long run when only expectation values are needed.
- Quoting a trajectory average without its statistical error.
