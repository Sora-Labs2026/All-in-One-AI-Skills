# PyTorch: plain training loops and fixing failures

Read this when a PyTorch script crashes (shapes, devices, dtypes, autograd, CUDA, data loading), runs out of GPU memory, produces NaNs, runs slowly, or will not use the GPU; or when you write or review a training loop without Lightning. Lightning, multi-GPU strategies and general training practice are in `deep-learning-pytorch.md`; Hugging Face models in `transformers.md`.

**Working rules.** Make the smallest change that fixes the actual error; do not refactor or change the architecture to make an error go away. Reproduce with a tiny batch first, then the real configuration. Do not silence warnings. Stop and report after three targeted attempts that leave the same error, when the cause is the driver or hardware, or when memory runs out even at batch size 1. Installing drivers or CUDA toolkits is the user's decision.

## Check the environment first

```bash
python -c "import torch; print(torch.__version__, 'cuda', torch.version.cuda, 'available', torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_name(0))"     # only if available
nvidia-smi                                                           # driver version and the newest CUDA it supports
python -m torch.utils.collect_env                                    # full report for issues and bug reports
python -m pip list 2>/dev/null | grep -iE "^(torch|nvidia-)"
```

- `torch.version.cuda` is `None`: a CPU-only build is installed. Install the CUDA build the project's lock file names, using the index URL from the PyTorch installation selector. The wheels bundle the CUDA runtime, so no system CUDA toolkit is needed, but the driver must be new enough for that runtime.
- A CUDA toolkit (`nvcc`) matters only when compiling extensions; its major version must match `torch.version.cuda`.
- Two PyTorch installations (pip and conda, or two virtual environments) cause confusing imports; check `python -c "import torch; print(torch.__file__)"`.
- Apple silicon uses the `mps` device (`torch.backends.mps.is_available()`); unsupported operations can fall back to the CPU with `PYTORCH_ENABLE_MPS_FALLBACK=1`, slowly.

## Error messages and their usual causes

| Message (abridged) | Usual cause | Fix |
|---|---|---|
| `mat1 and mat2 shapes cannot be multiplied (32x512 and 256x10)` | `nn.Linear(in_features)` does not match the flattened size | Set `in_features` from a dummy forward pass, or use `nn.LazyLinear` |
| `Expected all tensors to be on the same device` | A tensor created in `forward` on the CPU; the batch not moved | `torch.zeros(..., device=x.device)`; constants as `register_buffer`; move the batch once per step |
| `expected scalar type Float but found Double` | NumPy float64 arrays became tensors | Convert in the dataset (`torch.as_tensor(a, dtype=torch.float32)`) |
| `CUDA out of memory` | Batch too large, evaluation with gradients on, a growing list of loss tensors | See "Memory" below |
| `element 0 of tensors does not require grad` | Loss computed from `.detach()`, `.item()`, NumPy or under `no_grad`; all parameters frozen | Keep the loss path in torch; check `requires_grad` on parameters |
| `modified by an inplace operation` | An in-place operation overwrote a tensor that backward needs | Make that operation out-of-place; `torch.autograd.set_detect_anomaly(True)` names it. Most in-place operations are fine |
| `Trying to backward through the graph a second time` | State carried across steps (RNN hidden state, a tensor computed once outside the loop) | `h = h.detach()` between steps; recompute per step. `retain_graph=True` only when two backward passes are intended |
| `stack expects each tensor to be equal size` | Variable-length samples | A `collate_fn` that pads, or bucketing by length |
| `index out of range in self` (embedding) | Token id at or above `num_embeddings`, or negative | Check vocabulary size and padding id |
| `device-side assert triggered` | Usually an invalid index or class labels outside `0..C-1` for cross-entropy | Rerun on CPU for a readable error, or with `CUDA_LAUNCH_BLOCKING=1`; restart the process afterwards, the CUDA context is unusable |
| `DataLoader worker ... killed by signal: Bus error` | Shared memory too small (containers default to 64 MB `/dev/shm`) | `--shm-size` or `--ipc=host` for the container, or fewer workers |
| `Can't pickle local object` or `Can't get attribute` with workers | `spawn` start method (macOS, Windows) needs importable objects | Define datasets and collate functions at module level; guard the entry point with `if __name__ == "__main__":` |
| `Missing key(s)` or `Unexpected key(s)` with `module.` or `_orig_mod.` prefixes | Saved from a DDP-wrapped or compiled model | Save `model.module.state_dict()` (or the uncompiled module); strip prefixes when loading old files |
| `Weights only load failed` | Since PyTorch 2.6 `torch.load` defaults to `weights_only=True`; the file holds other objects | Save plain state dicts; `weights_only=False` only for files you produced yourself |

## Shapes and dtypes

- Print `shape`, `dtype` and `device` at the boundary where the error occurs; `torchinfo.summary(model, input_size=...)` prints per-layer shapes.
- Assert shapes at important boundaries (`assert x.shape[-1] == self.d_model, x.shape`); a wrong shape that happens to broadcast fails silently.
- `view` needs contiguous memory; after `transpose` or `permute` use `reshape` or `.contiguous()`.

## A plain training loop that holds up

