# Briefs and writing pages that serve people first

Read this when writing or planning a page meant to be found in search: an article, a guide, a comparison or alternatives page, a review, a glossary entry, a product or landing page. General writing craft (briefs, research logs, outlines, voice, titles without clickbait, co-authoring) is in `../../research-writing/references/content-and-coauthoring.md`; follow it and add what is here. Persuasive copy follows `../../ethical-persuasion.md`. Reviewing a finished page is `content-quality-review.md`.

The principle behind every rule below: write the page you would publish if search engines did not exist, for the person who typed the query, and make it easy for both the person and the engine to see what it offers.

## Before writing: the search brief

Write the brief into the project state and get the user's agreement on it. It extends the general brief with search evidence:

```markdown
## Brief: <working title>
Target: query group <lead query> -> URL <existing or new path> (from the target map)
Intent: <learn / compare / act / go / local>, confirmed on results snapshot <date, market, device>
Reader and task: <who, what they are trying to get done, what they already know>
The answer in two sentences: <what the page will tell them>
Must cover: <sub-questions every good result covers, plus People also ask and customer questions>
Our edge: <first-hand testing, data, product access, expert, local knowledge> and who provides it
Evidence needed: <facts, numbers, quotes to verify; research log location>
Page type and format: <guide, comparison table, calculator, steps with screenshots ...>
Author and reviewer: <named person with real experience; qualified reviewer for health, money, legal or safety topics>
Links: from <existing pages that should link here>; to <next steps and sources>
Title and description options: <2-3 each>
Structured data: <type that matches the visible content, or none>
Done when: <checks, including content-quality-review.md passes>
```

If the "our edge" line is empty, stop and discuss it with the user. A page with nothing to add to what already ranks is the kind of content search engines try to demote, and readers do not need it.

## Structure for the reader, which also serves the engine

- **Answer early.** State the core answer or verdict in the opening lines, then support it. Readers who need only the answer get it; the rest keep reading for the depth.
- **Headings that say something.** Each heading names what the section delivers ("Which plan fits a team of five" rather than "Pricing"). Read the headings alone: they should form a useful outline.
- **One idea per section,** short paragraphs, lists for parallel items, numbered steps for procedures, tables for comparisons of the same attributes across options.
- **Define terms** the audience may not know at first use.
- **Self-contained passages.** A paragraph quoted alone, in a snippet or an AI answer, should still be true and clear: name the subject instead of "it", include the condition or date it depends on.
- **Caveats and limits** where they apply: when the advice does not hold, what was not tested.
- **No padding.** There is no word count that search rewards; Google says so explicitly. Length follows the task: a precise answer can be short, a decision guide can be long.
- **A next step** that fits the intent: the related task, the comparison, the product, the source.

## Words people use

- Use the reader's own words for the topic in the title, the main heading and where they fit naturally. Synonyms and related terms come naturally when the topic is covered well.
- There is no keyword density to hit. Repeating phrases, stuffing lists of keywords or locations, or hiding text is spam under Google's policies and makes the page worse.
- The `meta keywords` tag is ignored by Google; do not spend time on it.

## Titles and descriptions

- The title names the page's subject and promise accurately and specifically. Each page has its own.
- The description summarizes what the page offers in a sentence or two. Engines often build the snippet from page text instead, which is another reason to state answers clearly in the body.
- Google may replace a title that is vague, stuffed, boilerplate or inaccurate with text from the page (its title system changed in August 2021). A title that matches the main heading and the content is replaced less often.
- Promise only what the page delivers: no "ultimate", "complete" or a year in the title unless true, no invented numbers, no false urgency.
- Lengths and markup are in `on-page-elements.md`; Open Graph and social cards in `structured-data-and-social-cards.md`.

## Showing experience and expertise

