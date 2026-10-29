# Search measurement: data sources, access and attribution

Read this when pulling or interpreting search data: Search Console and Bing Webmaster Tools, analytics, server and CDN logs, Core Web Vitals field data, AI referral traffic, and any claim that a change caused a rise or fall. Rank tracking, reports and alerts are in `rank-tracking-and-alerts.md`. Data analysis mechanics (joins, profiling, charts) are in `../../data-engineering/GUIDE.md`; statistics for tests are in `../../ml-engineering/references/statistical-inference.md`.

Every number in a search report needs four labels: the **source** (tool and property or view), the **date range** and time zone, the **filters and segments**, and its **status** (measured from that source, provided by the user, a vendor estimate, or an estimate of yours). A number without them cannot be checked or compared.

## What each source can and cannot tell you

| Source | Good for | Cannot tell you |
|---|---|---|
| Search Console Performance | Clicks, impressions, click-through rate and average position on Google, per query, page, country, device, search appearance and date | Sessions or conversions; queries hidden for privacy; complete rows for large sites through the UI |
| Search Console Pages (indexing) report and URL Inspection | Whether URLs are indexed and why not; Google-selected canonical; last crawl; rendered HTML in the live test | How pages rank |
| Search Console Crawl Stats, robots.txt report | Crawl volume, response codes, host problems, robots.txt fetches over 90 days | Per-URL crawl history (use logs) |
| Search Console Core Web Vitals report | Field data from Chrome users, grouped by similar URLs, mobile and desktop | Causes (use lab tools); pages without enough traffic |
| Search Console Links, Manual actions, Security issues | Google's sample of linking sites and pages; penalties and hacks | A complete link list |
| Bing Webmaster Tools | The same kinds of data for Bing (which also feeds other services), plus its own URL Inspection and backlink data | Google behavior |
| Analytics (GA4 or another tool) | Sessions, engagement and conversions by channel and landing page | Queries; visits blocked by consent choices or blockers |
| Server and CDN logs | Every request, including crawlers, with status and timing; ground truth for crawling | Rankings; anything about users beyond requests (and they contain personal data) |
| CrUX API, PageSpeed Insights | Field Core Web Vitals per URL or origin (28-day window, 75th percentile); lab diagnostics | Field data for low-traffic pages |
| A crawler you run | What the site serves: status, canonicals, titles, links, depth | What engines decided |
| Rank trackers and third-party SEO tools | Sampled positions; estimated volumes, traffic and "authority" scores | Your real traffic; Google's own metrics. Label their numbers as vendor estimates |

## Access without handling secrets

- Use read-only API scopes: the Search Console API with `https://www.googleapis.com/auth/webmasters.readonly`; the GA4 Data API with `https://www.googleapis.com/auth/analytics.readonly`; Bing Webmaster Tools' API key or OAuth; a Google Cloud API key for CrUX and PageSpeed Insights. OAuth mechanics, token storage and scope tables are in `../../integrations/references/oauth-and-tokens.md`.
- Keys and tokens are referenced by environment-variable name, set by the user through a guided script (`../../agent-safety/references/secrets.md`). Never paste them into the conversation, code or logs.
- Ask the owner for the least access that works: a restricted (read-only) Search Console user, a viewer role in analytics.
- Quotas change; check them before bulk pulls. At the time of writing, a Search Analytics request returns at most 25,000 rows (page with `startRow`), the API does not return every row for very large sites, and URL Inspection API calls are limited per property per day (about 2,000). For complete row-level data on a large site, the owner can enable Search Console's bulk export to BigQuery, which has storage and query costs.

```python
from googleapiclient.discovery import build   # google-api-python-client; credentials per oauth-and-tokens.md

sc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
rows, start = [], 0
while True:
    body = {"startDate": "2026-09-01", "endDate": "2026-09-28", "type": "web",
            "dimensions": ["page", "query"], "rowLimit": 25000, "startRow": start,
            "dataState": "final"}             # "all" adds fresh, still-changing data
    batch = sc.searchanalytics().query(siteUrl="sc-domain:example.com", body=body).execute().get("rows", [])
    rows += batch
    if len(batch) < 25000:
        break
    start += 25000
```

## Reading Search Console correctly

- **Time zone and delay.** Dates are Pacific Time. The last few days are preliminary and change; compare final data, or say that recent days are preliminary.
- **Retention.** 16 months. Export what you need for year-over-year comparisons before it disappears.
- **Privacy filtering.** Rare queries are not shown, so query rows add up to less than the page or site totals. Report totals from a query-less request.
- **Average position** is the average of the topmost position your site held in each impression. It moves when the mix of impressions changes: a page that starts appearing at position 40 for many new queries lowers the average while nothing got worse. Read it with impressions and clicks, never alone.
- **Property versus page aggregation.** By property, a query counts once even when several of your URLs appear; by page, each URL counts. Totals differ; do not mix them in one table.
- **AI features.** Clicks and impressions from AI Overviews and AI Mode are counted inside the Web search type and, as of 2025, cannot be filtered out separately. Discover and Google News have their own reports.
- **Clicks are not sessions.** Analytics counts sessions differently (consent, blockers, redirects, multiple tabs). Compare trends between the two, not absolute numbers.
- **Brand versus non-brand.** Split queries with a regular-expression filter (RE2 syntax) on brand names and common misspellings. Brand demand follows marketing and news, not search work.

## Analytics

