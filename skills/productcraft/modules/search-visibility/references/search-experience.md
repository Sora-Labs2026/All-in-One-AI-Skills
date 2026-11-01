# Search experience: matching the page to the intent

Read this when a page is technically sound but does not rank or does not satisfy: the page type may be wrong for the query, impressions are high but visitors leave or do not act, organic landing pages convert poorly, or a landing template is being redesigned. Reading the results page is `serp-analysis.md`; content quality is `content-quality-review.md`; forms and conversion design are in `../../forms-conversion.md`; honest persuasion in `../../ethical-persuasion.md`; layout and accessibility in `../../responsive-accessibility.md`.

Search experience is the overlap of search and user experience: the page a searcher lands on should be the kind of page the query calls for, show what they came for on the first screen of their device, and let them finish the task. A page fails in one of two ways. It is the **wrong type** (a blog post for a query where the results are all product pages), so the engine rarely shows it; or it is the **right type with a poor experience**, so the people who do arrive leave without what they needed.

## 1. Find the page type the results reward

Take a pinned, dated snapshot of the results for the query group (`serp-analysis.md`) and classify each top result with the same set of page types you use for your own page:

| Page type | Recognized by | Must deliver on the first screen |
|---|---|---|
| Product | Price, buy button, variants, specifications | Name, image, price, availability, the buy action |
| Category or listing | A grid of items with filters | Items, filters, a sense of the range |
| Comparison or "best" guide | Several options assessed on stated criteria | The verdict or shortlist and who each suits |
| How-to or troubleshooting | Numbered steps, prerequisites | What it fixes, what you need, the first step |
| Explainer or definition | A topic explained | The answer in a sentence or two |
| Tool or calculator | Inputs and a result | The tool itself, usable at once |
| Local service page | Address or area, hours, call and booking | Location or area served, contact, availability |
| Signup or product landing page | Value statement, pricing link, call to action | What it is, for whom, the main action |
| Documentation or reference | Parameters, versions, code | The exact item searched, with version |
| Forum or community thread | Questions and replies by users | The question and its best answers |
| News | Dated reporting | The headline facts and date |

Count the types in the top results. A clear majority is the engine's current reading of the intent. A mix means the intent is split; choose the part you can serve best and say which. Your own page type is the second input.

## 2. Decide what to do about a mismatch

| Your page | Results mostly | Usual decision |
|---|---|---|
| Article | Products or categories | Target the query with a category or product page; let the article serve the learning queries that lead to it, and link the two |
| Product or landing page | Explainers and guides | Write the guide at its own URL and link to the product; do not stuff the product page with essay text |
| Prose guide | Tools or calculators | Build the tool if you can make it accurate and useful; otherwise retarget the guide |
| National page | Local packs and local pages | A location or service-area page only where the business really operates there (`local-search-and-map-listings.md`) |
| Single-vendor page | Comparisons of several options | An honest comparison page (`content-briefs-and-writing.md`), or accept that this query is not yours |
| Any | The same type as yours | The type is right; work on the experience below and on substance (`content-quality-review.md`) |

Prefer a new page of the right type plus links over twisting an existing page into a hybrid that serves neither intent. Check the target map first so the new page does not compete with an existing one (`keyword-and-topic-research.md`).

## 3. Write down whom the page serves, from evidence

Derive the jobs the page must do from sources you can cite, not from invented personas:

- **Result features:** "People also ask" questions, related searches and the format of any featured answer show follow-up needs and the expected form of the answer.
- **The site's own data:** site search terms from visitors who landed on the page, support tickets, sales and chat questions, reviews, on-page feedback.
- **Customer research** the business already has.

Write each job as a short statement with its source:

```markdown
| Job (who, wants, because) | Blocked by | Evidence | Page answers it? |
|---|---|---|---|
| A team lead comparing tools wants the price for 8 users, to get budget approval | Pricing per seat hidden behind "contact us" | 41 site searches for "price" from /compare in Sept (analytics, 2026-09-01..30) | No |
```

Keep personas to the few the evidence supports, and drop any you cannot trace to a source.

## 4. Check the first screen and the path to the goal

