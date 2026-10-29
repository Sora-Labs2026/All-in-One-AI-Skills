# Structured data and social cards

Read this when adding, fixing or reviewing JSON-LD structured data (by feature type, validation, eligibility, retired features), or Open Graph and X (Twitter) card tags for link previews. Organization and Person markup for entity clarity (`sameAs`, knowledge panels) is in `entity-clarity.md`; this file covers the mechanics they share.

## What structured data does and does not do

- It describes the page's main content in a vocabulary machines read (schema.org). Google uses it to understand pages and to make them eligible for specific result features (product prices and ratings, recipe cards, event listings, breadcrumbs, and others).
- **Eligible is not guaranteed.** Valid markup qualifies a page; the engine decides whether to show a feature for a query.
- Google states structured data is not a general ranking boost. There is no published evidence that adding markup makes AI answer engines cite a page; treat claims that it does as speculation. Markup that is accurate and matches visible content is the safe default for every consumer.
- It never replaces visible content. What the markup says must be on the page for users.

## The rules that keep markup eligible

From Google's general structured data guidelines and spam policies:

- Mark up the main content of the page, visible to users, accurate and current. Do not mark up content hidden from users, unrelated to the page, or about something else.
- Use the most specific type that fits, and follow the feature's own guidelines (each feature page lists required and recommended properties and content policies).
- Reviews and ratings must come from real users and match what the page shows. Self-serving reviews (a business marking up reviews of itself on its own site for `LocalBusiness` or `Organization`) have not been eligible for review stars since 2019. Fake, bought or selectively displayed reviews are also a legal problem (`../../legal-ready/references/honest-commerce.md`, item 11).
- Violations lead to loss of eligibility or a structured data manual action in Search Console.
- Put JSON-LD in the server-rendered HTML. Google can read JSON-LD that JavaScript adds, but other consumers, including many AI crawlers, may never see it.

## Feature status (check before promising anything)

Google adds, changes and retires features often. Before recommending markup for a result feature, read that feature's page in Google's Search Gallery and note the date you checked. As of 2026:

| Status | Features |
|---|---|
| Documented and in use (examples) | Article; Breadcrumb; Product snippets and merchant listings; Review snippets (within their limits); Organization (logo and details); Local business; Event; Job posting; Recipe; Video; Dataset; Discussion forum; Profile page; Q&A; Software app; Paywalled content markup |
| Restricted | FAQ rich results: only well-known, authoritative government and health sites since August 2023. Breadcrumb trails: Google stopped displaying them in mobile results in early 2025 (desktop still shows them) |
| Retired | HowTo rich results (2023); sitelinks search box, so `WebSite` `SearchAction` markup no longer does anything in Google (November 2024); in 2025 Google phased out Book actions, Course info, Claim review (fact check), Estimated salary, Learning video, Special announcement and Vehicle listing |

Retired markup is still valid schema.org and does no harm, but do not add it for a Google feature, and remove it if it is costly to maintain. Bing and other consumers have their own documentation.

## JSON-LD patterns

Build markup from the same data the page renders, in one place per template, so it cannot drift from what users see. Prefer one script per page with linked entities over many disconnected blocks. Use absolute URLs, ISO 8601 dates with a time zone, and stable `@id` values (the page URL plus a fragment).

Home page:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", "@id": "https://www.example.com/#org",
      "name": "Example Outdoor", "url": "https://www.example.com/",
      "logo": "https://www.example.com/brand/logo-512.png" },
    { "@type": "WebSite", "@id": "https://www.example.com/#website",
      "url": "https://www.example.com/", "name": "Example Outdoor",
      "publisher": { "@id": "https://www.example.com/#org" } }
  ]
}
```

Article (Google lists no required properties for Article; these are its recommended ones):

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "How to choose trail running shoes",
  "image": ["https://www.example.com/img/trail-guide-16x9.jpg",
            "https://www.example.com/img/trail-guide-4x3.jpg"],
  "datePublished": "2026-03-02T08:00:00+01:00",
  "dateModified": "2026-09-18T10:30:00+02:00",
  "author": [{ "@type": "Person", "name": "Mara Lind",
               "url": "https://www.example.com/authors/mara-lind" }],
  "publisher": { "@type": "Organization", "@id": "https://www.example.com/#org",
                 "name": "Example Outdoor" }
}
```

