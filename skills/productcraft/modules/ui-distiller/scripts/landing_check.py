#!/usr/bin/env python3
"""ProductCraft landing-page markup check. Read-only, standard library, deterministic.

Reads built or hand-written HTML pages and reports ship-checklist gaps that are
visible in the markup. Each finding is a prompt to fix or to justify in the
report; see references/landing-pages.md, section 12.

  LANG            <html> has no lang attribute
  TITLE           no non-empty <title>
  META-DESC       no <meta name="description">
  SOCIAL          og:title or og:image missing
  NOINDEX         a robots meta tag says noindex (fine for campaign pages; decide on purpose)
  MAIN            no <main> landmark
  SKIP-LINK       no in-page link whose text starts with "Skip"
  H1-COUNT        not exactly one <h1>
  H1-LENGTH       the <h1> has more than --max-words words
  VAGUE-CTA       a button or link labeled only "Learn more", "Submit", "Get started" and similar
  HASH-LINK       a link whose href is just "#"
  IMG-ALT         an <img> without an alt attribute (use alt="" for decoration)
  IMG-SIZE        an <img> without width and height attributes or an inline aspect-ratio
  VIDEO-AUTOPLAY  an autoplaying <video> missing muted or playsinline
  REDUCED-MOTION  animation or transitions present but no prefers-reduced-motion rule

Usage: landing_check.py PAGE.html [PAGE.html ...] [--assets FILE ...] [--json] [--max-words 10]
--assets adds CSS or JS files whose text counts toward the REDUCED-MOTION check.
Exit codes: 0 nothing to review, 1 findings, 2 usage error (no readable page).
"""
import argparse
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

VERSION = "1.0.0"
VAGUE = {
    "learn more", "read more", "more", "submit", "get started", "start", "click here",
    "explore", "go", "discover", "find out more", "see more",
}
MOTION = re.compile(r"@keyframes|\banimation(?:-name)?\s*:|\btransition\s*:|\.animate\s*\(|\bgsap\.|requestAnimationFrame", re.I)
REDUCED = re.compile(r"prefers-reduced-motion", re.I)
WORD = re.compile(r"[\w'’-]+", re.U)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.findings = []
        self.html_lang = None
        self.saw_html = False
        self.title = ""
        self.in_title = False
        self.metas = []
        self.has_main = False
        self.h1 = []
        self.captures = []  # stack of [tag, attrs, text parts, line]
        self.links = []  # (href, text, line)
        self.buttons = []  # (text, line)

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        line = self.getpos()[0]
        if tag == "html":
            self.saw_html = True
            self.html_lang = a.get("lang", "").strip() or None
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "main" or a.get("role") == "main":
            self.has_main = True
        elif tag == "img":
            if "alt" not in a:
                self.add("IMG-ALT", line, f"image {a.get('src', '?')!r} has no alt attribute")
            style = a.get("style", "").lower()
            if not ("width" in a and "height" in a) and "aspect-ratio" not in style:
                self.add("IMG-SIZE", line, f"image {a.get('src', '?')!r} has no width and height; it can shift layout")
        elif tag == "video":
            if "autoplay" in a and not ("muted" in a and "playsinline" in a):
                self.add("VIDEO-AUTOPLAY", line, "autoplaying video needs muted and playsinline (and a pause control)")
        if tag in ("h1", "a", "button"):
            self.captures.append([tag, a, [], line])
        if tag == "input" and a.get("type", "").lower() in ("submit", "button"):
            self.buttons.append((a.get("value", "Submit" if a.get("type", "").lower() == "submit" else ""), line))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        for i in range(len(self.captures) - 1, -1, -1):
            if self.captures[i][0] == tag:
                ctag, a, parts, line = self.captures.pop(i)
                text = " ".join("".join(parts).split())
                if ctag == "h1":
                    self.h1.append((text, line))
                elif ctag == "a":
                    self.links.append((a.get("href"), text or a.get("aria-label", ""), line))
                else:
                    self.buttons.append((text or a.get("aria-label", ""), line))
                break

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        for cap in self.captures:
            cap[2].append(data)

    def add(self, rule, line, message):
        self.findings.append({"rule": rule, "line": line, "message": message})


