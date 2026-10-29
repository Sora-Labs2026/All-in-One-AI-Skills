# Links, authority scores and trust signals

Read this when reviewing the links and mentions a site earns from elsewhere, judging a domain's "authority" or trustworthiness, deciding about a disavow file, handling a manual action, or checking a site against the spam policies. Page-level content quality against E-E-A-T is in `content-quality-review.md`; entity clarity (Organization and Person markup, `sameAs`, knowledge panels) is in `entity-clarity.md`.

This module never builds links by buying, exchanging or placing them. Paid or exchanged links, private blog networks, link-placement services, mass guest posting with keyword anchors, comment and forum spam, and publishing on another site to borrow its reputation all break search engines' spam policies. If asked for them, explain the risk and offer the legitimate work below.

## What links do and what Google says about them

- Links help engines discover pages and are one of many signals of importance and relevance. Google's documentation describes using links as a signal and its spam systems (SpamBrain among them) as neutralizing many unnatural links rather than counting them.
- Its link-spam policy covers buying or selling links that pass ranking credit, excessive link exchanges, automated link creation, required links in widgets or terms, and keyword-rich anchors placed at scale in articles, directories or comments. Paid, sponsored and affiliate links are fine when marked `rel="sponsored"` or `nofollow`.
- A link's value depends on whether a real editor chose it, on a relevant page people read. Counts alone mean little.

## Data sources and their limits

| Source | What it shows | Limits |
|---|---|---|
| Search Console Links report | A sample of top linking sites, linked pages and anchor text, as Google sees them; exportable | A sample, not the full set; no quality judgment |
| Bing Webmaster Tools backlinks | Bing's view, including for competitors' domains | Its own crawl coverage |
| Third-party link indexes | Large crawls with history, new and lost links, competitor comparisons | Each crawls a different part of the web, so counts disagree; their authority scores are proprietary models that Google does not use |
| Analytics referrals | Which links send visitors | Only links people click |
| Server logs and old URL lists | Old URLs that still receive links or visits | Needs joining with link data |

Domain Rating, Domain Authority, Authority Score, Trust Flow and similar numbers are vendor estimates built from each vendor's link graph. They are useful for comparing sites within one tool. They are not Google metrics, they move when the vendor changes its model, and they should never be a goal in a report. Say which tool produced a number and when.

## Reviewing a link profile

1. **Export referring domains** (not individual links) from Search Console and at least one third-party index; deduplicate by registrable domain; record the export dates.
2. **Group by kind:** editorial mentions in articles, press, reviews and resource pages; partner, customer and supplier sites; directories and profiles; forums and comments; scraped or auto-generated copies; sitewide footer or widget links; links on unrelated sites in other languages.
3. **Look at a sample of real pages** in each group. Judge whether a person chose the link, whether the page is relevant and read, and where the link sits.
4. **Note patterns, not individual oddities.** Every site collects some spam it did not ask for, and engines mostly ignore it. Worry about patterns the site or its agencies created: many keyword-anchor links from unrelated sites, sponsored posts without `sponsored`, link exchanges, or a sudden burst bought in a campaign.
5. **Find what to fix on your side:** old URLs with external links that now return 404 (redirect them to the closest equivalent; this is the cleanest link reclamation there is), links pointing at redirect chains or non-canonical URLs, and your own outbound paid links missing `sponsored`.
6. **Compare with competitors only to learn** which kinds of pages earn links in the niche (original data, tools, guides, news). Do not copy their link sources.

Legitimate ways to earn links are the same as earning attention: original research and data, useful tools, clear documentation, expert commentary for journalists, partnerships that make sense on their own, and fixing mentions that link to the wrong or a broken URL. Outreach must be honest about who is asking and why (`../../ethical-persuasion.md`), and email outreach follows marketing-email law (`../../legal-ready/GUIDE.md`).

## Disavow files

The disavow tool asks Google to ignore links to your site. Google's guidance is that most sites never need it.

- **Use it** when the site has a manual action for unnatural links to it, or when the site or an agency built paid or scheme links that cannot be removed and a manual action is likely.
- **Do not use it** for random spam links, low-quality directories, scraped copies or fear of "negative SEO"; engines already discount these, and disavowing good links by mistake removes their value.
- The file lists `domain:example.net` lines or full URLs, one per line, with `#` comments. Uploading replaces the previous file for that property; keep the old file and a dated changelog.
- Uploading or changing a disavow file is the owner's decision: show the list, the evidence for each group, and the expected consequence first. Bing offers its own disavow tool.

## Manual actions and security issues

- Check Search Console's Manual actions and Security issues reports (and Bing's equivalents) at the start of any audit and after any sudden site-wide drop. A manual action names the policy and often sample URLs.
- To recover: fix the cause across the site, not only on the sample URLs; document what was removed or changed and when; then file a reconsideration request that explains the cause, the fix and how it will not recur. Be factual; the reviewers read it.
- Hacked content (injected spam pages, cloaked redirects, malware) needs a security response first: find the entry point, clean, rotate credentials, then request review (`../../code-security-review/GUIDE.md`).

