# Competitor and content-gap analysis

Read this when the user wants to know who they compete with in search, what those sites do better, which topics or formats the site is missing, or which gaps to close first. Market sizing and business positioning are in `../../research-writing/references/market-research.md`; single-query analysis is `serp-analysis.md`. The output is a short list of gaps worth closing, each with evidence and a reason the user can make something better.

## Search competitors are not only business rivals

The sites that compete for your queries include publishers, marketplaces, review sites, forums, government pages and tool vendors, not just companies that sell the same thing. Identify them from the results, across the query groups in the target map (`keyword-and-topic-research.md`):

```python
# Which domains hold the top results across your query set. Input CSV: query,rank,url (one snapshot).
import csv, sys
from collections import Counter
from urllib.parse import urlsplit

seen = {10: set(), 3: set()}; queries = set()
with open(sys.argv[1], newline="") as f:
    for r in csv.DictReader(f):
        host = (urlsplit(r["url"]).hostname or "").removeprefix("www.")
        queries.add(r["query"])
        for cut in seen:
            if int(r["rank"]) <= cut: seen[cut].add((r["query"], host))   # count a domain once per query
top10, top3 = (Counter(h for _, h in seen[c]) for c in (10, 3))
for host, n in top10.most_common(25):
    print(f"{host:32s} top 10 for {n / len(queries):4.0%} of queries, top 3 for {top3[host] / len(queries):4.0%}")
```

- The input is one dated snapshot from a source the user may use (their rank tracker or SERP data provider, or manual checks), with location, language and device recorded.
- Weight by what matters: run it per topic or intent, since a domain strong in how-to queries may be absent from commercial ones.
- Pick three to five sites to study: the ones that recur where the user most wants to win, plus one smaller site that ranks above its apparent weight (it shows what focus can achieve).

## What to compare

| Dimension | Look at | Source and label |
|---|---|---|
| Coverage | Sections and page types; which query groups each site serves | Their sitemap and navigation; results snapshots (Measured for the snapshot) |
| Depth and originality | Data, testing, tools, templates, expert input, examples | Reading the pages |
| Formats | Guides, comparisons, calculators, docs, video, glossaries | Reading the pages |
| Freshness | Visible dates, version references, changelogs | Reading the pages |
| Experience and trust signals | Named authors with real backgrounds, methods, disclosures, about and contact pages | Reading the pages (`content-quality-review.md`) |
| Technical quality | Indexability, speed, mobile layout | `crawl-and-index-controls.md`, `rendering-facets-pagination.md` and public Core Web Vitals field data |
| Links and mentions | Which of their pages attract links and why (data studies, tools, original research) | Vendor link indexes: partial and vendor-specific; label as estimates |
| Traffic | Relative size only | Vendor estimates: modeled, often far off for small sites; never present as measured |
| AI answers | Which sources an answer engine cites for your target questions | Dated, repeated prompts (`ai-answer-engines.md`) |

- Read their sitemap (`/sitemap.xml` or the one named in `robots.txt`) to inventory sections cheaply. If you crawl, honor `robots.txt`, keep the rate low, identify the crawler, and stay out of anything behind a login.
- Study why their strongest pages attract links and citations, then build something better of your own. Never buy, swap or solicit links for ranking (`links-authority-and-trust.md` covers legitimate link review).
- Do not copy their text, images or data. Learn the need they serve; serve it better with your own material.

## Finding the gaps

Put the query groups and topics in four buckets:

| Bucket | Meaning | Default move |
|---|---|---|
| They rank, you have nothing | A coverage gap | Candidate for a new page, if the need fits your audience and edge |
| Both have a page, they rank higher | A quality or relevance gap | Improve the existing page before writing another (`content-refresh-and-consolidation.md`) |
| You rank, they do not | Your advantage | Protect it: keep it current |
| Nobody serves it well | Possibly new territory | Confirm real demand first; it may be empty for a reason |

Then look for gaps that are not topics:

- **Format gaps:** the results reward a calculator, a template, a comparison table or a video, and you only have prose.
- **Stage gaps:** you cover learning queries but have nothing for people comparing options or ready to act, or the reverse. Map your pages to the stages your buyers go through and look for holes.
- **Evidence gaps:** you cover the topic but without testing, data or examples, while a competitor shows them.
- **Freshness gaps:** your page describes last year's product, prices or rules.

## Is the gap worth closing?

A competitor having a page is not a reason to make one. Each gap needs yes answers to:

1. **Demand:** real searchers want this (Search Console impressions, a volume range, or customer questions), stated with its label.
2. **Fit:** the visitor is someone the business serves.
3. **Edge:** the user can make the better page: first-hand experience, data, product knowledge or expertise the current results lack.
4. **Cost:** the effort, including keeping it current, is worth the value.

Rank the survivors in tiers (now, next, later) with one sentence each. If a number is wanted, agree the weights with the user and show the arithmetic; do not present a vendor-estimate composite as precise.

## Differentiation without disparagement

- State what the user can show that others cannot: their own test results, usage data, support experience, local presence, or a method they can explain. Claims about the user's own product need evidence (`../../legal-ready/references/honest-commerce.md`).
- Statements about named competitors must be accurate, sourced and dated. Comparison pages follow the honesty rules in `content-briefs-and-writing.md`.
- No fake reviews, no astroturfed forum posts, no anonymous attacks. None of these is a search strategy.

## Deliverable

```markdown
# Competitive and gap review: <site>, <market>, <date>
Data: results snapshot <date, source, location, device>; Search Console <property, range, filters>; vendor <tool, date> (estimates)

Search competitors by topic: <table: topic, domains holding top results, share of queries>
What they do better: <3-5 findings, each with the page and evidence>
Gaps worth closing: <table: gap, bucket, demand (labeled), fit, edge, effort, tier>
Gaps rejected and why: <list>
Advantages to protect: <list>
Open questions: <access, business priorities>
```

## Pitfalls

| Pitfall | Fix |
|---|---|
| Benchmarking against business rivals that do not appear in the results | Start from who actually holds the target queries |
| Treating vendor traffic or "authority" as measured | Label as vendor estimates; use for relative order only |
| A content calendar of every competitor topic | Keep only gaps with demand, fit and edge |
| Copying the top page's outline | Use shared coverage as the floor; win on the gaps |
| Studying links to copy them | Study why assets earn links; build better assets |

## Checks (done when)

- [ ] Competitors were chosen from dated results across the target query groups, per topic.
- [ ] Each finding names the competitor page and the evidence, with labels on every number.
- [ ] Every recommended gap passed the demand, fit, edge and cost questions.
- [ ] Nothing was fetched against `robots.txt` or terms, and no competitor content was copied.
- [ ] Recommendations name the action (new page, improve existing, protect) and land in the target map.
