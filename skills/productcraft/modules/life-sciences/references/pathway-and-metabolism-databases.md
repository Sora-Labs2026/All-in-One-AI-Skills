# Pathway, metabolite and enzyme databases

Read this when a task maps genes or metabolites to pathways, runs pathway enrichment, looks up human metabolites, searches public metabolomics studies, or needs enzyme kinetics: Reactome, KEGG, HMDB, Metabolomics Workbench and BRENDA. Shared rules are in `bio-data-access.md`. GO enrichment and ontology handling are in `biomedical-ontologies.md`; metabolic models in `metabolic-modeling.md`; spectra processing in `mass-spectrometry.md`.

## Which resource answers the question

| Question | Use | License note |
|---|---|---|
| Curated human pathways and reactions; enrichment with an open license | Reactome (also WikiPathways) | Open |
| KEGG maps, KEGG Orthology, organism-specific metabolic pathways and modules | KEGG | Academic only without a paid license |
| Human metabolite facts: structures, biofluid concentrations, spectra, pathways | HMDB | Commercial use needs permission |
| Public metabolomics studies, standardized metabolite names, m/z lookups | Metabolomics Workbench (RefMet) | Open, cite studies |
| Enzyme kinetics (Km, kcat, Ki), substrates, organisms, EC data | BRENDA (also SABIO-RK) | Attribution |

## Enrichment practice for any pathway source

- The background is the set of genes or metabolites your experiment could measure, not the whole genome or the whole database. A wrong background produces confident nonsense.
- Pin the pathway release and the identifier type, and report how many inputs failed to map.
- Report set size, overlap, raw and adjusted p-values (Benjamini-Hochberg unless the method defines its own) and the test used. Overlapping pathways repeat the same genes, so group redundant hits before interpreting them.
- Over-representation needs a cutoff list; ranked methods (GSEA, `fgsea`) use every gene's statistic and avoid the arbitrary cutoff. Pick one before looking at results.
- For publication analyses, run enrichment locally on downloaded gene-set files of a pinned release. Web services are for exploration (`gget.md` covers quick checks).

## Reactome

- **What it holds:** expert-curated human pathways and reactions, projected to other species by orthology. Stable IDs encode the species: `R-HSA-69620` (human); versioned forms add `.N`.
- **Content Service** (`https://reactome.org/ContentService/`): entity and pathway queries, for example `/data/query/R-HSA-69620`, `/data/mapping/UniProt/P04637/pathways` and `/data/database/version` for the release.
- **Analysis Service** (`https://reactome.org/AnalysisService/`): POST a newline-separated identifier list to `/identifiers/projection` (maps non-human identifiers to human pathways). The result carries a `token`; tokens expire, so save the full result (JSON or the CSV download) at once.

```python
import requests

ids = "\n".join(["P04637", "P38398", "Q13315"])          # UniProt accessions map more cleanly than symbols
r = requests.post("https://reactome.org/AnalysisService/identifiers/projection",
                  data=ids, headers={"Content-Type": "text/plain"}, timeout=120,
                  params={"interactors": "false", "pageSize": 50, "page": 1})
r.raise_for_status()
res = r.json()
print("not found:", res.get("identifiersNotFound"), "token:", res["summary"]["token"])
for p in res["pathways"][:10]:
    e = p["entities"]
    print(p["stId"], p["name"], e["found"], e["total"], e["fdr"])
```

- **Bulk:** the download page has identifier-to-pathway tables (`UniProt2Reactome.txt`, `Ensembl2Reactome.txt`, `NCBI2Reactome.txt`, in lowest-level and all-levels variants), a GMT gene-set file, BioPAX and SBML exports and a graph database dump.
- **Releases** are quarterly (release 94 was September 2025). The `reactome2py` package is not actively maintained; call the REST services directly.
- **License:** CC BY 4.0.

## KEGG

- **Identifiers:** reference pathways `map00010`, organism pathways `hsa04110`, orthology pathways `ko04110`; genes `hsa:7157` (organism code plus, for human, the NCBI Gene ID); orthologs `K04451`; compounds `C00031`; drugs `D00109`; reactions `R00200`; modules `M00001`; enzymes `ec:2.7.1.1`.
- **REST:** `https://rest.kegg.jp/<operation>/<arguments>` with `info`, `list`, `find`, `get`, `conv`, `link` and `ddi`. Responses are tab-separated text or flat-file entries.
  - `get` takes at most 10 entries per call, and only one for images, KGML or JSON.
  - `link/pathway/hsa` lists every human gene-pathway link in one call; `conv/ncbi-geneid/hsa` maps KEGG genes to NCBI Gene IDs.
  - `info/kegg` reports the current release; record it.
- **Throttle:** no published per-second limit. Keep to a few requests per second, cache everything, and expect blocking under heavy use.
- **License, plainly:**
  - The KEGG website and REST API are free for academic use by academic users.
  - Commercial use requires a paid license, and so does bulk download through the KEGG FTP service.
  - KEGG data may not be redistributed.
  - Enrichment packages that call the KEGG API at runtime fall under the same terms.
  - For a commercial product or redistributed dataset, use Reactome or WikiPathways (CC0) instead and say why.

