"""Tests for scripts/seo_drift.py. Run: python3 -B -m unittest discover -s modules/search-visibility/tests -v"""

import contextlib
import gzip
import importlib.util
import io
import json
import pathlib
import shutil
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("seo_drift", HERE.parent / "scripts" / "seo_drift.py")
drift = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drift)

BASE = "https://www.example.com"


def page(path="/", title="Trail shoes", desc="Shoes for trails.", canonical="self", robots=None, h1="Trail shoes",
         lang="en", body="<p>Grip, fit and drop explained for trail runners.</p>", links=(), jsonld=None,
         og=True, hreflang=None):
    head = [f"<title>{title}</title>" if title is not None else ""]
    if desc is not None:
        head.append(f'<meta name="description" content="{desc}">')
    if canonical:
        href = BASE + path if canonical == "self" else canonical
        head.append(f'<link rel="canonical" href="{href}">')
    if robots:
        head.append(f'<meta name="robots" content="{robots}">')
    if og:
        head.append(f'<meta property="og:title" content="{title}"><meta property="og:image" content="{BASE}/og.png">')
    for code, href in (hreflang or {}).items():
        head.append(f'<link rel="alternate" hreflang="{code}" href="{href}">')
    for block in ([jsonld] if isinstance(jsonld, str) else jsonld or []):
        head.append(f'<script type="application/ld+json">{block}</script>')
    anchors = "".join(f'<a href="{href}">link</a>' for href in links)
    heading = f"<h1>{h1}</h1>" if h1 else ""
    html_open = f'<html lang="{lang}">' if lang else "<html>"
    return (f"<!doctype html>{html_open}<head>{''.join(head)}</head><body><nav>{anchors}</nav>"
            f"<main>{heading}{body}</main><script>var hidden = 'not counted words here';</script></body></html>")


ORG = '{"@context": "https://schema.org", "@type": "Organization", "name": "Example Outdoor"}'
PRODUCT = '{"@context": "https://schema.org", "@graph": [{"@type": "Product", "name": "TR3"}, {"@type": "BreadcrumbList"}]}'
SITEMAP = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "{}</urlset>")


def sitemap(*paths):
    return SITEMAP.format("".join(f"<url><loc>{BASE}{p}</loc></url>" for p in paths))


class DriftCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def site(self, name, files):
        root = self.tmp / name
        if root.exists():
            shutil.rmtree(root)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(text, bytes):
                path.write_bytes(text)
            else:
                path.write_text(text, encoding="utf-8")
        root.mkdir(parents=True, exist_ok=True)
        return root

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = drift.main([str(a) for a in argv])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def snap(self, root, *extra):
        code, out, err = self.run_main("snapshot", root, "--base-url", BASE, *extra)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def compare(self, old_files, new_files, *extra, base=True):
        a = self.site("old", old_files)
        b = self.site("new", new_files)
        argv = ["diff", a, b, "--json"] + (["--base-url", BASE] if base else []) + list(extra)
        code, out, err = self.run_main(*argv)
        self.assertIn(code, (0, 1), err)
        return code, json.loads(out)

    @staticmethod
    def rules(report):
        return sorted({f["rule"] for f in report["findings"]})

    def home(self, **kw):
        return {"index.html": page("/", links=["/guides/shoes.html"], **kw),
                "guides/shoes.html": page("/guides/shoes.html", title="Shoes", h1="Shoes", links=["/"])}


