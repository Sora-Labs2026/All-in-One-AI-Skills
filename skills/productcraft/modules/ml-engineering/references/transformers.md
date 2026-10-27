# Hugging Face Transformers: loading, inference and task fine-tuning

Read this when you run or fine-tune pretrained models from the Hugging Face Hub for text, vision, audio or multimodal tasks: classification, token tagging, embeddings, summarization, generation. Parameter-efficient and LLM fine-tuning (LoRA, QLoRA, SFT, DPO) is in `fine-tuning.md`.

## Versions and setup

```bash
python -m pip install transformers datasets accelerate evaluate safetensors
python -c "import transformers, torch; print(transformers.__version__, torch.__version__)"
```

- The library moves fast. Major version 5 (2025-2026) dropped the TensorFlow and JAX backends and removed or renamed long-deprecated arguments (for example `torch_dtype` became `dtype` during late 4.x). Read the installed version's documentation and migration notes before copying older examples.
- Pin `transformers`, `tokenizers`, `accelerate` and the model revision (`revision="<commit sha>"`) for anything that must be reproducible; Hub repositories can change under the same name.

## Model licenses and access

- Every model card has a license. Many are permissive (Apache-2.0, MIT); some carry use restrictions, attribution requirements, user-count thresholds or non-commercial terms, and gated models need accepted terms. Check the license before building a product on a model, and record it.
- Authenticate with `huggingface-cli login` or the `HF_TOKEN` environment variable set by the user; never paste tokens into code or chat (see `../../agent-safety/GUIDE.md`). Use read-only tokens for downloads.
- `trust_remote_code=True` executes Python from the model repository. Avoid it; when unavoidable, review the code and pin the revision.
- Prefer `safetensors` weights; pickle-based `.bin` files can execute code when loaded.

## Choose the entry point

| Need | Use |
|---|---|
| Quick inference for a standard task | `pipeline(task, model=...)` |
| Control over batching, devices, outputs | `AutoTokenizer` / `AutoProcessor` + `AutoModelFor<Task>` |
| Sentence or document embeddings | sentence-transformers on top of Transformers |
| Fine-tune an encoder for classification or tagging | `Trainer` with `TrainingArguments`, or a plain PyTorch or Lightning loop |
| High-throughput LLM serving | A dedicated server (vLLM, TGI, llama.cpp), not `generate` in a web handler |

```python
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

name = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
tok = AutoTokenizer.from_pretrained(name)
model = AutoModelForSequenceClassification.from_pretrained(name).eval()
batch = tok(["works well", "broke after a day"], padding=True, truncation=True, max_length=256, return_tensors="pt")
with torch.inference_mode():
    probs = model(**batch).logits.softmax(-1)
print(model.config.id2label, probs)
```

## Tokenizers and chat templates

- Always use the tokenizer saved with the model; vocabularies are not interchangeable.
- Set `truncation=True` and an explicit `max_length`; check the share of inputs that get truncated, since truncated evidence silently degrades accuracy.
- Chat and instruction models expect their own prompt format. Build prompts with `tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)` instead of hand-written role markers.
- Decoder-only models generate after the last token, so batch generation needs `padding_side="left"`. If the tokenizer has no pad token, set one deliberately and make sure the attention mask is passed.
- Adding tokens requires `model.resize_token_embeddings(len(tok))` and training to make the new embeddings useful.

## Loading large models

```python
from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.bfloat16, device_map="auto")  # torch_dtype= on older 4.x
```

- Memory for weights is roughly parameters x bytes per parameter: a 7B model needs about 14 GB in bf16, about 4 to 5 GB in 4-bit. Generation adds the key-value cache, which grows with batch size and sequence length.
- `device_map="auto"` spreads layers across GPUs and CPU; offloading to CPU works but is slow.
- `attn_implementation="sdpa"` (PyTorch scaled dot-product attention) is a good default; FlashAttention 2 needs a separate install and supported GPUs.
- Quantized loading (bitsandbytes 8-bit or 4-bit, GPTQ, AWQ) trades some quality for memory; measure the quality drop on your evaluation set.

## Generation settings

- Greedy decoding (`do_sample=False`) for extraction and classification-like outputs; sampling with `temperature` and `top_p` for open-ended text. Beam search suits translation and summarization more than chat.
- Bound output with `max_new_tokens`, not `max_length` (which counts the prompt).
- Put settings in a `GenerationConfig` saved with the model so serving and evaluation use the same values.
- `repetition_penalty` and `no_repeat_ngram_size` patch symptoms; first check the prompt format and the end-of-sequence token.
- Stream tokens with `TextIteratorStreamer` for interactive use.

## Fine-tuning encoders for tasks

```python
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer, DataCollatorWithPadding
import numpy as np, evaluate

model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=len(labels),
                                                           id2label=id2label, label2id=label2id)
args = TrainingArguments(output_dir="out", learning_rate=2e-5, per_device_train_batch_size=16,
                         num_train_epochs=3, weight_decay=0.01, warmup_ratio=0.06,
                         eval_strategy="epoch", save_strategy="epoch",
                         load_best_model_at_end=True, metric_for_best_model="f1", bf16=True,
                         seed=0, report_to="none")
f1 = evaluate.load("f1")
def compute_metrics(p):
    return f1.compute(predictions=np.argmax(p.predictions, -1), references=p.label_ids, average="macro")
trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                  data_collator=DataCollatorWithPadding(tok), compute_metrics=compute_metrics)
trainer.train()
print(trainer.evaluate(test_ds))      # once, after model selection on val_ds
```

- Learning rates around 1e-5 to 5e-5 for full fine-tuning of encoders; a few epochs; warmup. Higher rates destroy pretrained knowledge.
- Small datasets: run several seeds; encoder fine-tuning is known to vary a lot between seeds on small data.
- Baselines: TF-IDF + logistic regression, and frozen embeddings + logistic regression. Report both.
- `evaluate.load` downloads metric scripts on first use; in offline environments compute metrics with scikit-learn instead.
- Argument names drift between versions (`evaluation_strategy` became `eval_strategy`; `tokenizer=` in `Trainer` became `processing_class=`). Follow the installed version.

## Embeddings

- Use models trained for embeddings (sentence-transformers and similar), not mean-pooled hidden states of a generative model.
- Some models need task prefixes (for example "query: " and "passage: "); follow the model card or retrieval quality drops.
- Normalize vectors when using cosine similarity; store the model name and revision with every vector (see `rag-systems.md`).

## Performance and cost

- Batch requests and sort by length to reduce padding.
- Inference on CPU is fine for small encoders; generative models need GPUs or a quantized CPU runtime (llama.cpp, ONNX Runtime).
- Cache downloads (`HF_HOME`) and, in CI or air-gapped settings, set `HF_HUB_OFFLINE=1` with pre-downloaded models.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Hand-written chat prompt format | `apply_chat_template` |
| Right padding for batched generation | `padding_side="left"` and the attention mask |
| `max_length` used to cap new text | `max_new_tokens` |
| Labels mapping lost (LABEL_0, LABEL_1 in outputs) | Pass `id2label` and `label2id` when creating the model |
| Unpinned model revision in production | `revision=` commit hash, recorded with the deployment |
| `trust_remote_code=True` copied from examples | Avoid, or review and pin |
| Test set used for `load_best_model_at_end` | A separate validation split |

## Done when

- [ ] Model license, revision and library versions are recorded.
- [ ] Prompt formatting uses the model's chat template; truncation share is known.
- [ ] Fine-tuned models beat simple baselines on a held-out test set, over several seeds where data is small.
- [ ] Generation settings are saved with the model and identical in evaluation and serving.
