# Citations, BibTeX, CSL and reference managers

Read this when adding, checking or formatting references: verifying that a citation exists and says what the text claims, building or cleaning a `.bib` file, choosing BibTeX or biblatex, formatting with a CSL style, or working with a Zotero library from code.

## Verify every reference

A reference is verified when all of these hold, and only then:

1. **It has an identifier** (DOI, PMID, PMCID, arXiv id, ISBN, or a stable URL with an archived copy for web sources).
2. **The identifier resolves in this session** (doi.org handle API, PubMed `esummary`, arXiv API; see `scholarly-apis.md` and `biomedical-and-preprint-apis.md`).
3. **The resolved record matches the entry:** title (normalized, near-identical), first author's surname, year (one year of slack for online-first versus issue), and venue. A DOI that resolves to a different paper is a wrong reference, not a typo.
4. **It is not retracted,** or the retraction is mentioned where it is cited.
5. **It supports the sentence that cites it.** Open at least the abstract; open the full text for numbers, quotes and anything beyond the main finding. Quotes are copied verbatim with page or section numbers.

Report each reference as `VERIFIED`, `METADATA ONLY` (record matches, claim not checked against the text), or `NOT FOUND`. Never silently drop or repair a reference the user wrote: report it and propose the fix.

Errors to expect, especially in text a language model drafted:

- A plausible title attached to real authors who never wrote it.
- A real paper with the wrong year, journal or volume.
- A DOI copied from a neighbouring entry, so it resolves to another paper.
- The preprint cited when the published version differs, or the reverse.
- A review cited for a finding that belongs to a primary study.
- A citation that exists but says something weaker, narrower or different.

A verification pass over a list of DOIs with the standard library (CSL JSON through content negotiation):

```python
import json, re, urllib.error, urllib.request, difflib

def csl(doi):
    req = urllib.request.Request("https://doi.org/" + doi,
                                 headers={"Accept": "application/vnd.citationstyles.csl+json",
                                          "User-Agent": "ref-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        return None if exc.code == 404 else {"_error": exc.code}

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def check(entry):               # entry: dict with key, doi, title, first_author, year
    rec = csl(entry["doi"])
    if rec is None:
        return "NOT FOUND", "DOI does not resolve"
    if "_error" in rec:
        return "UNCHECKED", f"HTTP {rec['_error']}"
    title = rec.get("title") if isinstance(rec.get("title"), str) else (rec.get("title") or [""])[0]
    ratio = difflib.SequenceMatcher(None, norm(entry["title"]), norm(title)).ratio()
    family = [a.get("family", "") for a in rec.get("author", [])]
    year = (rec.get("issued", {}).get("date-parts") or [[None]])[0][0]
    problems = []
    if ratio < 0.9:
        problems.append(f"title differs ({title!r})")
    if entry["first_author"].lower() not in (f.lower() for f in family[:1]):
        problems.append(f"first author {family[:1]}")
    if year is None or abs(int(entry["year"]) - year) > 1:
        problems.append(f"year {year}")
    return ("METADATA ONLY", "") if not problems else ("MISMATCH", "; ".join(problems))
```

`scripts/bib_check.py --list-ids refs.bib` prints each entry's key, DOI, arXiv id and PMID as tab-separated values to feed a loop like this. Pace requests (one or two per second) and stop on repeated errors.

## BibTeX or biblatex

| | BibTeX with a `.bst` style | biblatex with biber |
|---|---|---|
| Typical users | Journals and conferences that ship a `.bst` (IEEE, ACM, many society journals, most ML venues via natbib) | Theses, books, humanities, anyone free to choose |
| Unicode | Limited; use LaTeX escapes for accents in older setups | Full UTF-8 |
| Field names | `journal`, `year`, `address`, `school` | `journaltitle`, `date`, `location`, `institution` (biber maps the BibTeX names) |
| Extra types | Standard 14 types | `@online`, `@report`, `@thesis`, `@dataset`, `@software`, `@collection` and more |
| Styles | `.bst` files, hard to modify | Style options in LaTeX |

Use what the venue requires; their template decides. If a venue ships a `.bst`, do not switch to biblatex. arXiv needs the generated `.bbl` file in the upload (`venues-and-paper-pages.md`).

## Writing good entries

