# Search planning and topic architecture

Read this when the user wants a search plan or roadmap, is building a new site or a major new section, is choosing a site architecture, or wants to organize content into topic clusters (a hub or pillar page with supporting pages). Finding and grouping queries is `keyword-and-topic-research.md`; hierarchy, navigation and internal-link measurement are `site-structure-and-internal-links.md`; keeping the plan and its records across sessions is `search-project-state.md`.

A search plan is a short list of decisions in dependency order, each with an owner, a reason and a check. It is not a list of tactics, and it promises no rankings or traffic: search outcomes arrive weeks to months after the work and depend on competitors and engines as much as on the site.

## 1. Discovery

Collect and confirm with the user before planning; record answers in the project state:

- **Business model and goal:** what the site sells or provides, to whom, and which outcome search should support (sales, leads, sign-ups, support deflection, readership).
- **Markets:** countries, languages, local presence.
- **What the business can credibly say:** products, data, first-hand experience, experts who can write or review. Topics without that standing are poor targets.
- **Current state:** the platform and its constraints, access to Search Console, analytics and logs, and a baseline if the site exists (clicks, impressions and indexed pages per section, Core Web Vitals per template, notable links), each with source and dates (`search-measurement.md`).
- **Capacity:** writers, subject experts, developers and reviewers, and how many hours each can give. Capacity, not ambition, sets the pace.
- **Constraints and risks:** regulated topics (health, finance, legal), claims that need substantiation, planned migrations or rebrands, seasonality.

## 2. Architecture by business model

Shape sections around how customers think and decide. Common starting points, to adapt rather than copy:

| Model | Commercial core | Learning and comparison pages | Typical traps |
|---|---|---|---|
| Software or SaaS | Product, features, integrations, use cases or industries, pricing | Guides, templates, glossary, honest comparisons, documentation | Thin feature and integration pages generated per partner; comparison pages without sources |
| Online shop | Categories, subcategories, products, brands | Buying, sizing and care guides | Facet explosion, thin categories, manufacturer copy (`ecommerce-search.md`) |
| Local services | Services, locations or service areas, booking | Answers to customer questions, project examples | Swapped-name city pages (`local-search-and-map-listings.md`) |
| Publisher | Topic hubs, articles, authors | Explainers, evergreen guides | Tag and archive bloat, refreshed dates without changes |
| Marketplace or directory | Listing pages, category and location listings | Guides for buyers and sellers | Empty or near-empty listing combinations (`programmatic-pages.md`) |
| Documentation or developer platform | Reference, guides, tutorials, changelog | Concepts, migration guides | Versions competing with each other; docs rendered only on the client |
| Professional services | Services, industries, case studies, team | Insights, methods | Practice-area pages without substance; team pages without real bios |

For every architecture:

- Few top-level sections, shallow folders that mirror them, one primary place per item (`site-structure-and-internal-links.md`).
- Each page type gets a template with its own title, heading, canonical and structured data rules, so the rules live in code (`../GUIDE.md`, "Implement in code").
- Decide early which URL patterns are indexable and which are not (facets, search, tags), and write it down.
- On an existing site, a new architecture that changes URLs is a migration; weigh it against `site-migrations.md` before choosing it.

## 3. Topic clusters

A topic cluster is a hub page that answers the broad question of a topic, plus supporting pages for its distinct sub-needs, linked so readers and crawlers can move between them. It works when every page in it serves a real need; it fails when pages exist only to fill out the cluster.

- **Start from the target map.** Group queries by results overlap (`keyword-and-topic-research.md`). Each group is one page; the broadest group the business can serve well becomes the hub.
- **Size by real sub-needs,** not by a fixed number of supporting pages or words. A small topic may need a hub and two pages; another may need fifteen.
- **One need, one URL.** If two planned pages target overlapping results, merge them before writing.
- **Links follow the reader:** the hub links to every supporting page in the place a reader would want it; each supporting page links back to the hub and to siblings that answer the next question; product or service pages link where the topic leads to a decision. Use descriptive anchors (no keyword quotas).
- **Publish in order:** the hub and the strongest supporting pages first, with their links in the same release; add the rest as capacity allows, linking each from the hub on publication.
- **Maintain:** when a supporting page is merged, retired or added, update the hub and the target map in the same change.

Keep the plan as data, and check it against what the site actually links after each release:

```python
# Plan CSV: cluster,role,url   (role is "hub" or "page")
# Edges CSV from a crawl of the built or live site: source,target  (final canonical URLs)
import csv, sys
from collections import defaultdict

plan = defaultdict(lambda: {"hub": None, "pages": []})
for row in csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")):
    entry = plan[row["cluster"]]
    if row["role"] == "hub":
        entry["hub"] = row["url"]
    else:
        entry["pages"].append(row["url"])
edges = {(r["source"], r["target"]) for r in csv.DictReader(open(sys.argv[2], newline="", encoding="utf-8"))}
linked_to = {target for _, target in edges}
for name, c in sorted(plan.items()):
    for page in c["pages"]:
        if c["hub"] and (c["hub"], page) not in edges:
            print(f"{name}: hub does not link to {page}")
        if c["hub"] and (page, c["hub"]) not in edges:
            print(f"{name}: {page} does not link back to the hub")
        if page not in linked_to:
            print(f"{name}: {page} has no internal links at all")
```

The output is a worklist. Some missing links are deliberate; record why, so the next check does not reopen them.

## 4. Roadmap by dependency

Order work so each phase unblocks the next; give each phase exit criteria instead of promised dates for results.

| Phase | Work | Exit criteria |
|---|---|---|
| Foundation | Access (read-only), measurement and baseline, entity fact sheet, crawl and index blockers, templates for each page type, `seo_check.py` and drift checks in CI | Indexing blockers fixed; baseline stored; checks run on every build |
| Core pages | Commercial pages and hubs for the top topics, with their links | Pages live, indexed (Pages report), internal links verified by crawl |
| Supporting depth | Supporting pages by tier, comparison and guide pages, structured data where it matches content | Each page passed `content-quality-review.md`; target map current |
| Earned attention | Original data, tools, expert commentary, partnerships, link reclamation (`links-authority-and-trust.md`) | Assets published; outreach honest and approved |
| Maintenance | Scheduled refresh, consolidation, drift and invariant alerts, quarterly re-plan | Refresh calendar running; alerts with owners |

- **Schedule from capacity:** estimate hours per page type including research, expert review, design and development, then fill the calendar. Reserve an agreed share of capacity for refreshing existing pages; older pages that still bring visitors need upkeep as much as new pages need writing.
- **Tie each item to a goal and a check.** An item without either is a candidate for removal.
- **Name the dependencies:** developer time for templates, legal review for regulated claims, expert availability, a migration that freezes URL changes.

## 5. Measures and targets

| Goal | Leading indicators (weeks) | Outcomes (months) | Source |
|---|---|---|---|
| Pages can be found | Indexed share per sitemap; crawl errors; drift findings | Impressions per section | Search Console, CI |
| Topics gain visibility | Impressions and average position per query group; rich result validity | Non-brand clicks per section | Search Console |
| Search supports the business | Organic landing-page engagement; key events | Organic conversions, revenue or leads per template | Analytics |
| Answers cite the site | Crawler access verified; answer panel samples | Citation rates in repeated samples; AI referral visits | Logs, answer panel, analytics (`ai-answer-engines.md`) |

- Express targets as ranges with stated assumptions (capacity, publishing pace, seasonality), and revisit them quarterly. Never promise positions or traffic.
- Leave out vanity measures: totals of tracked keywords, vendor authority scores as goals, word counts.
- Report against the baseline and a control where possible (`rank-tracking-and-alerts.md`).

## 6. Keep the plan alive

- Record the plan, the target map, decisions and the change log in the project state (`search-project-state.md`); only user-approved decisions count as decisions.
- Review monthly against the exit criteria; re-plan quarterly with fresh data, and after any major engine update or business change.
- Drop items that stopped making sense, and say why.

## Deliverable

```markdown
# Search plan: <site>, <market>, <date>
Goal and audience: ...            Data: <sources, properties, date ranges>
Baseline: <table per section, with sources>          Capacity: <people and hours>
Architecture: <sections, URL patterns, indexable vs not, templates>
Topics and clusters: <hub and pages per topic, tiers, links>   (target map updated)
Roadmap: <phases, items, owners, exit criteria>
Measures and targets: <table with ranges and assumptions>
Risks and dependencies: <list with owners>
Decisions needed from the owner: <list>
```

## Done when

- [ ] Discovery answers are recorded and confirmed, including capacity and risks.
- [ ] The architecture fits the business model, states which URL patterns are indexable, and accounts for migration cost on an existing site.
- [ ] Every cluster page maps to one query group in the target map; the planned links are checked against a crawl after each release.
- [ ] The roadmap is ordered by dependency with exit criteria, scheduled from capacity, with refresh time reserved.
- [ ] Measures name their sources; targets are ranges with assumptions; nothing promises rankings or traffic.