class SnapshotTests(DriftCase):
    def test_fields_recorded(self):
        root = self.site("s", {
            "index.html": page("/", jsonld=ORG, links=["/guides/shoes.html", "guides/shoes.html#fit", "mailto:a@b.c"],
                               hreflang={"en-GB": f"{BASE}/", "de": f"{BASE}/de/"}),
            "guides/shoes.html": page("/guides/shoes.html", title="Shoes", robots="noindex, nofollow"),
        })
        snap = self.snap(root)
        home, shoes = snap["pages"]["/"], snap["pages"]["/guides/shoes.html"]
        self.assertEqual(home["title"], "Trail shoes")
        self.assertEqual(home["canonical"], f"{BASE}/")
        self.assertTrue(home["canonical_self"])
        self.assertTrue(home["indexable"])
        self.assertEqual(home["jsonld_types"], ["Organization"])
        self.assertEqual(home["hreflang"], {"de": f"{BASE}/de/", "en-gb": f"{BASE}/"})
        self.assertEqual(home["h1"], ["Trail shoes"])
        self.assertEqual(home["lang"], "en")
        self.assertEqual(shoes["robots"], ["nofollow", "noindex"])   # sorted
        self.assertFalse(shoes["indexable"])
        self.assertEqual(shoes["inlinks"], 1)        # two hrefs from one page count once
        self.assertEqual(home["inlinks"], 0)

    def test_word_count_prefers_main_and_skips_scripts(self):
        root = self.site("s", {"index.html": page("/", h1="Hi", body="<p>one two three</p>")})
        self.assertEqual(self.snap(root)["pages"]["/"]["words"], 4)

    def test_snapshot_is_deterministic(self):
        root = self.site("s", self.home(jsonld=[ORG, PRODUCT]))
        first = self.run_main("snapshot", root, "--base-url", BASE)[1]
        second = self.run_main("snapshot", root, "--base-url", BASE)[1]
        self.assertEqual(first, second)
        self.assertNotIn("label", json.loads(first))

    def test_graph_types_and_invalid_blocks(self):
        root = self.site("s", {"index.html": page("/", jsonld=[PRODUCT, "{not json"])})
        info = self.snap(root)["pages"]["/"]
        self.assertEqual(info["jsonld_types"], ["BreadcrumbList", "Product"])
        self.assertEqual(info["jsonld_invalid"], 1)
        self.assertEqual(info["jsonld_blocks"], 2)

    def test_clean_urls_keys_and_links(self):
        root = self.site("s", {"index.html": page("/", links=["/about"]),
                               "about.html": page("/about", canonical=f"{BASE}/about")})
        snap = self.snap(root, "--clean-urls")
        self.assertIn("/about", snap["pages"])
        self.assertTrue(snap["pages"]["/about"]["canonical_self"])
        self.assertEqual(snap["pages"]["/about"]["inlinks"], 1)

    def test_without_base_url_canonical_compares_paths(self):
        root = self.site("s", {"index.html": page("/"), "x.html": page("/x.html", canonical=f"{BASE}/")})
        code, out, _ = self.run_main("snapshot", root)
        snap = json.loads(out)
        self.assertTrue(snap["pages"]["/"]["canonical_self"])
        self.assertFalse(snap["pages"]["/x.html"]["canonical_self"])

    def test_exclude_and_label(self):
        root = self.site("s", {"index.html": page("/"), "drafts/x.html": page("/drafts/x.html")})
        snap = self.snap(root, "--exclude", "drafts/*", "--label", "release 42")
        self.assertEqual(list(snap["pages"]), ["/"])
        self.assertEqual(snap["label"], "release 42")

    def test_sitemaps_including_gzip_and_ignoring_feeds(self):
        root = self.site("s", {
            "index.html": page("/"),
            "sitemap-a.xml": sitemap("/"),
            "sitemap-b.xml.gz": gzip.compress(sitemap("/b").encode()),
            "feed.xml": "<rss><channel><title>t</title></channel></rss>",
        })
        snap = self.snap(root)
        self.assertEqual(snap["sitemap_urls"], [f"{BASE}/", f"{BASE}/b"])
        self.assertEqual([s["file"] for s in snap["sitemaps"]], ["sitemap-a.xml", "sitemap-b.xml.gz"])

    def test_out_file_written(self):
        root = self.site("s", {"index.html": page("/")})
        out = self.tmp / "snap.json"
        code, stdout, err = self.run_main("snapshot", root, "--out", out)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(out.read_text())["format"], drift.FORMAT)


class RobotsTests(unittest.TestCase):
    def test_longest_match_and_allow_tie(self):
        r = drift.Robots("User-agent: *\nDisallow: /shop\nAllow: /shop/help\nDisallow: /a\nAllow: /a\n")
        self.assertFalse(r.allowed("googlebot", "/shop/cart"))
        self.assertTrue(r.allowed("googlebot", "/shop/help/x"))
        self.assertTrue(r.allowed("googlebot", "/a"))

    def test_wildcards_and_anchor(self):
        r = drift.Robots("User-agent: *\nDisallow: /*.pdf$\nDisallow: /*?sort=\n")
        self.assertFalse(r.allowed("x", "/files/a.pdf"))
        self.assertTrue(r.allowed("x", "/files/a.pdf.html"))
        self.assertFalse(r.allowed("x", "/list?sort=price"))

    def test_named_group_replaces_star(self):
        r = drift.Robots("User-agent: *\nDisallow: /private\n\nUser-agent: Googlebot\nDisallow: /beta\n")
        self.assertTrue(r.allowed("googlebot", "/private"))
        self.assertFalse(r.allowed("googlebot", "/beta"))
        self.assertFalse(r.allowed("otherbot", "/private"))


