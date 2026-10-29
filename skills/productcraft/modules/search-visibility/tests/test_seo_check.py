"""Tests for scripts/seo_check.py. Run: python3 -B -m unittest discover -s modules/search-visibility/tests -v"""

import contextlib
import gzip
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("seo_check", HERE.parent / "scripts" / "seo_check.py")
seo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seo)

BASE = "https://www.example.com"


def page(title="Trail shoes", desc="Shoes for trails.", canonical=f"{BASE}/", head_extra="", body="<h1>Trail shoes</h1>",
         og=True, lang="en"):
    og_tags = (f'<meta property="og:title" content="{title}"><meta property="og:type" content="website">'
               f'<meta property="og:image" content="{BASE}/og.png"><meta property="og:url" content="{canonical}">') if og else ""
    parts = ['<!doctype html>', f'<html lang="{lang}">' if lang else "<html>", "<head>",
             '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">']
    if title is not None:
        parts.append(f"<title>{title}</title>")
    if desc is not None:
        parts.append(f'<meta name="description" content="{desc}">')
    if canonical:
        parts.append(f'<link rel="canonical" href="{canonical}">')
    parts += [og_tags, head_extra, "</head><body>", body, "</body></html>"]
    return "\n".join(parts)


class SiteCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "site"
        self.root.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text, binary=False):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def check(self, *extra, base=True):
        argv = [str(self.root)] + (["--base-url", BASE] if base else []) + list(extra)
        findings, _ = seo.run(seo.parse_args(argv))
        return findings

    @staticmethod
    def rules(findings, file=None):
        return sorted({f["rule"] for f in findings if file is None or f["file"] == file})

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = seo.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()


class TestPages(SiteCase):
    def test_clean_page_has_no_errors_or_warnings(self):
        self.write("index.html", page())
        found = self.check()
        self.assertEqual([f for f in found if f["severity"] != "info"], [])

    def test_title_rules_and_svg_title_ignored(self):
        self.write("index.html", page(title=None, body="<h1>x</h1><svg><title>icon</title></svg>"))
        self.write("empty.html", page(title=" ", canonical=f"{BASE}/empty.html"))
        self.write("two.html", page(canonical=f"{BASE}/two.html", head_extra="<title>Second</title>"))
        found = self.check()
        self.assertIn("TITLE_MISSING", self.rules(found, "index.html"))
        self.assertIn("TITLE_EMPTY", self.rules(found, "empty.html"))
        self.assertIn("TITLE_MULTIPLE", self.rules(found, "two.html"))

    def test_long_title_is_advisory(self):
        self.write("index.html", page(title="x" * 90))
        found = [f for f in self.check() if f["rule"] == "TITLE_LONG"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "info")

    def test_duplicate_titles_and_descriptions_reported_once(self):
        for name in ("a.html", "b.html", "c.html"):
            self.write(name, page(title="Same", desc="Same text", canonical=f"{BASE}/{name}"))
        found = self.check()
        dups = [f for f in found if f["rule"] in ("TITLE_DUPLICATE", "META_DESC_DUPLICATE")]
        self.assertEqual(sorted(f["rule"] for f in dups), ["META_DESC_DUPLICATE", "TITLE_DUPLICATE"])
        self.assertTrue(all(f["file"] == "a.html" and "3 pages" in f["message"] for f in dups))

    def test_duplicates_ignore_noindex_and_canonicalized_pages(self):
        self.write("a.html", page(title="Same", canonical=f"{BASE}/a.html"))
        self.write("b.html", page(title="Same", canonical=f"{BASE}/a.html"))
        self.write("c.html", page(title="Same", canonical=f"{BASE}/c.html",
                                  head_extra='<meta name="robots" content="noindex">'))
        self.assertNotIn("TITLE_DUPLICATE", self.rules(self.check()))

    def test_description_heading_and_misc_rules(self):
        self.write("index.html", page(desc=None, body="<p>no heading</p>", lang=None,
                                      head_extra='<meta name="keywords" content="a,b"><meta http-equiv="refresh" content="0;url=/x">'))
        self.write("h.html", page(canonical=f"{BASE}/h.html", body="<h1>a</h1><h1>b</h1>"))
        found = self.check()
        for rule in ("META_DESC_MISSING", "H1_MISSING", "HTML_LANG_MISSING", "META_KEYWORDS", "META_REFRESH"):
            self.assertIn(rule, self.rules(found, "index.html"))
        multiple = [f for f in found if f["rule"] == "H1_MULTIPLE"]
        self.assertEqual(multiple[0]["severity"], "info")

    def test_image_alt_rules(self):
        body = ('<h1>x</h1><img src="/a.jpg"><img src="/b.jpg" alt=""><img src="/c.jpg" aria-hidden="true">'
                '<img src="/d.jpg" alt="Blue shoe" width="10" height="10">')
        self.write("index.html", page(body=body))
        found = {f["rule"]: f for f in self.check()}
        self.assertIn("1 image(s) without alt", found["IMG_ALT_MISSING"]["message"])
        self.assertIn("3 image(s) without width and height", found["IMG_NO_DIMENSIONS"]["message"])

    def test_clickable_anchor_without_href(self):
        self.write("index.html", page(body='<h1>x</h1><a onclick="go()">Go</a><a href="/ok">ok</a>'))
        self.assertIn("LINK_NO_HREF", self.rules(self.check()))


