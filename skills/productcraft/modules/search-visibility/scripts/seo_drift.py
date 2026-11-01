#!/usr/bin/env python3
"""Snapshot the search-relevant state of a built site and diff two snapshots.

`snapshot` reads a folder of built pages (a static export or build output),
its robots.txt and its XML sitemaps, and records per page: title, meta
description, canonical, meta robots, h1, html lang, hreflang alternates,
JSON-LD types and a content hash, core Open Graph tags, visible word count and
text hash, how many other pages link to it, and whether robots.txt blocks it
for the chosen agent. `diff` compares two snapshots (or a snapshot and a build
folder) and reports regressions by severity, for example a noindex that
appeared, a self-canonical page that now points elsewhere, a page robots.txt
now blocks, or URLs that left the sitemaps.

Standard library only. Read-only: it writes nothing unless --out is given.
No network access. Deterministic output (no timestamps unless --label).
Like any build check it cannot see HTTP headers, status codes, redirects or
anything JavaScript adds; confirm those on the live site.

Exit codes: 0 = no finding at or above --fail-on, 1 = at least one,
2 = usage or input error.
"""

import argparse
import fnmatch
import gzip
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

VERSION = "1.0.0"
FORMAT = "seo-drift-snapshot/1"
RANK = {"info": 0, "warn": 1, "error": 2, "never": 3}
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_XML_BYTES = 60 * 1024 * 1024
PLACEHOLDER_HOST = "build.invalid"

RULES = {
    # pages
    "PAGE_REMOVED": ("error", "An indexable page in the old build is missing from the new one; confirm a redirect or a deliberate 404/410"),
    "PAGE_REMOVED_NONINDEXABLE": ("info", "A page that was noindex, canonicalized elsewhere or blocked is gone"),
    "PAGE_ADDED": ("info", "New page in the build"),
    "NOINDEX_ADDED": ("error", "noindex added to a page that was indexable"),
    "NOINDEX_REMOVED": ("warn", "noindex removed: the page can now be indexed; confirm it should be public"),
    "NOFOLLOW_ADDED": ("warn", "nofollow added to meta robots"),
    "ROBOTS_META_CHANGED": ("warn", "Other meta robots directives changed (snippet or preview limits, for example)"),
    "CANONICAL_NOW_ELSEWHERE": ("error", "A self-canonical page now declares another URL as canonical"),
    "CANONICAL_CHANGED": ("warn", "Canonical target changed"),
    "CANONICAL_REMOVED": ("warn", "Canonical link removed"),
    "CANONICAL_ADDED": ("info", "Canonical link added"),
    "PAGE_NOW_BLOCKED": ("error", "robots.txt now disallows this page for the chosen agent"),
    "PAGE_UNBLOCKED": ("info", "robots.txt no longer disallows this page"),
    "TITLE_REMOVED": ("error", "Title removed or empty"),
    "TITLE_CHANGED": ("info", "Title text changed"),
    "DESCRIPTION_REMOVED": ("warn", "Meta description removed or empty"),
    "DESCRIPTION_CHANGED": ("info", "Meta description changed"),
    "H1_REMOVED": ("warn", "No h1 any more"),
    "H1_CHANGED": ("info", "h1 text changed"),
    "LANG_CHANGED": ("warn", "html lang attribute changed"),
    "HREFLANG_REMOVED": ("warn", "hreflang alternate removed"),
    "HREFLANG_CHANGED": ("warn", "hreflang alternate points to a different URL"),
    "HREFLANG_ADDED": ("info", "hreflang alternate added"),
    "JSONLD_REMOVED": ("warn", "All JSON-LD removed from the page"),
    "JSONLD_TYPE_REMOVED": ("warn", "A structured data type disappeared from the page"),
    "JSONLD_TYPE_ADDED": ("info", "A structured data type was added"),
    "JSONLD_NOW_INVALID": ("error", "More JSON-LD blocks fail to parse than before"),
    "JSONLD_CHANGED": ("info", "JSON-LD content changed"),
    "OG_REMOVED": ("warn", "Open Graph tags removed"),
    "OG_CHANGED": ("info", "Open Graph title, description, type, image or URL changed"),
    "TEXT_SHRANK": ("warn", "Visible main text shrank by more than --text-drop"),
    "TEXT_CHANGED": ("info", "Visible main text changed"),
    "PAGE_ORPHANED": ("warn", "Other pages in the build linked here before; none do now"),
    # robots.txt
    "ROBOTS_FILE_REMOVED": ("warn", "robots.txt is gone; crawlers treat a 404 as no restrictions"),
    "ROBOTS_FILE_ADDED": ("info", "robots.txt added"),
    "ROBOTS_DISALLOW_ALL_NEW": ("error", "robots.txt now blocks the whole site for * or the chosen agent"),
    "ROBOTS_RULES_CHANGED": ("warn", "robots.txt rules or sitemap lines changed"),
    # sitemaps
    "SITEMAPS_GONE": ("error", "The old build had sitemaps; the new one has none"),
    "SITEMAP_URL_REMOVED": ("warn", "URL no longer listed in any sitemap"),
    "SITEMAP_URL_ADDED": ("info", "URL newly listed in a sitemap"),
    # snapshots
    "OPTIONS_DIFFER": ("warn", "The snapshots were taken with different options; some differences may be artifacts"),
    "SCAN_LIMIT": ("info", "A snapshot hit --max-files; pages past the limit were not compared"),
}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
NO_TEXT = {"script", "style", "noscript", "template", "svg", "head", "title", "nav", "header",
           "footer", "aside", "button", "select", "option", "textarea"}
