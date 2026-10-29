# Entity clarity: organizations, people, products and places

Read this when the user wants search engines and AI answers to describe their organization, people or products correctly; when a knowledge panel is missing or wrong; when AI products confuse the brand with another; when adding Organization, Person or LocalBusiness markup; or for local business listings. JSON-LD syntax, validation and feature eligibility are in `structured-data-and-social-cards.md`.

Engines connect mentions across the web to entities: one organization, one person, one product. Clarity means the same facts, stated the same way, wherever the entity is described, with links that say "these profiles are all the same entity". It is not a ranking trick; it prevents confusion and wrong answers.

## One fact sheet, reused everywhere

Keep a single entity fact sheet in the project state (`search-project-state.md`). Every page, markup block, profile and directory listing is filled from it, and every change starts there.

| Field | Value | Source | Last verified |
|---|---|---|---|
| Canonical name | Northwind Analytics | Company registration | 2026-10-01 |
| Legal name | Northwind Analytics Ltd | Companies register entry | 2026-10-01 |
| Other names | Northwind; formerly "NW Metrics" (renamed 2024) | Rename announcement URL | 2026-10-01 |
| Type | Organization (software company) | Owner | 2026-10-01 |
| Description (neutral, one sentence) | Northwind Analytics makes reporting software for small nonprofits. | Owner-approved | 2026-10-01 |
| Website and logo URL | https://www.northwind.example/ , /logo.png | Site | 2026-10-01 |
| Founded, founders, headquarters | 2019; founders with their consent; Leeds, UK | Owner, registry | 2026-10-01 |
| Identifiers | Company number, LEI, Wikidata item if one exists | Registries | 2026-10-01 |
| Official profiles | LinkedIn page, GitHub organization, app store listing | Each profile | 2026-10-01 |
| Not to be confused with | Northwind Freight (unrelated logistics company) | Observed in results and AI answers | 2026-10-01 |

- Only facts the owner confirms or a primary record shows. Never infer a founding date, headcount or founder from a third-party page and present it as fact.
- People in the sheet need their consent, and only work-relevant facts. Keep personal contact data out (`../../legal-ready/references/data-minimization.md`).
- Re-verify on any change (rename, move, new leadership) and at a set interval agreed with the user.

## On the site

- **About page:** states the fact-sheet facts in plain sentences, starting with the neutral description. Names, dates and places match the sheet exactly.
- **Contact page** with real ways to reach the business; for local businesses the same name, address and phone as the listings.
- **Author pages** for people who write or review content: a true biography, relevant experience and qualifications, links to their profiles elsewhere, and the pages they wrote. Never invent credentials.
- **Consistent naming:** the canonical name in the same form on every page, in titles, footers and markup. Use a qualifier consistently if the name collides with another entity.
- **Product pages** that state what the product is, who makes it, and its name exactly as elsewhere.

## Markup that matches the page

