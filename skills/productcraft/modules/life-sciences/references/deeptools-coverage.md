# Coverage tracks and signal QC with deepTools

Read this when you turn BAM files into normalized bigWig or bedGraph tracks, compare treatment against input or control, check ChIP-seq, ATAC-seq, CUT&RUN or CUT&Tag quality, or draw heatmaps and profiles of signal around genes or peaks. Peak calling itself (MACS3 and similar) is a separate step; interval operations are in `genomic-intervals.md`.

## Setup

```bash
python -m pip install deeptools pyBigWig
bamCoverage --version
```

deepTools is a set of command-line programs. Record the version and the full command of every run; tracks are only comparable when made the same way.

## Before anything: inputs

- BAMs coordinate-sorted and indexed, from the same aligner, build and filtering.
- Duplicates marked (or removed) consistently. Decide whether to `--ignoreDuplicates`; for ATAC and ChIP it is usual, for low-input libraries it can discard real signal. Apply the same choice to every sample.
- An exclusion list for the build (`--blackListFileName`), so artifact regions do not dominate normalization and heatmaps.
- The effective genome size for the build and read length, taken from the deepTools documentation table or computed for the exact filtering you use (mappable bases, or non-N bases when no mappability filter applies). Wrong values scale every RPGC track.
- Test parameters on one region first: `--region chr19` runs in seconds.

## Coverage tracks

```bash
bamCoverage -b sample.bam -o sample.cpm.bw \
  --binSize 10 --normalizeUsing CPM \
  --ignoreDuplicates --minMappingQuality 30 \
  --extendReads --blackListFileName exclusions.bed \
  -p 8
```

| Normalization | Meaning | Use for |
|---|---|---|
| `CPM` | Counts per million mapped reads | Most comparisons between samples of the same assay |
| `RPGC` | 1x genome coverage; needs `--effectiveGenomeSize` | ChIP and ATAC when you want coverage-like units |
| `BPM` | Bins per million, like TPM for bins | Comparing bin-level signal across depths |
| `RPKM` | Per kilobase per million | Rarely needed for bins; legacy |
| `None` | Raw counts | Inputs for your own normalization |

- These methods assume the total amount of signal is comparable between samples. When a treatment changes global levels (for example loss of a histone mark), only spike-in or other external normalization shows it: compute a scale factor from spike-in reads and pass `--scaleFactor` with `--normalizeUsing None`.
- `--extendReads`: single-end ChIP reads are extended to the fragment length (give the estimated length); paired-end reads use the actual fragment. Never extend spliced RNA-seq reads.
- `--centerReads` sharpens signal at binding sites; `--smoothLength` makes tracks prettier but blurs peaks. Report either.
- Bin size trades resolution for file size: 10 to 50 bp for TF and ATAC, 50 to 200 bp for broad marks.

### RNA-seq tracks

```bash
bamCoverage -b rna.bam -o rna.fwd.bw --filterRNAstrand forward --normalizeUsing CPM --binSize 1 -p 8
bamCoverage -b rna.bam -o rna.rev.bw --filterRNAstrand reverse --normalizeUsing CPM --binSize 1 -p 8
```

`--filterRNAstrand` assumes a dUTP-style (reverse-stranded) library. Check on a known highly expressed gene on each strand that signal lands on the correct track; if it is swapped, the library has the other orientation.

### ATAC-seq

Tn5 inserts with a 9 bp duplication; shifting reads (+4 on the plus strand, -5 on the minus strand) centers cut sites:

```bash
alignmentSieve -b atac.bam -o atac.shifted.bam --ATACshift --minMappingQuality 30 -p 8
samtools sort -o atac.shifted.sorted.bam atac.shifted.bam && samtools index atac.shifted.sorted.bam
bamPEFragmentSize -b atac.bam --histogram atac.fragsize.png
```

A good library shows a nucleosome-free peak below about 100 bp and a ladder at mono- and di-nucleosome sizes. A flat fragment distribution is a quality problem, not a parameter problem.

## Treatment against control

```bash
bamCompare -b1 chip.bam -b2 input.bam -o chip_vs_input.log2.bw \
  --operation log2 --scaleFactorsMethod readCount \
  --binSize 50 --extendReads --ignoreDuplicates \
  --blackListFileName exclusions.bed -p 8
```

- Pick one scaling: `--scaleFactorsMethod readCount` (or `SES`), or `--scaleFactorsMethod None` with `--normalizeUsing`. They are alternatives, not layers.
- `--pseudocount` keeps empty bins from producing infinite ratios; its value changes low-signal regions, so keep it fixed across samples.

## Quality control

```bash
multiBamSummary bins -b s1.bam s2.bam s3.bam s4.bam -o counts.npz --binSize 10000 \
  --blackListFileName exclusions.bed -p 8
plotCorrelation -in counts.npz --corMethod spearman --whatToShow heatmap --skipZeros -o corr.png
plotPCA -in counts.npz -o pca.png
plotFingerprint -b chip.bam input.bam --extendReads --ignoreDuplicates -o fingerprint.png \
  --outRawCounts fingerprint.tsv
```

What to look for:
- **Correlation and PCA:** replicates cluster together and separate by condition. An outlier replicate needs explanation before it is used or dropped.
- **Fingerprint:** input is close to the diagonal; good ChIP of a sharp factor bends strongly (a small fraction of bins holds most reads). A ChIP curve close to the input curve means weak enrichment.
- **GC bias:** `computeGCBias` shows whether coverage depends on GC. Correct only when the bias is real and strong; corrected BAMs contain duplicated reads, so do not remove duplicates afterwards.

## Heatmaps and profiles

```bash
computeMatrix reference-point --referencePoint TSS -S s1.cpm.bw s2.cpm.bw -R genes.bed \
  -b 3000 -a 3000 --binSize 50 --skipZeros --missingDataAsZero -o tss.mat.gz -p 8
plotHeatmap -m tss.mat.gz -o tss.heatmap.png --sortUsing mean --kmeans 3
plotProfile -m tss.mat.gz -o tss.profile.png --perGroup
```

- `reference-point` aligns on one point (TSS, peak summit); `scale-regions` stretches every region to the same length (gene bodies). The second hides length differences; say which you used.
- The regions file defines the plot. Strand matters for TSS plots (BED6 with strand), and the region set must use the same build and naming as the tracks.
- Heatmaps colored with a per-sample scale cannot be compared by eye. Set `--zMin` and `--zMax` explicitly for side-by-side panels.
- k-means clusters change with the seed and the number of clusters; treat them as a view of the data, not as findings, unless they hold up across settings.

## Reading tracks in Python

```python
import pyBigWig
bw = pyBigWig.open("s1.cpm.bw")
mean_signal = bw.stats("chr1", 1_000_000, 1_010_000, type="mean")[0]   # 0-based, half-open
bw.close()
```

## Checks (done when)

- [ ] Every track was built with the same normalization, bin size, filters, exclusion list and duplicate policy, with commands recorded.
- [ ] The effective genome size matches the build and filtering, or RPGC was not used.
- [ ] Correlation, PCA and fingerprint plots were reviewed and outliers explained.
- [ ] Strand assignment of RNA tracks and the ATAC fragment pattern were checked on known features.
- [ ] Heatmap panels share explicit color limits and state the matrix mode and region set.