class DiffTests(DriftCase):
    def test_identical_builds_are_clean(self):
        code, report = self.compare(self.home(), self.home())
        self.assertEqual(code, 0)
        self.assertEqual(report["findings"], [])

    def test_noindex_added_fails(self):
        new = self.home()
        new["guides/shoes.html"] = page("/guides/shoes.html", title="Shoes", h1="Shoes", links=["/"], robots="noindex")
        code, report = self.compare(self.home(), new)
        self.assertEqual(code, 1)
        self.assertIn("NOINDEX_ADDED", self.rules(report))

    def test_noindex_removed_warns(self):
        old = self.home()
        old["guides/shoes.html"] = page("/guides/shoes.html", title="Shoes", h1="Shoes", links=["/"], robots="noindex")
        code, report = self.compare(old, self.home())
        self.assertEqual(code, 0)
        self.assertIn("NOINDEX_REMOVED", self.rules(report))
        code, _ = self.compare(old, self.home(), "--strict")
        self.assertEqual(code, 1)

    def test_page_removed_severity_depends_on_indexability(self):
        old = self.home()
        old["old.html"] = page("/old.html")
        old["hidden.html"] = page("/hidden.html", robots="noindex")
        code, report = self.compare(old, self.home())
        by_rule = {f["where"]: f["rule"] for f in report["findings"]}
        self.assertEqual(by_rule["/old.html"], "PAGE_REMOVED")
        self.assertEqual(by_rule["/hidden.html"], "PAGE_REMOVED_NONINDEXABLE")
        self.assertEqual(code, 1)

    def test_page_added_is_info(self):
        new = self.home()
        new["new.html"] = page("/new.html")
        code, report = self.compare(self.home(), new)
        self.assertEqual((code, self.rules(report)), (0, ["PAGE_ADDED"]))

    def test_canonical_moves_elsewhere(self):
        new = self.home()
        new["guides/shoes.html"] = page("/guides/shoes.html", title="Shoes", h1="Shoes", links=["/"], canonical=f"{BASE}/")
        code, report = self.compare(self.home(), new)
        self.assertEqual(code, 1)
        self.assertIn("CANONICAL_NOW_ELSEWHERE", self.rules(report))

    def test_canonical_changed_and_removed(self):
        old = {"index.html": page("/"), "a.html": page("/a.html", canonical=f"{BASE}/x"),
               "b.html": page("/b.html")}
        new = {"index.html": page("/"), "a.html": page("/a.html", canonical=f"{BASE}/y"),
               "b.html": page("/b.html", canonical=None)}
        code, report = self.compare(old, new)
        found = {(f["rule"], f["where"]) for f in report["findings"]}
        self.assertIn(("CANONICAL_CHANGED", "/a.html"), found)
        self.assertIn(("CANONICAL_REMOVED", "/b.html"), found)
        self.assertEqual(code, 0)

    def test_title_changes(self):
        new = self.home(title="Trail running shoes")
        code, report = self.compare(self.home(), new)
        self.assertEqual((code, self.rules(report)), (0, ["OG_CHANGED", "TITLE_CHANGED"]))
        code, _ = self.compare(self.home(), new, "--fail-on", "info")
        self.assertEqual(code, 1)
        code, report = self.compare(self.home(), self.home(title=""))
        self.assertIn("TITLE_REMOVED", self.rules(report))
        self.assertEqual(code, 1)

    def test_description_h1_lang(self):
        new = self.home(desc=None, h1=None, lang="de")
        code, report = self.compare(self.home(), new)
        self.assertTrue({"DESCRIPTION_REMOVED", "H1_REMOVED", "LANG_CHANGED"} <= set(self.rules(report)))

    def test_robots_disallow_all(self):
        old = dict(self.home(), **{"robots.txt": "User-agent: *\nDisallow: /cart\n"})
        new = dict(self.home(), **{"robots.txt": "User-agent: *\nDisallow: /\n"})
        code, report = self.compare(old, new)
        rules = self.rules(report)
        self.assertEqual(code, 1)
        for rule in ("ROBOTS_DISALLOW_ALL_NEW", "PAGE_NOW_BLOCKED", "ROBOTS_RULES_CHANGED"):
            self.assertIn(rule, rules)
        detail = next(f["detail"] for f in report["findings"] if f["rule"] == "ROBOTS_RULES_CHANGED")
        self.assertIn("- [*] disallow: /cart", detail)
        self.assertIn("+ [*] disallow: /", detail)

    def test_agent_specific_block(self):
        old = dict(self.home(), **{"robots.txt": "User-agent: *\nDisallow:\n"})
        new = dict(self.home(), **{"robots.txt": "User-agent: *\nDisallow:\n\nUser-agent: Googlebot\nDisallow: /guides/\n"})
        code, report = self.compare(old, new)
        blocked = sorted(f["where"] for f in report["findings"] if f["rule"] == "PAGE_NOW_BLOCKED")
        self.assertEqual(blocked, ["/guides/shoes.html"])
        code, report = self.compare(old, new, "--agent", "bingbot")
        self.assertNotIn("PAGE_NOW_BLOCKED", self.rules(report))

    def test_robots_file_removed(self):
        old = dict(self.home(), **{"robots.txt": "User-agent: *\nDisallow: /cart\n"})
        code, report = self.compare(old, self.home())
        self.assertEqual((code, self.rules(report)), (0, ["ROBOTS_FILE_REMOVED"]))

    def test_sitemap_urls(self):
        old = dict(self.home(), **{"sitemap.xml": sitemap("/", "/guides/shoes.html")})
        new = dict(self.home(), **{"sitemap.xml": sitemap("/", "/guides/boots.html")})
        code, report = self.compare(old, new)
        found = {(f["rule"], f["where"]) for f in report["findings"]}
        self.assertIn(("SITEMAP_URL_REMOVED", f"{BASE}/guides/shoes.html"), found)
        self.assertIn(("SITEMAP_URL_ADDED", f"{BASE}/guides/boots.html"), found)
        code, report = self.compare(old, self.home())
        self.assertEqual((code, self.rules(report)), (1, ["SITEMAPS_GONE"]))

    def test_structured_data_changes(self):
        old = {"index.html": page("/", jsonld=[ORG, PRODUCT])}
        code, report = self.compare(old, {"index.html": page("/", jsonld=[ORG])})
        self.assertEqual(self.rules(report), ["JSONLD_TYPE_REMOVED"])
        code, report = self.compare(old, {"index.html": page("/")})
        self.assertEqual(self.rules(report), ["JSONLD_REMOVED"])
        code, report = self.compare(old, {"index.html": page("/", jsonld=[ORG, PRODUCT, "{broken"])})
        self.assertIn("JSONLD_NOW_INVALID", self.rules(report))
        self.assertEqual(code, 1)
        changed = ORG.replace("Example Outdoor", "Example Outdoors")
        code, report = self.compare(old, {"index.html": page("/", jsonld=[changed, PRODUCT])})
        self.assertEqual(self.rules(report), ["JSONLD_CHANGED"])

    def test_hreflang_changes(self):
        old = {"index.html": page("/", hreflang={"en": f"{BASE}/", "de": f"{BASE}/de/"})}
        new = {"index.html": page("/", hreflang={"en": f"{BASE}/en/", "fr": f"{BASE}/fr/"})}
        code, report = self.compare(old, new)
        self.assertEqual(self.rules(report), ["HREFLANG_ADDED", "HREFLANG_CHANGED", "HREFLANG_REMOVED"])

    def test_og_removed(self):
        code, report = self.compare(self.home(), self.home(og=False))
        self.assertIn("OG_REMOVED", self.rules(report))

    def test_text_shrank_threshold(self):
        long_body = "<p>" + " ".join(f"word{i}" for i in range(100)) + "</p>"
        short_body = "<p>" + " ".join(f"word{i}" for i in range(30)) + "</p>"
        old, new = {"index.html": page("/", body=long_body)}, {"index.html": page("/", body=short_body)}
        code, report = self.compare(old, new)
        self.assertEqual(self.rules(report), ["TEXT_SHRANK"])
        code, report = self.compare(old, new, "--text-drop", "0.9")
        self.assertEqual(self.rules(report), ["TEXT_CHANGED"])

    def test_page_orphaned(self):
        new = self.home()
        new["index.html"] = page("/", links=[])
        code, report = self.compare(self.home(), new)
        self.assertIn(("PAGE_ORPHANED", "/guides/shoes.html"),
                      {(f["rule"], f["where"]) for f in report["findings"]})

    def test_accept_file_suppresses_approved_changes(self):
        new = self.home()
        new["guides/shoes.html"] = page("/guides/shoes.html", title="Shoes", h1="Shoes", links=["/"], robots="noindex")
        accept = self.tmp / "approved.txt"
        accept.write_text("# approved by the owner on 2026-10-30\nNOINDEX_ADDED /guides/*\n", encoding="utf-8")
        code, report = self.compare(self.home(), new, "--accept", accept)
        self.assertEqual(code, 0)
        self.assertEqual(report["summary"]["accepted"], 1)
        self.assertNotIn("NOINDEX_ADDED", self.rules(report))

    def test_ignore_rules(self):
        code, report = self.compare(self.home(), self.home(title="New"), "--ignore", "TITLE_CHANGED,OG_CHANGED")
        self.assertEqual(report["findings"], [])

    def test_options_differ_between_snapshots(self):
        root = self.site("s", self.home())
        a = self.tmp / "a.json"
        b = self.tmp / "b.json"
        self.run_main("snapshot", root, "--base-url", BASE, "--out", a)
        self.run_main("snapshot", root, "--base-url", BASE, "--agent", "bingbot", "--out", b)
        code, out, _ = self.run_main("diff", a, b, "--json")
        self.assertIn("OPTIONS_DIFFER", self.rules(json.loads(out)))

    def test_snapshot_against_folder_and_text_output(self):
        root = self.site("s", self.home())
        snap = self.tmp / "before.json"
        self.run_main("snapshot", root, "--base-url", BASE, "--out", snap)
        (root / "guides" / "shoes.html").write_text(
            page("/guides/shoes.html", title="Shoes", h1="Shoes", links=["/"], robots="noindex"), encoding="utf-8")
        code, out, _ = self.run_main("diff", snap, root, "--base-url", BASE)
        self.assertEqual(code, 1)
        self.assertIn("ERROR NOINDEX_ADDED (1)", out)
        self.assertIn("/guides/shoes.html", out)

    def test_scan_limit_reported(self):
        files = {f"p{i}.html": page(f"/p{i}.html") for i in range(3)}
        code, report = self.compare(files, files, "--max-files", "2")
        self.assertIn("SCAN_LIMIT", self.rules(report))


