# Ontologies: term lookup, mapping and validation

Read this when a task annotates data with ontology terms (diseases, phenotypes, anatomy, cell types, gene function, chemicals, units, assays), maps terms between vocabularies, checks annotations against an ontology, or parses and navigates OWL, OBO or other RDF ontology files. The techniques are domain-neutral and apply equally to ontologies outside biology, such as materials-science ontologies for samples and simulations. Shared rules are in `bio-data-access.md`.

## Ontologies you will meet

| Domain | Ontology | Example ID | Notes |
|---|---|---|---|
| Gene function | Gene Ontology (GO) | `GO:0006915` apoptotic process | Three aspects (process, function, component); annotations ship separately as GAF or GPAD |
| Human phenotypes | HPO | `HP:0001250` seizure | Clinical features sit under `HP:0000118` (phenotypic abnormality); own license |
| Diseases | Mondo | `MONDO:0007739` Huntington disease | Curated equivalences to OMIM, Orphanet, DOID, NCIt and ICD |
| Diseases and traits | DOID, EFO, NCIt, Orphanet (ORDO) | `EFO:0001360` type 2 diabetes | EFO is used by the GWAS Catalog and Open Targets |
| Anatomy | UBERON | `UBERON:0002107` liver | Cross-species |
| Cell types | Cell Ontology (CL) | `CL:0000236` B cell | Used by single-cell atlases |
| Chemicals | ChEBI | `CHEBI:15422` ATP | |
| Sequence features and variant effects | Sequence Ontology (SO) | `SO:0001583` missense_variant | VEP consequence terms are SO terms |
| Taxonomy | NCBITaxon | `NCBITaxon:9606` | |
| Units, evidence, assays | UO, ECO, OBI | | |
| Clinical terminologies | SNOMED CT, ICD-10-CM, ICD-11, LOINC, MeSH, MedDRA, UMLS | | Several need license agreements: SNOMED CT (affiliate license), MedDRA (subscription), UMLS (license agreement); check each one's terms |

Most open biomedical ontologies are coordinated through the OBO Foundry, use CURIEs such as `GO:0006915` and resolve through PURLs (`http://purl.obolibrary.org/obo/GO_0006915`).

## Identifier forms

- **CURIE** `HP:0001250` is the form to store. The **IRI** is `http://purl.obolibrary.org/obo/HP_0001250`, and the **short form** `HP_0001250` (with an underscore) appears in OLS and Open Targets. Convert deliberately at the boundary.
- **Digits are zero-padded and significant.** Spreadsheets turn `GO:0006915` into nonsense or strip zeros from bare numbers. `../scripts/bio_id_check.py` flags `GO:6915`, lowercase prefixes and underscore forms.
- **Store IDs, display labels.** Labels and synonyms change between releases; IDs persist, and obsolete IDs are deprecated with a pointer to their replacement.

## Term lookup

| Route | Use for | Notes |
|---|---|---|
| OLS (EMBL-EBI Ontology Lookup Service, OLS4) | Search across hundreds of ontologies; term details and hierarchy | `https://www.ebi.ac.uk/ols4/api/search?q=seizure&ontology=hp&rows=20`; a term by IRI needs the IRI double URL-encoded in the path |
| BioPortal | Broad coverage including clinical terminologies | Free API key; license terms of each terminology still apply |
| Ubergraph | SPARQL over integrated OBO ontologies with precomputed inferences | Good for "all descendants that are also part of X" questions |
| Local release files with OAK (`oaklib`) or `pronto` | Pipelines, repeated lookups, pinned versions | No rate limits; the version is the file |

```bash
pip install oaklib
runoak -i sqlite:obo:hp info HP:0001250            # label, definition (downloads a prebuilt SQLite on first use)
runoak -i sqlite:obo:hp ancestors HP:0001250 -p i  # is_a ancestors
runoak -i sqlite:obo:hp search "seizure"
```

Lookup rules:
- Match on labels and **exact** synonyms. Narrow, broad and related synonyms are not equivalents.
- Reject or replace obsolete terms (`owl:deprecated true`); follow "term replaced by" (`IAO:0100001`) and review "consider" suggestions by hand.
- Check that the term sits in the expected branch: a phenotype column takes terms under `HP:0000118`, not inheritance modes; a cell-type column takes CL terms only; a GO annotation of a process uses a biological-process term.
- Record the ontology and its version (`owl:versionIRI`, or the dated release file) with every annotation set.

## Mapping between vocabularies

