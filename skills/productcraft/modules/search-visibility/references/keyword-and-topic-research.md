# Keyword and topic research

Read this when the user asks what people search for, what to write next, which queries a page should target, how to group queries into topics, or how to prioritize a list of keywords. Reading the results page for a query is `serp-analysis.md`; comparing your coverage with other sites is `competitor-and-gap-analysis.md`. The goal is a short, evidenced list of topics worth a page, each mapped to one URL, not a spreadsheet of thousands of terms.

## Start from the business, not the tool

Collect before searching, and write it into the project state (`search-project-state.md`):

- **Offer and audience:** what the site sells or provides, to whom, and what those people are trying to get done.
- **Market:** country or region, language, and whether intent is local ("near me", city names).
- **Goal:** sign-ups, sales, leads, readership, support deflection. A query that cannot lead toward the goal is reach at best.
- **What exists:** the current pages and which queries they already get impressions for.
- **What the site can credibly say:** first-hand experience, product knowledge, data, expert staff. A topic the site has no standing to cover is a poor target however large its volume.

## Where demand data comes from, and what each number means

| Source | What it tells you | Limits to state |
|---|---|---|
| Search Console Performance report (your own site) | Queries that already show your pages, with clicks, impressions, CTR and average position | Only queries where you appear; anonymized queries are omitted from the query table but counted in totals; average position is an impression-weighted average, not a rank; 16 months of history; the UI table stops at 1,000 rows (use the API or the bulk export for more) |
| Bing Webmaster Tools (your site and its keyword tool) | The same for Bing, plus Bing's own volume estimates | Bing's market share differs by country |
| Google Ads Keyword Planner | Monthly volume for a market and language, grouped close variants, seasonality | Needs an Ads account; low-spend accounts see ranges; close variants are merged, so volumes do not add up across variants |
| Google Trends | Relative interest over time and between places, 0 to 100 within your selection | An index, not a volume; sampled; compare terms only within the same Trends request |
| Autocomplete, People also ask, related searches | Real phrasings and follow-up questions | Personalized and location-dependent; qualitative only |
| Site search logs, support tickets, sales calls, reviews | The words your actual customers use | Personal data: aggregate and strip identifiers before analysis; follow the privacy policy |
| Third-party SEO tools (volume, "keyword difficulty", traffic estimates) | Rough size and competition for queries you do not rank for yet | Vendor models built from panels and clickstream data, not Google data; tools disagree widely; "difficulty" is mostly a link-count estimate on the vendor's own scale |

Label every number with its kind and origin:

- **Measured:** from the user's own Search Console, Bing Webmaster Tools, analytics or logs. Name the property, date range, country and device filter.
- **Vendor estimate:** name the tool, its database or market, and the date pulled. Compare difficulty scores only within one tool.
- **User-provided**, **Calculated** (show the formula) or **Unknown** (with the reason). Never fill a gap with a guess presented as data.

When two sources disagree, keep both values side by side. Do not average a Search Console count with a vendor estimate.

## Intent: what the searcher wants to happen next

Classify each query by the task behind it, then confirm with the live results page, which shows how the engine currently reads that intent:

| Intent | The searcher wants to | Page that usually serves it |
|---|---|---|
| Learn | Understand, fix or decide something | Explainer, tutorial, troubleshooting guide, reference page |
| Compare | Weigh options before choosing | Comparison, review, "best for" guide with real criteria |
| Act | Buy, sign up, book, download, contact | Product, pricing, signup, booking or local service page |
| Go | Reach a known site, product or account | The homepage, login, docs or product page itself |
| Local | Find a provider near a place | Local business page and its Business Profile |

- Many queries mix intents ("best CRM for nonprofits" is comparison with learning). Serve the dominant intent first; the results page tells you which it is.
- Questions are not always informational: "how much does X cost" is often comparison or action.
- Brand plus a modifier ("X pricing", "X login", "X vs Y") belongs to the brand's own pages or to honest comparison pages (`content-briefs-and-writing.md`).
- If the results page is dominated by a page type you cannot honestly provide (retailer category pages for a shopping query, government pages for a legal requirement), the query is probably not yours.

