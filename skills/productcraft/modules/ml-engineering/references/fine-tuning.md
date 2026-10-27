# Fine-tuning language models: LoRA, QLoRA and full fine-tuning

Read this when someone wants to adapt a pretrained language model to a task, style or domain: supervised fine-tuning (SFT), preference tuning (DPO and relatives), parameter-efficient methods (LoRA, QLoRA), or a provider's hosted fine-tuning. Loading and inference basics are in `transformers.md`.

## First decide whether to fine-tune

Fine-tuning is the most expensive way to change model behavior and the hardest to undo. Go down this list and stop at the first step that meets the target on the evaluation set:

1. **Better prompt and examples** (`prompt-design.md`), measured on an evaluation set.
2. **Retrieval** when the gap is missing or changing knowledge (`rag-systems.md`). Fine-tuning is a poor way to add facts: they are hard to update, hard to cite and prone to confabulation.
3. **A smaller fine-tuned model** when a large model already does the task well but is too slow or costly: distill its outputs into a smaller model.
4. **Fine-tuning** when you need a consistent format or style, a narrow skill the prompt cannot reach, lower latency, or behavior on data the base model never saw (internal codes, rare languages).

Before training, have: an evaluation set with a frozen test split, the base model's score on it, and the target score that justifies the cost.

## Pick the method

| Method | What trains | Memory (rough, 7B to 8B model) | When |
|---|---|---|---|
| Full fine-tuning | All weights | About 16 bytes per parameter with Adam in mixed precision (weights, gradients, fp32 master copy and two moments), over 100 GB before activations: several 80 GB GPUs with sharding | Large data, maximum quality, small models, or continued pretraining |
| LoRA | Low-rank adapters on chosen layers (well under 1% of parameters) | bf16 weights (about 16 GB) plus activations: one 24 to 48 GB GPU | The default for most task and style adaptation |
| QLoRA | LoRA on a 4-bit quantized frozen base | About 5 to 6 GB for weights: fits 24 GB GPUs comfortably | Memory-constrained hardware; small quality cost to measure |
| DoRA, rsLoRA and other variants | Variations of the adapter parameterization | Similar to LoRA | Try only after a LoRA baseline, and keep them only if the evaluation improves |
| Hosted fine-tuning API | Provider-managed | None locally | No GPUs; check data retention terms, model availability and export options first |

Memory also depends on sequence length and batch size; gradient checkpointing and smaller micro-batches with accumulation trade speed for memory.

## Data preparation

Data quality decides the result more than any hyperparameter.

- **Format:** chat-style records (`{"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}`) for chat models, or prompt-completion pairs. Render them with the base model's chat template; a mismatch between training and inference formats is a classic silent failure.
- **Loss on outputs only:** train on assistant or completion tokens, not on the prompt. Recent TRL versions do this for prompt-completion data and offer an assistant-only option for conversations; verify by decoding the tokens whose labels are not `-100` for a few examples.
- **Size:** a few hundred excellent examples can teach a format; thousands are typical for a narrow skill. More noisy data is worse than less clean data.
- **Cleaning:** deduplicate (exact and near duplicates), remove examples with wrong answers, strip personal data and secrets, balance task types, and check length distribution against the training sequence length (truncated answers teach truncation).
- **Splits:** hold out validation and test sets that are deduplicated against training, ideally from a later time or different sources. Check for contamination with any benchmark you will report.
- **Synthetic data** from a stronger model: allowed only if the provider's terms permit training other models on its outputs; filter it as strictly as human data, and keep a human-written test set.
- **Licensing and consent:** use data you have the right to train on. Customer data needs a lawful basis and the owner's approval (see `../../legal-ready/GUIDE.md`).

## LoRA with PEFT and TRL

```python
import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

base = "your-org/base-model"                       # pin revision= in real runs
tok = AutoTokenizer.from_pretrained(base)
model = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map="auto")
data = load_dataset("json", data_files={"train": "train.jsonl", "validation": "val.jsonl"})

peft_cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM")
cfg = SFTConfig(output_dir="out", num_train_epochs=2, learning_rate=1e-4, lr_scheduler_type="cosine",
                warmup_ratio=0.03, per_device_train_batch_size=4, gradient_accumulation_steps=8,
                gradient_checkpointing=True, bf16=True, max_length=2048,
                eval_strategy="steps", eval_steps=100, save_steps=100, load_best_model_at_end=True,
                logging_steps=10, seed=0, report_to="none")
trainer = SFTTrainer(model=model, args=cfg, train_dataset=data["train"], eval_dataset=data["validation"],
                     processing_class=tok, peft_config=peft_cfg)
trainer.train()
trainer.save_model("adapter")                      # saves the adapter, not the base weights
```