class TestCanonicalAndRobotsMeta(SiteCase):
    def test_multiple_relative_and_body_canonicals(self):
        self.write("index.html", page(canonical="/", body='<h1>x</h1><link rel="canonical" href="https://www.example.com/">'))
        rules = self.rules(self.check())
        for rule in ("CANONICAL_MULTIPLE", "CANONICAL_RELATIVE", "CANONICAL_IN_BODY"):
            self.assertIn(rule, rules)

    def test_canonical_to_noindex_target_and_chain(self):
        self.write("a.html", page(canonical=f"{BASE}/b.html"))
        self.write("b.html", page(canonical=f"{BASE}/b.html", head_extra='<meta name="robots" content="noindex, follow">'))
        self.write("c.html", page(canonical=f"{BASE}/d.html"))
        self.write("d.html", page(canonical=f"{BASE}/e.html"))
        found = self.check()
        self.assertIn("CANONICAL_TO_NOINDEX", self.rules(found, "a.html"))
        self.assertIn("CANONICAL_CHAIN", self.rules(found, "c.html"))
        self.assertIn("CANONICAL_TARGET_NOT_FOUND", self.rules(found, "d.html"))

    def test_noindex_and_mixed_signals(self):
        self.write("index.html", page())
        self.write("old.html", page(canonical=f"{BASE}/", head_extra='<meta name="robots" content="noindex">'))
        self.write("odd.html", page(canonical=f"{BASE}/odd.html", head_extra='<meta name="robots" content="index, noindex">'))
        found = self.check()
        self.assertIn("NOINDEX_WITH_CANONICAL", self.rules(found, "old.html"))
        self.assertIn("ROBOTS_META_CONFLICT", self.rules(found, "odd.html"))
        self.assertNotIn("CANONICAL_MISSING", self.rules(found, "old.html"))

    def test_agent_specific_meta_robots(self):
        self.write("index.html", page(head_extra='<meta name="bingbot" content="noindex">'))
        self.assertNotIn("ROBOTS_META_NOINDEX", self.rules(self.check()))
        self.assertIn("ROBOTS_META_NOINDEX", self.rules(self.check("--agent", "bingbot")))

    def test_clean_urls_and_base_path(self):
        self.write("about.html", page(canonical=f"{BASE}/docs/about"))
        args = [str(self.root), "--base-url", BASE + "/docs", "--clean-urls"]
        findings, _ = seo.run(seo.parse_args(args))
        self.assertNotIn("CANONICAL_TARGET_NOT_FOUND", self.rules(findings))


