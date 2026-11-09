#!/usr/bin/env python3
"""ProductCraft generic-UI tell scanner. Read-only, standard library, deterministic.

Scans HTML, CSS, SCSS, JSX/TSX, Vue and Svelte sources for interface patterns
that read as generated rather than designed, and that can be found in code.
Each finding is a prompt to decide, not a verdict: keep a pattern when the
product has a written reason. See references/generic-tells-and-fixes.md.

  GRADIENT-BG       gradient fills (CSS gradients, Tailwind bg-gradient-*)
  HEADLINE-PERIOD   two or more h1-h3 headings that end with a period
  HEADLINE-EMOJI    emoji inside h1-h3 headings
  ALL-CAPS          text-transform: uppercase / `uppercase` class, more than --caps-max times
  CODE-EYEBROW      fake-code breadcrumbs in visible text, such as "// data products"
  SECTION-NUMBER    "01 /" style section numbering in visible text
  AI-LABEL          "Powered by AI", "AI-powered" and similar labels
  SCALE-ZERO        animations that start from scale(0) (start popovers near 0.95)
  BOUNCE-EASING     cubic-bezier curves that overshoot (y outside 0..1)
  SLOW-MOTION       transition or animation durations above --max-ms (default 500)
  SPLIT-OTP         four or more maxlength="1" inputs in one file (breaks paste
                    and screen readers; use one input with autocomplete="one-time-code")
  OTP-AUTOCOMPLETE  a code input without autocomplete="one-time-code"

Usage: tell_scan.py PATH [PATH ...] [--json] [--max-ms 500] [--caps-max 3]
Exit codes: 0 nothing to review, 1 findings, 2 usage error (no readable input).
"""
import argparse
import json
import pathlib
import re
import sys

VERSION = "1.0.0"
EXTS = {".html", ".htm", ".css", ".scss", ".sass", ".less", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".astro", ".mdx"}
SKIP_DIRS = {"node_modules", "dist", "build", "out", ".git", ".next", "coverage", "vendor"}

HEADING = re.compile(r"<h([1-3])\b[^>]*>(.*?)</h\1>", re.I | re.S)
TAGS = re.compile(r"<[^>]+>|\{[^{}]*\}")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✨]")
LINE_RULES = [
    ("GRADIENT-BG", re.compile(r"(?:linear|radial|conic)-gradient\s*\(|\bbg-gradient-to-[a-z]+\b"),
     "gradient fill; prefer a solid surface and one accent unless the gradient carries meaning"),
    ("CODE-EYEBROW", re.compile(r">\s*//\s*[A-Za-z][\w -]{2,40}<"),
     "fake-code breadcrumb in visible text; use a plain heading"),
    ("SECTION-NUMBER", re.compile(r">\s*0\d\s*(?:/|—|–|\.|-)\s*[A-Za-z]"),
     "numbered section label; number only real sequences"),
    ("AI-LABEL", re.compile(r"\bpowered by ai\b|\bai[- ]powered\b|\bai[- ]driven\b|\bmagic ai\b", re.I),
     "generic AI label; say what the feature does instead"),
    ("SCALE-ZERO", re.compile(r"scale\(\s*0(?:\.0+)?\s*\)|\bscale\s*:\s*0(?:\.0+)?\s*[,;}]|\bscale-0\b"),
     "animation from scale 0; start popovers and menus near 0.95"),
]
BEZIER = re.compile(r"cubic-bezier\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")
DURATION = re.compile(r"(?:transition|animation)(?:-duration)?\s*:[^;{}]*?(\d+(?:\.\d+)?)(ms|s)\b|\bduration-(\d{3,4})\b")
CAPS = re.compile(r"text-transform\s*:\s*uppercase|(?<![\w-])uppercase(?![\w-])")
ONE_CHAR = re.compile(r"<input\b[^>]*\bmax[lL]ength\s*=\s*[\"'{]?\s*1\b", re.I)
CODE_INPUT = re.compile(r"<input\b[^>]*(?:\bname\s*=\s*[\"'](?:otp|code|one[-_]?time[-_]?code|verification[-_]?code)[\"'])[^>]*>", re.I)


