# Reads and variants: SAM, BAM, CRAM, VCF and BCF

Read this when you read, filter, count or write aligned reads or variant calls, with pysam in Python or samtools and bcftools on the command line, or when a cohort outgrows single VCF files. Interval logic (BED, overlaps, liftover) is in `genomic-intervals.md`; coverage tracks in `deeptools-coverage.md`.

## Pick the tool

| Job | Tool |
|---|---|
| Sort, index, merge, filter, count, flag statistics | `samtools` (fastest, well tested) |
| Filter, normalize, merge, annotate, query variants | `bcftools` |
| Custom per-read or per-variant logic in Python | `pysam` (same htslib underneath) |
| Many samples queried by region, added incrementally | TileDB-VCF, or a genotype format such as PLINK 2 `pgen` for association work, or Hail on Spark for very large cohorts |

Prefer a samtools or bcftools one-liner over a Python loop when one exists: it is faster, and reviewers can check it.

## Setup

```bash
python -m pip install pysam          # wheels bundle htslib, samtools and bcftools
samtools --version; bcftools --version
python -c "import pysam; print(pysam.__version__)"
```

Record the htslib version of the command-line tools and of pysam; they can differ.

## Coordinates

- pysam is 0-based half-open: `read.reference_start` is the first aligned base, `read.reference_end` is one past the last. `fetch("chr1", 999, 2000)` covers 1-based positions 1000 to 2000.
- Region strings follow samtools and are 1-based closed: `fetch(region="chr1:1000-2000")` covers the same bases.
- In `VariantFile`, `rec.pos` is the 1-based VCF position and `rec.start` is 0-based. Mixing the two is the classic off-by-one.
- `fetch` returns every read that **overlaps** the region, including reads that start before it. Clip or filter when you need containment.

## Indexes

| File | Index | Create |
|---|---|---|
| BAM | `.bai` (or `.csi` for contigs over 512 Mb) | `samtools index x.bam` (file must be coordinate-sorted) |
| CRAM | `.crai` | `samtools index x.cram` |
| FASTA | `.fai` | `samtools faidx ref.fa` |
| VCF | `.tbi` or `.csi` | `bgzip x.vcf && bcftools index -t x.vcf.gz` |
| BCF | `.csi` | `bcftools index x.bcf` |

VCFs for random access must be compressed with `bgzip`, not plain `gzip`. Both produce `.gz`; only BGZF can be indexed.

## Reads with pysam

```python
import pysam

with pysam.AlignmentFile("sample.bam", "rb") as bam:
    n = 0
    for read in bam.fetch("chr17", 7_661_778, 7_687_538):
        if (read.is_unmapped or read.is_secondary or read.is_supplementary
                or read.is_duplicate or read.is_qcfail or read.mapping_quality < 20):
            continue
        n += 1
```

```bash
# The same count, checkable by anyone: exclude unmapped, secondary, supplementary, duplicates, QC fail; MAPQ >= 20
samtools view -c -F 0xF04 -q 20 sample.bam chr17:7661779-7687538
```

- State the filters with every count. Flag `0x904` drops unmapped, secondary and supplementary records; add `0x400` (duplicates) and `0x200` (QC fail) as needed (`0xF04` covers all five).
- MAPQ scales differ by aligner (STAR reports 255 for unique hits; BWA uses 0 to 60). Choose thresholds per aligner.
- Duplicates are only flagged if a marking step ran (`samtools markdup`, Picard). Check the header `@PG` lines for what was done.
- Paired-end fragments: count read 1 only (`read.is_read1`) or proper pairs (`-f 0x2`) when counting fragments, not reads.
- CRAM needs the exact reference it was written against. Pass `reference_filename="ref.fa"` (pysam) or `-T ref.fa` (samtools) and set `REF_PATH` and `REF_CACHE`; otherwise htslib may try to download the reference from a public server.
- Opening several iterators on one handle interferes; use `multiple_iterators=True` or separate handles, and one handle per worker process.

## Pileups and coverage

```python
with pysam.AlignmentFile("sample.bam", "rb") as bam:
    a, c, g, t = bam.count_coverage("chr1", 999, 1010, quality_threshold=20)
    for col in bam.pileup("chr1", 999, 1010, truncate=True,
                          min_base_quality=20, max_depth=1_000_000):
        depth = col.get_num_aligned()
```

