# Research and Writing

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Find, judge and cite evidence correctly, and turn it into writing and presentations people can rely on: literature searches and reviews (narrative, systematic, scoping), scholarly and patent databases, citation management with BibTeX, biblatex, CSL and Zotero, appraisal of papers and sources, critical thinking and bias checks, hypothesis generation, scientific papers and study checklists, peer review, grant proposals, stress tests for plans and decisions, diagrams, talks, posters, venue templates and paper web pages, researched articles, co-authored documents, internal communications, meeting notes, market research, genealogy, learning plans, and web research with text extraction. Each topic has one focused reference. Read only the ones the task touches.

This module covers the content and its evidence. File formats belong elsewhere: Word, PowerPoint and PDF files in `../documents/GUIDE.md`; design docs, specs, ADRs and READMEs in `../engineering-practices/references/docs-and-decisions.md`; analysis code and figures in `../data-engineering/GUIDE.md` and statistics in `../ml-engineering/GUIDE.md`.

## When to activate

- The user asks what is known about a topic, wants papers found, a review written, or a claim checked against the literature; mentions PubMed, arXiv, OpenAlex, Crossref, DOIs, patents or prior art.
- References are added, checked or formatted: BibTeX or biblatex files, citation styles, Zotero, "is this citation real?".
- The user asks whether a paper, report, website or statistic can be trusted, or wants a paper scored or critiqued.
- Brainstorming research ideas, formulating hypotheses or designing a study.
- Writing or revising a paper, thesis, preprint, response to reviewers, peer review or grant proposal; choosing a reporting checklist.
- "Play devil's advocate", "what could go wrong", "red-team this plan", "what if...", "how would different stakeholders see this".
- Diagrams for documents, a talk, a poster, formatting for a venue, an arXiv upload, a project page for a paper.
- Articles, newsletters, status updates, announcements, incident notes, meeting notes or transcript analysis; market sizing or competitor research; family history; turning material into a learning plan; web research and extracting article text or transcripts.
- **Not for** office file mechanics (`../documents/GUIDE.md`), engineering design docs and ADRs (`../engineering-practices/references/docs-and-decisions.md`), data pipelines and plots (`../data-engineering/GUIDE.md`), statistical modeling (`../ml-engineering/GUIDE.md`), security threat models of code (`../code-security-review/GUIDE.md`) or marketing copy for a product UI (`../ethical-persuasion.md`).

## Ground rules

1. **Never invent a citation, quote, statistic, result or source.** Not as an example, not as a placeholder that looks real. Where content is missing, write a visible marker (`[[NEEDS SOURCE: ...]]`, `[[RESULT: ...]]`, `[[APPLICANT: ...]]`) and list it in the report.
2. **Verify every reference by identifier in this session.** Resolve the DOI, PMID, arXiv id, ISBN or URL; compare title, first author, year and venue with the record; check retraction status; and open the source to confirm it supports the sentence citing it (`references/citations-and-reference-managers.md`). Memory is not a source, including the model's own.
3. **Label what you did not check.** Use `VERIFIED`, `METADATA ONLY`, `NOT FOUND` for references and `NOT VERIFIED` for any claim or step you could not confirm, with the reason.
4. **Respect rights and rules.** Copyright and licenses on text, figures and data; site terms and `robots.txt`; API rate limits and licenses; no paywall or login circumvention; publishing agreements before posting papers.
5. **Authorship stays with the people.** The user's scientific ideas, results and decisions are theirs. Check venue and funder policies on AI assistance and disclosure; some funders and most journals restrict AI use in proposals, manuscripts and reviews.
6. **Confidential material stays confidential.** Manuscripts and proposals under review, internal documents, meeting recordings and family records are processed only as the user is entitled to; ask when a policy might forbid it.
7. **Privacy of people.** No profiles of colleagues from meeting data, no publication of living persons' details or DNA results without consent, inventor and author data aggregated, not profiled.
8. **General guidance, not professional advice.** Patent, legal, medical and investment questions get research support plus a clear pointer to a qualified professional; never present analysis as such advice.
9. **Keys by name, costs agreed.** API keys live in environment variables the user sets (`../agent-safety/references/secrets.md`); paid search, research-agent or image services run only after the user agrees to the cost.
10. **The user decides.** Stress tests, panels, reviews and evaluations end with options and evidence, not with the agent taking the decision.

## Pick the references