class TestHreflang(SiteCase):
    def alt(self, pairs):
        return "".join(f'<link rel="alternate" hreflang="{c}" href="{h}">' for c, h in pairs)

    def test_code_validation(self):
        self.assertIsNone(seo.hreflang_problem("x-default"))
        self.assertIsNone(seo.hreflang_problem("en-GB"))
        self.assertIsNone(seo.hreflang_problem("zh-Hant-TW"))
        self.assertIsNone(seo.hreflang_problem("de"))
        self.assertEqual(seo.hreflang_problem("en-UK")[0], "HREFLANG_INVALID")
        self.assertIn("'ja'", seo.hreflang_problem("jp")[1])
        self.assertEqual(seo.hreflang_problem("en-ZZ")[0], "HREFLANG_INVALID")
        self.assertEqual(seo.hreflang_problem("us")[0], "HREFLANG_INVALID")
        self.assertEqual(seo.hreflang_problem("es-419")[0], "HREFLANG_UNUSUAL_REGION")

    def test_iso_lists_complete(self):
        self.assertEqual(len(seo.ISO3166_ALPHA2), 249)
        self.assertGreaterEqual(len(seo.ISO639_1), 183)

    def test_valid_reciprocal_set(self):
        pairs = [("en", f"{BASE}/"), ("de", f"{BASE}/de/"), ("x-default", f"{BASE}/")]
        self.write("index.html", page(head_extra=self.alt(pairs)))
        self.write("de/index.html", page(canonical=f"{BASE}/de/", lang="de", title="Laufschuhe", desc="Schuhe.",
                                         head_extra=self.alt(pairs)))
        hreflang = [f for f in self.check() if f["rule"].startswith("HREFLANG")]
        self.assertEqual(hreflang, [])

    def test_missing_return_self_duplicate_relative(self):
        self.write("index.html", page(head_extra=self.alt([("en", f"{BASE}/"), ("de", f"{BASE}/de/"),
                                                           ("de", f"{BASE}/de2/"), ("fr", "/fr/")])))
        self.write("de/index.html", page(canonical=f"{BASE}/de/", title="Laufschuhe", desc="Schuhe.",
                                         head_extra=self.alt([("en", f"{BASE}/en/")])))
        found = self.check()
        root = self.rules(found, "index.html")
        for rule in ("HREFLANG_NO_RETURN", "HREFLANG_DUPLICATE", "HREFLANG_RELATIVE", "HREFLANG_NO_XDEFAULT"):
            self.assertIn(rule, root)
        de = self.rules(found, "de/index.html")
        self.assertIn("HREFLANG_NO_SELF", de)
        self.assertIn("HREFLANG_TARGET_NOT_FOUND", de)


class TestJsonLd(SiteCase):
    def ld(self, text):
        return f'<script type="application/ld+json">{text}</script>'

    def test_invalid_json(self):
        self.write("index.html", page(head_extra=self.ld('{"@context": "https://schema.org", "@type": "Thing",}')))
        self.assertIn("JSONLD_INVALID", self.rules(self.check()))

    def test_missing_type_and_context(self):
        self.write("index.html", page(head_extra=self.ld('{"name": "x"}')))
        rules = self.rules(self.check())
        self.assertIn("JSONLD_NO_TYPE", rules)
        self.assertIn("JSONLD_NO_CONTEXT", rules)

    def test_graph_with_reference_is_clean(self):
        graph = {"@context": "https://schema.org", "@graph": [
            {"@type": "Organization", "@id": f"{BASE}/#org", "name": "Example"},
            {"@id": f"{BASE}/#org"}]}
        self.write("index.html", page(head_extra=self.ld(json.dumps(graph))))
        self.assertFalse([f for f in self.check() if f["rule"].startswith("JSONLD")])

    def test_retired_and_review_markup(self):
        data = [{"@context": "https://schema.org", "@type": "HowTo", "name": "x"},
                {"@context": "https://schema.org", "@type": "Product", "name": "y",
                 "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.5", "reviewCount": "10"}}]
        self.write("index.html", page(head_extra=self.ld(json.dumps(data))))
        found = self.check()
        retired = [f for f in found if f["rule"] == "JSONLD_RETIRED_FEATURE"]
        self.assertEqual(len(retired), 1)
        self.assertIn("HowTo", retired[0]["message"])
        self.assertIn("JSONLD_REVIEW_MARKUP", self.rules(found))

    def test_html_comment_wrapper_tolerated(self):
        self.write("index.html", page(head_extra=self.ld('<!-- {"@context": "https://schema.org", "@type": "Thing"} -->')))
        self.assertNotIn("JSONLD_INVALID", self.rules(self.check()))