TRL and PEFT change argument names often (`max_seq_length` became `max_length`; `tokenizer` became `processing_class`). Check the installed versions' documentation; the structure above is stable, the names are not.

QLoRA: load the base with `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)` and pass the same LoRA config. bitsandbytes needs a supported GPU.

## Starting hyperparameters

| Setting | LoRA / QLoRA | Full fine-tuning |
|---|---|---|
| Learning rate | 1e-4 to 2e-4 | 1e-5 to 2e-5 |
| Epochs | 1 to 3 | 1 to 3 |
| Rank `r`, `lora_alpha` | 8 to 64; alpha about 1x to 2x r | n/a |
| Target modules | All linear layers (`"all-linear"`) usually beats attention-only | n/a |
| Effective batch size | 16 to 128 sequences | Same |
| Warmup | 3% to 10% of steps | Same |

Tune on validation loss and, more importantly, on the task metric for the validation set. Validation loss falling while task quality stalls is common.

## Preference tuning

- DPO (and relatives such as ORPO, KTO, SimPO) trains on pairs of preferred and rejected responses without a separate reward model. Start from an SFT model; use a low learning rate (around 5e-7 to 5e-6 for full models, higher for LoRA) and watch for reward hacking: longer, more verbose answers that judges like but users do not.
- RLHF with PPO and a reward model is heavier; use it only with a team that can debug it.
- Preference data needs consistent labeling guidelines and agreement checks between labelers.

## Evaluation

- Compare **base model with the best prompt** against the fine-tuned model on the same frozen test set, with the same decoding settings. Report the spread over several samples or seeds when decoding is stochastic.
- Task metrics first: exact match, F1, pass rate of unit tests, schema validity, human or calibrated-judge ratings (`llm-evaluation.md`). Perplexity and BLEU or ROUGE are weak proxies for most product tasks.
- **Regression checks:** fine-tuning can damage general abilities and safety behavior. Keep a small suite of general and refusal-sensitive prompts and compare before and after.
- Check overfitting to the training format: paraphrased inputs, longer inputs, and inputs from new sources.
- Watch the train and validation loss curves: validation loss rising while training loss falls means overfitting; stop at the best validation checkpoint.

## Merging, quantization and serving

- Serve adapters on top of the base (vLLM and TGI support LoRA adapters, including many adapters per base), or merge with `model.merge_and_unload()` into a bf16 base for a single artifact. Do not merge into a 4-bit quantized base; load the base in bf16 to merge, then quantize the merged model if needed.
- Post-training quantization (GPTQ, AWQ, GGUF for llama.cpp) cuts memory and cost; re-run the evaluation on the quantized model.
- Benchmark latency (time to first token, tokens per second) and throughput at realistic concurrency before choosing hardware.
- The fine-tuned model inherits the base model's license plus any terms from data sources. Record both with the artifact.

## Cost and safety

- Estimate GPU hours before training (tokens x epochs / measured throughput) and get approval for paid compute.
- Never put secrets or unconsented personal data in training sets: models can reproduce training text.
- Keep the training config, data version, base revision and evaluation results together in the experiment tracker (`mlops.md`).

## Pitfalls

| Pitfall | Fix |
|---|---|
| Fine-tuning to inject facts | Retrieval; fine-tune for behavior and format |
| Training format differs from inference format | Same chat template in training, evaluation and serving |
| Loss computed on prompt tokens | Completion-only or assistant-only loss, verified on decoded labels |
| Pad token set to end-of-sequence and EOS masked out of labels | Keep EOS in the labels so the model learns to stop; use a distinct pad token if available |
| Test examples near-duplicated in training | Deduplicate across splits before training |
| Comparing fine-tuned model with an unprompted base | Compare with the base under the best prompt |
| Merging into a 4-bit base | Merge into bf16, then quantize |

## Done when

- [ ] The decision record says why prompting and retrieval were not enough, with numbers.
- [ ] Data is deduplicated across splits, formatted with the model's template, and licensed for training.
- [ ] The fine-tuned model beats the best-prompted base on the frozen test set beyond run-to-run variation, without regressions on the general and safety suite.
- [ ] Quantized or merged artifacts were re-evaluated; latency and cost were measured.
- [ ] Base revision, data version, config, license and results are stored together.
