# Programmatic pages and publishing on other sites

Read this when the user wants many pages generated from a template and a dataset (locations, products, integrations, comparisons, glossary terms, data entries), wants to audit an existing generated section, or proposes publishing on other people's sites to rank. Faceted navigation, crawl budget and URL parameters are in `rendering-facets-pagination.md`; `noindex`, canonicals and sitemaps in `crawl-and-index-controls.md`.

Generated pages are legitimate when each one carries data that is specific to it and useful to the person who lands on it. A timetable per station, a specification page per product, an exchange-rate page per currency pair and an entry per item in a public dataset all pass. Pages that differ only by a swapped name do not, however many there are.

## Where the line is

Google's spam policies (updated March 2024) name the patterns that fail:

- **Scaled content abuse:** many pages made mainly to rank rather than to help, with little original value, whether written by people, automation or both.
- **Doorway abuse:** pages targeting similar queries or places that funnel visitors elsewhere or are near-identical (one page per city with the city name swapped is the classic case).
- **Thin affiliate pages:** product pages that copy the merchant's descriptions and add nothing.
- **Scraped content:** pages built from other sites' content without adding value or permission.

Each of these is judged by purpose and value, not by the production method. Generating pages is fine; generating pages nobody needs is not.

## The unique-useful-data test

Run all four checks on a draft set before anything is indexed, and on existing generated sections during audits. A page that fails any check is not generated, is merged into a parent or list page, or is kept out of the index.

### 1. A distinct need

Someone looks for this specific item, and the answer for it differs from the answer for its siblings. Evidence: Search Console impressions for comparable existing pages, site search logs, a volume range, or a clear navigational need (a product someone owns, a station someone uses). "There is a row in the table" is not a need.

### 2. Its own data

The page shows facts about this item that the template does not supply: measurements, prices, specifications, schedules, availability, statistics, reviews, locations, steps. Count the distinguishing fields per row before building, and set a minimum with the user:

- Rows with too few filled distinguishing fields are excluded, not filled with generic sentences.
- The data source is licensed for this use and is current; licensed and public data still needs attribution and an "as of" date.
- Data you own (product, usage, first-hand measurements) gives pages that cannot be copied. Public data everyone has needs something added (comparison, calculation, curation, local knowledge) or the pages duplicate what already exists.

### 3. Not interchangeable

Measure how much of each page is shared template text and how close each page is to its nearest sibling. Run this on the built HTML:

```python
# Unique-text share and nearest neighbour per page, for a folder of built HTML (standard library only).
# The page's slot value (the rare words in its <title>, such as a city name) is masked first,
# so a name swap does not count as unique content.
import pathlib, re, sys
from collections import Counter
from html.parser import HTMLParser

SKIP = {"script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside"}

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []; self.title, self.body, self.main = [], [], []
    def handle_starttag(self, tag, attrs): self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag in self.stack: del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
    def handle_data(self, data):
        if "title" in self.stack: self.title.append(data)
        elif not SKIP & set(self.stack):
            (self.main if "main" in self.stack else self.body).append(data)

words = lambda text: re.findall(r"\w+", text.lower())
parsed = {}
for path in sorted(pathlib.Path(sys.argv[1]).rglob("*.html")):
    p = Page(); p.feed(path.read_text(errors="ignore"))
    parsed[path] = (set(words(" ".join(p.title))), words(" ".join(p.main or p.body)))
rare = max(1, len(parsed) // 20)                        # "rare" = on at most 5 % of pages
word_df = Counter(w for _, body in parsed.values() for w in set(body))
pages = {}
for path, (title, body) in parsed.items():
    body = ["_" if w in title and word_df[w] <= rare else w for w in body]   # mask the slot value
    pages[path] = {" ".join(body[i:i + 5]) for i in range(len(body) - 4)}
seen_on = Counter(s for sh in pages.values() for s in sh)
for path, sh in pages.items():
    own = sum(seen_on[s] <= rare for s in sh) / len(sh) if sh else 0.0
    near, sim = max(((q, len(sh & o) / len(sh | o)) for q, o in pages.items() if q != path and (sh or o)),
                    key=lambda t: t[1], default=("-", 0.0))
    print(f"{own:6.1%} own  {sim:4.2f} max-sim  {len(sh):5d} shingles  {path}  ~ {near}")
```