Open the page on a phone-sized viewport (around 360 to 400 CSS pixels wide) and on desktop, as a first-time visitor coming from search:

- The first screen shows what the page type promises (the table in step 1), not a hero image, a newsletter prompt or a consent wall covering everything.
- The main heading matches the query's intent and the result title that brought the visitor.
- The next step for each job in step 3 is visible or one obvious action away.
- Nothing jumps: layout stability and responsiveness are fine (`../../engineering-practices/references/performance.md`).
- Interstitials: Google's guidance treats pop-ups that cover the main content right after arriving from search as intrusive. Banners that use a reasonable share of the screen, and dialogs the law requires (cookie consent, age checks), are acceptable when they do not hide the content behind them.
- Mobile and desktop carry the same main content, links, structured data and metadata. Google indexes the mobile version; content only on desktop does not count.
- Content in tabs and accordions is fine when it is in the HTML; content that loads only after a click is not seen by crawlers (`rendering-facets-pagination.md`).
- Ads and promotions leave the main content readable and are labeled.
- Forms ask only for what the task needs and work with a keyboard and on a phone (`../../forms-conversion.md`).

## 5. Measure behavior honestly

| Signal | Where | What it can and cannot tell |
|---|---|---|
| Engagement rate and engaged time per organic landing page | Analytics (GA4 counts a session as engaged after 10 seconds by default, a key event, or two page views) | Rough interest; short visits can be satisfied visits on answer pages |
| Key events and conversions from organic entrances | Analytics | Whether the page does its commercial job |
| Site search after landing | Analytics site search report | What the page failed to answer; one of the clearest signals |
| Scroll depth, clicks on the main action | Analytics events | Whether the first screen leads anywhere |
| Clicks and click-through rate per query | Search Console | Whether the result is chosen; not what happens after |
| Recordings and heatmaps | Session tools | Qualitative only; need consent and masking of form fields and personal data (`../../legal-ready/references/policies-and-consent.md`) |
| Usability sessions with real users | Moderated or unmoderated tests | Why people struggle; small samples, strong insight |

- Do not present bounce rate, dwell time or "pogo-sticking" as confirmed ranking factors. Google has said, including in testimony in the 2023 US antitrust trial, that some ranking systems use aggregated interaction data, but it has not published how, so there is no behavioral target that maps to rankings. Improve the experience because it serves the visitor, and report search results from search data.
- Compare like with like (`search-measurement.md`): the same page group, query intent and device, over equal periods.

## 6. Change and test safely

- Change one template group at a time, and measure against a control group of similar pages over a window agreed in advance (`search-measurement.md`; tests in `../../ml-engineering/references/statistical-inference.md`).
- For A/B tests that touch indexable pages, follow the engines' testing guidance: show crawlers what users in the test see (no cloaking), use `rel="canonical"` from variant URLs to the original, use 302 redirects for redirect tests, and end tests when they have an answer.
- Persuasion stays honest: no fake urgency, scarcity or social proof to lift conversions (`../../ethical-persuasion.md`).

## Output: a page-intent brief

```markdown
## Search experience: <URL> for <query group>, <date>
Results snapshot: <engine, location, device, date>; dominant type: <type> (7 of 10); our type: <type>
Decision: <aligned | new page of type X at /path | restructure | retarget>, because <evidence>
Jobs (with evidence): <table from step 3>
First screen now: <what a phone shows on load>
First screen target: <what it should show, in order, with the element for each job>
Experience issues: <interstitials, parity, speed, forms ...>
Measures and window: <metrics, control group, dates>
Not verified: <what could not be checked and why>
```

## Done when

- [ ] The page type that the results reward was taken from a pinned, dated snapshot and compared with the page's type.
- [ ] Any mismatch has a decision (new page, restructure, retarget, accept) that respects the target map.
- [ ] Jobs and personas are traced to cited evidence; untraceable ones were dropped.
- [ ] The first screen on a phone and on desktop delivers what the page type promises, with no intrusive interstitial and with mobile parity.
- [ ] Behavior is reported with its sources and limits, without claiming behavioral metrics as ranking factors; tests followed the engines' testing guidance and had a control group.
