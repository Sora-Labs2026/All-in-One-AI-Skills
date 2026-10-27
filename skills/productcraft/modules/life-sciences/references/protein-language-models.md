# Protein language models

Read this when you embed protein sequences for downstream models, score variants, search for remote homologs by embedding, or generate or complete sequences with a protein language model such as the ESM family. Structure prediction and docking are in `docking.md`; training mechanics in `../../ml-engineering/references/deep-learning-pytorch.md` and `../../ml-engineering/references/transformers.md`.

## What these models do

A protein language model is trained on large sequence databases to predict masked or next residues. Useful consequences:
- **Embeddings** capture structural and functional signal, so a small head trained on a few hundred labeled proteins often beats hand-built features.
- **Pseudo-likelihoods** of residues score how "natural" a variant looks, which correlates with fitness in many deep mutational scanning datasets, zero-shot.
- **Generation** proposes sequences that resemble natural proteins.

What they do not do: predict function or activity reliably without supervision, respect your experimental conditions, or guarantee that a designed sequence folds, expresses or is safe. Every design is a hypothesis for the bench.

## Model families and licenses

| Family | Typical use | Licensing note |
|---|---|---|
| ESM-2 (8M to 15B parameters) | Embeddings, variant scoring; widely used baseline | Permissive open weights |
| ESM C | Newer representation models, efficient at a given quality | Open weights under their own terms for smaller sizes; larger sizes may be API-only |
| ESM3 | Multimodal generation over sequence, structure and function | Smallest model has open weights with use restrictions; larger models served through the provider's API |
| ProtT5 and related encoder-decoder models | Embeddings, per-residue prediction | Check the specific checkpoint |

**Check the license and acceptable-use terms of the exact checkpoint before using it in a product or a publication**, and record them. Some open-weight protein models carry non-commercial or responsible-use conditions, and hosted APIs add terms about what you may submit. Sending proprietary or unpublished sequences to a hosted API needs the owner's permission.

## Setup

```bash
python -m pip install torch
python -m pip install fair-esm          # ESM-2 and earlier
# newer ESM C and ESM3 models ship in their own package; follow the provider's current instructions
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Weights download on first use and are large (hundreds of megabytes to tens of gigabytes). Ask before downloading, set a cache directory on a disk with room, and record the checkpoint name and hash.

## Embeddings that are not subtly wrong

```python
import torch, esm

model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
model.eval().requires_grad_(False)
converter = alphabet.get_batch_converter()

seqs = [("P69905", "MVLSPADKTNVKAAW..."), ("P68871", "MVHLTPEEKSAVTAL...")]
_, _, tokens = converter(seqs)
with torch.inference_mode():
    out = model(tokens, repr_layers=[33])
reps = out["representations"][33]                       # (batch, length + special tokens, dim)

embeddings = []
for i, (_, seq) in enumerate(seqs):
    residue_reps = reps[i, 1 : len(seq) + 1]            # drop BOS and padding/EOS
    embeddings.append(residue_reps.mean(0))             # mean over residues only
```

- **Exclude special tokens and padding from pooling.** Averaging over the padded tensor is the most common silent bug; it makes embeddings depend on batch composition.
- **Per-residue against per-protein:** keep residue embeddings for site-level tasks (binding sites, modification sites), pool for protein-level tasks.
- **Truncation:** models have a maximum context (ESM-2 is usually used up to about 1,022 residues). Long proteins must be truncated or chunked with overlap; record the rule and never compare pooled embeddings from different rules.
- **Batching:** group sequences of similar length to limit padding, and watch memory, which grows with the square of length for attention.
- **Cache embeddings** keyed by checkpoint, layer, pooling and sequence hash. They are deterministic and expensive.
- **Layer choice** matters: the last layer is not always best for a downstream task. Try a middle layer and the last layer, and select on validation data.

## Downstream models

- Start with a linear or shallow head (logistic regression, small MLP, gradient boosting) on frozen embeddings. Fine-tuning the whole model needs much more data and compute and often does not win.
- **Split by homology, not at random.** Sequences in a family are near-duplicates; random splits leak and inflate scores. Cluster at an identity threshold (MMseqs2 or CD-HIT at, for example, 30% identity) and split by cluster. See `../../ml-engineering/references/evaluation-and-leakage.md`.
- **Baselines to beat:** one-hot or amino-acid composition features, a position-specific scoring matrix from an alignment of the family, and BLAST nearest-neighbor transfer. Report them.

## Variant effect scoring (zero-shot)

```python
# Masked-marginal score for a substitution at 1-based position pos: log p(mut) - log p(wt)
# at the masked position, using the wild-type sequence as context.
```

- Masked-marginal scoring (mask the position, compare mutant and wild-type log probabilities) is the usual recipe and generally beats scoring the mutant sequence as a whole.
- Scores are **relative within one protein**; they are not comparable across proteins, and they are not predictions of pathogenicity or of any specific phenotype. A model trained on natural sequences reflects evolutionary constraint, which mixes fitness, expression and other pressures.
- Alignment-based methods remain strong, especially for proteins with deep alignments. Compare against one.
- For human variant interpretation, never present a model score as clinical evidence. Clinical classification follows established guidelines and curated databases, with expert review.

## Generation and design

- Treat generated sequences as candidates: check length, composition, obvious repeats, and the presence of required motifs; predict a structure and check that it is confident and matches the intent; and compare against natural homologs.
- Record the model, the prompt or constraints, temperature, seed and the number of candidates generated versus kept. Report selection criteria honestly, including how many candidates were discarded.
- **Biosecurity:** do not design, optimize or assist with sequences intended to harm, with toxins or with pathogen enhancement, and do not help bypass sequence screening by synthesis providers. Wet-lab work with designed sequences goes through institutional biosafety review; say so in the report.

## Compute

- Embedding a proteome (tens of thousands of proteins) with a mid-sized model takes hours on one GPU. Estimate first, process in batches with checkpointing, and use half precision (`torch.float16` or `bfloat16`) where the hardware supports it, confirming scores are unchanged on a sample.
- CPU-only inference works for small models and short sequences; it is far slower.

## Checks (done when)

- [ ] Checkpoint name, version, license and acceptable-use terms recorded; permission obtained for anything sent to a hosted API.
- [ ] Pooling excludes special tokens and padding; truncation rule stated and applied uniformly.
- [ ] Downstream evaluation uses homology-aware splits and reports simple baselines.
- [ ] Variant scores reported as relative, model-derived evidence, never as clinical interpretation.
- [ ] Generated sequences labeled as untested candidates, with selection criteria and discard counts.
