# Rendering, faceted navigation, pagination and crawl budget

Read this when public pages depend on JavaScript, when filters, sorts or parameters multiply URLs, when lists are paginated or infinitely scrolled, or when Search Console shows many URLs "Discovered, currently not indexed". The basic controls (`robots.txt`, `noindex`, canonical, status codes) are in `crawl-and-index-controls.md`. Choosing a rendering mode per route is in `../../stacks/references/web-frontend-foundations.md`; framework specifics such as the Next.js metadata API are in `../../stacks/references/nextjs.md`.

## How JavaScript pages get indexed

Google fetches the HTML, queues the page for rendering in an up-to-date Chromium, runs the JavaScript, then indexes the rendered result and follows the links it finds. Rendering usually happens soon after the fetch but can lag. Bing also renders, with its own limits. Many AI crawlers are reported to read only the initial HTML without executing JavaScript; vendors rarely document this, so assume it.

What follows from that:

- Content, links, `<title>`, meta description, canonical, `meta robots`, `hreflang` and JSON-LD that matter should be in the server-rendered HTML. Static generation or server rendering with hydration gives every crawler the same page users see. A client-rendered shell is acceptable for pages behind a login, where search does not matter.
- Dynamic rendering (serving bots a prerendered copy) is a workaround Google no longer recommends. Serving bots different content from users is cloaking.
- Every resource the page needs to render (scripts, CSS, API responses it fetches, fonts) must be crawlable and fast. A `robots.txt` rule on `/api/` can blank a page for Google.

## Check what crawlers receive

Compare the raw HTML with the rendered DOM. The gap is what non-rendering crawlers miss and what Google must render to see.

```bash
# Raw HTML as served (no JavaScript). Count links and look for the main heading and JSON-LD.
curl -sS -A "Mozilla/5.0 (compatible; site-audit)" https://www.example.com/guides/returns \
  | tee raw.html | grep -o '<a [^>]*href=' | wc -l
grep -c 'application/ld+json' raw.html
```

For the rendered side, use Search Console URL Inspection's live test (rendered HTML, screenshot, blocked resources and console messages as Google saw them) or a headless browser in your own tests (`../../builder-tools/references/playwright-web-testing.md`). For a static export, run `scripts/seo_check.py` on the build folder: it reads the HTML files as shipped, which is what a non-rendering crawler sees.

## Single-page application pitfalls

| Pitfall | Effect | Fix |
|---|---|---|
| Navigation through `<button>` or `onclick` without `href` | Crawlers find no links | Real `<a href="/path">` elements; intercept clicks for client routing |
| Routes in the fragment (`/#/products`) | Everything after `#` is ignored; the whole app is one URL | History API routes with server support for every path |
| Every unknown route returns 200 with a "not found" view | Soft 404s; junk URLs indexed | Server returns 404 for unknown paths, or the client sets `noindex` on the error view |
| Title, canonical or `robots` changed only after hydration | Engines may see the server values, or skip rendering after a server `noindex` | Emit final values in the server HTML |
| Content loaded only after a click, hover or scroll event | Not seen; Google does not click or scroll | Load content in the initial render or when it enters the viewport (`IntersectionObserver`, native `loading="lazy"`) |
| Consent wall or interstitial covering all content in the HTML | Main content missing or treated as intrusive | Keep content in the document; make banners overlays that do not replace it |
| Redirects or content swaps by IP or language | Googlebot, crawling mostly from US addresses, sees one version | Separate URLs per locale with links between them (`international-hreflang.md`) |
| A/B or personalization scripts that hide the original content | Crawlers may index the empty variant; serving bots a fixed variant can look like cloaking | Test on visible variants; keep the canonical content present; follow the engines' testing guidance (302s for redirect tests, canonical to the original) |

## Faceted navigation and parameters

Filters (color, size, price, brand), sorts and view options combine into far more URLs than there are products. Most combinations are near-duplicates that waste crawling and dilute signals. Google published dedicated guidance on this at the end of 2024; the decision has two branches.

**1. Decide which facet pages deserve to be indexed.** A filtered page earns its own indexable URL only when people search for that combination (for example "waterproof trail running shoes") and it shows a distinct, useful set of items. Give those pages a clean URL, a unique title and heading, a self-canonical, links from navigation and a place in the sitemap. Keep the list short and owned.