class TestSocial(SiteCase):
    def test_missing_and_incomplete_open_graph(self):
        self.write("index.html", page(og=False))
        self.write("b.html", page(canonical=f"{BASE}/b.html", og=False,
                                  head_extra='<meta property="og:title" content="b"><meta property="og:image" content="/b.png">'
                                             '<meta name="twitter:card" content="large">'))
        found = self.check()
        self.assertIn("OG_MISSING", self.rules(found, "index.html"))
        b = self.rules(found, "b.html")
        for rule in ("OG_INCOMPLETE", "OG_IMAGE_RELATIVE", "TWITTER_CARD_INVALID"):
            self.assertIn(rule, b)

    def test_og_url_mismatch_and_name_attribute_accepted(self):
        tags = ('<meta name="og:title" content="t"><meta name="og:type" content="article">'
                f'<meta name="og:image" content="{BASE}/i.png"><meta name="og:url" content="{BASE}/other">')
        self.write("index.html", page(og=False, head_extra=tags + '<meta name="twitter:card" content="summary">'))
        rules = self.rules(self.check())
        self.assertIn("OG_URL_MISMATCH", rules)
        self.assertNotIn("OG_INCOMPLETE", rules)
        self.assertNotIn("TWITTER_CARD_INVALID", rules)


class TestRobotsMatching(unittest.TestCase):
    def test_longest_match_and_allow_wins_tie(self):
        r = seo.Robots("User-agent: *\nDisallow: /shop/\nAllow: /shop/sale\nDisallow: /a\nAllow: /a\n")
        self.assertFalse(r.allowed("googlebot", "/shop/cart")[0])
        self.assertTrue(r.allowed("googlebot", "/shop/sale/1")[0])
        self.assertTrue(r.allowed("googlebot", "/a")[0])

    def test_wildcards_and_end_anchor(self):
        r = seo.Robots("User-agent: *\nDisallow: /*?*sort=\nDisallow: /*.pdf$\n")
        self.assertFalse(r.allowed("x", "/list?page=2&sort=asc")[0])
        self.assertTrue(r.allowed("x", "/list?page=2")[0])
        self.assertFalse(r.allowed("x", "/files/a.pdf")[0])
        self.assertTrue(r.allowed("x", "/files/a.pdf?v=2")[0])

    def test_specific_group_replaces_star_and_same_agent_groups_merge(self):
        text = ("User-agent: *\nDisallow: /private/\n\nUser-agent: Googlebot\nDisallow: /tmp/\n\n"
                "User-agent: googlebot\nDisallow: /beta/\n")
        r = seo.Robots(text)
        self.assertTrue(r.allowed("googlebot", "/private/x")[0])
        self.assertFalse(r.allowed("googlebot", "/tmp/x")[0])
        self.assertFalse(r.allowed("googlebot", "/beta/x")[0])
        self.assertFalse(r.allowed("bingbot", "/private/x")[0])

    def test_consecutive_agents_share_group_and_unknown_fields_do_not_split(self):
        r = seo.Robots("User-agent: a\nCrawl-delay: 3\nUser-agent: b\nDisallow: /x\n")
        self.assertFalse(r.allowed("a", "/x")[0])
        self.assertFalse(r.allowed("b", "/x")[0])

    def test_empty_disallow_and_robots_txt_always_allowed(self):
        r = seo.Robots("User-agent: *\nDisallow:\n")
        self.assertTrue(r.allowed("x", "/anything")[0])
        r = seo.Robots("User-agent: *\nDisallow: /\n")
        self.assertTrue(r.allowed("x", "/robots.txt")[0])
        self.assertFalse(r.allowed("x", "/")[0])


