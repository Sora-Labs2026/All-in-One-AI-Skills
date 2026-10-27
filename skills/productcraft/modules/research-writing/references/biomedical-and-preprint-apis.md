# Biomedical literature and preprint servers: PubMed, PMC, Europe PMC, arXiv, bioRxiv and medRxiv

Read this when searching or retrieving biomedical literature, full texts of open-access articles or preprints, or checking whether a preprint was later published. General scholarly APIs are in `scholarly-apis.md`; biological, chemical and clinical databases (genes, proteins, compounds, trials) are covered by `../../life-sciences/GUIDE.md`.

The client rules in `scholarly-apis.md` (identify yourself, keys by name, back off, cursors, cache) apply here too. Limits below were current in 2025-2026; check the provider's pages before bulk work.

## PubMed through NCBI E-utilities

Base URL `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`. The calls that matter:

| Call | Use |
|---|---|
| `esearch.fcgi?db=pubmed&term=...` | Run a query, get PMIDs and the count; `usehistory=y` stores the result set on the server |
| `esummary.fcgi?db=pubmed&id=...&retmode=json` | Light metadata for up to a few hundred PMIDs per call |
| `efetch.fcgi?db=pubmed&id=...&retmode=xml` | Full records (abstract, MeSH, publication types, DOI) |
| `elink.fcgi?dbfrom=pubmed&db=pubmed&id=...&linkname=pubmed_pubmed` | Similar articles; other link names give PMC full text or citing articles in PMC |
| `einfo.fcgi?db=pubmed` | Searchable fields and their tags |

Rules NCBI publishes:

- Send `tool` and `email` with every request. Without an API key the limit is 3 requests per second; with a key (from an NCBI account, passed as `api_key`) it is 10.
- Run large jobs on weekends or between 9 pm and 5 am US Eastern time on weekdays.
- `esearch` returns at most the first 10,000 PMIDs of a result set. For bigger sets, split the query by publication date ranges and merge.
- Fetch in batches (200 to 500 PMIDs per `efetch`) using `WebEnv` and `query_key` from the history server rather than pasting thousands of ids into a URL.
- For the whole database, use the annual baseline and daily update files from the NLM download service, not the API.

Biopython wraps this cleanly (`Bio.Entrez`; set `Entrez.email` and `Entrez.api_key` from environment variables). A standard-library version:

```python
import os, urllib.parse, urllib.request, json, xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
BASE = {"tool": "review-script", "email": os.environ["NCBI_EMAIL"]}
if os.environ.get("NCBI_API_KEY"):
    BASE["api_key"] = os.environ["NCBI_API_KEY"]

def eutil(name, **params):
    url = EUTILS + name + "?" + urllib.parse.urlencode({**BASE, **params})
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()

found = json.loads(eutil("esearch.fcgi", db="pubmed", retmode="json", retmax=0, usehistory="y",
                         term='("heart failure"[mh] OR "heart failure"[tiab]) AND sglt2[tiab] AND 2020:2025[dp]'))
res = found["esearchresult"]
print(res["count"], res.get("querytranslation"))        # always read the translation
xml = eutil("efetch.fcgi", db="pubmed", retmode="xml", retstart=0, retmax=200,
            WebEnv=res["webenv"], query_key=res["querykey"])
for art in ET.fromstring(xml).iter("PubmedArticle"):
    pmid = art.findtext(".//PMID")
    title = "".join(art.find(".//ArticleTitle").itertext())
    doi = next((e.text for e in art.iter("ELocationID") if e.get("EIdType") == "doi"), None)
    types = [t.text for t in art.iter("PublicationType")]
    if "Retracted Publication" in types:
        print("RETRACTED", pmid)
```

**Query syntax that changes results:**

- Field tags: `[ti]` title, `[tiab]` title and abstract, `[au]` author, `[mh]` MeSH heading (includes narrower terms), `[majr]` major MeSH topic, `[pt]` publication type, `[dp]` publication date, `[la]` language.
- PubMed rewrites untagged terms through automatic term mapping. Read `querytranslation` in the `esearch` response (or "Search details" on the website) to see what actually ran.
- MeSH indexing lags weeks to months behind publication and some records are never indexed. Pair every MeSH term with free-text `[tiab]` synonyms or the newest papers disappear.
- `humans[mh]` and similar filters remove records that are not yet indexed; apply them knowingly.
- XML pitfalls: `AbstractText` may come in several labeled parts (`Label="METHODS"`); titles and abstracts contain inline markup (`<i>`, `<sup>`), so join `itertext()`; the DOI sits in `ELocationID` or `ArticleIdList`, sometimes in neither.
- Retractions appear as publication type "Retracted Publication" on the original and "Retraction of Publication" on the notice, linked through `CommentsCorrectionsList`.

