# Rank tracking, reporting and alerts

Read this when setting up or reading rank tracking, writing a recurring search report, or configuring alerts for search problems. Where the underlying numbers come from, and how to attribute change, is in `search-measurement.md`.

## A ranking is a sample, not a fact

The same query returns different results for different people. Position depends on location (down to the city for local intent), device, language, signed-in history, the moment, and which result features (ads, maps, images, video, "People also ask", AI Overviews) are on the page. So:

- A rank tracker reports what one simulated searcher saw from one location and device at one time. Two vendors, or the same vendor on two days, can disagree by a few positions with nothing changed.
- "Position 1" can sit below an AI Overview, ads and a map pack. Some trackers report pixel depth or feature presence too; use them when click potential matters.
- Search Console's average position is a different measure: the topmost position your site held, averaged over real impressions. It will not match a tracker and should not be expected to.
- Third-party "keyword difficulty", "search volume" and "visibility" figures are vendor models. Use them to compare options within one tool, label them as estimates, and never report them as Google data.

## Setting up tracking

- **Keyword set:** start from real Search Console queries (with impressions) plus the queries the business targets, grouped by intent, section or template, and brand versus non-brand. A few hundred well-chosen queries beat thousands of random ones.
- **Fixed conditions:** one search engine, country, language, device and, for local businesses, the locations that matter. Changing them breaks the series.
- **Cadence:** daily for a small set of critical queries during launches or migrations; weekly is enough for trends.
- **Record the ranking URL,** not only the position. Two URLs of yours alternating for one query is a sign of overlap (cannibalization) worth a content decision; a ranking URL that changes after a release points at canonicals, redirects or internal links.
- **Record result features** present and whether you hold them.
- **Use a licensed data provider or Search Console.** Scraping Google results directly breaks Google's terms of service and gets blocked; do not build or run such scrapers.

## Reading changes

| Pattern | Likely cause | Check |
|---|---|---|
| Small daily moves on a few queries | Normal volatility and sampling | Weekly trend; ignore |
| Many queries across the site fall on the same day | Technical problem or an engine update | Status codes, `robots.txt`, `noindex`, canonicals and rendering on key templates; Google Search Status Dashboard |
| One URL falls for all its queries | Page-level change | Status, `noindex`, canonical, redirect, content or title changes, internal links removed (diff the page with an earlier crawl) |
| One section or template falls | Template or internal-link change | Template diff; `scripts/seo_check.py` on the build; crawl of that section |
| Gradual decline over months on one topic | Competitors improved, content aged, intent shifted | Current results for those queries; content review (`content-quality-review.md`, `content-refresh-and-consolidation.md`) |
| Tracker shows a fall, Search Console clicks are flat | Sampling, location or feature change, or tracker error | Search Console for the same query, country and device |

Report position movement as distributions (queries in positions 1 to 3, 4 to 10, 11 to 20, beyond) and as clicks and impressions from Search Console, not as a list of single-query moves.

## Writing the report

A useful search report answers four questions in order, with sources on every figure:

1. **What changed?** Clicks, impressions, indexed pages per sitemap, conversions from organic landing pages, Core Web Vitals per template: this period against the comparison period and against last year, in a small table with source and dates on each row.
2. **Why do we think so?** The timeline of known events, the segments where the change sits, the control comparison, and the evidence level (confirmed, likely, hypothesis).
3. **What did we do and what did it show?** Each change shipped, its verification (`../GUIDE.md`, verify table) and its measured effect so far, or "too early, window ends on <date>".
4. **What next?** Prioritized actions with an owner, the expected effect stated as a hypothesis, and the date of the next check.

Leave out vanity numbers: totals of tracked keywords, vendor authority scores as goals, "visibility" indices without a definition. Say which data was unavailable instead of filling gaps with estimates.

## Alerts

Two kinds of alert catch most search problems. Use both.

**Invariants: deterministic checks that should never fail.** They catch the causes of drops before traffic shows them, run cheaply in CI or a scheduled job, and rarely false-alarm:

- production `robots.txt` changed (alert on any diff) or contains `Disallow: /` for `*` or a major crawler;
- `noindex` present on key templates or URLs (home, categories, top pages);
- canonical host, scheme or path pattern changed on key templates;
- sitemaps return a non-200 status, fail to parse, or the URL count changes by more than an agreed share;
- 5xx or 404 rate for search-crawler requests above a threshold (from logs);
- key redirects no longer return one hop to the expected target;
- structured data stops parsing on a template; certificate expiry approaching.

Run `scripts/seo_check.py` on every production build and fail the build on errors; snapshot `robots.txt` and the sitemap index after each deploy and diff them.

**Anomalies: traffic outside its normal range.** Daily search data is noisy and weekly-seasonal, so compare like with like and use robust statistics instead of a fixed percentage:

```python
from statistics import median

def weekly_anomaly(history, current, k=3.0, min_weeks=8):
    """history: weekly totals (for example Search Console clicks) for the same
    segment, oldest first; current: the latest complete week.
    Returns a message when current falls below median - k * MAD, else None."""
    if len(history) < min_weeks:
        return None                                   # not enough history to judge
    med = median(history)
    mad = median(abs(x - med) for x in history) or 1.0
    if current < med - k * mad:
        return f"weekly value {current:.0f} is below the expected range (median {med:.0f}, MAD {mad:.0f})"
    return None
```

- Alert per segment that matters (non-brand clicks per key section, organic conversions), not only on the site total.
- Use complete weeks of final data; preliminary days create false alarms.
- Suppress or annotate during known events (migrations, holidays, campaigns) and re-baseline after structural changes.
- Every alert names an owner and links a short runbook: what to check first (the invariant list above), where the data lives, and who can approve a fix.
- Delivering alerts to chat or email uses the team's existing channels; posting to them is a write other people see, so set it up with the owner (`../../integrations/GUIDE.md`).

## Done when

- [ ] Tracking conditions (engine, country, language, device, locations, cadence) are fixed and written down; ranking URLs and result features are recorded; data comes from a licensed provider or Search Console.
- [ ] Reports state source, date range and evidence level for every figure, and separate observed changes from explanations.
- [ ] Invariant checks run on every production build or on a schedule; anomaly alerts use history-based thresholds per key segment; each alert has an owner and runbook.