| The task involves | Read | Minimum check before calling it done |
|---|---|---|
| Finding literature, writing a narrative, systematic, scoping or rapid review, PRISMA | `references/literature-search-and-review.md` | Sources, strings, dates and counts recorded; every included work traceable to a search or user file; flow counts add up |
| DOIs, Crossref, OpenAlex, Semantic Scholar, Unpaywall, DataCite, ORCID | `references/scholarly-apis.md` | Identifiers resolved; client identified and rate-limited; counts named by source and date |
| PubMed and E-utilities, PMC, Europe PMC, arXiv, bioRxiv, medRxiv | `references/biomedical-and-preprint-apis.md` | Query translation recorded; NCBI and arXiv limits respected; preprints labeled; retractions checked |
| Prior art, patent landscapes, patent status, trademarks | `references/patent-search.md` | Legal-advice boundary stated; counts by family; claims and status cited with dates |
| Adding, checking or formatting references; BibTeX, biblatex, CSL, Zotero | `references/citations-and-reference-managers.md` | Every reference has a status; `scripts/bib_check.py` clean of ERROR findings; cited and defined keys agree |
| Can this paper, report, site or statistic be trusted; scoring a manuscript | `references/appraising-evidence.md` | Venue, retraction, funding and design checked; wording matches evidence strength |
| Judging an argument or one's own conclusion; biases and fallacies | `references/critical-thinking-and-bias.md` | Claim restated and falsifiable; alternatives checked; confidence and unchecked parts stated |
| Brainstorming research ideas, hypotheses, study design | `references/ideation-and-hypotheses.md` | Novelty rests on a recorded search; hypotheses have refuting observations and a discriminating test |
| Drafting or revising a paper, thesis or report | `references/scientific-writing.md` | Every number traced to an output or source; claims match the design; abstract, text and figures agree |
| CONSORT, STROBE, PRISMA and other checklists, registration, data availability | `references/study-checklists-and-registration.md` | Checklist filled with locations; nothing marked reported that is not; data and code identifiers and licenses |
| Writing a peer review or answering reviewers | `references/peer-review.md` | Confidentiality and AI policy confirmed; located major issues with fixes; every comment answered |
| Grant and fellowship proposals | `references/grant-proposals.md` | Compliance matrix from the current call; no invented data, costs or rates; funder AI policy checked |
| Devil's advocate, pre-mortem, red team, assumption audit | `references/stress-tests.md` | Position steelmanned and confirmed; ranked concrete challenges; verdict with changes or tests |
| What-if scenarios, contingency planning, multi-perspective panels | `references/scenarios-and-panels.md` | Sharpened question; branches with signposts; no invented probabilities; core tension named |
| Diagrams and schematics, Mermaid, Graphviz, TikZ | `references/diagrams-and-mermaid.md` | Source kept with the document; accessible description; rendered and inspected in the target |
| Talks and slide decks | `references/slides-and-talks.md` | Timed rehearsal fits the slot; claim titles; rendered deck inspected slide by slide |
| Research posters | `references/posters.md` | Venue size recorded; type sizes met; PDF size and fonts verified; quarter-scale proof legible |
| Venue templates, anonymization, arXiv upload, paper web pages | `references/venues-and-paper-pages.md` | Current instructions met on the final PDF; clean build; rights checked before posting |
| Articles, newsletters, explainers; co-authoring a document section by section | `references/content-and-coauthoring.md` | Research log with primary sources; outline agreed; voice kept; cold-reader test for co-authored documents |
| Status updates, newsletters, FAQs, announcements, incident notes, meeting notes and transcripts | `references/internal-comms-and-meetings.md` | First line answers the reader; numbers sourced; actions owned; meeting analysis consented and evidence-based |
| Market sizing, competitors, industry analysis | `references/market-research.md` | Two sizing methods reconciled with sensitivity; every figure sourced and dated; no investment advice |
| Family history and genealogy | `references/genealogy-research.md` | Plan before searching; full citations; evidence analyzed and conflicts resolved; privacy respected |
| Turning material into practice; questions over the user's documents | `references/learning-plans.md` | Observable goal with baseline; one-week first cycle; answers cite passages |
| Web research, deep-research tools, article text, transcripts | `references/web-research-and-extraction.md` | Every claim checked on its page; costs agreed; robots and terms respected; provenance saved |

Several references often apply together. A review article typically needs `literature-search-and-review`, the API references, `appraising-evidence`, `scientific-writing`, `citations-and-reference-managers` and `study-checklists-and-registration`, in that order.

## Working method

1. **Frame:** the question, the reader, the decision or deliverable, the venue and its rules, the deadline. Ask only what you cannot infer, and record the answers.
2. **Gather with provenance:** every source enters with its identifier, retrieval date and how it was found. Keep a research log or screening table in the project, not only in the conversation.
3. **Judge before using:** appraise sources and claims; keep weak or single-source claims visibly labeled.
4. **Write from the evidence:** outline with a claim-evidence map, then prose; placeholders where results or sources are missing.
5. **Check mechanically and by eye:** run `scripts/bib_check.py` on bibliographies, build documents from clean sources, render slides, posters and diagrams and look at them.
6. **Report:** what was produced, which sources and tools were used, verification status of every reference, what remains `NOT VERIFIED` and what the user must do.

## Bibliography checker helper

`scripts/bib_check.py` is a read-only, standard-library checker for `.bib` files. It never uses the network and never writes files.