def iter_files(paths):
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if any(part in SKIP_DIRS for part in f.relative_to(p).parts[:-1]):
                    continue
                if f.is_file() and f.suffix.lower() in EXTS:
                    yield f


def find(name, text, max_ms, caps_max):
    out = []
    lines = text.splitlines()

    def add(rule, line, msg, snippet=""):
        out.append({"file": name, "line": line, "rule": rule, "message": msg, "text": snippet.strip()[:100]})

    for n, line in enumerate(lines, 1):
        for rule, rx, msg in LINE_RULES:
            if rx.search(line):
                add(rule, n, msg, line)
        for m in BEZIER.finditer(line):
            y1, y2 = float(m.group(2)), float(m.group(4))
            if not (0 <= y1 <= 1 and 0 <= y2 <= 1):
                add("BOUNCE-EASING", n, "overshooting curve; keep bounce for playful moments, not everyday UI", m.group(0))
        for m in DURATION.finditer(line):
            if m.group(3):
                ms = float(m.group(3))
            else:
                ms = float(m.group(1)) * (1000 if m.group(2) == "s" else 1)
            if ms > max_ms:
                add("SLOW-MOTION", n, f"{ms:g} ms is slow for interface motion; menus 150-250 ms, larger moves up to about 500 ms", line)

    def line_of(pos):
        return text.count("\n", 0, pos) + 1

    periods = []
    for m in HEADING.finditer(text):
        inner = " ".join(TAGS.sub(" ", m.group(2)).split())
        if EMOJI.search(inner):
            add("HEADLINE-EMOJI", line_of(m.start()), "emoji in a heading; use words", inner)
        if inner.endswith(".") and not inner.endswith("..."):
            periods.append((line_of(m.start()), inner))
    if len(periods) >= 2:
        for ln, inner in periods:
            add("HEADLINE-PERIOD", ln, f"{len(periods)} headings end with a period; drop it unless the whole voice is sentence-like", inner)

    caps = [line_of(m.start()) for m in CAPS.finditer(text)]
    if len(caps) > caps_max:
        add("ALL-CAPS", caps[0], f"uppercase used {len(caps)} times (lines {', '.join(map(str, caps[:8]))}); keep caps for a few short labels")

    singles = [line_of(m.start()) for m in ONE_CHAR.finditer(text)]
    if len(singles) >= 4:
        add("SPLIT-OTP", singles[0], f"{len(singles)} one-character inputs; use one input with autocomplete=\"one-time-code\" "
                                     "and inputmode=\"numeric\" so paste and screen readers work")
    for m in CODE_INPUT.finditer(text):
        if "one-time-code" not in m.group(0):
            add("OTP-AUTOCOMPLETE", line_of(m.start()), "code input without autocomplete=\"one-time-code\"", m.group(0))
    return out


def scan(paths, max_ms=500, caps_max=3):
    files = list(iter_files(paths))
    findings = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings += find(str(f), text, max_ms, caps_max)
    findings.sort(key=lambda x: (x["file"], x["line"], x["rule"]))
    return files, findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-ms", type=float, default=500, help="slowest interface duration before flagging (default 500)")
    ap.add_argument("--caps-max", type=int, default=3, help="uppercase uses allowed per file (default 3)")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    files, findings = scan(args.paths, args.max_ms, args.caps_max)
    if not files:
        print("no HTML, CSS or component files found in the given paths", file=sys.stderr)
        return 2
    counts = {}
    for f in findings:
        counts[f["rule"]] = counts.get(f["rule"], 0) + 1
    if args.json:
        print(json.dumps({"version": VERSION, "files": len(files), "counts": dict(sorted(counts.items())),
                          "findings": findings}, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f"{f['rule']:16} {f['file']}:{f['line']}: {f['message']}" + (f"\n                 {f['text']}" if f["text"] else ""))
        summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing to review"
        print(f"{len(files)} file(s): {summary}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
