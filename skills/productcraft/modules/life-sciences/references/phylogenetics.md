# Phylogenetics: alignment, tree inference and tree handling

Read this when you build a tree from sequences (multiple alignment, trimming, maximum likelihood inference, support values, rooting), compare or annotate trees, map taxonomy, or analyze gene trees for duplications with the ETE toolkit. Pairwise alignment and file parsing are in `biopython.md`; diversity metrics that use trees are in `microbiome-scikit-bio.md`.

## Tools

| Step | Default choice | Alternatives |
|---|---|---|
| Multiple alignment | MAFFT | MUSCLE 5, Clustal Omega; codon-aware: align proteins then back-translate, or MACSE |
| Trimming (optional) | trimAl or ClipKIT, gently | No trimming for short, clean alignments |
| Maximum likelihood tree | IQ-TREE (2.x, or 3.x where installed) | RAxML-NG; FastTree for very large sets |
| Dating | Least-squares dating in IQ-TREE, TreeTime | BEAST 2 for Bayesian dating |
| Recombination screen | GARD, 3SEQ; Gubbins or ClonalFrameML for bacterial genomes | |
| Tree handling in Python | ETE toolkit | Bio.Phylo, DendroPy, scikit-bio `TreeNode` |

Install command-line tools from Bioconda in a dedicated environment and record their versions (`mafft --version`, `iqtree2 --version`). Several (IQ-TREE, ETE) are GPL-licensed, which matters when they are bundled into distributed software.

## 1. Alignment

```bash
mafft --auto --thread 8 seqs.fa > aln.fa                              # picks a strategy by size
mafft --localpair --maxiterate 1000 --thread 8 seqs.fa > aln.linsi.fa # accurate, for up to a few hundred sequences
mafft --add new.fa --keeplength --thread 8 ref_aln.fa > aln.plus.fa   # add sequences to an existing alignment
```

- Coding sequences: align at the protein level and back-translate so codons stay intact; nucleotide alignment of divergent coding sequences shifts frames.
- Look at the alignment (a viewer such as AliView or Jalview, or a quick column-gap summary). Misaligned or reverse-complemented sequences and long unaligned tails are common and change the tree.
- Remove exact duplicates (keep one, record the mapping); identical sequences add time and no information.

## 2. Trimming

