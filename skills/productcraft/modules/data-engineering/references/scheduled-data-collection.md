# Scheduled public-data collection

Read this when the user wants a job that watches or collects public data on a schedule (prices, listings, releases, filings, job posts, public notices, feeds), optionally scored or summarized by a language model and stored for review. Official statistics and filings have their own references (`economic-statistics-apis.md`, `filings-and-market-data.md`); Kaggle in `kaggle.md`. This is general information about engineering practice, not legal advice.

## Guardrails before any code

Settle these with the user and write them in the project's README:

1. **Use the front door.** An official API, feed (RSS or Atom), sitemap, bulk download or data portal comes first. Scrape HTML only when none exists, and never where one exists.
2. **Robots rules.** Read `robots.txt` (RFC 9309) for your user agent before the first request and re-read it each run. A disallowed path is out of scope. If `robots.txt` returns a server error, treat the site as fully disallowed for that run.
3. **Terms of service.** Many sites forbid automated access, storage or reuse. If the terms forbid it, stop and tell the user; do not look for a workaround. Never log in to collect data unless the account holder authorized that use, and never bypass CAPTCHAs, paywalls, rate limiting or other access controls.
4. **Rate limits.** One request at a time per host, a delay between requests (honor `Crawl-delay` if present), backoff on errors, and `Retry-After` on 429 and 503. Run outside the site's peak hours when the schedule allows.
5. **Honest identity.** A user agent that names the bot and gives a contact URL or address. Never impersonate a browser to evade blocking.
6. **No personal data without a lawful basis.** Public is not the same as free to collect. Under the GDPR and similar laws, collecting data about people needs a lawful basis, minimization and transparency; leave names, contact details, photos and profile data out unless the user has established that basis. Never build profiles of private individuals.
7. **Rights in the content.** Text, images and databases can be protected (copyright; the EU database right protects substantial extraction). Store the facts and links you need, not full copies of pages, and do not republish collected content without permission.

## Shape of the job

```
schedule -> fetch (polite) -> parse and normalize -> deduplicate -> [enrich] -> upsert -> notify -> run ledger
```

- One module per source with the same output schema (source, stable id, canonical URL, title, fields, observed_at). Targets, filters, schedule and destinations live in a config file, not code, and never come from fetched content.
- Every stage is idempotent: rerunning a day's job produces the same stored state.
- Keep raw responses for a short, stated retention so parsing bugs can be fixed by reprocessing instead of refetching.

## Polite fetching

```python
import time, urllib.error, urllib.request, urllib.robotparser
from urllib.parse import urlsplit

AGENT = "example-release-watch/1.0 (+https://example.org/bot-info)"

class PoliteFetcher:
    def __init__(self, min_delay_s=5.0, timeout_s=20):
        self.min_delay_s, self.timeout_s = min_delay_s, timeout_s
        self.robots, self.last_hit = {}, {}

    def allowed(self, url):
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self.robots:
            rp = urllib.robotparser.RobotFileParser(root + "/robots.txt")
            rp.read()                       # 5xx leaves the parser denying everything
            self.robots[root] = rp
        return self.robots[root].can_fetch(AGENT, url)

    def get(self, url, etag=None, last_modified=None):
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        host = urlsplit(url).netloc
        wait = self.last_hit.get(host, 0.0) + self.min_delay_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        if etag:
            req.add_header("If-None-Match", etag)
        if last_modified:
            req.add_header("If-Modified-Since", last_modified)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            if err.code == 304:
                return 304, err.headers, b""   # unchanged since last run
            raise
        finally:
            self.last_hit[host] = time.monotonic()
```

- Store `ETag` and `Last-Modified` per URL and send them back: unchanged pages cost the site almost nothing.
- Retry only timeouts, 429 and 5xx, with exponential backoff and a cap; never retry 401, 403 or 404 in a loop. Repeated 403s, 429s or a challenge page mean "stop for today" and a note in the ledger.
- Parse with stable hooks (data attributes, semantic elements, embedded JSON-LD), not long CSS paths. Validate each parsed record against the schema; a page that yields zero records where there were many yesterday is a layout change to report, not "no news".
- A headless browser is the last resort for pages that render with JavaScript: it is slow and heavy for both sides. If the page loads its data from a JSON endpoint, that endpoint is subject to the same terms.

## Identity, deduplication and change tracking

