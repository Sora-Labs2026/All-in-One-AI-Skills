#!/usr/bin/env python3
"""ProductCraft effect guard. Read-only, standard library, deterministic.

Scans web sources (HTML, CSS, SCSS, JS/TS, JSX/TSX, Vue, Svelte) for the
mistakes that most often ship with scroll reveals, loops, canvases and WebGL
effects. Each finding is a prompt to check, not a verdict. See
references/scroll-and-reveal-effects.md, references/css-craft-techniques.md and
../creative-media/references/webgl-backgrounds-and-3d.md.

  NO-REDUCED-MOTION  the scanned set animates but never mentions
                     prefers-reduced-motion (or motion-safe/motion-reduce,
                     reducedMotion); reported once, at the first animated file
  HIDDEN-BY-DEFAULT  a reveal-style CSS rule sets opacity: 0 or visibility:
                     hidden without a script or motion gate (html.js,
                     .motion-ok, :root[...], a no-preference media block)
  RAF-NO-STOP        requestAnimationFrame with no cancelAnimationFrame,
                     IntersectionObserver or visibilitychange in the file
  OBSERVER-LEAK      an observer is created but never disconnected or unobserved
  SCROLL-NO-CLEANUP  ScrollTrigger used with no kill/revert/context/useGSAP/matchMedia
  DPR-UNCAPPED       devicePixelRatio used on a line without a cap (Math.min,
                     clamp or a max* variable)
  POINTER-UNGATED    pointermove/mousemove listener in a file that never checks
                     a fine pointer (pointer: fine, hover: hover, pointerType)
  CANVAS-UNLABELLED  <canvas> without aria-hidden, role or aria-label
  LOOP-NO-PAUSE      an infinite CSS animation while the set never sets
                     animation-play-state (MOT-19 needs a pause)

Usage: effect_guard.py PATH [PATH ...] [--json] [--ignore RULE[,RULE]]
Exit codes: 0 nothing to review, 1 findings, 2 usage error (no readable input).
"""
import argparse
import json
import pathlib
import re
import sys

VERSION = "1.0.0"
EXTS = {".html", ".htm", ".css", ".scss", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "vendor"}
RULES = ["NO-REDUCED-MOTION", "HIDDEN-BY-DEFAULT", "RAF-NO-STOP", "OBSERVER-LEAK", "SCROLL-NO-CLEANUP",
         "DPR-UNCAPPED", "POINTER-UNGATED", "CANVAS-UNLABELLED", "LOOP-NO-PAUSE"]

ANIMATES = re.compile(r"@keyframes|\banimation\s*:|\btransition\s*:|requestAnimationFrame|\bgsap\.|ScrollTrigger"
                      r"|animation-timeline|getContext\(\s*['\"]webgl|WebGLRenderer|\.animate\(", re.I)
REDUCED = re.compile(r"prefers-reduced-motion|motion-safe:|motion-reduce:|reducedMotion", re.I)
REVEAL_SEL = re.compile(r"reveal|animate|enter|fade|motion|word|split|in-view|inview", re.I)
GATE_SEL = re.compile(r"(^|[\s,>])(html|:root)\b|\.js\b|\.motion-ok\b|\.has-motion\b|\[data-js\]|\.is-ready\b", re.I)
HIDES = re.compile(r"(?:^|;|\{)\s*(?:opacity\s*:\s*0(?:\.0+)?\s*(?:;|$|!)|visibility\s*:\s*hidden)", re.I)
DPR_CAP = re.compile(r"Math\.min|clamp|\bmax[A-Z_]\w*|MAX_DPR|maxDpr|maxPixelRatio", re.I)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def css_rules(text):
    """Yield (selector, body, start_index, media_stack) for innermost CSS blocks."""
    text = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), text, flags=re.S)
    stack, prelude_start = [], 0
    for i, ch in enumerate(text):
        if ch == "{":
            stack.append((text[prelude_start:i].strip(), i))
            prelude_start = i + 1
        elif ch == "}":
            if stack:
                sel, open_i = stack.pop()
                body = text[open_i + 1:i]
                if "{" not in body and not sel.startswith("@"):
                    yield sel, body, open_i, [s for s, _ in stack]
            prelude_start = i + 1
        elif ch == ";" and not stack:
            prelude_start = i + 1


def style_sources(name, text):
    """CSS text to check: whole file for stylesheets, <style> blocks for markup and components."""
    if pathlib.Path(name).suffix.lower() in {".css", ".scss"}:
        return [(text, 0)]
    return [(m.group(1), m.start(1)) for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S | re.I)]


