# E-commerce search: categories, products, variants and merchant listings

Read this when the site sells products: category and collection pages, product pages, variants (size, color, material), out-of-stock, discontinued and seasonal products, `Product` and `Offer` markup, merchant listings and free product listings, product feeds, and measuring search for a shop. Faceted navigation and pagination mechanics are in `rendering-facets-pagination.md`; JSON-LD syntax and validation in `structured-data-and-social-cards.md`; product images in `image-search.md`; honest reviews and pricing claims in `../../legal-ready/references/honest-commerce.md`; platform specifics in `../../stacks/references/shopify.md` and `../../stacks/references/wordpress.md`.

## Page types and their jobs

| Page | Serves | Index it? |
|---|---|---|
| Category or collection | Broad and mid-range queries ("trail running shoes"), browsing | Yes; usually the strongest commercial pages |
| Subcategory or chosen facet ("waterproof trail running shoes") | Specific queries with their own demand and a distinct set of items | Only the combinations on the agreed list (`rendering-facets-pagination.md`) |
| Product | The product's name, model and specific needs ("trail runner 3 size 44") | Yes, one canonical URL per product or variant (below) |
| Brand page | Queries for a brand within the shop | Yes when it lists real range and adds something; otherwise a filter |
| Buying guides, comparisons, size and care guides | Learning and comparing queries before purchase | Yes, linked to the categories and products they discuss |
| Internal search results | Visitors only | No: keep out of the index, and out of crawling where the URL space is unbounded |
| Cart, checkout, account, wishlists | Visitors only | No; keep them out of crawling with `robots.txt` rules, and behind authentication where they hold personal data |

## Category pages

- A category page is a curated listing, not a block of keyword text. Lead with the items; add a short introduction that helps choose (what the range covers, how to pick a size or type) and links to subcategories and guides.
- Long "SEO text" below the grid that nobody reads adds nothing; put buying help where shoppers see it, or in a guide that links back.
- **Thin categories** (one or two items, or empty most of the year) dilute the site. Merge them into a parent, or keep them out of the index until they carry a real range.
- Sort orders and view options are duplicates of the default listing: canonicalize them to it or keep them uncrawlable. Pagination keeps its own self-canonical URLs.
- Keep out-of-stock items in listings only while they are likely to return, ordered after available ones if the business prefers, so pages do not empty and refill.

## Product pages

- **Unique, useful product content.** Manufacturer descriptions appear on every retailer's site. Keep the specification data, and add what only the shop knows: fit notes, measurements taken, comparisons with neighboring models, answers to questions customers ask, care instructions, compatibility.
- **The facts buyers need, visible:** price with taxes and currency for the market, availability, delivery cost and time, return terms, identifiers (brand, GTIN, model or MPN), specifications in a table, real photos from several angles.
- **Reviews** shown honestly, with the collection and moderation policy linked (`../../legal-ready/references/honest-commerce.md`). Reviews syndicated from a manufacturer or another retailer are labeled as such.
- **One canonical URL.** Products reachable under several category paths (some platforms generate `/collections/shoes/products/tr3` next to `/products/tr3`) canonicalize to one form, and internal links, sitemaps and markup use that form.
- **Breadcrumbs** follow the product's primary category (`site-structure-and-internal-links.md`).

## Variants

Variants are versions of one product that differ in size, color, material, pattern or similar. Google documented variant markup in 2024; read its current product variant page before implementing, and record the date.

| URL strategy | When it fits | Canonical |
|---|---|---|
| One URL for the product, variant chosen on the page | Variants differ only in size or minor options people do not search for | The product URL |
| One URL per variant (path or query parameter such as `?color=blue`) that preselects the variant | Variants have their own demand ("tr3 blue"), images, prices or availability | Either each variant self-canonical, or all pointing to one main variant; pick one approach and apply it consistently |

- Each variant URL that exists must load with that variant selected: its image, price, availability and identifiers, in the server HTML.
- Mark up the group with `ProductGroup` (`productGroupID`, `variesBy` with the varying properties, `hasVariant`), and each variant as a `Product` with its own `sku`, `gtin` where it exists, image and `offers`. A variant can point back with `isVariantOf` or `inProductGroupWithID`.
- Do not create indexable URLs for every option combination nobody searches for; that is faceted navigation again.

```json
{
  "@context": "https://schema.org",
  "@type": "ProductGroup",
  "@id": "https://www.example.com/products/trail-runner-3#group",
  "name": "Trail Runner 3",
  "brand": { "@type": "Brand", "name": "Example Outdoor" },
  "productGroupID": "TR3",
  "variesBy": ["https://schema.org/color", "https://schema.org/size"],
  "hasVariant": [
    { "@type": "Product", "sku": "TR3-BLU-44", "gtin14": "00012345678905", "name": "Trail Runner 3, blue, EU 44",
      "color": "Blue", "size": "44", "image": "https://www.example.com/img/tr3-blue.jpg",
      "url": "https://www.example.com/products/trail-runner-3?color=blue&size=44",
      "offers": { "@type": "Offer", "price": "129.00", "priceCurrency": "EUR",
                  "availability": "https://schema.org/InStock",
                  "itemCondition": "https://schema.org/NewCondition" } }
  ]
}
```

The GTIN above is a placeholder; use only identifiers assigned to the product.

## Availability over the product's life