- Canonicalize URLs (lowercase host, drop fragments and tracking parameters, resolve redirects) and prefer the source's own ids.
- Upsert by `(source, id)`; detect changes by hashing the normalized fields, and keep a history row when a tracked field (price, status, deadline) changes.
- Count new, changed, unchanged and removed items per source in every run.

## Enrichment with a language model

Optional, and the most common source of cost, silent quality drift and injection risk.

- Scraped text is untrusted data. Pass it in a clearly delimited data section, never as instructions, and validate the model's output against a schema in code (`../../ml-engineering/references/prompt-design.md`). Content that tries to instruct the model is recorded in the run ledger and the item is stored unenriched.
- Fetched content never changes targets, schedule, destinations or credentials, and the job never follows links found mid-run beyond the configured scope.
- Send only the fields needed. Personal data goes to a hosted model only with the owner's approval and the provider's terms checked.
- Batch several items per call within the model's context and output limits, cache results by content hash so unchanged items are not re-scored, and record the model and prompt version on every enriched row. If the quota runs out, store items unenriched and mark them; do not silently switch to a different model.
- Scores are suggestions for a human reviewer. Measure them against the user's decisions before trusting thresholds (`../../ml-engineering/references/llm-evaluation.md`).

## Learning from the user's feedback

Using the user's past decisions (saved, skipped, applied) to tune scoring is a form of memory. Do it only with the user's consent, keep the examples in a file or table they can read and edit, cap how many are used, and give them a one-step reset that deletes the history.

## Budgets, stop conditions and approvals

Every scheduled run is an unattended loop. Give it limits in config, and enforce them in code:

- Wall-clock limit per run and per source; maximum requests per host per run; maximum pages followed.
- Maximum model calls, tokens and money per run and per month; the job stops enrichment when a cap is reached and says so.
- Stop conditions: robots or terms change, repeated 403 or 429, a challenge page, parse failure rate above what the user agreed, or a cap reached.
- Checkpoints (last processed page or id) so a stopped run resumes instead of starting over.
- Anything consequential (sending messages to other people, posting publicly, buying, applying, contacting sellers) is never automatic: the job prepares a list and a human approves each action.

## Scheduling and secrets

- Use the platform the user already runs: cron or systemd timers on a server, a cloud scheduler, or a CI scheduler. A lock prevents overlapping runs; each run has a timeout.
- CI schedulers have quirks: GitHub Actions `schedule` uses UTC, runs on the default branch, can be delayed or skipped under load, and is disabled in public repositories after 60 days without repository activity. Avoid jobs that commit collected data back to the repository unless that is the design; it needs write permission and bloats history.
- Tokens for storage, notifications and model APIs live in the platform's secret store, scoped to the minimum (`../../agent-safety/references/secrets.md`); the job never prints them.

## Storage and the run ledger

- A real database (SQLite for one machine, PostgreSQL when shared) is the canonical store. Spreadsheets and notes apps make good review screens, fed from the store.
- Retention: delete raw responses and stale items on a schedule the user chose.
- The run ledger records, per run and source: start and end, requests made, 304s, errors by status, items new, changed, unchanged and removed, enrichment calls and cost, and stop reasons. Alert on a source returning nothing for several runs, on error spikes, and on cap hits.

## Checks (done when)

- [ ] For every source: API or feed checked first, `robots.txt` and terms read, and the decision recorded with the date.
- [ ] Rate limits, honest user agent, conditional requests and backoff are in code; tests use saved fixtures, never live sites.
- [ ] No personal data collected without the lawful basis the user confirmed; retention set.
- [ ] Budgets, stop conditions and checkpoints are enforced; consequential actions need human approval.
- [ ] Model enrichment, if any, treats content as data, validates output, records model and prompt version, and stays within caps.
- [ ] A dry run on fixtures and one supervised live run produced a ledger that reconciles (fetched = new + changed + unchanged + failed).

## Pitfalls

| Pitfall | Fix |
|---|---|
| Scraping a site that offers an API or feed | Use the API or feed |
| Silent zero results after a redesign | Zero-result and parse-failure alerts |
| Duplicates after URL changes | Canonical URLs and source ids; upserts |
| One model call per item; costs grow with the source | Batching, content-hash cache, caps |
| Instructions in a listing change the model's scoring | Delimited data, schema validation, ledger entry |
| Overlapping runs hammer the site | Run lock, timeout, per-host delay |