OG_KEYS = ("og:title", "og:description", "og:type", "og:image", "og:url")
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "ftp:")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def squash(text):
    return " ".join((text or "").split())


def normalize_url(url):
    """Lowercase scheme and host, drop default ports and the fragment, keep path and query."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host + (f":{port}" if port and port not in (80, 443) else "")
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


# ---------------------------------------------------------------- HTML

class SnapParser(HTMLParser):
    def __init__(self, agent):
        super().__init__(convert_charrefs=True)
        self.agent = agent
        self.titles, self.descriptions, self.robots, self.canonicals = [], [], [], []
        self.hreflang, self.og, self.twitter_card = {}, {}, None
        self.h1, self.jsonld, self.hrefs = [], [], []
        self.lang = None
        self.main_words, self.body_words = [], []
        self.stack = []
        self._title = self._h1 = self._script = None

    # tag bookkeeping ------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "").strip().lower() or None
        elif tag == "title" and "svg" not in self.stack:
            self._title = []
        elif tag == "h1":
            self._h1 = []
        elif tag == "meta":
            self._meta(a)
        elif tag == "link":
            self._link(a)
        elif tag == "script" and a.get("type", "").strip().lower() == "application/ld+json":
            self._script = []
        elif tag == "a" and a.get("href", "").strip():
            self.hrefs.append(a["href"].strip())
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag == "title" and self._title is not None:
            self.titles.append(squash("".join(self._title)))
            self._title = None
        elif tag == "h1" and self._h1 is not None:
            self.h1.append(squash("".join(self._h1)))
            self._h1 = None
        elif tag == "script" and self._script is not None:
            self.jsonld.append("".join(self._script))
            self._script = None
        if tag in self.stack:
            idx = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[idx:]

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
        if self._h1 is not None:
            self._h1.append(data)
        if self._script is not None:
            self._script.append(data)
            return
        if NO_TEXT & set(self.stack):
            return
        words = re.findall(r"\w+", data.lower())
        if not words:
            return
        (self.main_words if "main" in self.stack else self.body_words).extend(words)

    # head elements -------------------------------------------------
    def _meta(self, a):
        name = a.get("name", "").strip().lower()
        prop = a.get("property", "").strip().lower()
        content = a.get("content", "")
        if name == "description":
            self.descriptions.append(squash(content))
        elif name in ("robots", self.agent):
            self.robots.extend(d.strip().lower() for d in content.split(",") if d.strip())
        elif name == "twitter:card" and self.twitter_card is None:
            self.twitter_card = content.strip().lower()
        key = prop or name
        if key in OG_KEYS:
            self.og.setdefault(key, squash(content))

    def _link(self, a):
        rels = a.get("rel", "").lower().split()
        href = a.get("href", "").strip()
        if "canonical" in rels:
            self.canonicals.append(href)
        if "alternate" in rels and a.get("hreflang", "").strip():
            self.hreflang.setdefault(a["hreflang"].strip().lower(), href)


def jsonld_summary(blocks):
    parsed, invalid, types = [], 0, set()

    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            for value in (t if isinstance(t, list) else [t]):
                if isinstance(value, str) and value.strip():
                    types.add(value.strip().rsplit("/", 1)[-1])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for block in blocks:
        try:
            data = json.loads(block)
        except ValueError:
            invalid += 1
            continue
        parsed.append(data)
        walk(data)
    digest = sha(json.dumps(parsed, sort_keys=True, separators=(",", ":"))) if parsed else None
    return sorted(types), digest, invalid, len(blocks)


# ---------------------------------------------------------------- robots.txt

class Robots:
    """RFC 9309 groups; longest matching rule wins and allow wins a tie."""

    def __init__(self, text):
        self.groups, self.lines = [], []
        current, last_was_agent = None, False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, value = (part.strip() for part in line.split(":", 1))
            field = field.lower()
            if field == "user-agent":
                if current is None or not last_was_agent:
                    current = {"agents": [], "rules": []}
                    self.groups.append(current)
                current["agents"].append(value.lower())
                last_was_agent = True
            elif field in ("allow", "disallow"):
                last_was_agent = False
                if current is not None and value:
                    current["rules"].append((field == "allow", value))
                if current is not None:
                    self.lines.append(f"[{','.join(sorted(current['agents']))}] {field}: {value}")
            elif field == "sitemap":
                self.lines.append(f"[sitemap] {value}")
            else:   # crawl-delay and other extensions: recorded for the diff, no effect on matching
                agents = ",".join(sorted(current["agents"])) if current else "-"
                self.lines.append(f"[{agents}] {field}: {value}")

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
        if path == "/robots.txt":
            return True
        best = None
        for allow, pattern in self.rules_for(agent):
            if self.matches(pattern, path):
                key = (len(pattern), allow)
                if best is None or key > best:
                    best = key
        return True if best is None else best[1]


# ---------------------------------------------------------------- sitemaps

def local_name(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def read_sitemap(path):
    """Return (kind, locs) for a sitemap file, or (None, []) for other XML."""
    opener = gzip.open if path.lower().endswith(".gz") else open
    try:
        with opener(path, "rb") as f:
            raw = f.read(MAX_XML_BYTES + 1)
        if len(raw) > MAX_XML_BYTES:
            return None, []
        root = ET.fromstring(raw)
    except (OSError, ET.ParseError, EOFError, ValueError):
        return None, []
    kind = local_name(root.tag)
    if kind not in ("urlset", "sitemapindex"):
        return None, []
    locs = []
    for entry in root:
        for child in entry:
            if local_name(child.tag) == "loc" and (child.text or "").strip():
                locs.append(child.text.strip())
    return kind, locs


# ---------------------------------------------------------------- snapshot

def url_aliases(rel, clean_urls):
    """URL paths a static host typically serves for a file; primary first."""
    name = rel.rsplit("/", 1)[-1]
    folder = rel[: -len(name)]
    if name.lower() in ("index.html", "index.htm"):
        base = "/" + folder
        out = [base, "/" + rel]
        if base != "/":
            out.append(base.rstrip("/"))
        return out
    stem = "/" + rel.rsplit(".", 1)[0]
    return [stem, "/" + rel, stem + "/"] if clean_urls else ["/" + rel, stem, stem + "/"]


def collect(root, excludes, max_files):
    pages, xml_files, truncated = [], [], False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if any(fnmatch.fnmatch(rel, pattern) for pattern in excludes):
                continue
            lower = name.lower()
            if lower.endswith((".html", ".htm")):
                if len(pages) >= max_files:
                    truncated = True
                    continue
                pages.append((full, rel))
            elif lower.endswith((".xml", ".xml.gz")):
                xml_files.append((full, rel))
    return pages, xml_files, truncated


def resolve_internal(href, page_url, base_host):
    """Return the path of an internal link target, or None for external and special links."""
    if href.lower().startswith(SKIP_SCHEMES) or href.startswith("#"):
        return None
    try:
        target = urlsplit(urljoin(page_url, href))
    except ValueError:
        return None
    if target.scheme not in ("http", "https") or (target.hostname or "").lower() != base_host:
        return None
    return unquote(target.path or "/")


def snapshot(args):
    root = args.build
    if not os.path.isdir(root):
        raise UsageError(f"not a folder: {root}")
    base = args.base_url.rstrip("/") if args.base_url else None
    if base and urlsplit(base).scheme not in ("http", "https"):
        raise UsageError("--base-url must be an absolute http(s) URL")
    origin = base or f"https://{PLACEHOLDER_HOST}"
    base_host = (urlsplit(origin).hostname or "").lower()
    agent = args.agent.lower()

    files, xml_files, truncated = collect(root, args.exclude or [], args.max_files)
    alias, raw = {}, {}
    for full, rel in files:
        names = url_aliases(rel, args.clean_urls)
        key = names[0]
        if key in raw:
            continue
        for name in names:
            alias.setdefault(name, key)
        with open(full, "rb") as f:
            text = f.read(MAX_HTML_BYTES).decode("utf-8", errors="replace")
        parser = SnapParser(agent)
        parser.feed(text)
        parser.close()
        raw[key] = (rel, parser)

    def to_key(path):
        if path is None:
            return None
        for candidate in (path, path.rstrip("/") or "/", path + "/" if not path.endswith("/") else path):
            if candidate in alias:
                return alias[candidate]
        return None

    def display(url, page_url):
        """Absolute normalized URL, or the bare path for internal URLs when no --base-url was given."""
        if not url:
            return None
        try:
            absolute = normalize_url(urljoin(page_url, url))
        except ValueError:
            return url
        if not base and (urlsplit(absolute).hostname or "") == PLACEHOLDER_HOST:
            parts = urlsplit(absolute)
            return parts.path + (f"?{parts.query}" if parts.query else "")
        return absolute

    for given in [args.robots] + list(args.sitemap or []):
        if given and not os.path.isfile(given):
            raise UsageError(f"file not found: {given}")
    robots_path = args.robots or os.path.join(root, "robots.txt")
    robots = None
    robots_info = None
    if os.path.isfile(robots_path):
        with open(robots_path, "rb") as f:
            robots = Robots(f.read(600 * 1024).decode("utf-8", errors="replace"))
        robots_info = {
            "lines": robots.lines,
            "blocks_all": sorted(a for a in {"*", agent} if not robots.allowed(a, "/")),
        }

    inlinks = {key: 0 for key in raw}
    pages = {}
    for key in sorted(raw):
        rel, p = raw[key]
        page_url = origin + key
        targets = {to_key(resolve_internal(h, page_url, base_host)) for h in p.hrefs}
        for target in targets - {None, key}:
            inlinks[target] += 1
        canonical = display(p.canonicals[0], page_url) if p.canonicals else None
        canonical_key = None
        if p.canonicals and base:
            canonical_key = to_key(resolve_internal(p.canonicals[0], page_url, base_host))
        elif p.canonicals:   # no --base-url: the host is unknown, so compare paths only
            try:
                canonical_key = to_key(unquote(urlsplit(urljoin(page_url, p.canonicals[0])).path or "/"))
            except ValueError:
                canonical_key = None
        directives = sorted(set(p.robots))
        noindex = "noindex" in directives or "none" in directives
        blocked = bool(robots) and not robots.allowed(agent, key)
        canonical_self = canonical is None or canonical_key == key
        types, jdigest, jinvalid, jcount = jsonld_summary(p.jsonld)
        words = p.main_words or p.body_words
        pages[key] = {
            "file": rel,
            "title": p.titles[0] if p.titles else None,
            "description": p.descriptions[0] if p.descriptions else None,
            "canonical": canonical,
            "canonical_self": canonical_self,
            "robots": directives,
            "noindex": noindex,
            "blocked": blocked,
            "indexable": not noindex and canonical_self and not blocked,
            "h1": p.h1,
            "lang": p.lang,
            "hreflang": {code: display(href, page_url) for code, href in sorted(p.hreflang.items())},
            "jsonld_types": types,
            "jsonld_hash": jdigest,
            "jsonld_blocks": jcount,
            "jsonld_invalid": jinvalid,
            "og": {k: p.og[k] for k in OG_KEYS if k in p.og},
            "twitter_card": p.twitter_card,
            "words": len(words),
            "text_hash": sha(" ".join(words)) if words else None,
        }
    for key in pages:
        pages[key]["inlinks"] = inlinks[key]

    sitemap_files = list(xml_files) + [(path, os.path.basename(path)) for path in (args.sitemap or [])]
    sitemap_urls, sitemap_list = set(), []
    for full, rel in sorted(set(sitemap_files), key=lambda item: item[1]):
        kind, locs = read_sitemap(full)
        if kind is None:
            continue
        sitemap_list.append({"file": rel, "kind": kind, "entries": len(locs)})
        if kind == "urlset":
            sitemap_urls.update(normalize_url(loc) for loc in locs)

    snap = {
        "format": FORMAT,
        "tool_version": VERSION,
        "options": {"base_url": base, "agent": agent, "clean_urls": bool(args.clean_urls),
                    "exclude": sorted(args.exclude or [])},
        "truncated": truncated,
        "pages": pages,
        "robots": robots_info,
        "sitemaps": sitemap_list,
        "sitemap_urls": sorted(sitemap_urls),
    }
    if getattr(args, "label", None):
        snap["label"] = args.label
    return snap


# ---------------------------------------------------------------- diff

class UsageError(Exception):
    pass


def finding(rule, where, detail=""):
    return {"rule": rule, "severity": RULES[rule][0], "where": where, "detail": detail}


def show(value):
    if value is None:
        return "(none)"
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]" if value else "[]"
    text = str(value)
    return text if len(text) <= 90 else text[:87] + "..."


def diff_page(key, a, b, text_drop):
    out = []
    add = lambda rule, detail="": out.append(finding(rule, key, detail))
    # indexing controls
    if b["noindex"] and not a["noindex"]:
        add("NOINDEX_ADDED" if a["indexable"] else "ROBOTS_META_CHANGED", f"robots {show(a['robots'])} -> {show(b['robots'])}")
    elif a["noindex"] and not b["noindex"]:
        add("NOINDEX_REMOVED", f"robots {show(a['robots'])} -> {show(b['robots'])}")
    nofollow = lambda d: "nofollow" in d or "none" in d
    if nofollow(b["robots"]) and not nofollow(a["robots"]):
        add("NOFOLLOW_ADDED", f"robots {show(a['robots'])} -> {show(b['robots'])}")
    other = lambda d: sorted(set(d) - {"noindex", "nofollow", "none", "index", "follow", "all"})
    if other(a["robots"]) != other(b["robots"]):
        add("ROBOTS_META_CHANGED", f"{show(other(a['robots']))} -> {show(other(b['robots']))}")
    if b["blocked"] and not a["blocked"]:
        add("PAGE_NOW_BLOCKED")
    elif a["blocked"] and not b["blocked"]:
        add("PAGE_UNBLOCKED")
    # canonical
    if a["canonical"] != b["canonical"]:
        if b["canonical"] is None:
            add("CANONICAL_REMOVED", f"was {show(a['canonical'])}")
        elif a["canonical"] is None and b["canonical_self"]:
            add("CANONICAL_ADDED", show(b["canonical"]))
        elif a["canonical_self"] and not b["canonical_self"]:
            add("CANONICAL_NOW_ELSEWHERE", f"{show(a['canonical'])} -> {show(b['canonical'])}")
        else:
            add("CANONICAL_CHANGED", f"{show(a['canonical'])} -> {show(b['canonical'])}")
    # titles, descriptions, headings, language
    for field, removed, changed in (("title", "TITLE_REMOVED", "TITLE_CHANGED"),
                                    ("description", "DESCRIPTION_REMOVED", "DESCRIPTION_CHANGED")):
        if a[field] and not b[field]:
            add(removed, f"was \"{show(a[field])}\"")
        elif a[field] != b[field] and b[field]:
            add(changed, f"\"{show(a[field])}\" -> \"{show(b[field])}\"")
    if a["h1"] and not b["h1"]:
        add("H1_REMOVED", f"was \"{show(a['h1'][0])}\"")
    elif a["h1"] != b["h1"] and b["h1"]:
        add("H1_CHANGED", f"\"{show(a['h1'][0] if a['h1'] else None)}\" -> \"{show(b['h1'][0])}\"")
    if a["lang"] != b["lang"]:
        add("LANG_CHANGED", f"{show(a['lang'])} -> {show(b['lang'])}")
    # hreflang
    for code in sorted(set(a["hreflang"]) | set(b["hreflang"])):
        old, new = a["hreflang"].get(code), b["hreflang"].get(code)
        if old and not new:
            add("HREFLANG_REMOVED", f"{code} was {show(old)}")
        elif new and not old:
            add("HREFLANG_ADDED", f"{code} -> {show(new)}")
        elif old != new:
            add("HREFLANG_CHANGED", f"{code}: {show(old)} -> {show(new)}")
    # structured data
    if b["jsonld_invalid"] > a["jsonld_invalid"]:
        add("JSONLD_NOW_INVALID", f"invalid blocks {a['jsonld_invalid']} -> {b['jsonld_invalid']}")
    if a["jsonld_blocks"] and not b["jsonld_blocks"]:
        add("JSONLD_REMOVED", f"types were {show(a['jsonld_types'])}")
    else:
        gone = sorted(set(a["jsonld_types"]) - set(b["jsonld_types"]))
        new_types = sorted(set(b["jsonld_types"]) - set(a["jsonld_types"]))
        if gone:
            add("JSONLD_TYPE_REMOVED", show(gone))
        if new_types:
            add("JSONLD_TYPE_ADDED", show(new_types))
        if not gone and not new_types and a["jsonld_hash"] != b["jsonld_hash"] and b["jsonld_hash"]:
            add("JSONLD_CHANGED")
    # previews
    if a["og"] and not b["og"]:
        add("OG_REMOVED")
    elif a["og"] != b["og"]:
        changed = sorted(k for k in set(a["og"]) | set(b["og"]) if a["og"].get(k) != b["og"].get(k))
        add("OG_CHANGED", ", ".join(changed))
    # content and links
    if a["words"] and b["words"] < a["words"] * (1 - text_drop):
        add("TEXT_SHRANK", f"{a['words']} -> {b['words']} words")
    elif a["text_hash"] != b["text_hash"]:
        add("TEXT_CHANGED", f"{a['words']} -> {b['words']} words")
    if a["inlinks"] > 0 and b["inlinks"] == 0:
        add("PAGE_ORPHANED", f"linked from {a['inlinks']} page(s) before")
    return out


def diff(a, b, text_drop):
    out = []
    if a["options"] != b["options"]:
        out.append(finding("OPTIONS_DIFFER", "(snapshots)", f"{json.dumps(a['options'], sort_keys=True)} vs "
                                                           f"{json.dumps(b['options'], sort_keys=True)}"))
    for label, snap in (("old", a), ("new", b)):
        if snap.get("truncated"):
            out.append(finding("SCAN_LIMIT", f"({label} snapshot)"))
    old_pages, new_pages = a["pages"], b["pages"]
    for key in sorted(set(old_pages) - set(new_pages)):
        page = old_pages[key]
        rule = "PAGE_REMOVED" if page["indexable"] else "PAGE_REMOVED_NONINDEXABLE"
        out.append(finding(rule, key, f"file was {page['file']}"))
    for key in sorted(set(new_pages) - set(old_pages)):
        out.append(finding("PAGE_ADDED", key, "indexable" if new_pages[key]["indexable"] else "not indexable"))
    for key in sorted(set(old_pages) & set(new_pages)):
        out.extend(diff_page(key, old_pages[key], new_pages[key], text_drop))
    # robots.txt
    ra, rb = a.get("robots"), b.get("robots")
    if ra and not rb:
        out.append(finding("ROBOTS_FILE_REMOVED", "/robots.txt"))
    elif rb and not ra:
        out.append(finding("ROBOTS_FILE_ADDED", "/robots.txt"))
    if rb:
        newly = sorted(set(rb["blocks_all"]) - set(ra["blocks_all"] if ra else []))
        if newly:
            out.append(finding("ROBOTS_DISALLOW_ALL_NEW", "/robots.txt", f"user-agent {', '.join(newly)}"))
    if ra and rb and ra["lines"] != rb["lines"]:
        removed = [line for line in ra["lines"] if line not in rb["lines"]]
        added = [line for line in rb["lines"] if line not in ra["lines"]]
        detail = "; ".join([f"- {line}" for line in removed] + [f"+ {line}" for line in added]) or "order changed"
        out.append(finding("ROBOTS_RULES_CHANGED", "/robots.txt", detail))
    # sitemaps
    if a["sitemaps"] and not b["sitemaps"]:
        out.append(finding("SITEMAPS_GONE", "(sitemaps)", f"old: {', '.join(s['file'] for s in a['sitemaps'])}"))
    elif a["sitemaps"] and b["sitemaps"]:
        old_urls, new_urls = set(a["sitemap_urls"]), set(b["sitemap_urls"])
        out.extend(finding("SITEMAP_URL_REMOVED", url) for url in sorted(old_urls - new_urls))
        out.extend(finding("SITEMAP_URL_ADDED", url) for url in sorted(new_urls - old_urls))
    return out


# ---------------------------------------------------------------- CLI

def load_accept(path):
    """Approved changes: 'RULE_ID pattern' per line; the pattern is a glob on the finding's location."""
    accepted = []
    try:
        with open(path, encoding="utf-8") as f:
            for number, raw in enumerate(f, 1):
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2 or parts[0] not in RULES:
                    raise UsageError(f"{path}:{number}: expected 'RULE_ID path-or-glob', got: {line}")
                accepted.append((parts[0], parts[1].strip()))
    except OSError as exc:
        raise UsageError(f"cannot read --accept file: {exc}")
    return accepted