```python
use_amp = device.type == "cuda"
amp_dtype = torch.float16 if use_amp and not torch.cuda.is_bf16_supported() else torch.bfloat16
scaler = torch.amp.GradScaler("cuda", enabled=use_amp and amp_dtype == torch.float16)  # bf16 needs no scaling

model.train()
for step, (x, y) in enumerate(loader):
    x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
    with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=use_amp):
        loss = loss_fn(model(x), y) / accum_steps
    scaler.scale(loss).backward()
    if (step + 1) % accum_steps == 0:
        scaler.unscale_(optimizer)                                   # clip the real gradients
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        scheduler.step()                                             # per optimizer step, if the schedule is per step
    if step % log_every == 0:
        print(step, loss.item() * accum_steps)                       # .item() syncs the GPU: log sparingly

@torch.inference_mode()
def evaluate(model, loader):
    model.eval()
    total, n = 0.0, 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        total += loss_fn(model(x), y).item() * len(y)                # weight by batch size
        n += len(y)
    model.train()
    return total / n
```

- **Checkpoints for resuming** hold the model, optimizer, scheduler and scaler state dicts, the epoch and step, and the config. Write to a temporary file and rename. Reseed from `(seed, epoch)` on resume instead of pickling every random generator's state.
- **Inference artifacts** are separate: `model.state_dict()` (or `safetensors`) plus the code and config to rebuild the model.

## NaNs and infinities

1. Check the data: `torch.isfinite(x).all()` on a few batches, label ranges, division by zero in preprocessing.
2. Check the first loss: for cross-entropy over C balanced classes it should be near ln(C).
3. Lower the learning rate, add warmup, clip gradients.
4. float16 overflows above about 65,504: prefer bfloat16 on hardware that supports it, or keep the gradient scaler.
5. Guard `log`, `sqrt` and divisions with a small epsilon or `clamp`.
6. `torch.autograd.set_detect_anomaly(True)` names the operation that produced the NaN; it is slow, so enable it only while debugging.

## Memory

- Evaluation under `torch.inference_mode()`; accumulate `loss.item()`, not loss tensors (a list of tensors keeps every graph alive).
- Smaller batches with gradient accumulation; mixed precision; activation checkpointing (`torch.utils.checkpoint.checkpoint(block, x, use_reentrant=False)`) on large blocks.
- `torch.cuda.max_memory_allocated()` and `torch.cuda.memory_summary()` show what is used; PyTorch's memory snapshot tooling shows which allocations hold memory over time.
- `torch.cuda.empty_cache()` returns cached, unused blocks to the driver. It does not free memory held by live tensors and does not fix an out-of-memory error.

## Reproducibility

```python
import os, random, numpy as np, torch

def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)   # also seeds every CUDA device

def seed_worker(worker_id):
    s = torch.initial_seed() % 2**32
    np.random.seed(s); random.seed(s)

g = torch.Generator().manual_seed(1234)
loader = torch.utils.data.DataLoader(ds, batch_size=64, shuffle=True, num_workers=4,
                                     worker_init_fn=seed_worker, generator=g)
# For bitwise-repeatable debugging runs only (slower, and some operations will raise):
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
```

Results still differ across GPU models, driver versions and device counts; compare runs by mean and spread over several seeds.

## Speed

- Profile before tuning: `torch.profiler.profile(activities=[...CPU, ...CUDA])` around a few steps, sorted by CUDA time. Low GPU utilization usually means the input pipeline is the bottleneck: more `num_workers`, `pin_memory=True`, `persistent_workers=True`, decoding done once ahead of time.
- Remove hidden synchronizations from the hot loop: `.item()`, `.cpu()`, `print` of tensors, Python-side conditions on tensor values.
- On Ampere and newer GPUs, `torch.set_float32_matmul_precision("high")` allows TF32 matrix multiplication for float32 models; check the accuracy effect.
- `torch.compile(model)`: the first steps compile and are slow; varying input shapes trigger recompiles (mark dynamic dimensions or pad to buckets); `TORCH_LOGS="graph_breaks"` lists where compilation falls back to Python. Keep it only if measured faster (`benchmarking-methodology.md`).

## Report

```text
Fixed:   train.py:88  RuntimeError: mat1 and mat2 shapes cannot be multiplied (64x2048 and 512x10)
Cause:   classifier in_features hard-coded for 32x32 inputs; data now 64x64
Change:  in_features computed from a dummy forward in __init__
Proof:   python train.py --max-steps 5 --batch-size 2 (passes); full config 1 epoch: loss 2.30 -> 1.71
Left:    none
```

## Checks (done when)

- [ ] Environment facts (versions, CUDA availability, device) recorded before changes.
- [ ] The fix addresses the cause named in the table or found by inspection, and is minimal.
- [ ] A tiny run and a real-configuration run both pass; loss behaves sensibly.
- [ ] Evaluation runs in eval mode without gradients; checkpoints restore training state.
- [ ] Anything not fixed (driver, hardware, architecture change) is reported with the evidence.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `retain_graph=True` to silence a double-backward error | Detach carried state |
| `empty_cache()` as an out-of-memory fix | Reduce what is held: batch, precision, no-grad evaluation |
| GradScaler with bfloat16 | Not needed; use it for float16 only |
| Clipping before `unscale_` under AMP | `unscale_`, then clip |
| Debugging device-side asserts on the GPU | Reproduce on CPU or with `CUDA_LAUNCH_BLOCKING=1` |
| `torch.load` of downloaded checkpoints with `weights_only=False` | Trusted files only; prefer `safetensors` |
