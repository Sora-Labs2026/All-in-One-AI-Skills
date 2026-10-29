# Site migrations

Read this before any change that moves URLs at scale: a new domain, HTTP to HTTPS, merging hosts or subdomains, a new URL structure, a CMS or framework replatform, or a redesign that changes templates on many pages. A migration is the change most likely to cost a site search traffic for months, and almost every loss comes from something that could have been checked before launch.

The owner decides whether and when to migrate, signs off the redirect map, and holds the rollback decision. The agent prepares the inventory, the map, the checks and the exact commands. Production DNS, redirects, `robots.txt`, Search Console settings and the Change of Address tool are changed only with the owner's explicit go-ahead (`../GUIDE.md`).

## Know the type and its risk

| Change | What moves | Main risks |
|---|---|---|
| HTTP to HTTPS, same URLs | Protocol only | Mixed content; redirects missing on some paths; canonicals and sitemaps still on `http` |
| Domain change | Every URL | Signals take time to transfer; missed redirects; old domain lapsing |
| Subdomain into subfolder (or the reverse), merging sites | Sections | Duplicates during the overlap; conflicting canonicals; lost `hreflang` sets |
| New URL structure | Paths | Incomplete redirect map; chains with older redirects; internal links left on old paths |
| Replatform (CMS, framework, rendering mode) | Templates, often URLs | Content or links that now need JavaScript; changed titles, headings, canonicals, structured data; slower pages |
| Content pruning or consolidation | Some URLs disappear | Redirects to irrelevant pages (soft 404s); losing pages that brought traffic or links |

Do one kind of change at a time where you can. A domain move plus new URLs plus a redesign in one release makes any drop impossible to attribute and hard to roll back.

## Before launch

**1. Inventory every URL that matters**, from several sources, because each misses some:

- a full crawl of the current site (URL, status, canonical, title, `meta robots`, depth);
- all XML sitemaps;
- Search Console Performance export of pages with clicks or impressions over the full 16 months, per property;
- analytics landing pages with organic entrances;
- server logs, which show URLs crawlers and users still request, including old ones;
- backlink exports (Search Console Links plus any third-party tool), which show URLs other sites link to.

Merge them into one list, normalize (scheme, host, case, trailing slash, parameters), and mark each URL's value: traffic, external links, conversions.

**2. Freeze a baseline** with sources and dates: indexed counts per sitemap, clicks and impressions per section and per top page (Search Console), organic sessions and conversions per landing page (analytics), Core Web Vitals per template (Search Console CWV report and CrUX), structured data per template, and current redirect rules. Store it in the repository or the project folder (`search-project-state.md`), not only in a dashboard that keeps 16 months.

**3. Write the redirect map** as data, reviewed like code:

```csv
old_url,new_url,status,reason
https://old.example.com/shoes/trail-runner,https://www.example.com/running/trail-runner,301,structure
https://old.example.com/blog/2019/fit-guide,https://www.example.com/guides/shoe-fit,301,merged
https://old.example.com/promo/spring-2020,,410,expired promotion, no equivalent
```

- Every inventoried URL gets a row: a target or a deliberate 404 or 410 with a reason.
- One hop to the final URL. Fold existing redirects into the new map so no chain forms (`A to B` plus `B to C` becomes `A to C` and `B to C`). No loops.
- Targets are the closest equivalent, never the home page by default.
- Preserve query strings that carry meaning; drop tracking parameters.
- Pattern rules (regular expressions) are fine for regular structures, but test them against the full inventory, not a few examples.

**4. Check template parity on staging.** For each template, compare old and new: title, meta description, `h1`, main content, internal links, canonical, `meta robots`, `hreflang`, JSON-LD, Open Graph, image `alt`, pagination, and whether all of it is in the server HTML. Run `scripts/seo_check.py` on the staging build, and a crawler on staging, and diff the results against the baseline crawl.

**5. Protect staging with authentication**, not only with `noindex` or `robots.txt`. Those settings leak into production when files are copied, and a public staging host gets indexed as a duplicate.

**6. Test the redirects before launch** against staging or a preview host, with a short script that reports the status and the final location of every row. Run it with the owner's agreement, at a gentle rate:

```python
import csv, sys, time, urllib.request, urllib.error

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None                      # report the first hop instead of following it

opener = urllib.request.build_opener(NoRedirect)
failures = 0
with open(sys.argv[1], newline="") as f:
    for row in csv.DictReader(f):
        req = urllib.request.Request(row["old_url"], method="HEAD", headers={"User-Agent": "redirect-check"})
        try:
            resp = opener.open(req, timeout=15)
            got, location = resp.status, ""
        except urllib.error.HTTPError as e:   # 3xx and 4xx arrive here when not followed
            got, location = e.code, e.headers.get("Location", "")
        want = int(row["status"])
        ok = got == want and (want not in (301, 308) or location == row["new_url"])
        if not ok:
            failures += 1
            print(f"FAIL {row['old_url']} -> {got} {location} (expected {want} {row['new_url']})")
        time.sleep(0.2)                       # stay polite
print(f"{failures} failures")
sys.exit(1 if failures else 0)
```

Some servers answer `HEAD` differently from `GET`; switch the method if results look wrong. If the server sends relative `Location` headers, resolve them with `urllib.parse.urljoin(row["old_url"], location)` before comparing. Then request each `new_url` and confirm it returns 200, is indexable and is self-canonical.

**7. Agree the rollback plan and its triggers** before launch: which signals mean "roll back" (for example a 5xx rate above an agreed level, a share of old URLs not redirecting, or a site-wide `noindex` found), who decides, and how long a rollback takes.

## Launch day

1. Deploy redirects together with the new site, so no old URL ever returns 404.
2. Confirm production `robots.txt` and `meta robots` are the production versions (no staging `Disallow: /`, no global `noindex`).
3. Verify the new host or property in Search Console and Bing Webmaster Tools (both old and new must be verified for a domain move).
4. Submit the new sitemaps. Keeping a temporary sitemap of the old URLs can speed up discovery of the redirects; remove it after a few weeks.
5. For a domain move, use Search Console's Change of Address tool from the old property, and Bing's site move tool. These are for whole-domain moves, not for protocol or path changes.
6. Update what you control off-site: profile links, important partner links, ad and email destinations, and any `sameAs` links in structured data.
7. Watch logs and error dashboards for 404 and 5xx spikes on old and new URLs during the first hours.

## After launch

| When | Check | Source |
|---|---|---|
| First day | Redirect script against production; crawl of the new site for 4xx, 5xx, chains, `noindex` and canonical errors | Your crawl and script output |
| First week | Search engines fetching the new URLs and following redirects; robots.txt fetch healthy | Server logs; Search Console Crawl Stats and robots.txt report |
| Weeks 1 to 8 | New URLs moving into "Indexed", old ones into "Page with redirect"; no rise in 404, soft 404 or "Duplicate, Google chose different canonical" | Search Console Pages report, per sitemap |
| Weeks 1 to 12 | Clicks and impressions per section against the baseline, with the same weekdays and seasonality accounted for | Search Console Performance (old and new properties) |
| Weeks 4 to 12 | Core Web Vitals per template against the baseline | CWV report (28-day field data, so it lags) |

Fluctuation for several weeks is normal; large sites can take months to settle. A sustained loss concentrated in one section usually points to missing or wrong redirects, changed templates, or new rendering problems there, so compare that section's crawl and templates with the baseline first.

Keep the redirects for at least a year and in practice as long as old URLs still receive links or visits. Keep the old domain registered; a lapsed domain can be bought and used against your users and your reputation.

## Done when

- [ ] Every inventoried URL has a reviewed row in the redirect map, and the redirect script reports no failures against production.
- [ ] New URLs return 200, are self-canonical and indexable; no chains, loops or soft 404s; production `robots.txt` and `meta robots` verified.
- [ ] Template parity checked against the baseline crawl; structured data validates on each new template.
- [ ] Search Console and Bing properties verified, sitemaps submitted and, for a domain move, the move tools used, each with the owner's go-ahead.
- [ ] Baseline and post-launch figures reported with their sources and date ranges, and the rollback triggers were never hit, or the rollback happened as planned.