def is_accepted(f, accepted):
    return any(f["rule"] == rule and fnmatch.fnmatchcase(f["where"], pattern) for rule, pattern in accepted)


def load_side(value, args):
    if os.path.isdir(value):
        ns = argparse.Namespace(build=value, base_url=args.base_url, agent=args.agent, clean_urls=args.clean_urls,
                                robots=None, sitemap=None, exclude=args.exclude, max_files=args.max_files)
        return snapshot(ns), value
    try:
        with open(value, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read snapshot {value}: {exc}")
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise UsageError(f"{value} is not a {FORMAT} file; create one with the snapshot command")
    return data, value


def render_text(findings, accepted_count, a_name, b_name, a, b, limit):
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("error", "warn", "info")}
    lines = [f"seo_drift {VERSION}: {counts['error']} error(s), {counts['warn']} warning(s), {counts['info']} info"
             f" | old {a_name} ({len(a['pages'])} pages) -> new {b_name} ({len(b['pages'])} pages)"]
    if accepted_count:
        lines.append(f"{accepted_count} finding(s) matched --accept and are not shown")
    for severity in ("error", "warn", "info"):
        for rule in sorted({f["rule"] for f in findings if f["severity"] == severity}):
            group = [f for f in findings if f["rule"] == rule]
            lines.append(f"\n{severity.upper()} {rule} ({len(group)}): {RULES[rule][1]}")
            for f in group[:limit]:
                lines.append(f"  {f['where']}" + (f"   {f['detail']}" if f["detail"] else ""))
            if len(group) > limit:
                lines.append(f"  ... {len(group) - limit} more (use --json or --show)")
    if not findings:
        lines.append("No differences found.")
    return "\n".join(lines)


