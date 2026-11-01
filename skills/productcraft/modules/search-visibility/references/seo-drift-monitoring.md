# Drift and regression monitoring after deploys

Read this when a release, a CMS change, a theme or plugin update, a dependency upgrade or a configuration change could have changed what search engines see, when the user asks "did the deploy break anything for search", or when setting up checks that catch such breakage before traffic shows it. Point-in-time checks of one build are `scripts/seo_check.py` (`../GUIDE.md`, "Offline checker"); alerts on traffic anomalies and the invariant list are in `rank-tracking-and-alerts.md`; migrations that move URLs on purpose are in `site-migrations.md`.

A point-in-time check answers "is this build valid?". A drift check answers "what changed since the last good build, and was it meant?". Most search regressions are valid HTML: a template now emits `noindex`, a canonical points at the home page, a robots rule grew a wildcard, a component dropped the JSON-LD. Each one passes a validator and still removes pages from search. Comparing against a known-good snapshot catches them on the day they ship.

## What to snapshot

| Layer | Fields | Why they drift |
|---|---|---|
| Indexing controls | `meta robots` (and agent-specific tags), canonical, `X-Robots-Tag` header, status code | Environment flags, template inheritance, framework upgrades that change defaults |
| Crawl rules | `robots.txt` rules per group, sitemap lines, sitemap URL sets | Copied staging files, CMS plugins that rewrite the file, a generator that drops a section |
| Page identity | `<title>`, meta description, main heading, `html lang` | Component refactors, empty data fields, a fallback string reaching production |
| Alternates | `hreflang` sets | Locale config changes, a market added or removed |
| Structured data | Types present, whether blocks parse, a hash of the content | Removed scripts, data fields renamed upstream, hydration-only rendering |
| Previews | Open Graph title, image, URL | Asset pipeline changes, image CDN paths |
| Content and links | Visible word count and a text hash, how many pages link to each page | Content loaded only on the client, navigation or related-links modules removed |
| Live behavior | Status codes, redirects and their targets, response headers, rendered HTML | Server, CDN and edge rules that the build folder never shows |

Snapshot the build output in CI, and the live site after deploy. The build snapshot is cheap and runs before anything ships; the live snapshot catches what servers, CDNs and edge functions change.

## When to take snapshots

- **Before and after every production deploy** that touches templates, routing, rendering, head tags, `robots.txt`, sitemaps or CDN rules. Store the last known-good snapshot as the baseline.
- **Before risky work** (a framework upgrade, a theme change, a migration rehearsal) so there is something to compare against.
- **On a schedule** for the live site (daily or weekly, by size and change rate), because CMS editors, plugins and third-party scripts change pages without a deploy.
- **When traffic drops,** compare the current state with the snapshot from before the drop. A dated history of snapshots turns "when did the canonical change?" into a lookup.

Keep snapshots with the project's search records (`search-project-state.md`) or as CI artifacts, named by date and release. They hold no secrets, but they can be large; keep them out of the repository if they are.

## The offline drift script

`scripts/seo_drift.py` snapshots a folder of built pages, its `robots.txt` and its XML sitemaps, and diffs two snapshots (or a snapshot and a build folder). Standard library only, read-only, no network, deterministic output.

```bash
# After the last good release: store a baseline
python3 <productcraft>/modules/search-visibility/scripts/seo_drift.py snapshot dist/ \
  --base-url https://www.example.com --label "release 2026-10-28" --out baseline.json

# In CI for the next build: compare and fail on errors
python3 <productcraft>/modules/search-visibility/scripts/seo_drift.py diff baseline.json dist/ \
  --base-url https://www.example.com --accept docs/search/approved-changes.txt

python3 <productcraft>/modules/search-visibility/scripts/seo_drift.py --list-rules
```

