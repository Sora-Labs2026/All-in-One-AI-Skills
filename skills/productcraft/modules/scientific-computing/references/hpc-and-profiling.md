# HPC jobs, resources and performance

Read this before heavy computation: checking what the machine or allocation actually provides, estimating memory and time, writing Slurm job scripts (MPI, threads, GPUs, arrays, checkpoint signals), reading job accounting, running scaling studies, and profiling scientific code. The general measure-change-remeasure loop lives in `../../engineering-practices/references/performance.md`; this file adds what is specific to numerical and parallel work.

## 1. Check resources before heavy compute

```bash
python3 <productcraft>/modules/scientific-computing/scripts/resource_check.py
python3 <productcraft>/modules/scientific-computing/scripts/resource_check.py --json \
  --need-cores 8 --need-mem-gb 32 --need-disk-gb 200 --path /scratch/$USER/run01
```

It reports usable cores after CPU affinity, container quotas and a Slurm allocation; usable memory after container and Slurm limits; free disk at a path; GPU management tools on PATH (looked up, never executed); thread variables that would oversubscribe the cores; and whether a scheduler client is present outside a job, which usually means a login node. It reads `/proc`, `/sys`, the environment and PATH, runs no other program and changes nothing. Exit code 1 means a `--need-*` requirement is not met.

Read the result with judgment:

- `os.cpu_count()` reports the host's logical CPUs, not what a container or job may use. Size worker pools from the usable count.
- A GPU tool on PATH does not prove a working GPU. Confirm with the framework that will use it, as a deliberate step.
- On a login node, do only light work (editing, compiling, short tests). Submit everything heavy through the scheduler.
- Submitting jobs spends the user's allocation, and cloud instances cost money: state the request (nodes, hours, GPUs) and get a go-ahead first. Never cancel or modify jobs you did not submit.

## 2. Estimate before you ask for resources

| Quantity | Estimate |
|---|---|
| Field memory | points times fields times bytes; a 1024^3 grid of float64 is 8 GiB per field |
| Dense matrix | `8 n^2` bytes; `n = 50,000` is 20 GB |
| Sparse matrix (CSR) | `nnz * (8 + 4)` plus `(n + 1) * 4` bytes with 32-bit indices (64-bit indices add 4 per entry) |
| Sparse direct factorization | Fill-in can reach many times `nnz`, especially in 3D; measure on a smaller problem and extrapolate |
| Time | Time per step from a short pilot (after warm-up) times the number of steps, plus I/O; add a margin of 20 to 50% |
| Disk | Output size per snapshot times snapshots, plus checkpoints |

Leave headroom: the operating system, MPI buffers and library workspaces need memory too, and a container or job that crosses its memory limit is killed without a Python traceback.

## 3. Slurm job scripts

```bash
#!/bin/bash
#SBATCH --job-name=cavity-re1000
#SBATCH --account=<project>            # site-specific; ask the user
#SBATCH --partition=<partition>        # check `sinfo` and the site documentation
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=32           # MPI ranks per node
#SBATCH --cpus-per-task=4              # OpenMP threads per rank
#SBATCH --mem=180G                     # per node; or --mem-per-cpu, never both
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --signal=B:USR1@300            # USR1 to this script 5 minutes before the time limit

module purge
module load gcc/13 openmpi/4.1         # module names are site-specific: `module avail`
set -euo pipefail                      # after module loads: some module init scripts use unset variables

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_PLACES=cores OMP_PROC_BIND=close
cd "${SLURM_SUBMIT_DIR}"

srun --cpus-per-task="${SLURM_CPUS_PER_TASK}" ./solver --config config.yaml &
solver_pid=$!
trap 'echo "time limit near: asking the solver to checkpoint"; kill -USR1 "${solver_pid}"' USR1
status=0
wait "${solver_pid}" || status=$?
while kill -0 "${solver_pid}" 2>/dev/null; do   # a trapped signal interrupts wait; keep waiting
  status=0
  wait "${solver_pid}" || status=$?
done
exit "${status}"
```

- **Layout:** ranks per node times CPUs per task must not exceed the cores per node. Hybrid MPI plus OpenMP needs `OMP_NUM_THREADS` equal to `--cpus-per-task`.
- **Pass `--cpus-per-task` to `srun` explicitly.** Slurm 22.05 stopped `srun` from inheriting it from the batch allocation; passing it explicitly behaves the same on every version.
- **Launcher:** prefer `srun` (or what the site documents) over a bare `mpirun`, so placement and accounting follow the allocation.
- **GPUs:** `--gpus-per-node=4` (or the older `--gres=gpu:4`), usually one rank per GPU; check `CUDA_VISIBLE_DEVICES` inside the job. GPU binding options are site-specific.
- **Wall time:** shorter, accurate requests start sooner (backfill scheduling). Use the pilot estimate plus margin, and checkpoint (`time-integration-and-stability.md`).
- **Checkpoint signal:** with `--signal=B:USR1@300` the batch shell receives `USR1` five minutes before the limit; the trap forwards it to the solver, which must catch it, write a checkpoint and exit. At the limit Slurm sends `SIGTERM` and, after a short grace period, `SIGKILL`.
- **Check before submitting:** `sbatch --test-only job.sh` validates the script and estimates a start time without submitting. Create the `logs/` directory first: Slurm does not create output directories, and the job fails without a log. Run a short job on a debug partition before a large one.

### Arrays and dependencies

```bash
#SBATCH --array=0-199%20               # 200 tasks, at most 20 at once
#SBATCH --output=logs/%x-%A_%a.out
row=$(( SLURM_ARRAY_TASK_ID + 2 ))     # skip the CSV header; rows are 1-based in sed
config=$(sed -n "${row}p" manifest.csv | cut -d, -f2)
srun ./solver --config "${config}"
```

