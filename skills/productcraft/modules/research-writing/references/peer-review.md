# Peer review: writing reviews and answering them

Read this when the user is reviewing a manuscript, preprint, grant proposal or thesis, or is responding to reviewers' comments. Evaluating evidence quality in general is in `appraising-evidence.md`; checklists by study type in `study-checklists-and-registration.md`; funder review criteria in `grant-proposals.md`.

## Before reviewing: confidentiality and AI policy

A manuscript or proposal under review is confidential. Many journals, publishers and funders forbid uploading it to generative AI tools; NIH, for example, has prohibited reviewers from using generative AI on applications since 2023. Before analyzing a document the user received as a reviewer, ask them to confirm that the venue's policy allows it (or that the material is already public, such as a preprint). If it does not, help in ways that need no access to the text: explain review criteria, a review structure, statistical questions in general terms.

Also check with the user: conflicts of interest with the authors, whether their expertise covers the paper (say which parts it does not), and the deadline.

## Reading in passes

1. **The claim and the design.** What is the central question and finding? Can this design, data and analysis support it? This decides most recommendations; write it down before getting lost in detail.
2. **Methods and statistics in detail.** Controls, sample size and its justification, randomization and blinding, unit of analysis, handling of missing data, multiple comparisons, model validation, software and versions, data and code availability.
3. **Results, figures and integrity.** Do numbers agree between text, tables and figures? Are error bars defined? Are all conditions shown? Any signs of duplicated or manipulated images, or of reused data? Is every planned analysis reported?
4. **Context.** Is related work represented fairly and accurately? Spot-check the citations that carry the argument (`citations-and-reference-managers.md`); check that the work is not already published elsewhere.
5. **Reporting and ethics.** Required checklist items; ethics approval and consent; trial or review registration and agreement between registered and reported outcomes; competing interests.
6. **Clarity.** Only after the substance: structure, figures, language.

## Writing the review

```markdown
**Summary of the submission**
<3-5 sentences in your own words: question, approach, main findings, claimed contribution>

**Overall assessment**
<Is the central claim supported? What is the main strength and the main problem? Importance for the field.>

**Major issues** (each would change the conclusions or the validity)
1. <What the issue is, where (section, figure, line)> - <why it matters> - <what would resolve it: analysis, control, data, rewording>
2. ...

**Minor issues** (clarity, presentation, small errors)
- <location: point and suggested change>

**Questions for the authors**
- ...

**Confidential comments to the editor** (if the system has this field)
<Concerns about integrity, conflicts, or fit; never put these only in the author-facing part>
```

Give a recommendation (accept, minor revision, major revision, reject) only where the editor asks for it, and keep it consistent with the major issues.

## Tone and fairness

- Critique the work, not the authors; no sarcasm, no rhetorical questions.
- Be specific: point to the place and say what would satisfy you.
- Separate what is essential for the claims from what would be nice to have. Request new experiments only when a claim depends on them, and say why.
- Acknowledge real strengths.
- Do not ask authors to cite your own work unless it is genuinely missing and relevant; never make acceptance depend on it.
- In double-blind review, do not try to identify the authors and do not reveal yourself.
- If you suspect misconduct, describe the observation factually in the confidential comments; do not accuse.

## Statistical questions worth asking

Many reviews miss the statistics because the reviewer is a domain expert. These questions catch most problems; ask the editor for a statistical reviewer when the analysis is beyond your expertise.

- What is the unit of analysis, and is it the unit that was randomized or sampled? (Cells from one animal, repeated measures and clustered designs are not independent observations.)
- Was the sample size justified before data collection?
- Were the primary outcome and analysis pre-specified, and are all planned analyses reported?
- How many tests were run, and is there a correction or a clear split between confirmatory and exploratory results?
- Are effect sizes and intervals reported, not only p-values? Is the effect large enough to matter?
- How were missing data and exclusions handled, and would the result survive a sensitivity analysis?
- For models: was the test set held out from all tuning, is performance compared with a simple baseline, and is there external validation?

## Reviewing grant proposals

Score against the funder's criteria, in the funder's terms (`grant-proposals.md`), and justify every score with specific strengths and weaknesses. Judge whether the aims are feasible with the team, time and resources described, whether the risks have credible alternatives, and whether the proposal would matter if it succeeded. Do not penalize a proposal for choices that are matters of taste. Keep the same confidentiality rules as for manuscripts.

## Reviewing talks, posters and slide decks

Render them to images and look at each page (`../../documents/references/convert-and-render.md`), then report findings by slide or panel number: overflow, overlaps, illegible text, contrast, figure readability, unsupported claims, and timing against the slot (`slides-and-talks.md`, `posters.md`).

## Answering reviewers

1. **Collect and number** every comment from every reviewer and the editor into one table: comment, category (will do, partly, decline, misunderstanding), planned action, owner, status.
2. **Do the work first,** then write. New analyses come from the authors' code and data; the agent drafts text around results the authors produced, never invents them (`[[AUTHORS: rerun model with site as random effect]]`).
3. **Response letter structure:** one short thank-you at the top; then each comment quoted in full, the response, and the change with its location ("Methods, lines 112-120: added ...") and the new text quoted. Answer every comment, including the ones you decline.
4. **Disagreeing:** acknowledge the concern, explain with evidence or citations why the original approach stands, and offer a compromise when there is one (a sensitivity analysis, a clarified sentence, a limitation). Polite firmness works; arguing tone does not.
5. **Misunderstandings** mean the text was unclear: rewrite it, and say you did.
6. **Keep the manuscript consistent:** after changes, recheck abstract, figures, tables and numbers everywhere, and provide a tracked-changes or highlighted version if the venue asks.
7. **Conference rebuttals** have tight length limits and often forbid new results or links: correct factual misreadings first, answer the issues raised by more than one reviewer, and skip minor points.

## Checks (done when)

- [ ] Venue policy on AI and confidentiality confirmed before any confidential text was processed.
- [ ] The review states the central claim and whether the evidence supports it, with numbered, located major issues and what would resolve each.
- [ ] Requests are proportionate and separated into essential and optional.
- [ ] For a response letter: every comment answered, every change located and quoted, no result claimed that the authors did not produce, manuscript consistent after edits.
