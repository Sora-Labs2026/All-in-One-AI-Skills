# Scholarly metadata APIs: DOI resolution, Crossref, OpenAlex, Semantic Scholar, Unpaywall, DataCite, ORCID

Read this when code or an agent session needs to find papers, resolve or verify identifiers, follow citations, find legal open-access copies or count publications. Biomedical and preprint sources (PubMed, PMC, Europe PMC, arXiv, bioRxiv, medRxiv) are in `biomedical-and-preprint-apis.md`. How to check a reference against its record is in `citations-and-reference-managers.md`.

All of these services change limits, fields and authentication over time. The details below were current in 2025-2026; read the provider's documentation before a bulk job and trust the response headers over this file.

## Which source answers which question

| Question | Best first source | Why |
|---|---|---|
| Does this DOI exist, and what is it? | doi.org handle API, then content negotiation | Authoritative for every registration agency |
| Full metadata for a journal or book DOI | Crossref REST API | Publisher-deposited metadata, references, funders, update notices |
| Dataset or software DOI | DataCite REST API | DataCite registers most research data DOIs |
| Topic searches, counts by year, institutions, citation graph | OpenAlex | Open (CC0), broad coverage, filters and group-by |
| Paper search with relevance ranking, citation contexts, recommendations | Semantic Scholar Academic Graph | Good ranking for CS and biomedicine, batch lookups |
| Is there a legal free copy? | Unpaywall | Open-access locations with license and version |
| Which works belong to this person? | ORCID public API | Researcher-curated record (only as complete as the researcher keeps it) |
| Open citation links between DOIs | OpenCitations | CC0 citation index |

No single source is complete. Counts differ between OpenAlex, Semantic Scholar, Scopus and Web of Science because coverage and deduplication differ; say which source a number comes from.

## Ground rules for every API

- **Identify yourself.** Send a User-Agent with a project name and a contact address, and the `mailto` or `email` parameter where the service asks for it. Use an address the user agrees to share; do not invent one.
- **Keys by name only.** Read keys from environment variables the user set (`S2_API_KEY`, `OPENALEX_API_KEY`); never print them or paste them into the conversation (`../../agent-safety/references/secrets.md`).
- **Back off.** Honor `429` and `503` with `Retry-After` or exponential backoff and jitter, and stay under the published rate. Run large jobs as a bulk download (OpenAlex snapshot, Crossref public data file) instead of millions of API calls.
- **Page with cursors.** Offset paging is capped (Crossref at 10,000 results). Use cursor parameters for anything larger.
- **Cache and record.** Store raw responses with the request URL and retrieval date, so a review can be reproduced and a rerun does not hit the service again.
- **Respect licenses.** OpenAlex data and OpenCitations are CC0. Crossref metadata is free to reuse, but abstracts it carries may be copyrighted by publishers. Semantic Scholar has its own license agreement with restrictions; read it before commercial or bulk redistribution.

A minimal standard-library client that follows these rules:

```python
import hashlib, json, os, random, time, urllib.error, urllib.parse, urllib.request

CONTACT = os.environ.get("RESEARCH_CONTACT_EMAIL", "")      # set by the user
UA = f"lit-review-script/1.0 (mailto:{CONTACT})" if CONTACT else "lit-review-script/1.0"
CACHE = os.path.expanduser("~/.cache/scholarly-api")

def get_json(url, params=None, headers=None, tries=5):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"_url": url, "_retrieved": time.strftime("%Y-%m-%d"), **data}, fh)
            return data
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
            wait = float(exc.headers.get("Retry-After") or 2 ** attempt)
            time.sleep(wait + random.random())
```

## doi.org: existence and formatted metadata

```bash
# Does the DOI exist? responseCode 1 = found, 100 = not found
curl -s "https://doi.org/api/handles/10.1038/nphys1170" | python3 -c "import json,sys; print(json.load(sys.stdin)['responseCode'])"

# Metadata from whichever agency registered it (Crossref, DataCite, mEDRA, ...)
curl -sL -H "Accept: application/vnd.citationstyles.csl+json" "https://doi.org/10.1038/nphys1170"
curl -sL -H "Accept: application/x-bibtex" "https://doi.org/10.1038/nphys1170"
```

Content negotiation is the quickest way to turn a DOI into a BibTeX or CSL-JSON record. Treat the result as a draft: check the entry type, protect capitals in the title and fix author names before adding it to a bibliography.

## Crossref REST API

