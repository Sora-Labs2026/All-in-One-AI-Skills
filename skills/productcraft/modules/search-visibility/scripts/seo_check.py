#!/usr/bin/env python3
"""Offline search-readiness checker for built HTML files, robots.txt and XML sitemaps.

Reads a folder of built pages (a static export, a build output or saved HTML) and
reports problems search engines and link previews care about: titles and meta
descriptions, the main heading, canonical links, meta robots, hreflang sets, image
alt text, JSON-LD that parses and names a type, Open Graph and X card tags,
robots.txt syntax and rules, and sitemap syntax and contents.

Standard library only. Read-only. No network access. Deterministic output.
It sees files as shipped, so it cannot see HTTP headers (X-Robots-Tag, Link,
status codes, redirects) or anything JavaScript adds after load.

Exit codes: 0 = no finding at or above --fail-on, 1 = findings at or above it,
2 = usage error.
"""

import argparse
import gzip
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

VERSION = "1.0.0"
SEVERITIES = ("info", "warn", "error")
RANK = {"info": 0, "warn": 1, "error": 2, "never": 3}

RULES = {
    # pages
    "TITLE_MISSING": ("error", "No <title> element in the page"),
    "TITLE_EMPTY": ("error", "The <title> element is empty"),
    "TITLE_MULTIPLE": ("warn", "More than one <title> element"),
    "TITLE_LONG": ("info", "Title longer than --title-max characters; likely truncated in results"),
    "TITLE_DUPLICATE": ("warn", "Same title on several indexable, self-canonical pages"),
    "META_DESC_MISSING": ("warn", "No meta description"),
    "META_DESC_EMPTY": ("warn", "Meta description is empty"),
    "META_DESC_MULTIPLE": ("warn", "More than one meta description"),
    "META_DESC_LONG": ("info", "Meta description longer than --desc-max characters"),
    "META_DESC_DUPLICATE": ("warn", "Same meta description on several indexable, self-canonical pages"),
    "META_KEYWORDS": ("info", "meta keywords present; Google ignores it"),
    "META_REFRESH": ("warn", "meta refresh redirect; prefer a server-side 301 or 308"),
    "VIEWPORT_MISSING": ("warn", "No meta viewport; the page may not render well on mobile"),
    "HTML_LANG_MISSING": ("info", "No lang attribute on <html>"),
    "H1_MISSING": ("warn", "No <h1> heading"),
    "H1_MULTIPLE": ("info", "Several <h1> headings (allowed; one main heading is the usual convention)"),
    "ROBOTS_META_NOINDEX": ("info", "Page is noindex; confirm this is intended"),
    "ROBOTS_META_CONFLICT": ("warn", "meta robots says both index and noindex"),
    "NOINDEX_WITH_CANONICAL": ("warn", "noindex combined with a canonical pointing elsewhere sends mixed signals"),
    "CANONICAL_MISSING": ("info", "No canonical link on an indexable page"),
    "CANONICAL_EMPTY": ("error", "Canonical link has an empty href"),
    "CANONICAL_MULTIPLE": ("error", "Several canonical links; conflicting ones are ignored"),
    "CANONICAL_RELATIVE": ("warn", "Canonical href is not an absolute URL"),
    "CANONICAL_IN_BODY": ("error", "Canonical link in the <body>; it is ignored there"),
    "CANONICAL_TARGET_NOT_FOUND": ("warn", "Canonical points to a URL on this site with no page in the build"),
    "CANONICAL_TO_NOINDEX": ("error", "Canonical points to a page that is noindex"),
    "CANONICAL_CHAIN": ("warn", "Canonical points to a page whose own canonical points elsewhere"),
    "HREFLANG_INVALID": ("error", "hreflang value is not a valid language(-script)(-region) code or x-default"),
    "HREFLANG_UNUSUAL_REGION": ("info", "hreflang uses a numeric region; Google documents ISO 3166-1 alpha-2 regions"),
    "HREFLANG_RELATIVE": ("error", "hreflang href is not an absolute URL"),
    "HREFLANG_DUPLICATE": ("error", "The same hreflang value points to different URLs"),
    "HREFLANG_NO_SELF": ("warn", "hreflang set does not include the page itself"),
    "HREFLANG_NO_RETURN": ("error", "An alternate page in the build does not link back (missing return link)"),
    "HREFLANG_TARGET_NOT_FOUND": ("warn", "hreflang points to a URL on this site with no page in the build"),
    "HREFLANG_NO_XDEFAULT": ("info", "hreflang set has no x-default"),
    "IMG_ALT_MISSING": ("warn", "Images without an alt attribute (use alt=\"\" for decorative images)"),
    "IMG_NO_DIMENSIONS": ("info", "Images without width and height (layout shift risk)"),
    "LINK_NO_HREF": ("info", "Clickable <a> elements without an href; crawlers cannot follow them"),
    "JSONLD_INVALID": ("error", "JSON-LD block does not parse as JSON"),
    "JSONLD_NO_TYPE": ("error", "JSON-LD entity without @type"),
    "JSONLD_NO_CONTEXT": ("warn", "JSON-LD without a schema.org @context"),
    "JSONLD_RETIRED_FEATURE": ("info", "Markup for a Google result feature that is retired or restricted"),
    "JSONLD_REVIEW_MARKUP": ("info", "Rating or review markup; confirm it reflects real, visible reviews"),
    "OG_MISSING": ("warn", "No Open Graph tags; link previews fall back to guesses"),
    "OG_INCOMPLETE": ("warn", "Open Graph is missing one of og:title, og:type, og:image, og:url"),
    "OG_IMAGE_RELATIVE": ("warn", "og:image is not an absolute URL"),
    "OG_URL_MISMATCH": ("info", "og:url differs from the canonical URL"),
    "TWITTER_CARD_INVALID": ("warn", "twitter:card value is not summary, summary_large_image, app or player"),
    "PAGE_DISALLOWED": ("warn", "Page URL is disallowed by robots.txt for the chosen agent"),
    "RESOURCE_DISALLOWED": ("warn", "A stylesheet or script used by pages is disallowed by robots.txt"),
    # robots.txt
    "ROBOTS_SYNTAX": ("warn", "robots.txt line without a field name and colon"),
    "ROBOTS_UNKNOWN_FIELD": ("info", "robots.txt field that major crawlers do not support"),
    "ROBOTS_RULE_OUTSIDE_GROUP": ("warn", "allow or disallow before any user-agent line"),
    "ROBOTS_PATH_FORMAT": ("warn", "Rule path does not start with / or *"),
    "ROBOTS_DISALLOW_ALL": ("error", "All crawlers or a major search crawler are blocked from the whole site; only correct off production"),
    "ROBOTS_AGENT_BLOCKED": ("info", "A specific crawler is blocked from the whole site; confirm this is the chosen policy"),
    "ROBOTS_NOINDEX_LINE": ("error", "noindex in robots.txt is not supported (ignored by Google since 2019)"),
    "ROBOTS_CRAWL_DELAY": ("info", "crawl-delay is ignored by Google (Bing honors it)"),
    "ROBOTS_SITEMAP_RELATIVE": ("error", "Sitemap line is not an absolute URL"),
    "ROBOTS_TOO_LARGE": ("warn", "robots.txt larger than 500 KiB; Google ignores the rest"),
    # sitemaps
    "SITEMAP_PARSE": ("error", "Sitemap is not well-formed XML or cannot be read"),
    "SITEMAP_ROOT": ("error", "Sitemap root is neither urlset nor sitemapindex"),
    "SITEMAP_NAMESPACE": ("warn", "Sitemap does not use the sitemaps.org 0.9 namespace"),
    "SITEMAP_TOO_MANY": ("error", "More than 50,000 entries in one sitemap"),
    "SITEMAP_TOO_LARGE": ("error", "Sitemap larger than 50 MB uncompressed"),
    "SITEMAP_LOC_MISSING": ("error", "Entry without a loc"),
    "SITEMAP_LOC_INVALID": ("error", "loc is not an absolute http or https URL"),
    "SITEMAP_LASTMOD_INVALID": ("warn", "lastmod is not a W3C datetime"),
    "SITEMAP_DUPLICATE": ("warn", "Same URL listed more than once"),
    "SITEMAP_IGNORED_TAGS": ("info", "priority or changefreq present; Google ignores them"),
    "SITEMAP_CROSS_HOST": ("warn", "URL on a different host than --base-url"),
    "SITEMAP_URL_NOT_FOUND": ("warn", "Listed URL has no page in the build"),
    "SITEMAP_URL_NOINDEX": ("error", "Listed URL is a noindex page"),
    "SITEMAP_URL_NOT_CANONICAL": ("warn", "Listed URL's page declares a different canonical"),
    "SITEMAP_URL_DISALLOWED": ("error", "Listed URL is disallowed by robots.txt"),
    "SITEMAP_NOT_IN_ROBOTS": ("info", "robots.txt does not list this sitemap"),
    # scan
    "SCAN_LIMIT": ("info", "File limit reached; later files were not checked"),
}