- Organic search is a channel rule (source from a list of search engines with medium `organic`). Check the definition the property uses before comparing properties or tools.
- Consent banners, ad blockers and browser privacy features hide a share of visits that varies by audience and market, and changes when the banner changes. A drop that starts on the day the consent setup changed is a measurement change.
- Report landing-page performance (sessions, engagement, conversions or key events) for organic entrances, segmented by device and country, with the property's time zone.
- Analytics and consent rules are a legal matter too (`../../legal-ready/references/policies-and-consent.md`).

## Server and CDN logs

Logs answer what crawlers actually requested: which URL patterns, how often, with which status codes, and how fast. They are the only way to see crawler activity on URLs Search Console never reports, and the only way to see most AI crawlers at all.

```python
import re, sys
from collections import Counter

LINE = re.compile(r'\S+ \S+ \S+ \[[^\]]+\] "(?:\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
BOTS = ["Googlebot", "bingbot", "OAI-SearchBot", "GPTBot", "ChatGPT-User", "ClaudeBot",
        "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User", "CCBot"]   # check current names
counts = Counter()
for line in sys.stdin:                       # combined log format; adapt the pattern to your server
    m = LINE.match(line)
    if not m:
        continue
    path, status, agent = m.groups()
    bot = next((b for b in BOTS if b.lower() in agent.lower()), None)
    if bot:
        section = "/" + path.lstrip("/").split("/", 1)[0].split("?", 1)[0]
        counts[(bot, section, status)] += 1
for (bot, section, status), n in sorted(counts.items(), key=lambda kv: -kv[1])[:50]:
    print(f"{n:8d}  {bot:18s} {status}  {section}")
```

- These counts are **claimed** user agents. Anyone can send a crawler's name. Verify important ones before drawing conclusions: for Google, a reverse DNS lookup of the IP should end in `googlebot.com`, `google.com` or `googleusercontent.com`, and the forward lookup of that name must return the same IP; or match against the IP range files Google publishes for its crawlers and fetchers. Bing's crawler resolves to `search.msn.com`. Several AI vendors publish IP ranges for their crawlers; check their documentation.
- Logs contain IP addresses and URLs that may include personal data. Analyze an extract with the minimum fields, keep it out of the repository, and follow the site's retention rules.
- CDNs often hold the logs that matter (cached responses never reach the origin). Ask the owner for an export instead of requesting broad CDN access.

## Core Web Vitals in search

Thresholds, causes and fixes are in `../../engineering-practices/references/performance.md` (LCP, INP and CLS; INP replaced FID as a Core Web Vital in March 2024). For search work, add:

- Search engines use field data, which covers a rolling 28 days. A fix shows fully in the CWV report and CrUX only about four weeks after it reaches users; Search Console's "Validate fix" runs over that period.
- The report groups similar URLs; a failing group points to a template, not to one page.
- Good Core Web Vitals do not outrank more relevant content; they matter most between results of similar quality. Fix them for users first, and do not promise ranking gains.

## AI referral traffic

- In analytics, AI assistants appear as referral sources (at the time of writing, for example `chatgpt.com`, `perplexity.ai`, `gemini.google.com`, `copilot.microsoft.com`, `claude.ai`). Build a channel or segment from the sources that actually appear in the property, for example the regular expression `^(chatgpt\.com|perplexity\.ai|gemini\.google\.com|copilot\.microsoft\.com|claude\.ai)$` on session source, placed above the general referral rule in a custom channel group. Review the list every few months.
- It undercounts. Visits from apps, copied links and some assistants arrive without a referrer and land in direct traffic. Some assistants add `utm_source` parameters to links; check for those too. Clicks from Google's AI Overviews and AI Mode arrive as Google organic traffic.
- Volumes are usually small, so conversion rates swing widely. Report counts with their date range and compare with organic over the same window, saying how small the sample is.
- Whether an assistant mentions or cites a site without a click cannot be measured from analytics. Tools that sample assistant answers for a fixed set of prompts exist, but answers vary run to run, by location and by account, so treat their figures as samples: repeat prompts, report rates over a period, and label the source. What helps pages appear in AI answers, and a log for answer samples, are in `ai-answer-engines.md`.

## Comparing periods and attributing change

Search data moves for many reasons at once: seasonality, demand, competitors, engine updates, tracking changes and your own releases. Before saying a change caused a result:

1. **Compare like with like:** equal-length windows aligned on weekdays; year-over-year for seasonal businesses; the same filters, search type, country and device.
2. **Annotate the timeline:** deploys, migrations, content releases, consent or tracking changes, outages, campaigns, and Google's confirmed ranking updates (Google Search Status Dashboard).
3. **Segment:** brand and non-brand, section or template (URL folder), country, device, and query groups. A total that hides one falling section explains nothing.
4. **Use a control:** comparable pages, sections or markets that did not change. Report the change relative to the control, not the raw before and after.
5. **Fix the window before the change** and wait for the engine to recrawl the changed pages (URL Inspection shows the last crawl date). Judging a title test after three days measures noise.
6. **Change one thing at a time** per page group, or label the batch. For template-level tests on many similar pages, assign pages to test and control groups at random and compare their trends with a proper statistical test (`../../ml-engineering/references/statistical-inference.md`).
7. **Say how sure you are.** Correlation in the same period is not causation; a plausible mechanism plus a control plus a consistent segment pattern is evidence; anything less is a hypothesis.

## Done when

- [ ] Every figure carries its source, property or view, date range and time zone, filters, and status label.
- [ ] Access used read-only scopes and keys by name; no secret entered the conversation.
- [ ] Comparisons use like-for-like windows, segments, a timeline of known events and a control where a cause is claimed.
- [ ] Crawler conclusions rest on verified bots in logs, not claimed user agents.
- [ ] Limits are stated: privacy-filtered queries, preliminary days, analytics undercounting, AI referrals without referrers.
