# On-page elements

Read this when writing or reviewing the parts of a page that search engines read as signals or show in results: the `<title>`, meta description, headings, images and `alt` text, links and their attributes, and URL slugs. Writing and restructuring the content itself is in `content-briefs-and-writing.md`. Framework metadata APIs are in `../../stacks/references/nextjs.md` and the other stack references.

On-page work rarely fixes a page that is not crawled or indexed. Check indexing first (`crawl-and-index-controls.md`).

## What each element actually does

| Element | Role in search | Common myth |
|---|---|---|
| `<title>` | The main source of the title link in results and a relevance signal | "Must be 50-60 characters with the keyword first." There is no fixed limit; long titles are truncated by display width |
| Meta description | A candidate for the snippet; not a ranking signal | "Raises rankings." It can only influence clicks |
| Headings (`h1` to `h6`) | Structure that helps users, assistive technology and engines understand sections | "Exactly one `h1` or you are penalized." Google has said several `h1` elements are not a problem; one `h1` is a clarity and accessibility convention |
| `alt` text | Describes images for screen readers and image search | "Put keywords in every `alt`." Stuffing harms accessibility and helps nothing |
| Anchor text | Tells engines and users what the target is about | "Exact-match anchors everywhere." Write what the link leads to |
| URL slug | A small signal; shown as part of the result's breadcrumb | "Change URLs to include keywords." Changing URLs costs redirects and time |
| `meta keywords` | Ignored by Google | Still recommended in old checklists |

## Titles

- Unique per page, describing that page specifically. Lead with what distinguishes it (product name, article topic), then the site or brand name if useful, separated simply (`Trail Runner 3 waterproof shoes | Example Outdoor`).
- Build titles from page data in the template (product name, category, location), so thousands of pages get distinct, accurate titles. Avoid boilerplate repeated on every page and lists of keywords.
- Google rewrites title links when the `<title>` is missing, empty, stuffed, duplicated across many pages, or does not match the page. Frequent rewrites are a sign the titles do not describe the pages. Look at a sample of real results to see what is shown, remembering that results vary by location and device.
- Google takes the site name shown in results from the home page, using `WebSite` structured data with `name` as the preferred source alongside `og:site_name`, the title and headings. Keep them consistent.
- Keep titles stable once a page performs. Test changes on a group of similar pages with a before and after window and a control group (`search-measurement.md`), not one page over a few days.

## Meta descriptions

- One unique summary per page of what a searcher will find there, written for people. Engines often build the snippet from page text that matches the query instead, so a good description helps mainly on pages where the text does not summarize itself (home, category and product pages).
- Generate them from page data for large templates rather than leaving them blank or duplicated.
- No fixed length; snippets are truncated by width and may be longer or shorter than the description. Put the essential information first.
- Control what may be shown with `nosnippet`, `max-snippet` and `data-nosnippet` (`crawl-and-index-controls.md`), not by writing a vague description.

## Headings

- One clear main heading that says what the page is, then section headings in a logical order. Do not skip levels for visual size; style with CSS.
- Headings should match the content below them. Hidden or styled-away headings stuffed with phrases are hidden text.
- In component libraries, check that "Title" components render the right heading level, and that cards and widgets do not emit `h1` or `h2` elements everywhere.

## Images

- Use `<img>` or `<picture>` elements for meaningful images. Google does not index images set only as CSS backgrounds.
- `alt` describes what the image shows or does in context ("Side view of the Trail Runner 3 in blue"). Decorative images take `alt=""` so screen readers skip them. Missing `alt` attributes are an accessibility failure (`../../legal-ready/references/accessibility.md`).
- Descriptive file names (`trail-runner-3-blue-side.jpg`) and surrounding text help image search; the page text near an image is the main context.
- Performance: set `width` and `height` (or `aspect-ratio`), serve responsive sizes with `srcset` and `sizes`, use modern formats, and never lazy-load the image that is the Largest Contentful Paint element (`../../engineering-practices/references/performance.md`).
- Image sitemaps or `<image:image>` entries help when images load from a CDN or another host. Image licensing metadata (IPTC fields or `ImageObject` license properties) can show a license badge in image results.
- Product and recipe images also feed structured data; use the same URLs (`structured-data-and-social-cards.md`).

## Links

- Crawlable links are `<a>` elements with an `href` URL. Links made with `onclick`, `<span>` or buttons are not followed.
- Anchor text says where the link goes. Avoid "click here" and "read more" as the only text; for repeated "read more" links, add the target's name (visible or visually hidden).
- `rel` values: `nofollow` (do not endorse), `sponsored` (paid, affiliate or sponsored links), `ugc` (user-generated content). Google treats all three as hints since 2020. Paid and affiliate links must be marked `sponsored` or `nofollow`; leaving them unmarked breaks the link-spam policy.
- Do not `nofollow` your own internal links to steer ranking signals; it does not work that way and can hide pages from discovery.
- Fix broken links, and point links at the final canonical URL instead of through redirects or with tracking parameters.
- `target="_blank"` is a user-experience choice; modern browsers imply `noopener`, which is a security matter, not a search one.

## URLs

- Readable words separated by hyphens, consistent lowercase, consistent trailing-slash policy, no session IDs, and no content that exists only after a `#` fragment.
- Shallow, meaningful folders help people and make reporting by section easy (Search Console filters by URL prefix). Structure is covered in `site-structure-and-internal-links.md`.
- Once a URL ranks, do not change it for small cosmetic gains. If it must change, use a one-hop 301 and update internal links (`site-migrations.md` for many URLs).

## Practices to drop

These appear in many checklists but have no support in search engine documentation, or contradict it:

- Keyword density targets and "LSI keywords". Write naturally about the topic; repetition beyond natural use is keyword stuffing, which is a spam policy violation.
- Minimum word counts. Length should follow what the query needs; padding does not help.
- Adding the current year to titles of pages that were not updated, or changing dates without changing content. It misleads users and engines.
- Per-page link limits ("no more than 100 links"). Keep navigation usable instead.
- Title and description "click-through formulas" with promised percentage uplifts. Click rates vary by query, position and result features; test on your own data.

## Checking

- `scripts/seo_check.py` on the built HTML: missing or duplicate titles and descriptions, missing or multiple `h1`, images without `alt`, `meta keywords`, canonical and robots problems.
- A crawler for the live site, with the same checks across all pages and duplicate detection.
- Search Console Performance per page and query, with dates, to judge whether a change affected impressions and clicks.

## Done when

- [ ] Every indexable page has a unique, descriptive `<title>` and meta description generated from page data, without stuffing.
- [ ] Headings follow the content in order; one main heading names the page.
- [ ] Meaningful images use `<img>` with `alt` text that describes them; decorative images have `alt=""`; dimensions are set and the LCP image is not lazy-loaded.
- [ ] Links are crawlable `<a href>` elements with descriptive text; paid and affiliate links carry `sponsored` or `nofollow`.
- [ ] `seo_check.py` shows no errors on the build, and any change in clicks or impressions is reported with its Search Console date ranges.