## HMDB

- **Identifiers:** `HMDB0000122` (seven digits; D-glucose). Older five-digit IDs such as `HMDB00122` map by zero-padding to seven digits. Match metabolites across sources by InChIKey, not by name.
- **What it holds:** structures, biofluid and tissue concentrations with references, experimental and predicted NMR and MS spectra, pathways and disease links (version 5.0 at the time of writing).
- **Access:** no public REST API. Use the bulk downloads (XML, SDF, spectra) and parse locally; do not scrape the website. The full XML is several gigabytes, so stream it:

```python
from lxml import etree

NS = "{http://www.hmdb.ca}"
for _, el in etree.iterparse("hmdb_metabolites.xml", tag=f"{NS}metabolite"):
    acc, key = el.findtext(f"{NS}accession"), el.findtext(f"{NS}inchikey")
    # ... collect fields ...
    el.clear()
    while el.getprevious() is not None:       # free memory for already-processed siblings
        del el.getparent()[0]
```

- **Pitfalls:** predicted spectra sit next to experimental ones, so label which you used. Concentration units and specimen types vary per record. Names and synonyms are ambiguous across isomers.
- **License, plainly:** free for academic and non-commercial use with citation. Commercial use, and redistribution of the data in whole or in part, needs explicit permission from the HMDB authors.

## Metabolomics Workbench

- **What it holds:** the NIH Common Fund repository of metabolomics studies (`ST000001`), analyses (`AN000001`) and projects (`PR000001`), raw and processed MS and NMR data, and RefMet, a standardized metabolite nomenclature.
- **REST:** `https://www.metabolomicsworkbench.org/rest/{context}/{input item}/{input value}/{output item}/{format}` with contexts `study`, `compound`, `refmet`, `gene`, `protein`, `moverz` and `exactmass`. Examples: `/rest/study/study_id/ST000001/summary`, `/rest/refmet/name/Cholesterol/all`. The `moverz` context searches m/z values against a chosen database with an ion type and tolerance; read the documentation for its argument order.
- **Names:** map author or vendor metabolite names to RefMet names before comparing studies; report unmatched names.
- **Files:** study data in mwTab format (the `mwtab` Python package parses it). Studies can be embargoed until publication.
- **Terms:** public data; cite the study (and its DOI where one is assigned) and the Workbench.

## BRENDA

- **What it holds:** enzyme function by EC number and organism, with kinetic values (Km, kcat, Ki, specific activity), substrates, inhibitors, pH and temperature data, all extracted from the literature.
- **Access:** a SOAP API (WSDL `https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl`, used with `zeep`) after free registration. Every call starts with the account email and the SHA-256 hash of the password, taken from environment variables. Parameters are `field*value` strings with `*` as a wildcard. The full database can also be downloaded as text or JSON after accepting the license. Keep sustained use to about one request per second.

```python
import hashlib, os
from zeep import Client

client = Client("https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl")
auth = (os.environ["BRENDA_EMAIL"], hashlib.sha256(os.environ["BRENDA_PASSWORD"].encode()).hexdigest())
km = client.service.getKmValue(*auth, "ecNumber*1.1.1.1", "organism*Homo sapiens", "kmValue*",
                               "kmValueMaximum*", "substrate*", "commentary*",
                               "ligandStructureId*", "literature*")
```

- **Pitfalls:**
  - Values come from different conditions, mutants and non-natural substrates; the commentary field says which.
  - Units differ (Km usually in mM, kcat in 1/s).
  - The same value can appear through several papers.
  - Before using a value in a kinetic model, open the cited paper and confirm the conditions.
  - SABIO-RK offers kinetic laws with conditions through an open REST API and is a useful cross-check.
- **License:** CC BY 4.0 since the 2023 release; confirm on the site and cite the BRENDA paper it names.

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| Every tissue-specific gene list "enriches" for that tissue | Genome background; use the detectable-gene background |
| Many inputs unmapped in Reactome | Symbols or unversioned IDs of another species; submit UniProt or Ensembl IDs and use projection |
| KEGG calls start failing | Throttling or blocking; cache, slow down, and for scale move to licensed bulk access or open sources |
| HMDB ID "not found" | Legacy five-digit form; zero-pad to seven digits |
| Kinetic parameters disagree by orders of magnitude | Mixed organisms, mutants, substrates or units; filter on the commentary and check the source paper |

## Checks (done when)

- [ ] Pathway source, release, identifier type, background and unmapped count are reported for every enrichment.
- [ ] KEGG and HMDB use was checked against the intended use; any commercial or redistribution use was flagged to the user.
- [ ] Metabolites were matched across sources by InChIKey or RefMet name, with unmatched names listed.
- [ ] Every kinetic value used carries its organism, substrate, conditions and source reference.
- [ ] Reactome results were saved in full, not only as a token.