- `own` is the share of five-word sequences on the page that appear on few other pages; `max-sim` is the overlap (Jaccard) with the most similar sibling. On a test set of name-swapped pages it reports 0 % own and 1.00 similarity; pages with real per-row tables report most of their text as their own.
- The numbers are review triggers, not thresholds any search engine publishes. Calibrate on a small hand-labeled sample of good and bad pages from the same template, then review every page below the agreed `own` share or above the agreed similarity.
- Run it per template folder; the pairwise comparison grows with the square of the page count, so sample very large sets.
- Varying the wording to pass this check defeats its purpose. If pages need rotated phrasing to look different, they are not different; add data or merge them.

### 4. Useful to a person

Review a random sample (include the pages with the least data, not just the best) and answer for each:

- Would someone who arrived for this exact item get what they came for without going back to the results?
- Would the page be worth publishing if search sent no traffic, for example for visitors browsing the site?
- Is it at least as useful as the best existing page for the same item?

Record the answers with the page URLs. Any "no" on a sampled page means checking the whole segment it represents.

## Designing the template

- **Data first:** the item's own facts lead the page, with an "as of" date for anything volatile and the source credited.
- **Conditional sections:** a section appears only when its data exists. No filler sentences for empty fields ("Information about X is coming soon").
- **Honest text generation:** if language models phrase the copy, they work only from the row's fields, never add numbers, claims or quotes, and a person reviews a sample before every batch. Label generated text where readers would expect to know (`content-briefs-and-writing.md`).
- **Navigation:** link to the parent list, to genuinely related items (nearest in the data, not random), and back. Each page is reachable through normal browsing, not only through a sitemap.
- **Unique title and description built from the data,** a self-referencing canonical, and structured data only where the visible page supports it (for example `Product` with real offers).
- **Combinations:** do not create a page for every combination of filters (color by size by city). Choose the combinations with distinct demand and data, and keep the rest as filtered views that are not indexed.

## Indexing and rollout

- Index only pages that pass the test. Others are not generated, are merged into list pages, or carry `noindex` and stay out of sitemaps.
- Sitemaps list only indexable, canonical URLs; split them by section so Search Console reports per segment.
- Launch in batches, starting with the pages with the most data. Watch each batch in Search Console's Page indexing report: a large share of "Crawled, currently not indexed" or "Discovered, currently not indexed" for a template is a sign the engine sees little value or the site cannot be crawled efficiently. Watch impressions per page, not only the total.
- When an item disappears (product discontinued, place closed), return 404 or 410, or redirect to a true successor. Keep data fresh on a schedule the user owns.
- Before publishing, run `content-quality-review.md` on a sample covering every template variant.

## Publishing on other sites

Google's site reputation abuse policy (announced March 2024, enforced from May 2024, clarified in November 2024) targets third-party pages hosted on a site to exploit that site's ranking signals, such as coupon, payday-loan or casino sections on news sites, or paid "sponsored" sections unrelated to the host's purpose. The November 2024 clarification states that first-party involvement or oversight does not make such content acceptable. Practices that are out:

- Paying or arranging to host pages on a strong site so that they rank ("borrowing authority", "parasite" pages).
- Guest posts written mainly to get links, especially with keyword-rich anchors (listed as link spam).
- Mass-posting on platforms (forums, article sites, Q&A sites, social platforms) to place links or mentions.

Legitimate outside publishing exists and is judged by audience and purpose:

- Writing for a publication because its readers want the piece and its editors run it, with the author's affiliation disclosed. Paid placements are labeled as sponsored and their links carry `rel="sponsored"`.
- Syndicating an article to a partner with attribution and a link to the original. For the original to be the version that ranks, Google's current guidance is that the partner keeps its copy out of the index (`noindex`); a cross-domain canonical is only a hint. Check the current documentation and agree it with the partner.
- Taking part in communities (forums, open-source projects, Q&A sites) under their rules, answering the question asked, disclosing affiliation, and linking only where it helps.
- Hosting real project assets where they belong: code and documentation in a code-hosting repository, a talk on a conference site.

Ask of any outside placement: would it exist, in this form, on this site, if it passed no ranking benefit? If not, do not do it.

## Checks (done when)

- [ ] Each generated page has a distinct need and its own data, with the minimum distinguishing fields agreed with the user.
- [ ] The overlap check ran on the built pages, thresholds were calibrated on labeled examples, and every flagged page was reviewed.
- [ ] A random sample, including the thinnest pages, was reviewed by a person for usefulness, with URLs and answers recorded.
- [ ] Only passing pages are indexable and in sitemaps; rollout is batched and monitored per segment.
- [ ] No outside placement exists mainly to borrow another site's ranking signals or to place links.
