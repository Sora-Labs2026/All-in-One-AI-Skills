# Content quality review

Read this when the user asks whether a page is good enough to publish, why a page or section may be seen as low quality, or for an E-E-A-T or "helpful content" review. The checklist below is ProductCraft's own editorial review, built on the public concepts in Google's guidance on creating helpful, reliable, people-first content and on experience, expertise, authoritativeness and trust (E-E-A-T) from its Search Quality Rater Guidelines. It finds problems a reader would notice. It does not predict rankings: E-E-A-T is not a score Google computes, and rater judgments do not directly change rankings.

## Set up the review

Record before starting:

- **The page:** URL or draft, and the version reviewed.
- **Page type:** article, how-to, comparison, review, product or landing page, local page, generated page, news, documentation.
- **Audience and market:** who it is for, country, language.
- **Stakes:** does a mistake here affect someone's health, money, legal position, safety or civic participation? If yes, apply the high-stakes rules throughout.
- **What you can observe:** the page alone, the rendered page, or the site around it (author pages, about, policies, reputation). Site-level questions cannot be answered from a pasted draft; mark them unknown.
- **Date of the review.**

## Rate each question honestly

Use five states, and attach evidence (quote, location, screenshot, link) to every answer:

| State | Meaning |
|---|---|
| Met | The page clearly does this; evidence attached |
| Partly | Some of it; say what is missing |
| Not met | The page fails it; say where |
| Unknown | Applicable, but you could not check (no access to the rendered page, author page or site); say why |
| Not applicable | Does not apply to this page type; say why |

Do not turn the answers into a single number unless the user asks. If they do, count only questions you could observe, show the arithmetic, and report the unknowns next to the number. Never treat unknown as met, and never drop applicable questions to raise a total.

## Blocking issues: fix before publishing

Any one of these blocks publication until fixed, whatever else is good:

1. **Broken promise:** the title, heading or description promises something the page does not deliver.
2. **Errors or contradictions:** a factual error a reader could check, or the page contradicting itself on a material point.
3. **Hidden interest:** an affiliate, sponsorship, ownership or other material relationship that is not disclosed clearly near the relevant content.
4. **Invented evidence:** made-up statistics, quotes, test results, experiences, customer stories, authors or credentials.
5. **High-stakes content without competent review,** or advice that could cause harm.
6. **Deception in the page itself:** content shown to search engines differently from users, hidden text, misleading buttons or functionality, ads disguised as content.
7. **Copied or lightly reworded content** from other sources with nothing added.
8. **Markup that misrepresents the page:** ratings, prices, authors or dates in structured data that are not visible or not true.

A broken outbound link or a typo is a fix, not a block. A short page is not thin if it fully does its job.

## The review passes

### 1. Purpose and fit

- Who is this page for, and is that stated or obvious?
- What task brings the reader here, and does the page complete it, or at least hand them the next step?
- Does the topic belong to what this site is about and has standing to cover?
- Would the publisher make this page if search engines sent no traffic?

### 2. Substance and originality

- What does the page offer that the reader cannot get from the pages already ranking: original reporting, research, data, testing, analysis, a tool?
- Does it go beyond the obvious, or restate what everyone says?
- Where it draws on other sources, does it add real value (synthesis, judgment, correction, examples) rather than paraphrase?
- Is the coverage complete enough that the reader will not have to search again?
- Is everything on the page there for the reader, or is some of it padding, repetition or filler for length?

### 3. First-hand experience

- Does the author show they did the thing: used the product, ran the process, visited the place, handled the case?
- Is there evidence only first-hand work produces: original photos or screenshots, measurements, timings, results, problems encountered and how they were solved?
- Are limitations stated: what was not tested, where results may differ?

### 4. Accuracy and expertise

- Are the claims correct? Spot-check the most important ones against primary sources.
- Are sources cited where claims are made, with dates for anything that changes?
- Do numbers have their unit, denominator, time period and source?
- Is the reasoning visible, so an expert could follow and check it?
- Is the content written or reviewed by someone who demonstrably knows the subject? For high-stakes topics, is that person named with relevant qualifications and a review date?

### 5. Transparency and trust

