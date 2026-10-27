# Scientific writing: structure, sections, claims and revision

Read this when drafting, restructuring or editing a research paper, thesis chapter, technical report or preprint. Venue formatting is in `venues-and-paper-pages.md`, reporting checklists in `study-checklists-and-registration.md`, figures in `../../data-engineering/references/publication-figures.md`, and Word or PDF deliverables in `../../documents/GUIDE.md`.

## Integrity rules that come first

- **Every number, result and quote comes from something that exists:** the user's analysis output, a table they supplied, or a source verified by identifier. Where the result does not exist yet, write a visible placeholder (`[[RESULT: primary outcome difference with 95% CI]]`) and list it in the report. Never draft plausible-looking results.
- **The authors own the work.** Language models cannot be authors (ICMJE criteria and COPE guidance). Most publishers require disclosure of substantive AI assistance, usually in the methods or acknowledgments; tell the user to check the venue's policy and disclose accordingly.
- **No invented methods details.** If the randomization method, software version or exclusion rule is unknown, ask; do not fill it in to satisfy a checklist.
- **Text reuse:** quote with quotation marks and a citation; paraphrase genuinely, not by swapping synonyms; follow the venue's policy on reusing one's own methods text.

## Plan before prose

1. **One-sentence message:** what should a reader remember? If it takes three sentences, the paper may be two papers.
2. **Reader and venue:** specialists or a broad audience, and the venue's article type and limits.
3. **Figures first:** sketch the sequence of figures and tables that carries the argument. The text explains them.
4. **Claim-evidence map:** list each claim the paper makes with the figure, table, analysis or citation that supports it. Claims without evidence get cut or softened.
5. **Outline with key points per paragraph,** agreed with the user, then turn each into prose.

## IMRaD and what each part must do

| Part | Job | Common failures |
|---|---|---|
| Title | Say the finding or the question specifically | Vague ("A study of..."), hype, undefined abbreviations |
| Abstract | Stand alone: context, objective, methods, main results with numbers, conclusion | No numbers; conclusion stronger than results; content missing from the body |
| Introduction | Move from what is known to the specific gap, then the question and approach; end with the aim or hypothesis | Literature dump; gap asserted without evidence; results revealed piecemeal |
| Methods | Let a competent reader reproduce the work: design, participants or materials, procedures, measures, analysis, software and versions, data and code availability, ethics approvals | "Standard methods were used"; missing exclusions; analysis decided after the fact but presented as planned |
| Results | Report findings in the order of the questions, with effect sizes and uncertainty; no interpretation | Selective reporting; p-values without effects; figures repeated in text |
| Discussion | Principal findings, comparison with prior work, limitations, implications, conclusion | Restating results; ignoring contrary evidence; claims beyond the data; limitations as a token paragraph |

Variants are fine when the venue expects them: Results and Discussion combined, methods at the end, or the computer-science shape (introduction, related work, method, experiments, discussion, conclusion). Theses add a literature chapter and longer methods. Follow the venue's template rather than forcing IMRaD.

**Abstracts:** structured (labeled sections) when the venue asks, otherwise one paragraph; respect the word limit; include the main numbers; no citations; write it last and check every statement against the body.

## Claims that match the evidence

| Evidence | Verbs that fit |
|---|---|
| Randomized or otherwise causal design | causes, increases, reduces, improves |
| Observational association | is associated with, predicts, correlates with |
| Consistent but limited evidence | suggests, may, is consistent with |
| Speculation | we hypothesize, one possibility is |

- Reserve "significant" for statistical significance and report the effect size and interval next to it; report exact p-values rather than thresholds where the venue allows. Statistical reporting rules: `../../ml-engineering/references/statistical-inference.md`.
- Generalize only to the population and conditions studied.
- Put limitations where they matter (in the sentence making the claim), and give them their own subsection too: what they are, the direction of the bias they could introduce, and what would resolve them.

## Paragraphs and sentences

- One idea per paragraph, announced in its first sentence.
- Move from known to new information inside a sentence and across sentences, so each sentence starts with something the reader already has.
- Keep subject and verb close; put the important word at the end of the sentence.
- Active voice when the actor matters ("we excluded"), passive when it does not ("samples were stored at -80 °C").
- One term per concept throughout; define abbreviations at first use and do not invent ones the field does not use.
- Numbers: SI units with a space (5 mg, 37 °C), significant figures that match the measurement's precision, the same number of decimals across a table.
- Cut words that carry no information ("it is important to note that", "in order to").

## Citing in the text

- Cite the primary source for a finding and a review for an overview.
- Cite what you have read; verify each citation supports its sentence (`citations-and-reference-managers.md`).
- Cite fairly: include strong work that disagrees with you.
- Keep self-citation to what a reader needs.

## Figures and tables

Tables for exact values readers will look up; figures for patterns and comparisons. Every figure and table is cited in the text, numbered in order of first mention, and understandable from its caption alone (what is shown, sample sizes, what error bars mean, statistical tests). Build them with code so they regenerate from the data (`../../data-engineering/references/publication-figures.md`).

## Writing process

1. Draft methods and results first (they are concrete), then introduction and discussion, then the abstract and title.
2. Write the first draft fast from the outline; leave `[[CHECK]]` markers instead of stopping to look things up.
3. Revise in separate passes: structure (does the argument flow, is anything missing), paragraphs (one idea each, topic sentences), sentences (clarity, length), consistency (terms, numbers between abstract, text, tables and figures), references.
4. Test on a cold reader: give the draft only, with three or four questions a reviewer would ask, to a colleague or a fresh helper without this conversation's context; fix whatever they answer wrongly (the same method as for design docs in `../../engineering-practices/references/docs-and-decisions.md`).
5. Before submission, check the reporting checklist, the venue's instructions and the bibliography (`scripts/bib_check.py`).

## Editing someone else's draft

- Keep every fact, number, condition and hedge; editing for clarity must not change meaning.
- Show changes (tracked changes in Word through `../../documents/references/word-docx.md`, or a diff for LaTeX and Markdown) and explain substantive ones.
- For authors writing in a second language, fix grammar and idiom without flattening their voice; flag sentences whose meaning is ambiguous rather than guessing.

## Tooling

- LaTeX: the venue's class, `latexmk` for builds, one sentence per line in the source for clean diffs.
- Word: the venue's template; edit through the documents module so styles survive.
- Markdown with pandoc and citeproc: fine for preprints, reports and theses where the institution accepts it.

## Checks (done when)

- [ ] Every number in the text matches an analysis output or a verified source; placeholders remain only where results do not exist yet and are listed.
- [ ] Each claim maps to evidence; verbs match the design's strength.
- [ ] Abstract, text, tables and figures agree on every number.
- [ ] Methods are reproducible, with software versions, and data and code availability stated.
- [ ] Limitations are specific; AI-assistance disclosure handled per venue policy.
- [ ] The reporting checklist, venue instructions and bibliography check are done.
