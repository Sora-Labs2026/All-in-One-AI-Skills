# Patent and trademark searching

Read this when the user wants prior art for an idea, a patent landscape for a technology, the status or family of a known patent, the patents of a company or inventor, or a trademark's status. This is research support, not legal advice: patentability, freedom-to-operate, validity and infringement opinions need a registered patent attorney or agent. Say so once, plainly, when the question drifts there.

## Concepts that change the answer

- **Application versus grant.** Applications are usually published 18 months after the earliest priority date; grants come later or never. Anything filed in the last 18 months is mostly invisible, so recent counts are always incomplete.
- **Numbers and kind codes.** The same invention appears under several publication numbers. Kind codes tell the stage: in the US, A1 is a published application, B1 a grant without prior publication, B2 a grant after publication; at the EPO, A1 and A2 are applications (with or without search report) and B1 a granted patent. Always record number plus kind code.
- **Families.** One invention filed in many countries forms a family. A simple family shares exactly the same priorities; an extended family (INPADOC) links through any shared priority. Count inventions as families, not documents, or one invention filed in twenty offices looks like twenty.
- **Dates.** Priority date (earliest filing claimed) decides what counts as prior art against it; filing date and publication date are different. Term is normally 20 years from filing, adjusted or extended in some cases, and patents lapse early when fees are not paid.
- **Claims define the scope.** Title and abstract do not. Independent claims set the boundary; dependent claims narrow it. Claims can differ between family members and between the application and the grant.
- **Legal status is national.** Granted in one office, refused in another, lapsed in a third. Check status in each office's register, not in an aggregator snapshot.
- **Classification.** Cooperative Patent Classification (CPC, used by the EPO and USPTO) and the International Patent Classification (IPC) group documents by technology regardless of wording. Classification search finds documents that keyword search misses.

## Sources

| Source | Coverage and access | Use for |
|---|---|---|
| Espacenet (EPO) | Worldwide publications, families, legal status links; free web | First broad search, family lookup |
| EPO Open Patent Services (OPS) | API to EPO worldwide data; free registration with a weekly fair-use data allowance | Scripted bibliographic, family and legal-status retrieval |
| European Patent Register | EP procedural status | Status of EP applications and patents |
| USPTO Patent Public Search | US full text; free web | US full-text search with examiner-style operators |
| USPTO Open Data Portal | APIs and bulk data for US applications, file wrappers and assignments; API key | Examination history, status, assignments (it replaced several older USPTO data services in 2024-2025) |
| PatentsView PatentSearch API | Disambiguated US grants and pre-grant publications, inventors, assignees, locations; API key | Research analytics on US patents |
| WIPO PATENTSCOPE | PCT international applications plus national collections | PCT filings, multilingual search |
| Google Patents and its public BigQuery datasets | Worldwide full text and families; free web; BigQuery is billed per query | Quick full-text search; large-scale analysis in SQL |
| The Lens | Patents linked to scholarly works; free for non-commercial use with registration | Patent-to-paper links, landscapes |
| Trademarks: USPTO trademark search and TSDR API, EUIPO eSearch, WIPO Global Brand Database | Marks, owners, status | Trademark clearance research and status |

Do not scrape search websites whose terms forbid it (Google Patents among them); use the APIs, BigQuery or the offices' bulk files. Keys go in environment variables set by the user.

## Prior-art search method

1. **Write the invention as features.** Break it into the elements a claim would contain: what it is, what it does, how, and what makes it different. Each feature becomes a concept block.
2. **Keywords per block.** Include patent vocabulary (a "fastening means" rather than a "screw"), synonyms, and the older and broader terms examiners use. Combine with OR inside a block and AND across blocks; use proximity operators where the platform supports them.
3. **Classification.** Find the CPC groups of the most relevant documents found so far and search those groups directly, combined with one or two keyword blocks. Read the CPC scheme definitions to confirm a group fits.
4. **Citation chasing.** Look at the documents cited by examiners (backward) and the later documents citing them (forward); examiner citations are often the best prior art.
5. **Names.** For assignee or inventor searches, normalize variants (Inc., GmbH, subsidiaries, acquired companies, transliterations) and say which variants you combined.
6. **Non-patent literature.** Papers, theses, standards, product manuals and conference talks are prior art too. Run the literature search in parallel (`literature-search-and-review.md`).
7. **Date limit.** For prior art against a specific filing, keep documents published before its priority date; mark documents near the date.
8. **Record everything:** source, query, classification codes, date run, hit counts, and why each relevant document matters (which feature it discloses, with the paragraph or claim number).

## Reading a patent document

- Read the independent claims first and map each claim element to the user's features, citing claim and paragraph numbers.
- Check the family: a broader claim may exist in another jurisdiction or in a continuation.
- Check the status in the relevant office's register on the date of the search, including fee payments and any opposition or post-grant proceeding.
- Quote claim text exactly; paraphrase of claims is where scope gets distorted.

## Landscapes and portfolio counts

- Deduplicate to families before counting; normalize assignees; state the family definition used.
- Plot by earliest priority year and grey out or annotate the last two years, which are incomplete because of the publication delay.
- Count is not value: citation counts, family size and renewal behaviour are weak proxies. Say so when a chart invites a value judgment.
- Keep the analysis as code over a saved result set, so numbers can be regenerated.

A PatentsView PatentSearch request has this shape (endpoint and field names as of 2025; check the current API reference before relying on them):

```bash
curl -s -X POST "https://search.patentsview.org/api/v1/patent/" \
  -H "X-Api-Key: $PATENTSVIEW_API_KEY" -H "Content-Type: application/json" \
  -d '{"q": {"_and": [{"_gte": {"patent_date": "2023-01-01"}},
                      {"_text_any": {"patent_abstract": "solid electrolyte lithium"}}]},
       "f": ["patent_id", "patent_title", "patent_date"],
       "o": {"size": 100}}'
```

## Output of a prior-art search

```markdown
## Invention as features
F1 ... F2 ... F3 ...

## Searches run
| Source | Query or CPC codes | Date | Hits | Reviewed |

## Most relevant documents
| Publication no. (kind) | Family | Priority date | Status (office, date checked) | Features disclosed | Where (claim / paragraph) |

## Non-patent literature
| Reference (verified identifier) | Features disclosed | Where |

## Gaps and limits
<sources not searched, languages not covered, the 18-month blind spot, status not checked>

Research support only; not a patentability, validity or freedom-to-operate opinion.
```

## Privacy and terms

Inventor names and addresses are personal data even when published. Aggregate them for analysis, do not build profiles of individuals, and follow GDPR or similar rules when processing them. Bulk data and API terms differ per office; record them with the data.

## Checks (done when)

- [ ] The legal-advice boundary was stated where the question required it.
- [ ] Features, keyword blocks, CPC codes, sources, dates and counts are recorded.
- [ ] Every relevant document has number with kind code, family, priority date, status source and date, and the claim or paragraph that matters.
- [ ] Counts are by family, with the recent-years incompleteness marked.
- [ ] Non-patent literature was searched or its absence stated.
