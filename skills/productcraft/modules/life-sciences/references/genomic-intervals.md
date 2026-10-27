# Genomic intervals: BED, overlaps, liftover and region sets

Read this when you work with BED, bedGraph, narrowPeak, GTF or GFF files; intersect, merge, window or shuffle regions; build promoters or consensus peak sets; move coordinates between genome builds; or turn region sets into features for machine learning. Reads and variants are in `reads-and-variants.md`; signal tracks in `deeptools-coverage.md`.

## Formats and conventions

| Format | Convention | Notes |
|---|---|---|
| BED, bedGraph, narrowPeak, broadPeak | 0-based, half-open | `chr1 0 100` is the first 100 bases; zero-length intervals (`start == end`) mark insertion points |
| GTF, GFF3 | 1-based, closed | Column 4 is start, 5 is end; `start == end` is one base |
| VCF | 1-based | `POS` of the first REF base |
| Region strings (`chr1:1001-1100`) | 1-based, closed | samtools, IGV, UCSC browser |
| chrom.sizes, `.fai` | Lengths | The genome definition every interval tool needs for complements, slop and shuffles |

Convert once, at the boundary: 1-based closed `[s, e]` becomes BED `[s - 1, e)`. `scripts/interval_check.py convert` prints both forms of a region, and `scripts/interval_check.py check FILE --genome chrom.sizes` catches coordinates past the end of a chromosome (a strong sign of the wrong build), unknown contigs, `chr` naming mismatches, negative or inverted intervals and unsorted files.

## Pick the tool

- **bedtools** on the command line: the reference implementation, fast on sorted input, easy for reviewers to read.
- **bioframe** for pandas DataFrames with `chrom`, `start`, `end` columns, inside Python pipelines.
- **pyranges** for fast interval algebra on large sets. Its 1.x releases renamed many methods relative to 0.x; check the installed version before copying examples.
- **pybedtools** wraps bedtools from Python; it writes temporary files, so clean them up (`pybedtools.cleanup()`).

## Core operations

```bash
LC_ALL=C sort -k1,1 -k2,2n peaks.bed > peaks.sorted.bed     # or: bedtools sort -i peaks.bed

bedtools merge -i peaks.sorted.bed -d 100 > merged.bed                      # merge within 100 bp
bedtools intersect -a peaks.bed -b promoters.bed -u > peaks_in_promoters.bed   # A records with any overlap
bedtools intersect -a peaks.bed -b exclusion.bed -v > peaks.clean.bed       # A records with no overlap
bedtools intersect -a a.bed -b b.bed -wa -wb -f 0.5 -r                      # pairs overlapping 50% reciprocally
bedtools closest -a peaks.sorted.bed -b tss.sorted.bed -d -t first          # nearest TSS with distance
bedtools slop -i sites.bed -g genome.chrom.sizes -b 250                      # extend, clipped at chromosome ends
bedtools complement -i covered.bed -g genome.chrom.sizes                     # gaps
```

- `-s` makes operations strand-aware; without it, a minus-strand gene overlaps plus-strand peaks.
- Overlap definitions differ: one base (default), a fraction of A (`-f`), reciprocal (`-r`). State which one you used.
- `-sorted` with `-g` streams sorted inputs in constant memory; both files must be sorted in the same chromosome order as the genome file.
- Sort order matters: `chr10` before `chr2` in lexical order; tools that require a particular order say so. Use the genome file's order for `-sorted`.

```python
import bioframe as bf

peaks = bf.read_table("peaks.bed", schema="bed3")
genes = bf.read_table("genes.bed", schema="bed6")
hits = bf.overlap(peaks, genes, how="inner", suffixes=("", "_gene"))
merged = bf.merge(peaks, min_dist=100)
```

## Strand-aware promoters

```python
def promoter(chrom, start, end, strand, up=2000, down=500):
    """BED-style gene interval in, BED-style window around the TSS out."""
    if strand == "+":
        tss = start                      # 0-based first base
        return chrom, max(0, tss - up), tss + down
    tss = end - 1                        # on the minus strand the TSS is the last base
    return chrom, max(0, tss - down + 1), tss + up + 1
```

