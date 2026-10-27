# Researched content and co-authoring documents

Read this when writing or improving an article, blog post, newsletter issue, explainer, case study, white paper or op-ed, or when writing a longer document together with the user section by section. Design docs, specs, RFCs and ADRs follow `../../engineering-practices/references/docs-and-decisions.md`; internal updates and announcements are in `internal-comms-and-meetings.md`. Persuasive copy for products follows `../../ethical-persuasion.md`.

## Get a brief first

Ask only what you cannot infer, and keep the answers in the project:

- **Audience:** who reads it, what they already know, what they want from it.
- **Purpose:** inform, explain, persuade, teach, or report.
- **The one takeaway** a reader should leave with.
- **Format and channel:** length, where it will appear, deadline, house style guide.
- **Voice:** two or three samples of the user's writing, or published pieces they like.
- **Material in hand:** sources, notes, data, interviews, previous drafts.
- **Constraints:** legal or compliance review, embargoes, names that cannot appear.

## Research with a log

Keep a research log next to the draft and fill it as you go:

| Claim or fact | Source (title, publisher or author) | Link or identifier | Date published / accessed | Exact quote and location | Status |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | verified / single source / unverified |

- Trace every statistic to its origin and record its definition, date and population. A number seen in three articles that all cite the same survey has one source.
- Quotes are verbatim from a source you opened, attributed with where and when they were said. Never compose a quote, an expert's opinion, a customer story or an example company. Use `[[NEEDS SOURCE: claim]]` and tell the user.
- Prefer primary sources (the study, the dataset, the filing, the official statement) over coverage of them. Judge sources with `appraising-evidence.md`; search and verify the web with `web-research-and-extraction.md`.
- Note disagreements between credible sources and keep both sides in the log.
- Date-sensitive facts get a date in the text ("as of March 2026").

## Outline before drafting

Agree an outline with the user: the thesis, each section's point and its evidence, the counter-argument you will address, and the ending. Reordering an outline is cheap; reordering prose is not.

## Draft

- **Open with substance.** The first lines give the reader a reason to continue: a specific problem, a surprising but sourced fact, a short real scene, or the answer itself. No invented statistics, no false urgency, no headline the article does not deliver.
- **Specific over general:** names, numbers, examples, steps, with sources.
- **Structure for scanning** on the web: short paragraphs, subheadings that make a point, lists for steps; full arguments still need paragraphs.
- **Link sources** where claims are made; cite consistently in the style the outlet uses.
- **End with what to do or think next,** not a summary of the summary.
- Technical tutorials: test every command and code sample before publishing, state versions, and add a troubleshooting section for the errors you hit.

## Titles and openings without clickbait

Offer two or three options with different approaches and say what each does:

| Approach | Example shape | Works when |
|---|---|---|
| The answer | "Why our builds got 4x faster: we stopped compiling tests twice" | The finding is concrete and sourced |
| The problem | "Your error budget is lying to you if you count retries as successes" | Readers recognize the pain |
| The question | "Do code reviews catch bugs, or just style?" | The piece answers it, with evidence |
| A real scene | Two sentences of an actual incident or interview, with permission | You have the material and the right to use it |

Reject any option the article does not deliver on, any number not in the research log, and any story that did not happen.

## Keep the author's voice

- Learn from the samples: sentence length, formality, humor, favorite constructions, words they avoid.
- Suggest rather than overwrite: for a section, give the change and the reason; offer alternatives for openings and titles instead of one rewrite.
- Opinions stay the author's. Do not insert positions they have not taken; mark any sentence you added that states a view.
- If an edit would change meaning, ask.

## Feedback on a draft section

Order feedback by impact: argument and structure, then evidence, then clarity and flow, then style and line edits. For line edits show original, suggestion and reason. Name what works so it survives revision. Keep it to the changes that matter most; a list of forty nits buries the three that count.

## Co-authoring a longer document section by section

1. **Gather context:** ask the meta questions (type of document, readers, the decision or effect it should produce, template, constraints), then invite the user to dump everything relevant in any order and point you to existing documents; read them. Follow with five to ten numbered clarifying questions about the gaps, answerable in shorthand.
2. **Agree the structure:** propose sections from the questions readers will bring, or use the user's template. Create the skeleton with placeholders.
3. **Per section,** starting with the one that carries the decision or the most uncertainty: ask what it must cover; brainstorm candidate points; let the user keep, cut or merge them; draft; refine with targeted edits rather than rewriting the whole document. Learn from the user's cuts for the next sections.
4. **Whole-document pass** when most sections exist: repetition, contradictions, terminology drift, filler, and whether every paragraph earns its place.
5. **Test with a cold reader:** give only the document to a fresh helper (or ask the user to send it to a colleague) with five to ten questions real readers would ask. Every wrong or missing answer marks a gap to fix. Also ask the reader what the document assumes they already know.
6. **Final check by the user:** they own the document; ask them to confirm facts, names and links.

## Before publishing

- Facts, numbers, quotes and names re-checked against the log; every link opened.
- Images: licensed or the user's own, with credits; alternative text written.
- Disclosures the outlet or law requires: sponsorship, affiliate links, conflicts of interest, AI assistance where the publisher asks for it.
- Claims about identifiable people or companies are sourced and fair; flag anything that could be defamatory for the user's review.
- Search snippets: an accurate title and description; descriptive headings; no keyword stuffing.

## Checks (done when)

- [ ] Brief recorded: audience, purpose, takeaway, format, voice, constraints.
- [ ] Research log complete; every statistic and quote traced to a primary source or marked unverified.
- [ ] Outline agreed before drafting; the draft keeps the author's voice and positions.
- [ ] For co-authored documents, a cold-reader test was run and its gaps fixed.
- [ ] Pre-publication checks on facts, links, image rights and disclosures done.