- `pileup` stops counting at `max_depth` (default 8000). Deep amplicon or targeted data silently saturates unless you raise it.
- `truncate=True` limits columns to the requested window; without it you get every column touched by overlapping reads.
- Overlapping mates are counted once by default (`ignore_overlaps=True`); say so when reporting allele fractions.
- For genome-wide depth, `samtools depth -a` or `mosdepth` is far faster than Python loops.

## Variants with pysam

```python
with pysam.VariantFile("calls.vcf.gz") as vcf:
    for rec in vcf.fetch("chr1", 1_000_000, 2_000_000):
        if "PASS" not in rec.filter.keys():
            continue
        for alt in rec.alts or ():
            gt = rec.samples["S1"]["GT"]          # tuple such as (0, 1); None for missing alleles
            print(rec.chrom, rec.pos, rec.ref, alt, gt, rec.samples["S1"].phased)
```

- `rec.alts` is `None` for reference-only records (common in gVCF). Guard before iterating.
- INFO and FORMAT fields with `Number=A` hold one value per ALT; with `Number=R` one per allele including REF. Index them by allele, never by position in a flattened list.
- An empty `FILTER` (`.`) means no filters were applied, not that the record passed.
- Missing genotypes are `None` inside the tuple (`(None, None)`), not 0.

## Normalize before comparing

Two callers can describe the same indel differently. Before intersecting, merging or annotating:

```bash
bcftools norm -f ref.fa -m -any calls.vcf.gz -Oz -o calls.norm.vcf.gz   # left-align, split multi-allelic records
bcftools index -t calls.norm.vcf.gz
bcftools isec -p isec_out a.norm.vcf.gz b.norm.vcf.gz                    # set operations on normalized calls
```

Check that `bcftools norm` reports no REF mismatches; mismatches mean the wrong reference or build.

## Useful bcftools idioms

```bash
bcftools view -f PASS -i 'QUAL>=30 && INFO/DP>=10' in.vcf.gz -Oz -o filtered.vcf.gz
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT[\t%GT]\n' filtered.vcf.gz > table.tsv
bcftools stats filtered.vcf.gz > stats.txt         # Ti/Tv, indel lengths, per-sample counts
bcftools view -s S1,S2 --force-samples in.vcf.gz   # subset samples
```

Sanity numbers to compare against: for human whole-genome germline SNVs the transition/transversion ratio is near 2.0 to 2.1, and higher (about 2.8 to 3.0) in exomes. A large deviation points to false positives.

## Cohort scale with TileDB-VCF

Use it when many single-sample VCFs (often gVCFs) must be queried by region and sample, and new samples arrive over time without re-merging a giant joint VCF.

```python
import tiledbvcf

ds = tiledbvcf.Dataset("cohort_vcf", mode="w")
ds.create_dataset()
ds.ingest_samples(sample_uris=["s1.g.vcf.gz", "s2.g.vcf.gz"])     # single-sample, indexed inputs

ds = tiledbvcf.Dataset("cohort_vcf", mode="r")
df = ds.read(attrs=["sample_name", "contig", "pos_start", "alleles", "fmt_GT"],
             regions=["chr13:32315474-32400266"], samples=["s1", "s2"])
```

- Inputs must be single-sample VCF or BCF files with an index; split multi-sample files first.
- Region strings are 1-based closed, like samtools.
- Reads larger than the memory budget come back in pieces: loop on `ds.read_completed()` and `ds.continue_read()`, or raise the budget in the read configuration.
- One writer per dataset at a time; parallel ingestion goes through the library's own batching, not concurrent processes on the same URI.
- Object-store URIs (`s3://...`) work; credentials come from the environment, never from code.
- The Python API has changed between releases (configuration objects, attribute names). Check `tiledbvcf.version` and the documentation for that release.

## Privacy

Reads and genotypes from people are personal data and can re-identify them even without names. Keep them on approved storage, share summaries rather than files, and never upload them to public services without the owner's permission.

## Checks (done when)

- [ ] Every input is sorted and indexed, and the reference FASTA matches the build named in the headers.
- [ ] Every count states its flag, MAPQ and base-quality filters and the region convention.
- [ ] Variant sets are normalized against the same reference before comparison, with zero REF mismatches.
- [ ] At least one region's result matches an independent `samtools view -c` or `bcftools view` command.
- [ ] Summary statistics (flagstat, Ti/Tv, per-sample counts) are reported and plausible.