- Single work: `https://api.crossref.org/works/{doi}`. Search: `https://api.crossref.org/works?query.bibliographic=...&rows=5`. Filters: `filter=from-pub-date:2020-01-01,type:journal-article`; fields: `select=DOI,title,author,issued,container-title,type`; deep paging: `cursor=*` with `rows` up to 1000.
- Add `mailto=` for the polite pool. Rate limits are announced in the response headers and have tightened over time; obey them.
- Useful fields: `reference` (outgoing references when the publisher deposited them), `funder`, `license`, `update-to` and relations on correction and retraction notices, `is-referenced-by-count` (Crossref's own citation count, lower than others).
- Retractions: besides publisher-deposited update notices, the Retraction Watch database has been distributed openly by Crossref since 2023; check it for any work you rely on.

**Matching a free-text reference to a DOI.** `query.bibliographic` returns ranked candidates, and the top hit is often wrong for short or unusual titles. Accept a match only after comparing fields:

```python
import difflib, re

def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower())

def match_reference(title, first_author_surname, year):
    data = get_json("https://api.crossref.org/works",
                    {"query.bibliographic": f"{title} {first_author_surname} {year}", "rows": 5,
                     "mailto": CONTACT})
    for item in (data or {}).get("message", {}).get("items", []):
        cand_title = (item.get("title") or [""])[0]
        ratio = difflib.SequenceMatcher(None, norm(title), norm(cand_title)).ratio()
        surnames = [a.get("family", "").lower() for a in item.get("author", [])]
        cand_year = (item.get("issued", {}).get("date-parts") or [[None]])[0][0]
        if ratio >= 0.9 and first_author_surname.lower() in surnames and cand_year and abs(cand_year - int(year)) <= 1:
            return item["DOI"]
    return None   # report NOT FOUND; do not take the top hit
```

Allow one year of difference for online-first versus issue dates, and nothing looser.

## OpenAlex

- Entities: works, authors, sources (journals and repositories), institutions, topics, publishers, funders. Works can be addressed by DOI: `https://api.openalex.org/works/doi:10.1038/nphys1170`.
- Search and filter: `https://api.openalex.org/works?search=...&filter=publication_year:2020-2024,type:article,is_oa:true&per-page=200&cursor=*`. Combine values with `|` inside a filter (`doi:10.1/a|10.1/b`) for batch lookups; the number of values per filter is limited, so batch in groups of about 50.
- Trim responses with `select=id,doi,display_name,publication_year,cited_by_count,authorships`. Count with `group_by=publication_year` instead of downloading records.
- Citation graph: `referenced_works` on a work lists what it cites; `filter=cites:W123` lists works citing it.
- Abstracts come as an inverted index (word to positions), rebuilt like this:

```python
def abstract_text(inv):
    if not inv:
        return ""
    pos = {i: w for w, idxs in inv.items() for i in idxs}
    return " ".join(pos[i] for i in sorted(pos))
```

- Authors: name search returns several candidates for common names. Resolve with ORCID, institution and topic before filtering works by `authorships.author.id`, and say how you disambiguated.
- Topics replaced the older concepts taxonomy in 2024; the service also went through a large backend rewrite in 2025. Check field names against the current documentation when code that worked before returns empty fields.
- Access: a `mailto` parameter has long given better service; API keys and daily or per-second limits have been introduced for heavier use. For whole-corpus analysis, use the free snapshot instead of the API.
- Known limits: author disambiguation and institution matching are automated and imperfect; coverage of older, non-English and humanities literature is uneven; citation counts are OpenAlex's own.

## Semantic Scholar Academic Graph

- Lookup: `https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,year,authors,externalIds,venue,citationCount,isOpenAccess,openAccessPdf`. Other id prefixes: `ARXIV:`, `PMID:`, `CorpusId:`.
- Search: `/graph/v1/paper/search?query=...&fields=...&limit=100` for ranked results; `/graph/v1/paper/search/bulk` with a continuation token for large result sets.
- Batch: `POST /graph/v1/paper/batch` with `{"ids": [...]}` (up to 500 ids per call) and `fields` in the query string.
- Citations and references with context sentences: `/paper/{id}/citations` and `/paper/{id}/references`.
- Send the key in the `x-api-key` header. Unauthenticated calls share a pool and are throttled hard; a free key gives a modest dedicated rate. Request only the fields you need.

## Unpaywall

`https://api.unpaywall.org/v2/{doi}?email=...` returns `is_oa`, `oa_status` (gold, hybrid, bronze, green, closed) and `best_oa_location` with `url_for_pdf`, `license` and `version` (published, accepted or submitted manuscript). The daily allowance is generous (about 100,000 calls) but requires an email. Use it to find lawful copies; never fetch papers from shadow libraries or bypass paywalls.

## DataCite, ORCID and OpenCitations

- DataCite: `https://api.datacite.org/dois/{doi}` for datasets, software and other non-article outputs; `https://api.datacite.org/dois?query=...` to search. Cite datasets with their DOI and version.
- ORCID: `https://pub.orcid.org/v3.0/{orcid}/works` with `Accept: application/json` returns the public part of a record. The last character of an ORCID iD is a checksum (ISO 7064 MOD 11-2), so a mistyped iD can be detected offline. Records contain only what the researcher made public.
- OpenCitations: `https://api.opencitations.net/index/v2/citations/doi:{doi}` for incoming citations under CC0; coverage depends on publishers depositing references.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Taking the first search hit as the match | Compare title, first author and year; report NOT FOUND otherwise |
| Treating one database's citation count as "the" count | Name the source and date of every count |
| Retrying immediately on 429 | Honor `Retry-After`, add jitter, lower concurrency |
| Paging with offsets past the cap | Use cursors (`cursor=*` in Crossref and OpenAlex) |
| Author search by name only | Disambiguate with ORCID, affiliation and topic |
| Abstracts redistributed in a public dataset | Check copyright; store identifiers and link instead |
| Preprint and published version counted twice | Group by DOI relations, arXiv `journal_ref` or title similarity, keep one |

## Checks (done when)

- [ ] Each identifier was resolved in this session, and the metadata used matches the resolved record.
- [ ] Requests identified the client, stayed within limits and paged with cursors; raw responses are cached with dates.
- [ ] Every count or ranking names its source and retrieval date.
- [ ] Keys came from environment variables and never appeared in output.
- [ ] License and terms of each source were respected for what is stored or shared.