class TestRobotsFile(SiteCase):
    def test_file_findings(self):
        self.write("index.html", page())
        self.write("robots.txt", "Disallow: /early\nUser-agent: *\nDisallow: /\nDisallow: private\nNoindex: /x\n"
                                 "Crawl-delay: 2\nHost: example.com\njunk line\nSitemap: sitemap.xml\n")
        rules = self.rules(self.check(), "robots.txt")
        for rule in ("ROBOTS_RULE_OUTSIDE_GROUP", "ROBOTS_DISALLOW_ALL", "ROBOTS_PATH_FORMAT", "ROBOTS_NOINDEX_LINE",
                     "ROBOTS_CRAWL_DELAY", "ROBOTS_UNKNOWN_FIELD", "ROBOTS_SYNTAX", "ROBOTS_SITEMAP_RELATIVE"):
            self.assertIn(rule, rules)

    def test_blocking_one_ai_crawler_is_policy_not_error(self):
        self.write("robots.txt", "User-agent: ExampleTrainingBot\nDisallow: /\n\nUser-agent: *\nDisallow: /cart\n")
        found = [f for f in self.check() if f["file"] == "robots.txt"]
        self.assertEqual([(f["rule"], f["severity"]) for f in found], [("ROBOTS_AGENT_BLOCKED", "info")])

    def test_too_large(self):
        self.write("robots.txt", "User-agent: *\n" + ("Disallow: /x\n" * 50000))
        self.assertIn("ROBOTS_TOO_LARGE", self.rules(self.check()))

    def test_blocked_pages_and_resources(self):
        self.write("index.html", page(head_extra='<link rel="stylesheet" href="/static/site.css"><script src="/static/app.js"></script>'))
        self.write("private/p.html", page(canonical=f"{BASE}/private/p.html"))
        self.write("robots.txt", f"User-agent: *\nDisallow: /static/\nDisallow: /private/\nSitemap: {BASE}/sitemap.xml\n")
        found = self.check()
        resources = [f for f in found if f["rule"] == "RESOURCE_DISALLOWED"]
        self.assertEqual(len(resources), 2)
        self.assertIn("PAGE_DISALLOWED", self.rules(found, "private/p.html"))
        self.assertNotIn("PAGE_DISALLOWED", self.rules(found, "index.html"))


class TestSitemaps(SiteCase):
    NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'

    def urlset(self, body, ns=None):
        return f'<?xml version="1.0" encoding="UTF-8"?><urlset {ns or self.NS}>{body}</urlset>'

    def test_entry_level_findings(self):
        self.write("index.html", page())
        self.write("hidden.html", page(canonical=f"{BASE}/hidden.html", head_extra='<meta name="robots" content="noindex">'))
        self.write("dupe.html", page(canonical=f"{BASE}/"))
        body = (f"<url><loc>{BASE}/</loc><lastmod>2026-10-01T09:30:00+02:00</lastmod><priority>0.5</priority></url>"
                f"<url><loc>{BASE}/</loc></url>"
                f"<url><loc>/relative</loc></url><url><lastmod>2026-01-01</lastmod></url>"
                f"<url><loc>{BASE}/hidden.html</loc><lastmod>01/02/2026</lastmod></url>"
                f"<url><loc>{BASE}/dupe.html</loc></url><url><loc>{BASE}/gone/</loc></url>"
                f"<url><loc>https://cdn.example.net/x</loc></url>")
        self.write("sitemap.xml", self.urlset(body))
        rules = self.rules(self.check(), "sitemap.xml")
        for rule in ("SITEMAP_DUPLICATE", "SITEMAP_LOC_INVALID", "SITEMAP_LOC_MISSING", "SITEMAP_LASTMOD_INVALID",
                     "SITEMAP_URL_NOINDEX", "SITEMAP_URL_NOT_CANONICAL", "SITEMAP_URL_NOT_FOUND", "SITEMAP_CROSS_HOST",
                     "SITEMAP_IGNORED_TAGS"):
            self.assertIn(rule, rules)

    def test_lastmod_formats(self):
        for good in ("2026", "2026-10", "2026-10-29", "2026-10-29T08:00Z", "2026-10-29T08:00:00.5+01:00"):
            self.assertTrue(seo.valid_lastmod(good), good)
        for bad in ("2026-02-30", "2026-10-29 08:00", "29-10-2026", "2026-10-29T25:00Z", "2026-10-29T08:00"):
            self.assertFalse(seo.valid_lastmod(bad), bad)

    def test_parse_root_and_namespace(self):
        self.write("sitemap.xml", "<urlset><url><loc>broken")
        self.write("sitemap-b.xml", '<?xml version="1.0"?><feed></feed>')
        self.write("sitemap-c.xml", self.urlset(f"<url><loc>{BASE}/</loc></url>", ns='xmlns="http://example.org/other"'))
        self.write("index.html", page())
        found = self.check()
        self.assertIn("SITEMAP_PARSE", self.rules(found, "sitemap.xml"))
        self.assertIn("SITEMAP_ROOT", self.rules(found, "sitemap-b.xml"))
        self.assertIn("SITEMAP_NAMESPACE", self.rules(found, "sitemap-c.xml"))

    def test_too_many_entries(self):
        body = "".join(f"<url><loc>{BASE}/p{i}</loc></url>" for i in range(50_001))
        self.write("sitemap.xml", self.urlset(body))
        self.assertIn("SITEMAP_TOO_MANY", self.rules(self.check(base=False)))

    def test_index_children_gzip_robots_and_listing(self):
        self.write("index.html", page())
        self.write("private/a.html", page(canonical=f"{BASE}/private/a.html"))
        child = self.urlset(f"<url><loc>{BASE}/</loc></url><url><loc>{BASE}/private/a.html</loc></url>")
        self.write("maps/pages.xml.gz", gzip.compress(child.encode()), binary=True)
        self.write("sitemap-index.xml", f'<?xml version="1.0"?><sitemapindex {self.NS}>'
                                        f"<sitemap><loc>{BASE}/maps/pages.xml.gz</loc></sitemap></sitemapindex>")
        self.write("sitemap-extra.xml", self.urlset(f"<url><loc>{BASE}/</loc></url>"))
        self.write("robots.txt", f"User-agent: *\nDisallow: /private/\nSitemap: {BASE}/sitemap-index.xml\n")
        found = self.check()
        self.assertIn("SITEMAP_URL_DISALLOWED", self.rules(found, "maps/pages.xml.gz"))
        self.assertIn("SITEMAP_NOT_IN_ROBOTS", self.rules(found, "sitemap-extra.xml"))
        self.assertNotIn("SITEMAP_NOT_IN_ROBOTS", self.rules(found, "sitemap-index.xml"))


