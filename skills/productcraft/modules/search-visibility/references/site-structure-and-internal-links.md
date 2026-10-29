# Site structure and internal linking

Read this when planning a site's hierarchy, navigation, categories or URL folders, or when fixing internal links: orphan pages, pages buried deep, weak category pages, or a new section nobody links to. External links pointing at the site are in `links-authority-and-trust.md`; faceted navigation and pagination in `rendering-facets-pagination.md`.

Internal links do three jobs: they let crawlers discover pages, they tell engines and users what a target is about (anchor text and surrounding text), and they signal which pages the site itself treats as important. Structure is for people first; a hierarchy that makes sense to users nearly always works for search.

## Measure the current structure

Do not guess from the menu. Build the link graph from a crawl that starts at the home page and follows only crawlable `<a href>` links, as a search engine would. Then join it with the URLs the site claims to have:

- sitemaps (what the site wants indexed);
- Search Console Performance pages and analytics landing pages (what gets traffic);
- server logs (what crawlers and users request).

From the joined data compute:

| Measure | Meaning | Worry when |
|---|---|---|
| Click depth | Fewest clicks from the home page | Important pages sit much deeper than comparable ones; deep pages are crawled less often |
| Inbound internal links (count of distinct linking pages) | How strongly the site points at a page | Key pages have few, while low-value pages (tags, archives) collect many |
| Orphans | Pages in sitemaps, analytics or logs that no crawled page links to | Any valuable orphan; engines may find it only through the sitemap or not at all |
| Near-orphans | Reachable only via deep pagination, JavaScript-only links or `nofollow` | Same as orphans in practice |
| Links to redirects, 404s or non-canonical URLs | Wasted crawls and diluted signals | Any, on templates |

There is no official maximum depth. "Three clicks" is a planning convention, not a rule; what matters is that important pages are not much deeper than their peers and that every indexable page is reachable through links.

A crawler export gives you the edges. This standard-library script computes depth, inbound links and orphans from an edge list (`source,target` per line, already normalized to canonical URLs) and a list of known URLs:

```python
import csv, sys
from collections import defaultdict, deque

edges_file, known_file, home = sys.argv[1], sys.argv[2], sys.argv[3]
out_links, in_from = defaultdict(set), defaultdict(set)
with open(edges_file, newline="") as f:
    for src, dst in csv.reader(f):
        if src != dst:
            out_links[src].add(dst)
            in_from[dst].add(src)

depth, queue = {home: 0}, deque([home])
while queue:                                   # breadth-first search gives the fewest clicks
    page = queue.popleft()
    for nxt in sorted(out_links[page]):
        if nxt not in depth:
            depth[nxt] = depth[page] + 1
            queue.append(nxt)

known = {line.strip() for line in open(known_file) if line.strip()}
writer = csv.writer(sys.stdout)
writer.writerow(["url", "depth", "inbound_pages", "status"])
for url in sorted(known | set(depth)):
    status = "orphan" if url not in depth else ""
    writer.writerow([url, depth.get(url, ""), len(in_from[url]), status])
```

Run it on the crawl of the site as served, not on the CMS's idea of the site. Treat the output as leads: confirm a few orphans by searching the templates and pages that should link to them.

## Hierarchy and taxonomies

- **Few, clear top-level sections** that match how users think about the offering. Category pages are real pages: a useful introduction, the items, filters, and links to subcategories. They are often the best target for broad queries.
- **One primary place per item.** A product or article can appear in several lists, but has one canonical URL and one primary category used for breadcrumbs.
- **Tags and archives** create many thin, overlapping list pages. Keep a small, curated tag set with real content, or keep tag pages out of the index and out of the sitemap. Date archives rarely deserve indexing.
- **Breadcrumbs** that mirror the hierarchy help users and give engines context; mark them up with `BreadcrumbList` (`structured-data-and-social-cards.md`).
- **URL folders** that mirror sections (`/guides/`, `/running/trail/`) make the structure visible and allow reporting by section in Search Console. Keep them shallow, and do not rename existing folders just to match a new taxonomy unless the gain is worth a migration (`site-migrations.md`).

## Hubs and related links

A hub page (an overview of a topic linking to detailed pages, which link back to it and to each other where relevant) helps when the hub is genuinely useful to a reader. It becomes a problem when it is a thin list of links built only to pass signals. Practical rules:

- Link where a reader would want to go next: from overview to detail, between siblings that answer follow-up questions, from articles to the products or tools they discuss and back.
- Put important links in the main content, not only in footers or sidebars. Contextual links with descriptive anchors carry the clearest meaning.
- Vary anchors naturally; describe the target. There is no evidence-based "anchor ratio" for internal links.
- Related-content modules, "popular" lists and recently added lists spread links to new and deep pages automatically; check they render as crawlable links in the server HTML.
- Large sites benefit from an HTML sitemap or A to Z index for users and discovery.

## Navigation

- Main navigation and footer links appear on every page, so they define what the site treats as most important. Keep them to the sections users need; a huge mega menu makes every page link to hundreds of others and hides what matters.
- Navigation must work without JavaScript events alone: plain links in the HTML, even if a script enhances them.
- Mobile and desktop navigation should expose the same important links. Google indexes the mobile version of pages.

## Orphan and low-value page decisions

| Situation | Usual decision | Who decides |
|---|---|---|
| Valuable page with no links | Link it from its category, a hub and related pages | Agent proposes, owner approves |
| Duplicate of another page | Redirect to the canonical, or canonical if it must remain | Owner |
| Outdated but has external links or traffic | Update it, or redirect to the closest current equivalent | Owner |
| Outdated, no links, no traffic, no equivalent | 404 or 410, removed from sitemaps and links | Owner |
| Needed for users but not for search (legal notices, account help) | Keep linked; `noindex` only if it competes with better pages | Owner |

Deleting, redirecting or `noindex`ing pages at scale is on the owner-approval list in `../GUIDE.md`. Present the list with each page's traffic (Search Console and analytics, with dates) and external links before anything changes.

## Internal link hygiene

- Link to final, canonical URLs: no redirects, no tracking parameters, consistent host, scheme and trailing slash.
- No `nofollow` on internal links.
- Broken internal links fixed at the source, not only by redirects.
- When a page is published, add links to it from the relevant hub and related pages in the same release.
- After a structure change, re-crawl and re-run the depth and orphan measures, and compare them with the earlier run.

## Done when

- [ ] A crawl-based link graph exists, joined with sitemaps, Search Console, analytics and logs; depth, inbound links and orphans were computed from it.
- [ ] Every indexable page is reachable through crawlable links; important pages are not much deeper than their peers.
- [ ] Categories, tags and archives have a stated purpose; thin ones are curated or kept out of the index and sitemaps.
- [ ] Internal links point at canonical 200 URLs with descriptive anchors; none are `nofollow`.
- [ ] Every removal, redirect or `noindex` decision was approved by the owner with traffic and link data shown.