def add_snapshot_options(p):
    p.add_argument("--base-url", help="public origin, e.g. https://www.example.com (absolute canonicals become comparable)")
    p.add_argument("--agent", default="googlebot", help="robots.txt and meta robots agent to evaluate (default: googlebot)")
    p.add_argument("--clean-urls", action="store_true", help="pages are served without .html (about.html -> /about)")
    p.add_argument("--exclude", action="append", metavar="GLOB", help="skip files whose relative path matches (repeatable)")
    p.add_argument("--max-files", type=int, default=20000, help="stop reading HTML after this many files (default: 20000)")


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="seo_drift.py",
        description="Snapshot the search-relevant state of a built site and diff two snapshots. Read-only, offline.",
        epilog="Examples:\n"
               "  seo_drift.py snapshot dist/ --base-url https://www.example.com --out before.json\n"
               "  seo_drift.py diff before.json dist/ --base-url https://www.example.com\n"
               "  seo_drift.py diff before.json after.json --json --accept approved-changes.txt",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("--list-rules", action="store_true", help="list rule IDs with their severity and exit")
    sub = ap.add_subparsers(dest="command")

    sp = sub.add_parser("snapshot", help="record the state of a build folder as JSON")
    sp.add_argument("build", help="folder of built HTML pages (with robots.txt and sitemaps if present)")
    add_snapshot_options(sp)
    sp.add_argument("--robots", help="robots.txt to use (default: robots.txt in the build folder)")
    sp.add_argument("--sitemap", action="append", help="extra sitemap file outside the build folder (repeatable)")
    sp.add_argument("--label", help="free text stored in the snapshot, e.g. a commit or release id")
    sp.add_argument("--out", help="write the snapshot here instead of standard output")

    dp = sub.add_parser("diff", help="compare two snapshots, or a snapshot and a build folder")
    dp.add_argument("old", help="earlier snapshot JSON or build folder")
    dp.add_argument("new", help="later snapshot JSON or build folder")
    add_snapshot_options(dp)
    dp.add_argument("--text-drop", type=float, default=0.5,
                    help="share of visible words a page may lose before TEXT_SHRANK is a warning (default: 0.5; a review trigger to tune, not a search-engine number)")
    dp.add_argument("--ignore", default="", help="comma-separated rule IDs to skip")
    dp.add_argument("--accept", help="file of approved changes, one 'RULE_ID location-glob' per line, e.g. 'PAGE_NOW_BLOCKED /search*'")
    dp.add_argument("--fail-on", choices=["error", "warn", "info", "never"], default="error",
                    help="lowest severity that makes the exit code 1 (default: error)")
    dp.add_argument("--strict", action="store_true", help="same as --fail-on warn")
    dp.add_argument("--show", type=int, default=20, help="examples printed per rule in text output (default: 20)")
    dp.add_argument("--json", action="store_true", help="print JSON instead of text")
    return ap, ap.parse_args(argv)