It reports unbalanced braces (unclosed entries, early closes, stray braces), unterminated quotes, missing commas, missing or invalid keys, duplicate keys (and keys differing only in case), duplicate DOIs, likely duplicates by title and year, missing required fields per entry type under BibTeX or biblatex rules (chosen automatically, or with `--dialect`; crossref and xdata parents count), unknown entry types, malformed DOIs (and DOIs stored as URLs, with backslashes or trailing punctuation), malformed years and biblatex dates, year and date disagreements, author lists separated by commas or semicolons, "et al." in name fields, undefined `@string` macros, missing crossref parents, malformed arXiv ids, ISBNs and PMIDs, single-hyphen page ranges and title words whose capitals sentence-casing styles would lose. With `--cited-in` it compares the keys cited in `.tex`, `.aux` (BibTeX and biblatex) or Markdown files (pandoc citations) with the entries.

```bash
python3 <productcraft>/modules/research-writing/scripts/bib_check.py refs.bib
python3 <productcraft>/modules/research-writing/scripts/bib_check.py refs.bib --cited-in main.tex --strict
python3 <productcraft>/modules/research-writing/scripts/bib_check.py bib/ --json --min-level warn --ignore UNPROTECTED_CAPS
python3 <productcraft>/modules/research-writing/scripts/bib_check.py refs.bib --list-ids > ids.tsv
python3 <productcraft>/modules/research-writing/scripts/bib_check.py --list-rules
```

`<productcraft>` is the folder where the ProductCraft skill is installed. Exit codes: 0 when there are no ERROR findings, 1 with ERROR findings (or WARN findings with `--strict`), 2 for usage errors or unreadable files; `--list-ids` exits 0 and prints key, DOI, arXiv id and PMID as tab-separated values for a separate verification step. `--max-year` defaults to the current year plus one. A clean result means the file is well formed, not that the references are real: existence and accuracy need the verification in `references/citations-and-reference-managers.md`. It parses about 20,000 entries in under two seconds. Tests: `python3 -B -m unittest discover -s <productcraft>/modules/research-writing/tests -v`.

## Topic essentials

Use these when the reference is not needed; open it when a bullet raises a question.

- **Searching:** several sources, concept blocks with synonyms and controlled vocabulary, strings and dates recorded, citation chasing both ways; Google Scholar by hand only.
- **APIs:** identify the client, keys from the environment, back off on 429, cursors for paging, cache raw responses; never take the top search hit as a match.
- **References:** identifier resolved, metadata matched, retraction checked, claim checked in the source; `bib_check.py` before every build.
- **Appraisal:** design fits the claim; abstract matches results; registered outcomes match reported ones; words match evidence strength.
- **Writing:** figures first, claim-evidence map, numbers only from outputs, verbs matched to the design, limitations specific.
- **Reviews and proposals:** confidentiality and AI policies first; review the central claim before details; build a compliance matrix from the current call.
- **Stress tests:** steelman, three to five concrete challenges, no invented probabilities, end with changes and a verdict.
- **Presenting:** one message, claim titles, text readable at distance, render and look at every page.
- **Everyday writing:** the first line answers the reader; every number links to its source; owners and dates on actions.

## What to report

Add these to the engineering workflow's report or to `../../assets/review-template.md` when the work is part of a code change:

- References used from this module and, for each, the minimum check: met, not met or `NOT VERIFIED` with the reason.
- Sources searched (database, string, date, count) and sources not searched.
- Reference verification table: key, identifier, status, problem found.
- `bib_check.py` summary and how remaining WARN findings were handled.
- Placeholders left for the user (`[[NEEDS SOURCE]]`, `[[RESULT]]`, `[[APPLICANT]]`), and decisions left to them.
- Policies checked (venue, funder, AI disclosure, publishing agreement, site terms) and their outcome.

## Working with other ProductCraft modules

- `../documents/GUIDE.md`: Word, PowerPoint and PDF deliverables, tracked changes, rendering pages for inspection.
- `../engineering-practices/references/docs-and-decisions.md`: design docs, specs, ADRs and READMEs; the co-authoring and cold-reader method shared with this module.
- `../data-engineering/GUIDE.md`: data preparation, plots, publication figures, official statistics and filings used in reports.
- `../ml-engineering/GUIDE.md`: statistical inference, meta-analysis statistics, retrieval systems over document collections, machine-generated hypotheses.
- `../life-sciences/GUIDE.md`: biological, chemical and clinical databases, trial registries, clinical data handling.
- `../creative-media/GUIDE.md`: HTML slide decks, video and synthetic media for talks and paper pages.
- `../code-security-review/references/threat-modeling.md` and `../launchguard/GUIDE.md`: security-focused red teaming of software.
- `../legal-ready/GUIDE.md`: trackers, consent and licensing on published pages.
- `../agent-safety/GUIDE.md`: keys and secrets, installing tools, destructive actions such as deleting library items.
- `../lean-output.md`: shorter chat replies on request; documents written here follow their audience's conventions instead.