| Situation | Page | `Offer.availability` |
|---|---|---|
| In stock | Normal | `InStock` (or `LimitedAvailability` when true) |
| Temporarily out of stock, expected back | Keep live and indexable; show a restock date if known and a notify-me option; offer alternatives | `OutOfStock` or `BackOrder` if orders are taken |
| Pre-order | Live, with the release or dispatch date | `PreOrder` with `availabilityStarts` |
| Discontinued, with a true successor | 301 to the successor, or keep the page with a clear notice and link if it still answers questions people search for (manuals, compatibility) | `Discontinued` if kept |
| Discontinued, no successor, no ongoing interest | 404 or 410; link the category from the not-found page | n/a |
| Seasonal (advent calendars, ski gear, event ranges) | One stable URL kept year round, updated for the next season, rather than a new URL each year | `OutOfStock` or `PreOrder` out of season |
| Withdrawn for legal or safety reasons | Remove as the law or recall requires; recall notices follow the regulator's instructions | n/a |

Do not `noindex` products that are temporarily unavailable: they lose their place and must be rediscovered. Do not redirect every removed product to the home page; that is treated as a soft 404 (`crawl-and-index-controls.md`).

## Product markup and merchant listings

Google distinguishes two product features; check both pages before promising either:

- **Product snippets** (ratings, price, availability under a result) for pages about a product, including reviews and comparisons where the product cannot be bought on the page. `AggregateOffer` is acceptable here, for example for a price range across sellers.
- **Merchant listings** (shopping results, the Shopping tab, product knowledge panels) for pages where the shopper can buy. They need `name`, `image` and `offers` with a single `Offer`, a `price` above zero and a `priceCurrency`; availability, condition, identifiers, `shippingDetails` and `hasMerchantReturnPolicy` are recommended.

Practices that keep markup trustworthy:

- **Generate it from the same data as the visible page and the feed,** in the server HTML. Google's guidance on structured data generated with JavaScript warns that dynamically added `Product` markup can make shopping crawls less frequent and less reliable for fast-changing price and availability.
- **Price as shown:** a plain number (`"129.00"`) with an ISO 4217 currency. A sale shows the sale price as the offer price; a former price can be marked with a `priceSpecification` whose `priceType` is a strikethrough price, only when it is a genuine previous price. In the EU, a price reduction must state the prior price, meaning the lowest price in the 30 days before the reduction (Price Indication Directive as amended in 2019).
- **Shipping and returns** can be described per product (`shippingDetails`, `hasMerchantReturnPolicy`), as organization-level policies in markup, or in Merchant Center or Search Console settings, depending on what Google supports at the time. Pick one source of truth so they cannot contradict each other.
- **Ratings** only from real reviews shown on the page; no ratings copied from third-party review platforms, and no self-assigned ratings.
- **Other properties appear over time** (member and loyalty pricing, certifications such as energy labels, unit pricing, adult-content flags). Add one only when the current feature page documents it and the data is true.

## Merchant Center and free listings

- Shops can appear in Google's shopping surfaces without ads through free listings, from a product feed in Merchant Center or from product data Google reads from the site. Price and availability in the feed, the markup and the page must agree; mismatches lead to disapprovals and, repeated, to account warnings.
- Merchant Center enforces its own policies (misrepresentation, unavailable promotions, prohibited products, image rules such as no promotional overlays or watermarks on product images). Read the policies before the first feed and after any warning.
- AI-generated product content is regulated there too: Merchant Center asks for AI-generated product images to carry IPTC metadata declaring them as such, and for AI-generated titles and descriptions to go in the dedicated attributes that declare their source (`image-search.md`). Check the current requirements.
- Programmatic access moved to the Merchant API. The older Content API for Shopping was sunset on 18 August 2026, and requests fail from September 2026 unless Google granted an extension; build only on the Merchant API. Credentials follow `search-data-connectors.md`.
- Feed changes, account settings and policy appeals are writes under the merchant's name: prepare them, show them, and apply only with the owner's go-ahead.

## Agents that shop

Shopping assistants and agents that browse, compare and buy for people read product pages and feeds. Clean, consistent product data and accessible pages help them for the same reasons they help shoppers (`agentic-browsing.md`). Open protocols for agent checkout were published in 2025 and 2026 by AI and commerce platforms; they are early, change quickly and are adopted unevenly. Evaluate one only with the current specification, and keep a human confirmation step and hard spending limits on any purchase an agent can trigger.

## Measuring a shop's search performance

- **Search Console:** Performance segmented by template (product, category, guide folders), and the search appearance filters for product results and merchant listings where Search Console offers them; the Product snippets and Merchant listings rich result reports for markup errors per template; Pages report per sitemap (split sitemaps by template).
- **Merchant Center:** item diagnostics (disapprovals, warnings) and its performance reports for free listings.
- **Analytics:** revenue and conversion by organic landing page and template, with consent limits stated (`search-measurement.md`).
- Compare product and category templates over like periods; seasonality is strong in retail, so prefer year over year.

## Changes that need the owner's go-ahead

Bulk redirects or removals of products or categories; `noindex` or canonical changes on product or category templates; price, shipping or return data in markup or feeds; facet indexing rules; feed and Merchant Center account changes; review display policy.

## Done when

- [ ] Each page type has a stated role and index decision; internal search, cart and account pages stay out of the index.
- [ ] Categories are useful listings with links to subcategories and guides; thin ones are merged or kept out of the index.
- [ ] Product pages carry the shop's own information beyond manufacturer text, one canonical URL, and the facts buyers need in the server HTML.
- [ ] Variants follow one documented URL and canonical strategy, with `ProductGroup` markup matching the visible variants.
- [ ] The availability table is implemented in the templates; no temporarily unavailable product is `noindex`ed or redirected to the home page.
- [ ] `Product` and `Offer` markup, the feed and the page agree on price, currency and availability; the Rich Results Test and Merchant Center diagnostics show no errors on samples of each template.
- [ ] Results are reported per template with Search Console, Merchant Center and analytics sources and dates.
