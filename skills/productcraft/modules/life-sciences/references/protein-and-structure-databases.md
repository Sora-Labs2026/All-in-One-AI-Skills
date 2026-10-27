# Protein, domain, structure and interaction databases

Read this when a task needs protein function, sequences, isoforms or cross-references (UniProt), domain and family annotation (InterPro, Pfam), experimental structures (PDB), predicted structures (AlphaFold DB) or interaction networks and enrichment (STRING). Shared rules are in `bio-data-access.md`. Parsing structure files is in `biopython.md`; protein language models and docking are in `protein-language-models.md` and `docking.md`.

## Which resource answers the question

| Question | Use |
|---|---|
| What does this protein do; its sequence, isoforms, modifications, GO terms, cross-references | UniProtKB |
| Which domains or family does a known protein have | InterPro entries for its UniProt accession |
| Which domains does a new sequence have | InterProScan (local, or the EBI job service for a few sequences) |
| Is there an experimental 3D structure; at what resolution | PDB (RCSB, PDBe or PDBj) |
| No experimental structure; a predicted model will do | AlphaFold DB |
| Interaction partners, functional networks, enrichment of a protein list | STRING |

## UniProt

- **Entries:** UniProtKB has reviewed Swiss-Prot entries (manually curated) and unreviewed TrEMBL entries (automatic). Prefer reviewed entries or a reference proteome (`UP000005640` is human) unless coverage matters more than quality.
- **Identifiers:** accessions (`P04637`, or 10 characters such as `A0A023GPI8`) are stable; entry names (`P53_HUMAN`) are mnemonics that can change, so never key on them. Isoforms are `P04637-2`. Merged or split entries leave secondary accessions; the API redirects them, and the `sec_acc` field lists them. UniParc (`UPI...`) archives sequences; UniRef clusters are `UniRef90_P04637`.
- **REST:** `https://rest.uniprot.org/uniprotkb/search` with `query`, `fields`, `format` (`tsv`, `json`, `fasta`) and `size` (up to 500) returns pages; the `Link` header carries the next cursor and `X-Total-Results` the total. `/uniprotkb/stream` returns everything in one response, which is simpler but fails all at once on a dropped connection. Single entries: `/uniprotkb/P04637.json` or `.fasta`.
- **Query syntax:** `gene_exact:TP53 AND organism_id:9606 AND reviewed:true`. Use `organism_id` (taxonomy ID) rather than organism names, and `gene_exact` rather than `gene` when you mean that symbol.
- **ID mapping:** POST `/idmapping/run` with `from`, `to` and comma-separated `ids` (plus `taxId` when mapping gene names), poll `/idmapping/status/{jobId}`, then read `/idmapping/results/{jobId}` or the `stream` variant. Jobs have size limits and results expire after some days; split very large lists and save results immediately. Count unmapped and one-to-many results.
- **Releases:** roughly every eight weeks, named like `2025_04`. Read `X-UniProt-Release` from responses. For reproducibility, download the release files (FASTA, flat files) or store API results with the release.
- **License:** CC BY 4.0.

```python
import re, requests

def uniprot_tsv(query, fields="accession,id,gene_primary,organism_id,length", size=500):
    """Return (release, header, rows) for a UniProtKB query, following cursor links."""
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {"query": query, "fields": fields, "format": "tsv", "size": size}
    release, header, rows, total = None, None, [], None
    while url:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        release = release or r.headers.get("X-UniProt-Release")
        total = total or r.headers.get("X-Total-Results")
        lines = r.text.splitlines()
        if lines:
            header = header or lines[0]
            rows.extend(lines[1:])
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", ""))
        url, params = (nxt.group(1), None) if nxt else (None, None)
    if total is not None and int(total) != len(rows):
        raise RuntimeError(f"expected {total} rows, got {len(rows)}")
    return release, header, rows
```

## InterPro and Pfam

- **What it is:** InterPro integrates member databases (Pfam, PROSITE, SMART, PANTHER, CDD, PRINTS, PIRSF, HAMAP, SFLD, SUPERFAMILY, CATH-Gene3D, NCBIfam) into `IPR` entries typed as family, domain, homologous superfamily, repeat or site. Pfam's own website was retired in 2023; Pfam entries (`PF00870`) and clans are served through InterPro.
- **API:** `https://www.ebi.ac.uk/interpro/api/` composes a main endpoint with filters. Examples: `/entry/interpro/protein/uniprot/P04637` (InterPro entries matching a protein), `/protein/uniprot/entry/pfam/PF00870/?page_size=200` (proteins carrying a Pfam domain), `/entry/pfam/PF00870`. Follow the `next` URL for pages (page size up to 200). Very broad queries can time out; narrow by taxonomy or use bulk files.
- **New sequences:** run InterProScan locally (Java, with a large data download) for more than a handful of sequences. Its version string pairs software and data (`5.NN-MM.0` names the InterPro release `MM`), so recording it pins both.
- **Bulk:** per-release files such as `protein2ipr.dat.gz`, `entry.list` and `interpro2go` on the EBI FTP site.
- **Caveat:** GO terms derived from InterPro (`interpro2go`) are electronic annotations (evidence code IEA). Label them so, and do not count them as experimental evidence.
- **License:** CC0.

## PDB