Search engines describe what they reward in terms of experience, expertise, authoritativeness and trust (E-E-A-T, from Google's Search Quality Rater Guidelines). It is not a score or a single ranking factor; it describes what readers trust. Show it with evidence, not adjectives:

- **Experience:** what the author actually did: used the product for how long, ran the test, visited the place, fixed the problem. Original photos, measurements, screenshots, results, and the problems met along the way.
- **Expertise:** correct, precise explanation; primary sources; reasoning shown; edge cases known.
- **Who wrote it:** a byline that links to an author page with a real, true biography. Never invent authors, credentials, reviewers or testimonials.
- **How it was made:** for reviews and tests, the method; for data, the source and date; for automation or AI assistance, a note where readers would reasonably expect one.
- **Why it exists:** if the page earns money from what it recommends, say so plainly near the recommendation.

## Page types

### How-to and troubleshooting

Prerequisites, versions and time needed first; numbered steps that were actually performed and tested, with the expected result of each; the errors people hit and their fixes; how to verify success. State the product version and date; revisit when it changes.

### Comparisons and alternatives

Comparison pages ("X vs Y", "X alternatives", "best tools for Z") serve people who are choosing. They deserve particular care because the publisher often has a stake.

- **Keep one data file per product compared,** with each attribute, its value, the source and the date checked. Reuse it across pages so a price change is fixed once.
- **Same criteria for every option,** chosen from what buyers care about, stated up front.
- **Be fair:** state real strengths of competitors and real limits of the user's own product. Say who each option suits best, including when it is not the user's.
- **Sourced and dated facts only.** Prices, features and limits change; show "checked on" dates and update them. Mark unverified items as such rather than guessing.
- **Disclose** affiliate links, sponsorship and the publisher's own product in the comparison, close to the recommendation.
- **Claims about named companies** must be accurate and fair; comparative advertising and review law apply (`../../legal-ready/references/honest-commerce.md`).
- Listing "alternatives" means real, current options a buyer would consider, not a list padded with weak options to make one shine.

```yaml
# data/compare/acme-tracker.yaml : one file per product, reused by every page that mentions it
product: Acme Tracker
vendor: Acme Software Inc.
relationship: none            # none | affiliate | partner | ours  (drives the disclosure line)
best_for: "Small teams that need time tracking with invoicing"
not_ideal_for: "Teams that need on-premises hosting"
attributes:
  - name: Entry plan price
    value: "USD 9 per user per month, billed annually"
    source: https://acme.example/pricing
    checked: 2026-10-02
  - name: Offline mode
    value: "Mobile apps only"
    source: https://acme.example/docs/offline
    checked: 2026-10-02
  - name: Data export
    value: unknown            # not verified; the page shows "not confirmed", never a guess
strengths: ["Invoicing built in (checked in a trial account, 2026-10-02)"]
limits: ["No on-premises option (pricing page FAQ, 2026-10-02)"]
```

A check before publishing fails the page if any attribute shown is older than the agreed review interval or lacks a source.

### Reviews

Google's guidance on high-quality reviews asks for evidence of first-hand use, quantitative measurements where relevant, what sets the product apart, comparison with alternatives, benefits and drawbacks, and the factors that matter to the buyer's decision. Show your own photos and results. Review markup only describes real reviews on the page, never a self-assigned rating (`../../legal-ready/references/honest-commerce.md`).

### Definitions and glossary entries

Lead with a precise one- or two-sentence definition, then what it is used for, an example, how it differs from neighbors, and links to deeper pages. A glossary entry that only restates a dictionary adds nothing; include the context your audience needs.

### Product, service and landing pages

Match the action intent: what it is, who it is for, price or how pricing works, what happens after the click, proof that is real (`../../ethical-persuasion.md`). Thin landing pages cloned per city or audience with swapped names are doorway pages; see `programmatic-pages.md` for when many similar pages are legitimate.

## Topics where mistakes hurt people

Health, money, legal matters, safety and civic information are what the rater guidelines call "your money or your life" topics, held to the highest standard.

- A named author with relevant qualifications, or a qualified reviewer named on the page with the review date.
- Current primary sources (regulators, guidelines, peer-reviewed research), cited where the claim is made, with dates.
- Clear scope: general information, not personal advice; where to get professional help.
- Never invent a reviewer, a credential or an expert quote. If no qualified reviewer is available, say so to the user and mark the draft unreviewed.

## Drafting with AI assistance

Google's position (published February 2023 and reflected in its spam policies since March 2024) is that how content is produced matters less than whether it is helpful; using automation mainly to manipulate rankings, especially at scale, is spam (scaled content abuse). In practice:

- The draft is a starting point. A person with knowledge of the topic checks every fact, adds the first-hand material, and owns the result.
- Never generate experience you do not have: no fabricated tests, anecdotes, quotes, statistics, customer stories or authors. Missing material gets a visible marker (`[[NEEDS SOURCE: ...]]`) and goes on the user's list.
- Disclose AI assistance where readers would expect to know, and follow the publisher's own policy.
- Do not mass-publish drafts. Volume without review is exactly the pattern the spam policies describe.

## Links

- **Internal:** link from relevant existing pages to the new one with descriptive anchor text, and from the new page to the next useful step. Update the hub page of the topic. Architecture and orphan checks are in `site-structure-and-internal-links.md`.
- **External:** cite primary sources where claims are made. Linking out to good sources helps readers; there is no reason to avoid it.
- **Paid or sponsored links** carry `rel="sponsored"`; user-generated links carry `rel="ugc"` or `rel="nofollow"`.

## Before publishing

- [ ] The page answers the brief's two-sentence answer, early and clearly.
- [ ] Every fact, number and quote traced to the research log; dates shown on time-sensitive facts.
- [ ] The edge is visible: original evidence, testing or expertise that the current results lack.
- [ ] Author byline links to a true author page; reviewer named for high-stakes topics.
- [ ] Disclosures sit next to recommendations; no undisclosed commercial relationship.
- [ ] Title and main heading match the content; no exaggeration.
- [ ] Structured data, if any, describes only what is visible on the page.
- [ ] Internal links added both ways; the target map updated.
- [ ] `content-quality-review.md` passes with no blocking issue.

## Checks (done when)

- [ ] A search brief with intent evidence, an edge and an author was agreed before drafting.
- [ ] The draft follows the structure rules and contains no padding, stuffing or invented material.
- [ ] Comparison and review pages use sourced, dated data files and fair criteria, with disclosures.
- [ ] High-stakes topics have a named qualified reviewer, or the draft is marked unreviewed.
- [ ] The pre-publishing list is complete, and anything not verified is listed for the user.
