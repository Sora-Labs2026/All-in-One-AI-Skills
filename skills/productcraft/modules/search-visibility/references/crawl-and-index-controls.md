# Crawl and index controls

Read this when the work touches `robots.txt`, `meta robots` or `X-Robots-Tag`, XML sitemaps, canonical URLs, HTTP status codes and redirects, requests to (re)crawl, or the controls that decide which crawlers, including AI crawlers, may fetch a site. JavaScript rendering, faceted navigation, pagination and crawl budget are in `rendering-facets-pagination.md`; moving a site is in `site-migrations.md`.

Most of the changes in this file can remove a whole site or section from search. Read the owner-approval list in `../GUIDE.md` before editing any of them in production.

## Pick the right control

Each control answers a different question. Using the wrong one is the most common cause of pages that will not leave the index, or that leave it by accident.

| Goal | Use | Do not use |
|---|---|---|
| Keep a page out of search results | `noindex` in a `meta robots` tag or `X-Robots-Tag` header on a URL crawlers can fetch; or 404/410; or authentication | `robots.txt` (a blocked URL can still be indexed from links, without its content) |
| Stop crawlers spending requests on a URL space (filters, internal search, calendars) | `robots.txt` `Disallow` | `noindex` alone (the URLs still have to be crawled to see it) |
| Merge duplicates into one URL | 301 or 308 redirect where the duplicate has no reason to exist; `rel="canonical"` where it must stay reachable | `noindex` on the duplicate, `robots.txt` blocks |
| Keep content private | Authentication or IP restriction | `robots.txt` (it is public and advisory) or `noindex` |
| Hide something from results quickly | Search Console Removals (temporary, about six months) plus the permanent fix | Removals alone |
| Limit snippets, including use in Google's AI features | `nosnippet`, `max-snippet`, `data-nosnippet` | `Google-Extended` (it does not govern Search) |
| Opt out of a vendor's model training | That vendor's documented `robots.txt` token | Blocking search crawlers, which also removes you from search |

## robots.txt

The format is standardized in RFC 9309 (2022). Search engines add a few documented extensions.

- **Scope.** One file per protocol, host and port, at `/robots.txt`. `https://shop.example.com` and `http://example.com` each need their own. The path is case-sensitive.
- **Groups.** A group is one or more `User-agent` lines followed by `Allow` and `Disallow` rules. A crawler obeys the group whose user-agent matches its product token (case-insensitive) and ignores the others; groups naming the same token are merged. Only if no group matches does it fall back to `User-agent: *`. A crawler that has its own group therefore ignores everything under `*`, including rules you meant for everyone.
- **Matching.** Paths match from the start. `*` matches any run of characters and `$` anchors the end. The longest matching rule wins; when an `Allow` and a `Disallow` match with equal length, the `Allow` wins. An empty `Disallow:` allows everything.
- **Fetch results.** A 2xx response is parsed. Redirects are followed for a few hops. A 4xx (other than 429) means "no restrictions". A 5xx, 429 or network failure is treated as "disallow everything" for a while: Google stops crawling the site, then after about 30 days uses its last cached copy, or crawls without restrictions if it has none. A broken `robots.txt` can therefore stop crawling of a healthy site.
- **Size and caching.** Google reads the first 500 KiB and caches the file for up to about a day, so changes are not instant.
- **`Sitemap:` lines** take absolute URLs and may point to another host the owner controls.
- **Unsupported by Google:** `Crawl-delay` (Bing honors it), `Noindex:` lines (ignored since September 2019), and any attempt to control indexing.
- **Do not block resources needed to render pages:** CSS, JavaScript, fonts, images in templates and API endpoints the page fetches. Google renders pages, and a blocked script can hide content and links.
- **It is not access control.** Anyone can read it. Listing secret paths in it advertises them.

A small, readable file beats a clever one:

```text
# Crawl policy for www.example.com. Owner: web team. Changed 2026-10-12 (ticket WEB-412).
User-agent: *
Disallow: /cart
Disallow: /account/
Disallow: /search          # internal search results: infinite URL space
Disallow: /*?*sort=        # sort orders duplicate category pages
Allow: /search/help$       # one help page under the blocked prefix

Sitemap: https://www.example.com/sitemap-index.xml
```