class TestCli(SiteCase):
    def test_exit_codes_and_threshold(self):
        self.write("index.html", page())
        self.assertEqual(self.cli(str(self.root), "--base-url", BASE)[0], 0)
        self.write("broken.html", page(title=None, canonical=f"{BASE}/broken.html"))
        self.assertEqual(self.cli(str(self.root), "--base-url", BASE)[0], 1)
        self.assertEqual(self.cli(str(self.root), "--base-url", BASE, "--fail-on", "never")[0], 0)
        self.assertEqual(self.cli(str(self.root), "--base-url", BASE, "--ignore", "TITLE_MISSING")[0], 0)

    def test_strict_fails_on_warnings(self):
        self.write("index.html", page(desc=None))
        self.assertEqual(self.cli(str(self.root), "--base-url", BASE)[0], 0)
        self.assertEqual(self.cli(str(self.root), "--base-url", BASE, "--strict")[0], 1)

    def test_usage_errors(self):
        self.assertEqual(self.cli(str(self.root / "nope"))[0], 2)
        self.assertEqual(self.cli(str(self.root), "--ignore", "NOT_A_RULE")[0], 2)
        self.assertEqual(self.cli(str(self.root), "--base-url", "example.com")[0], 2)
        self.assertEqual(self.cli()[0], 2)

    def test_list_rules_and_json_is_deterministic(self):
        code, out, _ = self.cli("--list-rules")
        self.assertEqual(code, 0)
        self.assertIn("HREFLANG_NO_RETURN", out)
        self.write("index.html", page(title=None))
        self.write("b.html", page(desc=None, canonical=f"{BASE}/b.html"))
        first = self.cli(str(self.root), "--base-url", BASE, "--json")[1]
        second = self.cli(str(self.root), "--base-url", BASE, "--json")[1]
        self.assertEqual(first, second)
        data = json.loads(first)
        self.assertEqual(data["pages"], 2)
        self.assertEqual(data["summary"]["error"], 1)
        self.assertTrue(all(set(f) == {"rule", "severity", "file", "line", "message"} for f in data["findings"]))

    def test_text_output_states_limits(self):
        self.write("index.html", page())
        out = self.cli(str(self.root))[1]
        self.assertIn("headers, redirects and JavaScript output were not seen", out)

    def test_hidden_and_dependency_folders_skipped(self):
        self.write("index.html", page())
        self.write("node_modules/pkg/readme.html", "<html></html>")
        self.write(".cache/x.html", "<html></html>")
        findings, count = seo.run(seo.parse_args([str(self.root), "--base-url", BASE]))
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
