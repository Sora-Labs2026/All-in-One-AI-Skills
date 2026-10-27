# Sequences with Biopython

Read this when you parse or write FASTA, FASTQ, GenBank or EMBL files, translate or manipulate sequences, align a few sequences pairwise, query NCBI through Entrez, run or parse BLAST, or read atoms out of PDB and mmCIF files. Reads and variants at sequencing scale belong to `reads-and-variants.md`; trees to `phylogenetics.md`.

## When to use it, and when not

- **Use Biopython** for file formats with rich annotation (GenBank features, qualifiers, references), scripted NCBI access, parsing BLAST output, small-scale pairwise alignment and structure parsing.
- **Use something else** for millions of short reads (pysam, or `seqkit` on the command line, are far faster), multiple sequence alignment (MAFFT or MUSCLE, see `phylogenetics.md`), large homology searches (local BLAST+, DIAMOND or MMseqs2), or one-off lookups of a gene's sequence (`gget.md`).

## Setup

```bash
python -m pip install biopython
python -c "import Bio; print(Bio.__version__)"
```

Releases from 1.80 onwards removed long-deprecated modules (`Bio.Alphabet` is gone; `Bio.pairwise2` is deprecated in favor of `Bio.Align.PairwiseAligner`). Old tutorials and answers often use them. Check the installed version before copying patterns.

## Sequence files

```python
from Bio import SeqIO

# Stream: one record in memory at a time
n_in = n_out = 0
with open("reads.fastq") as fin, open("long_reads.fasta", "w") as fout:
    for rec in SeqIO.parse(fin, "fastq"):
        n_in += 1
        if len(rec.seq) >= 1000:
            n_out += SeqIO.write(rec, fout, "fasta")
print(n_in, n_out)

# Random access by ID without loading the file
idx = SeqIO.index("proteome.fasta", "fasta")          # dict-like, lazy
seq = idx["sp|P69905|HBA_HUMAN"].seq

# Exactly one record expected
rec = SeqIO.read("plasmid.gb", "genbank")
```

- `SeqIO.parse` is a generator; wrapping it in `list()` loads everything. Use `SeqIO.index` (or `index_db` for an on-disk SQLite index) for lookups.
- FASTQ comes in variants: `"fastq"` (Sanger, Phred+33, the modern default), `"fastq-illumina"` (old Phred+64). Wrong choice gives silently wrong qualities.
- Record IDs are the first word of the header; the rest is `description`. Check the ID style before joining files (`sp|P69905|HBA_HUMAN` against `P69905`).
- GenBank feature locations are 0-based half-open in Python (`feature.location.start`), although the file shows 1-based. Use `feature.extract(record.seq)` to get a feature's sequence: it handles strand and joins.
- Gzipped input: open with `gzip.open(path, "rt")` and pass the handle.

## Sequence operations

```python
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction

s = Seq("ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG")
s.reverse_complement()
s.translate(table=11, to_stop=True)   # bacterial code; stop at first stop codon
gc_fraction(s)
```

- Pass the genetic code explicitly (`table=1` standard, `11` bacterial and plastid, `2` vertebrate mitochondrial). The default is the standard code.
- `translate(cds=True)` validates a complete coding sequence (start codon, length a multiple of three, single terminal stop) and raises otherwise. Use it when the input claims to be a CDS.
- `gc_fraction` replaced `GC` in recent releases; ambiguous bases are handled by its `ambiguous` argument.

## Pairwise alignment

```python
from Bio import Align
from Bio.Align import substitution_matrices

aligner = Align.PairwiseAligner(mode="global")
aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
aligner.open_gap_score = -10
aligner.extend_gap_score = -0.5
best = aligner.align(prot_a, prot_b)[0]
print(best.score)
print(best)
```

- State the scoring scheme in the report; scores are meaningless without it.
- The number of optimal alignments can be astronomically large. Take the first or iterate lazily; never `len()` or `list()` the result for long sequences.
- `mode="local"` is Smith-Waterman. For more than a few thousand pairs, use a dedicated tool (parasail, or BLAST and DIAMOND for search).