Test before shipping: Search Console's robots.txt report shows the fetched version and fetch errors for each host (it replaced the old robots.txt tester in late 2023); Bing Webmaster Tools has its own tester; `scripts/seo_check.py --robots` checks syntax and evaluates your page, sitemap and asset URLs against the rules offline. Keep the file in version control so every change has a diff and a reason.

| Mistake | Effect | Fix |
|---|---|---|
| `Disallow: /` copied from staging to production | Crawling of the whole site stops; pages drop over the following weeks | Ship robots.txt from configuration per environment; add a CI check that fails a production build containing it |
| A crawler-specific group added without repeating the `*` rules | That crawler ignores all `*` rules | Repeat the shared rules in each named group |
| Blocking a URL to remove it from the index | It stays indexed ("Indexed, though blocked by robots.txt") and the `noindex` on it is never seen | Allow crawling, add `noindex`, remove the block after it drops out |
| Missing trailing slash (`Disallow: /admin`) | Also blocks `/administration`, `/admin-guide` | `/admin/`, or `/admin$` plus `/admin/` |
| Robots.txt returns 5xx or times out under load | Crawling pauses site-wide | Serve it as a static file from the edge; monitor its status |

## meta robots and X-Robots-Tag

- In HTML: `<meta name="robots" content="noindex, nofollow">` in the `<head>`. Target one crawler by name (`<meta name="googlebot" content="noindex">`). When rules conflict, the most restrictive one applies.
- For non-HTML files (PDFs, images, feeds) or whole paths, send the header: `X-Robots-Tag: noindex`. For example in nginx: `location ~* \.pdf$ { add_header X-Robots-Tag "noindex" always; }`.
- Common rules: `noindex`; `nofollow` (do not follow links on this page); `none` (both); `nosnippet`; `max-snippet:<n>`; `max-image-preview:none|standard|large`; `max-video-preview:<n>`; `noimageindex`; `notranslate`; `unavailable_after:<date>`; `indexifembedded`. Google no longer uses `noarchive`, since it removed cached-page links in 2024. Mark parts of a page as snippet-free with the `data-nosnippet` attribute on `span`, `div` or `section`.
- Google states that its snippet controls also apply to AI Overviews and AI Mode. Check the current documentation before promising an effect; Bing documents its own controls for its answer features.
- **The URL must be crawlable** for these rules to be read. `noindex` behind a `robots.txt` block does nothing.
- **Put it in the server HTML.** If the initial HTML says `noindex`, Google may not render the page at all, so JavaScript that removes the tag later does not reliably help. Adding `noindex` with JavaScript works, but server output is easier to verify.
- Never ship a site-wide `noindex` from a staging flag. Read it from environment configuration and test the production build.

## XML sitemaps

The protocol is documented at sitemaps.org; search engines add image, video, news and `hreflang` extensions.

