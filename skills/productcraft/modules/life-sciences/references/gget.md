# Quick lookups with gget

Read this when you need a fast answer from public resources: find a gene's Ensembl ID, fetch a transcript or protein sequence, get reference genome download links, run a small BLAST or BLAT, check an enrichment, or pull a few expression values. gget wraps many web services behind one command-line and Python interface. Direct, version-controlled access to each database (UniProt, Ensembl, PDB, AlphaFold DB, COSMIC and others) is covered in the public databases section of `../GUIDE.md`; prefer those routes for production pipelines.

## When to use it, and when not

- **Use gget** for interactive exploration, notebooks and small scripted lookups where one tool beats learning ten APIs.
- **Do not use gget** as the backbone of a pipeline that must be reproducible for years: it depends on remote services whose layouts change, and its modules are updated to follow them. Download pinned releases instead (`gget ref` gives the links).
- **Do not use it** for large batches (thousands of IDs or sequences): the remote services rate-limit, and local tools (BLAST+, DIAMOND, a downloaded annotation table) are faster and repeatable.

## Setup

```bash
python -m pip install --upgrade gget
gget --version
```

Some modules need extra dependencies installed through `gget setup <module>` (for example structure prediction and motif search). Ask before running setups that download large models or databases.

## Common modules

| Module | Does | Watch out for |
|---|---|---|
| `ref` | Ensembl FTP links for genome, GTF, cDNA, protein | Pin `-r <release>`; record it |
| `search` | Gene or transcript IDs from free-text terms | Matches descriptions loosely; check every hit |
| `info` | Gene and transcript metadata from Ensembl, UniProt, NCBI | Batch size limits (about a thousand IDs) |
| `seq` | Nucleotide or protein sequences for Ensembl IDs | `-iso` for all isoforms; canonical otherwise |
| `blast`, `blat` | Remote BLAST at NCBI, BLAT at UCSC | Sequence leaves the machine; small jobs only |
| `muscle`, `diamond` | Local alignment and fast protein search | Installed binaries; fine for modest sizes |
| `pdb`, `alphafold` | Structure files; local structure prediction | Prediction is heavy and slow; check the database first |
| `enrichr` | Gene-set enrichment through the Enrichr service | Background gene set; list leaves the machine |
| `archs4`, `bgee`, `cellxgene` | Tissue expression, orthologs, single-cell data | Different normalizations; do not mix values |
| `opentargets`, `cbio`, `cosmic` | Disease, drug and cancer annotations | COSMIC needs an account and a license for commercial use |

## Idioms

```bash
gget ref -r 112 -w gtf,dna homo_sapiens -o ref_links_e112.json     # pinned release, saved to file
gget search -s homo_sapiens -r 112 "tumor protein p53" -csv -o search.csv
gget info ENSG00000141510 -o tp53_info.json
gget seq -t ENSG00000141510 -o tp53_protein.fa                      # canonical protein
```

```python
import gget

info = gget.info(["ENSG00000141510", "ENSG00000012048"])     # DataFrame
seqs = gget.seq(["ENSG00000141510"], translate=True)          # list of FASTA lines
```

- Save every result with `-o` (or write the DataFrame) and record the gget version, the module, the database release and the date. A rerun next month can return different rows.
- IDs carry versions (`ENST00000269305.9`); keep them when the exact transcript matters, strip them for joins.
- Gene symbols are case-sensitive in some modules (human `TP53`, mouse `Trp53`); species must be explicit.

## Failure modes to expect

| Symptom | Cause and fix |
|---|---|
| A module worked last month and now errors or returns empty results | The remote service changed its layout. Upgrade the package, and check the module's documentation for a replacement |
| Empty result for a gene you know exists | Wrong species, wrong case, or a symbol that is an alias; search by ID instead |
| Timeouts or refused connections on a batch loop | Rate limiting; add delays, reduce batch size, or switch to a bulk download |
| Different answers for the same query | The underlying database was updated; pin a release where the module supports it, and record the date |
| A module asks for a setup step | It needs extra dependencies or data files; check what it downloads before running it |

Wrap lookups that feed a pipeline in explicit error handling, and fail loudly rather than continuing with an empty table.

## Enrichment, done carefully

- Enrichment is only as good as its background. A list of genes expressed in one tissue tested against the whole genome comes out enriched for that tissue's biology every time. Use a background of genes that could have been detected in the experiment when the tool supports it; otherwise state the limitation.
- Report the library and its release, the adjusted p-value method, the overlap counts, and the input list size.
- For publication-grade analyses, run enrichment locally with pinned gene-set files (for example with `gseapy` or a hypergeometric test you control) and a defined background.

## Privacy and terms

- `blast`, `blat`, `enrichr` and other remote modules send your sequences or gene lists to third-party servers. Ask before sending unpublished, proprietary or human-identifying data.
- Any module that forwards text to a hosted language model sends your prompt to that provider; do not use it with sensitive data, and prefer answering from verified sources.
- Each underlying database has its own license and citation request. Check the terms before redistributing downloaded data or using it commercially.

## Checks (done when)

- [ ] Every lookup result is saved with gget version, module, database release and date.
- [ ] Search hits were checked by ID and description, not accepted by rank.
- [ ] Enrichment states its background, library release and correction method.
- [ ] No sensitive sequence or gene list went to a remote service without permission.
- [ ] Anything that will be rerun later uses pinned downloads, not live lookups.