ISO639_1 = set("""
aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv dz
ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik
io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml
mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd
se sg si sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi
vo wa wo xh yi yo za zh zu
""".split())

ISO3166_ALPHA2 = set("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW
BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI
FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN
IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME
MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF
PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV
SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE
YT ZA ZM ZW
""".split())

LANG_HINTS = {"jp": "ja", "cn": "zh", "gr": "el", "dk": "da", "cz": "cs", "ua": "uk", "iw": "he",
              "in": "id", "ji": "yi", "vn": "vi"}

RETIRED_TYPES = {
    "HowTo": "Google stopped showing HowTo rich results in 2023",
    "FAQPage": "since August 2023 Google shows FAQ rich results only for well-known government and health sites",
    "ClaimReview": "Google phased out fact-check rich results in 2025",
    "SpecialAnnouncement": "Google phased out special announcement rich results in 2025",
    "SearchAction": "Google removed the sitelinks search box in November 2024",
}
REVIEW_KEYS = {"aggregateRating", "review", "reviews"}
REVIEW_TYPES = {"Review", "AggregateRating", "EmployerAggregateRating"}
TWITTER_CARDS = {"summary", "summary_large_image", "app", "player"}
ROBOTS_FIELDS = {"user-agent", "allow", "disallow", "sitemap"}
SEARCH_AGENTS = {"*", "googlebot", "bingbot"}
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
W3C_DATETIME = re.compile(
    r"^(\d{4})(?:-(\d{2})(?:-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2}))?)?)?$")
MAX_SITEMAP_BYTES = 52_428_800
MAX_ROBOTS_BYTES = 512_000
MAX_HTML_BYTES = 20_000_000
SKIP_DIRS = {"node_modules", "__pycache__"}


def finding(rule, path, message="", line=None):
    return {"rule": rule, "severity": RULES[rule][0], "file": path, "line": line,
            "message": message or RULES[rule][1]}


def is_absolute_http(url):
    parts = urlsplit(url or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def normalize_url(url):
    """Lowercase scheme and host, drop default ports and fragments, keep path and query."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    port = parts.port if parts.port not in (None, 80, 443) else None
    netloc = host + (f":{port}" if port else "")
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def short(text, limit=80):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


# ---------------------------------------------------------------- HTML pages

class PageParser(HTMLParser):
    def __init__(self, agent="googlebot"):
        super().__init__(convert_charrefs=True)
        self.agent = agent
        self.titles, self.descriptions, self.robots, self.canonicals = [], [], [], []
        self.hreflangs, self.jsonld, self.resources, self.og, self.twitter = [], [], [], {}, {}
        self.h1 = 0
        self.img_no_alt, self.img_no_dims, self.links_no_href = [], 0, 0
        self.lang = None
        self.viewport = self.keywords = self.refresh = False
        self._in_head = self._seen_body = False
        self._svg = 0
        self._title = self._script = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        line = self.getpos()[0]
        if tag == "svg":
            self._svg += 1
        elif tag == "html":
            self.lang = a.get("lang", "").strip() or None
        elif tag == "head":
            self._in_head = True
        elif tag == "body":
            self._in_head, self._seen_body = False, True
        elif tag == "title" and not self._svg:
            self._title = []
        elif tag == "h1" and not self._svg:
            self.h1 += 1
        elif tag == "meta":
            self._meta(a, line)
        elif tag == "link":
            self._link(a, line)
        elif tag == "script":
            if a.get("type", "").strip().lower() == "application/ld+json":
                self._script = ([], line)
            elif a.get("src"):
                self.resources.append(a["src"])
        elif tag == "img":
            hidden = a.get("aria-hidden", "").lower() == "true" or a.get("role", "").lower() in ("presentation", "none")
            if "alt" not in a and not hidden:
                self.img_no_alt.append(a.get("src", "(no src)"))
            if not (a.get("width") and a.get("height")):
                self.img_no_dims += 1
        elif tag == "a":
            href = a.get("href", "").strip()
            if (not href or href.lower().startswith("javascript:")) and ("onclick" in a or a.get("role") == "link"):
                self.links_no_href += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "svg":
            self._svg = max(0, self._svg - 1)

    def handle_endtag(self, tag):
        if tag == "svg":
            self._svg = max(0, self._svg - 1)
        elif tag == "head":
            self._in_head = False
        elif tag == "title" and self._title is not None:
            self.titles.append("".join(self._title))
            self._title = None
        elif tag == "script" and self._script is not None:
            self.jsonld.append(("".join(self._script[0]), self._script[1]))
            self._script = None

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
        if self._script is not None:
            self._script[0].append(data)

    def _meta(self, a, line):
        name = a.get("name", "").strip().lower()
        prop = a.get("property", "").strip().lower()
        content = a.get("content", "")
        if a.get("http-equiv", "").strip().lower() == "refresh":
            self.refresh = True
        if name == "description":
            self.descriptions.append(content)
        elif name in ("robots", self.agent):
            self.robots.append((name, content))
        elif name == "viewport":
            self.viewport = True
        elif name == "keywords":
            self.keywords = True
        key = prop or name
        if key.startswith("og:"):
            self.og.setdefault(key, content.strip())
        elif key.startswith("twitter:"):
            self.twitter.setdefault(key, content.strip())

    def _link(self, a, line):
        rels = a.get("rel", "").lower().split()
        href = a.get("href", "")
        if "canonical" in rels:
            self.canonicals.append((href.strip(), line, self._seen_body and not self._in_head))
        if "alternate" in rels and "hreflang" in a:
            self.hreflangs.append((a["hreflang"].strip(), href.strip(), line))
        if "stylesheet" in rels and href:
            self.resources.append(href)


class Page:
    def __init__(self, path, rel, parser, agent):
        self.path, self.rel, self.p = path, rel, parser
        directives = set()
        for name, content in parser.robots:
            if name == "robots" or name == agent:
                directives |= {d.strip().lower() for d in content.split(",") if d.strip()}
        self.directives = directives
        self.noindex = "noindex" in directives or "none" in directives
        self.canonical = parser.canonicals[0][0] if len(parser.canonicals) == 1 else None
        self.self_urls = set()
        self.url_path = None


def page_paths(rel, clean_urls):
    """URL paths a static host typically serves for a file, primary first."""
    rel = rel.replace(os.sep, "/")
    name = rel.rsplit("/", 1)[-1]
    folder = rel[: -len(name)]
    if name.lower() in ("index.html", "index.htm"):
        base = "/" + folder
        alts = [base, "/" + rel]
        if base != "/":
            alts.append(base.rstrip("/"))
        return alts
    stem = "/" + rel.rsplit(".", 1)[0]
    return [stem, "/" + rel] if clean_urls else ["/" + rel, stem]


def parse_page(path, rel, agent):
    with open(path, "rb") as f:
        raw = f.read(MAX_HTML_BYTES)
    parser = PageParser(agent)
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return Page(path, rel, parser, agent)


def check_page(pg, args, base, by_url):
    p, rel, out = pg.p, pg.rel, []
    if not p.titles:
        out.append(finding("TITLE_MISSING", rel))
    else:
        if len(p.titles) > 1:
            out.append(finding("TITLE_MULTIPLE", rel, f"{len(p.titles)} <title> elements"))
        title = " ".join(p.titles[0].split())
        if not title:
            out.append(finding("TITLE_EMPTY", rel))
        elif len(title) > args.title_max:
            out.append(finding("TITLE_LONG", rel, f"title is {len(title)} characters: \"{short(title)}\""))
    if not p.descriptions:
        out.append(finding("META_DESC_MISSING", rel))
    else:
        if len(p.descriptions) > 1:
            out.append(finding("META_DESC_MULTIPLE", rel, f"{len(p.descriptions)} meta descriptions"))
        desc = " ".join(p.descriptions[0].split())
        if not desc:
            out.append(finding("META_DESC_EMPTY", rel))
        elif len(desc) > args.desc_max:
            out.append(finding("META_DESC_LONG", rel, f"meta description is {len(desc)} characters"))
    if p.keywords:
        out.append(finding("META_KEYWORDS", rel))
    if p.refresh:
        out.append(finding("META_REFRESH", rel))
    if not p.viewport:
        out.append(finding("VIEWPORT_MISSING", rel))
    if not p.lang:
        out.append(finding("HTML_LANG_MISSING", rel))
    if p.h1 == 0:
        out.append(finding("H1_MISSING", rel))
    elif p.h1 > 1:
        out.append(finding("H1_MULTIPLE", rel, f"{p.h1} <h1> headings"))
    if pg.noindex:
        out.append(finding("ROBOTS_META_NOINDEX", rel))
    if "index" in pg.directives and pg.noindex:
        out.append(finding("ROBOTS_META_CONFLICT", rel))
    out += check_canonical(pg, base, by_url)
    out += check_hreflang(pg, base, by_url)
    if p.img_no_alt:
        examples = ", ".join(short(s, 40) for s in p.img_no_alt[:3])
        out.append(finding("IMG_ALT_MISSING", rel, f"{len(p.img_no_alt)} image(s) without alt, e.g. {examples}"))
    if p.img_no_dims:
        out.append(finding("IMG_NO_DIMENSIONS", rel, f"{p.img_no_dims} image(s) without width and height"))
    if p.links_no_href:
        out.append(finding("LINK_NO_HREF", rel, f"{p.links_no_href} clickable <a> element(s) without an href"))
    for text, line in p.jsonld:
        out += check_jsonld(text, rel, line)
    out += check_social(pg)
    return out


def resolve(href, pg, base):
    page_url = (base.rstrip("/") + pg.url_path) if base else "https://site.invalid" + pg.url_path
    return urljoin(page_url, href)


def lookup(url, base, by_url):
    """Find the page in the build that serves an absolute URL on the --base-url host."""
    if not base:
        return None
    parts, base_parts = urlsplit(url), urlsplit(base)
    if (parts.hostname or "").lower() != (base_parts.hostname or "").lower():
        return None
    path = unquote(parts.path or "/")
    prefix = base_parts.path.rstrip("/")
    if prefix:
        if not (path == prefix or path.startswith(prefix + "/")):
            return None
        path = path[len(prefix):] or "/"
    return by_url.get(path)


def same_host(url, base):
    return bool(base) and (urlsplit(url).hostname or "").lower() == (urlsplit(base).hostname or "").lower()


def check_canonical(pg, base, by_url):
    p, rel, out = pg.p, pg.rel, []
    if not p.canonicals:
        if not pg.noindex:
            out.append(finding("CANONICAL_MISSING", rel))
        return out
    if len(p.canonicals) > 1:
        out.append(finding("CANONICAL_MULTIPLE", rel, f"{len(p.canonicals)} canonical links", p.canonicals[1][1]))
    for href, line, in_body in p.canonicals:
        if in_body:
            out.append(finding("CANONICAL_IN_BODY", rel, line=line))
        if not href:
            out.append(finding("CANONICAL_EMPTY", rel, line=line))
        elif not is_absolute_http(href):
            out.append(finding("CANONICAL_RELATIVE", rel, f"canonical \"{short(href, 60)}\" is not absolute", line))
    if pg.canonical and is_absolute_http(pg.canonical):
        target_url = normalize_url(pg.canonical)
        points_elsewhere = target_url not in pg.self_urls if pg.self_urls else False
        if pg.noindex and points_elsewhere:
            out.append(finding("NOINDEX_WITH_CANONICAL", rel))
        if same_host(pg.canonical, base):
            target = lookup(pg.canonical, base, by_url)
            if target is None:
                out.append(finding("CANONICAL_TARGET_NOT_FOUND", rel, f"no page in the build for {short(pg.canonical, 70)}"))
            elif target is not pg:
                if target.noindex:
                    out.append(finding("CANONICAL_TO_NOINDEX", rel, f"canonical target {target.rel} is noindex"))
                if target.canonical and is_absolute_http(target.canonical) and \
                        normalize_url(target.canonical) not in target.self_urls:
                    out.append(finding("CANONICAL_CHAIN", rel, f"{target.rel} canonicalizes to {short(target.canonical, 60)}"))
    return out


def hreflang_problem(code):
    if code.lower() == "x-default":
        return None
    parts = code.split("-")
    lang = parts[0].lower()
    if lang not in ISO639_1:
        hint = LANG_HINTS.get(lang)
        return "HREFLANG_INVALID", f"'{parts[0]}' is not an ISO 639-1 language code" + (f"; did you mean '{hint}'?" if hint else "")
    rest = parts[1:]
    if rest and len(rest[0]) == 4 and rest[0].isalpha():
        rest = rest[1:]
    if not rest:
        return None
    region = rest[0]
    if len(rest) > 1:
        return "HREFLANG_INVALID", f"'{code}' has too many subtags"
    if region.isdigit() and len(region) == 3:
        return "HREFLANG_UNUSUAL_REGION", f"'{code}' uses the numeric region {region}"
    if region.upper() == "UK":
        return "HREFLANG_INVALID", f"'{code}': the ISO 3166-1 code for the United Kingdom is GB"
    if region.upper() not in ISO3166_ALPHA2:
        return "HREFLANG_INVALID", f"'{region}' in '{code}' is not an ISO 3166-1 alpha-2 region"
    return None


def check_hreflang(pg, base, by_url):
    rel, out, entries = pg.rel, [], pg.p.hreflangs
    if not entries:
        return out
    seen, urls = {}, set()
    for code, href, line in entries:
        problem = hreflang_problem(code)
        if problem:
            out.append(finding(problem[0], rel, problem[1], line))
        if not is_absolute_http(href):
            out.append(finding("HREFLANG_RELATIVE", rel, f"hreflang=\"{code}\" href \"{short(href, 50)}\" is not absolute", line))
            continue
        url = normalize_url(href)
        urls.add(url)
        key = code.lower()
        if key in seen and seen[key] != url:
            out.append(finding("HREFLANG_DUPLICATE", rel, f"hreflang=\"{code}\" points to two URLs", line))
        seen.setdefault(key, url)
    if "x-default" not in seen:
        out.append(finding("HREFLANG_NO_XDEFAULT", rel))
    mine = set(pg.self_urls)
    if pg.canonical and is_absolute_http(pg.canonical):
        mine.add(normalize_url(pg.canonical))
    if mine and not (urls & mine):
        out.append(finding("HREFLANG_NO_SELF", rel))
    for url in sorted(urls - mine):
        if not same_host(url, base):
            continue
        target = lookup(url, base, by_url)
        if target is None:
            out.append(finding("HREFLANG_TARGET_NOT_FOUND", rel, f"no page in the build for {short(url, 70)}"))
            continue
        if target is pg:
            continue
        back = {normalize_url(h) for _, h, _ in target.p.hreflangs if is_absolute_http(h)}
        if not (back & mine):
            out.append(finding("HREFLANG_NO_RETURN", rel, f"{target.rel} does not list this page in its hreflang set"))
    return out


def walk_types(node, types, keys):
    if isinstance(node, dict):
        t = node.get("@type")
        for value in (t if isinstance(t, list) else [t]):
            if isinstance(value, str):
                types.add(value.split(":")[-1].split("/")[-1])
        for k, v in node.items():
            keys.add(k)
            walk_types(v, types, keys)
    elif isinstance(node, list):
        for item in node:
            walk_types(item, types, keys)


def mentions_schema_org(ctx):
    if isinstance(ctx, str):
        return "schema.org" in ctx
    if isinstance(ctx, list):
        return any(mentions_schema_org(c) for c in ctx)
    if isinstance(ctx, dict):
        return any(mentions_schema_org(v) for v in ctx.values())
    return False


def check_jsonld(text, rel, line):
    body = text.strip()
    if body.startswith("<!--"):
        body = body[4:]
    if body.endswith("-->"):
        body = body[:-3]
    try:
        data = json.loads(body)
    except ValueError as e:
        return [finding("JSONLD_INVALID", rel, f"JSON-LD does not parse: {e}", line)]
    out = []
    tops = data if isinstance(data, list) else [data]
    for top in tops:
        if not isinstance(top, dict):
            out.append(finding("JSONLD_NO_TYPE", rel, "JSON-LD item is not an object", line))
            continue
        if not mentions_schema_org(top.get("@context")):
            out.append(finding("JSONLD_NO_CONTEXT", rel, line=line))
        entities = top["@graph"] if isinstance(top.get("@graph"), list) else [top]
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            is_reference = set(ent) <= {"@id", "@context"}
            if "@type" not in ent and not is_reference:
                out.append(finding("JSONLD_NO_TYPE", rel, line=line))
    types, keys = set(), set()
    walk_types(data, types, keys)
    for t in sorted(types & set(RETIRED_TYPES)):
        out.append(finding("JSONLD_RETIRED_FEATURE", rel, f"{t}: {RETIRED_TYPES[t]}; check Google's Search Gallery", line))
    if types & REVIEW_TYPES or keys & REVIEW_KEYS:
        out.append(finding("JSONLD_REVIEW_MARKUP", rel, line=line))
    return out


def check_social(pg):
    p, rel, out = pg.p, pg.rel, []
    if not p.og:
        out.append(finding("OG_MISSING", rel))
    else:
        missing = [k for k in ("og:title", "og:type", "og:image", "og:url") if not p.og.get(k)]
        if missing:
            out.append(finding("OG_INCOMPLETE", rel, "missing " + ", ".join(missing)))
        image = p.og.get("og:image")
        if image and not is_absolute_http(image):
            out.append(finding("OG_IMAGE_RELATIVE", rel, f"og:image \"{short(image, 60)}\" is not absolute"))
        og_url = p.og.get("og:url")
        if og_url and pg.canonical and is_absolute_http(og_url) and is_absolute_http(pg.canonical) \
                and normalize_url(og_url) != normalize_url(pg.canonical):
            out.append(finding("OG_URL_MISMATCH", rel))
    card = p.twitter.get("twitter:card")
    if card is not None and card.lower() not in TWITTER_CARDS:
        out.append(finding("TWITTER_CARD_INVALID", rel, f"twitter:card is \"{short(card, 40)}\""))
    return out


def check_duplicates(pages):
    out = []
    for attr, rule in (("title", "TITLE_DUPLICATE"), ("desc", "META_DESC_DUPLICATE")):
        groups = {}
        for pg in pages:
            if pg.noindex or (pg.canonical and is_absolute_http(pg.canonical) and pg.self_urls
                              and normalize_url(pg.canonical) not in pg.self_urls):
                continue
            values = pg.p.titles if attr == "title" else pg.p.descriptions
            value = " ".join(values[0].split()).casefold() if values else ""
            if value:
                groups.setdefault(value, []).append(pg.rel)
        for value, rels in sorted(groups.items()):
            if len(rels) > 1:
                rels = sorted(rels)
                others = ", ".join(rels[1:6]) + (" ..." if len(rels) > 6 else "")
                out.append(finding(rule, rels[0], f"shared by {len(rels)} pages: also {others}"))
    return out


# ---------------------------------------------------------------- robots.txt

class Robots:
    def __init__(self, text):
        self.groups, self.sitemaps, self.issues = [], [], []
        current, last_was_agent = None, False
        for number, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                self.issues.append(("ROBOTS_SYNTAX", f"\"{short(line, 50)}\"", number))
                continue
            field, value = line.split(":", 1)
            field, value = field.strip().lower(), value.strip()
            if field == "user-agent":
                if current is None or not last_was_agent:
                    current = {"agents": [], "rules": [], "line": number}
                    self.groups.append(current)
                current["agents"].append(value.lower())
                last_was_agent = True
                continue
            if field in ("allow", "disallow"):
                last_was_agent = False   # the next user-agent line starts a new group
                if current is None:
                    self.issues.append(("ROBOTS_RULE_OUTSIDE_GROUP", "", number))
                    continue
                if value and not value.startswith(("/", "*")):
                    self.issues.append(("ROBOTS_PATH_FORMAT", f"\"{short(value, 50)}\"", number))
                if value:
                    current["rules"].append((field == "allow", value, number))
            elif field == "sitemap":
                self.sitemaps.append((value, number))
            elif field == "noindex":
                self.issues.append(("ROBOTS_NOINDEX_LINE", "", number))
            elif field == "crawl-delay":
                self.issues.append(("ROBOTS_CRAWL_DELAY", "", number))
            elif field not in ROBOTS_FIELDS:
                self.issues.append(("ROBOTS_UNKNOWN_FIELD", f"\"{field}\"", number))

    def rules_for(self, agent):
        agent = agent.lower()
        chosen = [g for g in self.groups if agent in g["agents"]]
        if not chosen:
            chosen = [g for g in self.groups if "*" in g["agents"]]
        return [rule for g in chosen for rule in g["rules"]]

    @staticmethod
    def matches(pattern, path):
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        regex = ".*".join(re.escape(part) for part in body.split("*"))
        return re.match(regex + ("$" if anchored else ""), path) is not None

    def allowed(self, agent, path):
        """RFC 9309: the longest matching rule wins; allow wins a tie. Returns (allowed, rule)."""
        if path == "/robots.txt":
            return True, None
        best = None
        for allow, pattern, number in self.rules_for(agent):
            if self.matches(pattern, path):
                key = (len(pattern), allow)
                if best is None or key > best[0]:
                    best = (key, (allow, pattern, number))
        return (True, None) if best is None else (best[1][0], best[1])


def check_robots(text, size, rel):
    robots = Robots(text)
    out = [finding(rule, rel, f"{RULES[rule][1]}: {detail}" if detail else "", number)
           for rule, detail, number in robots.issues]
    if size > MAX_ROBOTS_BYTES:
        out.append(finding("ROBOTS_TOO_LARGE", rel, f"{size} bytes"))
    for group in robots.groups:
        paths = {p for allow, p, _ in group["rules"] if not allow}
        allows = [p for allow, p, _ in group["rules"] if allow]
        if paths & {"/", "/*"} and not allows:
            agents = ", ".join(group["agents"])
            rule = "ROBOTS_DISALLOW_ALL" if set(group["agents"]) & SEARCH_AGENTS else "ROBOTS_AGENT_BLOCKED"
            out.append(finding(rule, rel, f"user-agent {agents} is disallowed from the whole site", group["line"]))
    for url, number in robots.sitemaps:
        if not is_absolute_http(url):
            out.append(finding("ROBOTS_SITEMAP_RELATIVE", rel, f"Sitemap \"{short(url, 60)}\" is not absolute", number))
    return robots, out


# ---------------------------------------------------------------- sitemaps

def read_limited(path):
    opener = gzip.open if path.lower().endswith(".gz") else open
    with opener(path, "rb") as f:
        return f.read(MAX_SITEMAP_BYTES + 1)


def valid_lastmod(value):
    m = W3C_DATETIME.match(value.strip())
    if not m:
        return False
    year, month, day, hour, minute, second = m.groups()
    try:
        date(int(year), int(month or 1), int(day or 1))
    except ValueError:
        return False
    return (hour is None or int(hour) < 24) and (minute is None or int(minute) < 60) and \
        (second is None or int(second) < 61)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def check_sitemap(path, rel, ctx):
    out = []
    try:
        raw = read_limited(path)
    except (OSError, EOFError) as e:
        return [finding("SITEMAP_PARSE", rel, f"cannot read: {e}")], []
    if len(raw) > MAX_SITEMAP_BYTES:
        return [finding("SITEMAP_TOO_LARGE", rel)], []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return [finding("SITEMAP_PARSE", rel, f"XML error: {e}")], []
    kind = local(root.tag)
    if kind not in ("urlset", "sitemapindex"):
        return [finding("SITEMAP_ROOT", rel, f"root element is <{kind}>")], []
    if not root.tag.startswith("{" + SITEMAP_NS + "}"):
        out.append(finding("SITEMAP_NAMESPACE", rel))
    child_name = "url" if kind == "urlset" else "sitemap"
    entries = [e for e in root if local(e.tag) == child_name]
    if len(entries) > 50_000:
        out.append(finding("SITEMAP_TOO_MANY", rel, f"{len(entries)} entries"))
    seen, children, ignored = set(), [], False
    robots, base, agent = ctx["robots"], ctx["base"], ctx["agent"]
    for entry in entries:
        fields = {local(c.tag): (c.text or "").strip() for c in entry}
        ignored = ignored or "priority" in fields or "changefreq" in fields
        loc = fields.get("loc", "")
        if not loc:
            out.append(finding("SITEMAP_LOC_MISSING", rel))
            continue
        if not is_absolute_http(loc):
            out.append(finding("SITEMAP_LOC_INVALID", rel, f"\"{short(loc, 70)}\""))
            continue
        if "lastmod" in fields and not valid_lastmod(fields["lastmod"]):
            out.append(finding("SITEMAP_LASTMOD_INVALID", rel, f"\"{short(fields['lastmod'], 40)}\" for {short(loc, 60)}"))
        url = normalize_url(loc)
        if url in seen:
            out.append(finding("SITEMAP_DUPLICATE", rel, f"{short(loc, 70)}"))
            continue
        seen.add(url)
        if kind == "sitemapindex":
            children.append(loc)
            continue
        if base and not same_host(loc, base):
            out.append(finding("SITEMAP_CROSS_HOST", rel, f"{short(loc, 70)}"))
            continue
        parts = urlsplit(loc)
        target_path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        if robots is not None:
            ok, rule = robots.allowed(agent, target_path)
            if not ok:
                out.append(finding("SITEMAP_URL_DISALLOWED", rel, f"{short(loc, 60)} (robots.txt line {rule[2]}: {rule[1]})"))
        if base:
            page = lookup(loc, base, ctx["by_url"])
            if page is None:
                out.append(finding("SITEMAP_URL_NOT_FOUND", rel, f"{short(loc, 70)}"))
            elif page.noindex:
                out.append(finding("SITEMAP_URL_NOINDEX", rel, f"{short(loc, 60)} ({page.rel})"))
            elif page.canonical and is_absolute_http(page.canonical) and normalize_url(page.canonical) != url \
                    and normalize_url(page.canonical) not in page.self_urls:
                out.append(finding("SITEMAP_URL_NOT_CANONICAL", rel, f"{short(loc, 50)} declares {short(page.canonical, 50)}"))
    if ignored:
        out.append(finding("SITEMAP_IGNORED_TAGS", rel))
    return out, children


# ---------------------------------------------------------------- driver

def collect(paths, max_files):
    pages, robots_files, sitemaps, truncated = [], [], [], False
    root = None
    for given in paths:
        if os.path.isdir(given):
            root = root or given
            for dirpath, dirnames, filenames in os.walk(given):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
                for name in sorted(filenames):
                    full = os.path.join(dirpath, name)
                    lower = name.lower()
                    if lower.endswith((".html", ".htm")):
                        if len(pages) >= max_files:
                            truncated = True
                            continue
                        pages.append(full)
                    elif dirpath == given and lower == "robots.txt":
                        robots_files.append(full)
                    elif dirpath == given and lower.startswith("sitemap") and lower.endswith((".xml", ".xml.gz")):
                        sitemaps.append(full)
        elif os.path.isfile(given):
            lower = os.path.basename(given).lower()
            if lower == "robots.txt":
                robots_files.append(given)
            elif lower.endswith((".xml", ".xml.gz")):
                sitemaps.append(given)
            else:
                pages.append(given)
        else:
            raise FileNotFoundError(given)
    if root is None:
        root = os.path.dirname(os.path.abspath(paths[0]))
    return root, pages, robots_files, sitemaps, truncated


def display(path, root):
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = path
    return path if rel.startswith("..") else rel.replace(os.sep, "/")


def run(args):
    base = args.base_url.rstrip("/") if args.base_url else None
    root, page_files, robots_files, sitemap_files, truncated = collect(args.paths, args.max_files)
    root = args.site_root or root
    if args.robots:
        robots_files = [args.robots]
    sitemap_files = list(dict.fromkeys(sitemap_files + (args.sitemap or [])))
    findings = []
    if truncated:
        findings.append(finding("SCAN_LIMIT", display(root, root), f"stopped after {args.max_files} HTML files"))

    pages, by_url = [], {}
    for path in page_files:
        rel = display(path, root)
        pg = parse_page(path, rel, args.agent.lower())
        alternatives = page_paths(rel, args.clean_urls) if not rel.startswith("/") else ["/" + os.path.basename(path)]
        pg.url_path = alternatives[0]
        if base:
            pg.self_urls = {normalize_url(base + a) for a in alternatives}
        for a in alternatives:
            by_url.setdefault(unquote(a), pg)
        pages.append(pg)

    robots = None
    if robots_files:
        path = robots_files[0]
        with open(path, "rb") as f:
            raw = f.read()
        robots, robot_findings = check_robots(raw.decode("utf-8-sig", errors="replace"), len(raw), display(path, root))
        findings += robot_findings

    for pg in pages:
        findings += check_page(pg, args, base, by_url)
        if robots is not None:
            ok, rule = robots.allowed(args.agent, pg.url_path)
            if not ok:
                extra = "; its noindex can never be read" if pg.noindex else ""
                findings.append(finding("PAGE_DISALLOWED", pg.rel,
                                        f"{pg.url_path} blocked for {args.agent} by line {rule[2]} ({rule[1]}){extra}"))
    findings += check_duplicates(pages)

    if robots is not None:
        blocked = {}
        for pg in pages:
            for href in pg.p.resources:
                url = resolve(href, pg, base)
                if (base and not same_host(url, base)) or (not base and urlsplit(url).hostname != "site.invalid"):
                    continue
                parts = urlsplit(url)
                path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
                ok, rule = robots.allowed(args.agent, path)
                if not ok:
                    blocked.setdefault((path, rule[2], rule[1]), set()).add(pg.rel)
        for (path, number, pattern), rels in sorted(blocked.items()):
            findings.append(finding("RESOURCE_DISALLOWED", display(robots_files[0], root),
                                    f"{path} blocked by line {number} ({pattern}); used by {len(rels)} page(s)", number))

    ctx = {"robots": robots, "base": base, "agent": args.agent, "by_url": by_url}
    queue, done, processed, child_urls = list(sitemap_files), set(), [], set()
    if robots is not None and base:
        for url, _ in robots.sitemaps:
            candidate = local_file(url, base, root)
            if candidate:
                queue.append(candidate)
    while queue:
        path = queue.pop(0)
        real = os.path.realpath(path)
        if real in done:
            continue
        done.add(real)
        rel = display(path, root)
        processed.append(rel)
        sm_findings, children = check_sitemap(path, rel, ctx)
        findings += sm_findings
        for loc in children:
            child_urls.add(normalize_url(loc))
            candidate = local_file(loc, base, root)
            if candidate:
                queue.append(candidate)
    if robots is not None and base:
        listed = {normalize_url(u) for u, _ in robots.sitemaps if is_absolute_http(u)}
        for rel in processed:
            if rel.startswith(("/", "..")) or "/" in rel:
                continue                 # only sitemaps at the site root are expected in robots.txt
            own = normalize_url(base + "/" + rel)
            if own not in listed and own not in child_urls:
                findings.append(finding("SITEMAP_NOT_IN_ROBOTS", rel))

    ignore = set(args.ignore)
    findings = [f for f in findings if f["rule"] not in ignore]
    findings.sort(key=lambda f: (f["file"], f["line"] or 0, -RANK[f["severity"]], f["rule"], f["message"]))
    return findings, len(page_files)


def local_file(url, base, root):
    """Map a sitemap URL on the --base-url host to a file under the site root, if it exists."""
    if not base or not same_host(url, base):
        return None
    path = unquote(urlsplit(url).path)
    prefix = urlsplit(base).path.rstrip("/")
    if prefix and path.startswith(prefix + "/"):
        path = path[len(prefix):]
    top = os.path.abspath(root)
    candidate = os.path.abspath(os.path.join(top, path.lstrip("/")))
    if os.path.commonpath([candidate, top]) != top or not os.path.isfile(candidate):
        return None
    return candidate


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="seo_check.py",
        description="Offline checks for built HTML pages, robots.txt and XML sitemaps. Read-only, no network.",
        epilog="Exit codes: 0 no findings at or above --fail-on, 1 findings, 2 usage error.")
    ap.add_argument("paths", nargs="*", help="build folder(s) or individual .html, robots.txt and sitemap .xml files")
    ap.add_argument("--base-url", help="public origin of the site, e.g. https://www.example.com (enables cross-page checks)")
    ap.add_argument("--site-root", help="folder that maps to / on the site (default: first folder given)")
    ap.add_argument("--clean-urls", action="store_true", help="pages are served without .html (about.html -> /about)")
    ap.add_argument("--robots", help="robots.txt to use (default: robots.txt at the site root)")
    ap.add_argument("--sitemap", action="append", help="extra sitemap file to check (repeatable)")
    ap.add_argument("--agent", default="googlebot", help="robots.txt user-agent token to evaluate (default: googlebot)")
    ap.add_argument("--title-max", type=int, default=70, help="advisory title length (default: 70)")
    ap.add_argument("--desc-max", type=int, default=170, help="advisory meta description length (default: 170)")
    ap.add_argument("--max-files", type=int, default=20000, help="stop after this many HTML files (default: 20000)")
    ap.add_argument("--ignore", default="", help="comma-separated rule IDs to skip")
    ap.add_argument("--fail-on", choices=["error", "warn", "info", "never"], default="error",
                    help="lowest severity that makes the exit code 1 (default: error)")
    ap.add_argument("--strict", action="store_true", help="same as --fail-on warn")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--list-rules", action="store_true", help="list rule IDs and exit")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = ap.parse_args(argv)
    args.ignore = [r.strip().upper() for r in args.ignore.split(",") if r.strip()]
    unknown = [r for r in args.ignore if r not in RULES]
    if unknown:
        ap.error("unknown rule ID(s) in --ignore: " + ", ".join(unknown))
    if args.base_url and not is_absolute_http(args.base_url):
        ap.error("--base-url must be an absolute http or https URL")
    if args.strict:
        args.fail_on = "warn"
    if not args.paths and not args.list_rules:
        ap.error("give at least one folder or file to check")
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list_rules:
        for rule, (severity, text) in RULES.items():
            print(f"{rule:28s} {severity:5s}  {text}")
        return 0
    try:
        findings, page_count = run(args)
    except FileNotFoundError as e:
        print(f"seo_check.py: error: no such file or folder: {e}", file=sys.stderr)
        return 2
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    if args.json:
        print(json.dumps({"version": VERSION, "pages": page_count, "summary": counts, "findings": findings},
                         indent=2, sort_keys=True))
    else:
        current = None
        for f in findings:
            if f["file"] != current:
                current = f["file"]
                print(current)
            where = f"line {f['line']}: " if f["line"] else ""
            print(f"  {f['severity'].upper():5s}  {f['rule']:26s} {where}{f['message']}")
        print(f"Checked {page_count} page(s): {counts['error']} error(s), {counts['warn']} warning(s), "
              f"{counts['info']} info. Offline check of files as built; headers, redirects and "
              f"JavaScript output were not seen.")
    threshold = RANK[args.fail_on]
    return 1 if any(RANK[f["severity"]] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