**Terms.** NLM metadata is free to use, but abstracts can be copyrighted by their publishers. Store PMIDs and fetch abstracts as needed rather than redistributing abstract collections.

## PubMed Central (PMC)

- Full text is reusable only for articles in the PMC Open Access subset or under an explicit license (CC BY, CC BY-NC and others, per article). Author manuscripts and other articles are free to read, not free to redistribute or mine at scale.
- Use the PMC OA web service, the BioC API for text mining, or the PMC cloud data on AWS for bulk access. Bulk downloading through the website violates PMC's terms and gets blocked.
- Convert between PMID, PMCID and DOI with the PMC ID converter service.

## Europe PMC

`https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=...&format=json&pageSize=1000&cursorMark=*` searches PubMed records plus preprints (`SRC:PPR`), patents, guidelines and Agricola, with open-access full text for part of the corpus. Useful extras: `/{source}/{id}/citations` and `/references`, `fullTextXML` for open-access articles, and text-mined annotations. It is often the easier route for preprint-plus-published searches in the life sciences.

## arXiv

- API: `https://export.arxiv.org/api/query?search_query=ti:"graph neural"+AND+cat:cs.LG&start=0&max_results=100&sortBy=submittedDate&sortOrder=descending` returns an Atom feed. Field prefixes: `ti`, `au`, `abs`, `cat`, `all`; lookup by id with `id_list=2103.14030`.
- Terms of use: no more than one request every three seconds, one connection at a time, and modest page sizes. For bulk metadata use OAI-PMH; for bulk full text use arXiv's requester-pays cloud buckets.
- Identifiers: `YYMM.NNNNN` since 2015 (four digits after the dot before that), with versions `v1`, `v2`; old-style ids look like `hep-th/9901001`. Cite the version you read when results changed between versions.
- Each paper carries its own license (the default arXiv license allows reading, not redistribution; some papers are CC BY). Check before redistributing PDFs or text.
- Published version: the `journal_ref` and `doi` fields are author-supplied and often missing; search Crossref or OpenAlex by title and authors to find the published article, and cite that when it exists, noting important differences.
- Moderation is not peer review. Say "preprint" whenever you cite one.

## bioRxiv and medRxiv

- Details by date range: `https://api.biorxiv.org/details/biorxiv/2025-01-01/2025-01-31/0` (cursor steps of 100); single preprint: `https://api.biorxiv.org/details/biorxiv/{doi}`. For medRxiv replace `biorxiv` with `medrxiv`.
- Published versions: `https://api.biorxiv.org/pubs/biorxiv/{interval}/{cursor}` links preprint DOIs to journal DOIs.
- The API returns metadata, not search ranking; for keyword search use Europe PMC (`SRC:PPR`) or OpenAlex and then fetch details here.
- Preprints are not peer reviewed. medRxiv states that clinical preprints should not guide clinical practice or be reported as established information; carry that caution into anything written from them. Check later versions and the published article: conclusions sometimes change.

## Trial registries

Registered protocols and results (ClinicalTrials.gov API v2, the WHO ICTRP search portal, EU CTIS) are essential for detecting unpublished trials and switched outcomes. Their APIs and data models are covered by `../../life-sciences/GUIDE.md`; from a literature review, record the registry id of each trial and compare registered with reported outcomes (`appraising-evidence.md`).

## Pitfalls

| Pitfall | Fix |
|---|---|
| Query returns 10,000 and stops | Split by date ranges; report the true count from `esearch` |
| Untagged terms mapped to something unexpected | Read `querytranslation`; tag terms explicitly |
| Only MeSH terms used | Add `[tiab]` synonyms for recent, unindexed records |
| Abstracts parsed with `.text` only | Join `itertext()` and handle labeled sections |
| Preprint cited as if published | Label it; look for the published version |
| PMC full text mined from non-OA articles | Restrict to the OA subset or licensed articles |
| arXiv hit with parallel requests | One connection, three seconds apart, or use OAI-PMH |

## Checks (done when)

- [ ] Queries recorded with their translated form, filters, date run and full count.
- [ ] Rate limits and time-of-day rules followed; keys and email taken from the environment.
- [ ] Retraction status checked for every PubMed record relied on.
- [ ] Preprints labeled as such, with version, and checked for a published version.
- [ ] Full text used only where the license allows the use made of it.