- Map task IDs to rows of the campaign manifest (`parameter-studies-and-campaigns.md`), never to parameter values computed in shell arithmetic.
- Bundle runs shorter than a few minutes into one task; schedulers and file systems suffer under thousands of tiny jobs.
- Chain steps with `sbatch --dependency=afterok:<jobid> postprocess.sh`.

### After the job

```bash
sacct -j <jobid> --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,TotalCPU,MaxRSS,ReqMem
seff <jobid>                           # if the site installed it: CPU and memory efficiency
```

CPU efficiency is `TotalCPU / (Elapsed * AllocCPUS)`. Low efficiency means idle cores (wrong layout, serial bottleneck, I/O waits); `MaxRSS` far below the request means the next job can ask for less. Right-size requests from these numbers, not from guesses.

### Other schedulers and storage

- PBS Pro and OpenPBS use `#PBS -l select=2:ncpus=64:mpiprocs=32` and `qsub`; LSF uses `#BSUB` and `bsub`. Concepts map one to one; flags do not, so read the site documentation.
- Cloud batch services and Kubernetes jobs follow `../../cloud-infrastructure/GUIDE.md`: plan and cost first, nothing launched without permission.
- Write large outputs to scratch file systems, copy results you keep to project storage, and avoid millions of small files on parallel file systems (aggregate into HDF5 or Zarr). Scratch is often purged on a schedule.

## 4. Parallel scaling

- **Strong scaling** (fixed problem): speedup `S(p) = T(1) / T(p)`, efficiency `S(p) / p`. **Weak scaling** (work per process fixed): efficiency `T(1) / T(p)`.
- Amdahl's law bounds strong scaling: with parallel fraction `f`, `S(p) <= 1 / ((1 - f) + f / p)`. A 5% serial part caps the speedup at 20.
- Run a scaling study before requesting a large allocation: for example 1, 2, 4, 8 and 16 nodes, repeated, with startup and I/O timed separately. Choose the largest size whose efficiency the user accepts (0.7 is a common choice, not a law) and report the curve.
- **Oversubscription** is the most common performance bug in Python science: `multiprocessing`, `joblib` or Dask workers times BLAS or OpenMP threads per worker exceeding the cores. Set `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS` (often to 1 with many processes) or use `threadpoolctl`.
- Pin processes and threads (`srun --cpu-bind=cores`, `OMP_PROC_BIND`) on multi-socket nodes; memory bandwidth is per socket.

## 5. Profiling scientific code

| Layer | Tools |
|---|---|
| Python | `cProfile` with `pstats` or snakeviz; `py-spy` (sampling; `py-spy record`, `py-spy dump` for a stuck process, attaching may need extra privileges, so ask); `line_profiler` for one hot function; Scalene for CPU, memory and GPU together; `tracemalloc` and memray for memory |
| Compiled CPU code | `perf`, gprof, Intel VTune, Valgrind callgrind and cachegrind, compiler vectorization reports (`-fopt-info-vec`, `-qopt-report`) |
| MPI | mpiP, Score-P with Scalasca, TAU, HPCToolkit; look for load imbalance and time in collectives |
| GPU | Nsight Systems for the timeline, then Nsight Compute for single kernels; `rocprof` on AMD; deep-learning profilers per `../../ml-engineering/GUIDE.md` |

**NumPy and Python idioms that matter:**

- Element-wise Python loops over arrays: vectorize, or compile the loop with Numba (`@njit(cache=True)`); exclude the first, compiling call from timings.
- Chains of temporaries in large expressions: use `out=` arguments, in-place operations, or `numexpr`.
- Hidden copies from fancy indexing and non-contiguous slices: check `arr.flags["C_CONTIGUOUS"]`; use `np.ascontiguousarray` once rather than in a loop.
- Precision: float32 halves memory traffic; use it only after checking accuracy.
- The BLAS in use decides dense linear algebra speed: `np.show_config()`.

**Timing hygiene.** Warm up, repeat, use `time.perf_counter`, report the median and spread, and run on the same node type. GPU work is asynchronous: synchronize before reading a timer (`torch.cuda.synchronize()`, `cupy.cuda.Device().synchronize()`, JAX `block_until_ready()`), or the timing measures only the launch.

**Roofline thinking.** Arithmetic intensity (flops per byte moved) decides the ceiling. Stencils and sparse matrix-vector products move a lot of data per flop and are memory-bound; extra flops are nearly free there, while blocking, fusion and fewer passes over memory pay. Dense matrix multiplication is compute-bound.

**I/O** often dominates at scale. Profile it separately; write less often, in fewer larger files, with parallel HDF5 or a format designed for it, and compress where the data allow.

## Checks (done when)

- [ ] `../scripts/resource_check.py` ran (or the equivalent facts were gathered) and the plan fits the usable cores, memory and disk.
- [ ] Memory, time and disk were estimated from a pilot run, not guessed.
- [ ] The job script's layout matches the hardware, thread variables match the CPUs per task, and `sbatch --test-only` or a debug-partition run passed.
- [ ] The user approved allocation use; the request size is justified by a scaling study or a pilot.
- [ ] After the run, `sacct` or `seff` numbers were read and the next request right-sized.
- [ ] Performance claims come with baseline and result from the same method, per the general performance loop.

## Anti-patterns

- Heavy computation on a login node.
- `--mem` and `--mem-per-cpu` together, or thread counts that exceed the CPUs per task.
- Thousands of seconds-long jobs instead of bundled tasks.
- Timing a GPU kernel without synchronizing.
- Worker pools sized from `os.cpu_count()` inside a container or job.
- Asking for 100 nodes before measuring efficiency on 4.
