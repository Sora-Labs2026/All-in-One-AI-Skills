#!/usr/bin/env python3
"""ProductCraft render-contract lint for animation code. Read-only; standard library only.

Scans HTML, JavaScript, TypeScript and CSS for things that make rendered frames
differ from run to run or impossible to seek, so that every frame stays a pure
function of time:

  error  CLOCK          wall-clock reads: Date.now(), new Date(), performance.now()
  error  RANDOM         unseeded randomness: Math.random(), crypto.getRandomValues(), crypto.randomUUID()
  warn   TIMER          setTimeout / setInterval driving state
  warn   DELTA-CLOCK    THREE.Clock, getDelta(), getElapsedTime()
  warn   AUTOPLAY       <video> or <audio> with autoplay (seek media to t instead)
  warn   CSS-TRANSITION CSS transitions (start only on a style change; hard to seek)
  warn   GSAP-UNSEEKED  GSAP used, but no paused timeline, seek(), progress() or globalTimeline control
  warn   FONT-WAIT      web fonts declared, but no document.fonts.ready or fonts.load() wait
  warn   NO-FRAME-HOOK  no way to freeze a frame: a ?t= / ?frame= parameter, a render/seek hook
                        or Remotion's useCurrentFrame()

Silence a line that is deliberate (profiling, a preview-only path) with a
comment containing `motion-ok` on that line. Comment-only lines are skipped.

Usage:
  motion_contract_check.py PATH [PATH ...] [--json] [--errors-only]

PATH may be a file or a folder (searched recursively; node_modules, dist and
build folders and dot-folders are skipped). Output is sorted and deterministic.
Exit codes: 0 clean, 1 findings, 2 usage error (no readable input).
A clean result does not prove determinism: render one frame twice and compare
the hashes.
"""
import argparse
import json
import pathlib
import re
import sys

VERSION = "1.0.0"
EXTS = {".html", ".htm", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".css", ".vue", ".svelte"}
SKIP_DIRS = {"node_modules", "dist", "build", "out", ".git", "__pycache__", "coverage"}

LINE_RULES = [
    ("CLOCK", "error", re.compile(r"\bDate\.now\s*\(|\bnew\s+Date\s*\(\s*\)|\bperformance\.now\s*\("),
     "wall-clock time; derive every visible value from the frame time t"),
    ("RANDOM", "error", re.compile(r"\bMath\.random\s*\(|\bcrypto\.getRandomValues\s*\(|\bcrypto\.randomUUID\s*\("),
     "unseeded randomness; use one seeded generator"),
    ("TIMER", "warn", re.compile(r"\bset(?:Timeout|Interval)\s*\("),
     "timer fires by wall-clock; derive the state from t instead"),
    ("DELTA-CLOCK", "warn", re.compile(r"\bnew\s+(?:THREE\.)?Clock\s*\(|\.getDelta\s*\(|\.getElapsedTime\s*\("),
     "delta clock; pass t to every update instead"),
    ("AUTOPLAY", "warn", re.compile(r"<(?:video|audio)\b[^>]*\bautoplay\b", re.I),
     "autoplaying media drifts from the frame clock; set currentTime from t and await 'seeked'"),
]
CSS_TRANSITION = re.compile(r"(?:^|[\s;{\"'])transition\s*:\s*(?!\s*none\b)", re.I)
GSAP_USE = re.compile(r"\bgsap\.(?:to|from|fromTo|timeline|set)\s*\(")
GSAP_SEEK = re.compile(r"paused\s*:\s*true|\.seek\s*\(|\.progress\s*\(|\.totalTime\s*\(|\.time\s*\(|globalTimeline")
FONT_DECL = re.compile(r"@font-face|fonts\.googleapis\.com|new\s+FontFace\s*\(", re.I)
FONT_WAIT = re.compile(r"document\.fonts\.(?:ready|load)\b|\bloadFont\s*\(|\bdelayRender\s*\(")
FRAME_HOOK = re.compile(
    r"""searchParams\.get\(\s*['"](?:t|time|frame|f)['"]\s*\)"""
    r"|URLSearchParams[^\n]*['\"](?:t|time|frame)['\"]"
    r"|\b(?:window\.)?(?:renderFrame|seekTo|seekFrame|setFrame|setTime|__seek|__setTime|__renderFrame)\s*[=(]"
    r"|\buseCurrentFrame\s*\("
)
COMMENT_ONLY = re.compile(r"^\s*(?://|/\*|\*|<!--)")


