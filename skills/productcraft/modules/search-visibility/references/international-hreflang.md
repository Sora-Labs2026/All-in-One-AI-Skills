# International and multilingual sites

Read this when a site serves more than one language or country: choosing the URL structure, writing `hreflang`, handling language detection and redirects, and checking that search engines show each audience the right version. Interface translation, right-to-left layout and text expansion are in `../../responsive-accessibility.md`.

`hreflang` does not make a page rank. It tells search engines which equivalent page to show to which language or region, and it groups the versions so they are not treated as competing duplicates.

## Choose the URL structure

| Structure | Example | Strengths | Costs |
|---|---|---|---|
| Country-code domains | `example.de`, `example.fr` | Clear country signal to users and engines | Several domains to run, secure and build reputation for; country-only, not language |
| Subdirectories | `example.com/de/`, `example.com/fr-ca/` | One host, simple to run, shared reputation, easy reporting per folder | Country signal comes only from `hreflang` and content |
| Subdomains | `de.example.com` | Separate hosting per market is possible | More set-up and verification; often treated more like separate sites |
| Parameters | `example.com/?lang=de` | Few | Easy to lose in links and canonicals; avoid |

For most sites, subdirectories are the cheapest to get right. Whatever you pick, give each language or locale version its own stable URL. Serving different languages at the same URL by cookie, `Accept-Language` or IP address leaves crawlers seeing only one version.

Google retired the country-targeting setting in Search Console in 2022; there is no dashboard switch for country any more.

## hreflang rules

- **Values:** an ISO 639-1 language code (`de`), optionally a script (ISO 15924, `zh-Hant`) and an ISO 3166-1 alpha-2 region (`de-AT`, `zh-Hant-TW`). A region alone is invalid. Common mistakes are `en-UK` (the code is `GB`), `jp` (Japanese is `ja`) and `cn` as a language (Chinese is `zh`). Codes are case-insensitive; the conventional form is `en-GB`.
- **`x-default`** names the page for users matching no listed version, typically a language chooser or the main international page.
- **Complete sets.** Every version lists every version in the set, including itself. If page A names B but B does not name A, engines ignore the pair. Keep the sets symmetrical across all versions.
- **Absolute URLs** that return 200, are indexable and are the canonical URL of that version.
- **Canonical per version.** Each version's canonical points at itself. Pointing every language at the English page tells engines the other languages are duplicates and drops them.
- **One method per page set**, kept consistent:

```html
<!-- In the <head> of every version -->
<link rel="alternate" hreflang="en-GB" href="https://www.example.com/en-gb/delivery">
<link rel="alternate" hreflang="en-US" href="https://www.example.com/en-us/delivery">
<link rel="alternate" hreflang="de" href="https://www.example.com/de/lieferung">
<link rel="alternate" hreflang="x-default" href="https://www.example.com/delivery">
```

```text
# HTTP header, for PDFs and other non-HTML files
Link: <https://www.example.com/en/terms.pdf>; rel="alternate"; hreflang="en",
      <https://www.example.com/de/agb.pdf>; rel="alternate"; hreflang="de"
```

```xml
<!-- XML sitemap: each <url> repeats the full set -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://www.example.com/de/lieferung</loc>
    <xhtml:link rel="alternate" hreflang="de" href="https://www.example.com/de/lieferung"/>
    <xhtml:link rel="alternate" hreflang="en-GB" href="https://www.example.com/en-gb/delivery"/>
  </url>
  <url>
    <loc>https://www.example.com/en-gb/delivery</loc>
    <xhtml:link rel="alternate" hreflang="de" href="https://www.example.com/de/lieferung"/>
    <xhtml:link rel="alternate" hreflang="en-GB" href="https://www.example.com/en-gb/delivery"/>
  </url>
</urlset>
```

Sitemaps suit large sets because the head stays small and the sets live in one generated file. Generate `hreflang` from one data source (a table of equivalent pages per locale), never by hand per template, or the sets drift out of sync.

## Detection and redirects

- Do not force-redirect by IP address or browser language. Users travel and use VPNs, and Google crawls mainly from US addresses, so forced redirects hide versions from both. Suggest a version with a dismissible banner and remember the user's choice.
- If an entry URL must choose a locale (such as the bare home page), redirect with 302 from the `x-default` URL only, and keep every locale URL directly reachable.
- Link the versions to each other visibly (a language switcher with `<a href>` links), which helps users and discovery.
- Set `<html lang="de-AT">` correctly for accessibility and screen readers. Google says it detects page language from the visible content and does not use `lang` or `content-language` for that; Bing documents using them, so set them correctly anyway.

## Content that earns the locale

- A locale page needs a real translation or localization: currency, prices, units, delivery terms, legal pages, phone numbers and dates for that market. Translating only the navigation around untranslated text creates near-duplicates.
- Machine translation without review is risky where accuracy matters and can fall under the scaled-content spam policy when it produces many low-value pages (`links-authority-and-trust.md`). Have translations reviewed, and publish locales you can maintain.
- Same-language variants (en-GB, en-US, en-AU) are fine and are the main reason to use regions in `hreflang`, but they should differ where the markets differ (spelling, prices, shipping), or one page with an `x-default` may serve better.
- Legal and consent obligations differ by market (`../../legal-ready/GUIDE.md`).

## Common errors and how they show up

| Error | Symptom | Fix |
|---|---|---|
| Missing return links | Wrong version shown in some countries; versions compete | Generate sets from one table; check symmetry with `scripts/seo_check.py` or a crawler |
| Invalid codes (`en-UK`, `jp`) | That entry is ignored | Validate against ISO lists |
| `hreflang` pointing at redirects, 404s or `noindex` pages | Entry ignored; crawl waste | Point at final canonical URLs |
| All versions canonicalized to one language | Only that language indexed | Self-canonical per version |
| `hreflang` added by JavaScript only | Inconsistent pickup | Server HTML, header or sitemap |
| Mixing methods with different sets | Conflicting signals | One method, one source of truth |

Search Console no longer has a report for `hreflang` errors, so checking is up to you: run `scripts/seo_check.py` on the build (it validates codes, self-references, absolute URLs, duplicates and return links between pages it can see), and crawl production with a crawler that reports `hreflang` sets. Then confirm with real results: Search Console Performance filtered by country shows which URL earns impressions in each market.

## Done when

- [ ] Each locale has its own URL; no content varies by IP or `Accept-Language` at a single URL.
- [ ] Every page in a set lists all versions including itself plus `x-default`, with valid codes and absolute, canonical, indexable URLs, generated from one data source.
- [ ] Each version is self-canonical; the language switcher uses crawlable links.
- [ ] `seo_check.py` reports no `hreflang` errors on the build; a production crawl agrees.
- [ ] Country-filtered Search Console data, with its date range, shows the intended URL per market for key pages.
