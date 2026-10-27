# Deep learning with PyTorch and Lightning

Read this when you train or debug neural networks in PyTorch, organize training code with Lightning, scale to several GPUs, or need reproducible, comparable runs. Hugging Face models are in `transformers.md`; LLM fine-tuning in `fine-tuning.md`.

## When Lightning, when plain PyTorch

- **Plain PyTorch** for small experiments, unusual training loops (GAN-style alternation, RL, meta-learning) or when the project already has its own loop.
- **Lightning** (`lightning` package, 2.x) when you want standard loops, checkpointing, logging, mixed precision and multi-GPU strategies without writing them, and a clean split between model code and engineering.
- **Lightning Fabric** when you want to keep your own loop but get device placement, precision and distributed launch.
- Hugging Face `Trainer` or `accelerate` when the model comes from the Hugging Face ecosystem.

Package names: since 2.0 the unified package is `lightning` (`import lightning as L`, `lightning.pytorch`); the standalone `pytorch_lightning` package still exists. Do not mix imports from both in one project, or callbacks and loggers will not be recognized.

```bash
python -m pip install torch lightning torchmetrics   # pick the torch build for your CUDA version from pytorch.org
python -c "import torch, lightning; print(torch.__version__, lightning.__version__, torch.cuda.is_available())"
```

## The LightningModule and DataModule

```python
import lightning as L
import torch
import torch.nn.functional as F
import torchmetrics

class Classifier(L.LightningModule):
    def __init__(self, backbone: torch.nn.Module, num_classes: int, lr: float = 3e-4, weight_decay: float = 0.01):
        super().__init__()
        self.save_hyperparameters(ignore=["backbone"])      # stored in checkpoints; backbone saved as weights
        self.backbone = backbone
        self.val_acc = torchmetrics.classification.MulticlassAccuracy(num_classes=num_classes)

    def forward(self, x):
        return self.backbone(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        loss = F.cross_entropy(self(x), y)
        self.log("train/loss", loss, on_step=True, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        self.log("val/loss", F.cross_entropy(logits, y), on_epoch=True, sync_dist=True)
        self.val_acc.update(logits, y)
        self.log("val/acc", self.val_acc, on_epoch=True)    # torchmetrics syncs across devices itself

    def configure_optimizers(self):
        opt = torch.optim.AdamW(self.parameters(), lr=self.hparams.lr, weight_decay=self.hparams.weight_decay)
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=self.hparams.lr,
                                                    total_steps=self.trainer.estimated_stepping_batches)
        return {"optimizer": opt, "lr_scheduler": {"scheduler": sched, "interval": "step"}}
```

- A `LightningDataModule` owns downloading, splitting and the three dataloaders. Split in `setup()` with a fixed seed, and never let the test split influence anything before `trainer.test`.
- Never call `.cuda()` or `.to("cuda")` inside the module; use `self.device` or let Lightning place tensors. Register constant tensors with `self.register_buffer` so they move with the model.
- Use torchmetrics objects for metrics; they accumulate correctly across batches and devices. Averaging per-batch accuracies is wrong when batch sizes differ.
- In 2.x the `*_epoch_end(outputs)` hooks are gone; use `on_validation_epoch_end` and keep any per-step state yourself.

## The Trainer

```python
from lightning.pytorch.callbacks import ModelCheckpoint, EarlyStopping, LearningRateMonitor

L.seed_everything(42, workers=True)
trainer = L.Trainer(
    max_epochs=50, accelerator="auto", devices="auto",
    precision="bf16-mixed",                 # "16-mixed" on GPUs without bf16 support; "32-true" to debug
    gradient_clip_val=1.0, accumulate_grad_batches=1,
    callbacks=[ModelCheckpoint(monitor="val/loss", mode="min", save_top_k=2, save_last=True),
               EarlyStopping(monitor="val/loss", mode="min", patience=5),
               LearningRateMonitor(logging_interval="step")],
    deterministic=False, log_every_n_steps=20)
trainer.fit(model, datamodule=dm)
trainer.test(model, datamodule=dm, ckpt_path="best")      # once, at the very end
```

- Checkpoint and early-stop on a validation metric, never on test.
- `ckpt_path="best"` evaluates the best checkpoint, not the last weights.
- Resume with `trainer.fit(..., ckpt_path="last")`; it restores optimizer, scheduler and loop state.

## Debugging order