- **Sources, best first:**
  1. Curated mappings published by an ontology (Mondo's equivalence mappings, SSSOM files).
  2. Licensed metathesauri (UMLS).
  3. Cross-references in ontology files (`oboInOwl:hasDbXref`), which mix exact, broad and loosely related links.
  4. Lexical matching (OAK `lexmatch`), which only produces candidates.
- **Store mappings as SSSOM**: a TSV with `subject_id`, `predicate_id` (`skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`, `skos:narrowMatch`, `skos:relatedMatch`), `object_id`, `mapping_justification` (for example `semapv:ManualMappingCuration` or `semapv:LexicalMatching`), confidence, author and the versions of both vocabularies.

```text
subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	confidence
local:dx_017	Huntington chorea	skos:exactMatch	MONDO:0007739	Huntington disease	semapv:ManualMappingCuration	0.95
```

- **Rules:**
  - Use `exactMatch` only when the meanings are the same; keep broad and narrow mappings as such.
  - Do not chain mappings (A to B to C) without review; meaning drifts at every hop.
  - Expect one-to-many results (one ICD code to several Mondo diseases) and decide per use.
  - Have a person review lexical matches, or label them unreviewed.
  - A mapping is bound to both versions; re-check it when either vocabulary releases.
  - Report exact, close, broad or narrow, and unmapped counts.

## Validation

Two different jobs: checking **data that uses terms**, and checking **an ontology file** you author or extend.

### Annotations (data)

1. Every ID is well-formed (prefix, digit count).
2. Every ID exists in the pinned release and is not obsolete.
3. Every ID sits in the expected branch or namespace.
4. The label stored next to an ID matches the ontology's label for it (catches copy-paste errors).
5. One ontology version per dataset.

Constraints on the shape of instance data are better expressed as schemas than as code:
- **SHACL** shapes, checked with `pyshacl`, for RDF data: required properties, datatypes, cardinality, value ranges, and class membership of objects (domain and range).
- **LinkML** schemas for tabular, JSON or YAML data, with enumerations bound to ontology branches.
- Domain rules that OWL does not express go into SHACL or code with explicit messages. Examples: a cubic unit cell has equal edge lengths and right angles; a space-group number lies between 1 and 230; a dose has a unit from UO.

### Ontology files

```bash
robot reason --reasoner ELK --input my-ontology.owl --output reasoned.owl     # consistency, unsatisfiable classes
robot report --input my-ontology.owl --fail-on ERROR --output report.tsv      # labels, definitions, duplicates
robot validate-profile --profile DL --input my-ontology.owl --output profile.txt
robot diff --left v1.owl --right v2.owl --output changes.txt
```

- ELK is fast but covers only the OWL EL profile; use HermiT (through ROBOT or `owlready2`, which bundles HermiT and Pellet and needs Java) when axioms go beyond EL.
- Do not edit a published ontology for your project. Extend it in your own namespace and import it, or request the change upstream.

## Parsing and navigating in code

| Tool | Good for | Notes |
|---|---|---|
| `oaklib` (OAK) | One interface over local files, SQLite builds, OLS, BioPortal and Ubergraph; search, ancestors, lexical matching, diffs, validation | Python API and `runoak` CLI |
| `pronto` | OBO files and OBO-style OWL; quick hierarchy and synonym access | Pure Python |
| `rdflib` | Any RDF serialization (RDF/XML, Turtle, JSON-LD, N-Triples); SPARQL | No reasoning; slow for very large ontologies |
| `owlready2` | OWL object model and reasoning | LGPL; loads the whole ontology into memory |
| ROBOT (Java) | Conversion, merging, reasoning, reports, module extraction | The standard OBO tool chain |

```python
from rdflib import BNode, Graph, OWL, RDF, RDFS

g = Graph().parse("ontology.owl")                       # format inferred; pass format="xml" or "turtle" if needed
label = {s: str(o) for s, o in g.subject_objects(RDFS.label)}

classes = {c for c in g.subjects(RDF.type, OWL.Class) if not isinstance(c, BNode)}
parents = {c: [p for p in g.objects(c, RDFS.subClassOf) if not isinstance(p, BNode)] for c in classes}
roots = sorted(label.get(c, str(c)) for c, ps in parents.items() if not ps)

for prop in g.subjects(RDF.type, OWL.ObjectProperty):
    dom, rng = g.value(prop, RDFS.domain), g.value(prop, RDFS.range)
    # a BNode here is a class expression (for example owl:unionOf); expand it before reporting
    print(label.get(prop, prop), "|", label.get(dom, dom), "->", label.get(rng, rng))
```

- Blank nodes under `rdfs:subClassOf` are restrictions (`someValuesFrom` and similar), not parent classes; skip or expand them explicitly.
- Release variants differ. OBO projects publish a *base* file (only the ontology's own axioms), a *full* file (imports merged, reasoned) and a *simple* file (subclass hierarchy only). Use full for navigation and base for merging several ontologies.
- `owl:imports` pulls other files by IRI. Offline parsing needs the merged release or a catalog file that maps IRIs to local copies.

## Gene Ontology annotations and enrichment

- Annotations (GAF or GPAD per species, or through QuickGO) carry evidence codes. Electronic annotations (IEA) dominate many genomes; report whether they were included.
- `NOT` annotations say a gene does **not** have the function. Drop them before propagation, never count them.
- Propagate annotations up `is_a` and `part_of` only; `regulates` relations do not imply the parent function.
- The ontology release and the annotation release are versioned separately; record both. Enrichment rules (background, multiple testing) are in `pathway-and-metabolism-databases.md`.

## Checks (done when)

- [ ] Every ontology used is named with its version IRI or release date.
- [ ] All annotation IDs are well-formed, current, non-obsolete and in the expected branch; label mismatches were listed.
- [ ] Mappings are stored as SSSOM with predicates, justifications and both versions; lexical matches are marked reviewed or unreviewed.
- [ ] Instance-data constraints run as SHACL or LinkML validation, with the report attached.
- [ ] Authored or modified ontologies pass `robot reason` and `robot report` with no errors.
- [ ] Clinical terminologies were used only under a license that covers the use.
