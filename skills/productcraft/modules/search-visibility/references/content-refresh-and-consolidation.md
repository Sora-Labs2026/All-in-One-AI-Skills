# Refreshing, consolidating and retiring content

Read this when a page has lost traffic or rankings, content is out of date, several pages cover the same need, or the user wants to prune or merge a section. Redirect mechanics and status codes are in `crawl-and-index-controls.md`, moves at scale in `site-migrations.md`; this file decides what should happen to the content and how to tell whether it worked.

## Find candidates

Two routes, both useful:

- **Scheduled review** by content type: pages with prices, versions, statistics, rules or "best of" lists go stale fastest and need a review date in the project state. Evergreen explanations need less.
- **Data signals** from Search Console and analytics, read like for like:

```python
# Compare two Search Console page exports of equal length (for example the last 28 days and the same
# 28 days a year earlier). First column is the page URL; Clicks, Impressions and Position columns as exported.
import csv, sys

def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    head = rows[0]; col = {name: head.index(name) for name in ("Clicks", "Impressions", "Position")}
    return {r[0]: {k: float(r[i].replace(",", "")) for k, i in col.items()} for r in rows[1:] if r}

now, before = load(sys.argv[1]), load(sys.argv[2])
for page in sorted(before, key=lambda p: now.get(p, {"Clicks": 0})["Clicks"] - before[p]["Clicks"])[:30]:
    b, n = before[page], now.get(page)
    if b["Clicks"] < 20: continue                      # too few clicks to read a change; tune per site
    if n is None: print(f"{-b['Clicks']:+7.0f} clicks  not in the current export  {page}"); continue
    ctr_b, ctr_n = b["Clicks"] / max(b["Impressions"], 1), n["Clicks"] / max(n["Impressions"], 1)
    print(f"{n['Clicks'] - b['Clicks']:+7.0f} clicks  impressions {n['Impressions'] / max(b['Impressions'], 1) - 1:+5.0%}"
          f"  CTR {ctr_b:5.1%}->{ctr_n:5.1%}  position {b['Position']:4.1f}->{n['Position']:4.1f}  {page}")
```

- Export both periods with the same filters (search type, country, device). Prefer year over year for seasonal topics; a comparison with the previous period confuses seasonality with decay.
- Small numbers are noise. Set the click floor for the site, and read pages with few clicks as a group (a section or template), not one by one.
- Exports are capped at 1,000 rows in the UI; use the API or the bulk export for larger sites (`../../integrations/references/oauth-and-tokens.md` for access, keys by name per `../../agent-safety/references/secrets.md`). Analysis of large exports: `../../data-engineering/GUIDE.md`.

## Diagnose before rewriting

A drop has a shape. Read it before touching the content:

| Shape in the data | Likely causes | Check first |
|---|---|---|
| Clicks and impressions fall together, position holds | Less demand (seasonal, market), or the query mix shifted | Trends and year-over-year data for the query group |
| Impressions and position fall | Lost relevance or quality against competitors, a ranking update, or a technical problem | URL Inspection (indexed? canonical chosen by Google?), recent deploys, Google's Search Status Dashboard for update dates, the current results page |
| Impressions hold, CTR falls, position holds | The results page changed: AI answer, featured snippet lost, ads, a new feature; or the title is being rewritten | A fresh results snapshot (`serp-analysis.md`); the title shown versus the page title |
| Page drops out entirely | Not indexed any more: `noindex`, blocked by `robots.txt`, redirect, canonical to another URL, server errors, removal | URL Inspection and the Page indexing report |
| Analytics falls but Search Console does not | Tracking or consent change, not search | Tag deployment history, consent banner changes |
| Many pages of one template fall at once | Template or technical change, or a quality reassessment of that page type | Diff of the template; a sample of pages through `content-quality-review.md` |

Check technical causes and measurement first; they are faster to confirm and fix. Name the cause you found, the evidence, and what you ruled out. If no cause is confirmed, say so.

## Choose the action

| Situation | Action |
|---|---|
| Same need, still a good fit, facts or coverage dated | **Refresh in place** at the same URL |
| Same URL has links and history, but the need or intent changed | **Rewrite** for the current intent at the same URL, if the topic is still the same; otherwise a new page and a redirect only where the old need maps to it |
| Several pages compete for one need, none clearly strongest | **Consolidate:** merge the useful parts into the best URL, redirect the others to it |
| Useful to visitors but not to searchers (internal notices, thin tag pages) | Keep, and exclude from the index with `noindex` if it adds nothing in search |
| No value to anyone, no equivalent page | **Retire** with 404 or 410 |
| Obsolete, but a successor exists | Redirect (301 or 308) to the successor that serves the same need |

- Redirect only to a page that genuinely replaces the old one. Mass redirects to the homepage or a category are treated as soft 404s and frustrate users.
- After merging or redirecting, update internal links to point at the final URL, and update the target map.
- Deleting or noindexing large amounts of content to look "fresh" is a search-first behavior Google's guidance warns against. Prune because pages fail readers, and keep a list of what was removed and where it went.

## Refresh properly

- Re-check every fact, price, version, screenshot, step and statistic against current sources; update the research log.
- Add what the page now lacks against current results and reader questions: missing steps, new options, first-hand testing, clearer answers.
- Remove what is wrong or no longer useful, rather than appending an "update" box to stale text.
- Keep the URL. Keep what still works; heavy rewrites of good sections can lose what readers valued.
- Run `content-quality-review.md` on the refreshed page.

### Dates, honestly

- Show a visible date that matches what happened: "Published" and, for meaningful revisions, "Updated" with the date. Google's byline-date guidance asks for a clear visible date and matching `datePublished` and `dateModified` in structured data.
- Change the updated date only when the content changed meaningfully. Changing dates without substantive change, to look fresh, is one of the behaviors Google lists as made for search engines rather than people.
- Update the sitemap `lastmod` only for significant changes. Google uses `lastmod` when it is consistently accurate and ignores `changefreq` and `priority`.
- A short change note on pages where readers depend on currency (pricing, regulations, software versions) builds trust.

## After publishing

- Request recrawling sparingly: URL Inspection's request indexing has a quota and is a request, not a guarantee; an updated sitemap does the same at scale. IndexNow notifies Bing and other participating engines; Google does not use it.
- Record the change in the project state change log: date, URL, what changed, why.

## Did it work?

- Fix the window before looking: compare equal-length periods before and after, skipping the first days while the page is recrawled, and wait at least several weeks for ranking effects.
- Use a control: similar pages you did not change, from the same section, read over the same windows. Report the change relative to the control, not the raw change.
- Account for seasonality (year over year where possible) and for ranking updates in the window.
- One page is noisy. Conclusions are stronger across a batch of refreshed pages against a batch of unchanged ones.
- Report the source and filters of every number, and say plainly when the result is inconclusive.

## Checks (done when)

- [ ] Candidates came from scheduled review or like-for-like data, with filters and periods stated.
- [ ] The cause of each drop was diagnosed, technical and measurement causes checked first, with evidence.
- [ ] The chosen action (refresh, rewrite, consolidate, noindex, retire, redirect) fits the table, and redirects go only to true equivalents.
- [ ] Refreshed content is re-verified, dates reflect real changes, and structured data and `lastmod` match.
- [ ] The change is logged, and the effect is read against a control over a fixed window.