- Use the same `--base-url`, `--agent`, `--clean-urls` and `--exclude` for both sides; the diff warns (`OPTIONS_DIFFER`) when they differ, because differences may then be artifacts.
- **Errors** are changes that usually remove pages from search: an indexable page missing, `noindex` added, a self-canonical page now canonicalized elsewhere, a page `robots.txt` now blocks, the whole site disallowed, JSON-LD that stopped parsing, a title gone, all sitemaps gone.
- **Warnings** need a look: `noindex` removed (the page is now public), canonicals changed or removed, `hreflang` alternates removed or retargeted, structured data types dropped, Open Graph removed, a page that lost every internal link, visible text that shrank by more than `--text-drop` (default 0.5, a review trigger to tune, not a search-engine number), `robots.txt` rules changed, URLs leaving the sitemaps.
- **Info** is awareness: titles, descriptions, headings and text that changed, pages added.
- `--accept FILE` lists changes the owner approved, one `RULE_ID location-glob` per line (`NOINDEX_ADDED /drafts/*`, `PAGE_REMOVED /promo/spring-2026`). Accepted findings are counted but do not fail the run. Write the approval date and who approved in a comment, and prune the file after each release so old approvals do not hide new regressions.
- Exit code 0 means nothing at or above `--fail-on` (default `error`; `--strict` means `warn`), 1 means at least one finding, 2 means a usage or input error.
- It sees files as built. It cannot see status codes, redirects, response headers or what JavaScript adds; for those, compare live crawls (below).

## Live-site drift

For the live layer, crawl the production site with a crawler the user is entitled to run (their own site, at a polite rate, identified user agent) and keep its export per run. Compare runs on the same fields: status, final URL after redirects, canonical, `meta robots`, `X-Robots-Tag`, title, `hreflang`, structured data types. Add checks the build cannot cover:

- the home page, key templates and a sample per section return 200 with the production `robots.txt`;
- redirects from the migration map still return one hop to the expected target (`site-migrations.md` has a script);
- `X-Robots-Tag` headers on HTML responses did not appear;
- the rendered DOM still carries the content and links (URL Inspection's live test for a sample, or a headless browser per `../../builder-tools/references/playwright-web-testing.md`).

Search Console confirms the effect later, not the cause: Pages report reasons per sitemap, the robots.txt report, rich result reports and Crawl Stats (`search-measurement.md`).

## Triage a drift report

1. **Read errors first, grouped by rule.** One rule firing on hundreds of pages points at a template or configuration, not at content; find the commit that touched it.
2. **Decide intended or not with the change owner.** If intended, add it to the accept file with the approval. If not, fix the template and rebuild; do not patch pages one by one.
3. **For changes already live,** treat errors as incidents: revert or fix forward, then verify on the live site and record the incident window in the change log, because Search Console data for that window will look odd later.
4. **Warnings get an owner and a date.** Removed `hreflang`, dropped structured data types or orphaned pages rarely show in traffic for weeks, which is why they are easy to forget.
5. **Do not chase info noise.** Title and text changes are normal. Review them in batches when a section's clicks move (`content-refresh-and-consolidation.md`).

## Pitfalls

| Pitfall | Fix |
|---|---|
| Baseline taken from a broken build | Take the baseline from the release the owner considers good, and re-baseline only after a reviewed diff |
| Snapshots with different options or excludes | Keep the options in the CI script; the diff flags mismatches |
| Accept file grows forever | Prune it each release; approvals are per change, not permanent |
| Build-only checks on a site where the CDN rewrites headers or redirects | Add the live crawl comparison |
| Diffing a staging build that is meant to be `noindex` against production | Snapshot the production build configuration, or compare like with like |
| Treating every changed title as a regression | Titles change on purpose; the error class is reserved for changes that remove pages from search |

## Done when

- [ ] A known-good baseline exists for the build and, where relevant, the live site, with date, release and options recorded.
- [ ] Every production deploy runs `seo_drift.py diff` against the baseline (and `seo_check.py` on the build), failing on errors.
- [ ] Approved changes are in an accept file with who approved them and when, pruned each release.
- [ ] Live crawls cover status codes, redirects, headers and rendering on a schedule, with each run's export kept.
- [ ] Every error found was fixed or explicitly approved, and its window logged in the project's change log.