- **Archive:** the wwPDB archive is served by RCSB PDB (US), PDBe (Europe) and PDBj (Japan), updated weekly (Wednesdays, 00:00 UTC).
- **Identifiers:** four characters, first a digit 1-9 (`4HHB`), case-insensitive. Extended IDs (`pdb_00004hhb`) are being introduced as four-character IDs run out; accept both. Ligand chemical component IDs are three characters, and longer IDs are now issued. Author chain IDs (`auth_asym_id`) and label chain IDs (`label_asym_id`) differ; say which one you use.
- **RCSB APIs:**
  - Search API v2: POST JSON queries to `https://search.rcsb.org/rcsbsearch/v2/query` (full text, attributes, sequence similarity, structure similarity, chemical similarity).
  - Data API: REST `https://data.rcsb.org/rest/v1/core/entry/4HHB` and GraphQL `https://data.rcsb.org/graphql`.
  - Files: `https://files.rcsb.org/download/4HHB.cif`; biological assemblies such as `4HHB-assembly1.cif`.
  - Python: the official `rcsb-api` package (`rcsbapi.search`, `rcsbapi.data`).
- **Formats:** mmCIF (PDBx) is the archive format. Legacy PDB format cannot represent large structures (more than 99,999 atoms or 62 chains), and such entries have no PDB-format file. Parse with gemmi, Biotite or Biopython's `MMCIFParser`.
- **Quality before use:**
  - Check method, resolution and R-free (X-ray), map resolution (cryo-EM, which varies locally) and the wwPDB validation report (clashscore, Ramachandran and side-chain outliers).
  - Missing residues, alternate locations and crystallization additives posing as ligands are common.
  - The asymmetric unit is not the biological assembly; use the assembly files for interfaces.
- **Residue mapping:** map UniProt positions to PDB residues with SIFTS (per-residue mapping files from PDBe), not with your own alignment.
- **License:** CC0.

## AlphaFold DB

- **What it holds:** predicted monomer structures for most UniProtKB sequences. Entries are `AF-P04637-F1`; very long human proteins are split into overlapping fragments (`F1`, `F2`, ...).
- **API:** `https://alphafold.ebi.ac.uk/api/prediction/{UniProt accession}` returns JSON with the model URLs (`cifUrl`, `pdbUrl`, `paeDocUrl`) and the model version. Use those URLs rather than building file names with a hard-coded version suffix; model versions have advanced over time. Compare the model's sequence with the current UniProt sequence, which may have changed since prediction.
- **Confidence:** per-residue pLDDT (in the B-factor column): above 90 very high, 70 to 90 confident, 50 to 70 low, below 50 very low and often disordered. The predicted aligned error (PAE) matrix says whether the relative position of two domains is reliable; high inter-domain PAE means the arrangement is unknown.
- **Limits:**
  - Monomers only, with no ligands, cofactors, modifications or partners.
  - Low-pLDDT regions are not structures.
  - Comparing a mutant to a wild-type model does not predict the mutation's effect.
  - Say "predicted model" in every output.
- **Bulk:** per-proteome archives on the EBI FTP site and the Google Cloud public dataset; ask before multi-terabyte pulls. Foldseek searches structures at scale.
- **License:** CC BY 4.0; cite the AlphaFold and AlphaFold DB papers named on the site.

```python
import requests

def alphafold_models(accession):
    r = requests.get(f"https://alphafold.ebi.ac.uk/api/prediction/{accession}", timeout=60)
    if r.status_code == 404:
        return []                          # no prediction for this accession
    r.raise_for_status()
    return [{k: m.get(k) for k in ("entryId", "cifUrl", "paeDocUrl", "latestVersion")} for m in r.json()]
```

## STRING

- **What it holds:** functional association networks, not only physical binding. Evidence channels are experiments, curated databases, text mining, co-expression, genomic neighborhood, gene fusion and co-occurrence. The combined score runs 0 to 1000 (0 to 1 in API output). Common cutoffs: 150 low, 400 medium (default), 700 high, 900 highest. `network_type=physical` restricts to physical interactions.
- **Identifiers:** `9606.ENSP00000269305` (taxon ID, then the Ensembl protein ID). Map names first with `get_string_ids` and check each mapping before building a network.
- **API:** `https://string-db.org/api/{format}/{method}` with methods `get_string_ids`, `network`, `interaction_partners`, `enrichment`, `functional_annotation`, `ppi_enrichment`, `homology` and `version`. Send identifiers separated by `%0d` (newline), set `species`, add `caller_identity`, POST long lists and wait about a second between calls.
- **Reproducibility:** use the versioned host (`https://version-12-0.string-db.org/api/...`) and record the version from `/api/json/version`. Per-organism bulk files (`protein.links.detailed.v12.0.txt.gz`) are better for whole-network work.
- **Enrichment:**
  - The default background is the whole genome. Pass `background_string_identifiers` with the proteins your experiment could detect.
  - Text mining favors well-studied genes, which inflates their networks; check results with the text-mining channel excluded.
- **License:** CC BY 4.0.

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| UniProt query returns thousands of unreviewed entries | Add `reviewed:true` or restrict to a reference proteome |
| Accession "missing" from a new release | Merged or demerged entry; resolve through the redirect or secondary accessions |
| Residue numbers disagree between UniProt and PDB | Author numbering, tags and missing residues; use SIFTS |
| Interface analysis on the wrong oligomer | Used the asymmetric unit; load the biological assembly |
| AlphaFold file URL returns 404 | Hard-coded model version; take URLs from the API response |
| STRING network includes the wrong protein | Name mapped ambiguously; review `get_string_ids` output, then use STRING IDs |

## Checks (done when)

- [ ] UniProt release, query and reviewed or unreviewed status are recorded; accessions, not entry names, are stored.
- [ ] Domain annotations name the InterPro release (or InterProScan version) and mark electronic GO terms as IEA.
- [ ] Each PDB structure used has method, resolution and validation reviewed, and the choice of assembly and chain IDs is stated.
- [ ] AlphaFold models are labelled as predictions, with pLDDT and PAE considered for every region discussed.
- [ ] STRING results state the version, score cutoff, network type, evidence channels and background.