- At most 50,000 URLs and 50 MB uncompressed per file. Use a sitemap index (itself limited to 50,000 entries) for more. Gzip is allowed.
- UTF-8, entity-escaped, absolute URLs on the host where the sitemap lives (cross-host only when both hosts are verified for the same owner or declared in that host's `robots.txt`).
- List only canonical URLs that return 200 and are indexable. Every redirect, `noindex`, 404 or non-canonical URL in a sitemap is a mixed signal and hides real problems in the indexing reports.
- `<lastmod>`: W3C datetime (`2026-10-12` or `2026-10-12T09:30:00+00:00`). Google uses it only when it is consistently accurate, so update it when the main content changes, not on every deploy. Google ignores `<priority>` and `<changefreq>`.
- Submit sitemaps in Search Console and Bing Webmaster Tools, and list them in `robots.txt`. Google retired its anonymous sitemap "ping" endpoint in 2023.
- Split sitemaps by template or section (`sitemap-products.xml`, `sitemap-articles.xml`). Search Console reports indexing per submitted sitemap, which turns "how many product pages are indexed" into a number you can track.
- A news sitemap lists only articles published in the last two days, up to 1,000 entries.
- A sitemap helps discovery. It does not make a page indexed or rank.

## Canonical URLs

Canonicalization picks one URL to index from a set of duplicates or near-duplicates. Search engines treat your declaration as a strong hint, not an order, and weigh it with redirects (strongest), internal links, sitemap membership, `hreflang` and HTTPS.

- Declare it in the `<head>` with an absolute URL: `<link rel="canonical" href="https://www.example.com/shoes/trail-runner">`. For PDFs and other files use the HTTP header `Link: <https://www.example.com/guide.pdf>; rel="canonical"`.
- Give canonical pages a self-referencing canonical. Point duplicates at the preferred version.
- Make every signal agree: internal links, sitemaps, `hreflang` and redirects all use the same canonical form (scheme, host, trailing slash, case, no tracking parameters).
- Never point a canonical at a URL that redirects, returns 4xx or 5xx, is `noindex`, is blocked in `robots.txt`, or is a different page. Never emit two canonical tags; Google ignores both when they disagree. A canonical in the `<body>` is ignored.
- Do not canonicalize page 2 and later of a paginated list to page 1; each page lists different items.
- Syndicated copies on other sites: Google's guidance (2023) is that the partner should `noindex` the copy, because a cross-domain canonical between different-looking pages is often not honored.
- Usual duplicate sources: `http` and `https`, `www` and bare host, trailing slash, letter case, `index.html`, tracking and session parameters, sort orders, printer views, separate mobile hosts, staging hosts that leaked into the index.

Check what the engine decided, not only what you declared: Search Console URL Inspection shows the user-declared and the Google-selected canonical. When they differ, find which signal disagrees before changing anything.

## Status codes and redirects

| Response | What search engines do | Use it for |
|---|---|---|
| 200 | Index if nothing else forbids it | Real content |
| 301, 308 | Treat as permanent; signals move to the target, which becomes canonical | Moved or merged URLs |
| 302, 307 | Treat as temporary; the source usually stays indexed (a long-lived one may eventually be treated as permanent) | Short-term moves, A/B routing |
| 304 | Content unchanged since the last crawl | Conditional requests; saves crawl effort |
| 404, 410 | Drop the URL after recrawls; 410 is a slightly firmer signal | Content gone with no equivalent |
| 429, 500, 503 | Slow down crawling; persistent errors drop URLs | Overload and planned maintenance (503 with `Retry-After`, for hours, not weeks) |
| 200 with "not found" or empty content | Reported as a soft 404 and not indexed | Never: return a real 404 or 410 |

- One hop from old to final URL. Chains waste crawls and lose signals; loops fail. Googlebot gives up after about ten hops.
- Redirect to the closest equivalent page. Redirecting many removed pages to the home page is treated as soft 404s.
- Server-side redirects first. Meta refresh and JavaScript redirects are followed by Google but are slower and less reliable for other crawlers.
- Keep redirects from a move for at least a year, and in practice for as long as the old URLs still get links or traffic.
- After adding redirects, update internal links, canonicals, `hreflang` and sitemaps to the final URL so the redirect is only a safety net.
- Products out of stock: keep the page live with accurate availability (in the page and in `Offer.availability`) while the item may return. When it is discontinued, redirect to a true replacement if there is one; otherwise return 404 or 410 and link to the category.

## Asking for crawling and indexing

- **Google:** URL Inspection's "Request indexing" (small daily quota, no guarantee), sitemaps with accurate `lastmod`, and internal links from pages Google already crawls often. Google's Indexing API is limited by policy to job postings and livestream video pages; using it for other pages breaks its terms.
- **IndexNow** (Bing, Yandex, Seznam, Naver and others; not Google as of 2026) notifies participating engines of changed URLs. It needs a key file hosted on the site. Submitting is a write to a third party: prepare the URL list, show it, and submit only with the owner's go-ahead. A generated request that was never sent is not a submission; report only responses you received.
- **Removals** in Search Console hide a URL for about six months. The permanent fix (`noindex`, 404 or 410, or authentication) must be live before that runs out.

## AI crawlers and answer engines: access

The evidence on how AI answer engines choose sources is young. What is known is that they can only use pages their crawlers or fetchers can reach, and that each vendor documents its own user agents and controls. Names and behaviors change; read each vendor's current crawler documentation before writing rules, and record the date you checked.

| Kind | Examples at the time of writing (check current names) | Controlled by |
|---|---|---|
| Search and answer indexing | `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, `Bingbot` (feeds Bing and Copilot), `Googlebot` (feeds Search, including AI Overviews and AI Mode) | `robots.txt` groups for that token |
| Model training | `GPTBot`, `ClaudeBot`, `CCBot`; tokens without a separate crawler such as `Google-Extended` and `Applebot-Extended` | `robots.txt` groups for that token |
| Fetches a user asked for | `ChatGPT-User`, `Claude-User`, `Perplexity-User` | Vendor policy; some vendors state these do not follow `robots.txt` because a person requested the page |

- `Google-Extended` controls use of content for Google's models outside Search. It does not change crawling, indexing or appearance in Search, and it does not opt a site out of AI Overviews; only the Search controls above affect those.
- CDNs and web application firewalls can block or challenge crawlers before `robots.txt` matters, and some now block AI crawlers by default. Check the CDN's bot settings and the server logs, not only the file.
- User-agent strings are easy to fake. Verify important crawlers by reverse DNS or by the IP ranges the vendor publishes (`search-measurement.md`).
- What helps pages get used once crawlers can reach them is in `ai-answer-engines.md`.
- `robots.txt` signals intent; it is not a license or a contract. Rights reservations for text and data mining, and licensing terms, are legal matters for the owner and counsel (`../../legal-ready/GUIDE.md`).
- Which bots to allow is a business, licensing and legal decision. Present the options (allow search and answers, allow search but not training, block all) with their consequences, and let the owner choose.
- `llms.txt` is a 2024 proposal for a curated, Markdown index of a site for language models. No major engine has confirmed it affects crawling, ranking or citation. It is cheap to add, but treat it as optional, never as a control, and put nothing in it that is not on the site.

## Indexing report reasons and first checks

Search Console's Pages report groups URLs by reason. Sample the listed URLs (up to 1,000 per reason) and inspect several before acting.

| Reason | Usually means | First check |
|---|---|---|
| Discovered, currently not indexed | Known but not crawled yet: crawl capacity, low perceived value or too many similar URLs | Internal links to it; server speed; URL-space size (`rendering-facets-pagination.md`) |
| Crawled, currently not indexed | Fetched but not judged worth indexing yet | Thin or duplicate content, soft 404 patterns, rendering gaps |
| Duplicate, Google chose different canonical than user | Your signals disagree or the pages are not equivalent | Compare the two URLs; align links, sitemap and canonical |
| Alternate page with proper canonical tag | Working as intended | Nothing, unless the page should rank |
| Excluded by "noindex" tag | A `noindex` was served | Whether it was intended; templates and headers |
| Blocked by robots.txt / Indexed, though blocked by robots.txt | A `Disallow` matches | Which rule; whether the URL should be indexed or removed |
| Soft 404 | Thin, empty or "not found" page returning 200 | Return a real status or add real content |
| Page with redirect, Not found (404) | Expected after moves and removals | Internal links and sitemaps still pointing there |
| Server error (5xx), Redirect error | Availability or redirect problems | Logs at the crawl times; redirect chains and loops |

## Done when

- [ ] The chosen control matches the goal in the first table, and no URL is both blocked in `robots.txt` and expected to be read for `noindex` or canonical.
- [ ] `robots.txt` returns 200, parses, keeps rendering resources crawlable, and its diff was approved by the owner.
- [ ] Sitemaps list only canonical, indexable 200 URLs, with honest `lastmod`.
- [ ] Canonicals are absolute, single, in the `<head>`, and point at indexable 200 URLs; internal links agree.
- [ ] Redirects are single-hop to equivalent pages, and nothing indexable returns a soft 404.
- [ ] AI-crawler rules match a policy the owner chose, checked against current vendor documentation and the logs.
- [ ] `scripts/seo_check.py` ran on the build output, and URL Inspection or the Pages report confirms the result for sample URLs after recrawl.