def iter_files(paths):
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                rel = f.relative_to(p).parts
                if any(part in SKIP_DIRS or (part.startswith(".") and part not in (".", "..")) for part in rel[:-1]):
                    continue
                if f.is_file() and f.suffix.lower() in EXTS:
                    yield f


def scan_text(name, text):
    """Return (findings, facts) for one file; facts feed the project-level checks."""
    findings = []
    is_css = name.lower().endswith(".css")
    for n, line in enumerate(text.splitlines(), 1):
        if "motion-ok" in line or COMMENT_ONLY.match(line):
            continue
        for rule, sev, rx, msg in LINE_RULES:
            if not is_css and rx.search(line):
                findings.append({"file": name, "line": n, "rule": rule, "severity": sev, "message": msg,
                                 "text": line.strip()[:120]})
        if CSS_TRANSITION.search(line) and (is_css or "<style" in text or "style=" in line or ".style." in line):
            findings.append({"file": name, "line": n, "rule": "CSS-TRANSITION", "severity": "warn",
                             "message": "CSS transitions start on a style change and are hard to seek; use keyframed "
                                        "animations seeked through document.getAnimations(), or values computed from t",
                             "text": line.strip()[:120]})
    live = "\n".join(l for l in text.splitlines() if "motion-ok" not in l and not COMMENT_ONLY.match(l))
    facts = {
        "gsap_use": bool(GSAP_USE.search(live)),
        "gsap_seek": bool(GSAP_SEEK.search(live)),
        "font_decl": bool(FONT_DECL.search(live)),
        "font_wait": bool(FONT_WAIT.search(live)),
        "frame_hook": bool(FRAME_HOOK.search(live)),
        "code": not is_css,
    }
    return findings, facts


def check(paths):
    files = list(iter_files(paths))
    findings, facts = [], []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found, fact = scan_text(str(f), text)
        findings += found
        facts.append((str(f), fact))
    if facts:
        first = facts[0][0]
        any_ = lambda k: any(fa[k] for _, fa in facts)  # noqa: E731
        if any_("gsap_use") and not any_("gsap_seek"):
            where = next(n for n, fa in facts if fa["gsap_use"])
            findings.append({"file": where, "line": 0, "rule": "GSAP-UNSEEKED", "severity": "warn",
                             "message": "GSAP tweens play on the wall clock; create timelines with paused: true and "
                                        "seek(t), or pause gsap.globalTimeline and seek it", "text": ""})
        if any_("font_decl") and not any_("font_wait"):
            where = next(n for n, fa in facts if fa["font_decl"])
            findings.append({"file": where, "line": 0, "rule": "FONT-WAIT", "severity": "warn",
                             "message": "web fonts are declared but nothing waits for them; await document.fonts.ready "
                                        "before frame 0", "text": ""})
        if any_("code") and not any_("frame_hook"):
            findings.append({"file": first, "line": 0, "rule": "NO-FRAME-HOOK", "severity": "warn",
                             "message": "no way to freeze an exact frame; read ?t= or ?frame= from the URL or expose "
                                        "window.renderFrame(n)", "text": ""})
    findings.sort(key=lambda x: (x["file"], x["line"], x["rule"]))
    return files, findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="files or folders to scan")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--errors-only", action="store_true", help="report only errors")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)
    files, findings = check(args.paths)
    if not files:
        print("no HTML, JS, TS or CSS files found in the given paths", file=sys.stderr)
        return 2
    if args.errors_only:
        findings = [f for f in findings if f["severity"] == "error"]
    errors = sum(f["severity"] == "error" for f in findings)
    if args.json:
        print(json.dumps({"version": VERSION, "files": len(files), "errors": errors,
                          "warnings": len(findings) - errors, "findings": findings}, indent=2))
    else:
        for f in findings:
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            print(f"{f['severity'].upper():5} {f['rule']:14} {loc}: {f['message']}" + (f"\n      {f['text']}" if f["text"] else ""))
        print(f"{len(files)} file(s): {errors} error(s), {len(findings) - errors} warning(s)"
              + ("" if findings else " - clean (still hash one frame rendered twice)"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