## Expand, then collapse

Expand a seed into candidates with modifiers that real people use: audience ("for teams"), constraint ("without coding", "free"), comparison ("vs", "alternative"), problem ("not working", "error"), format ("template", "checklist", "calculator"), place and time. Questions from People also ask and from support tickets are often the best candidates.

Then collapse. Variants that one page can satisfy belong on one page. Creating a page per variant produces thin near-duplicates and competes with itself. The practical test is overlap of results: if two queries return mostly the same top pages, the engine treats them as one need.

```python
# Group queries by overlap of their top results. Input CSV: query,rank,url from one snapshot
# (same engine, market, language and device), with queries listed in priority order.
import csv, sys

TOP, SHARED = 10, 3     # join a group when at least 3 of the top 10 URLs match its lead query; tune on known pairs
top = {}
with open(sys.argv[1], newline="") as f:
    for row in csv.DictReader(f):
        if int(row["rank"]) <= TOP:
            top.setdefault(row["query"].strip().lower(), set()).add(row["url"].split("#")[0].rstrip("/"))

groups = []                                   # [lead query, members]; compare with the lead only, so groups don't chain
for query, urls in top.items():
    lead = next((g for g in groups if len(top[g[0]] & urls) >= SHARED), None)
    if lead: lead[1].append(query)
    else: groups.append([query, [query]])
for lead, members in groups:
    print(f"{lead}: {len(members)} queries | " + " | ".join(members[1:]))
```

- Results data must come from a source the user is entitled to use: their rank tracker or SERP data provider, or manual checks. Automated querying of search engines outside their terms is not an option.
- Tune `SHARED` on a few pairs you already know belong together or apart. Spot-check every group with more than a handful of members, and any group whose lead has a different intent from its members.
- Without results data, group by meaning and intent by hand and mark the grouping as unverified.

## Topics and hubs

A topic is a set of query groups a reader would expect one site to cover together. Organize it as a hub page that answers the broad question and links to focused pages for each sub-need, which link back and to their close siblings. Before committing to a topic:

- List the sub-needs you can genuinely serve. A topic padded with pages that exist only to fill the hub weakens it.
- Check what you can add that the current results lack: data, testing, tools, examples, expert explanation.
- Plan the internal links as part of the topic, using descriptive anchors (link structure and crawl depth: `site-structure-and-internal-links.md`).
- Publish the hub and the strongest supporting pages first. Add more only when a sub-need has its own demand or a reader would miss it.

## One need, one page: the target map

Keep a target map in the project state: each query group points to exactly one primary URL.

| Query group (lead query) | Intent | Primary URL | Status | Evidence | Owner |
|---|---|---|---|---|---|
| project tracking for nonprofits | compare | /solutions/nonprofits | live | GSC 2026-07-01..09-30: 4.1k impressions, avg pos 14 (Measured, US, all devices) | content |

Check the map before creating any page. If a group already has a page, improve that page instead of adding another.

**Cannibalization** is two or more of your pages competing for the same need. Look for it in Search Console: filter by a query and open the Pages tab; several URLs sharing impressions, or the top URL switching between dates, are the signals. Across many queries, use query-and-page rows from the API or the bulk export:

```python
# Queries where several of your pages split impressions. Input CSV from the Search Console API or bulk
# export with columns query,page,clicks,impressions for one date range, search type and country.
import csv, sys
from collections import defaultdict

MIN_IMPRESSIONS, MIN_SHARE = 100, 0.2     # ignore small queries; a page counts if it has 20 % of impressions
by_query = defaultdict(dict)
with open(sys.argv[1], newline="") as f:
    for r in csv.DictReader(f):
        by_query[r["query"]][r["page"]] = (int(r["clicks"]), int(r["impressions"]))
for query, pages in sorted(by_query.items(), key=lambda kv: -sum(i for _, i in kv[1].values())):
    total = sum(i for _, i in pages.values())
    if total < MIN_IMPRESSIONS: continue
    split = {p: v for p, v in pages.items() if v[1] / total >= MIN_SHARE}
    if len(split) > 1:
        print(f"{query} ({total} impressions): " + "; ".join(f"{p} {i / total:.0%} impr, {c} clicks" for p, (c, i) in split.items()))
```

