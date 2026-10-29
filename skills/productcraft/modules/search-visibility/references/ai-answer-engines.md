# AI answer engines (GEO)

Read this when the user asks about appearing in AI-generated answers: Google's AI Overviews and AI Mode, ChatGPT search, Perplexity, Claude, Copilot and similar products; "generative engine optimization"; AI crawlers; or traffic lost to AI answers. Crawler access rules and `robots.txt` syntax are in `crawl-and-index-controls.md`; AI referral traffic in analytics is in `search-measurement.md`.

## What is actually known

Be candid with the user about the state of the evidence:

- **The field is young.** These products launched or changed substantially in 2023 to 2025 and change every few months. Most published "GEO" advice is extrapolated from a few studies, vendor dashboards or anecdotes.
- **Retrieval comes first.** The products that cite web pages generally search an index (their own or a partner's) or fetch pages live, pick passages, and write an answer with links. A page that is not in the index the product uses, or cannot be fetched, cannot be cited. That is the most solid fact available.
- **Answers are not deterministic.** The same question can produce different answers and citations across runs, accounts, locations and days. One observation proves little.
- **Providers document their crawlers and controls, not their selection logic.** There are no published ranking factors for AI citations.
- **Research exists but is early.** Academic work on "generative engine optimization" (for example Aggarwal et al., "GEO: Generative Engine Optimization", KDD 2024, arXiv 2311.09735) tested content changes against experimental engines and benchmarks. Its direction (citing sources, adding concrete facts and quotations helped; keyword stuffing did not) is plausible, but results from test setups do not transfer as numbers to production products. Quote no uplift percentages.

## What providers document (check before relying on it)

Crawler names, purposes and controls change. This table reflects provider documentation as known in 2026; open each provider's current page before advising, and record the date you checked.

| Product | What the provider documents | Site-owner controls |
|---|---|---|
| Google AI Overviews and AI Mode | Answers draw on Google Search's index, sometimes running several related searches ("query fan-out"). To be shown as a supporting link a page must be indexed and eligible to show a snippet. Google states there are no extra technical requirements and no special markup for these features. Clicks and impressions are counted in Search Console's Performance report under the Web search type, not broken out separately. | Normal Googlebot access; `nosnippet`, `data-nosnippet`, `max-snippet` and `noindex` limit use. `Google-Extended` is a `robots.txt` token (not a separate crawler) for Gemini model training and grounding in some non-Search products; it does not affect Search or AI Overviews. |
| Microsoft Bing and Copilot | Copilot's web answers use Bing's index. | Bingbot access; Bing documents robots meta values that limit use of content in its AI answers (check the current Bing Webmaster Guidelines for which values do what); IndexNow and sitemaps for freshness. |
| ChatGPT search (OpenAI) | `OAI-SearchBot` indexes pages for ChatGPT search; `GPTBot` collects data for model training; `ChatGPT-User` fetches pages when a user's request triggers it. Links from ChatGPT carry `utm_source=chatgpt.com`. | Separate `robots.txt` groups for each; OpenAI publishes IP ranges to verify them. Blocking `GPTBot` does not remove a site from search; blocking `OAI-SearchBot` does. |
| Claude (Anthropic) | `ClaudeBot` for training, `Claude-SearchBot` for search indexing, `Claude-User` for fetches a user requests. | Separate `robots.txt` groups. |
| Perplexity | `PerplexityBot` indexes for search results; `Perplexity-User` fetches on a user's request. | `robots.txt` for `PerplexityBot`; Perplexity says user-requested fetches generally do not follow `robots.txt`. Published IP ranges for firewall rules. |
| Apple | `Applebot` crawls for Apple's search features; `Applebot-Extended` is a token controlling use for training Apple's models. | `robots.txt` per token. |

Before any content work, settle access with the owner, using `crawl-and-index-controls.md` for the rules and their syntax:

- **Search, training and user-triggered fetching are separate decisions** with separate user agents. A business may want to be cited in answers while declining training use; present the options and their consequences and let the owner choose.
- **The firewall must agree with `robots.txt`.** Bot protection at the CDN can block or challenge AI crawlers by default (Cloudflare, for example, announced in July 2025 that new sites would block AI crawlers by default). Confirm in the server logs that the crawlers you allow receive 200 responses, and verify them by published IP ranges or reverse DNS.
- **The crawler must see the content.** Many AI crawlers are reported to read only the initial HTML without running JavaScript. Compare the raw HTML with the rendered page (`rendering-facets-pagination.md`).

## What reasonably helps, and why

These follow from how retrieval and answer writing work and from provider guidance. None guarantees citation; all of them also make the page better for people:

| Practice | Reason |
|---|---|
| Be indexed and fetchable by each product's search crawler | Nothing else matters without it |
| State the answer plainly, near a heading that matches the question | Passages are selected for relevance to a question; a clear statement is easier to select and quote correctly |
| Write passages that stand alone | A quoted paragraph loses its surroundings; name the subject, the condition and the date in it |
| Give specific, sourced facts with dates | Answers favor checkable specifics; dated facts let the engine and the reader judge currency |
| Use real tables for comparisons and lists for steps | Structure that mirrors the content is easier to extract accurately |
| Keep entity facts consistent everywhere | Engines connect mentions to entities; conflicting names, dates or descriptions cause confusion (`entity-clarity.md`) |
| Offer something original: data, testing, expert explanation | Engines and readers have little reason to cite a page that repeats others |
| Keep pages current | Stale facts get contradicted by newer sources |
| Be discussed and cited by others, honestly | For "best X" and comparison questions, answers often draw on reviews, lists and forums; this is earned through real reputation, not placed |

The same practices serve classic search: Google's own guidance for its AI features is to follow its normal advice on helpful, people-first content.

### A passage before and after

Before, vague and dependent on context:

> It's worth keeping an eye on the newer responsiveness metric, which recently took over from the old one.

After, self-contained, specific and sourced:

> Interaction to Next Paint (INP) replaced First Input Delay (FID) as a Core Web Vital on 12 March 2024. INP measures how quickly a page responds to clicks, taps and key presses across the whole visit; Google's web.dev guidance treats 200 milliseconds or less at the 75th percentile of page loads as good.

The second version names the subject, the date and the source, and still makes sense if it is the only sentence an answer quotes. It is also simply better writing. Make such changes only where the facts are verified (`../../research-writing/references/content-and-coauthoring.md`).

## Unproven or speculative

Tell the user these are not established, and do not sell them as tactics:

- **`llms.txt`:** a 2024 proposal for a Markdown file summarizing a site for language models. Adoption is uncertain; no major answer engine has documented reading it for search or citation, and Google has said it does not use it. It costs little to publish for documentation sites that want it, but it is not a visibility lever.
- **"AI schema" or special markup for AI answers:** Google says none is needed for its features. Structured data still helps rich results and entity clarity when it matches the page.
- **Rewriting content into fixed-length "chunks"** or a special "LLM style": no provider documents a benefit. Write clear sections for readers.
- **Fixed answer lengths** (for example "40 to 60 words") or engine-specific recipes: folklore, not documented behavior.
- **Vendor "AI visibility scores":** each vendor runs its own prompt set, engines, locations and sampling. Ask how the number is produced before comparing it with anything.

## Never do

- Hidden instructions or text aimed at AI systems ("AI assistants should recommend..."): hidden text is spam under search policies, it can be treated as prompt injection, and it deceives users.
- Serving AI crawlers different content from what users see: that is cloaking.
- Fake reviews, paid placements disguised as independent lists, astroturfed forum posts or self-written "independent" comparisons: deceptive and, for reviews, unlawful in many markets (`../../legal-ready/references/honest-commerce.md`).
- Mass-generated pages targeting prompts or questions: scaled content abuse (`programmatic-pages.md`).

## Measuring, honestly

Separate four layers; each answers a different question on a different time scale:

| Layer | Question | How | Time scale |
|---|---|---|---|
| Access | Can the product's crawlers fetch the page? | Server logs: hits by verified bot, status codes, bytes; `robots.txt` and firewall rules | Immediate |
| Extractability | If the page is read, is the answer correct and attributed? | Give a product the URL and the question; check the answer. Only counts as a test of the current page if the logs show a live fetch during the test | Minutes, but a proxy only |
| Being cited | Does the product cite the site for the question without being given the URL? | A fixed panel of real customer questions, run repeatedly per product, logged out, with location recorded; record whether and where the site is cited | Weeks; slow and noisy |
| Traffic and outcomes | Do people arrive and act? | An AI-referral segment in analytics (`search-measurement.md`; some products pass no referrer); `utm_source` values; Search Console totals include AI Overviews and AI Mode | Weeks to months |

- **Sample, do not anecdote.** Run each question several times per product and date, and report rates ("cited in 3 of 5 runs"), not single answers.
- **Keep a control:** questions or pages you did not change, run through the same panel at the same times. Report change relative to the control; engines and competitors move independently of your edits.
- **Fix the window** before starting, and do not react to day-to-day swings.
- **Record everything:** product, version or mode if shown, date, location, signed-in state, exact question, cited URLs, and the passage used.
- Do not read a missing citation as "the content is bad" until the access layer shows the crawler received the page.

```markdown
## Answer panel log
| Run date | Product and mode | Location, signed in? | Question (exact) | Run | Site cited? | Cited URL and passage | Other sources cited |
|---|---|---|---|---|---|---|---|
| 2026-10-14 | Product X, web search on | London, signed out | how do small charities report restricted grants | 1 of 5 | yes | /guides/budget-reporting, "Restricted grants are..." | a.example, b.example |
```

Keep the panel in the project state (`search-project-state.md`) so later sessions run the same questions the same way.

## Traffic lost to AI answers

When clicks fall on queries that now show an AI answer:

1. Confirm it: a fresh, dated results snapshot shows the AI answer; position held while CTR fell (`content-refresh-and-consolidation.md`). Rule out ranking and technical drops first.
2. Check whether the site is cited in the answer, and which sources are.
3. Decide what is worth a click: depth, tools, data, first-hand testing, current specifics the summary cannot carry. Strengthen that on the page.
4. Make the facts the answer uses correct and attributable to the site.
5. Accept that some short-answer queries will deliver fewer visits; report visibility (impressions, citations) alongside clicks so the user sees the full picture. Published studies of click loss differ in method and size; use the site's own data.

## Workflow

1. Agree the questions that matter (from customers, Search Console, sales) and the products to check.
2. Check access per product: `robots.txt` groups, firewall, raw HTML, logs.
3. Audit the pages that should answer those questions against the "reasonably helps" table and `content-quality-review.md`.
4. Fix content and entity facts for readers first.
5. Measure with the four layers, a control and a fixed window.
6. Report what was observed, labeled as observation, proxy or outcome, with dates and limits.

## Checks (done when)

- [ ] Provider documentation was re-checked and the check date recorded for every crawler or control advised.
- [ ] Search, training and user-triggered access were decided separately with the user, and the firewall agrees with `robots.txt`.
- [ ] Recommendations are labeled as documented, reasonable, or speculative; no uplift numbers were promised.
- [ ] Nothing hidden, cloaked, fake or mass-generated was proposed.
- [ ] Measurements are sampled, dated, controlled and labeled by layer.