## NCBI Entrez

```python
import os
from Bio import Entrez, SeqIO

Entrez.email = os.environ["NCBI_EMAIL"]          # required: identifies you to NCBI
Entrez.api_key = os.environ.get("NCBI_API_KEY")  # optional: 10 requests per second instead of 3
Entrez.tool = "my-analysis"

ids = Entrez.read(Entrez.esearch(db="nucleotide", term="NC_045512[Accession]"))["IdList"]
with Entrez.efetch(db="nucleotide", id=ids, rettype="gb", retmode="text") as h:
    rec = SeqIO.read(h, "genbank")
```

- NCBI usage rules: identify yourself with `email` and `tool`, stay under 3 requests per second without a key and 10 with one, and run large jobs outside United States peak hours. Biopython throttles single calls, but parallel workers multiply the rate.
- Keep the email and API key in environment variables, never in code or chat (`../../agent-safety/GUIDE.md`).
- For many IDs, post them once with `epost` (or `usehistory="y"` in `esearch`) and fetch in batches of a few hundred using `WebEnv` and `query_key`.
- Cache every downloaded record on disk with the accession and version (`NM_000546.6`, not `NM_000546`). Records change; the version pins what you analyzed.
- Large or repeated pulls are better served by bulk FTP downloads or NCBI Datasets than by thousands of Entrez calls.

## BLAST

- **Remote** (`Bio.Blast.NCBIWWW.qblast`) is for a handful of queries. It is slow, rate-limited, sends your sequence to NCBI, and the database changes daily. Do not send unpublished or human-identifying sequences without the owner's permission.
- **Local** BLAST+ for anything else: build or download a database, run `blastn` or `blastp` with `-outfmt 6` or `-outfmt 5`, and parse.

```bash
makeblastdb -in refs.fasta -dbtype nucl -out refs
blastn -query q.fasta -db refs -evalue 1e-10 -outfmt "6 qseqid sseqid pident length evalue bitscore" -num_threads 8 > hits.tsv
```

- Record the program, version, database name and date, and E-value threshold. E-values depend on database size, so they are not comparable across databases.
- Percent identity over a short alignment means little; filter on alignment length or query coverage as well.

## Structures (Bio.PDB)

```python
from Bio.PDB import MMCIFParser, PDBParser

structure = MMCIFParser(QUIET=True).get_structure("x", "1abc.cif")
for chain in structure[0]:                      # first model only
    for res in chain:
        if res.id[0] == " ":                    # standard residue, not water or ligand
            ...
```

- Prefer mmCIF: large structures do not fit the legacy PDB format, and new entries may be mmCIF only.
- Residue IDs are tuples `(hetero flag, number, insertion code)`. Residue numbers follow the author's numbering, which is not the UniProt position; map with SIFTS when positions must agree.
- NMR and some cryo-EM entries have several models; pick one deliberately.
- Alternate locations, missing residues and missing atoms are common. Count them before computing distances or contacts.
- Fetching structures and predicted models is covered in the public databases section of `../GUIDE.md`.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Whole file loaded with `list(SeqIO.parse(...))` | Stream, or `SeqIO.index` for lookups |
| Wrong FASTQ quality encoding | Check the quality range; modern data is `"fastq"` (Phred+33) |
| Header IDs differ between files | Normalize IDs with an explicit rule and count unmatched records |
| Translation with the wrong genetic code | Pass `table=` explicitly; record it |
| Accession without version | Store `accession.version` and the download date |
| Entrez throttled or blocked | Email and key set, batches with history server, one worker |

## Checks (done when)

- [ ] Record counts in and out are reported and explained (filters, failures).
- [ ] IDs join across files with zero unexplained misses.
- [ ] Genetic code, alignment scoring and BLAST parameters are recorded.
- [ ] Every downloaded record is cached with accession, version and date; Entrez identification is set and the rate limit respected.
- [ ] No sequence went to a remote service without the owner's permission.
