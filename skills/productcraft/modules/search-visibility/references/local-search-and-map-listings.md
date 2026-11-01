# Local search and map listings

Read this when a business serves customers at a place or in an area: business profiles on map platforms, the local pack and map results, name, address and phone (NAP) consistency across listings, reviews and how to ask for and answer them, location and service-area pages, multi-location sites, and measuring local visibility. The entity fact sheet, `LocalBusiness` basics and how AI products describe a business are in `entity-clarity.md`; generated location pages are judged by `programmatic-pages.md`.

## How local results work

- Google states that local results rank mainly on **relevance** (how well a listing matches the search), **distance** (from the searcher or the place named in the query) and **prominence** (how well known the business is, including reviews, links and mentions). Nobody can pay for a better local ranking, and the business cannot change distance.
- Results depend on where the searcher stands. The same query from two streets apart can return different listings, so one check from one place proves little.
- Local results draw on the business profile first, then the website, reviews and other sources. AI answers and assistants describe local businesses from the same kinds of sources, and some of them lean on listings outside Google (Bing Places, Apple Business Connect, review platforms). Keep every listing true, not only the Google one.
- Published "local ranking factor" weights come from practitioner surveys and correlation studies. They can guide what to check; they are not measurements of any engine, and percentages from them should not appear in a report as facts.

## Decide the business type first

| Type | Example | Profile | Website |
|---|---|---|---|
| Storefront | Shop, clinic, restaurant where customers visit | Real, staffed address shown | A page per location with address, hours, directions |
| Service-area | Plumber, mobile groomer who travels to customers | Address hidden; service areas set (by city or region, within reasonable travel) | Service pages; area pages only with area-specific substance |
| Hybrid | Showroom that also installs at customers' homes | Address shown and service areas set | Both, kept consistent |
| Online only | No customer-facing location | Usually not eligible for a business profile | Ordinary pages; local intent is not the goal |