def meta_value(metas, key, value):
    for m in metas:
        if m.get(key, "").lower() == value:
            return m.get("content", "")
    return None


def check(name, text, extra_text="", max_words=10):
    page = Page()
    page.feed(text)
    page.close()
    out = page.findings
    if page.saw_html and not page.html_lang:
        out.append({"rule": "LANG", "line": 1, "message": "<html> has no lang attribute"})
    if not page.title.strip():
        out.append({"rule": "TITLE", "line": 1, "message": "no non-empty <title>"})
    if not (meta_value(page.metas, "name", "description") or "").strip():
        out.append({"rule": "META-DESC", "line": 1, "message": "no meta description"})
    missing = [p for p in ("og:title", "og:image") if meta_value(page.metas, "property", p) is None]
    if missing:
        out.append({"rule": "SOCIAL", "line": 1, "message": "missing " + ", ".join(missing)})
    robots = meta_value(page.metas, "name", "robots") or ""
    if "noindex" in robots.lower():
        out.append({"rule": "NOINDEX", "line": 1, "message": "robots noindex is set; keep it only for campaign or time-boxed pages"})
    if not page.has_main:
        out.append({"rule": "MAIN", "line": 1, "message": "no <main> landmark"})
    if not any((h or "").startswith("#") and len(h) > 1 and t.lower().startswith("skip") for h, t, _ in page.links):
        out.append({"rule": "SKIP-LINK", "line": 1, "message": "no skip link to the main content"})
    if len(page.h1) != 1:
        out.append({"rule": "H1-COUNT", "line": page.h1[1][1] if len(page.h1) > 1 else 1,
                    "message": f"{len(page.h1)} <h1> elements; use exactly one"})
    for h_text, h_line in page.h1[:1]:
        words = len(WORD.findall(h_text))
        if words > max_words:
            out.append({"rule": "H1-LENGTH", "line": h_line, "message": f"headline has {words} words (max {max_words}): {h_text[:60]!r}"})
    for label, line in page.buttons + [(t, ln) for _, t, ln in page.links]:
        if label.strip().lower().rstrip(" →>.!") in VAGUE:
            out.append({"rule": "VAGUE-CTA", "line": line, "message": f"label {label.strip()!r} says nothing about the outcome"})
    for href, t, line in page.links:
        if href is not None and href.strip() == "#":
            out.append({"rule": "HASH-LINK", "line": line, "message": f"link {t[:40]!r} points at '#'"})
    pooled = text + "\n" + extra_text
    if MOTION.search(pooled) and not REDUCED.search(pooled):
        out.append({"rule": "REDUCED-MOTION", "line": 1, "message": "motion found but no prefers-reduced-motion rule"})
    for f in out:
        f["file"] = name
    return sorted(out, key=lambda f: (f["line"], f["rule"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check landing-page HTML for ship-checklist gaps (read-only).")
    ap.add_argument("pages", nargs="+", help="HTML files to check")
    ap.add_argument("--assets", nargs="*", default=[], help="CSS or JS files pooled into the reduced-motion check")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--max-words", type=int, default=10, help="headline word limit (default 10)")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    if args.max_words < 1:
        print("error: --max-words must be at least 1", file=sys.stderr)
        return 2
    extra = []
    for a in args.assets:
        try:
            extra.append(pathlib.Path(a).read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            print(f"error: cannot read asset {a}: {exc}", file=sys.stderr)
            return 2
    findings, read = [], 0
    for p in args.pages:
        path = pathlib.Path(p)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"warning: cannot read {p}: {exc}", file=sys.stderr)
            continue
        read += 1
        findings += check(str(path), text, "\n".join(extra), args.max_words)
    if not read:
        print("error: no readable page", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"version": VERSION, "pages": read, "findings": findings}, indent=2))
    elif findings:
        for f in findings:
            print(f"{f['file']}:{f['line']}: {f['rule']}: {f['message']}")
        print(f"{len(findings)} finding(s) in {read} page(s)")
    else:
        print(f"OK: nothing to review in {read} page(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