def find(name, text):
    out = []

    def add(rule, idx, msg, snippet=""):
        out.append({"rule": rule, "file": name, "line": line_of(text, idx), "message": msg, "text": snippet.strip()[:120]})

    for css, offset in style_sources(name, text):
        for sel, body, idx, media in css_rules(css):
            if not REVEAL_SEL.search(sel) or not HIDES.search("{" + body):
                continue
            gated_media = any(re.search(r"prefers-reduced-motion\s*:\s*no-preference|@supports", m, re.I) for m in media)
            if not GATE_SEL.search(sel) and not gated_media:
                add("HIDDEN-BY-DEFAULT", offset + idx, "reveal start state hides content before script runs; gate it on a class set by script", sel)

    if "requestAnimationFrame" in text and not re.search(r"cancelAnimationFrame|IntersectionObserver|visibilitychange", text):
        add("RAF-NO-STOP", text.index("requestAnimationFrame"), "animation frames are requested but nothing stops or pauses them")
    for m in re.finditer(r"new\s+(IntersectionObserver|ResizeObserver|MutationObserver)\b", text):
        if not re.search(r"\.disconnect\(|\.unobserve\(", text):
            add("OBSERVER-LEAK", m.start(), f"{m.group(1)} is never disconnected or unobserved")
            break
    if "ScrollTrigger" in text and not re.search(r"\.kill\(|\.revert\(|gsap\.context|useGSAP|matchMedia\(", text):
        add("SCROLL-NO-CLEANUP", text.index("ScrollTrigger"), "ScrollTrigger instances are never killed or reverted")
    for m in re.finditer(r"[^\n]*devicePixelRatio[^\n]*", text):
        if not DPR_CAP.search(m.group(0)):
            add("DPR-UNCAPPED", m.start(), "cap devicePixelRatio (about 1.5 for soft fields, 2 for geometry)", m.group(0))
    pm = re.search(r"addEventListener\(\s*['\"](?:pointermove|mousemove)['\"]|on(?:Pointer|Mouse)Move\s*=", text)
    if pm and not re.search(r"pointer\s*:\s*fine|hover\s*:\s*hover|pointerType", text):
        add("POINTER-UNGATED", pm.start(), "pointer-follow effect without a fine-pointer check (MOT-18)")
    for m in re.finditer(r"<canvas\b[^>]*>", text, re.I):
        if not re.search(r"aria-hidden|role\s*=|aria-label", m.group(0), re.I):
            add("CANVAS-UNLABELLED", m.start(), "mark decorative canvases aria-hidden; label interactive ones", m.group(0))
    return out


def iter_files(paths):
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_file():
            if p.suffix.lower() in EXTS:
                yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in EXTS and not SKIP_DIRS.intersection(f.parts) \
                        and not f.name.endswith(".min.js"):
                    yield f


def scan(paths, ignore=()):
    files, findings, texts = [], [], {}
    for f in iter_files(paths):
        try:
            texts[str(f)] = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files.append(str(f))
    for name, text in texts.items():
        findings.extend(find(name, text))
    if texts and not any(REDUCED.search(t) for t in texts.values()):
        for name, text in texts.items():
            m = ANIMATES.search(text)
            if m:
                findings.append({"rule": "NO-REDUCED-MOTION", "file": name, "line": line_of(text, m.start()),
                                 "message": "motion found but no reduced-motion handling anywhere in the scanned files",
                                 "text": m.group(0)})
                break
    if not any("animation-play-state" in t for t in texts.values()):
        for name, text in texts.items():
            m = re.search(r"animation\s*:[^;{}]*\binfinite\b", text, re.I)
            if m:
                findings.append({"rule": "LOOP-NO-PAUSE", "file": name, "line": line_of(text, m.start()),
                                 "message": "infinite animation with no pause path; add a control and pause on hover/focus (MOT-19)",
                                 "text": m.group(0)[:120]})
                break
    findings = [f for f in findings if f["rule"] not in ignore]
    findings.sort(key=lambda f: (f["file"], f["line"], f["rule"]))
    return files, findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true", help="print machine-readable output")
    ap.add_argument("--ignore", default="", help="comma-separated rule names to skip")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    ignore = {r.strip().upper() for r in args.ignore.split(",") if r.strip()}
    unknown = ignore - set(RULES)
    if unknown:
        print(f"unknown rule(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    files, findings = scan(args.paths, ignore)
    if not files:
        print("no web source files found in the given paths", file=sys.stderr)
        return 2
    counts = {}
    for f in findings:
        counts[f["rule"]] = counts.get(f["rule"], 0) + 1
    if args.json:
        print(json.dumps({"version": VERSION, "files": len(files), "counts": dict(sorted(counts.items())),
                          "findings": findings}, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f"{f['rule']:18} {f['file']}:{f['line']}: {f['message']}" + (f"\n                   {f['text']}" if f["text"] else ""))
        print(f"{len(files)} file(s): " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing to review"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