## Spam policies to recognize in an audit

Google's spam policies were last broadly expanded in March 2024. Flag these when you see them, and never implement them:

| Policy | How it shows up in an audit |
|---|---|
| Scaled content abuse | Many pages produced (by people, templates or AI) mainly to rank, with little original value: rewrites, spun or stitched text, near-empty location or product variants |
| Site reputation abuse | Third-party pages published on a trusted site to exploit its ranking signals, with little oversight by the host (Google clarified in November 2024 that first-party involvement does not make this acceptable) |
| Expired domain abuse | A bought expired domain repurposed to rank unrelated, low-value content on its old reputation |
| Doorway pages | Many near-identical pages targeting variations of a query that funnel users to one destination |
| Cloaking and sneaky redirects | Bots served different content or URLs than users; mobile-only redirects to unrelated sites |
| Hidden text and links, keyword stuffing | Text styled to be invisible, off-screen or tiny; repeated lists of keywords or places |
| Link spam | As above |
| Thin affiliate pages | Product pages copied from a merchant feed with no added value |
| Scraped content | Copied or lightly modified content from other sites |
| User-generated spam | Spam comments, forum posts or profiles left unmoderated |
| Misleading functionality, malicious behavior | Fake tools or downloads, unwanted software, deceptive ads |
| Fake or incentivized reviews and ratings markup that does not reflect real reviews | Rating stars without visible, genuine reviews (`structured-data-and-social-cards.md`) |

Programmatic page sets are acceptable only when every page carries unique, useful data a searcher would want; `programmatic-pages.md` shows how to tell the difference, and covers publishing on other sites.

## Trust and authority at site level

E-E-A-T (experience, expertise, authoritativeness and trust) comes from Google's Search Quality Rater Guidelines. Raters use it to evaluate results; their ratings do not change rankings directly, and Google describes E-E-A-T as a concept its systems try to reflect, not a score you can measure. Trust is the most important part, and the bar is higher for topics that can affect health, money, safety or civic life.

Signals you can check on the site itself:

- **Who is behind it:** a clear about page, the legal entity and address where the law requires one, working contact options, customer-service and returns information for shops.
- **Who wrote it:** bylines that link to author pages with relevant background; editorial, review and correction policies for publishers; dates of publication and real updates.
- **Where facts come from:** sources cited for claims and data, especially in health, finance and legal topics (`../../research-writing/GUIDE.md` for verified citations).
- **Safety:** HTTPS across the site, no mixed content, no malware or deceptive ads, no security issues reported.

Signals that live elsewhere, which you can research the way a rater would:

- What independent sources say: reviews on independent platforms, news coverage, professional bodies, complaints. Search for the brand plus "reviews" or "complaints" while excluding the site itself, and summarize what you find with links and dates.
- For local businesses, consistent name, address and phone number across the business profile, directories and the site.
- Unlinked mentions in news and trade press show reputation and are worth knowing about; there is no documented ranking effect to promise.

Never improve these by faking them: no invented authors or credentials, no bought reviews, no review gating, no paid mentions presented as independent (`../../legal-ready/references/honest-commerce.md`).

## Reporting authority honestly

- There is no single authority number. Describe the evidence: kinds of referring sites and their relevance, notable earned links and mentions, problems found, manual actions or none, reputation findings, each with source and date.
- Compare with peers only inside one data source and say which.
- Several patterns look suspicious and usually are not. Test the innocent explanation first:

| Pattern | Usually innocent when | Worth a closer look when |
|---|---|---|
| Sudden burst of new links | A launch, funding news, a viral post or press coverage explains it | The links come from unrelated, templated or low-quality sites with no editorial context |
| Many links from one IP range | The sites sit on a shared host, platform or CDN | They also share an owner, template, interlinking and thin content |
| High share of `nofollow` links | They come from news sites, forums and social platforms that mark links that way by policy | They appear next to paid placements without `sponsored` |
| Few links but strong demand for the brand | An established or offline business that rarely earns links | Thin links, no brand searches and no independent mentions |
| Young domain or private registration | A real new business with clear ownership on the site | Combined with keyword-anchor links and link growth out of line with traffic |

- If data needed for a judgment is missing (no access to Search Console, no link export), say the judgment is incomplete rather than estimating.

## Done when

- [ ] Link data comes from named sources with export dates; vendor scores are labeled as vendor estimates and not used as goals.
- [ ] The review groups referring domains by kind, with real pages sampled, and separates patterns the site created from background spam.
- [ ] Old URLs with external links are redirected; paid and affiliate outbound links carry `sponsored` or `nofollow`.
- [ ] Disavow, reconsideration requests and any removals were decided by the owner with the evidence shown.
- [ ] Manual actions and security issues were checked and reported; trust findings cite pages and independent sources with dates.