- **Who:** is there a byline where readers would expect one, linking to an author page with a true background? Can the reader find who runs the site (about page, contact details, company information)?
- **How:** for reviews and tests, is the method described? For data, the source? Is the use of automation or AI disclosed where readers would expect to know?
- **Why:** are commercial relationships disclosed near the recommendations they affect?
- Is there a way to report errors, and evidence that corrections are made?
- Do ads and promotions leave the main content readable, clearly separated and labeled?

### 6. Presentation

- Does the main heading describe the content accurately, without exaggeration or shock?
- Can a reader find the answer quickly? Do headings form a useful outline?
- Is it well produced: correct spelling and grammar, consistent terms, working media, no signs of haste?
- Does it work on a phone: readable text, usable tables, no intrusive pop-ups blocking the content? (Speed and Core Web Vitals: `../../engineering-practices/references/performance.md`.)

### 7. Signs the page was made for search engines

Each of these is a warning sign. One alone may be innocent; several together usually mean the page needs rethinking, not polishing:

- Length chosen to hit a word count.
- The site publishing on many unrelated topics in the hope that some rank.
- Heavy automation producing many similar pages with little review.
- Mostly summarizing others without adding anything.
- Writing about a trend only because it is trending, not because the audience needs it.
- Answering a question that has no answer yet (an unannounced release date) as if it did.
- A refreshed date with no meaningful change to the content.
- Large batches of content added or removed mainly to make the site look fresh.
- The reader would need to go back to the results for a better answer.

### 8. Reputation (site level)

- What do independent sources say about the site or author: news coverage, professional bodies, reviews, recognition, complaints? Raters are asked to research this; a reviewer can too.
- For high-stakes topics, is the site or author recognized by others in the field?
- Mark this pass unknown when you cannot research it, and never manufacture reputation signals.

## What matters most by page type

| Page type | Weigh most | Typical blocking risk |
|---|---|---|
| Product review | First-hand experience and evidence, method, drawbacks, disclosure | Undisclosed affiliate relationship; reviews of products never used |
| Comparison or alternatives | Fair criteria, sourced and dated facts, who each option suits | Misstated competitor facts; the publisher's own product not disclosed |
| How-to or documentation | Accuracy, tested steps, versions, troubleshooting | Steps that do not work; outdated versions |
| High-stakes article | Expertise, named qualified reviewer, current primary sources, scope | No competent review; unsafe advice |
| Product or landing page | Substantiated claims, clear pricing and terms, honest proof | Unsupported claims; fake testimonials (`../../legal-ready/references/honest-commerce.md`) |
| News | Dates, sourcing, bylines, corrections | Unattributed claims; misleading headline |
| Generated or templated page | Unique data per page, usefulness per page | Interchangeable pages (`programmatic-pages.md`) |
| Local page | Real local information, consistent business details | Doorway-style city swaps |

## Write the findings

```markdown
## Quality review: <page>, <version>, <date>
Type: <page type> | Audience: <who, market> | Stakes: <high / normal> | Observed: <page only / rendered / site>

Blocking issues: <none, or each with location and evidence>

| Pass | Finding | Evidence (location) | Why it matters to the reader | Fix | Severity |
|---|---|---|---|---|---|
| Accuracy | The pricing table lists the 2025 plans | Section "Plans", row 2 | Readers will budget wrongly | Update from the pricing page, add "checked on" date | important |

Unknown: <questions you could not check, and what access would settle them>
Strengths to keep: <what works, so revisions keep it>
```

Order findings by impact on the reader: blocking, then important, then polish. Name the three changes that would help most.

## Revise and re-review

1. Fix blocking issues first, then the important findings.
2. Re-review only the passes the changes touched, and confirm each fixed item with new evidence.
3. Stop after two or three rounds and hand the remaining items to the user with the reason.
4. Never fix a finding by adding a signal that is not true: no invented author bios or credentials, no backdated or forward-dated content, no fake reviews, no markup for things that are not on the page.

## Checks (done when)

- [ ] Page, type, audience, stakes, observable scope and date are recorded.
- [ ] All blocking issues were checked, and any found are fixed or reported as blocking.
- [ ] Every applicable question has a state and evidence; unknowns are listed with the reason.
- [ ] Findings say where, why it matters, and how to fix, ordered by impact.
- [ ] No score was reported without its observed coverage, and no finding was fixed with an untrue signal.