def main(argv=None):
    ap, args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list_rules:
        for rule, (severity, text) in RULES.items():
            print(f"{rule:28s} {severity:5s}  {text}")
        return 0
    if not args.command:
        ap.print_usage(sys.stderr)
        print("seo_drift.py: error: choose a command: snapshot or diff", file=sys.stderr)
        return 2
    try:
        if args.max_files < 1:
            raise UsageError("--max-files must be at least 1")
        if args.command == "snapshot":
            data = json.dumps(snapshot(args), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
            if args.out:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(data)
                print(f"snapshot written to {args.out}", file=sys.stderr)
            else:
                sys.stdout.write(data)
            return 0
        if not 0 < args.text_drop < 1:
            raise UsageError("--text-drop must be between 0 and 1")
        ignore = {r.strip() for r in args.ignore.split(",") if r.strip()}
        unknown = sorted(ignore - set(RULES))
        if unknown:
            raise UsageError(f"unknown rule ID(s) in --ignore: {', '.join(unknown)}")
        accepted = load_accept(args.accept) if args.accept else []
        a, a_name = load_side(args.old, args)
        b, b_name = load_side(args.new, args)
    except UsageError as exc:
        print(f"seo_drift.py: error: {exc}", file=sys.stderr)
        return 2
    findings = [f for f in diff(a, b, args.text_drop) if f["rule"] not in ignore]
    kept = [f for f in findings if not is_accepted(f, accepted)]
    accepted_count = len(findings) - len(kept)
    fail_on = "warn" if args.strict else args.fail_on
    failed = any(RANK[f["severity"]] >= RANK[fail_on] for f in kept)
    if args.json:
        summary = {s: sum(1 for f in kept if f["severity"] == s) for s in ("error", "warn", "info")}
        summary.update({"accepted": accepted_count, "old": a_name, "new": b_name,
                        "old_pages": len(a["pages"]), "new_pages": len(b["pages"]), "fail_on": fail_on})
        print(json.dumps({"tool": "seo_drift", "version": VERSION, "summary": summary, "findings": kept},
                         indent=1, sort_keys=True, ensure_ascii=False))
    else:
        print(render_text(kept, accepted_count, a_name, b_name, a, b, max(args.show, 0)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