Product with an offer, plus breadcrumbs:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Product", "name": "Trail Runner 3",
      "image": ["https://www.example.com/img/tr3-blue-1x1.jpg"],
      "description": "Waterproof trail running shoe with a 6 mm drop.",
      "sku": "TR3-BLU", "brand": { "@type": "Brand", "name": "Example Outdoor" },
      "offers": { "@type": "Offer", "url": "https://www.example.com/running/trail-runner-3",
                  "price": "129.00", "priceCurrency": "EUR",
                  "availability": "https://schema.org/InStock",
                  "itemCondition": "https://schema.org/NewCondition" } },
    { "@type": "BreadcrumbList", "itemListElement": [
      { "@type": "ListItem", "position": 1, "name": "Running", "item": "https://www.example.com/running/" },
      { "@type": "ListItem", "position": 2, "name": "Trail Runner 3" } ] }
  ]
}
```

Merchant listings additionally use shipping and return details (`shippingDetails`, `hasMerchantReturnPolicy`, or the same settings in Merchant Center); read the current feature page for which properties are required. Products sold in variants (size, color) can be described with `ProductGroup`, `hasVariant` and `variesBy`, which Google has documented since 2024; give each variant URL that exists its own canonical and offer data. Add `aggregateRating` or `review` only when the page shows those real reviews.

**Embed it safely.** User-supplied text inside JSON-LD (product names, reviews) can break out of the `<script>` element if it contains `</script>`. Escape `<` when serializing:

```js
// React or Next.js: render as a script tag with escaped JSON
const json = JSON.stringify(data).replace(/</g, "\\u003c");
<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />
```

```python
json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")   # server templates
```

## Validate and monitor

1. **Syntax:** the JSON parses and every node has `@type` (`scripts/seo_check.py` checks this offline on built HTML, flags retired feature types, and lists pages with rating markup for review).
2. **Vocabulary:** the Schema Markup Validator (validator.schema.org) checks schema.org types and properties for any consumer.
3. **Google eligibility:** the Rich Results Test, on code or a live URL; for a URL it uses the rendered page, so it also shows JavaScript-injected markup. Fix errors (they block eligibility); treat warnings (missing recommended properties) as optional improvements when the data exists.
4. **After deploy:** Search Console's rich result reports per feature (valid, warnings, errors per URL group), URL Inspection for single URLs, and "Validate fix" after correcting an issue. Watch for a drop in valid items after template changes.
5. **Results:** Search Console Performance, filtered by search appearance where a feature is listed, shows clicks and impressions for those results. Compare like-for-like periods before attributing changes to markup (`search-measurement.md`).

## Open Graph and social cards

Link previews in social networks, chat apps and messaging come from Open Graph tags (and X card tags). They do not affect search rankings, but they decide how shared links look.

```html
<meta property="og:type" content="article">
<meta property="og:title" content="How to choose trail running shoes">
<meta property="og:description" content="Fit, grip and drop explained, with a size chart.">
<meta property="og:url" content="https://www.example.com/guides/trail-shoes">
<meta property="og:image" content="https://www.example.com/og/trail-shoes-1200x630.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Three trail shoes on a rocky path">
<meta property="og:site_name" content="Example Outdoor">
<meta name="twitter:card" content="summary_large_image">
```

- The Open Graph protocol requires `og:title`, `og:type`, `og:image` and `og:url`; add `og:description`, `og:site_name` and image dimensions and `alt`. Open Graph uses the `property` attribute; X card tags use `name`. X falls back to the Open Graph title, description and image, so `twitter:card` is often the only X tag needed. Valid `twitter:card` values: `summary`, `summary_large_image`, `app`, `player`.
- `og:url` matches the canonical URL. Images use absolute HTTPS URLs that are publicly reachable: not behind authentication, not blocked for the platforms' fetchers (for example `facebookexternalhit`, `Twitterbot`, `LinkedInBot`; check current names), and returned with a correct `Content-Type`.
- An image around 1200 by 630 pixels (1.91:1) works on most platforms; check each platform's current minimums and file-size limits, and keep important content away from edges that some apps crop to a square.
- Generate per-page images and text from page data. A single site-wide image makes every shared link look the same.
- Platforms cache previews. After changing tags, refresh with the platform's tool where one exists (Facebook's Sharing Debugger, LinkedIn's Post Inspector); otherwise expect the old preview until the cache expires.
- For Google Discover, large images need to be at least 1200 pixels wide and the page must allow them (`max-image-preview:large`).

## Done when

- [ ] Markup is generated from the page's own data, describes visible main content, and is in the server HTML.
- [ ] Every JSON-LD block parses, has `@context` and `@type`, uses absolute URLs and dated ISO 8601 values; `seo_check.py` reports no errors.
- [ ] Each targeted feature was checked against its current Google documentation (date recorded) and passes the Rich Results Test without errors; retired features are not promised.
- [ ] Rating and review markup reflects real, visible reviews and no self-serving reviews.
- [ ] Open Graph has title, type, image and URL with an absolute, reachable image; `twitter:card` is valid; a preview was checked in at least one platform tool.