Eligibility rules (staffed hours, no virtual offices or mailboxes as the address, one profile per real location or practitioner under each platform's rules) differ by platform and change. Read the current guidelines of each platform before creating or editing a profile, and note the date.

## Business profiles

The main profiles in most markets are Google Business Profile, Apple Business Connect and Bing Places; OpenStreetMap feeds many apps and has community editing rules of its own (map what exists on the ground; no promotional text). Market-specific map and directory services matter in some countries; ask which ones customers use.

| Field | Do | Do not |
|---|---|---|
| Name | The real-world name as on the signage, letterhead and registration | Add keywords, city names or slogans; this breaks the guidelines and is a common cause of suspension |
| Primary category | The most specific category that describes the core business | Pick a broader or trendier category for reach |
| Additional categories | Only services the business really provides at that location | Stack loosely related categories |
| Address or service area | The address customers visit, entered the same way everywhere; service areas the business really covers | Use a virtual office, a mailbox or a home address shown for a service-area business |
| Hours | Regular hours, special and holiday hours, temporary closures | Leave old hours after a change; mark "closed" to hide from competitors' searches |
| Phone | A number that reaches this location, in international format | Use call-tracking numbers inconsistently across listings (if one is used, keep the main number as an additional number) |
| Website link | The location page, tagged with campaign parameters so analytics can tell profile clicks apart | Point every location at the home page |
| Services, products, attributes | True and current; attributes only when they apply | Claim attributes (accessible entrance, women-owned, open 24 hours) that are not verified fact |
| Photos and description | Real, current photos of the place, team and work; a plain description of what the business does | Stock or AI-generated photos presented as the premises; descriptions stuffed with places |

- **Ownership.** The business owns its profiles under company accounts, with at least two owners or managers, and grants an agency manager access, never ownership. Record who has access in the project's records.
- **Edits can trigger re-verification** or a review of the profile. Batch changes, make them from the owner's accounts, and expect delays after a name, address or category change.
- **Features come and go.** Profile features have been added and withdrawn (Google ended profile chat in 2024, for example). Check the current help pages before recommending one, and never build a process on a feature without checking it still exists.
- **Suspensions** usually follow a guideline issue (name, address, eligibility) or an automated flag after edits. Fix the cause, collect evidence (business registration, signage photos, utility bill, lease), and use the platform's reinstatement or appeal process. Do not create a new profile to escape a suspension.
- **Spam from others** (keyword-stuffed names, fake locations) can be reported through the platform's edit suggestions or complaint forms. Report facts with evidence, once; do not harass competitors or mass-report.

## Name, address and phone consistency

Inconsistent details confuse engines, map apps, assistants and customers. Work from the entity fact sheet (`entity-clarity.md`) and keep an inventory of listings:

| Platform | Listing URL | Name | Address | Phone | Website | Status | Checked |
|---|---|---|---|---|---|---|---|

Compare the listings with the sheet field by field after normalizing: phone numbers to E.164, addresses by component (street, number, postal code, locality), names with case and punctuation folded. A sketch for a CSV export of the inventory:

```python
# Input CSV: platform,url,name,street,postal_code,locality,phone,website
# with one row whose platform is "fact-sheet" holding the confirmed values.
import csv, re, sys

def phone(v):   # keep digits and a leading +, enough to compare one market's numbers
    v = v.strip()
    return ("+" if v.startswith("+") else "") + re.sub(r"\D", "", v)

def text(v):
    return re.sub(r"[^\w]+", " ", v.lower()).strip()

FIELDS = {"name": text, "street": text, "postal_code": text, "locality": text, "phone": phone, "website": text}
rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
truth = next(r for r in rows if r["platform"] == "fact-sheet")
for r in rows:
    diffs = [f for f, norm in FIELDS.items() if norm(r.get(f, "")) != norm(truth.get(f, ""))]
    if diffs:
        print(f"{r['platform']}: differs in {', '.join(diffs)}  ({r.get('url', '')})")
```

Phone normalization this simple only works within one country's format; use a proper library or manual checks across countries. Treat the output as a worklist and check each difference by hand: abbreviations ("St" and "Street") are harmless, a wrong postal code is not.

- **Fix before adding.** Correct the main profiles first, then the data suppliers and directories that feed others in the market, then visible directories in the niche. Accuracy across the listings that matter beats a count of listings.
- **Duplicates:** find them by phone, address and name variants; ask the platform to merge or remove them through its own process. Never leave two live profiles for one location.
- **Moves, rebrands, phone changes:** update the fact sheet, the site and the main profiles first (on the same day where possible), then directories; keep old numbers forwarding for a while; follow `site-migrations.md` if URLs change.
- Submitting to directories and data suppliers writes to third parties under the business's name. Show the list and the exact data first, and submit only with the owner's go-ahead.

## Reviews

Reviews influence both customers and local prominence, and they are regulated.

- **Ask every customer, the same way.** A link or QR code after the service, at a consistent point in the process. Asking only happy customers, or filtering by a satisfaction question before showing the review link ("review gating"), is prohibited by Google's policies and is unlawful review suppression or manipulation in several markets.
- **No payment or incentive for reviews on platforms that forbid it** (Google does). Where incentives are allowed at all, they must not depend on sentiment and must be disclosed. The US FTC rule on consumer reviews (16 CFR Part 465, in force since October 2024), the EU consumer law rules on reviews and the UK DMCC Act 2024 apply; details are in `../../legal-ready/references/honest-commerce.md`.
- **Never write, buy, swap or have staff post reviews,** and never ask for reviews in exchange for a discount on the same platform.
- **Answer reviews,** good and bad, promptly and factually, in the business's voice. Do not reveal personal or transaction details. Health providers must not confirm that a reviewer is a patient or discuss their care: under HIPAA that is a disclosure of protected health information, and the US regulator has fined providers for review replies. Similar confidentiality applies to lawyers and other professions with secrecy duties.
- **Removal requests** are for reviews that break the platform's policy (spam, conflicts of interest, off-topic, harassment), with evidence, through the platform's process. A fair negative review stays; answer it.
- **Watch the pattern, not a magic number.** Track count, rating distribution and recency per location over time, and the reply rate. Sudden bursts of five-star reviews from new accounts, or of one-star reviews after a public dispute, are worth reporting to the platform. Claims that a specific review count or gap length triggers ranking changes come from single studies; do not present them as rules.
- **On the website:** showing reviews collected on the site is fine with honest moderation. Review star markup for the business itself on its own site is not eligible for rich results (`structured-data-and-social-cards.md`).

## Location pages and multi-location sites

- **One page per real location,** at a stable URL in a clear folder (`/locations/leeds/` or `/locations/leeds-city-centre/`), reachable through crawlable links from a locations index. A store locator that only works through a search box or map script leaves the pages undiscoverable; add a plain list of links by region.
- **Content specific to the place:** address, hours including holidays, phone, how to get there and park, services and products offered at that branch, staff, photos of that site, local policies, and answers to questions customers ask about that location. A page whose text stays true after swapping the city name is a doorway page; `programmatic-pages.md` has a check for that.
- **Service-area pages** only where the business really serves the area and has something specific to say (local regulations, typical jobs there, response times, projects done there). A page per town in a county with swapped names is the classic doorway pattern.
- **Markup per location:** the most specific `LocalBusiness` subtype, a stable `@id` per location, `parentOrganization` pointing at the organization's `@id` (schema.org lists `branchOf` as superseded by it), `address`, `telephone`, `openingHoursSpecification` (with special hours as separate entries with `validFrom` and `validThrough`), `geo` coordinates (Google asks for at least five decimal places), and `department` for distinct departments with their own hours. Values come from the fact sheet and match the visible page and the profile. Example and syntax: `entity-clarity.md` and `structured-data-and-social-cards.md`.
- **Embedded maps** help visitors; they are not a ranking lever. Load them lazily so they do not slow the page.
- Opening, closing or moving a location is a change to the profile, the page, the markup, the sitemaps and redirects together. Keep a closed location's page with a clear notice and a link to the nearest location for as long as people still look for it, or redirect to that location if the page serves no one.

## Measuring local visibility

| Question | Source | Limits |
|---|---|---|
| How do people interact with the profile? | The platform's performance or insights reports: views, searches that showed the profile, calls, direction requests, website clicks, bookings | Platform definitions change; compare like periods; some actions are sampled or thresholded |
| What do they do on the site? | Analytics segment for the tagged profile link; location page entrances | Only clicks that reach the site; consent and blockers hide some |
| Where does the listing rank? | A licensed local rank tracker sampling the query from a grid of points around the location, with date, device and grid recorded | A sample of simulated searchers; report as "top 3 at 31 of 49 points on 2026-10-14", not as one rank |
| How does the website rank for local queries? | Search Console Performance filtered by page and country | Does not separate map-pack clicks from the profile link unless the link is tagged |
| What do AI products say? | Repeated, dated samples of customer questions (`ai-answer-engines.md`) | Varies by run, location and account |

- Do not scrape map results or listings; use the platforms' own reports, their APIs under their terms, or licensed providers.
- Fix the tracking conditions (queries, grid size and spacing, device, cadence) before the first run and keep them; changing them breaks the series.
- Report changes per location against a control location or period, as for any search change (`search-measurement.md`).

## Changes that need the owner's go-ahead

Name, category, address or service-area changes; closing, merging or removing profiles; marking a location closed or moved; bulk submissions to directories or data suppliers; public replies to reviews (the business's voice, sometimes legal exposure); reporting competitors; giving any third party access to profiles. Prepare the exact change, the reason and the expected effect, then wait for a yes.

## Done when

- [ ] Business type and eligibility were checked against each platform's current guidelines, with the date recorded.
- [ ] Every main profile is owned by the business, matches the fact sheet field by field, and links to its location page with a tagged URL.
- [ ] A listing inventory exists; differences and duplicates are fixed or reported, with the owner approving submissions to third parties.
- [ ] The review process asks every customer the same way, with no gating, payment or staff reviews; replies disclose no personal or confidential information.
- [ ] Each real location has a crawlable page with place-specific content and matching `LocalBusiness` markup; no swapped-name area pages are indexable.
- [ ] Local visibility is reported from platform reports, tagged analytics and licensed grid samples, each with source, conditions and dates.