The output is a list of candidates, not verdicts. It is not always a problem: a product page and a help page can rightly appear for a brand query, and two results from one site can both be useful. When it is a problem, in order of preference:

1. Make the pages serve clearly different needs, and retitle them to say so.
2. Merge them into the stronger URL and redirect the other (`content-refresh-and-consolidation.md`).
3. Point internal links for that need at the chosen page.
4. Use a canonical link only for pages that really are duplicates or near-duplicates; it is a hint, not a merge.

## Prioritize openly

Avoid precise-looking scores built from vendor estimates. Rank candidates by four judgments, each written with its evidence:

| Factor | Ask | Evidence |
|---|---|---|
| Value | If this page ranked, would the visitor be someone the business serves, at a useful stage? | Offer, goal, intent |
| Demand | Is there enough search interest to matter, now or seasonally? | Search Console (Measured) or a range from Keyword Planner or a tool (Vendor estimate) |
| Feasibility | Can this site realistically earn a place? | The results page (`serp-analysis.md`): who ranks, whether focused sites like yours appear, your current position |
| Edge | Can you make the best page for it? | Expertise, data, product access, first-hand testing |

- **Queries where you already appear** are often the cheapest wins: queries with steady impressions where the page sits just outside the top few results. Read position per query and page, not the site average, and expect improvement only when the page clearly falls short of the need. Nothing is guaranteed.
- Group candidates into tiers (now, next, later, no) with one line of reasoning each. If the user wants a numeric score, agree the weights with them, show the arithmetic, and show how the order changes when a weight moves.
- Low-volume queries with clear intent and a strong fit often beat large vague ones, and volume tools undercount specific long queries.

## Seasonality, markets and languages

- Read seasonality from Trends and from year-over-year Search Console data. Publish or update ahead of the rise, using your own history of how long new pages take to be indexed and to settle.
- Compare like with like: the same weeks year over year, the same country and device filters, and note algorithm updates (Google lists them with dates on its Search Status Dashboard) and site changes that fall inside a window.
- Research each market in its own language with native speakers or local data. Translated keyword lists miss how people actually phrase things and which brands they name. Language and country targeting (hreflang) is in `international-hreflang.md`.

## Queries that AI answers absorb

Definitions, quick facts and simple how-tos increasingly get an AI-written answer at the top of the results. Mark such queries in the research, keep them where they matter to the reader journey, and plan for fewer clicks per impression. Read `ai-answer-engines.md` before promising traffic from them.

## Deliverable

1. One paragraph: market, goal, data sources and date ranges used.
2. The recommended topics, each with its query groups, intent, primary URL (existing or new), evidence and tier.
3. Queries deliberately excluded and why (wrong intent, no standing, served by an existing page).
4. Open questions for the user (missing access, business priorities to confirm).
5. Updated target map in the project state.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Treating a tool's volume or difficulty as fact | Label it as a vendor estimate with tool and date; prefer Search Console where it exists |
| A page for every keyword variant | Collapse by results overlap and intent; one page per need |
| Ignoring intent because the volume is large | Confirm intent on the live results page before planning |
| Copying a competitor's keyword list | Start from your audience and your edge; use competitors for gaps (`competitor-and-gap-analysis.md`) |
| Reading site-wide average position as progress | Report per query group and page, with date ranges and filters |
| Comparing a holiday month with an ordinary one | Compare the same period year over year and note updates in the window |

## Checks (done when)

- [ ] Market, language, goal and data sources are written down, with date ranges and filters.
- [ ] Every number is labeled Measured, Vendor estimate, User-provided, Calculated or Unknown.
- [ ] Each recommended query group has an intent confirmed on a dated results snapshot, or is marked unverified.
- [ ] Each group maps to exactly one URL in the target map; cannibalization candidates are listed with evidence.
- [ ] Priorities are tiers with reasons the user can challenge, not unexplained scores.