**2. Keep everything else from being crawled, not only from being indexed.**

| Method | Effect | Trade-off |
|---|---|---|
| `robots.txt` `Disallow` on the parameter patterns | Stops crawling of those URLs | They can still appear as bare URLs if linked externally; signals on them do not consolidate |
| Filters in the URL fragment (`#color=red`) or applied without changing the URL | Crawlers do not see separate URLs | Users cannot share or bookmark filtered views unless you add that back |
| `rel="canonical"` to the unfiltered page | Consolidates signals | URLs are still crawled, so it does not save crawling |
| `noindex` on filtered pages | Keeps them out of the index | Still crawled; links on pages that stay `noindex` are eventually not followed |
| `rel="nofollow"` on filter links | A hint that may reduce crawling | Not reliable on its own |

If filtered URLs must exist and be crawlable, keep them tidy: the standard `?key=value&key=value` form, one fixed parameter order, no duplicate parameters, and a 404 for combinations that return no items instead of an empty 200 page.

Tracking and session parameters: strip `utm_*`, click IDs and session IDs from internal links, canonicals and sitemaps; keep sessions in cookies; and point the canonical at the clean URL. Calendars, "next day" links and other infinite URL spaces need a limit or a `Disallow`.

## Pagination and infinite scroll

- Google has not used `rel="next"` and `rel="prev"` since 2019 (other engines may still read them; they do no harm). Link pages to each other with plain `<a href>` links, and link to the first page from every page.
- Each page in a series has its own URL (`?page=3` or `/page/3/`, not a fragment), its own self-referencing canonical, and stays indexable so the items listed only on it can be found.
- A "view all" page is an option when it loads quickly; then the series may canonicalize to it.
- Infinite scroll or "load more" needs a paginated URL sequence behind it, with each chunk reachable through a link and the URL updated as the user scrolls, so crawlers and users can reach item 500 without scrolling.
- Sort orders of the same list are duplicates: canonicalize them to the default order or keep them uncrawlable.

## Crawl budget

Crawl budget is how many URLs a search engine is willing and able to fetch from a site in a period. Google's guidance treats it as a concern mainly for very large sites (roughly a million or more pages changing weekly, or tens of thousands changing daily) and for sites with many URLs stuck in "Discovered, currently not indexed". For a few thousand pages, discovery and quality problems are far more likely than budget limits.

Diagnose before changing anything:

- **Search Console Crawl Stats** (Settings): requests per day, response codes, file types, purposes (discovery or refresh), average response time and host status (robots.txt fetch, DNS, connectivity) over the last 90 days.
- **Server logs**: which URL patterns verified search crawlers request, how often, and with which status. Logs are the only source showing crawls of URLs Search Console never reports (`search-measurement.md`).
- **Ratio checks**: crawled URLs that are parameters, redirects, 404s or non-canonical versus useful canonical pages.

Fixes in order of payoff: remove or block infinite URL spaces and duplicate parameter URLs; fix redirect chains and links to redirected or removed URLs; return real 404s instead of soft 404s; make responses fast and cacheable (stable `ETag` or `Last-Modified` with 304 responses); keep sitemaps clean so they list only canonical URLs. Google raises and lowers its crawl rate in response to server health. To slow it urgently, return 503 or 429 for a short time; Search Console's crawl-rate setting was removed in early 2024.

Do not use `noindex` to save crawl budget: a URL has to be crawled for its `noindex` to be seen.

## Done when

- [ ] Raw HTML of each public template contains the main content, crawlable links and final head tags; the rendered DOM adds nothing search depends on.
- [ ] Rendering resources are crawlable; URL Inspection's live test shows a complete render for sample pages.
- [ ] Unknown routes return 404; no route returns a soft 404.
- [ ] A written list says which facet combinations are indexable; the rest are kept from crawling, and the choice was approved by the owner.
- [ ] Paginated series use linked URLs with self-canonicals; infinite scroll has a paginated fallback.
- [ ] Any crawl-budget claim cites Crawl Stats or log figures with their date range.