class UsageTests(DriftCase):
    def test_list_rules_and_help(self):
        code, out, _ = self.run_main("--list-rules")
        self.assertEqual(code, 0)
        self.assertIn("NOINDEX_ADDED", out)
        code, out, _ = self.run_main("--help")
        self.assertEqual(code, 0)
        self.assertIn("snapshot", out)

    def test_usage_errors_exit_2(self):
        root = self.site("s", {"index.html": page("/")})
        bad = self.tmp / "bad.json"
        bad.write_text('{"format": "something-else"}', encoding="utf-8")
        cases = [
            [],
            ["snapshot", self.tmp / "missing"],
            ["snapshot", root, "--base-url", "www.example.com"],
            ["snapshot", root, "--robots", self.tmp / "no-robots.txt"],
            ["snapshot", root, "--sitemap", self.tmp / "no-sitemap.xml"],
            ["diff", bad, root],
            ["diff", root, root, "--ignore", "NOT_A_RULE"],
            ["diff", root, root, "--text-drop", "1.5"],
            ["diff", root, root, "--accept", self.tmp / "nope.txt"],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                self.assertEqual(self.run_main(*argv)[0], 2)

    def test_bad_accept_line(self):
        root = self.site("s", {"index.html": page("/")})
        accept = self.tmp / "accept.txt"
        accept.write_text("NOT_A_RULE /x\n", encoding="utf-8")
        self.assertEqual(self.run_main("diff", root, root, "--accept", accept)[0], 2)


if __name__ == "__main__":
    unittest.main()