- **Keys:** one convention per project, ASCII only, no spaces (for example `smith2020deep`). Never rename a key that manuscripts already cite without updating them. Zotero's Better BibTeX extension can pin keys so they stay stable across exports.
- **Types:** `@article` for journal papers, `@inproceedings` for conference papers, `@book` and `@incollection` for books and chapters, `@phdthesis` or `@thesis`, `@techreport` or `@report`, `@misc` or `@online` for web pages, `@software` and `@dataset` under biblatex. Preprints: `@misc` (BibTeX) or `@online`/`@article` with `eprint`, `eprinttype = {arxiv}` and `eprintclass` (biblatex), or `archivePrefix` and `primaryClass` with natbib styles that support them.
- **Names:** `Last, First and Last, First`; never commas between people. Organizations in double braces: `author = {{World Health Organization}}`. Use `and others` instead of "et al.".
- **Title capitals:** styles that sentence-case titles lowercase everything not protected. Brace only what must keep its capitals: `{DNA}`, `{Bayesian}`, `{Python}`, `{mRNA}`. Do not wrap the whole title in double braces; that disables the style's casing everywhere.
- **Pages:** `123--145` for an en dash range; article numbers (`e0123456`) go in `pages` or `eid` per style.
- **DOIs and URLs:** the bare DOI in `doi` (`10.1234/abcd`), not a URL and not escaped (`\_` breaks links in most styles). `url` only when there is no DOI or the URL adds something; with `urldate` for web pages.
- **Special characters:** with biber, plain UTF-8. With BibTeX, LaTeX escapes (`{\"o}`) or check that the engine and style handle UTF-8.
- **Duplicates:** one entry per work. Merge preprint and published versions unless both are cited deliberately.

## Check the file before every build

`scripts/bib_check.py` reads `.bib` files offline and reports unbalanced braces, unterminated quotes, missing commas, missing or invalid keys, duplicate keys and DOIs, likely duplicate titles, missing required fields per entry type (BibTeX or biblatex rules, chosen automatically), malformed DOIs, years, dates, arXiv ids, ISBNs and PMIDs, comma-separated author lists, "et al." in names, undefined `@string` macros, missing crossref parents and unprotected inner capitals. With `--cited-in paper.tex` (or `.aux`, or Markdown with pandoc citations) it also lists keys cited but not defined, and entries never cited.

```bash
python3 <productcraft>/modules/research-writing/scripts/bib_check.py refs.bib
python3 <productcraft>/modules/research-writing/scripts/bib_check.py refs.bib --cited-in main.tex --strict
python3 <productcraft>/modules/research-writing/scripts/bib_check.py bib/ --json --min-level warn
python3 <productcraft>/modules/research-writing/scripts/bib_check.py --list-rules
```

It does not use the network, so it cannot tell whether a DOI exists or matches the paper; that is the verification step above. Also read the LaTeX log: "Citation ... undefined", "There were undefined references" and biber warnings must be gone in the final build.

## CSL and pandoc

The Citation Style Language describes citation styles as XML; thousands of journal styles exist in the official CSL repository (the same styles Zotero uses). CSL-JSON is the matching data format.

```bash
pandoc paper.md --citeproc --bibliography refs.bib --csl apa.csl -o paper.docx
pandoc paper.md --citeproc --bibliography refs.json --csl nature.csl -o paper.pdf
```

Use the venue's own style file when it exists, and pin the file in the project rather than fetching it at build time. Citations in Markdown use pandoc syntax: `[@smith2020, p. 4; @lee2018]`, or `@smith2020` in running text.

## Reference managers

- **Zotero** (open source) captures records from browsers and identifiers, syncs libraries and exports BibTeX, biblatex, CSL-JSON and RIS. Better BibTeX adds stable keys and automatic export of a `.bib` file the LaTeX project reads; that export, not hand edits, should be the single source for the bibliography.
- **Zotero Web API (v3)**, usually through the `pyzotero` client. Create a key at the user's Zotero settings with the least access needed: read-only for reading, write only when the task writes, file access only for attachments. The user stores the key and library id in environment variables.

```python
import os
from pyzotero import zotero

zot = zotero.Zotero(os.environ["ZOTERO_LIBRARY_ID"], os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
                    os.environ["ZOTERO_API_KEY"])
items = zot.everything(zot.top(q="graph neural", itemType="journalArticle"))
for it in items:
    d = it["data"]
    print(d["key"], d.get("DOI", ""), d["title"][:80])
```

  Respect `Backoff` and `Retry-After` headers. Writes take at most 50 items per request; send the item version (or library version) so concurrent edits are rejected instead of overwritten; sync incrementally with `since=<version>`. Deleting items or collections is destructive: show the list and get approval first.
- **Zotero local API** (Zotero 7 and later, enabled in the desktop settings) serves the same read endpoints from the user's machine without a key; it is read-only.
- **JabRef** keeps a BibTeX or biblatex file as the library itself and is a good choice when the `.bib` is the source of truth in version control.
- **Mendeley, EndNote and others** export RIS or BibTeX; import once, then run `bib_check.py` and fix the findings, because exports often carry broken types, missing fields and duplicate keys.

## Checks (done when)

- [ ] Every reference has a resolved identifier and a status; mismatches and NOT FOUND items are reported to the user with proposed fixes.
- [ ] Claims and quotes were checked against the source for every reference marked verified.
- [ ] `bib_check.py` reports no ERROR findings; remaining WARN findings are explained.
- [ ] Cited keys and defined entries agree (`--cited-in`), and the document builds without undefined citations.
- [ ] The style file is the venue's own and is pinned in the project.
- [ ] API keys came from the environment with least-privilege scopes; nothing was deleted without approval.