Clip the end at the chromosome length (or use `bedtools flank` and `slop` with `-g`). Test on one plus-strand and one minus-strand gene whose TSS you can check in a genome browser.

## Genome builds and liftover

- Never intersect intervals from different builds. Check headers (`##reference`, `##contig` lines in VCF), file names, the source's documentation and coordinates against the sizes file.
- Lift intervals with UCSC `liftOver` or CrossMap and the matching chain file. Report how many records failed to lift and why; dropped regions are often the interesting, rearranged ones.
- Lifting can split, merge or shrink intervals. Use a minimum-match setting (`liftOver -minMatch`) and compare lengths before and after.
- Lift variants with a VCF-aware tool (`bcftools +liftover` or Picard `LiftoverVcf`), which also fixes REF and ALT alleles that change between builds. Interval tools do not.
- Prefer re-running the analysis on the target build from raw data when that is feasible.

## Exclusion lists and mappability

High-signal artifact regions (repeats, satellites, centromeres) create false peaks and inflate overlaps. Remove them with the published exclusion list for the assay and build (for example the ENCODE lists for GRCh38 and mm10) and say which version you used.

## Is an overlap meaningful?

Counting overlaps proves nothing on its own; large region sets overlap by chance.

1. Build a null by shuffling one set within the genome, keeping chromosome and excluding gaps and exclusion regions: `bedtools shuffle -i peaks.bed -g genome.chrom.sizes -chrom -excl gaps_and_exclusions.bed -seed 1`.
2. Repeat many times with recorded seeds and compare observed overlap with the null distribution.
3. Shuffling everywhere ignores GC content, gene density and mappability, which makes almost anything look enriched. Restrict the shuffle to a matched background (for example all accessible regions, `-incl`) when the question is about enrichment within that background.
4. Report the effect size (observed over expected) with the empirical p-value and the background definition.

## Region sets for machine learning

Region sets (peaks, accessible regions, single-cell ATAC fragments) can be turned into features:

- **Tokenize against a universe:** define a fixed reference set of regions (a consensus peak set built from many samples), then map every sample's regions to universe tokens by overlap. Samples become bags or sequences of tokens that downstream models can use. Libraries such as geniml (embeddings of regions, region sets and single cells) and gtars (fast tokenizers and interval utilities written in Rust with Python bindings) implement this; their APIs are young and change between releases, so read the documentation of the installed version.
- **The universe decides what the model can see.** Build it on the same build, exclude artifact regions, and record how it was made. Check what fraction of each sample's regions map to universe tokens; low coverage means the universe does not fit the data.
- **Single-cell ATAC:** fragment files are tabix-indexed BED-like files with a barcode column. Count fragments per cell over the universe (or tiles) to build a cells-by-regions matrix in AnnData (`anndata.md`), then use a dedicated toolkit for QC (TSS enrichment, fragment-length pattern, doublets).
- **Evaluate embeddings like any model:** held-out samples, a simple baseline (binary overlap matrix with TF-IDF and SVD), and labels the model never saw. See `../../ml-engineering/references/evaluation-and-leakage.md`.

## Pitfalls

| Pitfall | Fix |
|---|---|
| GTF start used as BED start | Subtract 1 from the start; keep the end |
| `chr1` against `1` gives zero overlaps | Rename with an explicit mapping table; recheck counts |
| Unstranded overlap of stranded features | `-s` (same strand) or `-S` (opposite strand) |
| Plain `gzip` BED that tabix rejects | Recompress with `bgzip`, then `tabix -p bed` |
| Enrichment against a genome-wide shuffle | Matched background, chromosome-preserving shuffle, exclusions |
| Lifted file treated as complete | Report unlifted counts and changed lengths |

## Checks (done when)

- [ ] `interval_check.py check` is clean (or every warning is explained) against the sizes file of the build in use.
- [ ] Every file in a comparison has the same build and naming style.
- [ ] Overlap definition, strandedness and any exclusion list are stated.
- [ ] One overlap and one promoter on each strand were verified by hand or in a genome browser.
- [ ] Enrichment claims come with the null model, background, seeds and effect size.