Work through these before long runs; each catches a different class of bug.
1. `Trainer(fast_dev_run=True)`: one batch of each loop, catches crashes and shape errors.
2. Inspect one batch by eye: inputs in the expected range, labels aligned with inputs, augmentations sensible.
3. `Trainer(overfit_batches=1)` (or 10): the loss must go to near zero. If it cannot memorize one batch, there is a bug (labels misaligned, wrong loss, frozen weights, learning rate far off).
4. Check the initial loss: for C balanced classes with cross-entropy it should be close to ln(C).
5. `limit_train_batches=0.1` for quick hyperparameter sanity runs.
6. NaNs: switch to `precision="32-true"`, add `detect_anomaly=True` temporarily, lower the learning rate, clip gradients, check for log of zero or division by small numbers.

## Reproducibility and comparing runs

- `L.seed_everything(seed, workers=True)` seeds Python, NumPy, torch and dataloader workers.
- `Trainer(deterministic=True)` forces deterministic algorithms; some operations then error or slow down. Use it for debugging differences, not necessarily for every run.
- Bitwise reproducibility across GPU models, driver versions or numbers of devices is not guaranteed. Compare runs by mean and spread over 3 to 5 seeds.
- Log the git commit, config, library versions and data version with every run (see `mlops.md`).

## Scaling up

| Situation | Strategy |
|---|---|
| Model fits on one GPU, want speed | `strategy="ddp"`, `devices=N`; global batch = per-device batch x devices x accumulation |
| Model does not fit on one GPU | `strategy="fsdp"` (shards parameters, gradients, optimizer state), or DeepSpeed ZeRO |
| Memory-bound activations | Activation checkpointing; mixed precision; smaller micro-batches with gradient accumulation |
| Input pipeline is the bottleneck (GPU utilization low) | More `num_workers`, `pin_memory=True`, `persistent_workers=True`, faster decoding, pre-processed shards |

- When the global batch grows, revisit the learning rate and warmup; do not assume the single-GPU setting transfers.
- `sync_dist=True` on logged values that must be averaged across processes; it adds communication, so skip it for per-step training logs.
- `torch.compile(model)` (PyTorch 2.x) often speeds up training; compile time is significant, and some dynamic code paths break it. Measure before and after.
- Run multi-node jobs through the cluster's scheduler (Slurm or Kubernetes); see `../../scientific-computing/GUIDE.md` and `../../cloud-infrastructure/GUIDE.md`. GPU time costs money: estimate it and get approval before launching large jobs.

## Training practices that hold up

- AdamW with weight decay, a warmup, then cosine or one-cycle decay is a robust default. Find a learning rate with a short range test (Lightning's `Tuner(trainer).lr_find`), then confirm on validation.
- Early stopping with patience, plus keeping the best checkpoint, is the cheapest regularizer.
- Transfer learning first: a pretrained backbone fine-tuned on your data beats training from scratch on small and medium datasets. Freeze the backbone for a few epochs, then unfreeze with a lower learning rate.
- Data augmentation belongs to the training set only; validation and test use deterministic preprocessing.
- Class imbalance: weighted loss or balanced sampling, evaluated with the metrics in `evaluation-and-leakage.md`.

## Serving and export

- Save the inference artifact separately from training checkpoints: `torch.save(model.state_dict(), ...)` plus the code and config to rebuild it, or `torch.export` / ONNX / TorchScript where the serving stack needs it. Compare outputs of the exported model with the original on a sample.
- `torch.load` on untrusted checkpoints can execute code; PyTorch 2.6 made `weights_only=True` the default. Load only trusted files and prefer the `safetensors` format for weights.
- Set `model.eval()` and use `torch.inference_mode()` in serving code.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Evaluation in train mode (dropout and batch-norm updates on) | `model.eval()`; Lightning does this in validation and test loops |
| Metrics averaged per batch | torchmetrics or sample-weighted aggregation |
| Validation data augmented or normalized with its own statistics | Training-set statistics; deterministic validation transforms |
| `num_workers=0` and a starving GPU | Raise workers; profile the dataloader |
| Learning rate copied across batch sizes or GPU counts | Re-tune or scale with warmup |
| Checkpoint selection by test score | Validation metric only |
| One seed reported | 3 to 5 seeds, mean and spread |

## Done when

- [ ] `fast_dev_run` and an overfit-one-batch check passed.
- [ ] The best checkpoint was chosen on validation; test was run once.
- [ ] Results are reported over several seeds with the baseline and versions recorded.
- [ ] The exported or saved model reproduces the in-memory predictions on a sample.