Trimming removes columns that are mostly gaps or poorly aligned. Aggressive trimming can remove real signal and make trees worse. Use a moderate setting (for example trimAl `-gappyout` or ClipKIT's default), and compare the tree with and without trimming when results matter.

## 3. Inference with IQ-TREE

```bash
iqtree2 -s aln.fa -m MFP -B 1000 -alrt 1000 -T AUTO --seed 20261027 --prefix run1
```

- `-m MFP` runs ModelFinder and uses the best model by BIC; the chosen model is in `run1.iqtree`. Report it. (`-m TEST` restricts the search to an older, smaller model set.)
- `-B 1000` gives ultrafast bootstrap support; `-alrt 1000` adds the SH-aLRT test. IQ-TREE's documentation treats a branch as well supported around UFBoot of at least 95 together with SH-aLRT of at least 80. Ultrafast values are not standard bootstrap percentages: do not apply the 70% rule of thumb for standard bootstrap to them.
- Under model violations, ultrafast support can be overconfident; `-bnni` reduces that.
- Multi-gene data: give a partition file (`-p partitions.nex`) so each gene gets its own model; concordance factors (`--gcf` with gene trees, `--scf` for sites) show how much of the data supports each branch, which bootstrap does not.
- Compare alternative topologies with the approximately unbiased test (`-z candidate_trees.nwk -zb 10000 -au`) rather than eyeballing likelihoods.
- Run at least two independent searches with different seeds; differing best trees mean a flat likelihood surface, which belongs in the report.

### Very large alignments

FastTree is much faster for many thousands of sequences, at some cost in accuracy:

```bash
FastTree -gtr -nt aln.fa > tree.fasttree.nwk      # nucleotides
FastTree -lg aln.fa > tree.fasttree.nwk           # proteins
```

Its support values are local SH-like supports on a 0 to 1 scale, not bootstrap percentages.

## 4. Rooting

- Inference produces unrooted trees. Root with an outgroup known to fall outside the group of interest (IQ-TREE `-o taxon`, or reroot afterwards).
- Midpoint rooting assumes roughly equal rates across lineages; say when you used it and why no outgroup was available.
- Root-to-tip regression (TreeTime, TempEst) checks whether sampling dates carry a clock signal before any dating.

## 5. Common traps

| Trap | Fix |
|---|---|
| Recombinant sequences (viruses, bacteria) treated as one tree | Screen for recombination; analyze segments, or mask recombinant regions |
| Long-branch attraction (fast lineages grouping together) | Better models, more taxa breaking long branches, outgroup checks |
| Saturated third codon positions in deep divergences | Partition by codon position or use amino acids |
| Support read as probability that a clade is true | Report the method and thresholds; support measures data consistency, not truth |
| Tree from a single gene presented as the species tree | Gene trees differ from species trees; use many loci and say which tree it is |

## Tree handling with the ETE toolkit

ETE has two lines: `ete3` (long-standing, widely used) and `ete4` (released 2024, with API changes such as how Newick flavors are selected and how node properties are stored). Check which is installed (`import ete3` or `import ete4`) and use that version's documentation.

```python
from ete3 import Tree

t = Tree("run1.treefile", format=1)        # format 1: internal labels read as names
for node in t.traverse():
    if not node.is_leaf() and node.name:
        alrt, ufboot = (float(x) for x in node.name.split("/"))   # IQ-TREE writes "SH-aLRT/UFBoot"
        node.add_features(alrt=alrt, ufboot=ufboot)

t.set_outgroup(t & "Outgroup_taxon")
t.prune(["A", "B", "C", "D"], preserve_branch_length=True)
t.write(outfile="rooted.nwk", format=1)
```

- Newick dialects differ (support versus names in internal labels, quoted names, NHX tags). Read with the format that matches the file, and check the number of leaves and a couple of support values after loading.
- `prune` without `preserve_branch_length=True` changes distances.
- Robinson-Foulds distance between trees (`t1.robinson_foulds(t2, unrooted_trees=True)`) compares topologies; normalize by the maximum and compare trees on the same leaf set.

### Taxonomy

```python
from ete3 import NCBITaxa
ncbi = NCBITaxa()                     # first use downloads the NCBI taxonomy dump into a local database
taxid = ncbi.get_name_translator(["Homo sapiens"])["Homo sapiens"][0]
lineage = ncbi.get_taxid_translator(ncbi.get_lineage(taxid))
```

The local database is a snapshot; record when it was downloaded (`update_taxonomy_database()` refreshes it). Taxonomy changes over time: names are merged and reassigned, so store taxon IDs, not just names.

### Gene trees, duplications and orthologs

`PhyloTree` with a species-naming function labels internal nodes as duplication or speciation by species overlap. This is a heuristic: it depends on the gene tree being right and on correct species parsing from leaf names. For genome-scale orthology, use a dedicated method (for example OrthoFinder) and use ETE for inspection.

### Drawing

ETE's renderer needs Qt; on a headless server set `QT_QPA_PLATFORM=offscreen` or run under `xvfb-run`. Alternatives: Bio.Phylo with matplotlib, toytree, or a web viewer (upload only non-sensitive trees). Show support values and a scale bar with units (substitutions per site).

## Checks (done when)

- [ ] Alignment inspected; strategy, trimming and tool versions recorded.
- [ ] Model selection result, support methods and thresholds reported.
- [ ] Two or more searches with different seeds agree, or disagreement is reported.
- [ ] Root justified (outgroup named, or midpoint with its assumption stated).
- [ ] Recombination considered for viral or bacterial data.
- [ ] Trees loaded in Python have the expected leaf count and correctly parsed supports.