Describe the organization once, on the homepage or about page (Google recommends one of those; it need not be on every page), with a stable `@id` that other markup can reference. Give the website a name so search can show the preferred site name. Reference authors as people with their own pages.

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://www.northwind.example/#organization",
      "name": "Northwind Analytics",
      "legalName": "Northwind Analytics Ltd",
      "alternateName": ["Northwind", "NW Metrics"],
      "url": "https://www.northwind.example/",
      "logo": "https://www.northwind.example/logo.png",
      "description": "Northwind Analytics makes reporting software for small nonprofits.",
      "foundingDate": "2019",
      "sameAs": [
        "https://social.example/company/northwind-analytics",
        "https://code.example/northwind-analytics"
      ]
    },
    {
      "@type": "WebSite",
      "@id": "https://www.northwind.example/#website",
      "name": "Northwind Analytics",
      "url": "https://www.northwind.example/",
      "publisher": { "@id": "https://www.northwind.example/#organization" }
    }
  ]
}
</script>
```

On an article, the author points at the person and their page:

```json
"author": {
  "@type": "Person",
  "name": "Priya Raman",
  "url": "https://www.northwind.example/authors/priya-raman",
  "sameAs": ["https://social.example/in/priya-raman"]
}
```

- **`sameAs`** lists URLs that unambiguously identify the same entity: its own official profiles, and reference entries about it (a Wikidata item or Wikipedia article if they exist). Not directory listings, not pages that merely mention it, never another entity's profile.
- Every value appears visibly on the site and matches the fact sheet. Markup that claims what the page does not show is a spam risk and confuses engines.
- Validate with Google's Rich Results Test (for Google features) and the Schema.org validator (for general syntax), and note that passing validation is not eligibility for a feature.
- Use the most specific accurate type (`LocalBusiness` subtypes for physical locations, `SoftwareApplication` or `Product` for products) only where the visible page supports it.

## Knowledge panels

- Google builds knowledge panels automatically from its Knowledge Graph, which draws on many sources. Nobody can buy one or create one directly.
- If a panel exists for the entity, an authorized representative can claim it through Google's verification process (signing in with an official profile listed in the panel) and then suggest changes. Anyone can send feedback from the panel. Changes are requests and may not be accepted.
- When a panel is wrong, fix the sources first: the site's own facts and markup, official profiles, and reference entries. Then use feedback with links to those sources.
- No panel is not a defect to fix at any cost; it often reflects limited independent coverage.

## Wikidata and Wikipedia

These are community projects with their own rules, not marketing channels.

- **Wikipedia** requires notability shown by significant coverage in independent reliable sources, and strongly discourages editing articles about yourself, your employer or your clients. Paid editing must be disclosed under the Wikimedia Terms of Use. Never write or commission a promotional article; if the user has a conflict of interest, the route is to propose changes on the article's talk page with sources.
- **Wikidata** items must meet its notability policy (for example, being described by serious, publicly available references) and carry references for statements. Do not create items only to gain a `sameAs` link. Correct existing items with sourced statements, disclosing any affiliation.
- If the entity does not meet these bars, it does not need them. Clarity on the site and official profiles is enough to start.

## Name collisions and renames

- **Shared name:** use the same qualifier everywhere ("Northwind Analytics", never just "Northwind"), keep descriptions distinct and specific, use a unique `@id`, list `sameAs` profiles, and add a "not to be confused with" line on the about page if confusion is real and frequent.
- **Renamed or merged:** state "formerly" on the about page, list the old name in `alternateName`, redirect old domains and pages to their equivalents, and update every profile and listing from the fact sheet.

## Local businesses

Google states that local results rank mainly on relevance, distance and prominence. What a business can influence:

- **Business Profile:** the real-world business name without added keywords or locations (keyword-stuffed names break the profile guidelines), an accurate primary category, the real address (no virtual offices or P.O. boxes where a staffed location is required), or a hidden address with service areas for businesses that visit customers, accurate hours including holidays, real photos. One profile per real location.
- **Consistency:** the same name, address and phone (NAP) as the fact sheet on the site, the Business Profile, Apple Business Connect, Bing Places and the directories that matter in the market. Fix wrong listings before adding new ones; accuracy beats volume.
- **Reviews:** ask customers fairly and never buy, filter or gate reviews (`../../legal-ready/references/honest-commerce.md`). Reply to reviews honestly.
- **Location pages:** one per real location, with information specific to it (address, hours, staff, services offered there, directions, local details). City pages for places where the business has no presence and nothing specific to say are doorway pages (`programmatic-pages.md`).
- `LocalBusiness` markup (or its most specific accurate subtype) on each location page, matching the profile and the visible page:

```json
{
  "@context": "https://schema.org",
  "@type": "Dentist",
  "@id": "https://www.smile.example/locations/leeds#location",
  "name": "Smile Dental Leeds",
  "parentOrganization": { "@id": "https://www.smile.example/#organization" },
  "url": "https://www.smile.example/locations/leeds",
  "telephone": "+44 113 496 0000",
  "address": { "@type": "PostalAddress", "streetAddress": "12 Example Street",
               "addressLocality": "Leeds", "postalCode": "LS1 1AA", "addressCountry": "GB" },
  "openingHoursSpecification": [{ "@type": "OpeningHoursSpecification",
    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "opens": "08:30", "closes": "17:30" }]
}
```

The values come from the fact sheet; the phone number above is from the UK range reserved for drama and examples.

## How AI products describe the entity

- Ask each product the questions a customer would ask ("What is Northwind Analytics?", "Who makes reporting software for small nonprofits?", "Northwind Analytics vs ..."), signed out, several times, and record date, product, answer and cited sources.
- Classify errors: wrong facts, confusion with another entity, outdated name, missing entirely.
- Fix the sources the answers cite or rely on (the site, official profiles, reference entries, prominent third-party pages that are wrong, via their correction processes). Do not try to "prompt" the engines through hidden text or fake pages (`ai-answer-engines.md`).
- Re-check on the agreed schedule; expect variation between runs.

## Checks (done when)

- [ ] A fact sheet exists, each fact with a source and verification date, confirmed by the owner.
- [ ] About, contact and author pages state the same facts; names are consistent sitewide.
- [ ] Organization and WebSite markup (and Person, LocalBusiness or Product where relevant) match visible content and the sheet, with stable `@id` values and only true `sameAs` links; validators were run.
- [ ] Knowledge panel, Wikidata and Wikipedia actions respect their rules, with conflicts of interest disclosed.
- [ ] Local listings match the sheet; AI descriptions were sampled and errors traced to sources.
