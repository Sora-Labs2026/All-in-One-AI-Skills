# Quantum computing: Qiskit, Cirq and PennyLane

Read this when building, simulating, compiling or running quantum circuits; writing variational algorithms; estimating expectation values; modeling noise; or moving work between frameworks or onto hardware. Continuous-time open-system dynamics (master equations, cavities, spins) are in `quantum-dynamics-qutip.md`.

## 1. Pick a framework

| Framework | Strengths | Typical use |
|---|---|---|
| Qiskit | Mature transpiler, primitives (Sampler, Estimator), IBM hardware access, large ecosystem | Hardware-oriented algorithm work, compilation studies |
| Cirq | Explicit moments and device constraints, flexible noise modeling, parameter sweeps | NISQ algorithm research, device-aware circuits |
| PennyLane | Differentiable programming with JAX, PyTorch or autograd; variational algorithms; quantum chemistry helpers; plugins for many backends | Variational algorithms, quantum machine learning, chemistry Hamiltonians |

- Fast simulators: Qiskit Aer, qsim (`qsimcirq`), PennyLane Lightning; tensor-network simulators (for example quimb) for low-entanglement circuits beyond statevector size; NVIDIA cuQuantum for GPUs.
- Exchange circuits with OpenQASM (`qiskit.qasm2` and `qiskit.qasm3`, Cirq's QASM import and export); PennyLane can load Qiskit circuits through its Qiskit plugin.
- Error mitigation that works across frameworks: Mitiq (zero-noise extrapolation, probabilistic error cancellation, readout mitigation).

## 2. Ground rules

1. **Simulate first.** Develop and test on exact simulators, then on noisy simulators with device-calibrated noise, then on hardware.
2. **Hardware runs need the user's go-ahead.** They consume paid time or limited quota. State the circuits, shots and estimated cost or quota first.
3. **Credentials stay out of code and chat.** Use the provider's saved-account mechanism or an environment variable that the user sets (`../../agent-safety/GUIDE.md`).
4. **Record** framework and plugin versions, backend name, the calibration snapshot or date, transpiler settings and seed, shots, simulator seed and the exact circuits (as QASM).
5. **Memory limits are hard.** A statevector of `n` qubits in complex128 needs `16 * 2^n` bytes: 30 qubits is 16 GiB, 34 qubits is 256 GiB. A density matrix squares that: 15 qubits is already 16 GiB.
6. **Mind bit order.** Qiskit count strings are little-endian (qubit 0 is the rightmost character). Cirq measurement results follow the order of qubits in the measurement (the first is the most significant bit) and state vectors follow sorted qubit order. PennyLane treats wire 0 as the most significant bit in `probs`. When comparing frameworks, test a circuit that flips only qubit 0.
7. **Report shot noise.** A probability estimated from `N` shots has standard error `sqrt(p (1 - p) / N)`; an expectation value's error is its standard deviation over `sqrt(N)`. Choose shots from the precision needed.

## 3. Qiskit (SDK 1.x and 2.x)

Packages: `qiskit` (core), `qiskit-aer` (simulators), `qiskit-ibm-runtime` (IBM hardware and fake backends). Version history that breaks old examples:

- 1.0 (2024) removed `execute`, `qiskit.Aer` and `BasicAer`, and the in-tree `qiskit.algorithms` (now the separate `qiskit-algorithms` package). Results come from primitives.
- 2.0 (2025) removed the pulse module, `c_if` (use `if_test` control flow) and older backend interfaces. Check the installed version before reusing any example older than that.

```python
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler, StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp

bell = QuantumCircuit(2)
bell.h(0)
bell.cx(0, 1)

estimator = StatevectorEstimator()
evs = estimator.run([(bell, SparsePauliOp.from_list([("ZZ", 1.0), ("XX", 1.0)]))]).result()[0].data.evs
assert abs(float(evs) - 2.0) < 1e-12                      # exact for the Bell state

measured = bell.copy()
measured.measure_all()                                     # creates the classical register "meas"
counts = StatevectorSampler(seed=1234).run([measured], shots=4000).result()[0].data.meas.get_counts()
p00 = counts.get("00", 0) / 4000                           # expect 0.5 within about 3 * 0.0079
```

**Running against a device model.** Hardware accepts only circuits expressed in its native gates and connectivity (instruction set architecture circuits):

```python
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import SamplerV2
from qiskit_ibm_runtime.fake_provider import FakeManilaV2

backend = FakeManilaV2()                                    # calibrated noise model, runs locally
pm = generate_preset_pass_manager(optimization_level=2, backend=backend, seed_transpiler=7)
isa = pm.run(measured)
job = SamplerV2(mode=backend).run([isa], shots=4000)        # local testing mode with a fake backend
noisy_counts = job.result()[0].data.meas.get_counts()
```

- For the Estimator on hardware, map observables to the transpiled layout: `observable.apply_layout(isa.layout)`.
- The same code with a real backend from `QiskitRuntimeService` submits to hardware. Execution modes (single jobs, batches, sessions) and which plans allow them change; check IBM's current documentation, and get approval first.
- Runtime error-mitigation and suppression options (resilience levels, dynamical decoupling, twirling) trade accuracy against shots and time; report which were on.

## 4. Cirq (1.x)

```python
import cirq
import numpy as np
import sympy

q0, q1 = cirq.LineQubit.range(2)
theta = sympy.Symbol("theta")
circuit = cirq.Circuit(cirq.ry(theta).on(q0), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key="m"))

simulator = cirq.Simulator(seed=7)
sweep = cirq.Linspace(theta, start=0.0, stop=np.pi, length=5)
for result in simulator.run_sweep(circuit, params=sweep, repetitions=4000):
    angle = result.params.value_of(theta)
    p11 = result.histogram(key="m")[3] / 4000                # 3 is binary 11; q0 is the high bit
    assert abs(p11 - np.sin(angle / 2) ** 2) < 4 * 0.5 / np.sqrt(4000)
```

- `simulator.simulate(circuit_without_measurements).final_state_vector` gives amplitudes; `cirq.unitary(circuit)` gives the matrix for small circuits.
- Noise: `cirq.DensityMatrixSimulator(noise=cirq.depolarize(p=0.01))`, or channel operations (`cirq.amplitude_damp`, `cirq.bit_flip`) inserted explicitly; `with_noise` on circuits.
- Compilation: `cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset())`; routing onto device connectivity with `cirq.RouteCQC`; validate with the device's `validate_circuit`.
- Check that compilation preserved behavior: `cirq.testing.assert_circuits_with_terminal_measurements_are_equivalent` or `cirq.testing.assert_allclose_up_to_global_phase` on unitaries of small circuits.
- Hardware access goes through vendor packages (for example `cirq-google`, `cirq-ionq`, `cirq-aqt`, `cirq-pasqal`), each with its own access terms.

## 5. PennyLane (0.3x to 0.4x)

```python
import pennylane as qml
from pennylane import numpy as pnp

H = qml.Hamiltonian([1.0, 0.5], [qml.Z(0) @ qml.Z(1), qml.X(0)])
dev = qml.device("default.qubit", wires=2)                 # "lightning.qubit" for speed

@qml.qnode(dev, diff_method="backprop")
def energy(params):
    qml.RY(params[0], wires=0)
    qml.RY(params[1], wires=1)
    qml.CNOT(wires=[0, 1])
    qml.RY(params[2], wires=1)
    return qml.expval(H)

params = pnp.array([0.1, 0.2, 0.3], requires_grad=True)
opt = qml.AdamOptimizer(stepsize=0.1)
for _ in range(300):
    params = opt.step(energy, params)
gap = float(energy(params)) - float(min(qml.eigvals(H)))   # report it; a large gap means a weak ansatz or a local minimum
```

- **Gradients:** `backprop` for simulators (fast, memory-hungry), `adjoint` with Lightning devices (memory-light), `parameter-shift` for hardware (two circuit evaluations per parameter for standard gates), finite differences as a last resort. Check a gradient once against parameter-shift or finite differences.
- **Shots:** recent releases (2025) moved finite-shot configuration from the device to the QNode (`qml.set_shots`, or a `shots` argument); older code sets `shots=` on `qml.device`. Use what the installed version documents.
- **Interfaces:** autograd (with `pennylane.numpy`) by default; JAX (`jax.jit` around QNodes) or PyTorch for larger hybrid models. Machine-learning practice is in `../../ml-engineering/GUIDE.md`.
- **Quantum chemistry:** `qml.qchem.Molecule(symbols, coordinates)` takes coordinates in Bohr unless you pass `unit="angstrom"`; a geometry in angstrom read as Bohr gives a wrong molecule silently. Compare variational energies with exact diagonalization of the qubit Hamiltonian (small cases) and with classical references (PySCF FCI or CCSD(T)); chemical accuracy is about 1.6 millihartree (1 kcal/mol).
- **Trainability:** deep random ansatzes have vanishing gradients (barren plateaus). Prefer problem-inspired ansatzes, local cost functions and layer-wise initialization; check gradient variance at initialization.

## 6. Noise, mitigation and honest claims

- Noise models: depolarizing, amplitude and phase damping, readout error; device-calibrated models from fake backends or vendor data. Use the same noise model across compared methods.
- Mitigation: readout calibration, zero-noise extrapolation, probabilistic error cancellation (cost grows exponentially with circuit size), Pauli twirling, dynamical decoupling. Report raw and mitigated results side by side, with the overhead.
- Compare against the best classical method for the same instance, not only against a naive baseline. Avoid "quantum advantage" claims unless the comparison is rigorous and published.
- Report resource counts after transpilation (two-qubit gate count, depth), not the logical circuit's.

## Checks (done when)

- [ ] Every result was first reproduced on an exact simulator against an analytic expectation, within shot-noise error bars.
- [ ] Bit-order conventions were tested with a single-qubit flip when results cross frameworks or tools.
- [ ] Transpiled resource counts, seeds, versions, backend and calibration date are recorded.
- [ ] Hardware runs were approved by the user, with shots and cost stated; credentials never appeared in code or output.
- [ ] Variational results report the gap to exact or classical reference energies, and gradients were checked once.

## Anti-patterns

- Examples using `execute`, `qiskit.Aer` or `c_if` on a current Qiskit.
- Submitting untranspiled circuits to hardware.
- Comparing count dictionaries across frameworks without mapping bit order.
- Angstrom geometries passed as Bohr.
- Reporting mitigated values without raw values and overheads.
